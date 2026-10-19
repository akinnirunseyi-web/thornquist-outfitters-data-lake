import unittest

from transform.sales_transform import (
    normalize_ecommerce_timestamp,
    parse_pos_date,
    transform_ecommerce_order,
    transform_pos_record,
)


class SalesTransformTests(unittest.TestCase):
    def setUp(self):
        self.customers = {
            "100101": {
                "first_name": "Alex",
                "last_name": "Martin",
                "loyalty_tier": "Gold",
                "region": "Ontario",
            },
            "100052": {
                "first_name": "Sam",
                "last_name": "Lee",
                "loyalty_tier": "Standard",
                "region": "Quebec",
            },
        }

    def test_pos_date_formats_are_normalized(self):
        self.assertEqual(parse_pos_date("2026-08-29"), "2026-08-29")
        self.assertEqual(parse_pos_date("29/08/2026"), "2026-08-29")

    def test_ecommerce_timestamp_is_normalized_to_utc(self):
        self.assertEqual(
            normalize_ecommerce_timestamp("2026-08-24T16:32:00+02:00"),
            "2026-08-24T14:32:00Z",
        )

    def test_pos_record_is_transformed_and_customer_is_joined(self):
        record = {
            "transaction_id": "500001",
            "store_id": "1",
            "store_name": "Toronto Yonge St",
            "region": "Ontario",
            "sale_date": "29/08/2026",
            "category": "Camping",
            "product_name": "\u00a0Trekking Pole Pair ",
            "quantity": "2",
            "unit_price": "12.50",
            "payment_method": "VISA",
            "cust_num": "100101",
        }

        result = transform_pos_record(
            record, "pos.csv", 2, self.customers
        )

        self.assertEqual(result["sale_line_id"], "pos:500001")
        self.assertEqual(result["sale_timestamp"], "2026-08-29")
        self.assertEqual(result["product_name"], "Trekking Pole Pair")
        self.assertEqual(result["quantity"], 2)
        self.assertEqual(result["unit_price"], "12.50")
        self.assertEqual(result["line_amount"], "25.00")
        self.assertEqual(result["customer_first_name"], "Alex")
        self.assertIsNone(result["sku"])
        self.assertIsNone(result["shipping_region"])

    def test_walk_in_sale_does_not_invent_customer_attributes(self):
        record = {
            "transaction_id": "500010",
            "store_id": "1",
            "store_name": "Toronto Yonge St",
            "region": "Ontario",
            "sale_date": "2026-08-29",
            "category": "Camping",
            "product_name": "Tent",
            "quantity": "1",
            "unit_price": "0",
            "payment_method": "CASH",
            "cust_num": "0000000",
        }

        result = transform_pos_record(record, "pos.csv", 10, self.customers)

        self.assertEqual(result["customer_id"], "0000000")
        self.assertIsNone(result["customer_first_name"])
        self.assertEqual(result["line_amount"], "0.00")

    def test_ecommerce_order_is_flattened_into_item_rows(self):
        order = {
            "order_id": 900000,
            "order_timestamp": "2026-08-24T14:32:00Z",
            "cust_ref": 100052,
            "channel": "online",
            "shipping_region": "Quebec",
            "items": [
                {
                    "sku": "CAM-2734",
                    "product_name": "Trekking Pole Pair",
                    "qty": 2,
                    "unit_price": 10.25,
                },
                {
                    "sku": "ACC-2299",
                    "product_name": "Wool Socks",
                    "qty": 1,
                    "unit_price": 5.50,
                },
            ],
            "order_total": 26.00,
        }

        rows = transform_ecommerce_order(
            order, "orders.json", 1, self.customers
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["sale_line_id"], "ecommerce:900000:1")
        self.assertEqual(rows[1]["sale_line_id"], "ecommerce:900000:2")
        self.assertEqual(rows[0]["customer_id"], "100052")
        self.assertEqual(rows[0]["customer_first_name"], "Sam")
        self.assertEqual(rows[0]["line_amount"], "20.50")
        self.assertEqual(rows[1]["line_amount"], "5.50")
        self.assertIsNone(rows[0]["category"])
        self.assertIsNone(rows[0]["store_id"])
        self.assertEqual(rows[0]["shipping_region"], "Quebec")


if __name__ == "__main__":
    unittest.main()
