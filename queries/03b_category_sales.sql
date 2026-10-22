-- Derived analysis only: does not update curated_sales.
-- Rerun coverage checks whenever product names or categories change.
WITH product_categories AS (
    SELECT LOWER(TRIM(product_name)) AS product_key, MAX(category) AS category
    FROM thornquist_outfitters.curated_sales
    WHERE source_system = 'pos'
      AND NULLIF(TRIM(category), '') IS NOT NULL
    GROUP BY LOWER(TRIM(product_name))
    HAVING COUNT(DISTINCT category) = 1
)
SELECT COALESCE(NULLIF(TRIM(s.category), ''), p.category) AS category,
       SUM(s.line_amount) AS total_sales
FROM thornquist_outfitters.curated_sales s
LEFT JOIN product_categories p
    ON LOWER(TRIM(s.product_name)) = p.product_key
GROUP BY 1
ORDER BY total_sales DESC;
