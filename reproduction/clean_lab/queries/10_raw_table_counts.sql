SELECT 'raw_customers' AS table_name, COUNT(*) AS records FROM __DATABASE__.raw_customers
UNION ALL
SELECT 'raw_pos', COUNT(*) FROM __DATABASE__.raw_pos
UNION ALL
SELECT 'raw_ecommerce_ndjson', COUNT(*) FROM __DATABASE__.raw_ecommerce_ndjson;
