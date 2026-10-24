# Governance access RACI and zone visibility

This access design accompanies `proposed_analyst_iam_policy.json`, `proposed_bucket_policy.json` and `lake_formation_permissions.md`. R means responsible for handling the data; A means accountable for approving access and corrections; C means consulted; I means informed. Access shown for the analyst is the documented target, subject to administrator approval and deployment in an account that allows a separate role.

| Zone or decision | Ingestion and ETL operator | Data steward | Analyst | Authorized administrator |
| --- | --- | --- | --- | --- |
| Landing source files | R: upload/read | C: source definitions | No access | A: approve access |
| Raw ingested data | R: ingest/read | C: inspect discrepancies | No access | A: approve access |
| Trusted accepted records | R: validate/write | A: approve correction rules | No access | C: review grants |
| Quarantine and quality reports | R: record/reprocess approved corrections | A: review rejects and corrections | No access | C: review grants |
| Curated sales | R: publish/refresh | C: approve definitions | R: read only | A: approve analyst grant |
| IAM, bucket and Lake Formation grants | C: identify required service access | C: approve business need | I: receive authorized access | A/R: review and apply controls |

The analyst target is SELECT and DESCRIBE on `thornquist_outfitters.curated_sales`, without Landing, Raw, Trusted or Quarantine access. The proposed IAM and S3 policies limit query execution and object access; the Lake Formation list names Curated-only catalog permissions. The live lab reused `LabRole`, enforced HTTPS at bucket level, and denied creation of `ThornquistAnalyst` and Lake Formation permission inspection. These facts do not turn the proposed analyst grants into deployed permissions.
