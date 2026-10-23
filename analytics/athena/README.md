# Thornquist Outfitters — Athena Analytics

## Data source
The initial analytical source is the Glue Data Catalog table
`thornquist_outfitters.sales_model`, stored in the Trusted S3 zone as Parquet.

## Queries
1. `01_sales_by_source.sql` — compares POS and e-commerce sales.
2. `02_sales_by_region.sql` — compares sales by region.
3. `03_top_products.sql` — ranks products by sales.
4. `04_sales_by_category_channel.sql` — compares categories and channels.
5. `05_sales_by_day.sql` — explores daily sales trends.

## Data handling
- Numeric text fields are converted with `TRY_CAST` to avoid query failures
  caused by invalid values.
- `line_amount` is used as the sales measure.
- The daily trend query attempts common timestamp/date formats. Verify its
  parsed date coverage against the source data before presenting the results.
- These queries use the Trusted sales model; they do not independently
  reprocess or deduplicate source records.

## Execution
Run the SQL in Amazon Athena using the `thornquist_outfitters` database.
Record each query execution ID and save result screenshots or exports as
project evidence.
