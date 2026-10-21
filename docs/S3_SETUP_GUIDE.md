# Reproduce the Thornquist S3 foundation

## Purpose and ownership

This script reproduces the S3 foundation assigned to Alahi in a fresh AWS account/bucket. Seyi's final deployment was created manually; saving this script does not mean that script deployment has been tested in AWS.

It creates the following in us-east-1:

- A general-purpose bucket with a new globally unique name.
- SSE-S3 (AES256) default encryption, BucketOwnerEnforced ownership (ACLs disabled), and all four Block Public Access settings enabled.
- Versioning left disabled on the new bucket; no bucket policy or lifecycle rules added at this stage.
- landing/, raw/, trusted/, curated/, quarantine/, athena-results/.
- landing/pos/, landing/ecommerce/, landing/customers/.
- The three unchanged instructor datasets under their corresponding landing folders.

This is the foundation only. Lambda ingestion, scheduled Glue loading, ETL, data quality, catalog tables, governance policies and analytics are separate deployment steps. Uploading all three source files does not satisfy the three distinct ingestion mechanisms requirement.

## Required repository files

Keep these paths in the existing repository:

```
infrastructure/setup_s3.py
docs/S3_SETUP_GUIDE.md
data/pos_sales_2026-08-24_to_2026-08-30.csv
data/ecommerce_orders.json
data/customer_extract.csv
```

The data files are already in the shared repository. The script checks their SHA-256 hashes against the verified instructor originals before deployment. It checks the uploaded bytes again after deployment.

## Run in a colleague's lab only when a new foundation is needed

Do not run --apply against Seyi's existing bucket. Existing buckets are intentionally refused; this script does not import, reset or overwrite them.

1. Start the target person's Learner Lab and open its AWS Console. Use their own authorized session; do not share login details or access keys.
2. Open AWS CloudShell in us-east-1 if it is permitted by that lab. Alternatively use an authorized terminal with Python 3, AWS CLI and the target lab's temporary credentials configured locally. Never save credentials in GitHub.
3. Download the shared repository's main branch as a ZIP. In CloudShell use Actions > Upload file to upload the ZIP. Extract it with the command below. If you previously extracted it, use that existing folder instead of overwriting files.

```bash
unzip thornquist-outfitters-data-lake-main.zip
cd thornquist-outfitters-data-lake-main
python3 -m pip install --user boto3
aws sts get-caller-identity --query Account --output text
```

4. Note the 12-digit account ID printed by the last command. Choose a NEW globally unique bucket name, for example thornquist-data-lake-YOURACCOUNTID-final (replace YOURACCOUNTID with the actual digits).
5. Preview using the following command, replacing BOTH placeholders. Preview checks local datasets and prints the plan; it does not contact AWS or verify credentials.

```bash
python3 infrastructure/setup_s3.py --bucket YOUR-NEW-BUCKET-NAME --expected-account YOURACCOUNTID
```

6. Confirm the printed account, bucket and paths. Deploy using the same values plus --apply:

```bash
python3 infrastructure/setup_s3.py --bucket YOUR-NEW-BUCKET-NAME --expected-account YOURACCOUNTID --apply
```

The apply mode checks the signed-in AWS account before making changes. It stops if the name exists or availability cannot be confirmed. It creates no IAM roles and uses the permissions of the current session. If the lab denies an operation, save the error and check the lab restrictions; do not work around them by sharing credentials.

If a later operation fails, the bucket may be partially configured. The script deliberately leaves it for inspection and does not delete anything. A second run with that bucket name stops. Complete the identified missing operation after review; do not delete the bucket just to rerun this script.

## Evidence and documentation checkpoint

After an actual successful deployment:

- Save the terminal success output and checksum verification results.
- Capture the six top-level folders and the three uploaded source files with their paths visible.
- Capture encryption, versioning and public-access settings.
- Save final deployment evidence under evidence/integration/s3/ in the shared repository.
- Record the actual deployment account, bucket, region, method (manual or script) and validation results in docs/FINAL_DEPLOYMENT.md. Preserve Alahi's earlier account details as development history.
- Update downstream scripts and job parameters to use the chosen final bucket. GitHub does not copy resources between AWS accounts.

Do not claim the script was AWS-tested until someone has actually run it successfully. Local syntax and preview checks are separate from a real deployment.

## Reference

AWS CLI bucket creation and ownership documentation: https://docs.aws.amazon.com/cli/latest/reference/s3api/create-bucket.html

AWS S3 CLI setup examples: https://docs.aws.amazon.com/AmazonS3/latest/userguide/GettingStartedS3CLI.html
