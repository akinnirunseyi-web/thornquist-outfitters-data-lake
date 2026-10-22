-- Reproduction DDL for the verified Trusted Parquet schema.
-- This table is a catalog definition over existing ETL output, not a data copy.
CREATE EXTERNAL TABLE IF NOT EXISTS thornquist_outfitters.trusted_sales_model (
 sale_line_id string, source_system string, transaction_id string, order_id string,
 order_line_number int, customer_id string, sale_timestamp string,
 sku string, product_name string, category string, quantity double,
 unit_price string, line_amount string, sales_region string, shipping_region string,
 store_id string, store_name string, payment_method string, channel string,
 source_file string, source_record_number int, customer_first_name string,
 customer_last_name string, customer_loyalty_tier string, customer_region string
)
STORED AS PARQUET
LOCATION 's3://thornquist-data-lake-2026102/trusted/sales_model/';
