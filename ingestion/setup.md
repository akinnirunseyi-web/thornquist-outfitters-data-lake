# Glue Data Catalog setup (local-first)

## Scope
Terraform manages the Glue database, three scheduled S3 crawlers, the crawler IAM role/policies, and an explicitly defined POS table. It references the existing S3 bucket and does not create it.

## Expected S3 source locations
- `s3://thornquist-data-lake-826238174496/landing/pos/`
- `s3://thornquist-data-lake-826238174496/landing/ecommerce/`
- `s3://thornquist-data-lake-826238174496/landing/customers/`

These prefixes are based on `data/S3_UPLOAD_COMMANDS.txt`. Confirm the team uploaded the files to these exact paths before deployment.

## Local validation (does not deploy or require AWS credentials)
From the repository root, run:

```bash
terraform -chdir=infrastructure/terraform fmt -recursive
terraform -chdir=infrastructure/terraform init -backend=false
terraform -chdir=infrastructure/terraform validate
terraform -chdir=infrastructure/terraform plan -var-file=terraform.tfvars
```

Create `infrastructure/terraform/terraform.tfvars` from `terraform.tfvars.example` if you need to override values. Do not commit real credentials or sensitive values. `plan` reads AWS account information through the provider, so it may require valid AWS credentials; `fmt`, `init -backend=false`, and `validate` are local code checks.

## Deployment (only after local review)
Configure valid AWS credentials for the correct learner lab/session, then review the plan. Deploy only after confirming the bucket and IAM permissions are in scope:

```bash
terraform -chdir=infrastructure/terraform init
terraform -chdir=infrastructure/terraform plan -var-file=terraform.tfvars
terraform -chdir=infrastructure/terraform apply -var-file=terraform.tfvars
```

Terraform requires permission to create Glue resources and IAM roles/policies. Some learner labs restrict IAM creation; if so, use the role provided by the lab and adapt the Terraform instead of repeatedly retrying.

## Run crawlers and inspect tables
After deployment, start the crawlers manually for immediate verification:

```bash
aws glue start-crawler --name thornquist-pos-crawler --region us-east-1
aws glue start-crawler --name thornquist-ecommerce-crawler --region us-east-1
aws glue start-crawler --name thornquist-customers-crawler --region us-east-1
```

Wait until each crawler state is `READY` before checking the tables. The daily schedule is UTC; manual starts are faster for project evidence. The crawler output table names depend on the source filenames and Glue naming rules, so inspect the Glue database and use the actual names in Athena queries.

## Why the manual POS table exists
The POS source has mixed `sale_date` formats and customer identifiers such as `0000000`. Crawler type inference can infer a numeric type for identifier columns and a date type for only part of the mixed date values. The explicit `pos_sales_manual` table keeps all source columns as strings so leading zeros and original date text are preserved. Parse/cast fields later in ETL after applying documented rules.

## Add-file update test
Add a small, valid additional source file to one of the existing source prefixes (do not overwrite the original dataset), then run the matching crawler again. Verify the crawler run succeeded and inspect the catalog table/location and Athena row results. A new file does not always create a new table; if it has a compatible schema and is in the same prefix, the existing table should normally be updated to cover the prefix. Record actual observed results in `evidence/`.

## Evidence to capture after deployment
1. Glue database showing the three crawler-discovered tables and `pos_sales_manual`.
2. Successful run details for all three crawlers.
3. POS crawler schema compared with the explicit manual table schema.
4. Athena query editor/results for `queries/catalog-validation.sql`.
5. Crawler run and Athena results after adding the test file.

Do not label planned or local validation as successful AWS deployment evidence.
