# Official Source Material

This directory contains the exact competition task PDF and the eight supplied workbooks, renamed to ASCII-safe repository filenames. The file bytes are unchanged.

## Source-of-truth files

```text
competition_task_financial_product_agent.pdf

data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx
data/PRBD01N001_schema.xlsx
data/PREF01N001_domestic_etf_20260711_datarows.xlsx
data/PREF01N001_schema.xlsx
data/PREF02N001_overseas_etf_20260711_datarows.xlsx
data/PREF02N001_schema.xlsx
data/PRFD01N001_public_funds_20260711_datarows.xlsx
data/PRFD01N001_schema.xlsx
```

`input_manifest.json` records SHA-256 and source contracts. `schema_catalog.json` is a reproducible extraction from the schema workbooks. Run:

```bash
python tools/verify_handoff.py
python tools/audit_source_data.py --check
python tools/extract_schema_catalog.py --check
```

Never edit an official workbook. A checksum mismatch is a stop condition. An officially replaced file requires a dated decision-log override, a fresh audit, and reviewed expectation changes.

The sample sheets contain `axis_*` fields. They are retained in the catalog as hints, not accepted as mandatory ground-truth labels.
