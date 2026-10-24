# Lake Formation analyst permission set — PROPOSED, NOT DEPLOYED

Target region: us-east-1. Catalog/account: __ACCOUNT__.
Hypothetical principal: arn:aws:iam::__ACCOUNT__:role/ThornquistAnalyst.

The lab denied lakeformation:ListPermissions. No grants or revocations were made during this review. Empty UI results after an authorization failure are not evidence of an empty permission set.

| Resource | Permission | Grant option | Rationale |
| --- | --- | --- | --- |
| Database __DATABASE__ | DESCRIBE | No | Discover the database containing the approved table |
| Table __DATABASE__.curated_sales | SELECT, DESCRIBE | No | Query accepted, analysis-ready sales only |
| Landing/Raw/Trusted tables | None | No | No access to pre-validation or higher-detail records |
| Quarantine and remediation demo tables | None | No | Rejects/test copies excluded from analyst data |
| Data locations | No DATA_LOCATION_ACCESS for analyst | No | Analyst must not create catalog tables against arbitrary lake locations |
| Catalog/database/table creation and mutation | No CREATE_DATABASE, CREATE_TABLE, ALTER, DROP, INSERT, DELETE or ALL | No | Read-only analyst persona |

Database DESCRIBE is not a SELECT grant on every table. Table SELECT must be limited to the named curated table, not a wildcard.

## Administrator prerequisites

- Approve a separate analyst identity; do not use the same LabRole as the processing jobs.
- Register only the intended curated S3 location with an appropriately scoped data-access role, and configure Athena/LF integration.
- Inspect and handle IAMAllowedPrincipals grants or explicitly opt the intended resources/principal into hybrid access mode. Named grants alone do not prove restrictive enforcement if broad IAM access remains effective. Do not modify these settings in the working lab without authorization and regression tests.
- Apply the companion scoped IAM policy and dedicated workgroup design. Restrict direct S3 source access to avoid bypassing any future row/column filtering.
- Test both allowed curated queries and denied raw/trusted queries; retain results.

## Production extension, not implemented

Regional-manager row filters and column restrictions could further reduce exposure. They are not part of the deployed lab. Customer ID, source metadata and location fields should be assessed before a broader analyst rollout. Query result files also need controlled access because they contain extracted data.
