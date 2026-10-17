# Thornquist Outfitters — Governed AWS Data Lake

AWS data engineering group project integrating POS sales, e-commerce orders, and customer data into a governed data lake using Amazon S3, AWS Glue, AWS Lambda, and Amazon Athena.

## Architecture

![Proposed Data Lake Architecture](architecture/Thornquist_Architecture.png)

The diagram shows the proposed data flow from source ingestion through S3 zones, data quality, transformation, and analytics. Components shown are not necessarily deployed yet.

## Team Responsibilities

| Member | Responsibility |
|---|---|
| Alahi | S3 infrastructure, source datasets, architecture, documentation, evidence |
| Justin | Ingestion pipelines, AWS Glue ETL, data quality |
| Seyi | Athena analytics, curated data, visualization, governance |

## AWS Environment

- Region: `us-east-1`
- S3 bucket: `thornquist-data-lake-826238174496`
- AWS Academy Learner Lab

## S3 Data Lake Zones

| Zone | Purpose |
|---|---|
| landing/ | Original source files |
| raw/ | Ingested source data |
| trusted/ | Validated and cleaned data |
| curated/ | Analytics-ready datasets |
| quarantine/ | Rejected or invalid records |
| athena-results/ | Athena query results |

## Original Source Datasets

| Dataset | Records |
|---|---:|
| POS Sales CSV | 1,051 |
| E-commerce Orders JSON | 265 |
| Customer Extract CSV | 400 |

All three original datasets were uploaded unchanged to the S3 landing zone and verified.

## Verified S3 Security

- Default server-side encryption: SSE-S3 (AES256)
- S3 Block Public Access: All four settings enabled
- Versioning: Not enabled at verification time
- Bucket policy: Not configured at verification time

## Infrastructure Verification

```bash
aws s3 ls s3://thornquist-data-lake-826238174496/ --region us-east-1
aws s3 ls s3://thornquist-data-lake-826238174496/landing/ --recursive --region us-east-1
aws s3api get-bucket-encryption --bucket thornquist-data-lake-826238174496 --region us-east-1
aws s3api get-public-access-block --bucket thornquist-data-lake-826238174496 --region us-east-1
```

## Documentation and Evidence

- [S3 Infrastructure Documentation](docs/S3_INFRASTRUCTURE.md)
- [S3 Source Dataset Evidence](evidence/Issue02_S3_Source_Datasets.png)
- [Architecture Diagram](architecture/Thornquist_Architecture.png)

## Implementation Status

**Verified:** S3 zones, original datasets, encryption, public access settings, architecture documentation, and S3 evidence.

**Pending team verification:** Ingestion pipelines, Glue ETL, data quality, trusted and curated datasets, Athena analytics, visualization, and governance implementation.

## Deployment Notes

This repository documents the AWS Academy project. Full pipeline deployment and reproducibility instructions will be added after the remaining team components are implemented and tested.
