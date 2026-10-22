# Schema reconciliation and quality gate

The deployed implementation is `transform/glue_sales_etl.py`. It reads Raw customer Parquet, POS CSV and the original ecommerce JSON array. Quality rules run as custom Python validation within AWS Glue, rather than managed Glue Data Quality rulesets.

## Resolved source differences

| Difference | Implemented treatment |
| --- | --- |
| `cust_num` versus `cust_ref` | Trimmed string customer IDs; preserve leading zeros |
| POS ISO and day/month/year dates versus ecommerce timestamps | Normalize POS dates; convert timezone-aware ecommerce timestamps to UTC; Curated exposes a DATE |
| One POS product row versus nested ecommerce items | Expand only accepted orders into item rows; retain order and line IDs |
| CSV text versus JSON numeric measures | Decimal validation and cent rounding; Curated monetary columns DECIMAL(18,2) |
| Store region versus shipping destination | Common reporting region retains source meaning; source-specific fields remain nullable |
| Ecommerce has no category | Leave stored value null; category analysis uses unambiguous POS product-name mapping, with all 553 ecommerce lines matched in the verified sample |
| POS identifiers initially inferred numeric | Catalog manually corrected to string; POS crawler configured to ignore schema changes; post-crawl regression remains to be verified |

## Rules

| Rule | Check | Failure handling |
| --- | --- | --- |
| DQ01 | Required fields and known placeholder values | Quarantine with field-specific reasons |
| DQ02 | Customer, transaction and order IDs unique within the source extract | First occurrence claims the identifier; later duplicates are quarantined; the first can still fail another rule |
| DQ03 | POS date and ecommerce timestamp parse | Quarantine invalid record |
| DQ04 | Customer reference exists in accepted customers | Quarantine; POS walk-in `0000000` is an explicit guest exception |
| DQ05 | Finite quantity >0 and finite unit price >=0 | Quarantine record/order with item-specific reasons |
| DQ06 | Nonempty ecommerce items array and required item fields | Quarantine whole order |
| DQ07 | Order total equals calculated item total to cents | Quarantine whole order |

These rules do not establish cross-batch deduplication. Multiple reasons can apply to one rejected record. Source files remain unchanged. Trusted records retain source metadata; Quarantine JSONL retains original records and rejection reasons. The normalized sales model contains customer enrichment, and Curated excludes first/last names while retaining customer identifiers and segmentation fields.

## Verified reconciliation

400 customers accepted; POS 1,051 read → 1,048 accepted +3 rejected; ecommerce 265 read →226 accepted +39 rejected. Ecommerce reasons include 35 unknown-customer and five duplicate flags, with one overlap. All 226 accepted orders reconciled and yielded 553 lines. Combined accepted sales: 1,601 lines / 320,570.35.

## Recovery demonstration

A separate copy of order 900000 had its first item quantity changed from 1 to -1 and was rejected. Restoring the authoritative original value 1 admitted one order and four reconciled lines to demonstration paths under `quarantine/remediation_demo/`, `trusted/remediation_demo/` and `reports/remediation_demo/`. This did not change production inputs or repair the 42 production rejects. Unknown customer references require authoritative correction evidence.
