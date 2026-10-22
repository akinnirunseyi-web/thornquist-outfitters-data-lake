# Proposed governance and operations RACI

For team review; responsibility assignments are recommendations, not evidence of completed approvals.

R = Responsible (does the work); A = Accountable (approves/owns outcome); C = Consulted; I = Informed. Each activity has one A.

| Activity | Alahi: platform/documentation | Justin: ingestion/ETL/DQ | Seyi: analytics/scheduling/testing | Authorized lab administrator/instructor |
| --- | --- | --- | --- | --- |
| Zone design and infrastructure documentation | A/R | C | C | I |
| Ingestion and conformed ETL source | C | A/R | C | I |
| DQ rules and quarantine operations | C | A/R | C | I |
| Approve correction evidence for unresolved customer references | C | R | C | A |
| Athena business queries and notebook | C | C | A/R | I |
| Scheduling, monitoring configuration and verification | C | C | A/R | I |
| Governance design files and evidence consolidation | A/R | C | R | C |
| IAM/LF permissions approval and restricted account changes | C | C | R | A |
| End-to-end acceptance and count reconciliation | C | R | A/R | I |
| Architecture update and final report assembly | A/R | C | R | I |
| Budget review and end-of-session checks | C | C | A/R | I |

An instructor/lab administrator is an escalation point for restricted actions, not an assumed business data owner. In a real retailer, an appointed customer-data owner would approve customer-reference corrections and a security owner would approve access. These business roles have not been established in the lab.

## Contribution context

Original agreed division: Alahi owns platform/architecture/documentation; Justin owns ingestion/ETL/DQ; Seyi owns Athena/visualizations/scheduling/final testing. Seyi performed integration and lab-specific adaptations while guided through the deployed build. Preserve Justin's original transformation/validation attribution and Alahi's original architecture contribution. Updated deployment files must reflect actual service choices and verified outputs rather than claiming all proposed architecture elements were deployed.

## Operational handling

- Unknown customer IDs remain quarantined until authoritative mapping is available; do not guess replacements.
- Review duplicate records against their retained counterparts before deciding correction, discard or replay.
- Corrected records must pass the same validation and reconciliation gates before promotion, with an audit link to the rejected original.
- The remediation_demo outputs are illustrative test copies and must remain outside production sales aggregation.
- Record job run IDs, input versions/checksums where available, quality summary, reviewer and correction reason for replay.
- Stop running compute when no longer needed and review schedules for unintended recurring charges; do not delete resources needed for assessment before evidence and reproducibility files are secured.
