# Official Source Material

This directory contains the exact competition task PDF and the eight supplied workbooks, renamed to ASCII-safe repository filenames. The file bytes are unchanged.

## Source-of-truth files

```text
competition_task_financial_product_agent.pdf

data/prbd01n001_data.xlsx
data/prbd01n001_schema.xlsx
data/pref01n001_data.xlsx
data/pref01n001_schema.xlsx
data/pref02n001_data.xlsx
data/pref02n001_schema.xlsx
data/prfd01n001_data.xlsx
data/prfd01n001_schema.xlsx
```

`input_manifest.json` records SHA-256 and source contracts. `schema_catalog.json` is a reproducible extraction from the schema workbooks. Run:

```bash
python tools/verify_handoff.py
python tools/audit_source_data.py --check
python tools/extract_schema_catalog.py --check
```

The active distribution date is 2026-08-24. Domestic/public coverage is through
2026-08-22 and overseas coverage is through 2026-08-23 Korea time. Never edit an
official workbook; publish only a complete candidate that passes checksum, schema,
header, independent-audit, and rollback verification.
