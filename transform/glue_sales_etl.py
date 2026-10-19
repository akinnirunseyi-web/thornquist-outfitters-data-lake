
#!/usr/bin/env python3
"""AWS Glue ETL for Thornquist Outfitters Data Lake."""

from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse


PLACEHOLDERS = {"", "null", "none", "n/a", "na", "unknown", "undefined"}
WALK_IN_CUSTOMER = "0000000"


def missing(value):
    return value is None or str(value).strip().lower() in PLACEHOLDERS


def norm_id(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def numeric(value):
    if missing(value):
        return None
    try:
        number = Decimal(str(value).strip())
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_pos_date(value):
    if missing(value):
        return False
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            datetime.strptime(str(value).strip(), fmt)
            return True
        except ValueError:
            pass
    return False


def parse_timestamp(value):
    if missing(value):
        return False
    try:
        datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def read_s3_text(s3, uri):
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError(f"Expected an S3 object URI, not a bucket/prefix: {uri}")
    response = s3.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
    return response["Body"].read().decode("utf-8-sig")


def read_csv_text(content):
    sample = content[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    return [dict(row) for row in csv.DictReader(io.StringIO(content), dialect=dialect)]


def read_json_text(content):
    data = json.loads(content)
    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
        raise ValueError("E-commerce source must be a JSON array of objects.")
    return data


def validate_customers(records, source_file):
    trusted, rejected, counts = [], [], Counter()
    seen = set()

    for number, record in enumerate(records, 1):
        reasons = []
        customer_id = norm_id(record.get("cust_num"))

        for field in ("cust_num", "first_name", "last_name", "email"):
            if missing(record.get(field)):
                reasons.append(f"DQ01_MISSING_REQUIRED:{field}")

        if customer_id and customer_id in seen:
            reasons.append("DQ02_DUPLICATE_CUSTOMER_ID")
        elif customer_id:
            seen.add(customer_id)

        entry = {
            "source_file": source_file,
            "record_number": number,
            "record": record,
        }
        counts["records_seen"] += 1

        if reasons:
            rejected.append({**entry, "rejection_reasons": reasons})
            counts["records_quarantined"] += 1
            for reason in reasons:
                counts[f"reason:{reason}"] += 1
        else:
            trusted.append(entry)
            counts["records_trusted"] += 1

    return trusted, rejected, counts


def validate_sales(records, source_file, customer_ids, source_type):
    trusted, rejected, counts = [], [], Counter()
    seen = set()

    for number, record in enumerate(records, 1):
        reasons = []

        if source_type == "pos":
            required = (
                "transaction_id", "store_id", "sale_date",
                "product_name", "quantity", "unit_price", "cust_num",
            )
            record_id = norm_id(record.get("transaction_id"))
            date_value = record.get("sale_date")
            customer_id = norm_id(record.get("cust_num"))
        else:
            required = ("order_id", "order_timestamp", "cust_ref", "items")
            record_id = norm_id(record.get("order_id"))
            date_value = record.get("order_timestamp")
            customer_id = norm_id(record.get("cust_ref"))

        for field in required:
            if missing(record.get(field)):
                reasons.append(f"DQ01_MISSING_REQUIRED:{field}")

        duplicate_reason = (
            "DQ02_DUPLICATE_TRANSACTION_ID"
            if source_type == "pos"
            else "DQ02_DUPLICATE_ORDER_ID"
        )
        if record_id and record_id in seen:
            reasons.append(duplicate_reason)
        elif record_id:
            seen.add(record_id)

        if not missing(date_value):
            valid_date = (
                parse_pos_date(date_value)
                if source_type == "pos"
                else parse_timestamp(date_value)
            )
            if not valid_date:
                reasons.append(
                    "DQ03_INVALID_SALE_DATE"
                    if source_type == "pos"
                    else "DQ03_INVALID_ORDER_TIMESTAMP"
                )

        if customer_id:
            if source_type == "pos" and customer_id == WALK_IN_CUSTOMER:
                pass
            elif customer_id not in customer_ids:
                reasons.append("DQ04_UNKNOWN_CUSTOMER_ID")

        if source_type == "pos":
            quantity = numeric(record.get("quantity"))
            price = numeric(record.get("unit_price"))
            if quantity is None or quantity <= 0:
                reasons.append("DQ05_INVALID_QUANTITY")
            if price is None or price < 0:
                reasons.append("DQ05_INVALID_UNIT_PRICE")
        else:
            items = record.get("items")
            if not isinstance(items, list) or not items:
                reasons.append("DQ06_ITEMS_MUST_BE_NONEMPTY_ARRAY")
            else:
                for item_number, item in enumerate(items, 1):
                    if not isinstance(item, dict):
                        reasons.append(f"DQ06_ITEM_{item_number}_NOT_OBJECT")
                        continue
                    for field in ("sku", "product_name", "qty", "unit_price"):
                        if missing(item.get(field)):
                            reasons.append(
                                f"DQ06_ITEM_{item_number}_MISSING:{field}"
                            )
                    quantity = numeric(item.get("qty"))
                    price = numeric(item.get("unit_price"))
                    if quantity is None or quantity <= 0:
                        reasons.append(
                            f"DQ05_ITEM_{item_number}_INVALID_QUANTITY"
                        )
                    if price is None or price < 0:
                        reasons.append(
                            f"DQ05_ITEM_{item_number}_INVALID_UNIT_PRICE"
                        )

        entry = {
            "source_file": source_file,
            "record_number": number,
            "record": record,
        }
        counts["records_seen"] += 1

        if reasons:
            rejected.append({**entry, "rejection_reasons": reasons})
            counts["records_quarantined"] += 1
            for reason in reasons:
                counts[f"reason:{reason}"] += 1
        else:
            trusted.append(entry)
            counts["records_trusted"] += 1

    return trusted, rejected, counts


def reconcile_order(order):
    try:
        calculated = sum(
            (
                numeric(item["qty"]) * numeric(item["unit_price"])
                for item in order["items"]
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
        reported = numeric(order["order_total"])
        return reported is not None and calculated == reported.quantize(
            Decimal("0.01")
        )
    except (KeyError, TypeError, InvalidOperation, AttributeError):
        return False


def clean(value):
    if value is None:
        return None
    value = str(value).replace("\u00a0", " ").strip()
    return value or None


def money(value):
    return format(
        Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        ),
        ".2f",
    )


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return (
            parsed.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    return parsed.isoformat(timespec="seconds")


def build_sales_model(pos_entries, orders, customer_lookup):
    rows = []

    for entry in pos_entries:
        record = entry["record"]
        transaction_id = norm_id(record.get("transaction_id"))
        customer_id = norm_id(record.get("cust_num"))
        quantity = numeric(record["quantity"])
        price = numeric(record["unit_price"])
        customer = customer_lookup.get(customer_id, {})

        sale_date = str(record["sale_date"]).strip()
        if "/" in sale_date:
            sale_date = datetime.strptime(sale_date, "%d/%m/%Y").date().isoformat()

        rows.append({
            "sale_line_id": f"pos:{transaction_id}",
            "source_system": "pos",
            "transaction_id": transaction_id,
            "order_id": None,
            "order_line_number": 1,
            "customer_id": customer_id or None,
            "sale_timestamp": sale_date,
            "sku": None,
            "product_name": clean(record.get("product_name")),
            "category": clean(record.get("category")),
            "quantity": float(quantity) if quantity % 1 else int(quantity),
            "unit_price": money(price),
            "line_amount": money(quantity * price),
            "sales_region": clean(record.get("region")),
            "shipping_region": None,
            "store_id": norm_id(record.get("store_id")) or None,
            "store_name": clean(record.get("store_name")),
            "payment_method": clean(record.get("payment_method")),
            "channel": "in_store",
            "source_file": entry["source_file"],
            "source_record_number": entry["record_number"],
            "customer_first_name": clean(customer.get("first_name")),
            "customer_last_name": clean(customer.get("last_name")),
            "customer_loyalty_tier": clean(customer.get("loyalty_tier")),
            "customer_region": clean(customer.get("region")),
        })

    reconciled, total_rejections = [], []
    for entry in orders:
        if reconcile_order(entry["record"]):
            reconciled.append(entry)
        else:
            total_rejections.append({
                **entry,
                "rejection_reasons": ["DQ07_ORDER_TOTAL_MISMATCH"],
            })

    for entry in reconciled:
        order = entry["record"]
        order_id = norm_id(order.get("order_id"))
        customer_id = norm_id(order.get("cust_ref"))
        customer = customer_lookup.get(customer_id, {})

        for line_number, item in enumerate(order["items"], 1):
            quantity = numeric(item["qty"])
            price = numeric(item["unit_price"])
            rows.append({
                "sale_line_id": f"ecommerce:{order_id}:{line_number}",
                "source_system": "ecommerce",
                "transaction_id": None,
                "order_id": order_id,
                "order_line_number": line_number,
                "customer_id": customer_id or None,
                "sale_timestamp": timestamp(order["order_timestamp"]),
                "sku": clean(item.get("sku")),
                "product_name": clean(item.get("product_name")),
                "category": None,
                "quantity": float(quantity) if quantity % 1 else int(quantity),
                "unit_price": money(price),
                "line_amount": money(quantity * price),
                "sales_region": None,
                "shipping_region": clean(order.get("shipping_region")),
                "store_id": None,
                "store_name": None,
                "payment_method": None,
                "channel": clean(order.get("channel")),
                "source_file": entry["source_file"],
                "source_record_number": entry["record_number"],
                "customer_first_name": clean(customer.get("first_name")),
                "customer_last_name": clean(customer.get("last_name")),
                "customer_loyalty_tier": clean(customer.get("loyalty_tier")),
                "customer_region": clean(customer.get("region")),
            })

    return rows, reconciled, total_rejections


def write_jsonl(s3, uri, records):
    parsed = urlparse(uri)
    key = parsed.path.lstrip("/")
    if not key.endswith("/"):
        key += "/"
    key += "part-00000.jsonl"
    body = "".join(
        json.dumps(record, ensure_ascii=False, default=str) + "\n"
        for record in records
    )
    s3.put_object(
        Bucket=parsed.netloc,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/x-ndjson",
    )


def main():
    from awsglue.utils import getResolvedOptions
    from pyspark.sql import SparkSession
    from pyspark.sql.types import (
        StructType, StructField, StringType, IntegerType, DoubleType
    )
    import boto3

    args = getResolvedOptions(sys.argv, [
        "JOB_NAME",
        "CUSTOMERS_S3_PATH",
        "POS_S3_PATH",
        "ECOMMERCE_S3_PATH",
        "TRUSTED_S3_PATH",
        "QUARANTINE_S3_PATH",
        "REPORTS_S3_PATH",
    ])

    spark = SparkSession.builder.appName(args["JOB_NAME"]).getOrCreate()
    s3 = boto3.client("s3")

    customer_path = args["CUSTOMERS_S3_PATH"]
    pos_path = args["POS_S3_PATH"]
    ecommerce_path = args["ECOMMERCE_S3_PATH"]

    customers_source = read_csv_text(read_s3_text(s3, customer_path))
    pos_source = read_csv_text(read_s3_text(s3, pos_path))
    ecommerce_source = read_json_text(read_s3_text(s3, ecommerce_path))

    customer_file = urlparse(customer_path).path.rsplit("/", 1)[-1]
    pos_file = urlparse(pos_path).path.rsplit("/", 1)[-1]
    ecommerce_file = urlparse(ecommerce_path).path.rsplit("/", 1)[-1]

    customers, bad_customers, customer_counts = validate_customers(
        customers_source, customer_file
    )
    customer_ids = {norm_id(x["record"].get("cust_num")) for x in customers}
    customer_lookup = {
        norm_id(x["record"].get("cust_num")): x["record"] for x in customers
    }

    pos, bad_pos, pos_counts = validate_sales(
        pos_source, pos_file, customer_ids, "pos"
    )
    orders, bad_orders, order_counts = validate_sales(
        ecommerce_source, ecommerce_file, customer_ids, "ecommerce"
    )

    sales_rows, reconciled_orders, total_rejections = build_sales_model(
        pos, orders, customer_lookup
    )
    bad_orders.extend(total_rejections)

    trusted_base = args["TRUSTED_S3_PATH"].rstrip("/")
    quarantine_base = args["QUARANTINE_S3_PATH"].rstrip("/")
    reports_base = args["REPORTS_S3_PATH"].rstrip("/")

    outputs = {
        "customers": customers,
        "pos_sales": pos,
        "ecommerce_orders": reconciled_orders,
        "sales_model": sales_rows,
    }
    rejects = {
        "customers": bad_customers,
        "pos_sales": bad_pos,
        "ecommerce_orders": bad_orders,
    }

    sales_schema = StructType([
        StructField("sale_line_id", StringType(), True),
        StructField("source_system", StringType(), True),
        StructField("transaction_id", StringType(), True),
        StructField("order_id", StringType(), True),
        StructField("order_line_number", IntegerType(), True),
        StructField("customer_id", StringType(), True),
        StructField("sale_timestamp", StringType(), True),
        StructField("sku", StringType(), True),
        StructField("product_name", StringType(), True),
        StructField("category", StringType(), True),
        StructField("quantity", DoubleType(), True),
        StructField("unit_price", StringType(), True),
        StructField("line_amount", StringType(), True),
        StructField("sales_region", StringType(), True),
        StructField("shipping_region", StringType(), True),
        StructField("store_id", StringType(), True),
        StructField("store_name", StringType(), True),
        StructField("payment_method", StringType(), True),
        StructField("channel", StringType(), True),
        StructField("source_file", StringType(), True),
        StructField("source_record_number", IntegerType(), True),
        StructField("customer_first_name", StringType(), True),
        StructField("customer_last_name", StringType(), True),
        StructField("customer_loyalty_tier", StringType(), True),
        StructField("customer_region", StringType(), True),
    ])


    # Trusted records are stored as Parquet, with original records retained
    # as JSON strings alongside source metadata for traceability.
    for name, records in outputs.items():
        if name == "sales_model":
            dataframe = spark.createDataFrame(records, schema=sales_schema)
        else:
            flattened = [{
                "source_file": entry["source_file"],
                "record_number": entry["record_number"],
                "record_json": json.dumps(entry["record"], ensure_ascii=False),
            } for entry in records]
            if not flattened:
                print(f"No trusted records for {name}; skipping Parquet output.")
                continue
            dataframe = spark.createDataFrame(flattened)

        dataframe.write.mode("overwrite").parquet(f"{trusted_base}/{name}/")

    for name, records in rejects.items():
        write_jsonl(s3, f"{quarantine_base}/{name}/", records)

    summary = {
        "execution_mode": "aws_glue",
        "validation": {
            "customers": dict(customer_counts),
            "pos_sales": dict(pos_counts),
            "ecommerce_orders": dict(order_counts),
        },
        "reconciliation": {
            "validated_orders_checked": len(orders),
            "orders_reconciled": len(reconciled_orders),
            "orders_with_total_mismatch": len(total_rejections),
        },
        "sales_model": {
            "rows_written": len(sales_rows),
            "pos_rows": len(pos),
            "ecommerce_item_rows": sum(
                len(entry["record"]["items"]) for entry in reconciled_orders
            ),
        },
    }

    report = urlparse(reports_base)
    report_key = report.path.lstrip("/")
    if not report_key.endswith("/"):
        report_key += "/"
    report_key += "sales_model_summary.json"
    s3.put_object(
        Bucket=report.netloc,
        Key=report_key,
        Body=(json.dumps(summary, indent=2, ensure_ascii=False) + "\n").encode(),
        ContentType="application/json",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
