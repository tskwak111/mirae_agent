"""Stable data-quality classifications and immutable issue contracts."""

import hashlib
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finproof.domain.locators import SourceCellLocator
from finproof.domain.source import SourceRow


class QualityStatus(StrEnum):
    """Quality states preserved alongside every normalized value."""

    VALID = "valid"
    MISSING_BLANK = "missing_blank"
    MISSING_LITERAL_NULL = "missing_literal_null"
    SENTINEL_ZERO = "sentinel_zero"
    SENTINEL_MAX_DATE = "sentinel_max_date"
    RECORDED_ZERO = "recorded_zero"
    RECORDED_ZERO_UNVERIFIED = "recorded_zero_unverified"
    INVALID_FORMAT = "invalid_format"
    OUT_OF_DOMAIN = "out_of_domain"
    CONSTANT_METRIC = "constant_metric"
    STALE = "stale"
    MIXED_SOURCE_VALUES = "mixed_source_values"
    MALFORMED_SOURCE_ROW = "malformed_source_row"


class IssueSeverity(StrEnum):
    """Stable severity classes for deterministic data-quality issues."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    BLOCKER = "blocker"


class DataQualityIssue(BaseModel):
    """A deterministic, payload-safe issue attached to an exact source cell."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    issue_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    severity: IssueSeverity
    quality_status: QualityStatus
    source: SourceCellLocator
    reason: str
    quarantined: bool
    raw_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_detected_at: datetime | None

    @field_validator("first_detected_at")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime | None) -> datetime | None:
        """Allow persisted timestamps only when they are explicitly UTC."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("first_detected_at must be timezone-aware")
        if value.utcoffset() != timedelta(0):
            raise ValueError("first_detected_at must be UTC")
        return value

    @classmethod
    def from_row(
        cls,
        row: SourceRow,
        column_name: str,
        *,
        rule_id: str,
        rule_version: str,
        severity: IssueSeverity,
        quality_status: QualityStatus,
        reason: str,
        quarantined: bool,
    ) -> "DataQualityIssue":
        """Build a clock-free issue from only immutable source-row lineage."""
        source = SourceCellLocator.from_row(row, column_name)
        issue_components = (
            rule_id,
            rule_version,
            source.source_table,
            source.source_file.as_posix(),
            source.source_sheet,
            str(source.source_row_number),
            source.source_column_name,
            str(source.source_column_number),
            source.source_column_letter,
            source.source_checksum,
            source.source_snapshot_date.isoformat(),
            source.source_applicable_date.isoformat()
            if source.source_applicable_date is not None
            else "",
        )
        return cls(
            issue_id=hashlib.sha256("\0".join(issue_components).encode("utf-8")).hexdigest(),
            rule_id=rule_id,
            rule_version=rule_version,
            severity=severity,
            quality_status=quality_status,
            source=source,
            reason=reason,
            quarantined=quarantined,
            raw_payload_sha256=hashlib.sha256(
                "\0".join(row.raw_payload).encode("utf-8")
            ).hexdigest(),
            first_detected_at=None,
        )
