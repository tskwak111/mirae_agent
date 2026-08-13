"""Tests for exact-text and identifier normalization."""

import pytest

from finproof.data.normalization.text import parse_identifier, parse_text
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
