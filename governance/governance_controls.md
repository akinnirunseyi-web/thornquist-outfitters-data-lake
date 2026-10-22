# Governance: deployed evidence and proposed design

## 1. Verified observations on 22 October 2026

| Control | Observation | Evidence |
| --- | --- | --- |
| S3 public access | Bucket Block Public Access shown On | Bucket Permissions screenshot |
| Encryption at rest | Default encryption shown SSE-S3; this is a bucket default, not an object-by-object encryption audit | Encryption screenshot |
| Encryption in transit | DenyInsecureTransport policy accepted on project bucket and all objects; direct AWS service principals excluded from that deny | PutBucketPolicy event 20:28:08 UTC, HTTP 204; verified_bucket_policy.json |
| Runtime identity | Glue/Lambda use existing LabRole; role page listed seven attached policies | Deployment verification; deployed job/function configuration |
| IAM inspection restriction | iam:GetPolicy explicitly denied by lab policy | Deployment verification |
| Lake Formation inspection restriction | lakeformation:ListPermissions denied; failed listing does not establish that no grants exist | Deployment verification |
| Customer schedule | Existing daily schedule resumed; user observed Activated, corroborated by StartTrigger at 20:48:02 UTC | Deployment verification and CloudTrail; automatic job execution not yet demonstrated |
| Logs and metrics | Glue run metrics visible and logs used for troubleshooting | Deployment verification and earlier logs |
| Lambda error alarm | thornquist-ecommerce-lambda-errors created; Errors >=1 for one 5-minute period; subsequently OK, actions enabled | Deployment verification; Sum and not-breaching were instructed but final metric/missing-data configuration still needs direct verification |
| Email destination | thornquist-pipeline-alerts SNS subscription reported Confirmed; alarm action points to that topic | Deployment verification; direct SNS test email received |
| Crawler schedules | Customer 07:15, ecommerce NDJSON 07:20, POS 07:25, Trusted sales 07:30 UTC, daily | Customer saved Scheduled shown; other saves confirmed by Seyi; automatic executions not yet demonstrated |
| POS schema protection | Seyi confirmed selecting ignore schema changes before saving POS schedule | Deployment verification workflow; post-crawl identifier-type regression not yet demonstrated |
| Glue job failure rule | thornquist-glue-job-failures Enabled on default bus; both project jobs, FAILED/TIMEOUT | Deployment verification; saved pattern read and tested through AWS API |
| EventBridge publishing permission | SNS policy allows events.amazonaws.com to sns:Publish on the alerts topic | Captured SNS policy |
| Failure event filter | Seven positive/negative test cases passed against the saved rule pattern | CloudShell output; pattern test does not invoke SNS |
| Audit history | CloudTrail Event history records alarm/topic creation, trigger activation and bucket policy change | Deployment verification; not proof of a dedicated trail or S3 object data-event logging |

Screenshots and raw AWS exports are indexed separately under evidence/.

## 2. What is not deployed or not verified

- A distinct analyst identity and production least-privilege roles have not been created. The lab's fixed role is reused; its hidden policies were not reviewed.
- Live cross-zone enforcement for an analyst has not been demonstrated. The saved bucket policy enforces transport only.
- Lake Formation grants, S3 registration and enforcement mode could not be inspected. Do not claim curated-only Lake Formation enforcement.
- Dedicated analyst Athena workgroup/result isolation is proposed; current demonstrated queries used primary.
- CloudTrail Event history is available, but durable trail retention and object-level access auditing were not configured or verified.
- Direct SNS-to-email delivery was tested successfully. Neither the Lambda alarm-to-email path nor an actual Glue failure-to-EventBridge-to-SNS-to-email path has been tested end to end. An OK alarm alone does not establish function health, especially if missing data is treated as not breaching.
- Glue failures/timeouts now have a separate EventBridge rule. Data-quality rejection counts and crawler failures do not have dedicated alerts. Scheduled configuration does not prove successful scheduled execution; see ../docs/monitoring_and_automation.md.

## 3. Least-privilege target

The proposed analyst role is arn:aws:iam::470551642447:role/ThornquistAnalyst. This is a design identifier, not an existing verified role. Do not substitute LabRole: sharing one identity between analyst and pipeline prevents meaningful identity-based separation and can break working jobs.

The analyst IAM policy is deliberately limited to Athena workgroup thornquist-analysts; metadata for curated_sales and its ancestors; Lake Formation GetDataAccess; and query-result access under athena-results/analyst/. GetDataAccess uses Resource '*' because that IAM action is not scoped to a table ARN; Lake Formation grants determine the authorized tables.

Curated source objects are accessed through Lake Formation-vended credentials, not a direct analyst S3 GetObject grant. An administrator must register curated/sales/ with a properly scoped registration role and ensure its access policy permits required S3 reads/listing. That registration role is distinct from the hypothetical analyst and is not provisioned by this package. The bucket's analyst restrictions do not apply to it.

The proposed bucket policy adds explicit denial of the analyst's access to landing/raw/trusted/quarantine/reports, denial of curated mutations, and constrained bucket listing. It grants nothing by itself. It is analyst-specific protection, not a complete organization-wide zone isolation policy. Other identities require their own reviewed policies. No anonymous Allow is added and Block Public Access stays On.

The analyst workgroup must enforce its configured output path athena-results/analyst/, encryption, and a reviewed per-query scan cap. One shared analyst result prefix is suitable for this hypothetical single analyst, not multi-user result confidentiality. Separate result prefixes/workgroups or a stronger result-isolation design are needed for multiple analysts. Console discovery permissions are omitted; this is a scoped API design rather than a full console convenience policy.

## 4. Zone promotion and handling rules

| Zone | Promotion rule and access intent |
| --- | --- |
| Landing | Synthetic files as received; ingestion operators upload/read; analysts have no access |
| Raw | POS CSV and original ecommerce JSON retained; customer ingestion currently produces Parquet, so Raw is not byte-identical for every source |
| Trusted | Custom Python checks inside Glue admit valid records; pipeline writes and stewards review; no analyst grant |
| Quarantine | Rejected record plus reasons retained for review; never used in accepted analytics; no analyst access |
| Curated | Conformed accepted sales written via Athena CTAS as partitioned Parquet; proposed analyst SELECT only |
| Reports | Quality/reconciliation outputs available to engineers and stewards; analyst access not granted in this design |

Production summary: customers 400 accepted; POS 1,048 accepted and 3 rejected; ecommerce 226 accepted and 39 rejected; 1,601 accepted sales lines. Ecommerce reason counts overlap: 35 unknown-customer and 5 duplicate flags across 39 records. Do not add reason counts as unique rejected records.

Correction evidence is a controlled test-copy demonstration: order 900000 with quantity -1 was rejected; restoring its original quantity 1 passed validation/reconciliation and produced four sales lines. It did not repair the 42 production quarantined records. Unknown references require authoritative correction evidence, not invented customer IDs.

Curated excludes customer first and last names, but retains a customer identifier and segmentation fields: it is reduced-detail, not anonymous data. All source data is synthetic as required by the brief.

## 5. Proposed access-policy approval and validation plan

1. Administrator reviews the complete effective policies, trust relationships and lab restrictions; do not remove explicit lab denies.
2. Validate JSON with IAM Access Analyzer policy validation where supported, then test in a separate non-production setup. Local parsing alone is not AWS authorization validation.
3. Provision an approved separate analyst identity and dedicated workgroup; prepare the registration role and LF grants. Inspect IAMAllowedPrincipals/hybrid mode before any changes. Do not revoke permissions blindly.
4. Merge reviewed bucket statements with the current policy; do not overwrite unrelated existing statements. Preserve HTTPS/public-access controls.
5. Positive tests: analyst SELECT on curated_sales succeeds; results are written/read only in its assigned result prefix.
6. Negative tests: analyst cannot read raw/customer files, query raw/trusted tables, inspect quarantine, alter/drop curated metadata, mutate curated objects or query through a different workgroup.
7. Regression tests: Lambda copy, customer ingestion, ETL, catalog and curated refresh remain functional with authorized pipeline identities.
8. SNS delivery and saved-rule filter testing are completed separately (see ../docs/monitoring_and_automation.md). Any subsequent controlled alarm or job-failure test must be labelled honestly and scoped to avoid changing production inputs.
9. Retain sanitized evidence and document residual gaps. Obtain authorized support for blocked requirements rather than bypassing lab permissions.

## 6. References

- Project1_Thornquist Outfitters.pdf, Project requirements and Learner Lab constraints.
- AWS S3 policy condition keys: https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html
- AWS Lake Formation permissions: https://docs.aws.amazon.com/lake-formation/latest/dg/lf-permissions-reference.html
- Athena access to Glue metadata: https://docs.aws.amazon.com/athena/latest/ug/fine-grained-access-to-glue-resources.html

These are proposed designs checked against documentation and local JSON syntax, not deployed/independently security-audited controls.
