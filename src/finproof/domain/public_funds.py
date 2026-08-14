"""Immutable public-fund domain contracts."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from finproof.domain.locators import SourceCellLocator
from finproof.domain.values import NormalizedValue


class FundItemValue[ValueT](BaseModel):
    """One representative item value with every equivalent source-cell locator."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    representative: NormalizedValue[ValueT]
    equivalent_sources: tuple[SourceCellLocator, ...]

    @model_validator(mode="after")
    def validate_equivalent_sources(self) -> Self:
        """Require complete, deterministic, same-column source lineage."""
        sources = self.equivalent_sources
        if not sources:
            raise ValueError("equivalent_sources must not be empty")
        if sources[0] != self.representative.source:
            raise ValueError("representative source must be first")

        positions = tuple(
            (source.source_row_number, source.source_column_number) for source in sources
        )
        if len(set(positions)) != len(positions):
            raise ValueError("equivalent source positions must be unique")
        if positions != tuple(sorted(positions)):
            raise ValueError("equivalent_sources must be sorted by row and column")

        representative_source = self.representative.source
        representative_lineage = (
            representative_source.source_table,
            representative_source.source_file,
            representative_source.source_sheet,
            representative_source.source_column_name,
            representative_source.source_column_number,
            representative_source.source_column_letter,
            representative_source.source_checksum,
            representative_source.source_snapshot_date,
        )
        for source in sources:
            source_lineage = (
                source.source_table,
                source.source_file,
                source.source_sheet,
                source.source_column_name,
                source.source_column_number,
                source.source_column_letter,
                source.source_checksum,
                source.source_snapshot_date,
            )
            if source_lineage != representative_lineage:
                raise ValueError("equivalent_sources must share representative source lineage")
        return self
