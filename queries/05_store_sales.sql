-- Question 5: POS only; ecommerce has no store identity in this source.
SELECT store_id, store_name, sales_region, SUM(line_amount) AS total_sales,
 SUM(quantity) AS units_sold, COUNT(DISTINCT transaction_id) AS transactions,
 ROUND(SUM(line_amount) / NULLIF(COUNT(DISTINCT transaction_id), 0), 2) AS average_transaction_value
FROM thornquist_outfitters.curated_sales
WHERE source_system = 'pos'
GROUP BY store_id, store_name, sales_region
ORDER BY total_sales DESC, store_id;
