"""Tests for shared normalization lineage and quality contracts."""

import hashlib
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import PurePosixPath
from typing import TypedDict

import pytest
from pydantic import BaseModel, ValidationError

from finproof.core.errors import NormalizationContractError
from finproof.domain.locators import SourceCellLocator
from finproof.domain.normalization import NormalizationResult
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.values import DerivedValue, NormalizedValue
from tests.helpers.source_rows import BOND_COLUMNS, DOMESTIC_LISTED_COLUMNS, source_row


class _IssueArguments(TypedDict):
    rule_id: str
    rule_version: str
    severity: IssueSeverity
    quality_status: QualityStatus
    reason: str
    quarantined: bool


def test_quality_and_severity_values_are_exact() -> None:
    """Adding, removing, or renaming a serialized quality value is a contract break."""
    assert {status.value for status in QualityStatus} == {
        "valid",
        "missing_blank",
        "missing_literal_null",
        "sentinel_zero",
        "sentinel_max_date",
        "recorded_zero",
        "recorded_zero_unverified",
        "invalid_format",
        "out_of_domain",
        "constant_metric",
        "stale",
        "mixed_source_values",
        "malformed_source_row",
    }
    assert {severity.value for severity in IssueSeverity} == {
        "info",
        "warning",
        "high",
        "blocker",
    }


@pytest.mark.parametrize(
    ("table_id", "columns"),
    [("PRBD01N001", BOND_COLUMNS), ("PREF01N001", DOMESTIC_LISTED_COLUMNS)],
)
def test_source_row_helper_builds_every_official_cell_in_order(
    table_id: str, columns: tuple[str, ...]
) -> None:
    """A helper missing a real source column must fail before normalizer tests use it."""
    row = source_row(table_id)  # type: ignore[arg-type]
    assert tuple(cell.column_name for cell in row.cells) == columns
    assert row.raw_payload == tuple(cell.raw_value for cell in row.cells)


def test_locator_is_built_only_from_exact_row_and_cell_lineage() -> None:
    """A locator must retain the source cell exactly and reject case-folded headers."""
    row = source_row(
        "PRBD01N001",
        {"PD_NO": "XS0000000001"},
        excel_row=19,
        applicable_dates={"PD_NO": date(2026, 7, 10)},
    )
    locator = SourceCellLocator.from_row(row, "PD_NO")
    assert locator.source_table == "PRBD01N001"
    assert locator.source_file.as_posix() == "data/PRBD01N001_fixture.xlsx"
    assert locator.source_sheet == "datarows"
    assert locator.source_row_number == 19
    assert locator.source_column_name == "PD_NO"
    assert locator.source_column_number == 1
    assert locator.source_column_letter == "A"
    assert locator.source_checksum == "a" * 64
    assert locator.source_snapshot_date == date(2026, 7, 11)
    assert locator.source_applicable_date == date(2026, 7, 10)
    with pytest.raises(KeyError, match="pd_no"):
        SourceCellLocator.from_row(row, "pd_no")


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        ("source_file", PurePosixPath("/absolute/forged.xlsx"), "manifest-relative"),
        ("source_file", PurePosixPath("../forged.xlsx"), "manifest-relative"),
        ("source_table", "", "source_table"),
        ("source_sheet", "", "source_sheet"),
        ("source_column_name", "", "source_column_name"),
        ("source_column_letter", "", "source_column_letter"),
    ],
)
def test_locator_direct_construction_rejects_unsafe_or_blank_lineage(
    field_name: str, invalid_value: str | PurePosixPath, message: str
) -> None:
    """Forged paths and blank source identity fields must not create a locator."""
    valid_locator = SourceCellLocator.from_row(source_row("PRBD01N001"), "PD_NO")
    with pytest.raises(ValidationError, match=message):
        SourceCellLocator.model_validate(valid_locator.model_dump() | {field_name: invalid_value})


def test_locator_direct_construction_requires_matching_multi_letter_column_location() -> None:
    """Column number and Excel letters are one location, including columns beyond Z."""
    valid_locator = SourceCellLocator.from_row(source_row("PRBD01N001"), "PD_NO")
    multi_letter_locator = SourceCellLocator.model_validate(
        valid_locator.model_dump()
        | {
            "source_column_number": 27,
            "source_column_letter": "AA",
        }
    )
    assert multi_letter_locator.source_column_letter == "AA"
    with pytest.raises(ValidationError, match="source_column_letter"):
        SourceCellLocator.model_validate(
            valid_locator.model_dump()
            | {
                "source_column_number": 27,
                "source_column_letter": "A",
            }
        )


@pytest.mark.parametrize(
    "model",
    [SourceCellLocator, NormalizedValue, DerivedValue, DataQualityIssue, NormalizationResult],
)
def test_new_normalization_contracts_enable_frozen_forbid_and_strict(
    model: type[BaseModel],
) -> None:
    """Configuration drift must not make normalized lineage coercive or mutable."""
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["strict"] is True


def test_normalized_and_derived_values_are_frozen_and_reject_empty_rules() -> None:
    """Rule-less or mutable transformed values cannot support reproducible evidence."""
    row = source_row("PRBD01N001", {"BUY_YIELD": " 3.50 "})
    value = NormalizedValue[Decimal](
        raw_value=" 3.50 ",
        normalized_value=Decimal("3.50"),
        quality_status=QualityStatus.VALID,
        rule_id="bond.buy_yield",
        rule_version="1.0.0",
        source=SourceCellLocator.from_row(row, "BUY_YIELD"),
    )
    derived = DerivedValue[int](
        value=9,
        quality_status=QualityStatus.VALID,
        rule_id="bond.remaining_days_at_as_of",
        rule_version="1.0.0",
        as_of_date=date(2026, 7, 11),
        inputs=(SourceCellLocator.from_row(row, "MAT_DT"),),
    )
    assert value.raw_value == " 3.50 "
    assert derived.inputs[0].source_column_name == "MAT_DT"
    with pytest.raises(ValidationError):
        value.raw_value = "3.50"
    with pytest.raises(ValidationError, match="at least 1 character"):
        DerivedValue[int](
            value=9,
            quality_status=QualityStatus.VALID,
            rule_id="",
            rule_version="1.0.0",
            as_of_date=date(2026, 7, 11),
            inputs=(SourceCellLocator.from_row(row, "MAT_DT"),),
        )


def test_quality_issue_is_deterministic_clock_free_and_payload_safe() -> None:
    """Repeating pure normalization must not expose raw data or invent a clock value."""
    row = source_row("PREF01N001", {"pd_itm_no": "KR"}, excel_row=1155)
    kwargs: _IssueArguments = {
        "rule_id": "domestic_listed.product_id",
        "rule_version": "1.0.0",
        "severity": IssueSeverity.BLOCKER,
        "quality_status": QualityStatus.MALFORMED_SOURCE_ROW,
        "reason": "domestic listed product identifier is malformed",
        "quarantined": True,
    }
    first = DataQualityIssue.from_row(row, "pd_itm_no", **kwargs)
    second = DataQualityIssue.from_row(row, "pd_itm_no", **kwargs)
    expected_payload_hash = hashlib.sha256("\0".join(row.raw_payload).encode("utf-8")).hexdigest()
    assert first == second
    assert first.issue_id == first.issue_id.lower()
    assert len(first.issue_id) == 64
    assert first.raw_payload_sha256 == expected_payload_hash
    assert first.first_detected_at is None
    assert "KR" not in first.reason
    assert "/Users/" not in first.reason


def test_persisted_issue_timestamp_must_be_utc() -> None:
    """Persisted issue timestamps must be explicit UTC values, never local time."""
    row = source_row("PREF01N001", {"pd_itm_no": "KR"})
    issue = DataQualityIssue.from_row(
        row,
        "pd_itm_no",
        rule_id="domestic_listed.product_id",
        rule_version="1.0.0",
        severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason="domestic listed product identifier is malformed",
        quarantined=True,
    )
    with pytest.raises(ValidationError, match="timezone-aware"):
        DataQualityIssue.model_validate(
            issue.model_dump() | {"first_detected_at": datetime(2026, 7, 11, 9, 0)}
        )
    with pytest.raises(ValidationError, match="UTC"):
        DataQualityIssue.model_validate(
            issue.model_dump()
            | {
                "first_detected_at": datetime(
                    2026, 7, 11, 9, 0, tzinfo=timezone(timedelta(hours=9))
                )
            }
        )
    persisted = DataQualityIssue.model_validate(
        issue.model_dump() | {"first_detected_at": datetime(2026, 7, 11, 0, 0, tzinfo=UTC)}
    )
    assert persisted.first_detected_at is not None


def test_normalization_result_enforces_quarantine_equivalence() -> None:
    """A missing record and a quarantined issue must always occur together."""
    row = source_row("PREF01N001", {"pd_itm_no": "KR"})
    blocker = DataQualityIssue.from_row(
        row,
        "pd_itm_no",
        rule_id="domestic_listed.product_id",
        rule_version="1.0.0",
        severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason="domestic listed product identifier is malformed",
        quarantined=True,
    )
    warning = DataQualityIssue.from_row(
        row,
        "pd_curr_cd",
        rule_id="domestic_listed.currency",
        rule_version="1.0.0",
        severity=IssueSeverity.WARNING,
        quality_status=QualityStatus.OUT_OF_DOMAIN,
        reason="domestic listed currency code is unregistered",
        quarantined=False,
    )
    assert NormalizationResult[str](record=None, issues=(blocker,)).record is None
    assert NormalizationResult[str](record="record", issues=(warning,)).record == "record"
    with pytest.raises(ValidationError, match="quarantined issue"):
        NormalizationResult[str](record=None, issues=())
    with pytest.raises(ValidationError, match="record cannot contain"):
        NormalizationResult[str](record="record", issues=(blocker,))


def test_normalization_contract_error_keeps_only_expected_and_actual_table_context() -> None:
    """Wrong-table programming errors must not carry a source path or raw payload."""
    error = NormalizationContractError("PRBD01N001", "PREF01N001")
    assert error.expected_table == "PRBD01N001"
    assert error.actual_table == "PREF01N001"
    assert "PRBD01N001" in str(error)
    assert "PREF01N001" in str(error)
    assert not hasattr(error, "source_file")
    assert not hasattr(error, "raw_payload")
