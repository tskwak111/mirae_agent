"""Immutable source-cell locators that preserve official-data lineage."""

from datetime import date
from pathlib import PurePosixPath
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from finproof.domain.source import SourceRow

NonEmptyText = Annotated[str, StringConstraints(min_length=1)]


def _excel_column_letter(number: int) -> str:
    """Return uppercase Excel column letters for a one-based column number."""
    letters: list[str] = []
    remaining = number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


class SourceCellLocator(BaseModel):
    """The complete immutable location of one raw source cell."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_table: NonEmptyText
    source_file: PurePosixPath
    source_sheet: NonEmptyText
    source_row_number: int = Field(gt=0)
    source_column_name: NonEmptyText
    source_column_number: int = Field(gt=0)
    source_column_letter: NonEmptyText
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_date: date
    source_applicable_date: date | None

    @model_validator(mode="after")
    def validate_source_lineage(self) -> Self:
        """Reject path and column-location values that cannot name one raw cell."""
        if self.source_file.is_absolute() or ".." in self.source_file.parts:
            raise ValueError("source_file must be a safe manifest-relative path")
        if self.source_column_letter != _excel_column_letter(self.source_column_number):
            raise ValueError("source_column_letter must match source_column_number")
        return self

    @classmethod
    def from_row(cls, row: SourceRow, column_name: str) -> "SourceCellLocator":
        """Copy immutable row and exact-cell lineage without caller overrides."""
        cell = row.cell(column_name)
        return cls(
            source_table=row.source_table,
            source_file=row.source_file,
            source_sheet=row.source_sheet,
            source_row_number=row.source_row_number,
            source_column_name=cell.column_name,
            source_column_number=cell.excel_column_number,
            source_column_letter=cell.excel_column_letter,
            source_checksum=row.source_checksum,
            source_snapshot_date=row.source_snapshot_date,
            source_applicable_date=cell.applicable_date,
        )
