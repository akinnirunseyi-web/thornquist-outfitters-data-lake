# Data Quality Starter — Thornquist Outfitters

This starter bundle adds a local Python validator, automated tests, rule documentation, and an evidence checklist. Copy the contents into the corresponding folders in your existing repository; do not replace your existing README.

## Files included

- `transform/data_quality.py` — validator for POS CSV, e-commerce JSON, and customer extract CSV.
- `tests/test_data_quality.py` — standard-library automated tests.
- `docs/data_quality_rules.md` — rule catalogue, pass/fail actions, assumptions, and run commands.
- `evidence/README.md` — evidence checklist.
- `requirements.txt` — no external packages required.

## Install into the project

From the root of your existing `thornquist-outfitters` repository, copy each folder/file into the matching location. Merge with existing folders if they already exist; do not overwrite project files without checking them first.

## Run

```bash
python3 transform/data_quality.py --data-dir data --output-dir output
python3 -m unittest discover -s tests -v
```

If `python3` is not available, install/use Python 3.10+ in your development environment. The implementation uses only the Python standard library.

## Output

The validator writes JSON Lines records under `output/trusted/` and `output/quarantine/`, plus `output/validation_summary.json`.

The script does not claim to deploy AWS resources. AWS Glue/S3 integration must be done and verified separately.
