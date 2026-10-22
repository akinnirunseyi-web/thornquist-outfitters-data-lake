-- Question 1: daily comparison by source. Transaction counts are computed per source.
SELECT sale_date, source_system, SUM(line_amount) AS total_sales,
 SUM(quantity) AS units_sold, COUNT(DISTINCT CASE WHEN source_system = 'pos' THEN transaction_id ELSE order_id END) AS transactions
FROM thornquist_outfitters.curated_sales
GROUP BY sale_date, source_system
ORDER BY sale_date, source_system;
