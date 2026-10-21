
resource "aws_s3_bucket" "lake" {
  bucket = local.bucket_name

  tags = {
    Project     = "Thornquist Outfitters"
    Environment = "Learning"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket = aws_s3_bucket.lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


locals {
  bucket_name = "${var.bucket_name}-${data.aws_caller_identity.current.account_id}"
}

data "aws_caller_identity" "current" {}

locals {
  source_prefixes = {
    pos       = "landing/pos/"
    ecommerce = "landing/ecommerce/"
    customers = "landing/customers/"
  }

  crawler_names = {
    pos       = "thornquist-pos-crawler"
    ecommerce = "thornquist-ecommerce-crawler"
    customers = "thornquist-customers-crawler"
  }
}

resource "aws_glue_catalog_database" "thornquist" {
  name        = "thornquist_outfitters"
  description = "Glue Data Catalog database for Thornquist Outfitters source datasets."
}

resource "aws_iam_role" "glue_crawler" {
  name = "thornquist-glue-crawler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service_role" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "source_read" {
  name = "thornquist-glue-source-read"
  role = aws_iam_role.glue_crawler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListLakeBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::${local.bucket_name}"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "landing",
              "landing/*"
            ]
          }
        }
      },
      {
        Sid      = "ReadSourceObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${local.bucket_name}/landing/*"
      }
    ]
  })
}

resource "aws_glue_crawler" "sources" {
  for_each      = local.source_prefixes
  name          = local.crawler_names[each.key]
  database_name = aws_glue_catalog_database.thornquist.name
  role          = aws_iam_role.glue_crawler.arn
  description   = "Catalog source dataset under s3://${local.bucket_name}/${each.value}"

  s3_target {
    path = "s3://${local.bucket_name}/${each.value}"
  }

  schedule = var.crawler_schedule

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }

  depends_on = [
    aws_iam_role_policy_attachment.glue_service_role,
    aws_iam_role_policy.source_read
  ]
}

# Explicit POS table: all fields are strings to preserve customer IDs such as
# "0000000" and the mixed source date formats (YYYY-MM-DD and DD/MM/YYYY).
# The crawler-discovered POS table remains available for comparison.
resource "aws_glue_catalog_table" "pos_manual" {
  name          = "pos_sales_manual"
  database_name = aws_glue_catalog_database.thornquist.name
  description   = "Manually curated POS CSV schema. String fields preserve leading-zero IDs and mixed date representations."
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL                 = "TRUE"
    classification           = "csv"
    "skip.header.line.count" = "1"
    "projection.enabled"     = "false"
  }

  storage_descriptor {
    location      = "s3://${local.bucket_name}/landing/pos/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    compressed    = false

    ser_de_info {
      name                  = "thornquist-pos-opencsv"
      serialization_library = "org.apache.hadoop.hive.serde2.OpenCSVSerde"
      parameters = {
        separatorChar = ","
        quoteChar     = "\""
        escapeChar    = "\\"
      }
    }

    columns {
      name = "transaction_id"
      type = "string"
    }
    columns {
      name = "store_id"
      type = "string"
    }
    columns {
      name = "store_name"
      type = "string"
    }
    columns {
      name = "region"
      type = "string"
    }
    columns {
      name = "sale_date"
      type = "string"
    }
    columns {
      name = "category"
      type = "string"
    }
    columns {
      name = "product_name"
      type = "string"
    }
    columns {
      name = "quantity"
      type = "string"
    }
    columns {
      name = "unit_price"
      type = "string"
    }
    columns {
      name = "payment_method"
      type = "string"
    }
    columns {
      name = "cust_num"
      type = "string"
    }
  }
}

output "glue_database_name" {
  value       = aws_glue_catalog_database.thornquist.name
  description = "Glue database created for the project."
}

output "crawler_names" {
  value       = { for key, crawler in aws_glue_crawler.sources : key => crawler.name }
  description = "Source crawler names."
}

output "manual_pos_table" {
  value       = aws_glue_catalog_table.pos_manual.name
  description = "Manually curated POS table name."
}

output "source_locations" {
  value = {
    for key, prefix in local.source_prefixes :
    key => "s3://${local.bucket_name}/${prefix}"
  }
}
