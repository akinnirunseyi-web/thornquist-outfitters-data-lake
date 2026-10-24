"""Offline checks. These do not constitute an AWS execution or clean-lab proof."""
import contextlib
import copy
import csv
import hashlib
import io
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import clean_lab as lab
import glue_sales_etl as etl


def local_validation(order_bytes):
    with (ROOT / "data" / lab.CUSTOMER_FILE).open(newline="") as source:
        customers_input = list(csv.DictReader(source))
    customers, bad_customers, customer_counts = etl.validate_customers(customers_input, "customer_extract.csv")
    lookup = {etl.norm_id(x["record"]["cust_num"]): x["record"] for x in customers}
    pos, bad_pos, pos_counts = etl.validate_sales(etl.read_csv_text((ROOT / "data" / lab.POS_FILE).read_text()), lab.POS_FILE, set(lookup), "pos")
    orders, bad_orders, order_counts = etl.validate_sales(json.loads(order_bytes), "controlled_copy.json", set(lookup), "ecommerce")
    lines, reconciled, total_rejects = etl.build_sales_model(pos, orders, lookup)
    bad_orders += total_rejects
    order_counts["records_trusted"] = len(reconciled)
    order_counts["records_quarantined"] = len(bad_orders)
    summary = {"execution_mode": "aws_glue", "validation": {"customers": dict(customer_counts), "pos_sales": dict(pos_counts), "ecommerce_orders": dict(order_counts)}, "sales_model": {"rows_written": len(lines)}}
    return lines, bad_orders, summary


class SourceAndGateTests(unittest.TestCase):
    def test_landing_catalog_preserves_original_pos_identifiers(self):
        config = lab.Config("470551642447", "catalogcheck")
        tables = {table["Name"]: table for table in lab.catalog_tables(config)}
        landing = tables["landing_pos"]
        self.assertEqual(landing["StorageDescriptor"]["Location"], config.uri("landing/pos/"))
        self.assertEqual(landing["Parameters"]["skip.header.line.count"], "1")
        types = {col["Name"]: col["Type"] for col in landing["StorageDescriptor"]["Columns"]}
        self.assertTrue(all(types[name] == "string" for name in ("transaction_id", "store_id", "cust_num")))
        self.assertIn("landing_pos", (ROOT / "queries/09_landing_pos_count.sql").read_text())

    def test_original_sources_and_bad_corrected_glue_rules(self):
        original = (ROOT / "data" / lab.ECOM_FILE).read_bytes()
        lab.validate_inputs()
        bad, corrected = lab.quality_variants()
        self.assertEqual(corrected, original)
        for variant, payload, expected_lines in (("bad", bad, 0), ("corrected", corrected, 4)):
            lines, rejects, report = local_validation(payload)
            lab.check_summary(report, variant)
            lab.check_gate_rejects(rejects, variant)
            target = [line for line in lines if line["order_id"] == lab.DEMO_ORDER]
            self.assertEqual(len(target), expected_lines)
            self.assertFalse(any(line["quantity"] <= 0 for line in lines))
            if variant == "corrected":
                self.assertEqual(sum(Decimal(line["line_amount"]) for line in lines), Decimal("320570.35"))
        self.assertEqual((ROOT / "data" / lab.ECOM_FILE).read_bytes(), original)

    def test_quality_failure_is_not_treated_as_promotion(self):
        _, rejects, summary = local_validation(lab.quality_variants()[0])
        wrong = copy.deepcopy(summary)
        wrong["validation"]["ecommerce_orders"]["records_quarantined"] = 39
        with self.assertRaisesRegex(RuntimeError, "Quality count mismatch"):
            lab.check_summary(wrong, "bad")
        with self.assertRaisesRegex(RuntimeError, "missing or repeated"):
            lab.check_gate_rejects([], "bad")
        with self.assertRaisesRegex(RuntimeError, "still quarantined"):
            lab.check_gate_rejects(rejects, "corrected")

    def test_preview_needs_no_aws_sdk_or_session(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            status = lab.main(["--expected-account", "470551642447", "--run-label", "preview01"])
        self.assertEqual(status, 0)
        self.assertIn("no AWS calls were made", buffer.getvalue())

    def test_names_reject_sql_or_path_injection(self):
        for value in ("demo;drop", "../demo", "DEMO", "a-b", "a" * 21):
            with self.assertRaises(ValueError):
                lab.Config("470551642447", value)

    def test_sources_fail_checksum_validation_if_edited(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            for name in (lab.POS_FILE, lab.CUSTOMER_FILE, lab.ECOM_FILE, "source_manifest.json"):
                (root / "data" / name).write_bytes((ROOT / "data" / name).read_bytes())
            (root / "data" / lab.ECOM_FILE).write_bytes(b"[]")
            with patch.object(lab, "ROOT", root), self.assertRaisesRegex(RuntimeError, "Source size changed"):
                lab.validate_inputs()

    def test_lambda_preserves_event_source_bytes(self):
        s3 = MagicMock()
        payload = (ROOT / "data" / lab.ECOM_FILE).read_bytes()
        s3.get_object.return_value = {"Body": io.BytesIO(payload)}
        fake_boto3 = types.SimpleNamespace(client=lambda service: s3)
        with patch.dict(sys.modules, {"boto3": fake_boto3}), patch.dict(os.environ, {"BUCKET_NAME": "isolated-test-bucket"}):
            spec = importlib.util.spec_from_file_location("lambda_under_test", ROOT / "scripts/lambda_function.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = module.lambda_handler({"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Put", "s3": {"bucket": {"name": "isolated-test-bucket"}, "object": {"key": "landing/ecommerce/ecommerce_orders.json"}}}]}, None)
        self.assertEqual(result["processed_files"], 1)
        written = s3.put_object.call_args.kwargs
        self.assertEqual(written["Body"], payload)
        self.assertEqual(written["Key"], "raw/ecommerce/ecommerce_orders.json")
        self.assertEqual(written["Metadata"]["source-sha256"], lab.validate_inputs()[lab.ECOM_FILE]["sha256"])

    def test_dashboard_uses_segment_results_and_escapes_labels(self):
        row = {"source_system": "pos", "sales_region": "Ontario", "category": "Gear <script>", "loyalty_tier": "Gold", "product_name": "Boots", "store_name": "Store 1", "total_sales": "10.00", "identified_customers": "1", "transactions": "2", "average_transaction_value": "5.00"}
        names = ("01_daily_sales", "02_regional_sales", "03a_top_products", "03b_category_sales", "04_loyalty_sales", "05_store_sales")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "analytics.html"
            lab.write_dashboard(destination, lab.Config("470551642447", "chartcheck"), {name: [row] for name in names}, {name: "qid-" + name for name in names})
            content = destination.read_text()
        self.assertIn("Gold generated the most revenue (10.00)", content)
        self.assertIn("Gear &lt;script&gt;", content)
        self.assertNotIn("Gear <script>", content)


class FakeSession:
    def __init__(self):
        self.clients = {name: MagicMock() for name in ("sts", "s3", "lambda", "glue", "athena")}

    def client(self, name, **kwargs):
        return self.clients[name]


class RunnerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.patches = (patch.object(lab, "ROOT", self.root), patch.object(lab, "fingerprint", return_value="test-bundle"))
        for item in self.patches:
            item.start()
        self.session = FakeSession()
        self.c = lab.Config("470551642447", "safety01")
        self.runner = lab.Runner(self.c, self.root / "state.json", self.session)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_account_mismatch_stops_before_any_s3_call(self):
        self.session.clients["sts"].get_caller_identity.return_value = {"Account": "111111111111"}
        with self.assertRaisesRegex(RuntimeError, "Account mismatch"):
            self.runner.preflight()
        self.assertFalse(self.session.clients["s3"].mock_calls)

    def test_owned_existing_bucket_is_not_recreated(self):
        self.session.clients["sts"].get_caller_identity.return_value = {"Account": self.c.account}
        self.session.clients["athena"].get_work_group.return_value = {"WorkGroup": {"State": "ENABLED", "Configuration": {}}}
        self.session.clients["s3"].list_buckets.return_value = {"Buckets": [{"Name": self.c.bucket}]}
        with self.assertRaisesRegex(RuntimeError, "already belongs"):
            self.runner.preflight()
        self.session.clients["s3"].create_bucket.assert_not_called()

    def test_existing_ctas_output_is_never_deleted_or_reused(self):
        self.runner.absent = MagicMock()
        self.session.clients["s3"].list_objects_v2.return_value = {"Contents": [{"Key": "curated/sales/old.parquet"}]}
        with self.assertRaisesRegex(RuntimeError, "not empty"):
            self.runner.query("ctas", "CREATE TABLE x AS SELECT 1", ctas=True)
        self.session.clients["athena"].start_query_execution.assert_not_called()
        self.session.clients["s3"].delete_object.assert_not_called()
        self.session.clients["s3"].delete_objects.assert_not_called()

    def test_interrupted_resource_creation_is_not_repeated(self):
        self.runner.state["steps"]["create resource"] = {"state": "STARTED"}
        action = MagicMock()
        with self.assertRaisesRegex(RuntimeError, "may already exist"):
            self.runner.step("create resource", action)
        action.assert_not_called()

    def test_select_and_show_results_keep_first_real_row(self):
        athena = self.session.clients["athena"]
        athena.start_query_execution.return_value = {"QueryExecutionId": "qid-1"}
        athena.get_query_execution.return_value = {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}}
        for name, header in (("select_check", True), ("show_check", False)):
            data = [{"Data": [{"VarCharValue": "sale_year=2026/sale_month=08"}]}]
            if header:
                data.insert(0, {"Data": [{"VarCharValue": "partition"}]})
            athena.get_query_results.return_value = {"ResultSet": {"ResultSetMetadata": {"ColumnInfo": [{"Name": "partition"}]}, "Rows": data}}
            values = self.runner.query(name, "SHOW PARTITIONS demo.curated_sales")
            self.assertEqual(values, [{"partition": "sale_year=2026/sale_month=08"}])

    def test_quality_report_failure_blocks_curated_creation(self):
        self.runner.provision = MagicMock()
        self.runner.ingest = MagicMock()
        self.runner.crawl = MagicMock()
        self.runner.run_job = MagicMock()
        self.runner.read_json = MagicMock(return_value={"execution_mode": "aws_glue", "validation": {"customers": {"records_seen": 401}}})
        self.session.clients["glue"].get_table.return_value = {"Table": {"StorageDescriptor": {"Columns": [{"Name": name, "Type": "string"} for name in ("transaction_id", "store_id", "cust_num")]}}}
        self.runner.query = MagicMock(side_effect=[
            [{"records": "1051"}],
            [{"table_name": "raw_pos", "records": "1051"}, {"table_name": "raw_customers", "records": "400"}, {"table_name": "raw_ecommerce_ndjson", "records": "265"}],
            [{"cust_num": "0000000"}],
        ])
        with patch.object(lab, "render_sql", return_value="SELECT 1"), self.assertRaisesRegex(RuntimeError, "Quality count mismatch"):
            self.runner.run_pipeline()
        self.assertNotIn("create_curated_sales", [call.args[0] for call in self.runner.query.call_args_list])

    def test_concurrent_rejection_waits_then_uses_one_queued_run(self):
        glue = self.session.clients["glue"]
        rejected = RuntimeError("Concurrent runs exceeded")
        rejected.response = {"Error": {"Code": "ConcurrentRunsExceededException"}}
        glue.start_job_run.side_effect = [rejected, {"JobRunId": "jr_queued"}]
        glue.get_job_run.side_effect = [
            {"JobRun": {"JobRunState": "WAITING"}},
            {"JobRun": {"JobRunState": "SUCCEEDED"}},
        ]
        with patch.object(lab.time, "sleep"):
            self.runner.run_job("corrected gate", "new-sales-job", {"--REPORTS_S3_PATH": "s3://new/reports/"})
        self.assertEqual(glue.start_job_run.call_count, 2)
        self.assertTrue(all(call.kwargs["JobRunQueuingEnabled"] for call in glue.start_job_run.call_args_list))
        self.assertEqual(self.runner.state["jobs"]["corrected gate"]["run_id"], "jr_queued")
        self.assertEqual(json.loads(self.runner.path.read_text())["jobs"]["corrected gate"]["submission"], "SUBMITTED")

    def test_definitive_concurrency_rejection_can_resume(self):
        self.runner.state["jobs"]["corrected gate"] = {"job": "new-sales-job", "arguments": {}, "submission": "REJECTED_CONCURRENCY"}
        glue = self.session.clients["glue"]
        glue.start_job_run.return_value = {"JobRunId": "jr_resumed"}
        glue.get_job_run.return_value = {"JobRun": {"JobRunState": "SUCCEEDED"}}
        self.runner.run_job("corrected gate", "new-sales-job", {})
        glue.start_job_run.assert_called_once()
        self.assertEqual(self.runner.state["jobs"]["corrected gate"]["run_id"], "jr_resumed")

    def test_unknown_submission_result_does_not_submit_a_duplicate(self):
        glue = self.session.clients["glue"]
        glue.start_job_run.side_effect = RuntimeError("Connection lost before response")
        with self.assertRaisesRegex(RuntimeError, "Connection lost"):
            self.runner.run_job("corrected gate", "new-sales-job", {})
        self.assertEqual(self.runner.state["jobs"]["corrected gate"]["submission"], "STARTED")
        with self.assertRaisesRegex(RuntimeError, "inspect AWS"):
            self.runner.run_job("corrected gate", "new-sales-job", {})
        self.assertEqual(glue.start_job_run.call_count, 1)

    def test_s3_event_retry_reuploads_identical_landing_bytes(self):
        clock = [0]
        copied = [False]
        body = b'[{"order_id": 1}]'
        s3 = self.session.clients["s3"]
        missing = RuntimeError("missing")
        missing.response = {"Error": {"Code": "NoSuchKey"}}
        def get_object(**kwargs):
            if not copied[0]:
                raise missing
            return {"Body": io.BytesIO(body), "Metadata": {"source-sha256": hashlib.sha256(body).hexdigest()}, "LastModified": "offline-test"}
        def put_object(**kwargs):
            self.assertEqual(kwargs["Key"], "landing/ecommerce/ecommerce_orders.json")
            self.assertEqual(kwargs["Body"], body)
            copied[0] = True  # Simulated S3 event delivery after the genuine PUT.
            return {}
        s3.get_object.side_effect = get_object
        s3.put_object.side_effect = put_object
        with patch.object(lab.time, "monotonic", side_effect=lambda: clock[0]), patch.object(lab.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
            self.runner.wait_for_lambda_copy("ecommerce_orders.json", body)
        s3.put_object.assert_called_once()
        self.session.clients["lambda"].invoke.assert_not_called()
        self.assertEqual(len(self.runner.state["s3_event_reuploads"]), 1)

    def test_s3_copy_checksum_failure_is_not_hidden_by_reupload(self):
        body = b'[]'
        s3 = self.session.clients["s3"]
        s3.get_object.return_value = {"Body": io.BytesIO(body), "Metadata": {"source-sha256": "wrong"}}
        with self.assertRaisesRegex(RuntimeError, "SHA metadata"):
            self.runner.wait_for_lambda_copy("ecommerce_orders.json", body)
        s3.put_object.assert_not_called()

    def test_s3_event_wait_is_bounded_and_never_writes_raw(self):
        clock = [0]
        missing = RuntimeError("missing")
        missing.response = {"Error": {"Code": "NoSuchKey"}}
        s3 = self.session.clients["s3"]
        s3.get_object.side_effect = missing
        with patch.object(lab.time, "monotonic", side_effect=lambda: clock[0]), patch.object(lab.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
            with self.assertRaisesRegex(RuntimeError, "10 minutes"):
                self.runner.wait_for_lambda_copy("ecommerce_orders.json", b'[]')
        self.assertEqual(clock[0], 600)
        self.assertEqual(s3.put_object.call_count, 3)
        self.assertTrue(all(call.kwargs["Key"].startswith("landing/ecommerce/") for call in s3.put_object.call_args_list))
        self.session.clients["lambda"].invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
