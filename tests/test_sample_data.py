"""Regression of retained Glue business logic against unchanged instructor files."""
import csv
import json
from pathlib import Path
from decimal import Decimal
from transform import glue_sales_etl as etl


def test_sample_reconciliation():
    data = Path(__file__).resolve().parents[1] / 'data'
    with (data / 'customer_extract.csv').open(encoding='utf-8-sig', newline='') as f:
        customers = list(csv.DictReader(f))
    with (data / 'pos_sales_2026-08-24_to_2026-08-30.csv').open(encoding='utf-8-sig', newline='') as f:
        pos = list(csv.DictReader(f))
    orders = json.loads((data / 'ecommerce_orders.json').read_text(encoding='utf-8-sig'))
    accepted, rejected, _ = etl.validate_customers(customers, 'customer_extract.csv')
    assert len(accepted) == 400 and not rejected
    lookup = {etl.norm_id(e['record']['cust_num']): e['record'] for e in accepted}
    p, bad_p, _ = etl.validate_sales(pos, 'pos.csv', set(lookup), 'pos')
    e, bad_e, _ = etl.validate_sales(orders, 'orders.json', set(lookup), 'ecommerce')
    rows, reconciled, mismatches = etl.build_sales_model(p, e, lookup)
    assert (len(p), len(bad_p), len(reconciled), len(bad_e)) == (1048, 3, 226, 39)
    assert not mismatches and len(rows) == 1601
    assert sum((Decimal(r['line_amount']) for r in rows), Decimal('0')) == Decimal('320570.35')
