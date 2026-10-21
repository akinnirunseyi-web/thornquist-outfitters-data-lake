import json
import os
from urllib.parse import unquote_plus
from pathlib import PurePosixPath

import boto3

s3 = boto3.client("s3")

DESTINATION_PREFIX = os.environ.get(
    "DESTINATION_PREFIX", "raw/ecommerce/"
)
SOURCE_PREFIX = os.environ.get(
    "SOURCE_PREFIX", "landing/ecommerce/"
)


def lambda_handler(event, context):
    results = []

    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            continue

        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        # Process only JSON objects in the source prefix.
        if not key.startswith(SOURCE_PREFIX):
            continue
        if not key.lower().endswith(".json"):
            continue

        response = s3.get_object(Bucket=bucket, Key=key)
        payload = json.loads(
            response["Body"].read().decode("utf-8")
        )

        # The actual source contains a JSON array at the root.
        if isinstance(payload, dict):
            orders = [payload]
        elif isinstance(payload, list):
            orders = payload
        else:
            raise ValueError(
                f"Unsupported JSON root type: s3://{bucket}/{key}"
            )

        if not all(isinstance(order, dict) for order in orders):
            raise ValueError(
                f"Expected JSON order objects in {key}"
            )

        # Write one complete order per line (NDJSON).
        output = "".join(
            json.dumps(
                order,
                ensure_ascii=False,
                separators=(",", ":")
            ) + "\n"
            for order in orders
        )

        basename = PurePosixPath(key).name
        output_key = f"{DESTINATION_PREFIX}{basename}.ndjson"

        s3.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=output.encode("utf-8"),
            ContentType="application/x-ndjson",
        )

        results.append({
            "source": f"s3://{bucket}/{key}",
            "destination": f"s3://{bucket}/{output_key}",
            "orders_written": len(orders),
        })

    return {
        "processed_files": len(results),
        "results": results,
    }
