-- Question 3a: top-ten ranking; it does not sum to total portfolio revenue.
SELECT product_name, SUM(line_amount) AS total_sales, SUM(quantity) AS units_sold,
 SUM(CASE WHEN source_system = 'pos' THEN line_amount ELSE 0 END) AS pos_sales,
 SUM(CASE WHEN source_system = 'ecommerce' THEN line_amount ELSE 0 END) AS ecommerce_sales
FROM __DATABASE__.curated_sales
GROUP BY product_name
ORDER BY total_sales DESC, product_name
LIMIT 10;
