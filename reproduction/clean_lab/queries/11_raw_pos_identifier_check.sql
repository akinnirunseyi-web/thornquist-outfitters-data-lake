-- Identifiers stay strings. This query must retain the 0000000 guest identifier.
SELECT transaction_id, store_id, cust_num, sale_date, quantity, unit_price
FROM __DATABASE__.raw_pos
WHERE cust_num = '0000000'
ORDER BY transaction_id
LIMIT 5;
