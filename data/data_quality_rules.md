# Thornquist Outfitters — Data Quality Rules

## Purpose

This document describes the initial local implementation of validation rules used to route source records to `Trusted` or `Quarantine`. The original files in `data/` must remain unchanged. This is a local Python implementation and does not, by itself, deploy or run an AWS Glue job.

## Rule catalogue

| Rule | Applies to | Pass condition | Fail action |
|---|---|---|---|
| DQ01 — Required-field completeness | POS, e-commerce, customer extract | Required fields are present and not blank or a recognized placeholder (`null`, `N/A`, `unknown`, etc.) | Quarantine with field-specific reason |
| DQ02 — Identifier uniqueness | POS transaction IDs, e-commerce order IDs, customer IDs | Identifier is not repeated in the same source extract | Keep the first occurrence; quarantine later duplicate occurrences |
| DQ03 — Date/timestamp validity | POS, e-commerce | POS date parses as `YYYY-MM-DD` or `DD/MM/YYYY`; e-commerce timestamp parses as ISO 8601 | Quarantine invalid date/timestamp |
| DQ04 — Customer referential integrity | POS, e-commerce | Customer ID exists in the valid customer extract | Quarantine unknown customer reference; POS `cust_num=0000000` is an allowed walk-in exception |
| DQ05 — Numeric range | POS quantity/unit price; e-commerce item quantity/unit price | Quantity is numeric and greater than zero; unit price is numeric and greater than or equal to zero | Quarantine with a numeric validation reason |
| DQ06 — E-commerce item structure | E-commerce orders | `items` is a non-empty array; each item is an object with `sku`, `product_name`, `qty`, and `unit_price`; quantity and price meet DQ05 | Quarantine the entire order with item-specific reason(s) |

## Output contract

The validator writes JSON Lines (`.jsonl`) files:

- `output/trusted/customers.jsonl`
- `output/trusted/pos_sales.jsonl`
- `output/trusted/ecommerce_orders.jsonl`
- `output/quarantine/customers.jsonl`
- `output/quarantine/pos_sales.jsonl`
- `output/quarantine/ecommerce_orders.jsonl`
- `output/validation_summary.json`

Trusted entries include source filename, record number, and the original record. Quarantine entries additionally include `rejection_reasons`. If a record violates more than one rule, all detected reasons are recorded.

## Important interpretation decisions

1. A duplicate means the same agreed identifier appears more than once within its source file. The first occurrence is retained and later occurrences are quarantined. Review this policy with the project team if another policy was agreed.
2. POS customer ID `0000000` means walk-in guest and is not checked against the customer extract.
3. POS date parsing supports the two formats documented for the supplied data.
4. Quantity must be greater than zero. Unit price may be zero but cannot be negative; change this if the business has explicitly agreed to stricter price semantics.
5. Customer IDs are compared as trimmed strings to avoid accidental type mismatches between CSV and JSON.
6. Product-name whitespace is not changed in the original data. Any later normalization should be documented as a transformation, not as a source-file edit.
7. A failed order is quarantined as a whole if one of its line items fails validation. This implementation does not flatten `items` into separate trusted rows.

## Local execution

From the project root:

```bash
python3 transform/data_quality.py --data-dir data --output-dir output
python3 -m unittest discover -s tests -v
```

No third-party Python packages are required.

## Correction and reprocessing evidence

For a reprocessing demonstration, preserve the original quarantined example and its rejection reasons. Create a separate corrected copy, correct only the failing field(s), and run the validation again on that copy or through the agreed pipeline. Record both the before and after outcomes in `evidence/`. Never edit the original source files in `data/`.

## AWS integration note

This local validator is a testable starting point. To satisfy an AWS Glue pipeline requirement, the validation logic and output contract still need to be integrated into the project's Glue ETL job(s), with S3 Trusted/Quarantine destinations and job-run evidence verified in the actual AWS environment.
