# Thornquist Outfitters Data Lake

AWS data engineering project integrating POS sales, ecommerce orders and customer records through S3 Landing, Raw, Trusted and Curated zones. The verified reporting week is **24–30 August 2026**. Sources are synthetic instructor-provided data.

## Results

| Measure | Verified result |
| --- | ---: |
| Customers accepted | 400 |
| POS records accepted / quarantined | 1,048 / 3 |
| Ecommerce orders accepted / quarantined | 226 / 39 |
| Accepted sales lines | 1,601 |
| Total accepted sales | 320,570.35 |
| POS / ecommerce sales | 214,561.78 / 106,008.57 |

Amounts use source monetary units; the dataset supplies no currency code. Rejection reasons overlap for one ecommerce order.

## Start here

- [Technical report (PDF)](docs/Thornquist_Technical_Report.pdf) · [Editable Word report](docs/Thornquist_Technical_Report.docx)
- [Architecture (two-page PDF)](architecture/Thornquist_Architecture.pdf) · [Editable draw.io](architecture/Thornquist_Architecture.drawio)
- [Deployment and reproduction guide](docs/deployment.md)
- [Schema and data quality](docs/schema_and_quality.md)
- [Governance controls and limitations](governance/governance_controls.md)
- [Monitoring and automation](docs/monitoring_and_automation.md)
- [Evidence index](evidence/INDEX.md)

![Deployed data flow](architecture/Thornquist_Architecture_1.svg)

## Repository structure

| Folder | Contents |
| --- | --- |
| `data/` | Three unchanged source datasets |
| `ingestion/` | POS copy, ecommerce Lambda and customer Glue scripts |
| `transform/` | Glue sales ETL with custom quality checks |
| `infrastructure/` | Guarded, preview-first bootstrap for a fresh S3 foundation |
| `queries/` | Curated CTAS, validation and five numbered business questions |
| `analytics/` | Executed notebook, HTML charts and six result CSVs |
| `governance/` | Verified policy snapshots and clearly marked proposed analyst controls |
| `monitoring/` | Read-only test of the deployed Glue failure rule |
| `architecture/` | Diagram PDF, SVGs and editable source |
| `docs/` | Report, deployment guide and focused supporting documentation |
| `tests/` | Local checks of the retained ETL and supplied datasets |
| `evidence/` | Verification index, local test results and captured filter-test text |

## Deployed environment

- Account: `470551642447`; region: `us-east-1`.
- Bucket: `thornquist-data-lake-2026102`; catalog database: `thornquist_outfitters`.
- Lambda: `thornquist-ingest-ecommerce`; Glue jobs: `thornquist-customer-ingestion`, `thornquist-sales-etl`.
- Curated table: `thornquist_outfitters.curated_sales`.
- Existing `LabRole` is reused under AWS Academy restrictions. No credentials are stored here.

POS ingestion is a manual Bash copy. Ecommerce uses an S3 ObjectCreated trigger and preserves the original JSON array. Customer CSV ingestion writes Raw Parquet. The sales ETL validates, joins and flattens records into Trusted Parquet, with rejects and reconciliation reports stored separately. Athena CTAS produces Snappy Parquet partitioned by year and month.

Four crawler schedules and the customer job schedule are configured. They are independent timers; successful scheduled executions and a complete automatic refresh chain have not been demonstrated. Ecommerce NDJSON conversion, the sales job, Curated CTAS and notebook refresh are manual. [Details and test scope](docs/monitoring_and_automation.md).

## Five business questions

| # | Question | SQL | Visualization |
| --- | --- | --- | --- |
| 1 | How do daily POS and ecommerce sales compare? | [Daily](queries/01_daily_sales.sql) | chart_1 |
| 2 | Which regions lead by channel? | [Regions](queries/02_regional_sales.sql) | chart_2 |
| 3 | Which products and categories lead sales? | [Products](queries/03a_top_products.sql), [Categories](queries/03b_category_sales.sql) | chart_3, chart_4 |
| 4 | How do customer loyalty segments differ? | [Loyalty](queries/04_loyalty_sales.sql) | chart_5 |
| 5 | Which stores lead POS sales? | [Stores](queries/05_store_sales.sql) | chart_6 |

[Open the notebook](analytics/Thornquist_Sales_Analytics.ipynb), or download [the HTML dashboard](analytics/Thornquist_Sales_Analytics.html) and open it in a browser. QuickSight access was denied in the lab; this permitted notebook fallback uses exported Athena results and has no live AWS connection. Keep the notebook beside its six CSV files when running it. Category mapping is derived at query time; [coverage and provenance](docs/category_mapping.md).

## Local verification

From the repository root, use Python 3.10 or later:

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
```

These tests exercise pure Python ETL logic and the supplied sample files. They do not run Spark, deploy AWS resources or prove end-to-end alert delivery. Glue runtime dependencies are supplied by AWS and are not installed through this requirements file.

## Team

| Member | Contribution |
| --- | --- |
| Alahi | Foundation design, source data and documentation coordination |
| Justin | Original ingestion, transformation and quality logic |
| Seyi | Deployment adaptation, Athena/Curated analytics, visualization, scheduling, monitoring and integration verification |

Original transformation credit is retained in the adapted script. See [responsibility matrix](docs/team_responsibilities.md).
