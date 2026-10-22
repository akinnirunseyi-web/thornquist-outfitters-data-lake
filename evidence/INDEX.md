# Evidence index

Verification date: 22 October 2026. Deployment evidence refers to account `470551642447` in `us-east-1`, bucket `thornquist-data-lake-2026102`. The uploaded repository contained local starter results and a source-upload screenshot from an earlier environment; those have been excluded from this redeployment evidence set.

## Included records

| File/location | Meaning |
| --- | --- |
| `event_filter_test_results.txt` | Transcription of seven passing AWS CloudShell pattern tests supplied by Seyi; filtering only |
| `local_test_results.txt` | Local test run of the cleaned source tree; not AWS deployment evidence |
| `../analytics/*.csv` | Five original Athena exports plus a transcribed category result |
| `../analytics/source_manifest.json` | Provenance/checksums of analytical exports |
| `../data/source_manifest.json` | Original input byte counts and SHA-256 values |
| `../governance/verified_bucket_policy.json` | Deployed HTTPS-only bucket policy, corroborated by a successful PutBucketPolicy event |
| `../governance/verified_eventbridge_publish_statement.json` | Observed SNS service publishing statement; not the complete topic policy |

## Screenshots and AWS exports to add

The following checklist identifies verified activities, not files already present. Add the actual saved screenshots/exports to `evidence/screenshots/` or `evidence/exports/` and replace the pending entries with links. Do not create placeholder screenshots or claim a proposed control was deployed.

| Area | Evidence to retain | Repository attachment |
| --- | --- | --- |
| Foundation | Current bucket zones, original datasets, SSE-S3 and Block Public Access | Pending upload |
| POS | Landing-to-Raw Bash output and destination object | Pending upload |
| Ecommerce | Lambda configuration, S3 trigger and actual upload-triggered log with 265 orders | Pending upload |
| Customers | Successful Glue run, 400-row output, active daily trigger | Pending upload |
| Catalog | Raw/Trusted crawler success, actual table schemas/counts and four saved schedules | Pending upload |
| ETL and quality | Successful job, actual `sales_model_summary.json`, representative rejects | Pending upload |
| Recovery | Original/corrected test-copy outcomes and correction summary; production unchanged | Pending upload |
| Curated | CTAS success, DATE/DECIMAL schema, partitioned Parquet and count/total checks | Pending upload |
| Analytics | Five business-question results/charts, category coverage and QuickSight denial | Pending upload |
| Governance | Deployed HTTPS policy and successful audit event; IAM/LF inspection restrictions | Pending upload |
| Monitoring | Alarm OK/actions, SNS confirmation, enabled Glue rule/target and received direct test email | Pending upload |

No successful scheduled execution, post-crawl POS type regression or complete failure-to-email transition has been evidenced. Existing screenshots should be selected by their contents; earlier working screenshot numbers were inconsistent. The required execution recording and demo link must also be added before submission.
