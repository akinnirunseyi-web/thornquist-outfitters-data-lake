-- Reproduction SQL matching the verified Curated shape and storage design.
-- Run only for a NEW table and EMPTY destination. Existing deployed table/data
-- must be preserved; a refresh requires a separately reviewed replacement plan.
CREATE TABLE thornquist_outfitters.curated_sales
WITH (
 format = 'PARQUET',
 write_compression = 'SNAPPY',
 external_location = 's3://thornquist-data-lake-2026102/curated/sales/',
 partitioned_by = ARRAY['sale_year', 'sale_month']
) AS
SELECT sale_line_id, source_system, transaction_id, order_id, order_line_number,
 customer_id, CAST(SUBSTR(sale_timestamp, 1, 10) AS DATE) AS sale_date,
 sku, product_name, category, quantity,
 CAST(unit_price AS DECIMAL(18,2)) AS unit_price,
 CAST(line_amount AS DECIMAL(18,2)) AS line_amount,
 COALESCE(NULLIF(TRIM(sales_region), ''), NULLIF(TRIM(shipping_region), '')) AS sales_region,
 shipping_region, store_id, store_name, payment_method, channel,
 source_file, source_record_number,
 customer_loyalty_tier AS loyalty_tier, customer_region,
 SUBSTR(sale_timestamp, 1, 4) AS sale_year,
 SUBSTR(sale_timestamp, 6, 2) AS sale_month
FROM thornquist_outfitters.trusted_sales_model;
