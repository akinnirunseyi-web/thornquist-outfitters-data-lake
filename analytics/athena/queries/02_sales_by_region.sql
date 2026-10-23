-- Compare sales by sales region, with shipping region as a fallback.
SELECT
    COALESCE(
        NULLIF(TRIM(sales_region), ''),
        NULLIF(TRIM(shipping_region), ''),
        'Unknown'
    ) AS region,
    COUNT(*) AS sales_lines,
    SUM(TRY_CAST(quantity AS DOUBLE)) AS units_sold,
    SUM(TRY_CAST(NULLIF(TRIM(line_amount), '') AS DECIMAL(18,2))) AS total_sales
FROM thornquist_outfitters.sales_model
GROUP BY 1
ORDER BY total_sales DESC;
