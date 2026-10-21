import unittest

from transform.build_sales_model import reconcile_order_total


class TestOrderTotalReconciliation(unittest.TestCase):
    def test_matching_order_total_is_accepted(self):
        order = {
            "items": [
                {"qty": "2", "unit_price": "10.00"},
                {"qty": "3", "unit_price": "5.00"},
            ],
            "order_total": "35.00",
        }

        self.assertTrue(reconcile_order_total(order))

    def test_mismatched_order_total_is_rejected(self):
        order = {
            "items": [
                {"qty": "2", "unit_price": "10.00"},
            ],
            "order_total": "19.99",
        }

        self.assertFalse(reconcile_order_total(order))

    def test_invalid_item_value_is_rejected(self):
        order = {
            "items": [
                {"qty": "invalid", "unit_price": "10.00"},
            ],
            "order_total": "20.00",
        }

        self.assertFalse(reconcile_order_total(order))

    def test_missing_order_total_is_rejected(self):
        order = {
            "items": [
                {"qty": "2", "unit_price": "10.00"},
            ],
        }

        self.assertFalse(reconcile_order_total(order))


if __name__ == "__main__":
    unittest.main()
