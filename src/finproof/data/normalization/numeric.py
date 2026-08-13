"""Pure finite Decimal and integral source parsers."""

from decimal import Decimal, InvalidOperation
from typing import Literal

from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

NumericZeroStatus = Literal[
    QualityStatus.RECORDED_ZERO,
    QualityStatus.RECORDED_ZERO_UNVERIFIED,
]
_MAX_EXPANDED_INTEGER_DIGITS = 4300


def _validate_zero_status(zero_status: NumericZeroStatus) -> None:
    """Reject a quality state that cannot describe an exact numeric zero."""
    if not isinstance(zero_status, QualityStatus) or (
        zero_status is not QualityStatus.RECORDED_ZERO
        and zero_status is not QualityStatus.RECORDED_ZERO_UNVERIFIED
    ):
        raise ValueError("zero_status must be a recorded-zero quality status")


def _parse_finite_decimal(raw_value: str) -> tuple[Decimal | None, QualityStatus]:
    """Parse one raw numeric cell without changing its text or zero policy."""
    if not raw_value.strip():
        return None, QualityStatus.MISSING_BLANK
    if raw_value != raw_value.strip():
        return None, QualityStatus.INVALID_FORMAT
    try:
        decimal_value = Decimal(raw_value)
    except (InvalidOperation, ValueError):
        return None, QualityStatus.INVALID_FORMAT
    if not decimal_value.is_finite():
        return None, QualityStatus.INVALID_FORMAT
    return decimal_value, QualityStatus.VALID


def parse_decimal(
    row: SourceRow,
    column_name: str,
    *,
    zero_status: NumericZeroStatus,
    rule_id: str,
    rule_version: str,
) -> NormalizedValue[Decimal]:
    """Parse an exact finite Decimal and apply the field's zero policy."""
    _validate_zero_status(zero_status)
    decimal_value, quality_status = _parse_finite_decimal(row.cell(column_name).raw_value)
    if decimal_value == Decimal(0):
        quality_status = zero_status
    return make_normalized_value(
        row,
        column_name,
        normalized_value=decimal_value,
        quality_status=quality_status,
        rule_id=rule_id,
        rule_version=rule_version,
    )


def parse_integer(
    row: SourceRow,
    column_name: str,
    *,
    zero_status: NumericZeroStatus,
    rule_id: str,
    rule_version: str,
) -> NormalizedValue[int]:
    """Parse a finite Decimal only when its mathematical value is integral."""
    _validate_zero_status(zero_status)
    decimal_value, quality_status = _parse_finite_decimal(row.cell(column_name).raw_value)
    if decimal_value is None:
        normalized_value = None
    elif decimal_value != decimal_value.to_integral_value() or (
        not decimal_value.is_zero() and decimal_value.adjusted() + 1 > _MAX_EXPANDED_INTEGER_DIGITS
    ):
        normalized_value = None
        quality_status = QualityStatus.INVALID_FORMAT
    else:
        normalized_value = int(decimal_value)
        if decimal_value == Decimal(0):
            quality_status = zero_status
    return make_normalized_value(
        row,
        column_name,
        normalized_value=normalized_value,
        quality_status=quality_status,
        rule_id=rule_id,
        rule_version=rule_version,
    )
