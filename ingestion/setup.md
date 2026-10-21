# Thornquist Outfitters — Data Ingestion Setup

## Scope

Terraform manages the S3 data lake infrastructure, Glue Data Catalog,
source crawlers, the explicit POS table, the e-commerce Lambda ingestion,
and the Glue customer ingestion job.

The customer ingestion trigger is currently disabled to avoid automatic
job executions during development. Run the Glue job manually when needed.

## AWS environment

- Region: us-east-1
- S3 bucket: thornquist-data-lake-659260838742
- Glue database: thornquist_outfitters

## S3 data locations

### Landing zone

- POS CSV: s3://thornquist-data-lake-659260838742/landing/pos/
- E-commerce JSON: s3://thornquist-data-lake-659260838742/landing/ecommerce/
- Customers CSV: s3://thornquist-data-lake-659260838742/landing/customers/

### Raw zone

- E-commerce NDJSON: s3://thornquist-data-lake-659260838742/raw/ecommerce/
- Customers Parquet: s3://thornquist-data-lake-659260838742/raw/customers/

## Ingestion workflows

### 1. POS CSV upload

Run from the repository root:

    ./ingestion/scripts/upload_pos.sh

The script uploads the POS source CSV to the landing zone and verifies
the uploaded object.

### 2. E-commerce JSON ingestion

The Lambda function `thornquist-ecommerce-ingestion` processes JSON objects
uploaded under `landing/ecommerce/`.

It converts each order to one NDJSON line and writes the result under
`raw/ecommerce/`. The S3 event notification filters the landing prefix and
`.json` suffix to prevent recursive invocations from raw-zone output.

### 3. Customer CSV to Parquet

The Glue job `thornquist-customer-ingestion` reads customer CSV data from
`landing/customers/` and writes Parquet output to `raw/customers/`.

The transformation keeps customer fields as strings to preserve identifiers
such as leading zeros. The job overwrites its target output when rerun.

Start a run manually:

    aws glue start-job-run \
      --job-name thornquist-customer-ingestion \
      --region us-east-1

Check the latest run status:

    aws glue get-job-runs \
      --job-name thornquist-customer-ingestion \
      --region us-east-1 \
      --max-results 1 \
      --query 'JobRuns[0].[Id,JobRunState,ErrorMessage]' \
      --output table

## Glue crawlers

| Crawler | S3 target |
|---|---|
| `thornquist-pos-crawler` | `landing/pos/` |
| `thornquist-ecommerce-crawler` | `landing/ecommerce/` |
| `thornquist-customers-crawler` | `landing/customers/` |
| `thornquist-customers-raw-crawler` | `raw/customers/` |

The raw customer crawler catalogs the transformed Parquet dataset separately
from the original landing CSV data.

## Validation and verified results

- POS CSV uploaded; verified size: 103,415 bytes.
- E-commerce Lambda test produced 265 NDJSON lines.
- Customer Glue job completed successfully.
- Parquet output was created under `raw/customers/`.
- Raw customer crawler completed successfully.
- The raw customer table exposes seven expected columns:
  `cust_num`, `first_name`, `last_name`, `email`, `signup_date`,
  `loyalty_tier`, and `region`.
- The scheduled customer ingestion trigger is deactivated during development.

## Terraform validation

From `infrastructure/terraform/`, run:

    terraform fmt
    terraform validate
    terraform plan

Review the plan before applying infrastructure changes. Do not commit
Terraform state files, saved plans, credentials, or secrets.
