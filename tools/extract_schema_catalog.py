#!/usr/bin/env python3
"""Extract a compact machine-readable catalog from the four schema workbooks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

if TYPE_CHECKING:
    from tools.xlsx_stream import iter_sheet_rows
elif __package__:
    from .xlsx_stream import iter_sheet_rows
else:
    from xlsx_stream import iter_sheet_rows

ROOT: Final = Path(__file__).resolve().parents[1]
DATA: Final = ROOT / "source_material" / "data"
DEFAULT_OUTPUT: Final = ROOT / "source_material" / "schema_catalog.json"

FILES: Final = {
    "PRBD01N001": "prbd01n001_schema.xlsx",
    "PREF01N001": "pref01n001_schema.xlsx",
    "PREF02N001": "pref02n001_schema.xlsx",
    "PRFD01N001": "prfd01n001_schema.xlsx",
}

SCHEMA_HEADER: Final = ("순번", "컬럼명", "데이터타입", "Nullable", "컬럼코멘트")


def padded(values: tuple[str, ...], length: int) -> tuple[str, ...]:
    return values + ("",) * max(0, length - len(values))


def extract_table(table_id: str, file_name: str, *, schema_root: Path = DATA) -> dict[str, Any]:
    path = schema_root / file_name
    schema_rows = list(iter_sheet_rows(path, "schema"))
    if not schema_rows or schema_rows[0].values != SCHEMA_HEADER:
        raise ValueError(f"schema header differs for {table_id}")
    columns: list[dict[str, str | int]] = []
    for expected_ordinal, row in enumerate(schema_rows[1:], start=1):
        values = padded(row.values, 5)
        if values[0].strip() != str(expected_ordinal):
            raise ValueError(f"schema ordinal differs for {table_id}")
        column_name = values[1].strip()
        if not column_name:
            raise ValueError(f"schema column is blank for {table_id}")
        columns.append(
            {
                "column_name": column_name,
                "column_type": values[2].strip(),
                "nullable": values[3].strip(),
                "column_comment": values[4].strip(),
                "key": "",
                "name_ko": "",
                "example": "",
                "schema_excel_row": row.excel_row_number,
            }
        )
    return {
        "table_id": table_id,
        "schema_file": file_name,
        "source_snapshot_label": "2026-08-24",
        "total_row_label": "",
        "column_count": len(columns),
        "columns": columns,
        "sample": {},
        "sample_axis_columns": [],
        "axis_warning": "Schema columns are authoritative; source values retain field dates.",
    }


def build_catalog(*, schema_root: Path = DATA) -> dict[str, Any]:
    if not schema_root.is_dir():
        raise FileNotFoundError(schema_root)
    return {
        "catalog_version": "1.0.0",
        "snapshot_date": "2026-08-24",
        "tables": {
            table_id: extract_table(table_id, file_name, schema_root=schema_root)
            for table_id, file_name in FILES.items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-root", type=Path, default=DATA)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    output = cast(
        Path,
        args.output
        or (
            DEFAULT_OUTPUT
            if args.schema_root == DATA
            else args.schema_root.parent / "schema_catalog.json"
        ),
    )

    catalog = build_catalog(schema_root=args.schema_root)
    rendered = json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not output.is_file():
            print(f"Schema catalog is missing: {output}")
            return 2
        if output.read_text(encoding="utf-8") != rendered:
            print(f"Schema catalog differs from source: {output}")
            return 1
        column_count = sum(table["column_count"] for table in catalog["tables"].values())
        print(f"Schema catalog PASS: {column_count} columns")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
