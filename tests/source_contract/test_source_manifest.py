"""Tests for fail-closed official manifest and schema-catalog loading."""

import json
import os
from collections.abc import Callable
from datetime import date
from errno import EACCES, ELOOP
from pathlib import Path, PurePosixPath
from typing import Any, cast

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


def test_manifest_rejects_injected_schema_catalog_field(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        manifest["schema_catalog"] = {}

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is SourceErrorCode.MANIFEST_INVALID


def test_manifest_rejects_coercible_numeric_scalar(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        _manifest_files(manifest)[1]["expected_rows"] = "1"

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


@pytest.mark.parametrize(
    ("field", "unsupported_version", "expected_code"),
    [
        ("manifest_version", "999.0", SourceErrorCode.MANIFEST_INVALID),
        ("catalog_version", "unsupported", SourceErrorCode.CATALOG_INVALID),
    ],
)
def test_manifest_and_catalog_reject_unsupported_versions(
    tmp_path: Path,
    field: str,
    unsupported_version: str,
    expected_code: SourceErrorCode,
) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        target = manifest if field == "manifest_version" else catalog
        target[field] = unsupported_version

    with pytest.raises(SourceContractError) as raised:
        _load_mutated(tmp_path, mutate)

    assert raised.value.code is expected_code


def test_manifest_load_accepts_paths_for_verification_boundary(tmp_path: Path) -> None:
    def mutate(manifest: dict[str, object], catalog: dict[str, object]) -> None:
        del catalog
        _manifest_files(manifest)[1]["path"] = "../outside.xlsx"

    manifest = _load_mutated(tmp_path, mutate)

    assert manifest.data_entry("PRBD01N001").path == PurePosixPath("../outside.xlsx")


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


def test_official_manifest_verifies_all_files() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )

    verified = manifest.verify(ROOT / "source_material")

    bond = verified.data_file("PRBD01N001")
    assert bond.manifest_relative_path == PurePosixPath(
        "data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx"
    )
    assert bond.snapshot_date == date(2026, 7, 11)
    assert bond.sha256 == "728f44a567a986d21cf843d711c6c4dfa1a24d05b39c7da0541b981b57ecccf8"
    assert bond.expected_headers[:3] == ("PD_NO", "PD_EXG_MKT", "PD_NM")


def test_verify_rejects_missing_file(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    (tmp_path / "data/PRBD01N001_data.xlsx").unlink()
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.FILE_MISSING


def test_verify_rejects_size_mismatch(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    target = tmp_path / "data/PRBD01N001_data.xlsx"
    target.write_bytes(target.read_bytes() + b"x")
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.SIZE_MISMATCH


def test_verify_rejects_checksum_mismatch(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    target = tmp_path / "data/PRBD01N001_data.xlsx"
    target.write_bytes(b"x" * target.stat().st_size)
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.CHECKSUM_MISMATCH


def test_verify_rejects_directory_instead_of_file(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    target = tmp_path / "data/PRBD01N001_data.xlsx"
    target.unlink()
    target.mkdir()
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.FILE_TYPE_INVALID


def test_verify_rejects_symlink_instead_of_file(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    target = tmp_path / "data/PRBD01N001_data.xlsx"
    external = tmp_path / "external.xlsx"
    external.write_bytes(b"external")
    target.unlink()
    try:
        target.symlink_to(external)
    except OSError as error:
        pytest.skip(f"platform refused test symlink creation: {error}")
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.FILE_TYPE_INVALID


def test_verify_rejects_symlinked_parent_directory(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    data_dir = tmp_path / "data"
    real_data_dir = tmp_path / "real_data"
    data_dir.rename(real_data_dir)
    try:
        data_dir.symlink_to(real_data_dir, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"platform refused test symlink creation: {error}")
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.FILE_TYPE_INVALID
    assert str(tmp_path) not in str(raised.value)


def test_verify_rejects_path_escape_before_hashing_without_absolute_path_leak(
    tmp_path: Path,
) -> None:
    manifest_path, catalog_path, manifest_payload, catalog = _load_payloads(tmp_path)
    _manifest_files(manifest_payload)[1]["path"] = "../outside.xlsx"
    _write_payloads(manifest_path, catalog_path, manifest_payload, catalog)
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.PATH_ESCAPE
    assert "../outside.xlsx" in str(raised.value)
    assert str(tmp_path) not in str(raised.value)


def test_verify_rejects_absolute_manifest_path_without_path_leak(tmp_path: Path) -> None:
    manifest_path, catalog_path, manifest_payload, catalog = _load_payloads(tmp_path)
    _manifest_files(manifest_payload)[1]["path"] = "/outside.xlsx"
    _write_payloads(manifest_path, catalog_path, manifest_payload, catalog)
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.PATH_ESCAPE
    assert "/outside.xlsx" not in str(raised.value)
    assert str(tmp_path) not in str(raised.value)


def test_verify_is_all_or_nothing_and_does_not_cache_failure(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    final_schema = tmp_path / "data/PRFD01N001_schema.xlsx"
    final_schema.write_bytes(final_schema.read_bytes() + b"x")
    manifest = SourceFileManifest.load(manifest_path, catalog_path)
    before = manifest.__dict__.copy()

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.SIZE_MISMATCH
    assert manifest.__dict__ == before


@pytest.mark.parametrize("error_number", [EACCES, ELOOP])
def test_verify_converts_resolution_os_error_to_safe_contract_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_number: int
) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    def deny_resolution(path: Path, *, strict: bool = False) -> Path:
        del strict
        raise OSError(error_number, "resolution denied", path)

    monkeypatch.setattr(Path, "resolve", deny_resolution)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.FILE_TYPE_INVALID
    assert str(tmp_path) not in str(raised.value)


def test_verify_converts_stat_os_error_to_safe_contract_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    manifest = SourceFileManifest.load(manifest_path, catalog_path)
    target = (tmp_path / "data/PRBD01N001_data.xlsx").resolve()
    original_stat = Path.stat
    target_stat_calls = 0

    def deny_target_stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        nonlocal target_stat_calls
        if path == target and follow_symlinks:
            target_stat_calls += 1
            if target_stat_calls == 2:
                raise PermissionError(13, "permission denied", path)
        return original_stat(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", deny_target_stat)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert target_stat_calls == 2
    assert raised.value.code is SourceErrorCode.FILE_TYPE_INVALID
    assert str(tmp_path) not in str(raised.value)


def test_verify_converts_hash_open_os_error_to_safe_contract_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    manifest = SourceFileManifest.load(manifest_path, catalog_path)
    target = (tmp_path / "data/PRBD01N001_data.xlsx").resolve()
    original_open = cast(Any, Path.open)

    def deny_target_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == target:
            raise PermissionError(13, "permission denied", path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_target_open)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.FILE_TYPE_INVALID
    assert str(tmp_path) not in str(raised.value)
