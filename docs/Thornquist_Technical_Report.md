# Thornquist Outfitters Data Lake Technical Report

CCGC 5506 Mid Term Project | Humber Fall 2026 | 23 October 2026

## Business purpose and delivery outcome

Thornquist Outfitters needs a shared view of store and ecommerce sales linked to customer information. Its source formats and identifiers differ, and deliberately inconsistent records make direct aggregation unreliable. We built a zoned Amazon S3 lake with three ingestion mechanisms, a Glue validation and conformance job, partitioned Parquet analytics, and an offline notebook visualization layer. The verified reporting period is August 24 to 30, 2026. The sample represents ten stores, although the fictional business operates forty.

The accepted dataset contains 1,601 sales lines and total sales of 320,570.35 in source monetary units. POS contributes 214,561.78 and ecommerce 106,008.57. These values exclude quarantined records. No currency code was supplied, so the analysis does not label amounts as Canadian dollars. The isolated 23 October rehearsal exercised ingestion, the quality gate, Raw and Trusted queries, Curated creation and six business queries.

## Architecture and zone boundaries

The deployment uses bucket thornquist-data-lake-2026102 in us-east-1. Landing retains submitted synthetic source files. Raw holds ingested data before business validation. Trusted contains records that pass validation and the flattened sales model. Curated exposes accepted sales in a query-oriented structure. Separate quarantine and reports prefixes retain rejected records and reconciliation evidence. Query outputs use athena-results. The companion architecture diagram shows data flow separately from catalog, monitoring and access controls.

Promotion is explicit. Ingestion moves Landing data into Raw without treating a successful copy as proof of business validity. The Glue sales job validates Raw inputs and sends invalid records to Quarantine with rejection reasons. Accepted records enter Trusted, where customer enrichment and order reconciliation produce a common sales-line model. Athena CREATE TABLE AS SELECT, or CTAS, creates Curated Parquet from that model. Curated refresh is manually initiated. These logical prefixes organize processing; the shared execution identity means they are not yet independently enforced access boundaries.

## Ingestion and catalog design

POS ingestion uses a Bash copy from landing/pos to raw/pos. Ecommerce ingestion uses the thornquist-ingest-ecommerce Lambda function, triggered by S3 object creation under landing/ecommerce. Manual invocation and an actual upload-triggered copy were verified. The original JSON array contains 265 orders and remains intact in raw/ecommerce. No API Gateway endpoint was deployed.

The thornquist-customer-ingestion Glue job reads the customer CSV and writes 400 rows as Parquet under raw/customers. This makes the customer Raw representation structurally transformed, while Landing preserves its original file. The 07:00 UTC daily job trigger started a customer run automatically on 23 October; it succeeded and the trigger was later restarted after being found deactivated. A separate manual conversion produces ecommerce NDJSON for Athena catalog exploration; the sales ETL reads the original JSON array, so it does not depend on that conversion.

Four crawlers populate the thornquist_outfitters database. Daily schedules were configured for customers at 07:15, ecommerce NDJSON at 07:20, POS at 07:25 and Trusted sales at 07:30 UTC. Existing successful runs demonstrate crawler operation. The customer job trigger ran successfully at 07:00 UTC on 23 October; crawler schedules are independent timers and do not wait for upstream success. In our AWS run, we showed catalog tables covering Landing, Raw, Trusted and Curated. The repository documents the corresponding table definitions, including Landing POS with identifiers preserved as text, and a count query for its 1,051 source rows. The clean-session run also completed the quality gate, Curated creation and business queries.

## Schema reconciliation

We resolved source differences in the common sales model and documented the remaining classification assumptions. First, POS dates accept ISO and day/month/year formats, while ecommerce supplies ISO timestamps. POS dates are normalized, and timezone-aware ecommerce timestamps are converted to UTC. Curated exposes a DATE for reporting. Date-only store records do not acquire a fabricated time of day.

Second, POS cust_num and ecommerce cust_ref become customer_id. Identifiers are treated as strings so leading zeros remain meaningful. The POS crawler initially inferred numeric identifiers; transaction_id, store_id and cust_num were manually corrected to string in the catalog. The crawler was subsequently configured to ignore schema updates, protecting that manual definition. A post-crawl catalog screenshot shows the three corrected identifier columns still typed as strings.

Third, ecommerce orders contain nested item arrays, whereas each POS record already describes a sales line. Accepted orders are expanded into item lines with order identifiers and line numbers. Transaction counts therefore combine 1,048 POS transactions with 226 ecommerce orders, rather than counting all 1,601 lines as separate transactions.

Fourth, amounts arrive with different numeric representations. Decimal arithmetic and cent rounding support item-total reconciliation; Curated casts unit price and line amount to DECIMAL(18,2). Fifth, POS region describes a store location, while ecommerce shipping_region describes a delivery destination. The common reporting region preserves that interpretation. Sixth, ecommerce categories are absent. For category analysis, trimmed lowercase product names map to POS categories only when the name has exactly one nonblank category. All 553 ecommerce lines matched. This derived query classification leaves the underlying Curated category field unchanged and requires review on refresh.

## Automated quality gate and recovery

Custom Python validation inside thornquist-sales-etl implements the permitted alternative to managed Glue Data Quality rulesets. The rules cover required fields and placeholder values, duplicate identifiers, valid dates and timestamps, customer reference integrity, positive quantities, nonnegative finite prices, nonempty item arrays and required item fields. A further check compares each accepted ecommerce order total with the calculated item total. A record can fail more than one rule.

Rejected records retain their original content, source file, record number and rejection reasons. They do not enter accepted sales analytics. The POS walk-in identifier is an explicit guest exception to the customer lookup. It does not represent an individually identified customer. Unrecognized ecommerce customer references remain quarantined because inventing a customer mapping would conceal the source defect.

| Source | Records read | Accepted records | Quarantined records |
| --- | ---: | ---: | ---: |
| Customers | 400 | 400 | 0 |
| POS | 1,051 | 1,048 | 3 |
| Ecommerce orders | 265 | 226 | 39 |

The three POS rejects were duplicates. Ecommerce rejection reasons included 35 unknown-customer references and five duplicate-order flags across 39 rejected orders; one record had overlapping reasons. All 226 accepted orders reconciled to item totals and expanded into 553 lines. Together with POS, they produced 1,601 accepted lines. These are batch-level results; duplicate detection does not establish a historical, cross-batch deduplication service.

A controlled recovery demonstration changed the first item quantity in a copy of order 900000 from its original value 1 to -1. Validation rejected the test copy. Restoring the authoritative original quantity admitted one order and four reconciled lines into separate demonstration paths. Production data was not modified, and the 42 production rejects were not repaired by this demonstration. In an isolated clean-session rehearsal on 23 October, separate Glue runs rejected quantity -1 and accepted the corrected quantity 1. Raw and Trusted Athena queries, a partitioned Curated CTAS, six business queries and an HTML analytics snapshot completed in that rehearsal. The repository runner includes retries, Glue queuing and the Landing POS catalog check.

## Curated storage and analytical findings

Athena CTAS wrote Snappy-compressed Parquet to curated/sales, partitioned by sale_year and sale_month. The verified sample resides in sale_year=2026/sale_month=08. Curated omits customer first and last names but retains customer identifiers and segmentation fields, so it is not anonymous. The table is explicitly shaped through SQL rather than relying on crawler inference alone.

Six query result sets support five business questions, with product and category analyses grouped together. Daily, regional, loyalty and category totals reconcile to 320,570.35. Store totals reconcile to POS sales only. The top-ten-product result is a ranking and must not be interpreted as total portfolio revenue.

| Business question | Verified finding |
| --- | --- |
| How do daily store and ecommerce sales compare | POS exceeds ecommerce on each of the seven days; ecommerce contributes 33.1 percent of total sales |
| Which regions lead by channel | Ontario leads POS; Quebec leads ecommerce; Atlantic ecommerce exceeds Atlantic POS |
| Which products and categories generate the most sales | Alpine Hiking Shoe leads product revenue; Camping leads category revenue at 84,458.34 |
| How do customer segments differ | Standard contributes the most sales; Silver has the highest average transaction value in the reporting week |
| Which stores lead POS sales | Toronto Yonge St leads Victoria Douglas by 37.41; Victoria has more transactions and units |

QuickSight access was denied for the Learner Lab identity. We used a pandas and matplotlib notebook in VS Code, with saved charts and a browser-readable HTML version. It consumes exported Athena results and does not connect live to AWS. Five original CSV exports are retained unchanged; the category CSV was transcribed from the complete Athena results supplied during verification. The category query and mapping rationale accompany the package.

These findings describe one week and do not establish growth trends or causal loyalty effects. Customer counts by tier cannot establish cross-channel customer overlap. Store productivity cannot be inferred without traffic, floor area or operating hours. The category matching provides full sample coverage but still needs an authoritative product master for a larger deployment.

## Governance and operational controls

Bucket Block Public Access is enabled, and default encryption uses SSE-S3. The deployed DenyInsecureTransport policy rejects insecure transport for the bucket and objects, with direct AWS service principals excluded from that deny. CloudTrail recorded a successful PutBucketPolicy request with HTTP 204. Default encryption was inspected at bucket level, not audited object by object.

The lab uses existing execution roles and restricts IAM administration. An iam:GetPolicy request was explicitly denied, Lake Formation ListPermissions was unavailable, and an attempt to create the separate ThornquistAnalyst role returned AccessDenied for iam:CreateRole. We documented those boundaries rather than claiming to have inspected effective permissions. A failed permissions listing does not prove that no grants exist.

Our governance package includes the least-privilege analyst IAM JSON, a proposed bucket policy that denies that analyst access to Landing, Raw, Trusted and Quarantine, a Lake Formation permission list specifying SELECT on Curated sales, and an access RACI showing who should see each zone. In that RACI, ingestion and ETL operators handle source and validation data, a data steward reviews rejects, and the analyst would read Curated data only. We deployed an HTTPS-only bucket policy. The Learner Lab denied creation of the separate analyst role and Lake Formation permission inspection, so we supplied the role-specific controls as the documented governance design requested by the brief. An administrator would need to apply and test those controls in an account that permits the separate role and grants.

Operational monitoring includes Glue logs and metrics, an enabled Lambda Errors alarm, and an enabled EventBridge rule for FAILED or TIMEOUT states from both Glue jobs. The rule targets thornquist-pipeline-alerts. Its SNS policy permits EventBridge publishing without creating another execution role. The observed service permission is not restricted exclusively to this rule.

Seven AWS event-pattern tests passed. We received an SNS email when we deliberately set the Lambda alarm to ALARM, and another when a customer Glue run genuinely failed on a deliberately missing input. This demonstrates both configured email routes. The first test changed the alarm state directly; we did not deliberately cause a Lambda execution error. Successful S3-triggered Lambda ingestion was demonstrated separately.

## Cost and performance choices

We used S3 Standard for the small, actively queried sample and wrote Curated sales as Snappy Parquet partitioned by year and month. That layout supports column reads and period filters while avoiding daily partitions for a one-week dataset. With only one monthly partition in the sample, we did not measure a multi-period scan or cost reduction. The on-demand Glue and Athena design suits a short Learner Lab session; we did not configure a lifecycle transition without a defined retention policy.

## Lessons learned

We learned to inspect crawler-inferred schemas before using them for joins, preserve customer identifiers as strings, and reconcile ecommerce totals at order level before expanding items into sales lines. The customer Parquet output required us to adapt the sales reader, and category coverage required an explicit product-name mapping. When QuickSight access was denied, our notebook and exported Athena results provided the required channel, region, category and customer-segment views.

Our clean-session reproduction completed the quality rejection, correction, Curated table and business queries. We retained the run evidence separately. The Learner Lab restrictions on QuickSight, Lake Formation permission inspection and separate IAM role creation shaped our implementation and governance package; our access RACI and policy files describe the intended analyst boundary.

## References

[1] Humber College. CCGC 5506 Mid Term Project. Project 1 Thornquist Outfitters. Fall 2026. Requirements, assessment rubric and Learner Lab constraints.

[2] AWS. Partition your data. https://docs.aws.amazon.com/athena/latest/ug/partitions.html

[3] AWS. Optimize data. https://docs.aws.amazon.com/athena/latest/ug/performance-tuning-data-optimization-techniques.html

[4] AWS. Automating AWS Glue with EventBridge. https://docs.aws.amazon.com/glue/latest/dg/automating-awsglue-with-cloudwatch-events.html

[5] Project evidence. AWS run results, sales_model_summary.json, category mapping results, seven EventBridge pattern tests, and controlled notification emails, 22–23 October 2026.
