"""Contract tests for canonical persisted data-quality issues."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from tests.helpers.source_rows import source_row

ROOT = Path(__file__).resolve().parents[2]


def _validator() -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas/quality_issue.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _issue() -> DataQualityIssue:
    return DataQualityIssue.from_row(
        source_row("PREF01N001", {"pd_itm_no": "KR"}, excel_row=1155),
        "pd_itm_no",
        rule_id="domestic_listed.product_id",
        rule_version="1.0.0",
        severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason="Domestic listed product identifier is malformed.",
        quarantined=True,
    )


def _messages(instance: object) -> tuple[str, ...]:
    return tuple(error.message for error in _validator().iter_errors(instance))


def test_pure_domain_issue_json_is_the_canonical_schema_instance() -> None:
    payload = _issue().model_dump(mode="json")
    assert payload["first_detected_at"] is None
    assert _messages(payload) == ()
    assert set(payload) == {
        "issue_id",
        "rule_id",
        "rule_version",
        "severity",
        "quality_status",
        "source",
        "reason",
        "quarantined",
        "raw_payload_sha256",
        "first_detected_at",
    }
    assert set(payload["source"]) == {
        "source_table",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_column_name",
        "source_column_number",
        "source_column_letter",
        "source_checksum",
        "source_snapshot_date",
        "source_applicable_date",
    }


def test_persisted_utc_issue_serializes_with_z_and_validates() -> None:
    issue = DataQualityIssue.model_validate(
        _issue().model_dump() | {"first_detected_at": datetime(2026, 7, 11, 0, 0, tzinfo=UTC)}
    )
    payload = issue.model_dump(mode="json")
    assert payload["first_detected_at"] == "2026-07-11T00:00:00Z"
    assert _messages(payload) == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issue_id", "A" * 64),
        ("raw_payload_sha256", "0" * 63),
        ("severity", "critical"),
        ("quality_status", "unknown"),
        ("first_detected_at", "2026-07-11T00:00:00"),
        ("first_detected_at", "2026-07-11T09:00:00+09:00"),
        ("first_detected_at", "not-a-date"),
    ],
)
def test_issue_schema_rejects_bad_hash_enum_and_timestamp(field: str, value: object) -> None:
    payload = _issue().model_dump(mode="json") | {field: value}
    assert _messages(payload)


def test_issue_schema_rejects_missing_and_extra_issue_fields() -> None:
    payload = _issue().model_dump(mode="json")
    missing = dict(payload)
    missing.pop("quarantined")
    assert _messages(missing)
    assert _messages(payload | {"raw_payload": "secret"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_file", "/absolute/source.xlsx"),
        ("source_file", "../escape.xlsx"),
        ("source_row_number", 0),
        ("source_column_number", 0),
        ("source_column_letter", "a"),
        ("source_checksum", "g" * 64),
        ("source_snapshot_date", "2026-02-30"),
        ("source_applicable_date", "2026/07/11"),
    ],
)
def test_issue_schema_rejects_incomplete_or_unsafe_locator(field: str, value: object) -> None:
    payload = _issue().model_dump(mode="json")
    payload["source"] = payload["source"] | {field: value}
    assert _messages(payload)


def test_issue_schema_rejects_missing_and_extra_locator_fields() -> None:
    payload = _issue().model_dump(mode="json")
    missing = dict(payload["source"])
    missing.pop("source_column_name")
    payload["source"] = missing
    assert _messages(payload)

    payload = _issue().model_dump(mode="json")
    payload["source"] = payload["source"] | {"absolute_path": "/absolute/source.xlsx"}
    assert _messages(payload)
