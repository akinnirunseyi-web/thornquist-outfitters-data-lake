SELECT 'bad' AS variant, COUNT(*) AS sales_lines
FROM __DATABASE__.demo_bad_sales WHERE order_id = '900000'
UNION ALL
SELECT 'corrected', COUNT(*)
FROM __DATABASE__.trusted_sales_model WHERE order_id = '900000';
