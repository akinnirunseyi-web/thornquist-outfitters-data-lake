#!/usr/bin/env python3
"""Validate the source extracts and build a unified local sales model."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from transform.data_quality import (
    classify_records,
    load_customer_reference,
    read_csv_records,
    read_json_records,
    write_jsonl,
)
from transform.sales_transform import (
    decimal_value,
    money,
    transform_ecommerce_order,
    transform_pos_record,
)


def reconcile_order_total(order: dict[str, Any]) -> bool:
    """Check whether an order total equals the sum of its item amounts."""
    try:
        calculated = sum(
            (
                decimal_value(item["qty"], "qty")
                * decimal_value(item["unit_price"], "unit_price")
                for item in order["items"]
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"))

        reported = decimal_value(order["order_total"], "order_total").quantize(
            Decimal("0.01")
        )
        return calculated == reported
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--pos-file",
        default="pos_sales_2026-08-24_to_2026-08-30.csv",
    )
    parser.add_argument(
        "--ecommerce-file",
        default="ecommerce_orders.json",
    )
    parser.add_argument(
        "--customers-file",
        default="customer_extract.csv",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    customer_path = data_dir / args.customers_file
    pos_path = data_dir / args.pos_file
    ecommerce_path = data_dir / args.ecommerce_file

    for path in (customer_path, pos_path, ecommerce_path):
        if not path.is_file():
            parser.error(f"Required source file not found: {path}")

    customer_ids, customers_trusted, customers_quarantine, customer_counts = (
        load_customer_reference(customer_path)
    )
    pos_records = read_csv_records(pos_path)
    ecommerce_records = read_json_records(ecommerce_path)

    pos_trusted, pos_quarantine, pos_counts = classify_records(
        pos_records, pos_path.name, customer_ids
    )
    ecommerce_trusted, ecommerce_quarantine, ecommerce_counts = classify_records(
        ecommerce_records, ecommerce_path.name, customer_ids
    )

    customer_lookup = {
        str(entry["record"]["cust_num"]).strip(): entry["record"]
        for entry in customers_trusted
    }

    # Reconcile each validated order before flattening it into item rows.
    reconciled_orders = []
    total_mismatch_quarantine = []

    for entry in ecommerce_trusted:
        order = entry["record"]

        if reconcile_order_total(order):
            reconciled_orders.append(entry)
        else:
            total_mismatch_quarantine.append(
                {
                    **entry,
                    "rejection_reasons": ["DQ07_ORDER_TOTAL_MISMATCH"],
                }
            )

    # Build the unified, one-row-per-sold-item model.
    sales_rows = []

    for entry in pos_trusted:
        sales_rows.append(
            transform_pos_record(
                entry["record"],
                entry["source_file"],
                entry["record_number"],
                customer_lookup,
            )
        )

    for entry in reconciled_orders:
        sales_rows.extend(
            transform_ecommerce_order(
                entry["record"],
                entry["source_file"],
                entry["record_number"],
                customer_lookup,
            )
        )

    # Preserve validation outputs and add reconciliation results.
    trusted_dir = output_dir / "trusted"
    quarantine_dir = output_dir / "quarantine"

    write_jsonl(trusted_dir / "customers.jsonl", customers_trusted)
    write_jsonl(trusted_dir / "pos_sales.jsonl", pos_trusted)
    write_jsonl(trusted_dir / "ecommerce_orders.jsonl", reconciled_orders)
    write_jsonl(trusted_dir / "sales_model.jsonl", sales_rows)

    write_jsonl(quarantine_dir / "customers.jsonl", customers_quarantine)
    write_jsonl(quarantine_dir / "pos_sales.jsonl", pos_quarantine)
    write_jsonl(
        quarantine_dir / "ecommerce_orders.jsonl",
        ecommerce_quarantine + total_mismatch_quarantine,
    )

    summary = {
        "execution_mode": "local",
        "source_files": {
            "customers": customer_path.name,
            "pos_sales": pos_path.name,
            "ecommerce_orders": ecommerce_path.name,
        },
        "validation": {
            "customers": dict(customer_counts),
            "pos_sales": dict(pos_counts),
            "ecommerce_orders": dict(ecommerce_counts),
        },
        "reconciliation": {
            "validated_orders_checked": len(ecommerce_trusted),
            "orders_reconciled": len(reconciled_orders),
            "orders_with_total_mismatch": len(total_mismatch_quarantine),
        },
        "sales_model": {
            "rows_written": len(sales_rows),
            "pos_rows": len(pos_trusted),
            "ecommerce_item_rows": sum(
                len(entry["record"]["items"]) for entry in reconciled_orders
            ),
            "distinct_source_systems": sorted(
                {row["source_system"] for row in sales_rows}
            ),
        },
        "output_files": [
            "trusted/customers.jsonl",
            "trusted/pos_sales.jsonl",
            "trusted/ecommerce_orders.jsonl",
            "trusted/sales_model.jsonl",
            "quarantine/customers.jsonl",
            "quarantine/pos_sales.jsonl",
            "quarantine/ecommerce_orders.jsonl",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sales_model_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nSales model written to: {(trusted_dir / 'sales_model.jsonl').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
