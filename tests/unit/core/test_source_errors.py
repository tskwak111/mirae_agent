"""Contract tests for safe official-source errors."""

from pathlib import Path, PurePosixPath

import pytest

from finproof.core.errors import SourceContractError, SourceErrorCode

EXPECTED_CODES = {
    "manifest_invalid",
    "catalog_invalid",
    "path_escape",
    "file_missing",
    "file_type_invalid",
    "size_mismatch",
    "checksum_mismatch",
    "snapshot_mismatch",
    "duplicate_table",
    "missing_sheet",
    "column_count_mismatch",
    "header_mismatch",
    "blank_header",
    "duplicate_header",
    "duplicate_cell",
    "row_wider_than_header",
    "row_count_mismatch",
    "unsupported_formula",
    "malformed_workbook",
}


def test_source_contract_error_has_stable_safe_context() -> None:
    """A manifest-relative error exposes a stable, safe contract context."""
    error = SourceContractError(
        SourceErrorCode.CHECKSUM_MISMATCH,
        "SHA-256 does not match the official manifest",
        source_file=PurePosixPath("data/source.xlsx"),
        table_id="PRBD01N001",
    )

    assert error.code is SourceErrorCode.CHECKSUM_MISMATCH
    assert error.source_file == PurePosixPath("data/source.xlsx")
    assert error.table_id == "PRBD01N001"
    assert str(error) == (
        "checksum_mismatch: data/source.xlsx [PRBD01N001]: "
        "SHA-256 does not match the official manifest"
    )
    assert "/Users/" not in str(error)


def test_source_contract_error_rejects_absolute_path_context() -> None:
    """Absolute filesystem locations never become user-facing error context."""
    with pytest.raises(ValueError, match="manifest-relative"):
        SourceContractError(
            SourceErrorCode.FILE_MISSING,
            "official input is missing",
            source_file=PurePosixPath("/private/source.xlsx"),
        )


def test_source_contract_error_rejects_path_context() -> None:
    """A filesystem Path cannot accidentally render an absolute local location."""
    with pytest.raises(TypeError, match="PurePosixPath"):
        SourceContractError(
            SourceErrorCode.FILE_MISSING,
            "official input is missing",
            source_file=Path("data/source.xlsx"),  # type: ignore[arg-type]
        )


def test_source_error_codes_are_stable() -> None:
    """Every approved failure category remains available to fail closed."""
    assert {code.value for code in SourceErrorCode} == EXPECTED_CODES
