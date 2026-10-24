SELECT 'trusted_customers' AS table_name, COUNT(*) AS records FROM __DATABASE__.trusted_customers
UNION ALL
SELECT 'trusted_pos_sales', COUNT(*) FROM __DATABASE__.trusted_pos_sales
UNION ALL
SELECT 'trusted_ecommerce_orders', COUNT(*) FROM __DATABASE__.trusted_ecommerce_orders
UNION ALL
SELECT 'trusted_sales_model', COUNT(*) FROM __DATABASE__.trusted_sales_model;
