# Thornquist Outfitters — Source Schema Conflicts and Reconciliation

## Purpose

This document records measured conflicts in the instructor-provided
POS, e-commerce, and customer datasets and proposes ETL resolutions.

The original files in `data/` must remain unchanged. All corrections
and normalizations must occur in the ETL layer.

## 1. Profiling summary

| Source or check | Measured result |
|---|---:|
| POS source rows | 1,051 |
| E-commerce orders | 265 |
| Customer source rows | 400 |
| Duplicate POS transaction occurrences beyond first occurrence | 3 |
| Duplicate e-commerce order occurrences beyond first occurrence | 5 |
| Duplicate customer IDs | 0 |
| POS walk-in guest references (`0000000`) | 185 |
| POS unknown customer references excluding walk-ins | 0 |
| E-commerce unknown customer references | 35 |
| POS dates in `YYYY-MM-DD` format | 1,018 |
| POS dates in `DD/MM/YYYY` format | 33 |
| POS product names with surrounding whitespace or NBSP | 13 |
| E-commerce nested line items | 654 |
| E-commerce line items without an explicit category field | 654 |
| E-commerce orders with line sums differing from `order_total` | 0 |

Counts describe the original input profiling run. Duplicate and customer
validation failures may overlap within the same order. The counts above
must not be added to infer a unique rejected-order count.

## 2. Identified conflicts and proposed resolutions

### C01 — Customer key naming and representation

- POS/customer extract key: `cust_num`.
- E-commerce customer key: `cust_ref`.
- CSV identifiers are strings; JSON identifiers may be numeric.
- Measured issue: 35 e-commerce orders reference customer IDs not found
  in the customer extract. POS has 185 walk-in guest references.

**Proposed resolution:** normalize comparable customer IDs to trimmed
strings without converting them to integers or losing leading zeros.
Join `cust_num` to normalized `cust_ref`. Quarantine unknown customer
references according to DQ04. Treat POS `0000000` as an explicit guest
exception, never as a real customer match.

### C02 — Inconsistent POS date formats

- 1,018 POS rows use `YYYY-MM-DD`.
- 33 POS rows use `DD/MM/YYYY`.
- E-commerce uses ISO 8601 timestamps, with `Z` indicating UTC in the
  observed example.

**Proposed resolution:** parse both approved POS date formats and
standardize the target timestamp/date type. Preserve UTC semantics for
e-commerce timestamps. Do not infer a local timezone for POS dates
without an agreed business rule.

### C03 — Different record grain and nested e-commerce items

- POS contains transaction-level product rows.
- E-commerce contains order objects with nested `items` arrays.
- The source has 654 nested e-commerce line items across 265 orders.

**Proposed resolution:** use one target row per sold item. Retain source
system and source transaction/order ID. Expand each e-commerce item into
a separate row only after the parent order passes validation.

### C04 — Duplicate business identifiers

- POS has 3 duplicate transaction occurrences beyond the first.
- E-commerce has 5 duplicate order occurrences beyond the first.
- Customer IDs have no duplicates in the measured extract.

**Proposed resolution:** apply the existing DQ02 policy: retain the first
occurrence in deterministic source order and quarantine later duplicate
occurrences. Keep source system in the unified line identifier to avoid
cross-source key collisions.

### C05 — Product-name whitespace

- 13 POS product names contain surrounding whitespace or a non-breaking
  space (NBSP).

**Proposed resolution:** normalize surrounding whitespace and replace
NBSP characters in the transformed output. Preserve the original source
record in lineage or quarantine output for auditability.

### C06 — Missing product category in e-commerce line items

- The observed e-commerce item schema contains `sku`, `product_name`,
  `qty`, and `unit_price`.
- All 654 profiled items lack an explicit `category` field.
- POS rows have an explicit `category` field.

**Proposed resolution:** do not infer category from product names or SKU
prefixes without an approved mapping. Agree with the team whether the
target uses null, `UNKNOWN`, or an authoritative product lookup.

### C07 — Numeric representation and standardized measures

- POS quantity and unit price arrive as CSV text.
- E-commerce quantity and unit price are JSON numeric values.

**Proposed resolution:** cast quantity to an integer where valid and use
a fixed-precision decimal type for monetary values. Define
`line_amount = quantity * unit_price`. Quarantine invalid numeric values
according to DQ05.

### C08 — Different source fields and incomplete product identity

- POS provides store, region, payment method, category, and transaction
  fields but no explicit SKU in the supplied header.
- E-commerce provides channel, shipping region, SKU, and order total.

**Proposed resolution:** define a common target schema with source-specific
fields nullable where they do not apply. Do not invent POS SKUs or treat
store region and shipping region as semantically identical without
approval.

## 3. Monetary reconciliation

For every profiled e-commerce order, the sum of
`qty * unit_price` across its items matched the declared `order_total`
to two decimal places. No mismatches were found in the profiling run.

The ETL should retain `order_total` at order grain for reconciliation
and must not repeat it as an additive measure on every flattened line.
The line-level analytical measure is `line_amount`.

## 4. Proposed common sales model

Candidate fields for team review:

- `sale_line_id`
- `source_system`
- `transaction_id`
- `customer_id`
- `sale_timestamp`
- `sku`
- `product_name`
- `category`
- `quantity`
- `unit_price`
- `line_amount`
- `region`
- `payment_method`
- `channel`
- `source_file`

This is a proposed logical schema, not a finalized team contract.
Confirm field names, nullable fields, category policy, guest handling,
and timestamp semantics with the project lead before deployment.

## 5. Validation and evidence

The local data-quality validator currently writes JSONL Trusted and
Quarantine outputs plus a validation summary. Its integration into AWS
Glue, its S3 destinations, and successful Glue job runs must be verified
separately. Do not describe local test results as proof of Glue deployment.

Profiling was performed against the original files without modifying
them. Re-run profiling and tests after ETL changes and preserve relevant
evidence under `evidence/`.
