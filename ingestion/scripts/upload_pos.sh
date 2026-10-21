#!/usr/bin/env bash
set -euo pipefail

BUCKET_NAME="${1:-thornquist-data-lake-659260838742}"
SOURCE_FILE="${2:-data/pos_sales_2026-08-24_to_2026-08-30.csv}"
REGION="us-east-1"
DESTINATION_KEY="landing/pos/$(basename "$SOURCE_FILE")"

if [[ ! -f "$SOURCE_FILE" ]]; then
    echo "ERREUR : fichier introuvable : $SOURCE_FILE"
    exit 1
fi

echo "Fichier source : $SOURCE_FILE"
echo "Destination S3 : s3://${BUCKET_NAME}/${DESTINATION_KEY}"

aws s3 cp \
    "$SOURCE_FILE" \
    "s3://${BUCKET_NAME}/${DESTINATION_KEY}" \
    --region "$REGION"

echo "Vérification de l'objet S3 :"

aws s3api head-object \
    --bucket "$BUCKET_NAME" \
    --key "$DESTINATION_KEY" \
    --region "$REGION" \
    --query '{Size:ContentLength,LastModified:LastModified,ETag:ETag}' \
    --output table

echo "Ingestion POS terminée."
