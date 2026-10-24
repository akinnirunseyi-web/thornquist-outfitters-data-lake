# Monitoring and automation verification

Updated 23 October 2026 from AWS screenshots and pasted CloudShell output. These checks were performed in the deployed Learner Lab environment.

## Daily schedules (UTC)

| Resource | Time | Verification |
| --- | --- | --- |
| thornquist-customer-ingestion-daily job trigger | 07:00 | Run `jr_4d3cb3e1439b61f099dc644469422d22a6ced6c7537045b7ab34a6a40a891b8a` succeeded after automatic start at 07:00:03 UTC on 23 October. Later restarted and confirmed `ACTIVATED` |
| thornquist-raw-customers-crawler | 07:15 | Saved Schedule tab showed Scheduled, Daily, 07:15 |
| thornquist-raw-ecommerce-crawler | 07:20 | Target raw/ecommerce_ndjson/ verified; saved configuration captured |
| thornquist-raw-pos-crawler | 07:25 | Schema-update behavior saved as ignore changes; post-crawl table schema captured |
| thornquist-trusted-sales-crawler | 07:30 | Daily 07:30 shown in editor; saved schedule captured |

These are independent time-based schedules, not success-dependent orchestration. The customer crawler has a 15-minute nominal offset after ingestion starts; it does not wait for ingestion success. The 23 October customer job run proves this one scheduled trigger executed successfully; it does not prove scheduled sales ETL, Curated refresh or notebook refresh. Lab availability can affect later scheduled execution.

The POS crawler's schema policy preserves the manually corrected string identifier columns instead of automatically replacing the schema. The saved post-crawl table screenshot shows `transaction_id`, `store_id` and `cust_num` as strings. Future schema changes require review.

Ecommerce Lambda ingestion remains S3-event driven and copies the original JSON array. The NDJSON conversion remains manual; scheduling its crawler does not automate conversion. The sales ETL and Curated CTAS refresh remain manually initiated. Notebook CSV refresh is manual. These schedules do not establish an automatic end-to-end refresh chain.

## Alerts and tested behavior

- Existing Lambda alarm: thornquist-ecommerce-lambda-errors, Errors Sum >= 1 for one 5-minute period, missing data treated as not breaching. The saved alarm was OK with actions enabled, and its notification action targets thornquist-pipeline-alerts.
- New EventBridge rule: thornquist-glue-job-failures, Enabled on the default event bus in us-east-1. It matches Glue Job State Change events for thornquist-customer-ingestion and thornquist-sales-etl with state FAILED or TIMEOUT.
- Target configured as SNS topic thornquist-pipeline-alerts. Execution-role creation was disabled; the console added an SNS topic-policy statement permitting events.amazonaws.com to sns:Publish. That statement was verified in the user-pasted policy. It contains no rule-specific condition; do not describe it as authorization scoped exclusively to this rule.
- Confirmed SNS subscription: a direct message with subject 'Thornquist pipeline alert test' was published and received. Controlled alarm and Glue failure tests subsequently exercised both configured notification paths.
- The saved deployed EventPattern was read through describe_rule and tested with test_event_pattern. Seven cases passed, as recorded below. The repository checker now confirms the signed-in account and that the rule is enabled before repeating these read-only checks. For a different account containing the same rule, pass `--expected-account ACCOUNT_ID`. These tests match event JSON without publishing events or invoking targets.

| Job | State | Expected match | Recorded result |
| --- | --- | --- | --- |
| thornquist-customer-ingestion | FAILED | true | PASS |
| thornquist-customer-ingestion | TIMEOUT | true | PASS |
| thornquist-customer-ingestion | SUCCEEDED | false | PASS |
| thornquist-sales-etl | FAILED | true | PASS |
| thornquist-sales-etl | TIMEOUT | true | PASS |
| thornquist-sales-etl | SUCCEEDED | false | PASS |
| unrelated-job | FAILED | false | PASS |

The first test attempt failed because the sample timestamp format was rejected. Repeating the test with a UTC timestamp in YYYY-MM-DDTHH:MM:SSZ format produced the seven passing results. No rule change was needed.

### Controlled delivery tests on 23 October

- **Alarm to email:** `aws cloudwatch set-alarm-state` set `thornquist-ecommerce-lambda-errors` to `ALARM` with the reason “Controlled Thornquist alarm-to-email notification test.” The configured SNS alarm action delivered an email, recorded in the evidence screenshot. This tests the alarm action and downstream delivery for a forced transition; it does not show an actual Lambda error generated the metric.
- **Glue failure to email:** Customer ingestion run `jr_37406547be22c09f7013fff8615e8c1ead464eb98f8734007dd1ee36df94bc88` was started with a deliberately nonexistent CSV path under `monitoring-tests/`. Glue reported `FAILED` with `RESOURCE_NOT_FOUND_ERROR` at 02:37:34 UTC. The EventBridge/SNS notification email was received. The normal source path and job defaults were not changed for this test.

## Scope of scheduled and alert tests

The forced ALARM test proved CloudWatch-to-SNS email delivery, and the deliberately failed Glue run proved Glue-to-EventBridge-to-SNS email delivery. We did not inject a Lambda execution error. The scheduled customer job succeeded at 07:00 UTC; the independent crawler timers and manual sales ETL/CTAS do not constitute a daily automatic Curated refresh. No separate alert was configured for data-quality rejects or crawler failures. The email screenshots contain personal subscription details and should be reviewed before publication in a public repository.

## References

- https://docs.aws.amazon.com/glue/latest/dg/Update-crawler-schedule.html
- https://docs.aws.amazon.com/glue/latest/dg/crawler-schema-changes-prevent.html
- https://docs.aws.amazon.com/glue/latest/dg/automating-awsglue-with-cloudwatch-events.html
- https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-resource-based.html
- https://docs.aws.amazon.com/boto3/latest/reference/services/events/client/test_event_pattern.html
