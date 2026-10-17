# Thornquist Outfitters — S3 Data Lake Infrastructure

## AWS Environment
- Region: `us-east-1`
- S3 bucket: `thornquist-data-lake-826238174496`
- Environment: AWS Academy Learner Lab

## S3 Zones
| Prefix | Purpose |
|---|---|
| `landing/` | Initial arrival of source datasets |
| `raw/` | Original source data preserved for processing |
| `trusted/` | Validated and cleaned data |
| `curated/` | Analytics-ready datasets |
| `quarantine/` | Records failing data-quality checks |

## Existing Source Paths
- POS: `landing/pos/pos_sales.csv`
- E-commerce: `landing/ecommerce/ecommerce_orders.json`
- Customers: `landing/customers/customer_extract.csv`

## Data Promotion Conditions
- Landing to Raw: Preserve source data without modifying original records.
- Raw to Trusted: Apply schema reconciliation and data-quality validation; send failed records to quarantine.
- Trusted to Curated: Produce partitioned Parquet datasets for analytics.

## Reproduce the S3 Structure
Create an S3 bucket with a globally unique name in `us-east-1`, then create these prefixes: `landing/`, `raw/`, `trusted/`, `curated/`, `quarantine/`.

Upload the three synthetic datasets from the repository's `data/` directory to their matching `landing/` prefixes.

## Coordination
- Athena query-results prefix: awaiting agreement with Seyi.
- S3 access and bucket policy: coordinate with Seyi.
- AWS Academy Learner Lab accounts may have different account IDs and permissions; use the bucket name created in your own environment.
- Athena query results: `s3://thornquist-data-lake-826238174496/athena-results/`
- This prefix was agreed with Seyi on October 17, 2026.
- The prefix was successfully created in AWS S3 using CloudShell.
- Athena query results will remain separate from the landing, raw, trusted, and curated data zones.
