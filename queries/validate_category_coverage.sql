-- Run before the category chart whenever inputs change.
WITH product_categories AS (
 SELECT LOWER(TRIM(product_name)) AS product_key, MAX(category) AS category
 FROM thornquist_outfitters.curated_sales
 WHERE source_system = 'pos' AND NULLIF(TRIM(category), '') IS NOT NULL
 GROUP BY LOWER(TRIM(product_name)) HAVING COUNT(DISTINCT category) = 1
)
SELECT CASE WHEN p.category IS NOT NULL THEN 'Category matched' ELSE 'Unmatched' END AS mapping_status,
 COUNT(*) AS sales_lines, SUM(s.line_amount) AS total_sales
FROM thornquist_outfitters.curated_sales s
LEFT JOIN product_categories p ON LOWER(TRIM(s.product_name)) = p.product_key
WHERE s.source_system = 'ecommerce'
GROUP BY 1;
