#!/usr/bin/env bash
set -euo pipefail

BUCKET="${1:?Provide the target bucket name}"
EXPECTED_ACCOUNT="${2:?Provide the target AWS account ID}"
REGION="us-east-1"
FILE="pos_sales_2026-08-24_to_2026-08-30.csv"

ACTUAL_ACCOUNT="$(aws sts get-caller-identity \
  --query Account --output text)"

if [[ "$ACTUAL_ACCOUNT" != "$EXPECTED_ACCOUNT" ]]; then
  echo "STOP: Signed into the wrong AWS account."
  exit 1
fi

SOURCE="s3://${BUCKET}/landing/pos/${FILE}"
TARGET="s3://${BUCKET}/raw/pos/${FILE}"

echo "Copying original POS data from Landing to Raw."
aws s3 cp "$SOURCE" "$TARGET" --region "$REGION"

echo "Checking the Raw destination:"
aws s3 ls "$TARGET" --region "$REGION"
