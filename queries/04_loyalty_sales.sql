-- Question 4: walk-ins remain a separate, unidentified segment.
WITH segment_sales AS (
 SELECT CASE WHEN customer_id = '0000000' THEN 'Walk-in'
             ELSE COALESCE(NULLIF(TRIM(loyalty_tier), ''), 'Walk-in') END AS loyalty_tier,
        customer_id, line_amount,
        source_system || ':' || CASE WHEN source_system = 'pos' THEN transaction_id ELSE order_id END AS transaction_key
 FROM thornquist_outfitters.curated_sales
)
SELECT loyalty_tier, SUM(line_amount) AS total_sales,
 COUNT(DISTINCT CASE WHEN customer_id <> '0000000' THEN customer_id END) AS identified_customers,
 COUNT(DISTINCT transaction_key) AS transactions,
 ROUND(SUM(line_amount) / NULLIF(COUNT(DISTINCT transaction_key), 0), 2) AS average_transaction_value
FROM segment_sales
GROUP BY loyalty_tier
ORDER BY total_sales DESC;
