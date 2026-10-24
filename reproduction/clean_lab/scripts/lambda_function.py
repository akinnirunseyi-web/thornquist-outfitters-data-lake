import hashlib
import json
import os
from urllib.parse import unquote_plus

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]
PREFIX = "landing/ecommerce/"


def lambda_handler(event, context):
    # S3 sends this when a notification is configured.
    if event.get("Event") == "s3:TestEvent":
        return {"status": "notification_test_received"}

    records = event.get("Records")
    if not records:
        raise ValueError("Expected an S3 event containing Records.")

    results = []

    for record in records:
        if (
            record.get("eventSource") != "aws:s3"
            or not record.get("eventName", "").startswith("ObjectCreated:")
        ):
            continue

        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if (
            bucket != BUCKET
            or not key.startswith(PREFIX)
            or not key.endswith(".json")
        ):
            continue

        response = s3.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()

        orders = json.loads(body.decode("utf-8-sig"))
        if not isinstance(orders, list) or not all(
            isinstance(order, dict) for order in orders
        ):
            raise ValueError("Expected a JSON array of order objects.")

        target = "raw/ecommerce/" + key[len(PREFIX):]
        checksum = hashlib.sha256(body).hexdigest()

        # Keep the original bytes and a stable destination filename.
        s3.put_object(
            Bucket=BUCKET,
            Key=target,
            Body=body,
            ContentType="application/json",
            ServerSideEncryption="AES256",
            Metadata={"source-sha256": checksum},
        )

        result = {
            "status": "copied",
            "bucket": BUCKET,
            "source": key,
            "target": target,
            "order_count": len(orders),
            "bytes": len(body),
            "sha256": checksum,
        }
        print(json.dumps(result))
        results.append(result)

    return {"processed_files": len(results), "results": results}
