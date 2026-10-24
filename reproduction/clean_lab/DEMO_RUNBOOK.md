# Recording the clean-session proof

The professor's requirement is: **automated quality gate demonstrably rejecting bad records; Curated table; full pipeline run end to end from a clean Learner Lab session; included in the demo.**

Complete the AWS rehearsal before recording the final clips. All three people should show stages from the same clean run label. Preserve the same bucket/database names and job/query IDs when cutting waiting time. Previously saved screenshots and local test results do not replace fresh execution evidence.

Version 1.1 runs from `thornquist_clean_lab_v1_1`. Start the recording from a fresh Learner Lab session and use a fresh label, such as `recording01`. Keep the actual run log/IDs from the recording; resuming a completed rehearsal reuses prior executions and does not create a fresh end-to-end run.

## Clip 1 — Alahi: foundation and ingestion, about 75 seconds

1. Show a fresh Learner Lab/CloudShell session, account/region, new run label and the preview plan. Starting a new session alone does not prove resources were rebuilt; show the new namespace and creation stages.
2. Begin the apply command. Show the new S3 bucket and Landing/Raw/Trusted/Curated prefixes as populated by the run.
3. Show unchanged source uploads and the scripted POS copy. Show the actual Lambda-triggered Raw object and SHA metadata; the driver never directly invokes Lambda or writes the ecommerce Raw objects.
4. Show successful customer ingestion and its job run ID, plus the activated daily trigger if schedules were enabled.
5. In Athena show the Raw count query result: customers 400, POS 1,051 and ecommerce NDJSON 265. Mention that NDJSON is the query representation; the source JSON array is retained.

Waiting time can be cut. Retain visible stage names/run IDs so the flow remains traceable.

## Clip 2 — Justin: automated rejection and correction, about 150 seconds

1. Show the controlled bad copy: order `900000`, first item `qty=-1`. The original source still has `qty=1`.
2. Show the **actual Glue sales job's bad-run ID and SUCCEEDED state**. Its report records 225 accepted/40 quarantined ecommerce orders; the combined accepted sales model has 1,597 lines. Job success means the gate ran, not that every record passed.
3. Open the bad-run S3 quarantine JSONL and find order `900000`, reason `DQ05_ITEM_1_INVALID_QUANTITY`. Show the corresponding record is absent from the bad Trusted model.
4. Show the corrected copy (`qty=1`, bytes matching the supplied original), the second actual Glue run ID and the corrected report: 226 accepted/39 quarantined ecommerce orders, POS 1,048 accepted/3 rejected, customers 400 accepted, combined 1,601 sales lines.
5. Show `quality_gate_comparison`: **bad=0 lines, corrected=4 lines** for order `900000`. Show four Trusted Athena counts. Preserve the saved query ID.
6. Explain briefly: required fields, uniqueness, valid dates, customer references, quantity/price checks and order reconciliation determine quarantine versus promotion. The original 42 rejected records remain quarantined; this controlled correction is separate.

## Clip 3 — Seyi: Curated, business output and boundaries, about 120 seconds

1. Show the new Curated CTAS execution succeeding after the quality/report checks.
2. Show Curated totals: **1,601 lines, 320,570.35 source monetary units, August 24–30, 2026**. Show `sale_year=2026/sale_month=08` and Parquet storage metadata. Currency is not specified in the source.
3. Show the fresh analytics snapshot with its run label and six query IDs. Cover revenue by channel, region, category, products and stores, then one actual loyalty-segment insight produced by joining customers to sales.
4. Show the evidence ZIP/run manifest result `PASSED`. Briefly distinguish enabled daily schedules from a demonstrated automatic run. Analyst IAM/Lake Formation restrictions remain proposed design artifacts.

The earlier email monitoring demonstrations remain separately evidenced: simulated CloudWatch ALARM-to-SNS-to-email; an actual controlled customer Glue failure-to-EventBridge-to-SNS-to-email. Those tests do not themselves demonstrate row-level quality rejection and are not recreated by this package.

## Presentation timing

Keep the existing eight-minute allocation: Alahi two minutes, Justin three minutes, Seyi three minutes, plus two minutes for questions. Introduce each stage live, then play that person's narrated recording. Update deck claims to the newly captured evidence after the rehearsal succeeds. Do not narrate all slides first and then play all clips as a separate block.

## Evidence to retain

| Requirement | Evidence in the new run |
| --- | --- |
| Clean reproduction | Fresh session, new namespace, creation log, run manifest |
| Three ingestion mechanisms | POS copy entry, event-created Lambda object/hash, customer Glue run ID and schedule configuration |
| Queryable Raw | `raw_table_counts.csv` and `.execution.json`; leading-zero query |
| Queryable Trusted | `trusted_table_counts.csv` and `.execution.json` |
| Automated reject/correct | Both Glue run records, both quality reports, quarantine record, `quality_gate_comparison.csv`/query ID |
| Curated table | CTAS execution, `curated_verification.csv`, partitions and storage proof |
| Business analysis | Six fresh query CSVs/IDs, category coverage and analytics snapshot |

The evidence ZIP is supplemental; the recording should visibly show these results in AWS, not only read a checklist.
