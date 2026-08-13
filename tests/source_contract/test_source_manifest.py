"""Tests for fail-closed official manifest and schema-catalog loading."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from finproof.core.errors import SourceContractError, SourceErrorCode
from finproof.data.source_manifest import OFFICIAL_TABLE_IDS, SourceFileManifest
from tests.helpers.source_manifest import write_source_contract_fixture

ROOT = Path(__file__).resolve().parents[2]


def _load_payloads(tmp_path: Path) -> tuple[Path, Path, dict[str, object], dict[str, object]]:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    return manifest_path, catalog_path, manifest, catalog


def _write_payloads(
    manifest_path: Path,
    catalog_path: Path,
    manifest: dict[str, object],
    catalog: dict[str, object],
) -> None:
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")


def _load_mutated(
    tmp_path: Path, mutate: Callable[[dict[str, object], dict[str, object]], None]
) -> SourceFileManifest:
    manifest_path, catalog_path, manifest, catalog = _load_payloads(tmp_path)
    mutate(manifest, catalog)
    _write_payloads(manifest_path, catalog_path, manifest, catalog)
    return SourceFileManifest.load(manifest_path, catalog_path)


def _manifest_files(manifest: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], manifest["files"])


def _catalog_table(catalog: dict[str, object], table_id: str) -> dict[str, object]:
    tables = cast(dict[str, dict[str, object]], catalog["tables"])
    return tables[table_id]


def _catalog_columns(catalog: dict[str, object], table_id: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], _catalog_table(catalog, table_id)["columns"])


def test_official_manifest_and_catalog_load_with_exact_tables() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    assert tuple(entry.table_id for entry in manifest.data_files) == OFFICIAL_TABLE_IDS
    assert manifest.data_entry("PRBD01N001").expected_rows == 42_394
    assert manifest.expected_headers("PRBD01N001")[0] == "PD_NO"


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        manifest["unexpected"] = True

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.MANIFEST_INVALID


def test_catalog_rejects_unknown_fields(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del manifest
        catalog["unexpected"] = True

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.CATALOG_INVALID


def test_manifest_rejects_snapshot_mismatch(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        manifest["snapshot_date"] = "2026-07-10"

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.SNAPSHOT_MISMATCH


def test_catalog_rejects_snapshot_mismatch(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del manifest
        catalog["snapshot_date"] = "2026-07-10"

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.SNAPSHOT_MISMATCH


@pytest.mark.parametrize("kind", ["data", "schema"])
def test_manifest_rejects_duplicate_table_entries(tmp_path: Path, kind: str) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        entries = [entry for entry in _manifest_files(manifest) if entry["kind"] == kind]
        entries[1]["table_id"] = entries[0]["table_id"]

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.DUPLICATE_TABLE


@pytest.mark.parametrize("kind", ["data", "schema"])
def test_manifest_rejects_missing_table_entries(tmp_path: Path, kind: str) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        manifest["files"] = [
            entry
            for entry in _manifest_files(manifest)
            if not (entry["kind"] == kind and entry["table_id"] == "PREF02N001")
        ]

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.MANIFEST_INVALID


@pytest.mark.parametrize("pdf_count", [0, 2])
def test_manifest_requires_exactly_one_official_task_pdf(tmp_path: Path, pdf_count: int) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        files = _manifest_files(manifest)
        pdf = next(entry for entry in files if entry["kind"] == "official_task_pdf")
        filtered_files = [entry for entry in files if entry["kind"] != "official_task_pdf"]
        if pdf_count == 2:
            filtered_files.extend([pdf, pdf])
        manifest["files"] = filtered_files

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.MANIFEST_INVALID


def test_manifest_rejects_catalog_column_count_disagreement(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del manifest
        _catalog_table(catalog, "PRBD01N001")["column_count"] = 3

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.COLUMN_COUNT_MISMATCH


@pytest.mark.parametrize(
    ("header", "expected_code"),
    [("", SourceErrorCode.BLANK_HEADER), ("PD_NO", SourceErrorCode.DUPLICATE_HEADER)],
)
def test_catalog_rejects_blank_or_duplicate_headers(
    tmp_path: Path, header: str, expected_code: SourceErrorCode
) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del manifest
        _catalog_columns(catalog, "PRBD01N001")[1]["column_name"] = header

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is expected_code
