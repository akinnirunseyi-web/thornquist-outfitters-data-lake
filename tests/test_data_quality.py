import unittest

from transform.data_quality import (
    classify_records,
    is_missing,
    norm_id,
    parse_iso_timestamp,
    parse_pos_date,
)


class DataQualityTests(unittest.TestCase):
    def test_missing_values_and_placeholders(self):
        for value in (None, "", "   ", "NULL", "N/A", "unknown"):
            self.assertTrue(is_missing(value))
        self.assertFalse(is_missing("0"))
        self.assertFalse(is_missing("A-123"))

    def test_pos_date_accepts_both_source_formats(self):
        self.assertTrue(parse_pos_date("2026-08-29"))
        self.assertTrue(parse_pos_date("29/08/2026"))
        self.assertFalse(parse_pos_date("31/02/2026"))
        self.assertFalse(parse_pos_date("not-a-date"))

    def test_iso_timestamp(self):
        self.assertTrue(parse_iso_timestamp("2026-08-24T14:32:00Z"))
        self.assertTrue(parse_iso_timestamp("2026-08-24T14:32:00+00:00"))
        self.assertFalse(parse_iso_timestamp("yesterday"))

    def test_identifier_normalization(self):
        self.assertEqual(norm_id(900000.0), "900000")
        self.assertEqual(norm_id(" 100052 "), "100052")

    def test_valid_pos_record_passes_and_walk_in_is_allowed(self):
        record = {
            "transaction_id": "TX-1", "store_id": "S-1", "sale_date": "29/08/2026",
            "product_name": "Item", "quantity": "1", "unit_price": "12.50",
            "cust_num": "0000000",
        }
        trusted, quarantine, _ = classify_records([record], "pos.csv", set())
        self.assertEqual(len(trusted), 1)
        self.assertEqual(quarantine, [])

    def test_invalid_pos_record_is_quarantined_with_reason(self):
        record = {
            "transaction_id": "TX-1", "store_id": "S-1", "sale_date": "31/02/2026",
            "product_name": "Item", "quantity": "0", "unit_price": "-2",
            "cust_num": "999999",
        }
        trusted, quarantine, _ = classify_records([record], "pos.csv", set())
        self.assertEqual(trusted, [])
        self.assertEqual(len(quarantine), 1)
        self.assertIn("DQ03_INVALID_SALE_DATE", quarantine[0]["rejection_reasons"])
        self.assertIn("DQ04_UNKNOWN_CUSTOMER_ID", quarantine[0]["rejection_reasons"])
        self.assertIn("DQ05_INVALID_QUANTITY", quarantine[0]["rejection_reasons"])
        self.assertIn("DQ05_INVALID_UNIT_PRICE", quarantine[0]["rejection_reasons"])

    def test_duplicate_order_id_quarantines_later_occurrence(self):
        record = {
            "order_id": 1, "order_timestamp": "2026-08-24T14:32:00Z",
            "cust_ref": 100, "items": [{"sku": "SKU-1", "product_name": "Item", "qty": 1, "unit_price": 2.0}],
        }
        trusted, quarantine, _ = classify_records([record, record], "orders.json", {"100"})
        self.assertEqual(len(trusted), 1)
        self.assertEqual(len(quarantine), 1)
        self.assertIn("DQ02_DUPLICATE_ORDER_ID", quarantine[0]["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
