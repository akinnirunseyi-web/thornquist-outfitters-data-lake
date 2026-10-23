# Athena Cost and Performance Recommendations

## 1. Purpose

This document records practical recommendations for controlling query
costs and improving performance in the Thornquist Outfitters data lake.

## 2. Current observed baseline

- AWS Region: us-east-1.
- Athena workgroup: primary.
- Athena engine: version 3 (AUTO).
- Glue database: thornquist_outfitters.
- The trusted sales_model table is stored as Parquet.
- The current sales_model table location is
  s3://thornquist-data-lake-659260838742/trusted/sales_model/.
- The sales_model table has 1,601 rows based on the completed ETL
  validation.
- The current sales_model schema has no verified partition columns.

The table is currently a small project dataset. The recommendations
below are intended to support efficient analysis as the dataset grows.

## 3. Cost controls

Athena query cost is primarily affected by the amount of data scanned.
Use these practices:

1. Select only the columns needed for an analysis; avoid SELECT *.
2. Filter rows using selective WHERE conditions.
3. Prefer Parquet or another suitable columnar format over repeatedly
   scanning raw CSV or JSON for analytical workloads.
4. Compress analytical data using a compatible codec.
5. Avoid repeatedly running the same expensive query during development.
6. Reuse saved SQL and previously downloaded result files when the
   underlying data has not changed.
7. Review bytes scanned and execution metrics in Athena query details.
8. Consider workgroup-level data-scan limits and monitoring before
   production use.
9. Apply a suitable lifecycle policy to old Athena query-result objects
   after confirming retention requirements.

A LIMIT clause restricts the number of returned rows but does not
necessarily reduce the amount of source data scanned.

## 4. Performance improvements

### Columnar storage

The trusted sales_model table is already stored in Parquet. Keep
analytical transformations on a validated columnar dataset where
appropriate, rather than querying raw source files for every report.

### Partitioning

For larger datasets, consider partitioning by a commonly filtered
attribute, such as sale date or a derived year/month/day key. Partition
design should follow actual query patterns and avoid creating excessive
numbers of tiny files or partitions.

The current sales_model table has no verified partition columns.
Partitioning is therefore a future optimization, not a completed
configuration.

### Query design

- Use explicit column lists.
- Filter by date or other selective fields when applicable.
- Avoid unnecessary joins and repeated transformations.
- Validate join keys and data types before joining large datasets.
- Use TRY_CAST where source values may be malformed, and track invalid
  values rather than silently treating them as valid business data.
- Aggregate at the required reporting grain.
- Check execution status and query metrics after important runs.

### File layout

For larger workloads, consider consolidating very small Parquet files
and targeting a practical file size for the workload. Confirm the
chosen size with measured performance rather than treating one value
as universally optimal.

## 5. Monitoring and validation

For each important query, record:

- Query name and execution ID.
- Final status.
- Data scanned, where available.
- Execution duration, where available.
- Output location.
- Any errors or data-quality limitations.

Use Athena execution details and AWS monitoring to identify expensive
queries and recurring failures. Establish cost alerts and budgets
according to the team's AWS account requirements.

## 6. Current analytical limitations

- E-commerce category values appear as Unknown in the current
  category/channel results. Do not infer categories without a verified
  source mapping.
- SKU values were missing in the initial top-products query results.
  The current report ranks products by product name and category.
- Numeric amounts in sales_model are represented as strings, so
  analytical SQL uses TRY_CAST before summing amounts.
- The sales_model table is currently unpartitioned based on the
  inspected schema.

These limitations should be revisited if the source data or ETL model
changes.

## 7. Recommended next steps

- [ ] Review bytes scanned and execution duration for saved queries.
- [ ] Decide whether the current table size justifies partitioning.
- [ ] Evaluate a partitioned curated table for larger workloads.
- [ ] Configure workgroup-level query controls where appropriate.
- [ ] Define retention and lifecycle policies for query results.
- [ ] Re-run baseline queries after material ETL or schema changes.
