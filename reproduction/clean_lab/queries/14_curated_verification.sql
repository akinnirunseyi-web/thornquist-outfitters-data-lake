SELECT COUNT(*) AS sales_lines,
       SUM(line_amount) AS total_sales,
       MIN(sale_date) AS first_date,
       MAX(sale_date) AS last_date,
       COUNT_IF(quantity <= 0 OR quantity IS NULL) AS bad_quantity_lines,
       COUNT(*) - COUNT(DISTINCT sale_line_id) AS duplicate_line_ids
FROM __DATABASE__.curated_sales;
