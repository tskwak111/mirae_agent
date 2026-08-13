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
    "PRBD01N001": "PRBD01N001_schema.xlsx",
    "PREF01N001": "PREF01N001_schema.xlsx",
    "PREF02N001": "PREF02N001_schema.xlsx",
    "PRFD01N001": "PRFD01N001_schema.xlsx",
}


def padded(values: tuple[str, ...], length: int) -> tuple[str, ...]:
    return values + ("",) * max(0, length - len(values))


def extract_table(table_id: str, file_name: str) -> dict[str, Any]:
    path = DATA / file_name
    schema_rows = list(iter_sheet_rows(path, "Sheet1_Schema"))
    header_index = next(
        index
        for index, row in enumerate(schema_rows)
        if row.values and row.values[0].strip() == "컬럼명"
    )
    columns: list[dict[str, str | int]] = []
    for row in schema_rows[header_index + 1 :]:
        values = padded(row.values, 5)
        column_name = values[0].strip()
        if not column_name:
            continue
        columns.append(
            {
                "column_name": column_name,
                "key": values[1].strip(),
                "column_type": values[2].strip(),
                "name_ko": values[3].strip(),
                "example": values[4].strip(),
                "schema_excel_row": row.excel_row_number,
            }
        )

    sample_rows = list(iter_sheet_rows(path, "Sheet2_Sample"))
    total_text = next(
        (
            row.values[0]
            for row in sample_rows
            if row.values and row.values[0].startswith("Total Row:")
        ),
        "",
    )
    sample_header: tuple[str, ...] = ()
    sample_values: tuple[str, ...] = ()
    for index, row in enumerate(sample_rows):
        if row.values and row.values[0].startswith("Total Row:"):
            for next_row in sample_rows[index + 1 :]:
                if next_row.values and any(value.strip() for value in next_row.values):
                    sample_header = next_row.values
                    break
            if sample_header:
                header_position = sample_rows.index(next_row)
                for value_row in sample_rows[header_position + 1 :]:
                    if value_row.values and any(value.strip() for value in value_row.values):
                        sample_values = value_row.values
                        break
            break

    sample = dict(zip(sample_header, padded(sample_values, len(sample_header)), strict=True))
    return {
        "table_id": table_id,
        "schema_file": file_name,
        "source_snapshot_label": schema_rows[0].values[0]
        if schema_rows and schema_rows[0].values
        else "",
        "total_row_label": total_text,
        "column_count": len(columns),
        "columns": columns,
        "sample": sample,
        "sample_axis_columns": sorted(key for key in sample if key.startswith("axis_")),
        "axis_warning": (
            "Sample axis_* fields are reference hints, not mandatory official ground-truth labels."
        ),
    }


def build_catalog() -> dict[str, Any]:
    return {
        "catalog_version": "1.0.0",
        "snapshot_date": "2026-07-11",
        "tables": {
            table_id: extract_table(table_id, file_name) for table_id, file_name in FILES.items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    output = cast(Path, args.output)

    catalog = build_catalog()
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
