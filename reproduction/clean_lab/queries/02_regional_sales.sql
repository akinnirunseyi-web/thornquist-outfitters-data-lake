-- Question 2: region means store location for POS and destination for ecommerce.
SELECT sales_region, source_system, SUM(line_amount) AS total_sales,
 SUM(quantity) AS units_sold, COUNT(DISTINCT CASE WHEN source_system = 'pos' THEN transaction_id ELSE order_id END) AS transactions
FROM __DATABASE__.curated_sales
GROUP BY sales_region, source_system
ORDER BY total_sales DESC;
