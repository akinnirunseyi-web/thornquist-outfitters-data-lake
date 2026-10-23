-- Daily sales trend. Supports common ISO and date-only representations.
WITH parsed_sales AS (
    SELECT
        COALESCE(
            TRY_CAST(sale_timestamp AS TIMESTAMP),
            TRY_CAST(
                from_iso8601_timestamp(sale_timestamp) AS TIMESTAMP
            ),
            TRY_CAST(
                date_parse(sale_timestamp, '%d/%m/%Y') AS TIMESTAMP
            )
        ) AS sale_time,
        TRY_CAST(
            NULLIF(TRIM(line_amount), '') AS DECIMAL(18,2)
        ) AS amount,
        TRY_CAST(quantity AS DOUBLE) AS qty
    FROM thornquist_outfitters.sales_model
)
SELECT
    CAST(sale_time AS DATE) AS sale_date,
    COUNT(*) AS sales_lines,
    SUM(qty) AS units_sold,
    SUM(amount) AS total_sales
FROM parsed_sales
WHERE sale_time IS NOT NULL
GROUP BY CAST(sale_time AS DATE)
ORDER BY sale_date;
