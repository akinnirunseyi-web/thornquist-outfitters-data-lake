# Ecommerce ingestion deployment

## Purpose and ownership
Automatically copy ecommerce JSON files from Landing to Raw when
they are uploaded to S3. This implements the ecommerce ingestion
component within Justin’s assigned scope.

Seyi deployed and tested this implementation in the final AWS account.

## Tested configuration
- AWS account: 470551642447
- Region: us-east-1
- Bucket: thornquist-data-lake-2026102
- Lambda function: thornquist-ingest-ecommerce
- Source code: ingestion/lambda_function.py
- Runtime: Python 3.14
- Architecture: x86_64
- Handler: lambda_function.lambda_handler
- Execution role: LabRole
- Memory: 128 MB
- Timeout: 30 seconds
- Environment variable:
  BUCKET_NAME=thornquist-data-lake-2026102

## S3 trigger
- Bucket: thornquist-data-lake-2026102
- Event: s3:ObjectCreated:*
- Prefix: landing/ecommerce/
- Suffix: .json

The function writes to raw/ecommerce/, outside the trigger prefix.

## Deploy in another AWS lab
1. Confirm the target AWS account and use us-east-1.
2. Prepare the target S3 bucket and original ecommerce dataset.
3. Create the Lambda function using the configuration above.
4. Select an execution role in the target account that Lambda can
   assume and that permits reading Landing, writing Raw, and logging
   to CloudWatch. LabRole was used in the tested account.
5. Copy ingestion/lambda_function.py into the Lambda code editor
   as lambda_function.py and deploy.
6. Set BUCKET_NAME to the target bucket name.
7. Configure the S3 trigger with the prefix and suffix above.
   S3 must have permission to invoke the function.
8. Upload the unchanged ecommerce_orders.json into
   landing/ecommerce/ after configuring the trigger.
9. Check the new CloudWatch invocation and the Raw output.

Use the target account’s bucket and role when deploying elsewhere.

## Validation completed on October 21, 2026
Both a manual test and an automatic S3 upload test succeeded.

Automatic invocation:
- Time: 2026-10-21T17:58:37.968Z
- Request ID: 6dba7a8c-2af0-4f18-bb2e-be7a8a3fc9d9
- Status: copied
- Source: landing/ecommerce/ecommerce_orders.json
- Target: raw/ecommerce/ecommerce_orders.json
- Order count: 265
- File size: 143360 bytes
- Source SHA-256:
  874604830bfcb953e7c87fe514441b5be4f593811aeeaa55a825d56c587222d0

The automatic test used a fresh upload of the unchanged original
file, without pressing the Lambda Test button.

## Processing behaviour
The function validates that the input is a JSON array of objects.
It preserves the original file bytes when writing to Raw and stores
the source SHA-256 in object metadata.

Repeated processing of the same filename writes to the same Raw key.
Business data-quality checks, deduplication, schema reconciliation,
and quarantine processing are handled separately.

## Evidence
Screenshots are retained locally for upload to the repository:
- 13-ecommerce-s3-trigger.png
- 14-ecommerce-trigger-upload.png
- 15-ecommerce-automatic-ingestion.png
