-- Expected: POS 1048 / 214561.78; ecommerce 553 / 106008.57.
SELECT source_system, COUNT(*) AS sales_lines, SUM(line_amount) AS total_sales
FROM thornquist_outfitters.curated_sales GROUP BY source_system;
-- Expected: 1601 / 320570.35, August 24 through August 30, 2026.
SELECT COUNT(*) AS sales_lines, SUM(line_amount) AS total_sales,
       MIN(sale_date) AS first_date, MAX(sale_date) AS last_date
FROM thornquist_outfitters.curated_sales;
SHOW PARTITIONS thornquist_outfitters.curated_sales;
DESCRIBE thornquist_outfitters.curated_sales;
