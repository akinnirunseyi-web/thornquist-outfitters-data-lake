# Evidence — Glue ETL Sales Model

## Scope
These artifacts document local validation and sales-model transformation
for the customer, POS sales, and e-commerce source datasets.

## Evidence files
- `Issue02_S3_Source_Datasets.png`: source-dataset evidence.
- `02-tests.txt`: local pytest results.
- `03-validation-summary.json`: local data-quality validation summary.
- `04-sales-model-summary.json`: local reconciliation and sales-model summary.
- `05-quarantine-example.jsonl`: example of a rejected POS record and its reason.
- `06-trusted-sales-example.jsonl`: example of a normalized sales-model record.

## Latest local results
- Automated tests: 28 passed.
- Customers: 400 records validated.
- POS: 1,051 records examined; 1,048 trusted; 3 quarantined.
- E-commerce: 265 orders examined; 226 trusted; 39 quarantined.
- Reconciliation: 226 validated orders checked; 0 total mismatches.
- Unified sales model: 1,601 rows (1,048 POS rows and 553 e-commerce item rows).

## Important limitations
These results were produced locally. They do not demonstrate a successful
AWS Glue job run or a successful publication to S3 in Parquet format.
AWS Glue execution, S3 output, and the final Trusted schema still require
confirmation against the team's agreed implementation.

Customer names are redacted in the saved trusted example. Review all
evidence files for sensitive information before committing.
