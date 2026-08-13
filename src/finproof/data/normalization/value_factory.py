"""Construct normalized values from exact immutable source lineage."""

from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue


def make_normalized_value[ValueT](
    row: SourceRow,
    column_name: str,
    *,
    normalized_value: ValueT | None,
    quality_status: QualityStatus,
    rule_id: str,
    rule_version: str,
) -> NormalizedValue[ValueT]:
    """Return a typed value retaining its exact raw source cell and locator."""
    return NormalizedValue[ValueT](
        raw_value=row.cell(column_name).raw_value,
        normalized_value=normalized_value,
        quality_status=quality_status,
        rule_id=rule_id,
        rule_version=rule_version,
        source=SourceCellLocator.from_row(row, column_name),
    )
