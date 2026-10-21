import json
from decimal import Decimal

import pytest

from transform import glue_sales_etl as glue


def customer(customer_id="C001"):
    return {
        "cust_num": customer_id,
        "first_name": "Alex",
        "last_name": "Martin",
        "email": "alex@example.com",
        "loyalty_tier": "Gold",
        "region": "Ontario",
    }


def pos_record(**overrides):
    record = {
        "transaction_id": "T001",
        "store_id": "S01",
        "sale_date": "2026-08-24",
        "product_name": "Jacket",
        "quantity": "2",
        "unit_price": "25.00",
        "cust_num": "C001",
        "category": "Clothing",
        "region": "Ontario",
        "store_name": "Ottawa Store",
        "payment_method": "Card",
    }
    record.update(overrides)
    return record


def ecommerce_record(**overrides):
    record = {
        "order_id": "O001",
        "order_timestamp": "2026-08-24T10:00:00-04:00",
        "cust_ref": "C001",
        "order_total": "7.00",
        "shipping_region": "Ontario",
        "channel": "web",
        "items": [
            {
                "sku": "SKU001",
                "product_name": "Cap",
                "qty": "2",
                "unit_price": "3.50",
            }
        ],
    }
    record.update(overrides)
    return record


def test_missing_and_numeric_helpers():
    assert glue.missing(None)
    assert glue.missing(" UNKNOWN ")
    assert not glue.missing("C001")
    assert glue.numeric("12.50") == Decimal("12.50")
    assert glue.numeric("not-a-number") is None
    assert glue.numeric("NaN") is None


def test_date_parsers_accept_valid_and_reject_invalid_values():
    assert glue.parse_pos_date("2026-08-24")
    assert glue.parse_pos_date("24/08/2026")
    assert not glue.parse_pos_date("2026-02-30")
    assert not glue.parse_pos_date("")

    assert glue.parse_timestamp("2026-08-24T10:00:00Z")
    assert glue.parse_timestamp("2026-08-24T10:00:00-04:00")
    assert not glue.parse_timestamp("not-a-timestamp")


def test_csv_and_json_readers():
    csv_records = glue.read_csv_text(
        "cust_num,first_name\nC001,Alex\n"
    )
    assert csv_records == [{"cust_num": "C001", "first_name": "Alex"}]

    assert glue.read_json_text('[{"order_id":"O001"}]') == [
        {"order_id": "O001"}
    ]

    with pytest.raises(ValueError):
        glue.read_json_text('{"order_id":"O001"}')


def test_validate_customers_quarantines_duplicate_and_missing_fields():
    records = [
        customer(),
        customer(),
        {"cust_num": "C002", "first_name": "Sam"},
    ]

    trusted, rejected, counts = glue.validate_customers(
        records, "customers.csv"
    )

    assert len(trusted) == 1
    assert len(rejected) == 2
    assert "DQ02_DUPLICATE_CUSTOMER_ID" in rejected[0]["rejection_reasons"]
    assert "DQ01_MISSING_REQUIRED:last_name" in rejected[1]["rejection_reasons"]
    assert counts["records_seen"] == 3
    assert counts["records_trusted"] == 1
    assert counts["records_quarantined"] == 2


def test_validate_sales_accepts_valid_pos_and_walk_in_customer():
    records = [
        pos_record(),
        pos_record(
            transaction_id="T002",
            cust_num=glue.WALK_IN_CUSTOMER,
        ),
    ]

    trusted, rejected, counts = glue.validate_sales(
        records, "pos.csv", {"C001"}, "pos"
    )

    assert len(trusted) == 2
    assert rejected == []
    assert counts["records_trusted"] == 2


def test_validate_sales_quarantines_invalid_pos_and_duplicate():
    records = [
        pos_record(),
        pos_record(),
        pos_record(
            transaction_id="T003",
            sale_date="2026-02-30",
            quantity="0",
            unit_price="-1",
            cust_num="UNKNOWN-CUSTOMER",
        ),
    ]

    trusted, rejected, counts = glue.validate_sales(
        records, "pos.csv", {"C001"}, "pos"
    )

    assert len(trusted) == 1
    assert len(rejected) == 2
    assert "DQ02_DUPLICATE_TRANSACTION_ID" in rejected[0]["rejection_reasons"]
    assert "DQ03_INVALID_SALE_DATE" in rejected[1]["rejection_reasons"]
    assert "DQ04_UNKNOWN_CUSTOMER_ID" in rejected[1]["rejection_reasons"]
    assert "DQ05_INVALID_QUANTITY" in rejected[1]["rejection_reasons"]
    assert "DQ05_INVALID_UNIT_PRICE" in rejected[1]["rejection_reasons"]
    assert counts["records_quarantined"] == 2


def test_validate_sales_checks_ecommerce_items():
    valid, rejected, _ = glue.validate_sales(
        [ecommerce_record()], "orders.json", {"C001"}, "ecommerce"
    )
    assert len(valid) == 1
    assert rejected == []

    invalid_order = ecommerce_record(
        order_id="O002",
        items=[{"sku": "SKU002", "qty": "0", "unit_price": "-2"}],
    )
    valid, rejected, _ = glue.validate_sales(
        [invalid_order], "orders.json", {"C001"}, "ecommerce"
    )

    assert valid == []
    reasons = rejected[0]["rejection_reasons"]
    assert "DQ06_ITEM_1_MISSING:product_name" in reasons
    assert "DQ05_ITEM_1_INVALID_QUANTITY" in reasons
    assert "DQ05_ITEM_1_INVALID_UNIT_PRICE" in reasons


def test_reconcile_order_checks_reported_total():
    assert glue.reconcile_order(ecommerce_record())
    assert not glue.reconcile_order(
        ecommerce_record(order_total="8.00")
    )
    assert not glue.reconcile_order(
        ecommerce_record(order_total="invalid")
    )


def test_timestamp_converts_aware_values_to_utc():
    assert (
        glue.timestamp("2026-08-24T10:00:00-04:00")
        == "2026-08-24T14:00:00Z"
    )
    assert (
        glue.timestamp("2026-08-24T10:00:00Z")
        == "2026-08-24T10:00:00Z"
    )


def test_build_sales_model_creates_pos_and_ecommerce_rows():
    customer_lookup = {"C001": customer()}

    pos_entries = [{
        "source_file": "pos.csv",
        "record_number": 1,
        "record": pos_record(),
    }]
    order_entries = [{
        "source_file": "orders.json",
        "record_number": 1,
        "record": ecommerce_record(),
    }]

    rows, reconciled, total_rejections = glue.build_sales_model(
        pos_entries, order_entries, customer_lookup
    )

    assert len(rows) == 2
    assert len(reconciled) == 1
    assert total_rejections == []

    pos_row = next(row for row in rows if row["source_system"] == "pos")
    assert pos_row["sale_line_id"] == "pos:T001"
    assert pos_row["line_amount"] == "50.00"
    assert pos_row["customer_first_name"] == "Alex"

    ecommerce_row = next(
        row for row in rows if row["source_system"] == "ecommerce"
    )
    assert ecommerce_row["sale_line_id"] == "ecommerce:O001:1"
    assert ecommerce_row["sale_timestamp"] == "2026-08-24T14:00:00Z"
    assert ecommerce_row["line_amount"] == "7.00"


def test_build_sales_model_quarantines_order_total_mismatch():
    order_entry = {
        "source_file": "orders.json",
        "record_number": 1,
        "record": ecommerce_record(order_total="99.00"),
    }

    rows, reconciled, total_rejections = glue.build_sales_model(
        [], [order_entry], {"C001": customer()}
    )

    assert rows == []
    assert reconciled == []
    assert len(total_rejections) == 1
    assert (
        total_rejections[0]["rejection_reasons"]
        == ["DQ07_ORDER_TOTAL_MISMATCH"]
    )


def test_money_uses_round_half_up():
    from decimal import Decimal
    from transform.glue_sales_etl import money

    assert money(Decimal("2.345")) == "2.35"
    assert money(Decimal("2.344")) == "2.34"
