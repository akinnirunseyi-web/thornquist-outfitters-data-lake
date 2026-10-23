# Athena Governance, Security and Access Control

## 1. Purpose

This document describes the security controls relevant to querying the
Thornquist Outfitters data lake with Amazon Athena. It distinguishes
verified project settings from recommended controls that still require
deployment or validation.

## 2. Verified project configuration

The following settings were observed during project work:

- AWS Region: us-east-1.
- Glue Data Catalog database: thornquist_outfitters.
- Athena workgroup: primary.
- Athena engine: version 3 (AUTO).
- Query results are written to the S3 athena-results/ prefix.
- The data lake bucket uses SSE-S3 (AES256) default encryption.
- S3 Block Public Access settings were enabled when checked.
- The trusted sales_model table is stored in Parquet format.
- The sales_model table contains sales and customer-related attributes.

These observations do not establish that every IAM permission or
resource policy has been reviewed.

## 3. Recommended least-privilege access

Create separate IAM roles or policies for administrators, ETL jobs,
and analytics users. Do not grant broad administrative permissions
to analysts merely to run Athena queries.

An analyst role generally needs only the actions required to:

- Start and inspect Athena queries and retrieve their results.
- Read the relevant Glue database, table, and partition metadata.
- Read the approved trusted or curated S3 data locations.
- Write Athena query results to the designated results prefix.

Depending on the workflow, relevant actions may include:

- athena:StartQueryExecution
- athena:GetQueryExecution
- athena:GetQueryResults
- athena:GetWorkGroup
- glue:GetDatabase
- glue:GetTable
- glue:GetPartitions
- s3:GetObject on approved data prefixes
- s3:ListBucket restricted to approved prefixes
- s3:PutObject on the Athena results prefix

These are examples for policy design, not confirmation that a
corresponding IAM policy has already been deployed. Validate the
minimum required actions against the actual workflow. Restrict access
to specific resources and prefixes wherever supported.

## 4. Data protection

Recommended controls:

1. Keep S3 Block Public Access enabled.
2. Keep default encryption enabled for data and query results.
3. Restrict access to landing, raw, trusted, curated, quarantine, and
   Athena results prefixes according to job responsibilities.
4. Do not place credentials, access keys, or sensitive identifiers in
   source code, screenshots, or Git commits.
5. Review who can read quarantined records, which may contain invalid
   source data.
6. Consider S3 versioning and lifecycle policies based on recovery,
   retention, and cost requirements.
7. Use AWS CloudTrail and appropriate monitoring to review access and
   administrative activity.

SSE-S3 and Block Public Access do not replace IAM least privilege.

## 5. Athena query-result controls

- Configure a controlled S3 location for Athena query results.
- Restrict read and write access to that location.
- Avoid storing unnecessary sensitive information in query results.
- Apply an appropriate retention or lifecycle policy after the team's
  retention requirements are established.
- Review Athena workgroup settings for enforced output location,
  encryption, and query limits before production use.

The current workflow supplies the output location when submitting
queries. Enforcement of that location at the workgroup level has not
been verified.

## 6. Governance limitations and follow-up

The following items require verification before they can be described
as implemented controls:

- IAM policies and role assignments.
- Bucket policy and prefix-level permissions.
- Lake Formation permissions, if Lake Formation is used.
- Athena workgroup-enforced result location and encryption.
- CloudTrail coverage and alerting.
- S3 versioning and lifecycle configuration.
- Retention requirements and data classification.

## 7. Review checklist

- [ ] Confirm analyst and ETL IAM roles.
- [ ] Test that analysts cannot access unauthorized prefixes.
- [ ] Verify encryption and Block Public Access settings.
- [ ] Review Athena workgroup result configuration.
- [ ] Confirm query-result retention.
- [ ] Review logging and monitoring.
- [ ] Document the approved retention and access requirements.
