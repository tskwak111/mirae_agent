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
DATA: Final = SOURCE / "data"
DEFAULT_OUTPUT: Final = SOURCE / "input_manifest.json"

FILE_SPECS: Final = (
    {
        "path": "competition_task_financial_product_agent.pdf",
        "kind": "official_task_pdf",
        "size_bytes": 924413,
        "sha256": "3717441e091958b7214db710e0e4b9b8ae15ac6c205cad6e51721214798eb3de",
    },
    {
        "path": "data/prbd01n001_data.xlsx",
        "kind": "data",
        "table_id": "PRBD01N001",
        "sheet_name": "data",
        "expected_rows": 21882,
        "expected_columns": 58,
    },
    {
        "path": "data/prbd01n001_schema.xlsx",
        "kind": "schema",
        "table_id": "PRBD01N001",
        "sheet_names": ["schema"],
        "expected_columns": 58,
    },
    {
        "path": "data/pref01n001_data.xlsx",
        "kind": "data",
        "table_id": "PREF01N001",
        "sheet_name": "data",
        "expected_rows": 1780,
        "expected_columns": 98,
    },
    {
        "path": "data/pref01n001_schema.xlsx",
        "kind": "schema",
        "table_id": "PREF01N001",
        "sheet_names": ["schema"],
        "expected_columns": 98,
    },
    {
        "path": "data/pref02n001_data.xlsx",
        "kind": "data",
        "table_id": "PREF02N001",
        "sheet_name": "data",
        "expected_rows": 6037,
        "expected_columns": 49,
    },
    {
        "path": "data/pref02n001_schema.xlsx",
        "kind": "schema",
        "table_id": "PREF02N001",
        "sheet_names": ["schema"],
        "expected_columns": 49,
    },
    {
        "path": "data/prfd01n001_data.xlsx",
        "kind": "data",
        "table_id": "PRFD01N001",
        "sheet_name": "data",
        "expected_rows": 23676,
        "expected_columns": 75,
    },
    {
        "path": "data/prfd01n001_schema.xlsx",
        "kind": "schema",
        "table_id": "PRFD01N001",
        "sheet_names": ["schema"],
        "expected_columns": 75,
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(*, data_root: Path = DATA) -> dict[str, Any]:
    if not data_root.is_dir():
        raise FileNotFoundError(data_root)
    files = []
    for spec in FILE_SPECS:
        entry = dict(spec)
        if entry["kind"] != "official_task_pdf":
            path = data_root / Path(cast(str, spec["path"])).name
            entry["size_bytes"] = path.stat().st_size
            entry["sha256"] = sha256(path)
        files.append(entry)
    return {
        "manifest_version": "1.0.0",
        "competition": "제10회 2026 미래에셋증권 AI Festival — 금융상품 Agent",
        "snapshot_date": "2026-08-24",
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DATA)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = cast(
        Path,
        args.output
        or (
            DEFAULT_OUTPUT
            if args.data_root == DATA
            else args.data_root.parent / "input_manifest.json"
        ),
    )
    manifest = build_manifest(data_root=args.data_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
