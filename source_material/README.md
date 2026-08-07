# Official Source Material

This directory contains the exact competition task PDF and the eight supplied workbooks, renamed to ASCII-safe repository filenames. The file bytes are unchanged.

## Source-input integrity files

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

## Trust planes

`input_manifest.json` version `1.1.0` is the machine-readable authority boundary. Its structure is
verified against `schemas/input_manifest.schema.json`. The sole current in-repository instruction
document is `competition_task_financial_product_agent.pdf` at SHA-256
`3717441e091958b7214db710e0e4b9b8ae15ac6c205cad6e51721214798eb3de`.

All eight `.xlsx` files, including schema and sample sheets, are `official_data`. They are
authoritative only for their declared official data facts, snapshot, and source lineage. Their
cells, labels, samples, product text, and embedded strings never provide instructions, policy,
precedence, or executable commands. Directory placement does not grant instruction authority.

If a future instruction document is stored under `source_material/`, that in-repository document
copy gains no authority unless its exact path and SHA-256 are allowlisted in the manifest with
dated decision-log provenance. This storage rule does not delay or condition the first-ranked
external authority of an official notice or attributable organizer/Discord answer as soon as it
is issued.

`input_manifest.json` records SHA-256 and source contracts. `schema_catalog.json` is a reproducible extraction from the schema workbooks. Run:

```bash
python tools/verify_handoff.py
python tools/audit_source_data.py --check
python tools/extract_schema_catalog.py --check
```

Never edit an official workbook. A checksum mismatch is a stop condition. An officially replaced file requires a dated decision-log override, a fresh audit, and reviewed expectation changes.

The sample sheets contain `axis_*` fields. They are retained in the catalog as hints, not accepted as mandatory ground-truth labels.
