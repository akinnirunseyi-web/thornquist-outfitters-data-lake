#!/usr/bin/env python3
"""Transform validated POS and ecommerce records into a common sales model."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from transform.data_quality import norm_id


CENT = Decimal("0.01")


def clean_text(value: Any) -> str | None:
    """Trim text and normalize non-breaking spaces."""
    if value is None:
        return None
    result = str(value).replace("\u00a0", " ").strip()
    return result or None


def parse_pos_date(value: Any) -> str:
    """Normalize supported POS dates to YYYY-MM-DD."""
    value = str(value).strip()

    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue

    raise ValueError(f"Unsupported POS sale date: {value!r}")


def normalize_ecommerce_timestamp(value: Any) -> str:
    """Normalize timezone-aware ISO timestamps to UTC; preserve naive timestamps."""
    value = str(value).strip()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is not None:
        return (
            parsed.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    return parsed.isoformat(timespec="seconds")


def decimal_value(value: Any, field_name: str) -> Decimal:
    """Convert a validated numeric field to Decimal."""
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Invalid numeric value for {field_name}: {value!r}") from None

    if not result.is_finite():
        raise ValueError(f"Non-finite numeric value for {field_name}: {value!r}")

    return result


def money(value: Decimal) -> str:
    """Return a fixed two-decimal monetary value for exact JSON serialization."""
    return format(value.quantize(CENT, rounding=ROUND_HALF_UP), ".2f")


def quantity_value(value: Decimal) -> int | float:
    """Represent whole quantities as integers and fractional quantities as floats."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def customer_attributes(
    customer_id: str,
    customer_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return customer attributes when a matching customer record exists."""
    customer = customer_lookup.get(customer_id, {})

    return {
        "customer_first_name": clean_text(customer.get("first_name")),
        "customer_last_name": clean_text(customer.get("last_name")),
        "customer_loyalty_tier": clean_text(customer.get("loyalty_tier")),
        "customer_region": clean_text(customer.get("region")),
    }


def transform_pos_record(
    record: dict[str, Any],
    source_file: str,
    record_number: int,
    customer_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Transform one validated POS transaction into one sales-model row."""
    transaction_id = norm_id(record.get("transaction_id"))
    customer_id = norm_id(record.get("cust_num"))

    quantity = decimal_value(record["quantity"], "quantity")
    unit_price = decimal_value(record["unit_price"], "unit_price")

    result = {
        "sale_line_id": f"pos:{transaction_id}",
        "source_system": "pos",
        "transaction_id": transaction_id,
        "order_id": None,
        "order_line_number": 1,
        "customer_id": customer_id or None,
        "sale_timestamp": parse_pos_date(record["sale_date"]),
        "sku": None,
        "product_name": clean_text(record.get("product_name")),
        "category": clean_text(record.get("category")),
        "quantity": quantity_value(quantity),
        "unit_price": money(unit_price),
        "line_amount": money(quantity * unit_price),
        "sales_region": clean_text(record.get("region")),
        "shipping_region": None,
        "store_id": norm_id(record.get("store_id")) or None,
        "store_name": clean_text(record.get("store_name")),
        "payment_method": clean_text(record.get("payment_method")),
        "channel": "in_store",
        "source_file": source_file,
        "source_record_number": record_number,
    }

    result.update(customer_attributes(customer_id, customer_lookup))
    return result


def transform_ecommerce_order(
    order: dict[str, Any],
    source_file: str,
    record_number: int,
    customer_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flatten one validated ecommerce order into one row per item."""
    order_id = norm_id(order.get("order_id"))
    customer_id = norm_id(order.get("cust_ref"))
    timestamp = normalize_ecommerce_timestamp(order["order_timestamp"])

    shared_fields = {
        "source_system": "ecommerce",
        "transaction_id": None,
        "order_id": order_id,
        "customer_id": customer_id or None,
        "sale_timestamp": timestamp,
        "sales_region": None,
        "shipping_region": clean_text(order.get("shipping_region")),
        "store_id": None,
        "store_name": None,
        "payment_method": None,
        "channel": clean_text(order.get("channel")),
        "source_file": source_file,
        "source_record_number": record_number,
    }

    rows: list[dict[str, Any]] = []

    for line_number, item in enumerate(order["items"], start=1):
        quantity = decimal_value(item["qty"], "qty")
        unit_price = decimal_value(item["unit_price"], "unit_price")

        row = {
            **shared_fields,
            "sale_line_id": f"ecommerce:{order_id}:{line_number}",
            "order_line_number": line_number,
            "sku": clean_text(item.get("sku")),
            "product_name": clean_text(item.get("product_name")),
            # Ecommerce source records do not currently provide a category.
            "category": None,
            "quantity": quantity_value(quantity),
            "unit_price": money(unit_price),
            "line_amount": money(quantity * unit_price),
        }

        row.update(customer_attributes(customer_id, customer_lookup))
        rows.append(row)

    return rows
