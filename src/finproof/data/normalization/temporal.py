"""Pure parsers for strict date and source-datetime values."""

import re
from datetime import date, datetime

from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

_YYYYMMDD_PATTERN = re.compile(r"[0-9]{8}", flags=re.ASCII)
_SOURCE_DATETIME_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", flags=re.ASCII
)


def parse_yyyymmdd(
    row: SourceRow,
    column_name: str,
    *,
    allow_max_sentinel: bool,
    rule_id: str,
    rule_version: str,
) -> NormalizedValue[date]:
    """Parse an exact ASCII ``YYYYMMDD`` source date and declared sentinels."""
    raw_value = row.cell(column_name).raw_value
    if not raw_value.strip():
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.MISSING_BLANK,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    if raw_value in {"0", "00000000"}:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.SENTINEL_ZERO,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    if raw_value == "99991231" and allow_max_sentinel:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.SENTINEL_MAX_DATE,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    if _YYYYMMDD_PATTERN.fullmatch(raw_value) is None:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.INVALID_FORMAT,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    try:
        normalized_value = datetime.strptime(raw_value, "%Y%m%d").date()
    except ValueError:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.INVALID_FORMAT,
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


def parse_source_datetime(
    row: SourceRow,
    column_name: str,
    *,
    rule_id: str,
    rule_version: str,
) -> NormalizedValue[datetime]:
    """Parse the source's exact timezone-naive timestamp format."""
    raw_value = row.cell(column_name).raw_value
    if not raw_value.strip():
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.MISSING_BLANK,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    if _SOURCE_DATETIME_PATTERN.fullmatch(raw_value) is None:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.INVALID_FORMAT,
            rule_id=rule_id,
            rule_version=rule_version,
        )
    try:
        normalized_value = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return make_normalized_value(
            row,
            column_name,
            normalized_value=None,
            quality_status=QualityStatus.INVALID_FORMAT,
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
