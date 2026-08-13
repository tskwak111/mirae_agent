"""Pure text and identifier parsers with exact raw-value retention."""

import re

from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue


def parse_text(
    row: SourceRow,
    column_name: str,
    *,
    rule_id: str,
    rule_version: str,
) -> NormalizedValue[str]:
    """Normalize surrounding Unicode whitespace while preserving raw source text."""
    raw_value = row.cell(column_name).raw_value
    normalized_value = raw_value.strip()
    if not normalized_value:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.MISSING_BLANK,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    return make_normalized_value(
        row,
        column_name,
        normalized_value=normalized_value,
        quality_status=QualityStatus.VALID,
        rule_id=rule_id,
        rule_version=rule_version,
    )


def parse_identifier(
    row: SourceRow,
    column_name: str,
    *,
    rule_id: str,
    rule_version: str,
) -> NormalizedValue[str]:
    """Accept only an exact twelve-character uppercase ASCII identifier."""
    raw_value = row.cell(column_name).raw_value
    if re.fullmatch(r"[A-Z0-9]{12}", raw_value, flags=re.ASCII) is None:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    return make_normalized_value(
        row,
        column_name,
        normalized_value=raw_value,
        quality_status=QualityStatus.VALID,
        rule_id=rule_id,
        rule_version=rule_version,
    )
