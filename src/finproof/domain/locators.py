"""Immutable source-cell locators that preserve official-data lineage."""

from datetime import date
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from finproof.domain.source import SourceRow


class SourceCellLocator(BaseModel):
    """The complete immutable location of one raw source cell."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_table: str
    source_file: PurePosixPath
    source_sheet: str
    source_row_number: int = Field(gt=0)
    source_column_name: str
    source_column_number: int = Field(gt=0)
    source_column_letter: str
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_date: date
    source_applicable_date: date | None

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
