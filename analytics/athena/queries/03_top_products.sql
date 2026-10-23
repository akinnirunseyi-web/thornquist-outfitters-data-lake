-- Rank products by name and category because SKU values are missing in results.
SELECT
    product_name,
    category,
    SUM(TRY_CAST(quantity AS DOUBLE)) AS units_sold,
    SUM(TRY_CAST(NULLIF(TRIM(line_amount), '') AS DECIMAL(18,2))) AS total_sales
FROM thornquist_outfitters.sales_model
WHERE NULLIF(TRIM(product_name), '') IS NOT NULL
GROUP BY product_name, category
ORDER BY total_sales DESC
LIMIT 10;
