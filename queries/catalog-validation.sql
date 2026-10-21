-- Run in Athena with database thornquist_outfitters selected.
-- 1) Validate the manually curated table and preserve identifiers as strings.
SELECT transaction_id, sale_date, cust_num, quantity, unit_price
FROM thornquist_outfitters.pos_sales_manual
LIMIT 10;

-- 2) Confirm walk-in identifiers retain leading zeros.
SELECT cust_num, count(*) AS rows
FROM thornquist_outfitters.pos_sales_manual
WHERE cust_num = '0000000'
GROUP BY cust_num;

-- 3) Check row count on the manually defined POS table.
SELECT count(*) AS pos_rows
FROM thornquist_outfitters.pos_sales_manual;

-- After crawler runs, use SHOW TABLES to discover the exact crawler-generated names:
SHOW TABLES IN thornquist_outfitters;

-- Then run DESCRIBE <actual_crawler_generated_table_name> and a COUNT(*) query
-- for each crawler table. Glue table names are derived from source filenames
-- and can differ if the files/prefixes differ from the expected setup.
