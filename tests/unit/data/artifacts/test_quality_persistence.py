"""Persisted D-021 quality and bounded relation contracts."""

# ruff: noqa: E501

import json
from copy import copy
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from finproof.data.artifacts.quality_persistence import persist_quality_issue
from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from tests.helpers.artifacts import artifact_build_input_identity, artifact_staging_settings
from tests.helpers.source_rows import source_row


def _issue() -> DataQualityIssue:
    row = source_row("PRBD01N001", excel_row=2)
    return DataQualityIssue.from_row(
        row,
        "PD_NM",
        rule_id="fixture.rule",
        rule_version="1.0.0",
        severity=IssueSeverity.WARNING,
        quality_status=QualityStatus.INVALID_FORMAT,
        reason="Fixture issue.",
        quarantined=True,
    )


def _empty_staged_set(session: Any, *, count: int = 9) -> Any:
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    verifications = []
    for spec in TABLE_SPECS[:count]:
        leaf = session.claim_parquet_leaf(spec)
        ParquetBatchWriter(spec, leaf).close()
        verifications.append(verify_staged_parquet_table(owner=session, leaf=leaf, spec=spec))
    return StagedParquetSet.from_verified(owner=session, verifications=tuple(verifications))


def _quality_staged_set(session: Any, *, case: str = "valid") -> Any:
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.serialization import (
        BronzeSourceCellRecord,
        serialize_bronze_source_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    timestamp = session.persistence_timestamp
    source = source_row("PRBD01N001", excel_row=2)
    persisted = persist_quality_issue(_issue(), persistence_timestamp=timestamp)
    cell = source.cell("PD_NM")
    cell_record = BronzeSourceCellRecord(
        source_table_order=0,
        source_table=source.source_table,
        source_file=source.source_file,
        source_sheet=source.source_sheet,
        source_row_number=source.source_row_number,
        source_column_name=cell.column_name,
        source_column_number=cell.excel_column_number,
        source_column_letter=cell.excel_column_letter,
        source_checksum=source.source_checksum,
        source_snapshot_date=source.source_snapshot_date,
        source_applicable_date=cell.applicable_date,
        raw_value=cell.raw_value,
    )
    row_by_table: dict[str, tuple[object, ...]] = {
        "bronze_source_row": (
            dict(
                serialize_bronze_source_row(
                    TABLE_SPEC_BY_NAME["bronze_source_row"],
                    source,
                    persistence_timestamp=timestamp,
                )
            ),
        ),
        "bronze_source_cell": (
            dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["bronze_source_cell"],
                    cell_record,
                )
            ),
        ),
        "silver_quality_issue": (
            dict(serialize_table_row(TABLE_SPEC_BY_NAME["silver_quality_issue"], persisted)),
        ),
    }
    if case == "missing-row":
        row_by_table["bronze_source_row"] = ()
    elif case == "missing-cell":
        row_by_table["bronze_source_cell"] = ()
    elif case == "raw-hash":
        row_by_table["bronze_source_row"][0]["raw_payload_sha256"] = "b" * 64  # type: ignore[index]
    elif case == "timestamp":
        row_by_table["bronze_source_row"][0]["loaded_at"] = datetime(  # type: ignore[index]
            2026, 8, 16, tzinfo=UTC
        )
    elif case == "record-json":
        changed = persisted.model_copy(update={"reason": "Changed reason."})
        row_by_table["silver_quality_issue"][0]["record_json"] = canonical_record_json(  # type: ignore[index]
            changed
        )

    verifications = []
    for spec in TABLE_SPECS[:9]:
        leaf = session.claim_parquet_leaf(spec)
        writer = ParquetBatchWriter(spec, leaf)
        rows = row_by_table.get(spec.table_name, ())
        if rows:
            writer.write_batch(rows)
        writer.close()
        verifications.append(verify_staged_parquet_table(owner=session, leaf=leaf, spec=spec))
    return StagedParquetSet.from_verified(owner=session, verifications=tuple(verifications))


def test_quality_persistence_accepts_only_exact_untimestamped_data_quality_issue_and_utc_build_time() -> (
    None
):
    issue = _issue()
    timestamp = datetime(2026, 8, 15, tzinfo=UTC)

    persisted = persist_quality_issue(issue, persistence_timestamp=timestamp)

    assert type(persisted) is DataQualityIssue
    assert persisted is not issue
    assert persisted.first_detected_at is timestamp
    invalid_inputs = (
        (issue.model_dump(mode="python"), timestamp),
        (issue.model_copy(update={"first_detected_at": timestamp}), timestamp),
        (issue, datetime(2026, 8, 15)),
        (issue, datetime(2026, 8, 15, tzinfo=timezone(timedelta(hours=9)))),
    )
    for supplied_issue, supplied_timestamp in invalid_inputs:
        with pytest.raises((TypeError, ValueError)):
            persist_quality_issue(
                supplied_issue,  # type: ignore[arg-type]
                persistence_timestamp=supplied_timestamp,
            )


def test_persisted_quality_row_and_record_json_match_exact_d021_schema() -> None:
    persisted = persist_quality_issue(
        _issue(),
        persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
    )

    row = serialize_table_row(TABLE_SPEC_BY_NAME["silver_quality_issue"], persisted)
    record_json = row["record_json"]

    assert record_json == canonical_record_json(persisted)
    assert isinstance(record_json, str)
    assert '"first_detected_at":"2026-08-15T00:00:00Z"' in record_json
    schema_path = Path(__file__).resolve().parents[4] / "schemas/quality_issue.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(json.loads(record_json))


def test_quality_relation_external_sort_is_unique_and_globally_ordered(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderRelation,
        ExternalOrderRow,
    )

    issues = tuple(
        persist_quality_issue(
            DataQualityIssue.from_row(
                source_row("PRBD01N001", excel_row=row_number),
                "PD_NM",
                rule_id="fixture.rule",
                rule_version="1.0.0",
                severity=IssueSeverity.WARNING,
                quality_status=QualityStatus.INVALID_FORMAT,
                reason="Fixture issue.",
                quarantined=True,
            ),
            persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
        )
        for row_number in (10, 2, 7)
    )

    def ordered_row(issue: DataQualityIssue) -> ExternalOrderRow:
        source = issue.source
        return ExternalOrderRow(
            key=(
                0,
                source.source_file.as_posix(),
                source.source_sheet,
                source.source_row_number,
                source.source_column_number,
                issue.rule_id,
                issue.issue_id,
            ),
            payload_json=canonical_record_json(issue),
        )

    settings = artifact_staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=artifact_build_input_identity(settings),
        ) as session,
        session.open_external_order_store(config=config) as store,
    ):
        rows = tuple(ordered_row(issue) for issue in issues)
        store.insert_batch(relation=ExternalOrderRelation.SILVER_QUALITY_ISSUE, rows=rows)
        ordered = tuple(
            row
            for batch in store.iter_ordered_batches(
                relation=ExternalOrderRelation.SILVER_QUALITY_ISSUE
            )
            for row in batch
        )
        assert tuple(row.key for row in ordered) == tuple(sorted(row.key for row in rows))
        with pytest.raises(ArtifactContractError):
            store.insert_batch(
                relation=ExternalOrderRelation.SILVER_QUALITY_ISSUE,
                rows=(rows[0],),
            )


def test_quality_join_observations_are_immutable_strict_and_internally_consistent() -> None:
    from finproof.data.artifacts.reports import QualityJoinObservations

    payload = {
        "total_issues": 3,
        "distinct_issue_ids": 3,
        "matched_bronze_rows": 3,
        "matched_bronze_cells": 3,
        "distinct_affected_source_rows": 2,
        "quarantined_issue_count": 2,
        "quarantined_source_row_count": 1,
        "persistence_timestamp": datetime(2026, 8, 15, tzinfo=UTC),
        "quality_table_logical_hash": "a" * 64,
    }
    observed = QualityJoinObservations.model_validate(payload, strict=True)
    assert observed.total_issues == 3
    with pytest.raises(ValidationError):
        observed.total_issues = 4
    invalid = (
        {"total_issues": True},
        {"total_issues": -1},
        {"distinct_issue_ids": 2},
        {"matched_bronze_rows": 2},
        {"matched_bronze_cells": 2},
        {"distinct_affected_source_rows": 4},
        {"quarantined_issue_count": 4},
        {"quarantined_source_row_count": 3},
        {"persistence_timestamp": datetime(2026, 8, 15)},
        {"quality_table_logical_hash": "A" * 64},
    )
    for update in invalid:
        with pytest.raises(ValidationError):
            QualityJoinObservations.model_validate(payload | update, strict=True)


def test_quality_relation_rejects_foreign_copied_incomplete_reordered_closed_or_timestamp_mismatched_set(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.parquet_io import StagedParquetSet
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderJoinOperation,
    )

    def forged(tables: Any, **updates: object) -> Any:
        value = object.__new__(StagedParquetSet)
        for name in (
            "_owner",
            "_registration_token",
            "verifications",
            "handles",
            "persistence_timestamp",
        ):
            object.__setattr__(value, name, updates.get(name, getattr(tables, name)))
        return value

    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    settings = artifact_staging_settings(tmp_path / "repository")
    foreign_settings = artifact_staging_settings(tmp_path / "foreign-repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    options = ArtifactBuildOptions(persistence_timestamp=timestamp)
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            options,
            input_identity=artifact_build_input_identity(settings),
        ) as session,
        session.open_external_order_store(config=config) as store,
    ):
        tables = _empty_staged_set(session)
        with ArtifactBuildSession.initialize(
            foreign_settings,
            VersionBundle(),
            options,
            input_identity=artifact_build_input_identity(foreign_settings),
        ) as foreign_owner:
            foreign = _empty_staged_set(foreign_owner)
            with pytest.raises(ArtifactContractError):
                tuple(
                    store.iter_join_batches(
                        operation=ExternalOrderJoinOperation.QUALITY_TO_BRONZE,
                        tables=foreign,
                    )
                )

        invalid = (
            copy(tables),
            forged(
                tables,
                verifications=tables.verifications[:3],
                handles=tables.handles[:3],
            ),
            forged(
                tables,
                verifications=tables.verifications[::-1],
                handles=tables.handles[::-1],
            ),
            foreign,
            forged(
                tables,
                persistence_timestamp=datetime(2026, 8, 16, tzinfo=UTC),
            ),
        )
        for supplied in invalid:
            with pytest.raises(ArtifactContractError):
                tuple(
                    store.iter_join_batches(
                        operation=ExternalOrderJoinOperation.QUALITY_TO_BRONZE,
                        tables=supplied,
                    )
                )


def test_quality_relation_rejects_missing_row_cell_raw_hash_timestamp_and_record_json_mismatches(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.quality_persistence import StagedBoundedRelationVerifier
    from finproof.data.artifacts.staging import ArtifactBuildSession

    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    for case in ("valid", "missing-row", "missing-cell", "raw-hash", "timestamp", "record-json"):
        settings = artifact_staging_settings(tmp_path / case / "repository")
        with (
            ArtifactBuildSession.initialize(
                settings,
                VersionBundle(),
                ArtifactBuildOptions(persistence_timestamp=timestamp),
                input_identity=artifact_build_input_identity(settings),
            ) as session,
            session.open_external_order_store(config=config) as store,
        ):
            verifier = StagedBoundedRelationVerifier.for_store(store)
            if case == "valid":
                observations = verifier.verify_quality_to_bronze(
                    tables=_quality_staged_set(session)
                )
                assert observations.total_issues == 1
                assert observations.matched_bronze_rows == 1
                assert observations.matched_bronze_cells == 1
            else:

                def verify_invalid_case(
                    case_value: str = case,
                    session_value: ArtifactBuildSession = session,
                    verifier_value: StagedBoundedRelationVerifier = verifier,
                ) -> None:
                    tables = _quality_staged_set(session_value, case=case_value)
                    verifier_value.verify_quality_to_bronze(tables=tables)

                with pytest.raises((ArtifactContractError, ValueError)):
                    verify_invalid_case()
