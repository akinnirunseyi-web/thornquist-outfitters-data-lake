# Deployment and reproduction

Verified target: account `470551642447`, region `us-east-1`, bucket `thornquist-data-lake-2026102`, database `thornquist_outfitters`. This guide describes the original manual console/CloudShell deployment. For a fresh, isolated Learner Lab session, use [the repository deployment runner](../reproduction/clean_lab/README.md) and its runbook; the `rehearsal01` run completed the pipeline on 23 October. For another account, use its account number and a new run label. Preserve the original `data/` files.

## Four-zone catalog map

| Zone | Original deployment location | Catalog definition |
| --- | --- | --- |
| Landing | `landing/pos/`, `landing/ecommerce/`, `landing/customers/` | `landing_pos` DDL is in `queries/09_landing_pos_catalog.sql`; it preserves POS identifiers as strings and queries the unchanged CSV. The source JSON array and customer CSV stay intact. |
| Raw | `raw/pos/`, `raw/ecommerce_ndjson/`, `raw/customers/` | `raw_pos`, `raw_ecommerce_ndjson`, `raw_customers` |
| Trusted | `trusted/` | `trusted_customers`, `trusted_pos_sales`, `trusted_ecommerce_orders`, `trusted_sales_model` in the isolated reproduction; original deployment catalogs the flattened Trusted sales model |
| Curated | `curated/sales/` | `curated_sales`, created through Athena CTAS as partitioned Parquet |

Our AWS run showed catalog tables across Landing, Raw, Trusted and Curated. For a fresh deployment, [the Landing POS DDL](../queries/09_landing_pos_catalog.sql) records the Landing table definition; execute it only if that table is absent, then use [the count query](../queries/09_landing_pos_count.sql) to check for 1,051 source rows. The repository runner creates the definition and executes the count check during a fresh run. No ingestion job needs replaying merely to inspect the existing catalog.

## 1. Foundation and inputs

Check `aws sts get-caller-identity` before AWS changes. For a fresh environment, create a general-purpose S3 bucket in `us-east-1`, enable all four Block Public Access settings and SSE-S3 default encryption. Keep versioning disabled to match this demonstration. Create the logical prefixes `landing/`, `raw/`, `trusted/`, `curated/`, `quarantine/`, `reports/` and `athena-results/`. Empty folder markers are optional; uploads create prefixes.

Upload the three unchanged source files into `landing/pos/`, `landing/ecommerce/` and `landing/customers/`, respectively. Compare their local checksums with `data/source_manifest.json`. Apply the transport-only policy in `governance/verified_bucket_policy.json` through S3 Permissions after checking the bucket ARN. Merge with any existing policy rather than overwriting unrelated statements.

The verified environment reuses the existing `LabRole`. Inspect its service trust/permissions where authorized. Glue needs source reads and output/log writes; Lambda needs the corresponding S3 and logging permissions. The lab restricted IAM policy inspection and Lake Formation listing; do not attempt to remove lab denies. The proposed analyst policies are separate design artifacts and must not be substituted for execution-role permissions.

For a fresh bucket, `infrastructure/setup_s3.py` is an optional foundation-only bootstrap. It validates source hashes and previews by default:

```bash
python3 infrastructure/setup_s3.py --bucket NEW_UNIQUE_BUCKET --expected-account YOUR_12_DIGIT_ACCOUNT
```

Add `--apply` only to create the reviewed new bucket and upload originals. It stops if the bucket already exists, and does not provision Glue/Lambda/Athena or install the HTTPS policy. The existing deployed bucket should not be recreated.

## 2. POS Bash ingestion

From the repository root in CloudShell:

```bash
bash ingestion/ingest_pos.sh thornquist-data-lake-2026102 470551642447
```

This checks the account and copies the original Landing CSV to Raw. Expected Raw file size: 103,415 bytes and 1,051 data rows. The script does not upload the initial Landing file.

## 3. Ecommerce Lambda

Create `thornquist-ingest-ecommerce`, Python 3.14, x86_64, 128 MB and a 30-second timeout, using the authorized existing lab execution role. Paste `ingestion/lambda_function.py`; handler is `lambda_function.lambda_handler`. Set environment variable `BUCKET_NAME=thornquist-data-lake-2026102`.

Add an S3 ObjectCreated trigger for prefix `landing/ecommerce/` and suffix `.json`. Keep the source and destination prefixes distinct. Check the bucket's existing notification configuration when adding a trigger so unrelated notifications are retained. Upload the source file to the matching Landing key after the trigger is enabled. Expected log/result: `copied`, 265 orders, 143,360 bytes, destination `raw/ecommerce/ecommerce_orders.json`. Compare its SHA-256 with the source manifest. Both manual invocation and a real upload-triggered copy were verified.

For the separate Athena catalog representation, run:

```bash
python3 ingestion/convert_ecommerce_ndjson.py --bucket thornquist-data-lake-2026102
```

The helper reconstructs the manual conversion step, writes `raw/ecommerce_ndjson/ecommerce_orders.ndjson` and expects 265 orders. It is not attached to the Lambda or scheduled. The sales job continues to read the original array JSON.

## 4. Customer Glue job

Create Spark script job `thornquist-customer-ingestion` with `ingestion/glue/customer_ingestion.py`, existing `LabRole`, Glue 4.0 and two G.1X workers. Set parameters:

| Parameter | Value |
| --- | --- |
| `--S3_SOURCE_PATH` | `s3://thornquist-data-lake-2026102/landing/customers/customer_extract.csv` |
| `--S3_TARGET_PATH` | `s3://thornquist-data-lake-2026102/raw/customers/` |

Run and wait for success. Expected: 400 rows, seven string fields, Parquet under Raw customers. Create/activate scheduled Glue trigger `thornquist-customer-ingestion-daily`, daily at 07:00 UTC (`cron(0 7 * * ? *)`). The job overwrites its configured Raw destination. On 23 October, the trigger started run `jr_4d3cb3e1439b61f099dc644469422d22a6ced6c7537045b7ab34a6a40a891b8a` at 07:00:03 UTC; it succeeded at 07:01:18 UTC. The trigger was later observed deactivated, then restarted and confirmed `ACTIVATED` with the same schedule.

## 5. Catalog and crawler settings

Create Glue database `thornquist_outfitters`. Use `LabRole` and crawl all folders for the four S3 targets below. Raw crawler table prefix: `raw_`; Trusted prefix: `trusted_`.

| Crawler | Target relative to bucket | Daily UTC |
| --- | --- | --- |
| `thornquist-raw-customers-crawler` | `raw/customers/` | 07:15 |
| `thornquist-raw-ecommerce-crawler` | `raw/ecommerce_ndjson/` | 07:20 |
| `thornquist-raw-pos-crawler` | `raw/pos/` | 07:25 |
| `thornquist-trusted-sales-crawler` | `trusted/sales_model/` | 07:30 |

Run Raw crawlers after ingestion; run the Trusted crawler after the sales job. Use `SHOW TABLES IN thornquist_outfitters` to discover generated names. Validate counts: customers 400, ecommerce NDJSON 265 and POS 1,051. In the POS catalog table, ensure `transaction_id`, `store_id` and `cust_num` are strings. The POS crawler was changed to ignore schema updates to preserve these manual corrections. A saved post-crawl catalog screenshot shows all three identifier columns as strings; future schema changes still require review.

These schedules are independent timers and do not wait for upstream success. Sales ETL has no demonstrated automatic schedule in this deployment. The Trusted schedule therefore catalogs the latest available ETL output, rather than proving a newly completed daily sales refresh.

## 6. Sales validation and Trusted output

Create `thornquist-sales-etl` from `transform/glue_sales_etl.py`, using Glue 4.0, two G.1X workers, 20-minute timeout and zero retries. Parameters:

| Parameter | Value |
| --- | --- |
| `--CUSTOMERS_S3_PATH` | `s3://thornquist-data-lake-2026102/raw/customers/` |
| `--POS_S3_PATH` | `s3://thornquist-data-lake-2026102/raw/pos/pos_sales_2026-08-24_to_2026-08-30.csv` |
| `--ECOMMERCE_S3_PATH` | `s3://thornquist-data-lake-2026102/raw/ecommerce/ecommerce_orders.json` |
| `--TRUSTED_S3_PATH` | `s3://thornquist-data-lake-2026102/trusted/` |
| `--QUARANTINE_S3_PATH` | `s3://thornquist-data-lake-2026102/quarantine/` |
| `--REPORTS_S3_PATH` | `s3://thornquist-data-lake-2026102/reports/` |

`JOB_NAME` is supplied by Glue. Run manually after all Raw inputs exist. The script writes Parquet to `trusted/customers/`, `trusted/pos_sales/`, `trusted/ecommerce_orders/`, `trusted/sales_model/`; JSONL rejects under corresponding Quarantine subdirectories; and `reports/sales_model_summary.json`. Its current design collects small customer inputs and performs business validation in driver memory; larger workloads need distributed processing.

This script overwrites its named output datasets. Expected accepted/rejected counts and quality rules are in [schema_and_quality.md](schema_and_quality.md). Check the report before proceeding. Do not treat job success alone as evidence that every input record passed.

## 7. Curated and analytical SQL

In Athena, use the project database and a result location under `s3://thornquist-data-lake-2026102/athena-results/`. Demonstrated queries used workgroup `primary`.

`queries/00_trusted_sales_model.sql` provides a stable catalog definition over Trusted output for reproduction. Review any existing table before using it. `queries/00_curated_sales_ctas.sql` reconstructs the verified Curated shape: date, decimal measures, common reporting region, loyalty tier, and year/month partitions. It creates new data and must only target an absent table and empty location. Do not rerun it over the already deployed table or delete data merely to make CTAS succeed. For another run, use a separate table/path and review the resulting counts before replacing the reporting table.

Run `queries/validate_curated.sql`: expected 1,601 lines, 320,570.35 total, 1,048 POS lines and 553 ecommerce lines, August 24–30, 2026; partition `sale_year=2026/sale_month=08`.

Run numbered business queries 01–05; Q3 has separate product and category queries. Before categories, execute `validate_category_coverage.sql`: expected `Category matched`, 553 lines, 106,008.57 with no unmatched group. The original-deployment SQL files reconstruct the verified analytical logic and expected result schemas; they were not re-executed against AWS during initial repository assembly. The isolated `rehearsal01` run subsequently executed six business queries against its separate Curated table. Preserve the five original CSV exports. The category CSV is a transcription of the supplied final original-deployment query result.

## 8. Visualization

Install `requirements.txt`, open `analytics/Thornquist_Sales_Analytics.ipynb` in VS Code/Jupyter with `analytics/` as the working directory, and run all cells. It checks totals before plotting. Six chart outputs answer five business questions. The HTML version is a browser-readable snapshot. Changes in AWS do not automatically update these local files.

## 9. Monitoring and audit

Use the enabled Glue failure pattern from `governance/glue_failure_event_pattern.json` with EventBridge rule `thornquist-glue-job-failures` on the default bus. Target SNS topic `thornquist-pipeline-alerts`. The observed SNS service publishing statement is retained separately; it is not a full replacement topic policy. Add the target through the console and preserve existing permissions.

The Lambda alarm `thornquist-ecommerce-lambda-errors` monitors Errors >=1 for one datapoint within five minutes and targets that SNS topic. The saved alarm was OK with actions enabled; its statistic was Sum and missing data was treated as not breaching. Confirm the SNS email subscription. A direct SNS test message was received. Run the read-only filter test with:

```bash
python3 monitoring/test_glue_failure_pattern.py
```

Seven cases passed in the lab; pattern matching alone does not publish events. Separate controlled tests then exercised delivery: `set-alarm-state` forced the Lambda alarm to `ALARM` and sent an email, and customer Glue run `jr_37406547be22c09f7013fff8615e8c1ead464eb98f8734007dd1ee36df94bc88` failed on an intentionally missing test input and sent an email through EventBridge/SNS. The forced alarm transition did not test real Lambda error detection. CloudTrail Event history supplies management-event evidence; a dedicated trail and object-level audit were not verified. See [monitoring_and_automation.md](monitoring_and_automation.md).

## SQL reference

Athena CTAS properties and empty destination requirements: https://docs.aws.amazon.com/athena/latest/ug/create-table-as.html
