# Monitoring and automation verification

Updated 22 October 2026 from AWS screenshots, user confirmations and pasted CloudShell output. These checks were performed in the deployed Learner Lab environment.

## Daily schedules (UTC)

| Resource | Time | Verification |
| --- | --- | --- |
| thornquist-customer-ingestion-daily job trigger | 07:00 | Activated shown earlier; StartTrigger audit event recorded |
| thornquist-raw-customers-crawler | 07:15 | Saved Schedule tab showed Scheduled, Daily, 07:15 |
| thornquist-raw-ecommerce-crawler | 07:20 | Target raw/ecommerce_ndjson/ verified; save confirmed by user |
| thornquist-raw-pos-crawler | 07:25 | User confirmed schema-update behavior changed to ignore changes, schedule saved |
| thornquist-trusted-sales-crawler | 07:30 | Daily 07:30 shown in editor; user confirmed save and evidence step |

These are independent time-based schedules, not success-dependent orchestration. The customer crawler has a 15-minute nominal offset after ingestion starts; it does not wait for ingestion success. No successful automatically scheduled execution has yet been demonstrated. Lab availability can affect scheduled execution.

The POS crawler's schema policy preserves the manually corrected string identifier columns instead of automatically replacing the schema. Future schema changes require review. A post-crawl regression check of transaction_id, store_id and cust_num is still pending.

Ecommerce Lambda ingestion remains S3-event driven and copies the original JSON array. The NDJSON conversion remains manual; scheduling its crawler does not automate conversion. The sales ETL and Curated CTAS refresh remain manually initiated. Notebook CSV refresh is manual. These schedules do not establish an automatic end-to-end refresh chain.

## Alerts and tested behavior

- Existing Lambda alarm: thornquist-ecommerce-lambda-errors, Errors >= 1 for one 5-minute period; OK and Actions enabled shown. Its notification action targets thornquist-pipeline-alerts. Final Sum/missing-data settings still need direct verification.
- New EventBridge rule: thornquist-glue-job-failures, Enabled on the default event bus in us-east-1. It matches Glue Job State Change events for thornquist-customer-ingestion and thornquist-sales-etl with state FAILED or TIMEOUT.
- Target configured as SNS topic thornquist-pipeline-alerts. Execution-role creation was disabled; the console added an SNS topic-policy statement permitting events.amazonaws.com to sns:Publish. That statement was verified in the user-pasted policy. It contains no rule-specific condition; do not describe it as authorization scoped exclusively to this rule.
- Confirmed SNS subscription: a direct message with subject 'Thornquist pipeline alert test' was published and the user confirmed receipt. This verifies SNS-to-email delivery only.
- The saved deployed EventPattern was read through describe_rule and tested with test_event_pattern. Seven cases passed, as recorded below. These tests match event JSON without publishing events or invoking targets.

| Job | State | Expected match | User-observed result |
| --- | --- | --- | --- |
| thornquist-customer-ingestion | FAILED | true | PASS |
| thornquist-customer-ingestion | TIMEOUT | true | PASS |
| thornquist-customer-ingestion | SUCCEEDED | false | PASS |
| thornquist-sales-etl | FAILED | true | PASS |
| thornquist-sales-etl | TIMEOUT | true | PASS |
| thornquist-sales-etl | SUCCEEDED | false | PASS |
| unrelated-job | FAILED | false | PASS |

The first test attempt failed because the sample timestamp format was rejected. Repeating the test with a UTC timestamp in YYYY-MM-DDTHH:MM:SSZ format produced the seven passing results. No rule change was needed.

## Remaining verification limits

No real Glue failure-to-email or Lambda alarm-to-email transition was exercised. No dedicated data-quality-rejection or crawler-failure alert was configured. Pattern tests plus direct SNS delivery establish two separately tested components, not an end-to-end alert delivery test. Preserve this distinction in the report and demo.

## References

- https://docs.aws.amazon.com/glue/latest/dg/Update-crawler-schedule.html
- https://docs.aws.amazon.com/glue/latest/dg/crawler-schema-changes-prevent.html
- https://docs.aws.amazon.com/glue/latest/dg/automating-awsglue-with-cloudwatch-events.html
- https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-resource-based.html
- https://docs.aws.amazon.com/boto3/latest/reference/services/events/client/test_event_pattern.html
