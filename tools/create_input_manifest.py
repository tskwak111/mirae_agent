#!/usr/bin/env python3
"""Create the immutable official-input manifest for initial handoff/review.

Do not run this to silence a checksum mismatch. A changed source requires an
official update and a decision-log entry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Final, cast

ROOT: Final = Path(__file__).resolve().parents[1]
SOURCE: Final = ROOT / "source_material"
DEFAULT_OUTPUT: Final = SOURCE / "input_manifest.json"

FILE_SPECS: Final = (
    {"path": "competition_task_financial_product_agent.pdf", "kind": "official_task_pdf"},
    {
        "path": "data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx",
        "kind": "data",
        "table_id": "PRBD01N001",
        "sheet_name": "datarows",
        "expected_rows": 42394,
        "expected_columns": 40,
    },
    {
        "path": "data/PRBD01N001_schema.xlsx",
        "kind": "schema",
        "table_id": "PRBD01N001",
        "sheet_names": ["Sheet1_Schema", "Sheet2_Sample"],
        "expected_columns": 40,
    },
    {
        "path": "data/PREF01N001_domestic_etf_20260711_datarows.xlsx",
        "kind": "data",
        "table_id": "PREF01N001",
        "sheet_name": "datarows",
        "expected_rows": 1734,
        "expected_columns": 73,
    },
    {
        "path": "data/PREF01N001_schema.xlsx",
        "kind": "schema",
        "table_id": "PREF01N001",
        "sheet_names": ["Sheet1_Schema", "Sheet2_Sample"],
        "expected_columns": 73,
    },
    {
        "path": "data/PREF02N001_overseas_etf_20260711_datarows.xlsx",
        "kind": "data",
        "table_id": "PREF02N001",
        "sheet_name": "datarows",
        "expected_rows": 5646,
        "expected_columns": 49,
    },
    {
        "path": "data/PREF02N001_schema.xlsx",
        "kind": "schema",
        "table_id": "PREF02N001",
        "sheet_names": ["Sheet1_Schema", "Sheet2_Sample"],
        "expected_columns": 49,
    },
    {
        "path": "data/PRFD01N001_public_funds_20260711_datarows.xlsx",
        "kind": "data",
        "table_id": "PRFD01N001",
        "sheet_name": "datarows",
        "expected_rows": 95619,
        "expected_columns": 45,
    },
    {
        "path": "data/PRFD01N001_schema.xlsx",
        "kind": "schema",
        "table_id": "PRFD01N001",
        "sheet_names": ["Sheet1_Schema", "Sheet2_Sample"],
        "expected_columns": 45,
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest() -> dict[str, Any]:
    files = []
    for spec in FILE_SPECS:
        path = SOURCE / cast(str, spec["path"])
        entry = dict(spec)
        entry["size_bytes"] = path.stat().st_size
        entry["sha256"] = sha256(path)
        files.append(entry)
    return {
        "manifest_version": "1.0.0",
        "competition": "제10회 2026 미래에셋증권 AI Festival — 금융상품 Agent",
        "snapshot_date": "2026-07-11",
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = cast(Path, args.output)
    manifest = build_manifest()
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
