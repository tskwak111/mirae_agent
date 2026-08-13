"""Immutable raw-lineage contracts for verified official-source rows."""

from datetime import date
from pathlib import PurePosixPath
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PositiveInt = Annotated[int, Field(gt=0)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def _excel_column_letter(number: int) -> str:
    """Return the uppercase Excel column letters for a one-based column number."""
    letters: list[str] = []
    remaining = number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


class SourceCell(BaseModel):
    """One exact raw worksheet cell and its Excel location."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    column_name: str
    excel_column_number: PositiveInt
    excel_column_letter: str
    raw_value: str
    applicable_date: date | None = None

    @model_validator(mode="after")
    def validate_excel_column_letter(self) -> Self:
        """Ensure the redundant numeric and letter locations agree exactly."""
        if self.excel_column_letter != _excel_column_letter(self.excel_column_number):
            raise ValueError("excel_column_letter must match excel_column_number")
        return self


class SourceRow(BaseModel):
    """One immutable raw source row with complete manifest-relative lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_table: str
    source_file: PurePosixPath
    source_sheet: str
    source_row_number: PositiveInt
    source_checksum: Sha256Hex
    source_snapshot_date: date
    raw_payload: tuple[str, ...]
    cells: tuple[SourceCell, ...]

    @model_validator(mode="after")
    def validate_raw_lineage(self) -> Self:
        """Enforce the raw-cell ordering and source-identity invariants."""
        if self.source_file.is_absolute() or ".." in self.source_file.parts:
            raise ValueError("source_file must be a safe manifest-relative path")
        if tuple(cell.raw_value for cell in self.cells) != self.raw_payload:
            raise ValueError("raw_payload must match cells in header order")
        if tuple(cell.excel_column_number for cell in self.cells) != tuple(
            range(1, len(self.cells) + 1)
        ):
            raise ValueError("cells must use contiguous one-based columns")
        if len({cell.column_name for cell in self.cells}) != len(self.cells):
            raise ValueError("cell column names must be unique")
        return self

    def cell(self, column_name: str) -> SourceCell:
        """Return the source cell for an exact, case-sensitive header name."""
        for cell in self.cells:
            if cell.column_name == column_name:
                return cell
        raise KeyError(column_name)
