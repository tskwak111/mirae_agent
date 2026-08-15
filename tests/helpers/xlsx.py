# mypy: disable-error-code="arg-type,no-untyped-def"
"""Minimal XLSX builders for streaming-reader contract tests."""

import json
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

from finproof.data.source_manifest import (
    SourceFileManifest,
    VerifiedSourceFile,
)
from tests.helpers.source_manifest import write_source_contract_fixture
from tests.helpers.source_rows import (
    BOND_COLUMNS,
    DOMESTIC_LISTED_COLUMNS,
    OVERSEAS_LISTED_COLUMNS,
    PUBLIC_FUND_COLUMNS,
    source_row,
)

MAIN_URI = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_URI = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_URI = "http://schemas.openxmlformats.org/package/2006/relationships"

COMPLETE_BRONZE_COLUMNS = {
    "PRBD01N001": BOND_COLUMNS,
    "PREF01N001": DOMESTIC_LISTED_COLUMNS,
    "PREF02N001": OVERSEAS_LISTED_COLUMNS,
    "PRFD01N001": PUBLIC_FUND_COLUMNS,
}


def _column_letter(number: int) -> str:
    letters: list[str] = []
    remaining = number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def _cell_xml(reference: str, value: str, *, formula: bool) -> str:
    formula_xml = "<f>1+1</f>" if formula else ""
    return (
        f'<c r="{reference}" t="inlineStr">{formula_xml}'
        f'<is><t xml:space="preserve">{escape(value)}</t></is></c>'
    )


def write_xlsx(
    path: Path,
    *,
    sheet_name: str = "datarows",
    rows: tuple[tuple[str | None, ...], ...],
    formulas: frozenset[str] = frozenset(),
    duplicate_cells: frozenset[str] = frozenset(),
) -> None:
    """Write the minimum workbook/rels/worksheet parts needed by the reader."""
    worksheet_rows: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells: list[str] = []
        for column_number, value in enumerate(row, start=1):
            if value is None:
                continue
            reference = f"{_column_letter(column_number)}{row_number}"
            cell = _cell_xml(reference, value, formula=reference in formulas)
            cells.append(cell)
            if reference in duplicate_cells:
                cells.append(cell)
        worksheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    workbook_content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
    )
    worksheet_content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
    )
    content_types = f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="{workbook_content_type}"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="{worksheet_content_type}"/>
</Types>"""
    workbook = f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{MAIN_URI}" xmlns:r="{REL_URI}">
  <sheets><sheet name={quoteattr(sheet_name)} sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{PACKAGE_REL_URI}">
  <Relationship Id="rId1" Type="{REL_URI}/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    worksheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_URI}"><sheetData>{"".join(worksheet_rows)}</sheetData></worksheet>"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def verified_fixture_source(
    base_dir: Path,
    *,
    table_id: str,
    workbook: Path,
    expected_headers: tuple[str, ...],
    expected_rows: int,
) -> VerifiedSourceFile:
    """Verify an official-shaped fixture containing one substituted workbook."""
    relative_workbook = f"data/{table_id}_data.xlsx"
    manifest_path, catalog_path = write_source_contract_fixture(
        base_dir,
        data_payloads={relative_workbook: workbook.read_bytes()},
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    for entry in manifest["files"]:
        if entry.get("table_id") != table_id:
            continue
        if entry["kind"] == "data":
            entry["expected_rows"] = expected_rows
        entry["expected_columns"] = len(expected_headers)

    table = catalog["tables"][table_id]
    table["column_count"] = len(expected_headers)
    table["columns"] = [
        {
            "column_name": header,
            "column_type": "text",
            "example": "",
            "key": "",
            "name_ko": "",
            "schema_excel_row": index + 3,
        }
        for index, header in enumerate(expected_headers)
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    verified = SourceFileManifest.load(manifest_path, catalog_path).verify(base_dir)
    return verified.data_file(table_id)


def write_complete_bronze_repository(repository_root: Path):
    """Write one complete four-workbook canonical-header CP4 repository fixture."""
    from finproof.core.settings import Settings

    source_root = repository_root / "source_material"
    payloads: dict[str, bytes] = {}
    for table_id, columns in COMPLETE_BRONZE_COLUMNS.items():
        workbook = repository_root / f"{table_id}.xlsx"
        value = source_row(table_id)
        write_xlsx(workbook, rows=(columns, value.raw_payload))
        payloads[f"data/{table_id}_data.xlsx"] = workbook.read_bytes()
        workbook.unlink()
    manifest_path, catalog_path = write_source_contract_fixture(
        source_root,
        data_payloads=payloads,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        table_id = entry.get("table_id")
        if table_id not in COMPLETE_BRONZE_COLUMNS:
            continue
        columns = COMPLETE_BRONZE_COLUMNS[table_id]
        entry["expected_columns"] = len(columns)
        if entry["kind"] == "data":
            entry["expected_rows"] = 1
    for table_id, columns in COMPLETE_BRONZE_COLUMNS.items():
        table = catalog["tables"][table_id]
        table["column_count"] = len(columns)
        table["schema_file"] = f"data/{table_id}_schema.xlsx"
        table["columns"] = [
            {
                "column_name": name,
                "column_type": "text",
                "example": "",
                "key": "",
                "name_ko": "",
                "schema_excel_row": number + 2,
            }
            for number, name in enumerate(columns, start=1)
        ]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    config_root = repository_root / "config"
    config_root.mkdir()
    project_root = Path(__file__).resolve().parents[2]
    for name in (
        "artifact_build.yaml",
        "datasets.yaml",
        "quality_rules.yaml",
        "rating_scale.yaml",
        "state_rules.yaml",
    ):
        (config_root / name).write_bytes((project_root / "config" / name).read_bytes())
    schema_root = repository_root / "schemas"
    schema_root.mkdir()
    for name in ("artifact_manifest.schema.json", "quality_issue.schema.json"):
        (schema_root / name).write_bytes(b"{}")
    return Settings(
        repository_root=repository_root,
        source_root=source_root,
        data_dir=source_root / "data",
        artifact_dir=repository_root / "artifacts",
        database_path=repository_root / "artifacts/finproof.duckdb",
        artifact_build_config_path=config_root / "artifact_build.yaml",
        expected_artifact_contract_path=config_root / "expected_phase1_artifacts.json",
    )
