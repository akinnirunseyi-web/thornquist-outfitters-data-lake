-- Count POS transactions and e-commerce orders using the available identifier.
SELECT
    source_system,
    COUNT(*) AS sales_lines,
    COUNT(DISTINCT COALESCE(
        NULLIF(TRIM(transaction_id), ''),
        NULLIF(TRIM(order_id), '')
    )) AS transactions_or_orders,
    SUM(TRY_CAST(NULLIF(TRIM(line_amount), '') AS DECIMAL(18,2))) AS total_sales,
    SUM(TRY_CAST(quantity AS DOUBLE)) AS units_sold
FROM thornquist_outfitters.sales_model
GROUP BY source_system
ORDER BY total_sales DESC;
