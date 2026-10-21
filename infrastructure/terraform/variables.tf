variable "aws_region" {
  description = "AWS region for the Thornquist Outfitters catalog."
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Existing S3 data lake bucket; Terraform will not create or modify the bucket."
  type        = string
  default     = "thornquist-data-lake"
}

variable "crawler_schedule" {
  description = "Glue crawler schedule in UTC. For rapid testing, crawlers can also be started manually."
  type        = string
  default     = "cron(0 6 * * ? *)"
}
