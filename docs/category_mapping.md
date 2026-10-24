# Category analysis provenance

Reporting period: August 24–30, 2026. We recorded these results from Athena on 22 October 2026.

The original Curated table has blank categories on all 553 ecommerce lines, representing 106,008.57. POS categories cover 1,048 lines and 214,561.78. We ran a coverage query that matched every ecommerce line to a POS product name after LOWER(TRIM(product_name)); only names with exactly one distinct nonblank POS category qualified. Coverage result: Category matched, 553 lines, 106,008.57; no unmatched group was returned.

The included SQL fills blank categories for analysis using those unambiguous matches. It does not update the underlying Curated table, ETL, or product master. Product-name agreement supports this derived classification but does not establish authoritative SKU equivalence across channels. Recheck coverage and ambiguity after every refresh; review any unmatched results before reporting.

Sales_by_category.csv is transcribed from the final Athena query result, rather than an original downloaded CSV:

| Category | Total sales |
| --- | ---: |
| Camping | 84,458.34 |
| Apparel | 81,480.70 |
| Accessories | 78,678.77 |
| Footwear | 75,952.54 |
| Total | 320,570.35 |

The total reconciles exactly to daily, regional and loyalty results. Monetary values use source units because no currency code was supplied.

SQL: [category sales](../queries/03b_category_sales.sql) and [coverage check](../queries/validate_category_coverage.sql).
