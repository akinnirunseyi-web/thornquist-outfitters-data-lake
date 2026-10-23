-- Compare sales across product categories and sales channels.
SELECT
    COALESCE(NULLIF(TRIM(category), ''), 'Unknown') AS category,
    COALESCE(NULLIF(TRIM(channel), ''), 'Unknown') AS channel,
    COUNT(*) AS sales_lines,
    SUM(TRY_CAST(quantity AS DOUBLE)) AS units_sold,
    SUM(TRY_CAST(NULLIF(TRIM(line_amount), '') AS DECIMAL(18,2))) AS total_sales
FROM thornquist_outfitters.sales_model
GROUP BY 1, 2
ORDER BY total_sales DESC;
