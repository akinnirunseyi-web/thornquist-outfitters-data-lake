#!/usr/bin/env python3
"""Local data-quality validation for Thornquist Outfitters source extracts.

Uses only the Python standard library. Source files are read-only; results are
written to output/trusted and output/quarantine as JSON Lines files.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PLACEHOLDERS = {"", "null", "none", "n/a", "na", "unknown", "undefined"}
POS_WALK_IN_CUSTOMER = "0000000"


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() in PLACEHOLDERS


def norm_id(value: Any) -> str:
    """Normalize identifiers for comparisons without changing source records."""
    if value is None:
        return ""
    # Avoid turning integer JSON IDs into strings ending in .0.
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def read_csv_records(path: Path) -> list[dict[str, Any]]:
    """Read comma- or tab-delimited CSV, preserving field names and values."""
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        return [dict(row) for row in csv.DictReader(f, dialect=dialect)]


def read_json_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a top-level JSON array of order objects")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path}: every JSON array item must be an object")
    return data


def parse_pos_date(value: Any) -> bool:
    if is_missing(value):
        return False
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass
    return False


def parse_iso_timestamp(value: Any) -> bool:
    if is_missing(value):
        return False
    value = str(value).strip()
    try:
        # Python accepts ISO timestamps with UTC Z after replacing it by +00:00.
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def numeric(value: Any) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def classify_records(
    records: list[dict[str, Any]],
    source_file: str,
    customers: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter]:
    """Validate POS or e-commerce records; first occurrence wins for duplicate IDs."""
    trusted: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    counts: Counter = Counter()
    seen_ids: set[str] = set()
    is_pos = source_file.lower().endswith(".csv")
    is_ecommerce = source_file.lower().endswith(".json")

    for index, record in enumerate(records, start=1):
        reasons: list[str] = []

        if is_pos:
            required = ("transaction_id", "store_id", "sale_date", "product_name",
                        "quantity", "unit_price", "cust_num")
            for field in required:
                if is_missing(record.get(field)):
                    reasons.append(f"DQ01_MISSING_REQUIRED:{field}")

            tx_id = norm_id(record.get("transaction_id"))
            if tx_id and tx_id in seen_ids:
                reasons.append("DQ02_DUPLICATE_TRANSACTION_ID")
            elif tx_id:
                seen_ids.add(tx_id)

            if not is_missing(record.get("sale_date")) and not parse_pos_date(record.get("sale_date")):
                reasons.append("DQ03_INVALID_SALE_DATE")

            customer_id = norm_id(record.get("cust_num"))
            if customer_id and customer_id != POS_WALK_IN_CUSTOMER and customer_id not in customers:
                reasons.append("DQ04_UNKNOWN_CUSTOMER_ID")

            qty = numeric(record.get("quantity"))
            if qty is None or qty <= 0:
                reasons.append("DQ05_INVALID_QUANTITY")
            price = numeric(record.get("unit_price"))
            if price is None or price < 0:
                reasons.append("DQ05_INVALID_UNIT_PRICE")

        elif is_ecommerce:
            required = ("order_id", "order_timestamp", "cust_ref", "items")
            for field in required:
                if is_missing(record.get(field)):
                    reasons.append(f"DQ01_MISSING_REQUIRED:{field}")

            order_id = norm_id(record.get("order_id"))
            if order_id and order_id in seen_ids:
                reasons.append("DQ02_DUPLICATE_ORDER_ID")
            elif order_id:
                seen_ids.add(order_id)

            if not is_missing(record.get("order_timestamp")) and not parse_iso_timestamp(record.get("order_timestamp")):
                reasons.append("DQ03_INVALID_ORDER_TIMESTAMP")

            customer_id = norm_id(record.get("cust_ref"))
            if customer_id and customer_id not in customers:
                reasons.append("DQ04_UNKNOWN_CUSTOMER_ID")

            items = record.get("items")
            if not isinstance(items, list) or len(items) == 0:
                reasons.append("DQ06_ITEMS_MUST_BE_NONEMPTY_ARRAY")
            else:
                for item_index, item in enumerate(items, start=1):
                    if not isinstance(item, dict):
                        reasons.append(f"DQ06_ITEM_{item_index}_NOT_OBJECT")
                        continue
                    for field in ("sku", "product_name", "qty", "unit_price"):
                        if is_missing(item.get(field)):
                            reasons.append(f"DQ06_ITEM_{item_index}_MISSING:{field}")
                    qty = numeric(item.get("qty"))
                    if qty is None or qty <= 0:
                        reasons.append(f"DQ05_ITEM_{item_index}_INVALID_QUANTITY")
                    price = numeric(item.get("unit_price"))
                    if price is None or price < 0:
                        reasons.append(f"DQ05_ITEM_{item_index}_INVALID_UNIT_PRICE")

        else:
            reasons.append("DQ00_UNSUPPORTED_SOURCE_TYPE")

        counts["records_seen"] += 1
        if reasons:
            counts["records_quarantined"] += 1
            for reason in reasons:
                counts[f"reason:{reason}"] += 1
            quarantine.append({
                "source_file": source_file,
                "record_number": index,
                "rejection_reasons": reasons,
                "record": record,
            })
        else:
            counts["records_trusted"] += 1
            trusted.append({
                "source_file": source_file,
                "record_number": index,
                "record": record,
            })

    return trusted, quarantine, counts


def load_customer_reference(path: Path) -> tuple[set[str], list[dict[str, Any]], Counter]:
    """Load customer IDs and quarantine incomplete/duplicate customer records."""
    records = read_csv_records(path)
    valid_ids: set[str] = set()
    seen_ids: set[str] = set()
    trusted: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    counts: Counter = Counter()

    for index, record in enumerate(records, start=1):
        reasons = []
        customer_id = norm_id(record.get("cust_num"))
        for field in ("cust_num", "first_name", "last_name", "email"):
            if is_missing(record.get(field)):
                reasons.append(f"DQ01_MISSING_REQUIRED:{field}")
        if customer_id and customer_id in seen_ids:
            reasons.append("DQ02_DUPLICATE_CUSTOMER_ID")
        elif customer_id:
            seen_ids.add(customer_id)

        if reasons:
            quarantine.append({
                "source_file": path.name,
                "record_number": index,
                "rejection_reasons": reasons,
                "record": record,
            })
            counts["records_quarantined"] += 1
            for reason in reasons:
                counts[f"reason:{reason}"] += 1
        else:
            valid_ids.add(customer_id)
            trusted.append({
                "source_file": path.name,
                "record_number": index,
                "record": record,
            })
            counts["records_trusted"] += 1
        counts["records_seen"] += 1

    return valid_ids, trusted, quarantine, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Directory containing the three original source files")
    parser.add_argument("--output-dir", default="output", help="Output directory; defaults to ./output")
    parser.add_argument("--pos-file", default="pos_sales_2026-08-24_to_2026-08-30.csv")
    parser.add_argument("--ecommerce-file", default="ecommerce_orders.json")
    parser.add_argument("--customers-file", default="customer_extract.csv")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    pos_path = data_dir / args.pos_file
    ecommerce_path = data_dir / args.ecommerce_file
    customers_path = data_dir / args.customers_file

    for path in (pos_path, ecommerce_path, customers_path):
        if not path.is_file():
            parser.error(f"Required source file not found: {path}")

    customer_ids, customer_trusted, customer_quarantine, customer_counts = load_customer_reference(customers_path)
    pos_records = read_csv_records(pos_path)
    ecommerce_records = read_json_records(ecommerce_path)

    pos_trusted, pos_quarantine, pos_counts = classify_records(pos_records, pos_path.name, customer_ids)
    ecommerce_trusted, ecommerce_quarantine, ecommerce_counts = classify_records(
        ecommerce_records, ecommerce_path.name, customer_ids
    )

    trusted_dir = output_dir / "trusted"
    quarantine_dir = output_dir / "quarantine"
    write_jsonl(trusted_dir / "customers.jsonl", customer_trusted)
    write_jsonl(trusted_dir / "pos_sales.jsonl", pos_trusted)
    write_jsonl(trusted_dir / "ecommerce_orders.jsonl", ecommerce_trusted)

    write_jsonl(quarantine_dir / "customers.jsonl", customer_quarantine)
    write_jsonl(quarantine_dir / "pos_sales.jsonl", pos_quarantine)
    write_jsonl(quarantine_dir / "ecommerce_orders.jsonl", ecommerce_quarantine)

    summary = {
        "note": "Local validation run. Source files are read-only; JSONL output preserves the original record plus metadata.",
        "customer_extract": dict(customer_counts),
        "pos_sales": dict(pos_counts),
        "ecommerce_orders": dict(ecommerce_counts),
        "customer_reference_ids_loaded": len(customer_ids),
        "output_files": [
            "trusted/customers.jsonl", "trusted/pos_sales.jsonl", "trusted/ecommerce_orders.jsonl",
            "quarantine/customers.jsonl", "quarantine/pos_sales.jsonl", "quarantine/ecommerce_orders.jsonl",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nResults written to: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
