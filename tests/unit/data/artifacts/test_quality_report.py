"""Deterministic quality-summary report contracts."""

# ruff: noqa: E501

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Literal

import pytest

from finproof.data.artifacts.hashing import table_logical_hash
from finproof.data.artifacts.quality_persistence import persist_quality_issue
from finproof.data.artifacts.reports import (
    ExcludedSilverCount,
    QualityJoinObservations,
    QualitySummaryReport,
)
from finproof.data.artifacts.serialization import logical_table_row, serialize_table_row
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from tests.helpers.source_rows import source_row


def _persisted_issue() -> DataQualityIssue:
    pure = DataQualityIssue.from_row(
        source_row("PRBD01N001", excel_row=2),
        "PD_NM",
        rule_id="fixture.rule",
        rule_version="1.0.0",
        severity=IssueSeverity.WARNING,
        quality_status=QualityStatus.INVALID_FORMAT,
        reason="Fixture issue.",
        quarantined=True,
    )
    return persist_quality_issue(
        pure,
        persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
    )


def _join_observations(issue: DataQualityIssue) -> QualityJoinObservations:
    spec = TABLE_SPEC_BY_NAME["silver_quality_issue"]
    physical = serialize_table_row(spec, issue)
    digest = table_logical_hash(
        spec,
        row_count=1,
        rows=(logical_table_row(spec, physical),),
    )
    return QualityJoinObservations(
        total_issues=1,
        distinct_issue_ids=1,
        matched_bronze_rows=1,
        matched_bronze_cells=1,
        distinct_affected_source_rows=1,
        quarantined_issue_count=1,
        quarantined_source_row_count=1,
        persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
        quality_table_logical_hash=digest,
    )


def _excluded() -> tuple[ExcludedSilverCount, ...]:
    return (
        ExcludedSilverCount(grain="fund_item", count=1),
        ExcludedSilverCount(grain="instrument", count=1),
    )


def test_quality_report_factory_accepts_only_exact_persisted_issue_stream_and_verified_join_observations() -> (
    None
):
    issue = _persisted_issue()

    class OnePassIssues:
        def __init__(self) -> None:
            self.iterations = 0

        def __len__(self) -> int:
            raise AssertionError("quality issue stream must not be sized")

        def __iter__(self) -> Iterator[DataQualityIssue]:
            if self.iterations:
                raise AssertionError("quality issue stream must be consumed once")
            self.iterations += 1
            yield issue

    issues = OnePassIssues()
    report = QualitySummaryReport.from_verified_quality(
        issues=issues,
        join_observations=_join_observations(issue),
        excluded_silver_records=_excluded(),
    )

    assert report.total_issues == 1
    assert issues.iterations == 1
    with pytest.raises((TypeError, ValueError)):
        QualitySummaryReport.from_verified_quality(
            issues=(issue.model_dump(mode="python"),),  # type: ignore[arg-type]
            join_observations=_join_observations(issue),
            excluded_silver_records=_excluded(),
        )
    pure = issue.model_copy(update={"first_detected_at": None})
    with pytest.raises((TypeError, ValueError)):
        QualitySummaryReport.from_verified_quality(
            issues=(pure,),
            join_observations=_join_observations(issue),
            excluded_silver_records=_excluded(),
        )


def test_quality_report_derives_closed_lexical_groups_counts_and_excluded_grains() -> None:
    issue = _persisted_issue()

    report = QualitySummaryReport.from_verified_quality(
        issues=(issue,),
        join_observations=_join_observations(issue),
        excluded_silver_records=_excluded(),
    )

    assert tuple((item.source_table, item.count) for item in report.by_source_table) == (
        ("PRBD01N001", 1),
    )
    assert tuple((item.rule_id, item.rule_version, item.count) for item in report.by_rule) == (
        ("fixture.rule", "1.0.0", 1),
    )
    assert tuple((item.severity.value, item.count) for item in report.by_severity) == (
        ("warning", 1),
    )
    assert tuple((item.quality_status.value, item.count) for item in report.by_quality_status) == (
        ("invalid_format", 1),
    )
    assert tuple((item.value, item.count) for item in report.by_quarantine_flag) == (
        (False, 0),
        (True, 1),
    )
    assert tuple((item.grain, item.count) for item in report.excluded_silver_records) == (
        ("fund_item", 1),
        ("instrument", 1),
    )


def test_quality_report_semantic_projection_is_timestamp_path_and_rendering_independent() -> None:
    issue = _persisted_issue()
    report = QualitySummaryReport.from_verified_quality(
        issues=(issue,),
        join_observations=_join_observations(issue),
        excluded_silver_records=_excluded(),
    )

    projection = report.semantic_projection()
    compact = json.dumps(projection, default=str, sort_keys=True, separators=(",", ":"))
    pretty = json.dumps(projection, default=str, sort_keys=True, indent=2)

    assert json.loads(compact) == json.loads(pretty)
    assert "2026-08-15" not in compact
    assert "persistence_timestamp" not in compact
    assert "/tmp/" not in compact  # noqa: S108 -- verifies path absence


def test_silver_observations_preserve_exact_bronze_prefix_and_reject_forged_or_complete_phase_admission() -> (
    None
):
    from finproof.data.artifacts.reports import (
        BronzeSourceAuditObservations,
        ExpectedObservedCount,
        NamedExpectedObservedCount,
        SilverSourceAuditObservations,
        SourceTableAudit,
        require_silver_source_audit_observations,
    )

    source_names: tuple[Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"], ...] = (
        "PRBD01N001",
        "PREF01N001",
        "PREF02N001",
        "PRFD01N001",
    )
    source_tables = tuple(
        SourceTableAudit(
            source_table=table,
            expected_rows=1,
            observed_rows=1,
            expected_columns=1,
            observed_columns=1,
            expected_cells=1,
            observed_cells=1,
        )
        for table in source_names
    )
    bronze = BronzeSourceAuditObservations.from_bronze(
        source_snapshot_date=date(2026, 7, 11),
        source_manifest_sha256="a" * 64,
        schema_catalog_sha256="b" * 64,
        source_tables=source_tables,
    )
    silver_names: tuple[
        Literal[
            "bond_instrument",
            "domestic_listed_product",
            "overseas_listed_product",
            "fund_item",
            "fund_item_attribute",
        ],
        ...,
    ] = (
        "bond_instrument",
        "domestic_listed_product",
        "overseas_listed_product",
        "fund_item",
        "fund_item_attribute",
    )
    silver_counts = tuple(
        NamedExpectedObservedCount(name=name, expected=1, observed=1) for name in silver_names
    )
    quarantine = ExpectedObservedCount(expected=0, observed=0)

    silver = bronze.with_silver(silver_counts, quarantine)

    assert type(silver) is SilverSourceAuditObservations
    assert silver.source_tables is bronze.source_tables
    assert silver.source_manifest_sha256 is bronze.source_manifest_sha256
    assert silver.schema_catalog_sha256 is bronze.schema_catalog_sha256
    assert silver.silver_tables is silver_counts
    assert silver.quarantine_source_rows is quarantine
    require_silver_source_audit_observations(silver)
    assert not hasattr(silver, "exact_links")
    assert not hasattr(silver, "with_silver")
    with pytest.raises((TypeError, ValueError)):
        bronze.with_silver(silver_counts, quarantine)
    forged = object.__new__(SilverSourceAuditObservations)
    for name in (
        "source_snapshot_date",
        "source_manifest_sha256",
        "schema_catalog_sha256",
        "source_tables",
        "silver_tables",
        "quarantine_source_rows",
    ):
        object.__setattr__(forged, name, getattr(silver, name))
    with pytest.raises((TypeError, ValueError)):
        require_silver_source_audit_observations(forged)
