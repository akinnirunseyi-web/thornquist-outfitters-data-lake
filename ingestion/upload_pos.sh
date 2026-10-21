#!/usr/bin/env bash
set -euo pipefail

BUCKET_NAME="${1:-thornquist-data-lake-659260838742}"
SOURCE_FILE="${2:-data/pos_sales_2026-08-24_to_2026-08-30.csv}"
DESTINATION_KEY="landing/pos/$(basename "$SOURCE_FILE")"

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "ERROR: Source file not found: $SOURCE_FILE" >&2
  exit 1
fi

aws s3 cp "$SOURCE_FILE" "s3://${BUCKET_NAME}/${DESTINATION_KEY}" \
  --region us-east-1

aws s3api head-object \
  --bucket "$BUCKET_NAME" \
  --key "$DESTINATION_KEY" \
  --region us-east-1 \
  --query '{Key:Key,Size:ContentLength,LastModified:LastModified}' \
  --output table

echo "POS upload verified: s3://${BUCKET_NAME}/${DESTINATION_KEY}"
