"""Tests for strict source temporal formats and source sentinels."""

from datetime import date, datetime

import pytest

from finproof.data.normalization.temporal import parse_source_datetime, parse_yyyymmdd
from finproof.domain.quality import QualityStatus
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize(
    ("raw", "allow_max", "value", "status"),
    [
        ("", False, None, QualityStatus.MISSING_BLANK),
        (" \t", False, None, QualityStatus.MISSING_BLANK),
        ("0", True, None, QualityStatus.SENTINEL_ZERO),
        ("00000000", False, None, QualityStatus.SENTINEL_ZERO),
        ("99991231", True, None, QualityStatus.SENTINEL_MAX_DATE),
        ("99991231", False, date(9999, 12, 31), QualityStatus.VALID),
        ("20260711", False, date(2026, 7, 11), QualityStatus.VALID),
        ("20260230", False, None, QualityStatus.INVALID_FORMAT),
        ("2026-07-11", False, None, QualityStatus.INVALID_FORMAT),
        (
            "\uff12\uff10\uff12\uff16\uff10\uff17\uff11\uff11",
            False,
            None,
            QualityStatus.INVALID_FORMAT,
        ),
        (" 20260711", False, None, QualityStatus.INVALID_FORMAT),
    ],
)
def test_yyyymmdd_parser_distinguishes_every_date_state(
    raw: str, allow_max: bool, value: date | None, status: QualityStatus
) -> None:
    """Only exact ASCII dates can become typed calendar values."""
    row = source_row("PRBD01N001", {"MAT_DT": raw})
    result = parse_yyyymmdd(
        row,
        "MAT_DT",
        allow_max_sentinel=allow_max,
        rule_id="bond.maturity_date",
        rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value == value
    assert result.quality_status is status


@pytest.mark.parametrize(
    ("raw", "value", "status"),
    [
        ("", None, QualityStatus.MISSING_BLANK),
        ("2026-07-11 09:30:00", datetime(2026, 7, 11, 9, 30), QualityStatus.VALID),
        ("2026-07-11T09:30:00", None, QualityStatus.INVALID_FORMAT),
        ("2026-07-11 09:30", None, QualityStatus.INVALID_FORMAT),
        ("2026-07-11 09:30:00+09:00", None, QualityStatus.INVALID_FORMAT),
    ],
)
def test_source_datetime_is_exact_and_timezone_naive(
    raw: str, value: datetime | None, status: QualityStatus
) -> None:
    """The source timestamp accepts its exact naive format only."""
    row = source_row("PREF01N001", {"du_upt_dt": raw})
    result = parse_source_datetime(
        row,
        "du_upt_dt",
        rule_id="domestic_listed.daily_update_at",
        rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value == value
    assert result.quality_status is status
    if result.normalized_value is not None:
        assert result.normalized_value.tzinfo is None
