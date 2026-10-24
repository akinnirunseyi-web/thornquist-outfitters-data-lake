# Thornquist clean Learner Lab reproduction

This package builds a separate, uniquely named pipeline, runs the actual Glue quality gate on a bad copy and its corrected version, queries Raw and Trusted in Athena, creates Curated, and exports six business-query results and an analytics snapshot.

**Runner revision 1.2:** the package includes the retry and Glue queuing behavior used to handle the observed lab timing issues and defines a Landing POS catalog table alongside Raw, Trusted and Curated tables. The `rehearsal01` AWS run completed the pipeline on 23 October 2026: the quality gate rejected the controlled bad order, accepted its corrected copy, and Athena completed Raw, Trusted, Curated and six business queries. Its evidence ZIP was downloaded from CloudShell. This repository revision records the Landing table definition and count check in the reproducible runner. Our AWS demonstration showed catalog tables across all four zones.

For a fresh session, use a new run label. Keep the earlier rehearsal directory and evidence; a changed script cannot resume an older checkpoint.

## Start in AWS CloudShell

1. Start a fresh Learner Lab session and open CloudShell in **us-east-1**. Download this GitHub repository as a ZIP and upload it through CloudShell **Actions → Upload file**.
2. Extract it, then change into its `reproduction/clean_lab` directory. The downloaded ZIP's top-level folder name depends on the repository and branch:

   ```bash
   unzip thornquist-outfitters-data-lake-main.zip
   cd thornquist-outfitters-data-lake-main/reproduction/clean_lab
   ```

3. Preview the plan. This command validates the unchanged input hashes without calling AWS:

   ```bash
   python3 clean_lab.py \
     --expected-account 470551642447 \
     --run-label recording01 \
     --enable-schedules
   ```

4. Execute that plan:

   ```bash
   python3 clean_lab.py \
     --expected-account 470551642447 \
     --run-label recording01 \
     --enable-schedules \
     --apply
   ```

For a teammate's account, replace the account number with theirs. Use a new label for each independent rehearsal, such as `recording02`. Labels have 3–20 lowercase letters/digits and start with a letter. The existing `LabRole` must already allow the demonstrated S3, Lambda, Glue, Athena and logging actions and be usable by Glue and Lambda. No IAM identities or role permissions are created or changed. boto3 is needed only for `--apply`; it is normally available in CloudShell. If missing, install `requirements.txt` in your chosen Python environment.

The runner reuses the selected existing Athena workgroup (`primary` by default) and stops if its enforced settings conflict with the CTAS location. It does not change that workgroup. Lab-specific permission denials must be resolved through the permitted lab configuration; this package does not remove lab restrictions.

## Resources and execution

For `recording01` in the example account:

| Resource | Name |
| --- | --- |
| New S3 bucket | `thornquist-clean-470551642447-recording01` |
| New Glue database | `tq_clean_recording01` |
| Ecommerce Lambda | `tqclean-recording01-ecommerce` |
| Customer Glue job | `tqclean-recording01-customer-ingestion` |
| Sales Glue job | `tqclean-recording01-sales-etl` |
| Customer daily trigger | `tqclean-recording01-customer-daily` |
| Four crawlers | `tqclean-recording01-raw-customers`, `-raw-ecommerce`, `-raw-pos`, `-trusted-sales` |

Both Spark jobs use **Glue 4.0, G.1X, two workers, zero retries, job-run queuing enabled and a 20-minute execution timeout**. The sales runtime/worker settings match the exported deployed job. The customer job uses the same reproduction configuration. Lambda uses the deployed Python 3.14 handler and preserves ecommerce JSON bytes.

Execution is sequential and stops at failed checks:

1. Verify the AWS account and fresh resource names, then create private/encrypted S3, Lambda with an S3 trigger, Glue jobs, explicit catalog tables and crawler definitions.
2. Upload unchanged originals. Copy POS into Raw by script; observe the actual S3-triggered Lambda copy of ecommerce; create its separate NDJSON query representation; run customer ingestion to Raw Parquet.
3. Query the unchanged Landing POS CSV through `landing_pos` (1,051 rows). Run the three Raw crawlers, query all three Raw tables in Athena and check the leading-zero guest identifier.
4. Run the actual sales Glue job against a separate controlled copy with order `900000`, first-item quantity `-1`. Check its quarantine entry, reason and full output counts.
5. Run the actual sales Glue job against a corrected copy containing the **unchanged original bytes**, quantity `1`. Check the reports, then crawl Trusted. Query four Trusted tables. Athena must show zero lines for that order in the bad variant and four in the corrected variant.
6. Create a new Curated table only after those checks pass. Verify counts, total, dates, positive quantities, unique line IDs, year/month partitions, catalog Parquet format and a data object's `PAR1` signature. Successful CTAS SQL records the requested Snappy compression.
7. Execute six business queries, reconcile their totals and produce a fresh browser-readable analytics snapshot and evidence ZIP.

There are three Glue executions: one customer ingestion and two sales quality-gate runs. AWS startup, crawlers and queries take longer than the edited presentation clip. The CloudShell program orchestrates this rehearsal; it is not an installed production scheduling service. Queued Glue runs show WAITING before capacity becomes available. Explicit concurrency rejections are retried for up to 15 minutes. A submission whose outcome is unknown is held for inspection rather than resubmitted automatically.

## Catalog coverage across the four zones

All table counts below are **expected results for the supplied dataset**, to be verified by the new AWS run.

| Athena table | S3 representation | Expected rows |
| --- | --- | ---: |
| `landing_pos` | Unchanged Landing POS CSV, header skipped | 1,051 |
| `raw_pos` | Original CSV, header skipped | 1,051 |
| `raw_customers` | Customer ingestion Parquet | 400 |
| `raw_ecommerce_ndjson` | One JSON object per line, nested items retained | 265 orders |
| `trusted_customers` | Accepted original record JSON plus provenance, in Parquet | 400 |
| `trusted_pos_sales` | Accepted original record JSON plus provenance, in Parquet | 1,048 |
| `trusted_ecommerce_orders` | Accepted original record JSON plus provenance, in Parquet | 226 orders |
| `trusted_sales_model` | Conformed, flattened sales lines, in Parquet | 1,601 |
| `demo_bad_sales` | Separate bad-variant accepted lines, in Parquet | 1,597 |
| `curated_sales` | Accepted sales, dates/decimals, Snappy Parquet, year/month partitions | 1,601 |

`landing_pos` and `raw_pos` deliberately define source fields as strings, including `cust_num`, `store_id`, `transaction_id` and unvalidated measures. This preserves the received values and avoids losing `0000000`. The custom Glue gate performs date/numeric checks and conversion. Crawler schema updates are `LOG`, preserving manually curated definitions; all four schedules recrawl the complete target. The manual definition and a post-crawl Athena identifier query are saved as evidence. The S3-event wait logs progress every 30 seconds, repeats identical Landing uploads at 60/180/360 seconds if Raw is still absent, and stops after ten minutes if no valid copy arrives. Re-upload attempts and hashes are retained in the run state.

The original ecommerce file is a pretty-printed JSON array. It is retained unchanged under Landing and Raw; Athena's table points at the separate NDJSON representation, not that array. NDJSON conversion is run by the rehearsal driver after Lambda ingestion, and is not a second Lambda trigger.

For the three per-source Trusted tables, individual source fields can be queried with `json_extract_scalar(record_json, '$.cust_num')` or the appropriate source key. The conformed `trusted_sales_model` exposes sales fields directly.

## Automated quality gate and zone promotion

The deployed Glue script applies required-field, source-key uniqueness, valid-date/timestamp, known-customer, quantity/price range, nonempty/valid item-array and order-total reconciliation rules. Bad records are written with explicit reasons to Quarantine; accepted records are written to Trusted. A successful Glue job can contain quarantined rows: this is an automated **record** gate. Batch/report checks in the runner then prevent Curated creation if expected reconciliation or controlled-demo checks fail.

| Zone | Promotion rule |
| --- | --- |
| Landing | Preserve received source bytes; no business validation implied |
| Raw | POS/ecommerce retain original bytes; customer CSV is converted to Parquet with explicit string schema |
| Trusted | Only records accepted by the custom rules; retain source filename/record number |
| Quarantine | Rejected original record and reasons; excluded from accepted analytics |
| Curated | Created only from accepted Trusted sales after the runner's reconciliation and demonstration checks pass |

Controlled bad/corrected copies live under `landing/ecommerce/quality-demo/` and the event-created corresponding Raw path. Bad-run outputs are isolated under `quality-demo/bad/`. Corrected outputs use the main `trusted/`, `quarantine/` and `reports/` prefixes. Both variants and both Glue run IDs remain available. No source file in the package is edited. Correction of the introduced demonstration error does not repair the original sample's 3 POS and 39 ecommerce rejected records.

Four schema reconciliations are implemented/documented in the ETL and SQL: differing customer identifier keys/types become strings; POS date formats and ecommerce timestamps are normalized; nested ecommerce orders become sale lines; monetary measures become decimal values in Curated. Ecommerce category reporting additionally uses unambiguous product-name matches to POS categories, with complete sample coverage checked before plotting. Currency and physical units are unspecified in the source, so neither currency conversion nor unit conversion is claimed.

## Capture the result

Success ends with `PASSED`. Local output is `run-evidence/recording01/`; the portable result is `Thornquist_Run_Evidence_recording01.zip` in the package directory. Copies are also saved under the new bucket's `reports/`. Download the ZIP through CloudShell **Actions → Download file**. Open `Thornquist_Clean_Run_Analytics.html` from the extracted evidence on your computer.

The evidence includes the Landing POS count query, Glue run IDs and states, Lambda object hashes, crawler results/schedules, actual Athena execution IDs/SQL/CSVs, the controlled rejection and correction comparison, Curated storage/partition checks, all six business-query results, and the analytics snapshot. The snapshot summarizes revenue by channel/region/category, and calculates a customer loyalty insight from the customer-sales join. It is refreshed by executing new queries, not by opening the file.

Use `DEMO_RUNBOOK.md` to record each stage. A prepared ZIP or local unit test is not evidence of a successful AWS run. The completed `rehearsal01` run establishes the clean-session pipeline outcome; retain its evidence ZIP and the presentation recording together.

## Daily schedules

With `--enable-schedules`, the customer trigger is activated for 07:00 UTC and crawlers for 07:15/07:20/07:25/07:30 UTC. The rehearsal starts their first executions directly so it does not wait for the next day. Configuration/activation is separate from proof of an automatic scheduled execution. These independent timers do not chain the full pipeline or refresh Curated. The clean-run script supplies stage ordering during the demonstration.

Omitting `--enable-schedules` leaves the scheduled definitions inactive. Use the flag when demonstrating an activated schedule. After recording, pause only the newly created rehearsal schedules if no further daily runs are needed:

```bash
python3 clean_lab.py \
  --expected-account 470551642447 \
  --run-label recording01 \
  --pause-schedules \
  --apply
```

This pauses schedules; it does not delete the pipeline, stop already running jobs or alter the earlier project deployment.

## Recovery and scope

Keep `.clean-lab-state/recording01.json`. If CloudShell disconnects, return to the same extracted directory and rerun the **same apply command/options**. Saved Glue run IDs and Athena query IDs are reused rather than submitting duplicates. A definitively rejected concurrent submission can be retried safely; an uncertain response without a run ID requires inspection. An interrupted resource creation with uncertain ownership stops; inspect the stated error and use a fresh label for a new rehearsal. Existing buckets/tables are never adopted or emptied. No cleanup/deletion command is included.

The only existing AWS resources intentionally reused are `LabRole` and the selected Athena workgroup. The runner does not recreate the earlier project's SNS/EventBridge/CloudWatch email monitoring tests, provision a separate analyst identity, deploy analyst IAM/bucket restrictions, change Lake Formation grants or create a CloudTrail trail. The `governance/` files are clearly marked proposed designs and require placeholder replacement and administrator review. The new bucket enforces public-access blocking, default SSE-S3 and an insecure-transport deny for non-service principals; these do not constitute analyst cross-zone isolation.

## Local validation

```bash
python3 -m unittest discover -s tests -v
```

The checks exercise the supplied data through the actual pure-Python Glue validators, confirm bad/corrected order behavior and revenue, reject changed source hashes, and check account/resource/CTAS/promotion safeguards. These tests use no AWS credentials and do not test Spark deployment, service permissions, or real AWS execution.

## AWS references

- Lambda S3 event setup and permission scoping: https://docs.aws.amazon.com/lambda/latest/dg/with-s3-example.html
- Glue job argument precedence: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-arguments.html
- Glue crawler recrawl modes: https://docs.aws.amazon.com/glue/latest/webapi/API_RecrawlPolicy.html
- Athena Open CSV SerDe/header handling: https://docs.aws.amazon.com/athena/latest/ug/csv-serde.html
- Athena newline JSON representation: https://docs.aws.amazon.com/athena/latest/ug/openx-json-serde.html
- Athena CTAS empty destinations and partition columns: https://docs.aws.amazon.com/athena/latest/ug/create-table-as.html
