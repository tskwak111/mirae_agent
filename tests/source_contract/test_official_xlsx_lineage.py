"""Acceptance evidence for complete lineage through official XLSX workbooks."""

from collections import Counter
from pathlib import Path

import pytest
from tools.xlsx_stream import iter_table_dicts

from finproof.data.source_manifest import SourceFileManifest, VerifiedSourceFile
from finproof.data.xlsx_stream import iter_xlsx_rows

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROWS = {
    "PRBD01N001": 42_394,
    "PREF01N001": 1_734,
    "PREF02N001": 5_646,
    "PRFD01N001": 95_619,
}

pytestmark = [pytest.mark.source_contract, pytest.mark.slow]


def test_official_workbooks_stream_with_complete_lineage() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")
    observed: Counter[str] = Counter()

    for table_id, expected_rows in EXPECTED_ROWS.items():
        source = verified.data_file(table_id)
        for row in iter_xlsx_rows(source):
            observed[table_id] += 1
            assert row.source_table == table_id
            assert row.source_file == source.manifest_relative_path
            assert row.source_sheet == source.sheet_name
            assert row.source_checksum == source.sha256
            assert row.source_snapshot_date == source.snapshot_date
            assert len(row.cells) == source.expected_columns
            assert row.raw_payload == tuple(cell.raw_value for cell in row.cells)
        assert observed[table_id] == expected_rows

    assert sum(observed.values()) == 145_393


def test_official_first_bond_row_preserves_exact_values() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    source = manifest.verify(ROOT / "source_material").data_file("PRBD01N001")
    row = next(iter_xlsx_rows(source))

    assert row.source_row_number == 2
    assert row.cell("PD_NO").raw_value == "KR101501DA16"
    assert row.cell("PD_NM").raw_value == "국민주택1종채권 20-01"


def _selected_rows(source: VerifiedSourceFile) -> dict[int, dict[str, str]]:
    wanted = {2, source.expected_rows // 2 + 2, source.expected_rows + 1}
    selected = {
        row.source_row_number: {cell.column_name: cell.raw_value for cell in row.cells}
        for row in iter_xlsx_rows(source)
        if row.source_row_number in wanted
    }
    assert set(selected) == wanted
    return selected


def _bootstrap_selected_rows(source: VerifiedSourceFile) -> dict[int, dict[str, str]]:
    wanted = {2, source.expected_rows // 2 + 2, source.expected_rows + 1}
    selected = {
        excel_row: raw_values
        for excel_row, raw_values in iter_table_dicts(
            source.verified_absolute_path, source.sheet_name
        )
        if excel_row in wanted
    }
    assert set(selected) == wanted
    return selected


def test_official_selected_rows_match_independent_bootstrap_reader() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")

    for table_id in EXPECTED_ROWS:
        source = verified.data_file(table_id)
        assert _selected_rows(source) == _bootstrap_selected_rows(source)
