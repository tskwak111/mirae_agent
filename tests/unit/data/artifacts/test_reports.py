# mypy: disable-error-code="arg-type"
"""Strict semantic artifact report contracts."""

import hashlib
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from finproof.data.artifacts.reports import QualitySummaryReport, SourceAuditReport
from finproof.domain.quality import IssueSeverity, QualityStatus


@pytest.mark.parametrize(
    "case",
    [
        "snapshot",
        "snapshot-string",
        "manifest-uppercase",
        "manifest-short",
        "manifest-type",
        "catalog-uppercase",
        "catalog-short",
        "catalog-type",
        "tables-list",
        "tables-missing",
        "tables-reorder",
        "tables-duplicate",
        "expected-rows",
        "observed-rows",
        "expected-columns",
        "observed-columns",
        "expected-cells",
        "observed-cells",
        "bool-count",
    ],
)
def test_bronze_observations_require_exact_hashes_and_four_ordered_source_tables(
    case: str,
) -> None:
    from finproof.data.artifacts.reports import BronzeSourceAuditObservations, SourceTableAudit

    source_tables = tuple(
        SourceTableAudit.model_validate(entry, strict=True)
        for entry in _source_audit_payload()["source_tables"]
    )
    payload: dict[str, object] = {
        "source_snapshot_date": date(2026, 7, 11),
        "source_manifest_sha256": "a" * 64,
        "schema_catalog_sha256": "b" * 64,
        "source_tables": source_tables,
    }
    if case == "snapshot":
        payload["source_snapshot_date"] = date(2026, 7, 10)
    elif case == "snapshot-string":
        payload["source_snapshot_date"] = "2026-07-11"
    elif case.startswith("manifest-"):
        payload["source_manifest_sha256"] = {
            "manifest-uppercase": "A" * 64,
            "manifest-short": "a" * 63,
            "manifest-type": b"a" * 64,
        }[case]
    elif case.startswith("catalog-"):
        payload["schema_catalog_sha256"] = {
            "catalog-uppercase": "B" * 64,
            "catalog-short": "b" * 63,
            "catalog-type": b"b" * 64,
        }[case]
    elif case == "tables-list":
        payload["source_tables"] = list(source_tables)
    elif case == "tables-missing":
        payload["source_tables"] = source_tables[:-1]
    elif case == "tables-reorder":
        payload["source_tables"] = tuple(reversed(source_tables))
    elif case == "tables-duplicate":
        payload["source_tables"] = (source_tables[0], source_tables[0], *source_tables[2:])
    else:
        field = case.replace("-", "_")
        if case == "bool-count":
            field = "expected_rows"
            replacement: object = True
        else:
            replacement = getattr(source_tables[0], field) + 1
        forged = source_tables[0].model_copy(update={field: replacement})
        payload["source_tables"] = (forged, *source_tables[1:])

    with pytest.raises((TypeError, ValueError)):
        BronzeSourceAuditObservations.from_bronze(**payload)

    valid = BronzeSourceAuditObservations.from_bronze(
        source_snapshot_date=date(2026, 7, 11),
        source_manifest_sha256="a" * 64,
        schema_catalog_sha256="b" * 64,
        source_tables=source_tables,
    )
    assert valid.source_tables is source_tables


@pytest.mark.parametrize(
    "case",
    ["copy", "object-new", "subclass-suffix", "mapping", "report", "mutated"],
)
def test_cp4_bronze_observations_reject_forged_later_typestate_and_report_admission(
    case: str,
) -> None:
    from copy import copy

    from finproof.data.artifacts import reports
    from finproof.data.artifacts.reports import (
        BronzeSourceAuditObservations,
        SourceTableAudit,
        require_bronze_source_audit_observations,
    )

    source_tables = tuple(
        SourceTableAudit.model_validate(entry, strict=True)
        for entry in _source_audit_payload()["source_tables"]
    )
    value = BronzeSourceAuditObservations.from_bronze(
        source_snapshot_date=date(2026, 7, 11),
        source_manifest_sha256="a" * 64,
        schema_catalog_sha256="b" * 64,
        source_tables=source_tables,
    )

    def attempt_forgery() -> None:
        if case == "copy":
            forged: object = copy(value)
        elif case == "object-new":
            forged = object.__new__(BronzeSourceAuditObservations)
            for name in (
                "source_snapshot_date",
                "source_manifest_sha256",
                "schema_catalog_sha256",
                "source_tables",
            ):
                object.__setattr__(forged, name, getattr(value, name))
        elif case == "subclass-suffix":

            class LaterPhase(BronzeSourceAuditObservations):
                __slots__ = ("silver_tables",)

            forged = object.__new__(LaterPhase)
            for name in (
                "source_snapshot_date",
                "source_manifest_sha256",
                "schema_catalog_sha256",
                "source_tables",
            ):
                object.__setattr__(forged, name, getattr(value, name))
            object.__setattr__(forged, "silver_tables", ())
        elif case == "mapping":
            forged = {
                "source_snapshot_date": value.source_snapshot_date,
                "source_manifest_sha256": value.source_manifest_sha256,
                "schema_catalog_sha256": value.schema_catalog_sha256,
                "source_tables": value.source_tables,
            }
        elif case == "report":
            forged = SourceAuditReport.model_validate(_source_audit_payload(), strict=True)
        else:
            object.__setattr__(value, "source_manifest_sha256", "c" * 64)
            forged = value
        require_bronze_source_audit_observations(forged)

    with pytest.raises((TypeError, ValueError)):
        attempt_forgery()

    assert not hasattr(reports, "SilverSourceAuditObservations")
    assert not hasattr(reports, "CompleteSourceAuditObservations")
    assert not hasattr(reports, "produce_source_audit_report")


def _source_audit_payload() -> dict[str, Any]:
    return {
        "report_id": "source_audit",
        "report_contract_version": "1.0.0",
        "artifact_contract_version": "1.0.0",
        "source_snapshot_date": date(2026, 7, 11),
        "source_manifest_sha256": "a" * 64,
        "schema_catalog_sha256": "b" * 64,
        "source_tables": (
            {
                "source_table": "PRBD01N001",
                "expected_rows": 42_394,
                "observed_rows": 42_394,
                "expected_columns": 40,
                "observed_columns": 40,
                "expected_cells": 1_695_760,
                "observed_cells": 1_695_760,
            },
            {
                "source_table": "PREF01N001",
                "expected_rows": 1_734,
                "observed_rows": 1_734,
                "expected_columns": 73,
                "observed_columns": 73,
                "expected_cells": 126_582,
                "observed_cells": 126_582,
            },
            {
                "source_table": "PREF02N001",
                "expected_rows": 5_646,
                "observed_rows": 5_646,
                "expected_columns": 49,
                "observed_columns": 49,
                "expected_cells": 276_654,
                "observed_cells": 276_654,
            },
            {
                "source_table": "PRFD01N001",
                "expected_rows": 95_619,
                "observed_rows": 95_619,
                "expected_columns": 45,
                "observed_columns": 45,
                "expected_cells": 4_302_855,
                "observed_cells": 4_302_855,
            },
        ),
        "silver_tables": (
            {"name": "bond_instrument", "expected": 42_394, "observed": 42_394},
            {
                "name": "domestic_listed_product",
                "expected": 1_733,
                "observed": 1_733,
            },
            {
                "name": "overseas_listed_product",
                "expected": 5_646,
                "observed": 5_646,
            },
            {"name": "fund_item", "expected": 11_138, "observed": 11_138},
            {
                "name": "fund_item_attribute",
                "expected": 95_618,
                "observed": 95_618,
            },
        ),
        "quarantine_source_rows": {"expected": 2, "observed": 2},
        "exact_links": {"expected": 47, "observed": 47},
        "exact_link_evidence": {"expected": 371, "observed": 371},
        "exact_link_pair_sha256": {"expected": "c" * 64, "observed": "c" * 64},
    }


def _quality_summary_payload() -> dict[str, Any]:
    return {
        "report_id": "quality_summary",
        "report_contract_version": "1.0.0",
        "artifact_contract_version": "1.0.0",
        "total_issues": 4,
        "distinct_affected_source_rows": 3,
        "by_source_table": (
            {"source_table": "PRBD01N001", "count": 2},
            {"source_table": "PREF01N001", "count": 2},
        ),
        "by_rule": (
            {"rule_id": "Q-001", "rule_version": "1.0.0", "count": 2},
            {"rule_id": "Q-002", "rule_version": "1.0.0", "count": 2},
        ),
        "by_severity": (
            {"severity": IssueSeverity.HIGH, "count": 2},
            {"severity": IssueSeverity.WARNING, "count": 2},
        ),
        "by_quality_status": (
            {"quality_status": QualityStatus.INVALID_FORMAT, "count": 2},
            {"quality_status": QualityStatus.MISSING_BLANK, "count": 2},
        ),
        "by_quarantine_flag": (
            {"value": False, "count": 2},
            {"value": True, "count": 2},
        ),
        "quarantined_issue_count": 2,
        "quarantined_source_row_count": 2,
        "excluded_silver_records": (
            {"grain": "fund_item", "count": 1},
            {"grain": "instrument", "count": 1},
        ),
        "quality_table_logical_hash": "d" * 64,
    }


def test_closed_report_semantic_mutation_changes_only_report_logical_hash(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.hashing import canonical_json_bytes, report_logical_hash

    original = SourceAuditReport.model_validate(_source_audit_payload(), strict=True)
    pretty_path = tmp_path / "pretty.json"
    compact_path = tmp_path / "nested" / "compact.json"
    compact_path.parent.mkdir()
    pretty_path.write_text(
        json.dumps(original.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    compact_path.write_text(original.model_dump_json(), encoding="utf-8")
    original_hash = report_logical_hash(original)
    canonical = canonical_json_bytes(original.semantic_projection())
    assert hashlib.sha256(canonical).hexdigest() == original_hash
    assert pretty_path.read_bytes() != canonical
    assert compact_path.read_bytes() != canonical

    payload = _source_audit_payload()
    payload["source_manifest_sha256"] = "e" * 64
    mutated = SourceAuditReport.model_validate(payload, strict=True)

    assert mutated.report_id == original.report_id
    assert mutated.source_snapshot_date == original.source_snapshot_date
    assert report_logical_hash(mutated) != original_hash


def test_source_audit_report_exact_fields_and_declaration_order() -> None:
    report = SourceAuditReport.model_validate(_source_audit_payload(), strict=True)

    assert tuple(SourceAuditReport.model_fields) == (
        "report_id",
        "report_contract_version",
        "artifact_contract_version",
        "source_snapshot_date",
        "source_manifest_sha256",
        "schema_catalog_sha256",
        "source_tables",
        "silver_tables",
        "quarantine_source_rows",
        "exact_links",
        "exact_link_evidence",
        "exact_link_pair_sha256",
    )
    assert tuple(type(report.source_tables[0]).model_fields) == (
        "source_table",
        "expected_rows",
        "observed_rows",
        "expected_columns",
        "observed_columns",
        "expected_cells",
        "observed_cells",
    )
    assert tuple(type(report.silver_tables[0]).model_fields) == (
        "name",
        "expected",
        "observed",
    )
    assert tuple(type(report.quarantine_source_rows).model_fields) == (
        "expected",
        "observed",
    )
    assert tuple(type(report.exact_link_pair_sha256).model_fields) == (
        "expected",
        "observed",
    )


def test_source_audit_report_exact_semantic_projection() -> None:
    report = SourceAuditReport.model_validate(_source_audit_payload(), strict=True)

    projection = report.semantic_projection()

    assert tuple(projection) == tuple(SourceAuditReport.model_fields)
    assert projection == report.model_dump(mode="python", warnings="none")


@pytest.mark.parametrize(
    "case",
    [
        "report-id",
        "report-version",
        "artifact-version",
        "snapshot-date",
        "source-manifest-hash",
        "schema-catalog-hash",
        "source-order",
        "source-missing",
        "source-duplicate",
        "source-unknown",
        "silver-order",
        "silver-missing",
        "silver-duplicate",
        "silver-unknown",
        "negative-source-count",
        "negative-silver-count",
        "negative-plain-count",
        "source-row-inequality",
        "source-column-inequality",
        "source-cell-inequality",
        "silver-inequality",
        "plain-count-inequality",
        "sha-inequality",
    ],
)
def test_source_audit_report_rejects_every_inventory_and_inequality(
    case: str,
) -> None:
    payload = deepcopy(_source_audit_payload())
    source_tables = list(payload["source_tables"])
    silver_tables = list(payload["silver_tables"])
    if case == "report-id":
        payload["report_id"] = "other"
    elif case == "report-version":
        payload["report_contract_version"] = "2.0.0"
    elif case == "artifact-version":
        payload["artifact_contract_version"] = "2.0.0"
    elif case == "snapshot-date":
        payload["source_snapshot_date"] = date(2026, 7, 10)
    elif case == "source-manifest-hash":
        payload["source_manifest_sha256"] = "A" * 64
    elif case == "schema-catalog-hash":
        payload["schema_catalog_sha256"] = "short"
    elif case == "source-order":
        payload["source_tables"] = tuple(reversed(source_tables))
    elif case == "source-missing":
        payload["source_tables"] = tuple(source_tables[:-1])
    elif case == "source-duplicate":
        payload["source_tables"] = (*source_tables[:-1], source_tables[0])
    elif case == "source-unknown":
        source_tables[0]["source_table"] = "UNKNOWN"
    elif case == "silver-order":
        payload["silver_tables"] = tuple(reversed(silver_tables))
    elif case == "silver-missing":
        payload["silver_tables"] = tuple(silver_tables[:-1])
    elif case == "silver-duplicate":
        payload["silver_tables"] = (*silver_tables[:-1], silver_tables[0])
    elif case == "silver-unknown":
        silver_tables[0]["name"] = "unknown"
    elif case == "negative-source-count":
        source_tables[0]["expected_rows"] = -1
        source_tables[0]["observed_rows"] = -1
    elif case == "negative-silver-count":
        silver_tables[0]["expected"] = -1
        silver_tables[0]["observed"] = -1
    elif case == "negative-plain-count":
        payload["exact_links"] = {"expected": -1, "observed": -1}
    elif case == "source-row-inequality":
        source_tables[0]["observed_rows"] += 1
    elif case == "source-column-inequality":
        source_tables[0]["observed_columns"] += 1
    elif case == "source-cell-inequality":
        source_tables[0]["observed_cells"] += 1
    elif case == "silver-inequality":
        silver_tables[0]["observed"] += 1
    elif case == "plain-count-inequality":
        payload["exact_links"]["observed"] += 1
    else:
        payload["exact_link_pair_sha256"]["observed"] = "d" * 64

    payload["source_tables"] = (
        tuple(source_tables)
        if case
        in {
            "source-unknown",
            "negative-source-count",
            "source-row-inequality",
            "source-column-inequality",
            "source-cell-inequality",
        }
        else payload["source_tables"]
    )
    payload["silver_tables"] = (
        tuple(silver_tables)
        if case
        in {
            "silver-unknown",
            "negative-silver-count",
            "silver-inequality",
        }
        else payload["silver_tables"]
    )
    with pytest.raises(ValueError, match="validation error"):
        SourceAuditReport.model_validate(payload, strict=True)


def test_quality_summary_report_exact_fields_and_declaration_order() -> None:
    report = QualitySummaryReport.model_validate(_quality_summary_payload(), strict=True)

    assert tuple(QualitySummaryReport.model_fields) == (
        "report_id",
        "report_contract_version",
        "artifact_contract_version",
        "total_issues",
        "distinct_affected_source_rows",
        "by_source_table",
        "by_rule",
        "by_severity",
        "by_quality_status",
        "by_quarantine_flag",
        "quarantined_issue_count",
        "quarantined_source_row_count",
        "excluded_silver_records",
        "quality_table_logical_hash",
    )
    nested = (
        (report.by_source_table[0], ("source_table", "count")),
        (report.by_rule[0], ("rule_id", "rule_version", "count")),
        (report.by_severity[0], ("severity", "count")),
        (report.by_quality_status[0], ("quality_status", "count")),
        (report.by_quarantine_flag[0], ("value", "count")),
        (report.excluded_silver_records[0], ("grain", "count")),
    )
    for entry, fields in nested:
        assert tuple(type(entry).model_fields) == fields


def test_quality_summary_report_exact_semantic_projection() -> None:
    report = QualitySummaryReport.model_validate(_quality_summary_payload(), strict=True)

    projection = report.semantic_projection()

    assert tuple(projection) == tuple(QualitySummaryReport.model_fields)
    assert projection == report.model_dump(mode="python", warnings="none")


@pytest.mark.parametrize(
    "case",
    [
        "report-id",
        "report-version",
        "artifact-version",
        "negative-total",
        "negative-distinct",
        "negative-quarantined-issues",
        "negative-quarantined-rows",
        "uppercase-hash",
        "source-unknown",
        "source-zero",
        "source-order",
        "source-duplicate",
        "rule-empty-id",
        "rule-empty-version",
        "rule-zero",
        "rule-order",
        "rule-duplicate",
        "severity-zero",
        "severity-order",
        "severity-duplicate",
        "status-zero",
        "status-order",
        "status-duplicate",
        "flags-order",
        "flags-duplicate",
        "excluded-unknown",
        "excluded-zero",
        "excluded-order",
        "excluded-duplicate",
        "source-sum",
        "rule-sum",
        "severity-sum",
        "status-sum",
        "flags-sum",
        "true-quarantine-mismatch",
        "distinct-exceeds-total",
        "quarantined-rows-exceed-issues",
    ],
)
def test_quality_summary_rejects_group_order_duplicates_and_aggregate_mismatch(
    case: str,
) -> None:
    payload = deepcopy(_quality_summary_payload())
    if case == "report-id":
        payload["report_id"] = "other"
    elif case == "report-version":
        payload["report_contract_version"] = "2.0.0"
    elif case == "artifact-version":
        payload["artifact_contract_version"] = "2.0.0"
    elif case == "negative-total":
        payload["total_issues"] = -1
    elif case == "negative-distinct":
        payload["distinct_affected_source_rows"] = -1
    elif case == "negative-quarantined-issues":
        payload["quarantined_issue_count"] = -1
    elif case == "negative-quarantined-rows":
        payload["quarantined_source_row_count"] = -1
    elif case == "uppercase-hash":
        payload["quality_table_logical_hash"] = "D" * 64
    elif case.startswith("source-"):
        entries = list(payload["by_source_table"])
        if case == "source-unknown":
            entries[0]["source_table"] = "UNKNOWN"
        elif case == "source-zero":
            entries[0]["count"] = 0
        elif case == "source-order":
            entries.reverse()
        elif case == "source-duplicate":
            entries[1] = deepcopy(entries[0])
        else:
            entries[0]["count"] += 1
        payload["by_source_table"] = tuple(entries)
    elif case.startswith("rule-"):
        entries = list(payload["by_rule"])
        if case == "rule-empty-id":
            entries[0]["rule_id"] = ""
        elif case == "rule-empty-version":
            entries[0]["rule_version"] = ""
        elif case == "rule-zero":
            entries[0]["count"] = 0
        elif case == "rule-order":
            entries.reverse()
        elif case == "rule-duplicate":
            entries[1] = deepcopy(entries[0])
        else:
            entries[0]["count"] += 1
        payload["by_rule"] = tuple(entries)
    elif case.startswith("severity-"):
        entries = list(payload["by_severity"])
        if case == "severity-zero":
            entries[0]["count"] = 0
        elif case == "severity-order":
            entries.reverse()
        elif case == "severity-duplicate":
            entries[1] = deepcopy(entries[0])
        else:
            entries[0]["count"] += 1
        payload["by_severity"] = tuple(entries)
    elif case.startswith("status-"):
        entries = list(payload["by_quality_status"])
        if case == "status-zero":
            entries[0]["count"] = 0
        elif case == "status-order":
            entries.reverse()
        elif case == "status-duplicate":
            entries[1] = deepcopy(entries[0])
        else:
            entries[0]["count"] += 1
        payload["by_quality_status"] = tuple(entries)
    elif case.startswith("flags-"):
        entries = list(payload["by_quarantine_flag"])
        if case == "flags-order":
            entries.reverse()
        elif case == "flags-duplicate":
            entries[1] = deepcopy(entries[0])
        else:
            entries[0]["count"] += 1
        payload["by_quarantine_flag"] = tuple(entries)
    elif case.startswith("excluded-"):
        entries = list(payload["excluded_silver_records"])
        if case == "excluded-unknown":
            entries[0]["grain"] = "unknown"
        elif case == "excluded-zero":
            entries[0]["count"] = 0
        elif case == "excluded-order":
            entries.reverse()
        else:
            entries[1] = deepcopy(entries[0])
        payload["excluded_silver_records"] = tuple(entries)
    elif case == "true-quarantine-mismatch":
        payload["quarantined_issue_count"] = 1
    elif case == "distinct-exceeds-total":
        payload["distinct_affected_source_rows"] = 5
    else:
        payload["quarantined_source_row_count"] = 3

    with pytest.raises(ValueError, match="validation error"):
        QualitySummaryReport.model_validate(payload, strict=True)
