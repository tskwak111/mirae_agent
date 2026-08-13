# Source-contract baselines

`expected_source_audit.json` is the frozen, machine-readable baseline reproduced from the eight official workbooks under `source_material/data/`.

## Rules

- Do not edit the baseline merely to make a failing test pass.
- A checksum or count mismatch is a stop condition until an official source update is documented in `docs/10_DECISION_LOG.md`.
- Source-contract tests must preserve workbook, sheet, row, column, raw value, and source-row lineage.
- The malformed public-fund row remains in Bronze/source lineage and is excluded only from normal Silver/Gold result paths through an explicit quality issue.

## Verification

```bash
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```
