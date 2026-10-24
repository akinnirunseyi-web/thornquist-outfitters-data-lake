#!/usr/bin/env python3
"""Create and exercise an isolated Thornquist Learner Lab deployment.

Preview is local-only. --apply uses the signed-in CloudShell boto3 session.
No IAM roles are created, no existing project resources are adopted or deleted.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import io
import json
import re
import sys
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = "1.2"
S3_EVENT_TIMEOUT_SECONDS = 600
S3_EVENT_REUPLOAD_SECONDS = (60, 180, 360)
POS_FILE = "pos_sales_2026-08-24_to_2026-08-30.csv"
ECOM_FILE = "ecommerce_orders.json"
CUSTOMER_FILE = "customer_extract.csv"
DEMO_ORDER = "900000"
CRAWL_SCHEDULES = {
    "raw-customers": "cron(15 7 * * ? *)",
    "raw-ecommerce": "cron(20 7 * * ? *)",
    "raw-pos": "cron(25 7 * * ? *)",
    "trusted-sales": "cron(30 7 * * ? *)",
}
SALES_COLUMNS = [
    ("sale_line_id", "string"), ("source_system", "string"),
    ("transaction_id", "string"), ("order_id", "string"),
    ("order_line_number", "int"), ("customer_id", "string"),
    ("sale_timestamp", "string"), ("sku", "string"),
    ("product_name", "string"), ("category", "string"),
    ("quantity", "double"), ("unit_price", "string"),
    ("line_amount", "string"), ("sales_region", "string"),
    ("shipping_region", "string"), ("store_id", "string"),
    ("store_name", "string"), ("payment_method", "string"),
    ("channel", "string"), ("source_file", "string"),
    ("source_record_number", "int"), ("customer_first_name", "string"),
    ("customer_last_name", "string"), ("customer_loyalty_tier", "string"),
    ("customer_region", "string"),
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dumps(value):
    return json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


@dataclass(frozen=True)
class Config:
    account: str
    label: str
    region: str = "us-east-1"
    workgroup: str = "primary"
    enable_schedules: bool = False

    def __post_init__(self):
        if not re.fullmatch(r"[0-9]{12}", self.account):
            raise ValueError("--expected-account must have 12 digits")
        if not re.fullmatch(r"[a-z][a-z0-9]{2,19}", self.label):
            raise ValueError("--run-label needs 3-20 lowercase letters/digits, starting with a letter")
        if self.region != "us-east-1":
            raise ValueError("This reproduction targets us-east-1")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.workgroup):
            raise ValueError("Invalid Athena workgroup name")

    @property
    def bucket(self):
        return f"thornquist-clean-{self.account}-{self.label}"

    @property
    def prefix(self):
        return f"tqclean-{self.label}"

    @property
    def database(self):
        return f"tq_clean_{self.label}"

    @property
    def role(self):
        return f"arn:aws:iam::{self.account}:role/LabRole"

    def uri(self, key):
        return f"s3://{self.bucket}/{key.lstrip('/')}"


def validate_inputs():
    manifest = json.loads((ROOT / "data/source_manifest.json").read_text())
    require(set(manifest) == {POS_FILE, ECOM_FILE, CUSTOMER_FILE}, "Unexpected source manifest")
    for name, expected in manifest.items():
        data = (ROOT / "data" / name).read_bytes()
        require(len(data) == expected["bytes"], f"Source size changed: {name}")
        require(hashlib.sha256(data).hexdigest() == expected["sha256"], f"Source checksum changed: {name}")
    return manifest


def fingerprint():
    digest = hashlib.sha256()
    files = [ROOT / "clean_lab.py"]
    for directory in ("scripts", "data", "queries"):
        files.extend(sorted((ROOT / directory).glob("*")))
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def quality_variants():
    """Change one field in a COPY; the supplied source file is never edited."""
    original = (ROOT / "data" / ECOM_FILE).read_bytes()
    orders = json.loads(original)
    targets = [o for o in orders if str(o["order_id"]) == DEMO_ORDER]
    require(len(targets) == 1, "Controlled demo order is not unique")
    require(targets[0]["items"][0]["qty"] == 1, "Unexpected original demo quantity")
    bad = copy.deepcopy(orders)
    next(o for o in bad if str(o["order_id"]) == DEMO_ORDER)["items"][0]["qty"] = -1
    return (dumps(bad).encode(), original)


def render_sql(name, config):
    sql = (ROOT / "queries" / name).read_text()
    return sql.replace("__DATABASE__", config.database).replace("__BUCKET__", config.bucket)


def check_summary(summary, variant):
    expected = {
        "customers": (400, 400, 0),
        "pos_sales": (1051, 1048, 3),
        "ecommerce_orders": (265, 225 if variant == "bad" else 226, 40 if variant == "bad" else 39),
    }
    require(summary.get("execution_mode") == "aws_glue", "Expected an actual Glue report")
    for source, counts in expected.items():
        values = summary["validation"][source]
        actual = tuple(values.get(k, 0) for k in ("records_seen", "records_trusted", "records_quarantined"))
        require(actual == counts, f"Quality count mismatch for {variant}/{source}: {actual} != {counts}")
        require(actual[0] == actual[1] + actual[2], f"Unaccounted rows in {source}")
    require(summary["sales_model"]["rows_written"] == (1597 if variant == "bad" else 1601), "Sales model line count mismatch")


def check_gate_rejects(records, variant):
    targets = [x for x in records if str(x["record"].get("order_id")) == DEMO_ORDER]
    if variant == "bad":
        require(len(targets) == 1, "Controlled bad order missing or repeated in quarantine")
        require("DQ05_ITEM_1_INVALID_QUANTITY" in targets[0]["rejection_reasons"], "Missing quantity rejection reason")
        return {"order_id": DEMO_ORDER, "quantity": -1, "rejection_reasons": targets[0]["rejection_reasons"], "record_number": targets[0]["record_number"]}
    require(not targets, "Corrected order is still quarantined")
    return {"order_id": DEMO_ORDER, "quantity": 1, "quarantined": False}


def table_input(name, location, columns, kind="parquet"):
    storage = {"Columns": [{"Name": key, "Type": typ} for key, typ in columns], "Location": location}
    parameters = {"EXTERNAL": "TRUE", "classification": kind}
    if kind == "parquet":
        storage.update({
            "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {"SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe", "Parameters": {"serialization.format": "1"}},
        })
    else:
        storage.update({"InputFormat": "org.apache.hadoop.mapred.TextInputFormat", "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"})
        if kind == "csv":
            storage["SerdeInfo"] = {"SerializationLibrary": "org.apache.hadoop.hive.serde2.OpenCSVSerde", "Parameters": {"separatorChar": ",", "quoteChar": '"', "escapeChar": "\\"}}
            parameters["skip.header.line.count"] = "1"
        else:
            storage["SerdeInfo"] = {"SerializationLibrary": "org.openx.data.jsonserde.JsonSerDe", "Parameters": {}}
    return {"Name": name, "TableType": "EXTERNAL_TABLE", "Parameters": parameters, "StorageDescriptor": storage, "PartitionKeys": []}


def catalog_tables(config):
    pos_columns = [(name, "string") for name in (
        "transaction_id", "store_id", "store_name", "region", "sale_date", "category", "product_name", "quantity", "unit_price", "payment_method", "cust_num")]
    customer_columns = [(name, "string") for name in ("cust_num", "first_name", "last_name", "email", "signup_date", "loyalty_tier", "region")]
    ecom_columns = [(name, "string") for name in ("order_id", "order_timestamp", "cust_ref", "channel", "shipping_region")]
    ecom_columns += [("items", "array<struct<sku:string,product_name:string,qty:string,unit_price:string>>"), ("order_total", "string")]
    tables = [
        table_input("landing_pos", config.uri("landing/pos/"), pos_columns, "csv"),
        table_input("raw_pos", config.uri("raw/pos/"), pos_columns, "csv"),
        table_input("raw_customers", config.uri("raw/customers/"), customer_columns),
        table_input("raw_ecommerce_ndjson", config.uri("raw/ecommerce_ndjson/"), ecom_columns, "json"),
        table_input("trusted_sales_model", config.uri("trusted/sales_model/"), SALES_COLUMNS),
        table_input("demo_bad_sales", config.uri("quality-demo/bad/trusted/sales_model/"), SALES_COLUMNS),
    ]
    for name in ("customers", "pos_sales", "ecommerce_orders"):
        tables.append(table_input("trusted_" + name, config.uri(f"trusted/{name}/"), [("source_file", "string"), ("record_number", "bigint"), ("record_json", "string")]))
    return tables


def write_dashboard(path, config, results, query_ids):
    """A local snapshot built only from the results of THIS Athena run."""
    sections = [
        ("Revenue by channel", "01_daily_sales", "source_system"),
        ("Revenue by region", "02_regional_sales", "sales_region"),
        ("Revenue by category", "03b_category_sales", "category"),
        ("Customer loyalty segments", "04_loyalty_sales", "loyalty_tier"),
        ("Top products", "03a_top_products", "product_name"),
        ("Revenue by store", "05_store_sales", "store_name"),
    ]
    parts = []
    for title, key, dimension in sections:
        rows = results[key]
        totals = {}
        for row in rows:
            label = row.get(dimension) or "Unspecified"
            # The product query calls its measure revenue; others use total_sales.
            amount = row.get("total_sales", row.get("revenue", "0"))
            totals[label] = totals.get(label, Decimal(0)) + Decimal(amount or "0")
        ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        maximum = max((value for _, value in ordered), default=Decimal(1)) or Decimal(1)
        bars = "".join(f'<div class="barrow"><span>{html.escape(label)}</span><div class="track"><div class="bar" style="width:{float(value / maximum * 100):.2f}%"></div></div><b>{value:,.2f}</b></div>' for label, value in ordered)
        header = "".join(f"<th>{html.escape(c)}</th>" for c in (list(rows[0]) if rows else []))
        body = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row.values()) + "</tr>" for row in rows)
        parts.append(f'<section><h2>{title}</h2>{bars}<details><summary>Query result and execution ID</summary><p>{html.escape(query_ids[key])}</p><div class="table"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div></details></section>')
    document = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Thornquist clean-run analytics</title><style>body{font:16px system-ui,sans-serif;margin:0;background:#f1f5f7;color:#18332f}main{max-width:1120px;margin:auto;padding:32px}h1{font-size:32px}h2{font-size:21px}section{background:white;margin:22px 0;padding:24px;border-radius:12px}.barrow{display:grid;grid-template-columns:minmax(130px,220px) 1fr 120px;align-items:center;gap:12px;margin:14px 0}.track{background:#e7efed;height:20px}.bar{height:20px;background:#217969}b{text-align:right;font-variant-numeric:tabular-nums}p{line-height:1.5}summary{cursor:pointer;margin-top:22px}.table{overflow:auto}th,td{text-align:left;border-bottom:1px solid #ddd;padding:8px;white-space:nowrap}@media(max-width:600px){main{padding:16px}.barrow{grid-template-columns:105px 1fr 90px;font-size:12px}}</style><main>'
    segments = [r for r in results["04_loyalty_sales"] if r["loyalty_tier"] != "Walk-in" and int(r["identified_customers"]) > 0]
    insight = ""
    if segments:
        top_revenue = max(segments, key=lambda row: Decimal(row["total_sales"]))
        top_average = max(segments, key=lambda row: Decimal(row["average_transaction_value"]))
        insight = f'<p><strong>Customer insight:</strong> Among identified loyalty segments, {html.escape(top_revenue["loyalty_tier"])} generated the most revenue ({Decimal(top_revenue["total_sales"]):,.2f}) across {int(top_revenue["transactions"]):,} transactions. {html.escape(top_average["loyalty_tier"])} had the highest average transaction value ({Decimal(top_average["average_transaction_value"]):,.2f}). These are associations in this sample, not evidence that loyalty status causes spending.</p>'
    document += f'<h1>Thornquist · clean-run analytics</h1><p>Run <strong>{html.escape(config.label)}</strong> · {html.escape(utc_now())}<br>Database {html.escape(config.database)} · Region {config.region}</p><p>1,601 accepted sales lines · total 320,570.35 source monetary units. Currency is unspecified in the source. Channel is grouped as POS versus e-commerce. Region means store region for POS and shipping destination for e-commerce. Categories for e-commerce are derived from unambiguous POS product matches.</p><p>Customer loyalty comes from the customer extract joined to sales by normalized customer ID. Segment revenue, identified customers and average transaction value are in the segment query below. Walk-in customers are unidentified.</p>{insight}<p>This is a snapshot of this run’s Athena results. Refresh by producing new query results; it is not a live connection.</p>'
    path.write_text(document + "".join(parts) + "</main></html>")


class Runner:
    def __init__(self, config, state_path, session):
        self.c = config
        self.path = state_path
        self.out = ROOT / "run-evidence" / config.label
        self.out.mkdir(parents=True, exist_ok=True)
        self.clients = {name: session.client(name, region_name=config.region) for name in ("sts", "s3", "lambda", "glue", "athena")}
        if state_path.exists():
            self.state = json.loads(state_path.read_text())
            require(self.state["config"] == asdict(config), "Resume configuration differs; use the exact original options")
            require(self.state["bundle_sha256"] == fingerprint(), "Bundle changed since this run; use an untouched copy and a fresh label")
        else:
            self.state = {"version": VERSION, "config": asdict(config), "bundle_sha256": fingerprint(), "owner_token": str(uuid.uuid4()), "started_utc": utc_now(), "steps": {}, "jobs": {}, "queries": {}, "crawls": {}}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(dumps(self.state))
        tmp.replace(self.path)

    def log(self, message):
        line = f"[{utc_now()}] {message}"
        print(line, flush=True)
        with (self.out / "execution.log").open("a") as target:
            target.write(line + "\n")

    def client(self, name):
        return self.clients[name]

    def absent(self, operation, **args):
        try:
            operation(**args)
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchBucket", "NotFoundException", "ResourceNotFoundException", "EntityNotFoundException"):
                return
            raise
        raise RuntimeError(f"Resource already exists: {args}. Choose a fresh run label.")

    def identity(self):
        identity = self.client("sts").get_caller_identity()
        require(identity["Account"] == self.c.account, f"Account mismatch: signed in to {identity['Account']}")
        self.state["caller_identity"] = identity
        self.log(f"Account verified: {self.c.account}; role reused: LabRole")

    def preflight(self):
        self.identity()
        wg = self.client("athena").get_work_group(WorkGroup=self.c.workgroup)["WorkGroup"]
        require(wg["State"] == "ENABLED", "Athena workgroup is not enabled")
        require(not wg.get("Configuration", {}).get("EnforceWorkGroupConfiguration"), "Workgroup enforces settings incompatible with this CTAS external location; select an authorized workgroup without enforced settings")
        self.state["athena_workgroup"] = {"name": self.c.workgroup, "enforces_settings": False}
        if self.state.get("preflight_complete"):
            owner = self.read_json("infrastructure/clean_lab_owner.json")
            require(owner["owner_token"] == self.state["owner_token"], "Bucket ownership marker does not match local state")
            require(owner["config"] == asdict(self.c), "Bucket marker configuration mismatch")
            self.log("Resuming only the resources owned by this run")
            return
        own_buckets = self.client("s3").list_buckets()["Buckets"]
        require(self.c.bucket not in {b["Name"] for b in own_buckets}, "Bucket already belongs to this account; choose a fresh label")
        self.absent(self.client("s3").head_bucket, Bucket=self.c.bucket)
        self.absent(self.client("glue").get_database, Name=self.c.database)
        self.absent(self.client("lambda").get_function, FunctionName=self.c.prefix + "-ecommerce")
        for suffix in ("customer-ingestion", "sales-etl"):
            self.absent(self.client("glue").get_job, JobName=self.c.prefix + "-" + suffix)
        for suffix in CRAWL_SCHEDULES:
            self.absent(self.client("glue").get_crawler, Name=self.c.prefix + "-" + suffix)
        self.absent(self.client("glue").get_trigger, Name=self.c.prefix + "-customer-daily")
        self.save()

    def step(self, name, action, repeatable=False):
        previous = self.state["steps"].get(name, {})
        if previous.get("state") == "SUCCEEDED":
            return previous.get("result")
        if previous and not repeatable:
            raise RuntimeError(f"Step {name} was interrupted or failed; an AWS resource may already exist. Keep the evidence and use a fresh run label after resolving the error. No existing resource will be overwritten.")
        self.state["steps"][name] = {"state": "STARTED", "started_utc": utc_now()}
        self.save()
        self.log(name)
        try:
            result = action()
            self.state["steps"][name].update(state="SUCCEEDED", completed_utc=utc_now(), result=result)
            self.save()
            return result
        except Exception as exc:
            self.state["steps"][name].update(state="FAILED", error=str(exc), completed_utc=utc_now())
            self.save()
            raise

    def put(self, key, body, content_type="application/octet-stream"):
        if isinstance(body, str):
            body = body.encode()
        self.client("s3").put_object(Bucket=self.c.bucket, Key=key, Body=body, ContentType=content_type, ServerSideEncryption="AES256", ExpectedBucketOwner=self.c.account)
        return {"key": key, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}

    def read_bytes(self, key):
        return self.client("s3").get_object(Bucket=self.c.bucket, Key=key, ExpectedBucketOwner=self.c.account)["Body"].read()

    def read_json(self, key):
        return json.loads(self.read_bytes(key))

    def provision(self):
        def create_bucket():
            s3 = self.client("s3")
            s3.create_bucket(Bucket=self.c.bucket, ObjectOwnership="BucketOwnerEnforced")
            s3.put_public_access_block(Bucket=self.c.bucket, PublicAccessBlockConfiguration={k: True for k in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")}, ExpectedBucketOwner=self.c.account)
            s3.put_bucket_encryption(Bucket=self.c.bucket, ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}, ExpectedBucketOwner=self.c.account)
            policy = {"Version": "2012-10-17", "Statement": [{"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*", "Resource": [f"arn:aws:s3:::{self.c.bucket}", f"arn:aws:s3:::{self.c.bucket}/*"], "Condition": {"Bool": {"aws:SecureTransport": "false", "aws:PrincipalIsAWSService": "false"}}}]}
            s3.put_bucket_policy(Bucket=self.c.bucket, Policy=json.dumps(policy), ExpectedBucketOwner=self.c.account)
            self.put("infrastructure/clean_lab_owner.json", dumps({"owner_token": self.state["owner_token"], "config": asdict(self.c)}), "application/json")
            self.state["preflight_complete"] = True
            return {"bucket": self.c.bucket}
        self.step("Create isolated private bucket", create_bucket)
        for name in ("lambda_function.py", "customer_ingestion.py", "glue_sales_etl.py"):
            self.step("Upload script " + name, lambda n=name: self.put("infrastructure/scripts/" + n, (ROOT / "scripts" / n).read_bytes(), "text/x-python"), repeatable=True)
        self.step("Create catalog database", lambda: self.client("glue").create_database(DatabaseInput={"Name": self.c.database, "Description": "Isolated Thornquist clean-lab reproduction " + self.c.label}))
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.write(ROOT / "scripts/lambda_function.py", "lambda_function.py")
        function = self.c.prefix + "-ecommerce"
        self.step("Create ecommerce Lambda", lambda: self.client("lambda").create_function(FunctionName=function, Runtime="python3.14", Role=self.c.role, Handler="lambda_function.lambda_handler", Code={"ZipFile": archive.getvalue()}, Description="Copy original ecommerce array JSON from Landing to Raw", Timeout=30, MemorySize=128, Architectures=["x86_64"], Environment={"Variables": {"BUCKET_NAME": self.c.bucket}}, Publish=True))
        self.log("Waiting for Lambda to become active")
        self.client("lambda").get_waiter("function_active_v2").wait(FunctionName=function, WaiterConfig={"Delay": 5, "MaxAttempts": 60})
        self.step("Allow this bucket to invoke Lambda", lambda: self.client("lambda").add_permission(FunctionName=function, StatementId="ThornquistLandingEvent", Action="lambda:InvokeFunction", Principal="s3.amazonaws.com", SourceArn=f"arn:aws:s3:::{self.c.bucket}", SourceAccount=self.c.account))
        def notification():
            arn = f"arn:aws:lambda:{self.c.region}:{self.c.account}:function:{function}"
            return self.client("s3").put_bucket_notification_configuration(Bucket=self.c.bucket, ExpectedBucketOwner=self.c.account, NotificationConfiguration={"LambdaFunctionConfigurations": [{"Id": "EcommerceLandingCreated", "LambdaFunctionArn": arn, "Events": ["s3:ObjectCreated:*"], "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "landing/ecommerce/"}, {"Name": "suffix", "Value": ".json"}]}}}]})
        self.step("Configure new bucket event notification", notification, repeatable=True)
        common = {"--job-language": "python", "--TempDir": self.c.uri("temporary/glue/"), "--enable-continuous-cloudwatch-log": "true"}
        customer_args = {**common, "--S3_SOURCE_PATH": self.c.uri("landing/customers/" + CUSTOMER_FILE), "--S3_TARGET_PATH": self.c.uri("raw/customers/")}
        sales_args = {**common, **self.sales_arguments("corrected")}
        for suffix, script, arguments in (("customer-ingestion", "customer_ingestion.py", customer_args), ("sales-etl", "glue_sales_etl.py", sales_args)):
            self.step("Create Glue job " + suffix, lambda s=suffix, p=script, a=arguments: self.client("glue").create_job(Name=self.c.prefix + "-" + s, Role=self.c.role, Command={"Name": "glueetl", "ScriptLocation": self.c.uri("infrastructure/scripts/" + p), "PythonVersion": "3"}, DefaultArguments=a, ExecutionProperty={"MaxConcurrentRuns": 1}, JobRunQueuingEnabled=True, MaxRetries=0, Timeout=20, GlueVersion="4.0", WorkerType="G.1X", NumberOfWorkers=2))
        self.step("Create daily customer trigger", lambda: self.client("glue").create_trigger(Name=self.c.prefix + "-customer-daily", Type="SCHEDULED", Schedule="cron(0 7 * * ? *)", StartOnCreation=self.c.enable_schedules, Actions=[{"JobName": self.c.prefix + "-customer-ingestion"}]))
        for table in catalog_tables(self.c):
            self.step("Define catalog table " + table["Name"], lambda t=table: self.client("glue").create_table(DatabaseName=self.c.database, TableInput=t))
        paths = {"raw-customers": "raw/customers/", "raw-ecommerce": "raw/ecommerce_ndjson/", "raw-pos": "raw/pos/", "trusted-sales": "trusted/sales_model/"}
        for suffix, key in paths.items():
            name = self.c.prefix + "-" + suffix
            self.step("Create crawler " + suffix, lambda n=name, s=suffix, k=key: self.client("glue").create_crawler(Name=n, Role=self.c.role, DatabaseName=self.c.database, Targets={"S3Targets": [{"Path": self.c.uri(k)}]}, TablePrefix="trusted_" if s == "trusted-sales" else "raw_", RecrawlPolicy={"RecrawlBehavior": "CRAWL_EVERYTHING"}, SchemaChangePolicy={"UpdateBehavior": "LOG", "DeleteBehavior": "LOG"}))
            def schedule(n=name, s=suffix):
                glue = self.client("glue")
                glue.update_crawler_schedule(CrawlerName=n, Schedule=CRAWL_SCHEDULES[s])
                crawler = glue.get_crawler(Name=n)["Crawler"]
                state = crawler.get("Schedule", {}).get("State")
                if self.c.enable_schedules and state != "SCHEDULED":
                    glue.start_crawler_schedule(CrawlerName=n)
                elif not self.c.enable_schedules and state == "SCHEDULED":
                    glue.stop_crawler_schedule(CrawlerName=n)
                return {"cron": CRAWL_SCHEDULES[s], "enabled_requested": self.c.enable_schedules}
            self.step("Configure crawler schedule " + suffix, schedule, repeatable=True)

    def sales_arguments(self, variant):
        bad = variant == "bad"
        return {
            "--CUSTOMERS_S3_PATH": self.c.uri("raw/customers/"),
            "--POS_S3_PATH": self.c.uri("raw/pos/" + POS_FILE),
            "--ECOMMERCE_S3_PATH": self.c.uri("raw/ecommerce/quality-demo/" + ("bad.json" if bad else "corrected.json")),
            "--TRUSTED_S3_PATH": self.c.uri("quality-demo/bad/trusted/" if bad else "trusted/"),
            "--QUARANTINE_S3_PATH": self.c.uri("quality-demo/bad/quarantine/" if bad else "quarantine/"),
            "--REPORTS_S3_PATH": self.c.uri("quality-demo/bad/reports/" if bad else "reports/"),
        }

    def ingest(self):
        for directory, name in (("pos", POS_FILE), ("customers", CUSTOMER_FILE), ("ecommerce", ECOM_FILE)):
            self.step("Upload unchanged Landing " + name, lambda d=directory, n=name: self.put(f"landing/{d}/{n}", (ROOT / "data" / n).read_bytes()), repeatable=True)
        def copy_pos():
            self.client("s3").copy_object(Bucket=self.c.bucket, Key="raw/pos/" + POS_FILE, CopySource={"Bucket": self.c.bucket, "Key": "landing/pos/" + POS_FILE}, ServerSideEncryption="AES256", ExpectedBucketOwner=self.c.account, ExpectedSourceBucketOwner=self.c.account)
            body = self.read_bytes("raw/pos/" + POS_FILE)
            require(hashlib.sha256(body).hexdigest() == validate_inputs()[POS_FILE]["sha256"], "POS raw checksum mismatch")
            return {"mechanism": "scripted S3 copy", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        self.step("Scripted POS ingestion to Raw", copy_pos, repeatable=True)
        self.wait_for_lambda_copy("ecommerce_orders.json", (ROOT / "data" / ECOM_FILE).read_bytes())
        def ndjson():
            orders = json.loads(self.read_bytes("raw/ecommerce/" + ECOM_FILE))
            require(len(orders) == 265, "Unexpected ecommerce order count")
            data = "".join(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n" for o in orders)
            return self.put("raw/ecommerce_ndjson/ecommerce_orders.ndjson", data, "application/x-ndjson")
        self.step("Build queryable ecommerce NDJSON representation", ndjson, repeatable=True)
        for variant, payload in zip(("bad", "corrected"), quality_variants()):
            self.step("Upload controlled demo " + variant, lambda v=variant, p=payload: self.put(f"landing/ecommerce/quality-demo/{v}.json", p, "application/json"), repeatable=True)
            self.wait_for_lambda_copy(f"quality-demo/{variant}.json", payload)
        self.run_job("customer ingestion", self.c.prefix + "-customer-ingestion", {})

    def wait_for_lambda_copy(self, relative, expected):
        key = "raw/ecommerce/" + relative
        self.log("Waiting for actual S3-event Lambda copy: " + relative)
        started = time.monotonic()
        deadline = started + S3_EVENT_TIMEOUT_SECONDS
        reuploads = iter(S3_EVENT_REUPLOAD_SECONDS)
        next_reupload = next(reuploads, None)
        next_progress = started + 30
        while time.monotonic() < deadline:
            try:
                response = self.client("s3").get_object(Bucket=self.c.bucket, Key=key, ExpectedBucketOwner=self.c.account)
                data = response["Body"].read()
                checksum = hashlib.sha256(data).hexdigest()
                require(data == expected, "Lambda copy bytes differ from Landing input")
                require(response.get("Metadata", {}).get("source-sha256") == checksum, "Lambda SHA metadata missing or invalid")
                proof = {"mechanism": "actual S3 ObjectCreated event; no direct Lambda invocation", "raw_key": key, "sha256": checksum, "bytes": len(data), "last_modified": response["LastModified"]}
                (self.out / ("lambda_" + relative.replace("/", "_") + ".json")).write_text(dumps(proof))
                self.log("Lambda event copy verified: " + relative)
                return
            except Exception as exc:
                if getattr(exc, "response", {}).get("Error", {}).get("Code") not in ("NoSuchKey", "404"):
                    raise
            now = time.monotonic()
            elapsed = int(now - started)
            if next_reupload is not None and elapsed >= next_reupload:
                # Repeat the genuine Landing PUT with identical bytes. Do not
                # invoke Lambda directly or write its Raw output as a fallback.
                source = "landing/ecommerce/" + relative
                self.log(f"S3 event copy pending after {elapsed}s; re-uploading identical Landing bytes: {relative}")
                uploaded = self.put(source, expected, "application/json")
                self.state.setdefault("s3_event_reuploads", []).append({"utc": utc_now(), "source_key": source, "raw_key": key, **uploaded})
                self.save()
                next_reupload = next(reuploads, None)
            if now >= next_progress:
                self.log(f"Still waiting for S3-triggered Lambda copy: {relative} · {elapsed}s elapsed")
                next_progress = now + 30
            time.sleep(5)
        raise RuntimeError("Timed out after 10 minutes waiting for the S3-triggered Lambda copy. Check Lambda logs/trigger permissions. Completed stages are saved; rerun the same command after resolving the error.")

    def run_job(self, label, job, arguments):
        glue = self.client("glue")
        record = self.state["jobs"].get(label)
        if not record:
            self.state["jobs"][label] = {"job": job, "submission": "STARTED", "arguments": arguments, "started_utc": utc_now()}
            self.save()
            record = self.state["jobs"][label]
        else:
            require(record["job"] == job and record["arguments"] == arguments, "Saved Glue request differs from this stage")
            if not record.get("run_id"):
                require(record.get("submission") == "REJECTED_CONCURRENCY", f"Glue submission interrupted for {label}; inspect AWS before any resubmission. No new run was submitted.")
        if not record.get("run_id"):
            submit_deadline = time.monotonic() + 900
            while True:
                record["submission"] = "STARTED"
                self.save()
                try:
                    response = glue.start_job_run(JobName=job, Arguments=arguments, JobRunQueuingEnabled=True)
                except Exception as exc:
                    code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                    record["submission_error"] = str(exc)
                    if code == "ConcurrentRunsExceededException":
                        # A definitive rejection has no run ID. Persist this
                        # distinction from an unknown network/submission result.
                        record["submission"] = "REJECTED_CONCURRENCY"
                        self.save()
                        require(time.monotonic() < submit_deadline, "Glue capacity unavailable after 15 minutes. Saved rejection can be retried with the same command; no run ID was issued.")
                        self.log(f"Glue {label}: waiting for capacity; retrying submission in 15s")
                        time.sleep(15)
                        continue
                    self.save()
                    raise
                record.update(submission="SUBMITTED", run_id=response["JobRunId"], queuing_enabled=True)
                self.save()
                break
        require(record.get("run_id"), f"Glue submission interrupted for {label}; inspect AWS before any resubmission. Use a fresh label for a new rehearsal.")
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            details = glue.get_job_run(JobName=job, RunId=record["run_id"])["JobRun"]
            status = details["JobRunState"]
            self.log(f"Glue {label}: {status} · {record['run_id']}")
            record["details"] = details
            self.save()
            if status == "SUCCEEDED":
                (self.out / ("glue_" + label.replace(" ", "_") + ".json")).write_text(dumps(record))
                return
            require(status not in {"FAILED", "TIMEOUT", "STOPPED", "ERROR", "EXPIRED"}, f"Glue {label} {status}: {details.get('ErrorMessage', '')}. No Curated promotion.")
            time.sleep(15)
        raise RuntimeError("Glue wait exceeded 30 minutes. Run the same command to resume waiting on the same run ID.")

    def crawl(self, suffix):
        glue = self.client("glue")
        name = self.c.prefix + "-" + suffix
        record = self.state["crawls"].get(suffix)
        if record and record.get("succeeded"):
            return
        if not record:
            crawler = glue.get_crawler(Name=name)["Crawler"]
            require(crawler["State"] == "READY", f"Crawler {name} is already running; wait and rerun")
            record = {"before_start": str(crawler.get("LastCrawl", {}).get("StartTime", "")), "submission": "STARTED"}
            self.state["crawls"][suffix] = record
            self.save()
            glue.start_crawler(Name=name)
            record["submission"] = "SUBMITTED"
            self.save()
        require(record["submission"] == "SUBMITTED", "Crawler start interrupted; inspect its status before proceeding")
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            crawler = glue.get_crawler(Name=name)["Crawler"]
            last = crawler.get("LastCrawl", {})
            if crawler["State"] == "READY" and str(last.get("StartTime", "")) != record["before_start"]:
                require(last.get("Status") == "SUCCEEDED", f"Crawler {name} failed: {last.get('ErrorMessage', '')}")
                record.update(succeeded=True, crawler=crawler)
                self.save()
                (self.out / ("crawler_" + suffix + ".json")).write_text(dumps(crawler))
                return
            self.log(f"Crawler {suffix}: {crawler['State']}")
            time.sleep(15)
        raise RuntimeError("Crawler wait exceeded 30 minutes; rerun to resume")

    def query(self, name, sql, ctas=False):
        athena = self.client("athena")
        stored = self.state["queries"].get(name)
        token = hashlib.sha256((self.state["owner_token"] + name + sql).encode()).hexdigest()
        if not stored:
            if ctas:
                self.absent(self.client("glue").get_table, DatabaseName=self.c.database, Name="curated_sales")
                existing = self.client("s3").list_objects_v2(Bucket=self.c.bucket, Prefix="curated/sales/", MaxKeys=1, ExpectedBucketOwner=self.c.account)
                require(not existing.get("Contents"), "Curated CTAS destination is not empty; no objects will be deleted")
            response = athena.start_query_execution(QueryString=sql, ClientRequestToken=token, QueryExecutionContext={"Database": self.c.database, "Catalog": "AwsDataCatalog"}, ResultConfiguration={"OutputLocation": self.c.uri("athena-results/"), "ExpectedBucketOwner": self.c.account, "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"}}, WorkGroup=self.c.workgroup)
            stored = {"query_id": response["QueryExecutionId"], "sql": sql, "token": token}
            self.state["queries"][name] = stored
            self.save()
        require(stored["token"] == token, "SQL changed during resume")
        qid = stored["query_id"]
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            details = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
            status = details["Status"]["State"]
            if status == "SUCCEEDED":
                stored["details"] = details
                self.save()
                (self.out / (name + ".execution.json")).write_text(dumps(details))
                (self.out / (name + ".sql")).write_text(sql)
                if ctas:
                    self.log(f"Athena {name}: SUCCEEDED · {qid}")
                    return []
                values, columns, next_token, first = [], [], None, True
                while True:
                    request = {"QueryExecutionId": qid, "MaxResults": 1000}
                    if next_token:
                        request["NextToken"] = next_token
                    page = athena.get_query_results(**request)
                    columns = [c["Name"] for c in page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]]
                    rows = page["ResultSet"]["Rows"]
                    if first:
                        # SELECT usually has a header; SHOW results may not.
                        first_values = [c.get("VarCharValue", "") for c in rows[0]["Data"]] if rows else []
                        if first_values == columns:
                            rows = rows[1:]
                        first = False
                    for row in rows:
                        values.append(dict(zip(columns, [c.get("VarCharValue", "") for c in row["Data"]])))
                    next_token = page.get("NextToken")
                    if not next_token:
                        break
                with (self.out / (name + ".csv")).open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(values)
                self.log(f"Athena {name}: SUCCEEDED · {qid} · {len(values)} result rows")
                return values
            require(status not in {"FAILED", "CANCELLED"}, f"Athena {name} {status}: {details['Status'].get('StateChangeReason', '')}")
            time.sleep(3)
        raise RuntimeError("Athena wait exceeded 10 minutes; rerun to resume")

    def run_pipeline(self):
        self.provision()
        self.ingest()
        landing = self.query("landing_pos_count", render_sql("09_landing_pos_count.sql", self.c))
        require(len(landing) == 1 and int(landing[0]["records"]) == 1051, "Landing POS catalog count differs from unchanged source")
        for suffix in ("raw-customers", "raw-ecommerce", "raw-pos"):
            self.crawl(suffix)
        raw = self.query("raw_table_counts", render_sql("10_raw_table_counts.sql", self.c))
        require({r["table_name"]: int(r["records"]) for r in raw} == {"raw_pos": 1051, "raw_customers": 400, "raw_ecommerce_ndjson": 265}, "Raw Athena counts do not match sources")
        pos = self.client("glue").get_table(DatabaseName=self.c.database, Name="raw_pos")["Table"]
        types = {column["Name"]: column["Type"] for column in pos["StorageDescriptor"]["Columns"]}
        require(all(types[x] == "string" for x in ("transaction_id", "store_id", "cust_num")), "Crawler changed identifier types")
        (self.out / "raw_pos_manual_schema.json").write_text(dumps(pos))
        identifiers = self.query("raw_pos_identifier_check", render_sql("11_raw_pos_identifier_check.sql", self.c))
        require(bool(identifiers) and all(row["cust_num"] == "0000000" for row in identifiers), "Raw query lost the leading-zero guest identifier")
        gate = {}
        for variant in ("bad", "corrected"):
            self.run_job(variant + " sales quality gate", self.c.prefix + "-sales-etl", self.sales_arguments(variant))
            prefix = "quality-demo/bad/" if variant == "bad" else ""
            report = self.read_json(prefix + "reports/sales_model_summary.json")
            check_summary(report, variant)
            rejects = [json.loads(line) for line in self.read_bytes(prefix + "quarantine/ecommerce_orders/part-00000.jsonl").decode().splitlines() if line.strip()]
            proof = check_gate_rejects(rejects, variant)
            gate[variant] = {"glue_run_id": self.state["jobs"][variant + " sales quality gate"]["run_id"], "summary": report, "controlled_record": proof, "quarantine_s3_uri": self.c.uri(prefix + "quarantine/ecommerce_orders/part-00000.jsonl")}
            (self.out / (variant + "_quality_report.json")).write_text(dumps(gate[variant]))
        self.crawl("trusted-sales")
        trusted = self.query("trusted_table_counts", render_sql("12_trusted_table_counts.sql", self.c))
        require({r["table_name"]: int(r["records"]) for r in trusted} == {"trusted_customers": 400, "trusted_pos_sales": 1048, "trusted_ecommerce_orders": 226, "trusted_sales_model": 1601}, "Trusted Athena counts differ from quality reports")
        comparison = self.query("quality_gate_comparison", render_sql("13_quality_gate_comparison.sql", self.c))
        require({r["variant"]: int(r["sales_lines"]) for r in comparison} == {"bad": 0, "corrected": 4}, "Controlled order exclusion/promotion proof failed")
        gate["athena_comparison"] = comparison
        gate["athena_query_id"] = self.state["queries"]["quality_gate_comparison"]["query_id"]
        (self.out / "quality_gate_proof.json").write_text(dumps(gate))
        # Promotion happens only after actual quarantine, report and Athena checks pass.
        self.query("create_curated_sales", render_sql("00_curated_sales_ctas.sql", self.c), ctas=True)
        totals = self.query("curated_verification", render_sql("14_curated_verification.sql", self.c))
        require(len(totals) == 1, "Unexpected Curated verification result")
        total = totals[0]
        require(int(total["sales_lines"]) == 1601 and Decimal(total["total_sales"]) == Decimal("320570.35"), "Curated totals differ from the supplied sample")
        require((total["first_date"], total["last_date"]) == ("2026-08-24", "2026-08-30"), "Unexpected sale dates")
        require(int(total["bad_quantity_lines"]) == 0 and int(total["duplicate_line_ids"]) == 0, "Curated quality invariant failed")
        partitions = self.query("curated_partitions", f"SHOW PARTITIONS {self.c.database}.curated_sales")
        require(any("sale_year=2026/sale_month=08" in str(row) for row in partitions), "Expected year/month partition missing")
        curated_table = self.client("glue").get_table(DatabaseName=self.c.database, Name="curated_sales")["Table"]
        require("parquet" in curated_table["StorageDescriptor"]["InputFormat"].lower(), "Curated catalog is not Parquet")
        require([column["Name"] for column in curated_table["PartitionKeys"]] == ["sale_year", "sale_month"], "Curated partition key mismatch")
        objects = self.client("s3").list_objects_v2(Bucket=self.c.bucket, Prefix="curated/sales/sale_year=2026/sale_month=08/", MaxKeys=10, ExpectedBucketOwner=self.c.account).get("Contents", [])
        data_files = [obj for obj in objects if obj["Size"] > 4 and not obj["Key"].endswith("/")]
        require(bool(data_files), "No Curated partition data file found")
        magic = self.client("s3").get_object(Bucket=self.c.bucket, Key=data_files[0]["Key"], Range="bytes=0-3", ExpectedBucketOwner=self.c.account)["Body"].read()
        require(magic == b"PAR1", "Curated object does not have the Parquet file signature")
        (self.out / "curated_storage_proof.json").write_text(dumps({"table": curated_table, "partition_objects": data_files, "first_object_magic": "PAR1", "compression_requested_by_successful_ctas": "SNAPPY"}))
        coverage = self.query("category_coverage", render_sql("validate_category_coverage.sql", self.c))
        require(len(coverage) == 1 and coverage[0]["mapping_status"] == "Category matched" and int(coverage[0]["sales_lines"]) == 553, "Category mapping coverage failed; no category dashboard")
        names = ("01_daily_sales", "02_regional_sales", "03a_top_products", "03b_category_sales", "04_loyalty_sales", "05_store_sales")
        results = {name: self.query(name, render_sql(name + ".sql", self.c)) for name in names}
        for name in ("01_daily_sales", "02_regional_sales", "03b_category_sales", "04_loyalty_sales"):
            require(sum(Decimal(row["total_sales"]) for row in results[name]) == Decimal("320570.35"), "Analytical revenue reconciliation failed: " + name)
        require(sum(Decimal(row["total_sales"]) for row in results["05_store_sales"]) == Decimal("214561.78"), "Store revenue does not reconcile to POS")
        write_dashboard(self.out / "Thornquist_Clean_Run_Analytics.html", self.c, results, {name: self.state["queries"][name]["query_id"] for name in names})
        self.state["completed_utc"] = utc_now()
        self.state["result"] = "PASSED"
        self.save()
        (self.out / "run_manifest.json").write_text(dumps(self.state))
        self.put("reports/clean_run_manifest.json", dumps(self.state), "application/json")
        # Preserve a portable evidence bundle in both CloudShell and this new bucket.
        evidence_zip = ROOT / ("Thornquist_Run_Evidence_" + self.c.label + ".zip")
        with zipfile.ZipFile(evidence_zip, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(self.out.rglob("*")):
                if path.is_file():
                    bundle.write(path, self.c.label + "/" + path.relative_to(self.out).as_posix())
        self.put("reports/" + evidence_zip.name, evidence_zip.read_bytes(), "application/zip")
        self.log("PASSED: actual Lambda ingestion, Glue rejection/correction, Raw/Trusted Athena queries, partitioned Curated and six business queries")
        self.log("Evidence ZIP: " + str(evidence_zip))
        self.log("Dashboard: " + str(self.out / "Thornquist_Clean_Run_Analytics.html"))

    def pause_schedules(self):
        self.identity()
        owner = self.read_json("infrastructure/clean_lab_owner.json")
        require(owner["owner_token"] == self.state["owner_token"], "Ownership marker mismatch")
        glue = self.client("glue")
        trigger_name = self.c.prefix + "-customer-daily"
        trigger = glue.get_trigger(Name=trigger_name)["Trigger"]
        if trigger["State"] in ("ACTIVATED", "ACTIVATING"):
            glue.stop_trigger(Name=trigger_name)
        for suffix in CRAWL_SCHEDULES:
            name = self.c.prefix + "-" + suffix
            crawler = glue.get_crawler(Name=name)["Crawler"]
            if crawler.get("Schedule", {}).get("State") == "SCHEDULED":
                glue.stop_crawler_schedule(CrawlerName=name)
        self.state["schedules_pause_requested_utc"] = utc_now()
        self.save()
        self.log("Pause requested for only this rehearsal's customer trigger and four crawler schedules")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-account", required=True)
    parser.add_argument("--run-label", required=True, help="Fresh 3-20 character label, e.g. demo01")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--workgroup", default="primary")
    parser.add_argument("--enable-schedules", action="store_true", help="Activate daily customer and crawler schedules; first rehearsal executions are still started manually")
    parser.add_argument("--apply", action="store_true", help="Create resources and run AWS jobs/queries")
    parser.add_argument("--pause-schedules", action="store_true", help="Pause only schedules belonging to this saved run; requires --apply")
    args = parser.parse_args(argv)
    config = Config(args.expected_account, args.run_label, args.region, args.workgroup, args.enable_schedules)
    manifest = validate_inputs()
    state_path = ROOT / ".clean-lab-state" / (config.label + ".json")
    plan = {"version": VERSION, "aws_writes": bool(args.apply), "config": asdict(config), "new_bucket": config.bucket, "new_database": config.database, "resource_prefix": config.prefix, "existing_execution_role": config.role, "glue_settings": {"version": "4.0", "worker_type": "G.1X", "workers": 2, "max_retries": 0, "timeout_minutes": 20}, "source_integrity": manifest, "steps": ["Create isolated S3, Lambda, Glue jobs, catalog tables and scheduled crawler definitions", "Upload originals; scripted POS copy; real S3 event invokes ecommerce Lambda; run customer ingestion", "Query Landing POS; crawl Raw and query all three Raw tables in Athena", "Actual Glue run rejects controlled order 900000 (qty=-1) into a separate quarantine path", "Actual Glue run accepts corrected order (qty=1); preserve both variants and job IDs", "Crawl Trusted; query four Trusted tables; prove controlled order absent/present", "Create new partitioned Snappy Parquet Curated table after gate checks", "Verify totals and execute six business queries; build analytics snapshot and evidence ZIP"], "expected_corrected_run": {"raw_customers": 400, "raw_pos": 1051, "raw_ecommerce_orders": 265, "trusted_lines": 1601, "pos_quarantine": 3, "ecommerce_quarantine": 39, "curated_total": "320570.35"}, "scope": "Pipeline reproduction. This package does not recreate the separate previously verified email monitoring tests or deploy analyst IAM/Lake Formation policies."}
    if not args.apply:
        require(not args.pause_schedules, "--pause-schedules requires --apply")
        print(dumps(plan))
        print("PREVIEW ONLY: no AWS calls were made. Add --apply to execute this plan.")
        return 0
    if args.pause_schedules:
        require(state_path.exists(), "No saved state for this run; no schedules will be changed")
        saved = json.loads(state_path.read_text())["config"]
        require(saved["account"] == config.account, "Saved run account mismatch")
        config = Config(**saved)
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for --apply. Use AWS CloudShell or install requirements.txt in your own environment.") from exc
    runner = Runner(config, state_path, boto3.Session(region_name=config.region))
    if args.pause_schedules:
        runner.pause_schedules()
    else:
        runner.preflight()
        runner.run_pipeline()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        sys.exit(1)
