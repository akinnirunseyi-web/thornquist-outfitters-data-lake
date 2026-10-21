# Package the e-commerce Lambda handler.
data "archive_file" "ecommerce_lambda" {
  type        = "zip"
  source_file = "${path.module}/../../ingestion/lambda/ecommerce_handler.py"
  output_path = "${path.module}/.terraform/ecommerce_handler.zip"
}

# Lambda execution role.
resource "aws_iam_role" "ecommerce_lambda" {
  name = "thornquist-ecommerce-ingestion-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecommerce_lambda_logs" {
  role       = aws_iam_role.ecommerce_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "ecommerce_lambda_s3" {
  name = "thornquist-ecommerce-s3-access"
  role = aws_iam_role.ecommerce_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadEcommerceLanding"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${local.bucket_name}/landing/ecommerce/*"
      },
      {
        Sid      = "WriteEcommerceRaw"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:aws:s3:::${local.bucket_name}/raw/ecommerce/*"
      }
    ]
  })
}

resource "aws_lambda_function" "ecommerce_ingestion" {
  function_name    = "thornquist-ecommerce-ingestion"
  description      = "Converts landing e-commerce JSON arrays into NDJSON in the raw zone."
  role             = aws_iam_role.ecommerce_lambda.arn
  handler          = "ecommerce_handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.ecommerce_lambda.output_path
  source_code_hash = data.archive_file.ecommerce_lambda.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      SOURCE_PREFIX      = "landing/ecommerce/"
      DESTINATION_PREFIX = "raw/ecommerce/"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecommerce_lambda_logs,
    aws_iam_role_policy.ecommerce_lambda_s3
  ]

  tags = {
    Project = "Thornquist Outfitters"
  }
}

# S3 is allowed to invoke the Lambda function.
resource "aws_lambda_permission" "allow_ecommerce_s3" {
  statement_id  = "AllowS3InvokeEcommerceIngestion"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ecommerce_ingestion.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.lake.arn
}

# Trigger only for JSON files uploaded to the e-commerce landing prefix.
# The Lambda writes to raw/ecommerce/, so its output cannot retrigger it.
resource "aws_s3_bucket_notification" "ecommerce_ingestion" {
  bucket = aws_s3_bucket.lake.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ecommerce_ingestion.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "landing/ecommerce/"
    filter_suffix       = ".json"
  }

  depends_on = [
    aws_lambda_permission.allow_ecommerce_s3
  ]
}

# Upload the Glue customer ingestion script to S3.
resource "aws_s3_object" "customer_ingestion_script" {
  bucket       = aws_s3_bucket.lake.id
  key          = "infrastructure/glue/customer_ingestion.py"
  source       = "${path.module}/../../ingestion/glue/customer_ingestion.py"
  source_hash  = filemd5("${path.module}/../../ingestion/glue/customer_ingestion.py")
  content_type = "text/x-python"
}

# Glue execution role for the customer ingestion job.
resource "aws_iam_role" "customer_ingestion_glue" {
  name = "thornquist-customer-ingestion-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "glue.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "customer_ingestion_glue_service" {
  role       = aws_iam_role.customer_ingestion_glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "customer_ingestion_s3" {
  name = "thornquist-customer-ingestion-s3-access"
  role = aws_iam_role.customer_ingestion_glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListRequiredLakePrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::${local.bucket_name}"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "landing/customers",
              "landing/customers/*",
              "raw/customers",
              "raw/customers/*",
              "glue-temp",
              "glue-temp/*",
              "infrastructure/glue",
              "infrastructure/glue/*"
            ]
          }
        }
      },
      {
        Sid    = "ReadCustomerSourceAndScript"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "arn:aws:s3:::${local.bucket_name}/landing/customers/*",
          "arn:aws:s3:::${local.bucket_name}/infrastructure/glue/*"
        ]
      },
      {
        Sid    = "WriteCustomerOutputAndTemp"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:AbortMultipartUpload"]
        Resource = [
          "arn:aws:s3:::${local.bucket_name}/raw/customers/*",
          "arn:aws:s3:::${local.bucket_name}/glue-temp/*"
        ]
      },
      {
        Sid      = "ReadBucketLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = "arn:aws:s3:::${local.bucket_name}"
      }
    ]
  })
}

resource "aws_glue_job" "customer_ingestion" {
  name              = "thornquist-customer-ingestion"
  description       = "Reads customer CSV data from landing and writes Parquet to raw."
  role_arn          = aws_iam_role.customer_ingestion_glue.arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 10
  max_retries       = 0

  command {
    name            = "glueetl"
    script_location = "s3://${local.bucket_name}/${aws_s3_object.customer_ingestion_script.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--S3_SOURCE_PATH"                   = "s3://${local.bucket_name}/landing/customers/"
    "--S3_TARGET_PATH"                   = "s3://${local.bucket_name}/raw/customers/"
    "--TempDir"                          = "s3://${local.bucket_name}/glue-temp/"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
  }

  depends_on = [
    aws_iam_role_policy_attachment.customer_ingestion_glue_service,
    aws_iam_role_policy.customer_ingestion_s3
  ]

  tags = {
    Project = "Thornquist Outfitters"
  }
}

# Run the customer ingestion once daily at 07:00 UTC.
resource "aws_glue_trigger" "customer_ingestion_daily" {
  name     = "thornquist-customer-ingestion-daily"
  type     = "SCHEDULED"
  schedule = "cron(0 7 * * ? *)"
  enabled  = false

  actions {
    job_name = aws_glue_job.customer_ingestion.name
  }
}

output "ecommerce_lambda_name" {
  value       = aws_lambda_function.ecommerce_ingestion.function_name
  description = "Lambda function for e-commerce JSON ingestion."
}

output "customer_ingestion_job_name" {
  value       = aws_glue_job.customer_ingestion.name
  description = "Scheduled Glue job for customer CSV ingestion."
}

# Sales ETL: validate, normalize, reconcile and publish Trusted/Quarantine data.
resource "aws_s3_object" "sales_etl_script" {
  bucket       = local.bucket_name
  key          = "infrastructure/glue/glue_sales_etl.py"
  source       = "${path.module}/../../transform/glue_sales_etl.py"
  source_hash  = filemd5("${path.module}/../../transform/glue_sales_etl.py")
  content_type = "text/x-python"
}

resource "aws_iam_role" "sales_etl_glue" {
  name = "thornquist-sales-etl-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "glue.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sales_etl_glue_service" {
  role       = aws_iam_role.sales_etl_glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "sales_etl_s3" {
  name = "thornquist-sales-etl-s3-access"
  role = aws_iam_role.sales_etl_glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListLakePrefixes"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::${local.bucket_name}"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "landing/customers", "landing/customers/*",
              "landing/pos", "landing/pos/*",
              "landing/ecommerce", "landing/ecommerce/*",
              "infrastructure/glue", "infrastructure/glue/*",
              "trusted", "trusted/*",
              "quarantine", "quarantine/*",
              "reports", "reports/*",
              "glue-temp", "glue-temp/*"
            ]
          }
        }
      },
      {
        Sid    = "ReadSourcesAndScript"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "arn:aws:s3:::${local.bucket_name}/landing/customers/*",
          "arn:aws:s3:::${local.bucket_name}/landing/pos/*",
          "arn:aws:s3:::${local.bucket_name}/landing/ecommerce/*",
          "arn:aws:s3:::${local.bucket_name}/infrastructure/glue/*"
        ]
      },
      {
        Sid    = "WriteETLOutputsAndTemp"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::${local.bucket_name}/trusted/*",
          "arn:aws:s3:::${local.bucket_name}/trusted_$folder$",
          "arn:aws:s3:::${local.bucket_name}/quarantine/*",
          "arn:aws:s3:::${local.bucket_name}/reports/*",
          "arn:aws:s3:::${local.bucket_name}/glue-temp/*"
        ]
      },
      {
        Sid      = "ReadBucketLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = "arn:aws:s3:::${local.bucket_name}"
      }
    ]
  })
}

resource "aws_glue_job" "sales_etl" {
  name              = "thornquist-sales-etl"
  description       = "Validates source records, quarantines invalid data, reconciles orders and builds the sales model."
  role_arn          = aws_iam_role.sales_etl_glue.arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 20
  max_retries       = 0

  command {
    name            = "glueetl"
    script_location = "s3://${local.bucket_name}/${aws_s3_object.sales_etl_script.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--CUSTOMERS_S3_PATH"                = "s3://${local.bucket_name}/landing/customers/customer_extract.csv"
    "--POS_S3_PATH"                      = "s3://${local.bucket_name}/landing/pos/pos_sales_2026-08-24_to_2026-08-30.csv"
    "--ECOMMERCE_S3_PATH"                = "s3://${local.bucket_name}/landing/ecommerce/ecommerce_orders.json"
    "--TRUSTED_S3_PATH"                  = "s3://${local.bucket_name}/trusted"
    "--QUARANTINE_S3_PATH"               = "s3://${local.bucket_name}/quarantine"
    "--REPORTS_S3_PATH"                  = "s3://${local.bucket_name}/reports/sales_model"
    "--TempDir"                          = "s3://${local.bucket_name}/glue-temp/"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
  }

  depends_on = [
    aws_iam_role_policy_attachment.sales_etl_glue_service,
    aws_iam_role_policy.sales_etl_s3
  ]

  tags = {
    Project = "Thornquist Outfitters"
  }
}

output "sales_etl_job_name" {
  value       = aws_glue_job.sales_etl.name
  description = "AWS Glue job for sales data quality, reconciliation and modeling."
}
