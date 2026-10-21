# Evidence checklist

Place screenshots, command output, and small sanitized examples here after running the validator.

Recommended evidence:
1. `01-source-files.png` — source filenames in `data/`, showing the supplied originals remain in place.
2. `02-tests.txt` — output from `python3 -m unittest discover -s tests -v`.
3. `03-validation-summary.json` — copy of the generated `output/validation_summary.json`.
4. `04-quarantine-examples.jsonl` — a small sample showing `rejection_reasons` and the original record.
5. `05-trusted-examples.jsonl` — a small sample of accepted records.
6. `06-reprocessing.txt` — original rejected example, the corrected copy, and the validation result after correction.
7. `07-glue-run.png` — only if/when the validation is integrated and run in AWS Glue.

Do not write expected results as if they were actual results. Capture evidence only after the corresponding command or job has run successfully. Avoid including credentials, access keys, or other secrets in screenshots.
