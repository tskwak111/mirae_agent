"""Deterministic fixtures for source-manifest contract tests."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

TABLE_COLUMNS = {
    "PRBD01N001": ("PD_NO", "PD_NM"),
    "PREF01N001": ("pd_itm_no", "pd_nm"),
    "PREF02N001": ("pd_itm_no", "pd_nm"),
    "PRFD01N001": ("itm_no", "itm_nm"),
}


def write_source_contract_fixture(
    base_dir: Path, *, data_payloads: Mapping[str, bytes] | None = None
) -> tuple[Path, Path]:
    """Write an official-shaped manifest and catalog only below ``base_dir``."""
    payloads = {"competition_task.pdf": b"pdf"}
    for table_id in TABLE_COLUMNS:
        payloads[f"data/{table_id}_data.xlsx"] = f"{table_id}-data".encode()
        payloads[f"data/{table_id}_schema.xlsx"] = f"{table_id}-schema".encode()
    if data_payloads is not None:
        data_paths = {f"data/{table_id}_data.xlsx" for table_id in TABLE_COLUMNS}
        unknown_paths = set(data_payloads) - data_paths
        if unknown_paths:
            raise ValueError("data_payloads keys must name fixture data workbooks")
        payloads.update(data_payloads)
    for relative_path, payload in payloads.items():
        destination = base_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    def common(relative_path: str) -> dict[str, object]:
        payload = payloads[relative_path]
        return {
            "path": relative_path,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    files: list[dict[str, object]] = [
        common("competition_task.pdf") | {"kind": "official_task_pdf"}
    ]
    for table_id, headers in TABLE_COLUMNS.items():
        files.extend(
            [
                common(f"data/{table_id}_data.xlsx")
                | {
                    "kind": "data",
                    "table_id": table_id,
                    "sheet_name": "datarows",
                    "expected_rows": 1,
                    "expected_columns": len(headers),
                },
                common(f"data/{table_id}_schema.xlsx")
                | {
                    "kind": "schema",
                    "table_id": table_id,
                    "sheet_names": ["Sheet1_Schema", "Sheet2_Sample"],
                    "expected_columns": len(headers),
                },
            ]
        )

    manifest = {
        "manifest_version": "1.0.0",
        "competition": "FinProof test fixture",
        "snapshot_date": "2026-08-24",
        "files": files,
    }
    catalog = {
        "catalog_version": "1.0.0",
        "snapshot_date": "2026-08-24",
        "tables": {
            table_id: {
                "axis_warning": "test fixture",
                "column_count": len(headers),
                "columns": [
                    {
                        "column_name": header,
                        "column_type": "text",
                        "example": "",
                        "key": "",
                        "name_ko": "",
                        "schema_excel_row": index + 3,
                    }
                    for index, header in enumerate(headers)
                ],
            }
            for table_id, headers in TABLE_COLUMNS.items()
        },
    }
    manifest_path = base_dir / "input_manifest.json"
    catalog_path = base_dir / "schema_catalog.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path, catalog_path
