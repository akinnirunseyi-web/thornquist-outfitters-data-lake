# Governance scope for the clean reproduction

The runner creates a private bucket with all four S3 Block Public Access controls, default SSE-S3 encryption, BucketOwnerEnforced ownership, and a policy denying insecure transport to non-service principals. Existing LabRole and Athena workgroup settings are reused rather than changed.

The accompanying analyst IAM, bucket and Lake Formation designs are **proposed, not deployed or verified**. Replace `__ACCOUNT__`, `__BUCKET__` and `__DATABASE__` before administrative review. The proposed IAM policy also refers to a separate `thornquist-analysts` workgroup, which this pipeline runner does not create.

The earlier lab denied IAM policy inspection and Lake Formation permission listing. The new package makes no claim that a separate analyst identity exists or that Curated-only analyst enforcement is active. Public-access blocking and HTTPS requirements do not restrict an authorized analyst's cross-zone reads.

The IAM/Lake Formation design intends to grant SELECT/DESCRIBE only on Curated, permit scoped query-result access, and withhold Raw/Trusted/Quarantine access. Enforcing that design requires an approved separate identity, appropriately scoped registered data-access role, review of broad IAMAllowedPrincipals grants/hybrid mode, and both positive Curated and negative Raw/Trusted access tests. Do not apply proposed analyst restrictions to the pipeline's LabRole.

No policy or grant is installed automatically from this directory. No CloudTrail trail or object-level audit is created. Previously verified monitoring emails belong to the original deployment; this isolated pipeline package does not reproduce that monitoring setup.
