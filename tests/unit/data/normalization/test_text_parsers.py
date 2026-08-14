"""Tests for exact-text and identifier normalization."""

import pytest

from finproof.data.normalization.text import (
    parse_exact_source_identity,
    parse_identifier,
    parse_literal_null_text,
    parse_text,
)
from finproof.domain.quality import QualityStatus
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize(
    ("raw", "normalized", "status"),
    [
        ("  채권\u3000", "채권", QualityStatus.VALID),
        ("", None, QualityStatus.MISSING_BLANK),
        (" \t\u3000", None, QualityStatus.MISSING_BLANK),
        ("NULL", "NULL", QualityStatus.VALID),
    ],
)
def test_text_preserves_raw_and_only_trims_normalized_value(
    raw: str, normalized: str | None, status: QualityStatus
) -> None:
    """Only normalized text may trim its surrounding Unicode whitespace."""
    row = source_row("PRBD01N001", {"PD_NM": raw})
    result = parse_text(row, "PD_NM", rule_id="bond.name", rule_version="1.0.0")
    assert result.raw_value == raw
    assert result.normalized_value == normalized
    assert result.quality_status is status
    assert result.source == result.source.from_row(row, "PD_NM")


@pytest.mark.parametrize("raw", ["KR0000000001", "XS0000000001", "A1B2C3D4E5F6"])
def test_identifier_accepts_only_exact_uppercase_ascii_shape(raw: str) -> None:
    """Twelve-character uppercase ASCII product identifiers are valid."""
    result = parse_identifier(
        source_row("PRBD01N001", {"PD_NO": raw}),
        "PD_NO",
        rule_id="bond.product_id",
        rule_version="1.0.0",
    )
    assert result.normalized_value == raw
    assert result.quality_status is QualityStatus.VALID


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "KR",
        " KR0000000001",
        "KR0000000001 ",
        "kr0000000001",
        "\uff2b\uff320000000001",
    ],
)
def test_identifier_rejects_blank_short_padded_lowercase_and_non_ascii(raw: str) -> None:
    """Identifiers never trim, case-fold, or accept non-ASCII lookalikes."""
    result = parse_identifier(
        source_row("PRBD01N001", {"PD_NO": raw}),
        "PD_NO",
        rule_id="bond.product_id",
        rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value is None
    assert result.quality_status is QualityStatus.MALFORMED_SOURCE_ROW


@pytest.mark.parametrize("raw", ["BND.O", "XW", "EES", "kr.f", "A/B", "123456789012345"])
def test_exact_source_identity_preserves_nonblank_unpadded_raw_text(raw: str) -> None:
    """Exact source identities preserve case, punctuation, and length."""
    value = parse_exact_source_identity(
        source_row("PREF02N001", {"pd_itm_no": raw}),
        "pd_itm_no",
        rule_id="overseas_listed.product_id",
        rule_version="1.0.0",
    )
    assert value.raw_value == raw
    assert value.normalized_value == raw
    assert value.quality_status is QualityStatus.VALID


@pytest.mark.parametrize("raw", ["", " ", " BND.O", "BND.O ", "\tXW"])
def test_exact_source_identity_rejects_blank_or_surrounding_whitespace(raw: str) -> None:
    """Identity parsing must not silently trim a source identifier."""
    value = parse_exact_source_identity(
        source_row("PREF02N001", {"pd_itm_no": raw}),
        "pd_itm_no",
        rule_id="overseas_listed.product_id",
        rule_version="1.0.0",
    )
    assert value.raw_value == raw
    assert value.normalized_value is None
    assert value.quality_status is QualityStatus.MALFORMED_SOURCE_ROW


def test_literal_null_is_declared_parser_behavior_not_global_text_behavior() -> None:
    """Only an explicit field policy may reinterpret the exact NULL literal."""
    row = source_row("PRFD01N001", {"zrin_fd_ivst_risk_gcd": "NULL", "itm_nm": "NULL"})
    risk = parse_literal_null_text(
        row,
        "zrin_fd_ivst_risk_gcd",
        rule_id="public_fund.risk_code",
        rule_version="1.0.0",
    )
    name = parse_text(
        row,
        "itm_nm",
        rule_id="public_fund.name",
        rule_version="1.0.0",
    )
    assert (risk.normalized_value, risk.quality_status) == (
        None,
        QualityStatus.MISSING_LITERAL_NULL,
    )
    assert (name.normalized_value, name.quality_status) == (
        "NULL",
        QualityStatus.VALID,
    )
