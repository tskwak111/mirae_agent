"""Tests for exact finite Decimal and integral source parsing."""

from decimal import Decimal
from typing import Any

import pytest

from finproof.data.normalization.numeric import parse_decimal, parse_integer
from finproof.domain.quality import QualityStatus
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize(
    ("raw", "zero_status", "value", "status"),
    [
        ("", QualityStatus.RECORDED_ZERO, None, QualityStatus.MISSING_BLANK),
        (" \t", QualityStatus.RECORDED_ZERO, None, QualityStatus.MISSING_BLANK),
        ("0", QualityStatus.RECORDED_ZERO, Decimal("0"), QualityStatus.RECORDED_ZERO),
        (
            "-0.00",
            QualityStatus.RECORDED_ZERO_UNVERIFIED,
            Decimal("-0.00"),
            QualityStatus.RECORDED_ZERO_UNVERIFIED,
        ),
        ("3.500", QualityStatus.RECORDED_ZERO, Decimal("3.500"), QualityStatus.VALID),
        ("-100", QualityStatus.RECORDED_ZERO, Decimal("-100"), QualityStatus.VALID),
        ("NaN", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
        ("Infinity", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
        ("1,000", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
        (" 3.5", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
    ],
)
def test_decimal_parser_preserves_exact_finite_values_and_field_zero_status(
    raw: str,
    zero_status: QualityStatus,
    value: Decimal | None,
    status: QualityStatus,
) -> None:
    """Finite decimals retain their exact exponent and field-specific zero meaning."""
    row = source_row("PREF01N001", {"cu_charge_rt": raw})
    result = parse_decimal(
        row,
        "cu_charge_rt",
        zero_status=zero_status,  # type: ignore[arg-type]
        rule_id="domestic_listed.total_fee",
        rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value == value
    assert result.quality_status is status
    if raw == "3.500":
        assert result.normalized_value is not None
        assert result.normalized_value.as_tuple().exponent == -3


@pytest.mark.parametrize(
    ("raw", "value", "status"),
    [
        ("12", 12, QualityStatus.VALID),
        ("12.0", 12, QualityStatus.VALID),
        ("0.0", 0, QualityStatus.RECORDED_ZERO),
        ("12.5", None, QualityStatus.INVALID_FORMAT),
        ("NaN", None, QualityStatus.INVALID_FORMAT),
        ("1e2", 100, QualityStatus.VALID),
    ],
)
def test_integer_parser_accepts_decimal_syntax_only_when_integral(
    raw: str, value: int | None, status: QualityStatus
) -> None:
    """Integer source fields accept only mathematically integral decimal values."""
    row = source_row("PRBD01N001", {"REMAINING_DAYS": raw})
    result = parse_integer(
        row,
        "REMAINING_DAYS",
        zero_status=QualityStatus.RECORDED_ZERO,
        rule_id="bond.source_remaining_days",
        rule_version="1.0.0",
    )
    assert result.normalized_value == value
    assert result.quality_status is status


def test_numeric_parsers_reject_a_nonzero_quality_status() -> None:
    """Callers must declare one of the two field-level recorded-zero policies."""
    row = source_row("PRBD01N001", {"REMAINING_DAYS": "1"})
    with pytest.raises(ValueError, match="zero_status"):
        parse_decimal(
            row,
            "REMAINING_DAYS",
            zero_status=QualityStatus.VALID,  # type: ignore[arg-type]
            rule_id="bond.source_remaining_days",
            rule_version="1.0.0",
        )


def test_numeric_parsers_reject_raw_string_zero_statuses() -> None:
    """String lookalikes cannot bypass the enum-only zero-policy contract."""
    row = source_row("PRBD01N001", {"REMAINING_DAYS": "1"})
    raw_zero_status: Any = "recorded_zero"
    with pytest.raises(ValueError, match="zero_status"):
        parse_decimal(
            row,
            "REMAINING_DAYS",
            zero_status=raw_zero_status,
            rule_id="bond.source_remaining_days",
            rule_version="1.0.0",
        )
    with pytest.raises(ValueError, match="zero_status"):
        parse_integer(
            row,
            "REMAINING_DAYS",
            zero_status=raw_zero_status,
            rule_id="bond.source_remaining_days",
            rule_version="1.0.0",
        )


def test_integer_parser_rejects_compact_values_exceeding_expanded_digit_limit() -> None:
    """An exponent cannot cause an unbounded integer allocation during parsing."""
    result = parse_integer(
        source_row("PRBD01N001", {"REMAINING_DAYS": "1e100000"}),
        "REMAINING_DAYS",
        zero_status=QualityStatus.RECORDED_ZERO,
        rule_id="bond.source_remaining_days",
        rule_version="1.0.0",
    )
    assert result.normalized_value is None
    assert result.quality_status is QualityStatus.INVALID_FORMAT
