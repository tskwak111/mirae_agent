"""Contract tests for immutable official-source row lineage."""

from datetime import date
from pathlib import PurePosixPath

import pytest
from pydantic import ValidationError

from finproof.domain.source import SourceCell, SourceRow


def _cells() -> tuple[SourceCell, ...]:
    return (
        SourceCell(
            column_name="PD_NO",
            excel_column_number=1,
            excel_column_letter="A",
            raw_value="00123",
        ),
        SourceCell(
            column_name="PD_NM",
            excel_column_number=2,
            excel_column_letter="B",
            raw_value="  채권 ",
        ),
    )


def _row() -> SourceRow:
    cells = _cells()
    return SourceRow(
        source_table="PRBD01N001",
        source_file=PurePosixPath("data/bonds.xlsx"),
        source_sheet="datarows",
        source_row_number=2,
        source_checksum="a" * 64,
        source_snapshot_date=date(2026, 7, 11),
        raw_payload=("00123", "  채권 "),
        cells=cells,
    )


def test_source_row_preserves_exact_values_and_lineage() -> None:
    """Raw source values and their manifest-relative locator remain exact."""
    row = _row()

    assert row.raw_payload == ("00123", "  채권 ")
    assert row.cell("PD_NO").raw_value == "00123"
    assert row.cell("PD_NO").applicable_date is None
    assert row.source_file == PurePosixPath("data/bonds.xlsx")
    assert row.source_snapshot_date == date(2026, 7, 11)


def test_source_row_cell_lookup_is_exact_and_case_sensitive() -> None:
    """A caller cannot retrieve a different header through case normalization."""
    row = _row()

    with pytest.raises(KeyError, match="pd_no"):
        row.cell("pd_no")


def test_source_row_rejects_payload_cell_disagreement() -> None:
    """Payload and cells cannot silently point to different raw values."""
    row = _row()

    with pytest.raises(ValidationError, match="raw_payload"):
        SourceRow.model_validate(row.model_dump() | {"raw_payload": ("different", "  채권 ")})


def test_source_models_are_frozen() -> None:
    """Trusted raw lineage cannot be mutated after construction."""
    row = _row()

    with pytest.raises(ValidationError):
        row.source_row_number = 3


@pytest.mark.parametrize(
    ("cells", "message"),
    [
        (
            (
                SourceCell(
                    column_name="PD_NO",
                    excel_column_number=1,
                    excel_column_letter="A",
                    raw_value="00123",
                ),
                SourceCell(
                    column_name="PD_NO",
                    excel_column_number=2,
                    excel_column_letter="B",
                    raw_value="  채권 ",
                ),
            ),
            "unique",
        ),
        (
            (
                SourceCell(
                    column_name="PD_NO",
                    excel_column_number=1,
                    excel_column_letter="A",
                    raw_value="00123",
                ),
                SourceCell(
                    column_name="PD_NM",
                    excel_column_number=3,
                    excel_column_letter="C",
                    raw_value="  채권 ",
                ),
            ),
            "contiguous",
        ),
    ],
)
def test_source_row_rejects_invalid_cell_layout(
    cells: tuple[SourceCell, ...], message: str
) -> None:
    """Headers must have unique names in contiguous one-based Excel columns."""
    with pytest.raises(ValidationError, match=message):
        SourceRow(
            source_table="PRBD01N001",
            source_file=PurePosixPath("data/bonds.xlsx"),
            source_sheet="datarows",
            source_row_number=2,
            source_checksum="a" * 64,
            source_snapshot_date=date(2026, 7, 11),
            raw_payload=("00123", "  채권 "),
            cells=cells,
        )


def test_source_cell_rejects_incorrect_excel_column_letter() -> None:
    """A column's written Excel letter must agree with its numeric locator."""
    with pytest.raises(ValidationError, match="excel_column_letter"):
        SourceCell(
            column_name="PD_NM",
            excel_column_number=2,
            excel_column_letter="C",
            raw_value="  채권 ",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_file", PurePosixPath("/data/bonds.xlsx"), "safe manifest-relative"),
        ("source_checksum", "A" * 64, "pattern"),
    ],
)
def test_source_row_rejects_unsafe_or_invalid_source_identity(
    field: str, value: PurePosixPath | str, message: str
) -> None:
    """Rows reject unsafe file identities and non-canonical source checksums."""
    with pytest.raises(ValidationError, match=message):
        SourceRow.model_validate(_row().model_dump() | {field: value})
