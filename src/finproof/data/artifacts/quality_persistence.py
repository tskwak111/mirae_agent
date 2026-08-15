"""Canonical D-021 quality persistence and bounded staged verification."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.parquet_io import StagedParquetSet
from finproof.data.artifacts.reports import (
    ExactLinkedSide,
    LinkedRecordJson,
    QualityJoinObservations,
)
from finproof.data.artifacts.serialization import serialize_table_row
from finproof.data.artifacts.staging import ExternalOrderJoinOperation, ExternalOrderStore
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.domain.quality import DataQualityIssue


def persist_quality_issue(
    issue: DataQualityIssue,
    *,
    persistence_timestamp: datetime,
) -> DataQualityIssue:
    """Attach the one exact build timestamp to an untimestamped domain issue."""
    if type(issue) is not DataQualityIssue or issue.first_detected_at is not None:
        raise TypeError("quality persistence requires one exact untimestamped issue")
    offset = persistence_timestamp.utcoffset() if type(persistence_timestamp) is datetime else None
    if (
        type(persistence_timestamp) is not datetime
        or persistence_timestamp.tzinfo is None
        or offset is None
        or offset.total_seconds() != 0
    ):
        raise ValueError("quality persistence timestamp must be exact aware UTC")
    payload = issue.model_dump(mode="python")
    payload["first_detected_at"] = persistence_timestamp
    return DataQualityIssue.model_validate(payload, strict=True)


class StagedBoundedRelationVerifier:
    """Stage-backed verifier over only owner-validated bounded table streams."""

    __slots__ = ("_store",)
    _store: ExternalOrderStore

    def __new__(cls) -> StagedBoundedRelationVerifier:
        raise TypeError("StagedBoundedRelationVerifier is store-issued")

    @classmethod
    def for_store(cls, store: ExternalOrderStore) -> StagedBoundedRelationVerifier:
        if type(store) is not ExternalOrderStore:
            raise TypeError("relation verifier requires the exact external-order store")
        value = object.__new__(cls)
        value._store = store
        return value

    def verify_quality_to_bronze(
        self,
        *,
        tables: StagedParquetSet,
    ) -> QualityJoinObservations:
        try:
            tuple(
                self._store.iter_join_batches(
                    operation=ExternalOrderJoinOperation.QUALITY_TO_BRONZE,
                    tables=tables,
                )
            )
            quality_rows = _iter_staged_rows(tables, "silver_quality_issue")
            bronze_rows = _iter_staged_rows(tables, "bronze_source_row")
            bronze_cells = _iter_staged_rows(tables, "bronze_source_cell")
            current_row = next(bronze_rows, None)
            current_cell = next(bronze_cells, None)
            total = affected = quarantined_issues = quarantined_rows = 0
            previous_source_key: tuple[object, ...] | None = None
            previous_quarantined_key: tuple[object, ...] | None = None
            for quality in quality_rows:
                source_key = _quality_source_key(quality)
                while current_row is not None and _bronze_row_key(current_row) < source_key:
                    current_row = next(bronze_rows, None)
                cell_key = (*source_key, quality["source_column_number"])
                while current_cell is not None and _bronze_cell_key(current_cell) < cell_key:
                    current_cell = next(bronze_cells, None)
                if (
                    current_row is None
                    or _bronze_row_key(current_row) != source_key
                    or current_cell is None
                    or _bronze_cell_key(current_cell) != cell_key
                ):
                    raise ValueError("quality issue does not match one Bronze row and cell")
                _validate_quality_join_match(
                    quality,
                    current_row,
                    current_cell,
                    tables.persistence_timestamp,
                )
                total += 1
                if source_key != previous_source_key:
                    affected += 1
                    previous_source_key = source_key
                if quality["quarantined"] is True:
                    quarantined_issues += 1
                    if source_key != previous_quarantined_key:
                        quarantined_rows += 1
                        previous_quarantined_key = source_key
            quality_verification = tables.verification_for("silver_quality_issue")
            return QualityJoinObservations(
                total_issues=total,
                distinct_issue_ids=total,
                matched_bronze_rows=total,
                matched_bronze_cells=total,
                distinct_affected_source_rows=affected,
                quarantined_issue_count=quarantined_issues,
                quarantined_source_row_count=quarantined_rows,
                persistence_timestamp=tables.persistence_timestamp,
                quality_table_logical_hash=quality_verification.logical.logical_hash,
            )
        except ArtifactContractError:
            raise
        except (AttributeError, KeyError, TypeError, ValidationError, ValueError) as exc:
            raise _quality_contract_error() from exc

    def verify_exact_evidence_to_bronze(self, *, tables: StagedParquetSet) -> None:
        del tables
        raise _quality_contract_error()

    def iter_linked_record_json(
        self,
        *,
        tables: StagedParquetSet,
        side: ExactLinkedSide,
        exact_ids: tuple[str, ...],
    ) -> Iterator[tuple[LinkedRecordJson, ...]]:
        del tables, side, exact_ids
        yield from ()
        raise _quality_contract_error()


def _iter_staged_rows(
    tables: StagedParquetSet,
    table_name: str,
) -> Iterator[dict[str, Any]]:
    verification = tables.verification_for(table_name)
    with verification.handle.iter_batches(batch_size=65_536) as batches:
        for batch in batches:
            for row in batch.to_pylist():
                if type(row) is not dict:
                    raise ValueError("staged relation row is not a mapping")
                yield row


def _quality_source_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        row["source_table"],
        row["source_file"],
        row["source_sheet"],
        row["source_row_number"],
    )


def _bronze_row_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        row["source_table"],
        row["source_file"],
        row["source_sheet"],
        row["source_row_number"],
    )


def _bronze_cell_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (*_bronze_row_key(row), row["source_column_number"])


def _validate_quality_join_match(
    quality: Mapping[str, object],
    bronze_row: Mapping[str, object],
    bronze_cell: Mapping[str, object],
    timestamp: datetime,
) -> None:
    for name in (
        "source_table",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_column_name",
        "source_column_number",
        "source_column_letter",
        "source_checksum",
        "source_snapshot_date",
    ):
        counterpart = bronze_cell[name] if name in bronze_cell else bronze_row[name]
        if quality[name] != counterpart:
            raise ValueError("quality source locator does not match Bronze")
    if (
        quality["source_applicable_date"] != bronze_cell["source_applicable_date"]
        or quality["raw_payload_sha256"] != bronze_row["raw_payload_sha256"]
        or quality["first_detected_at"] != timestamp
        or bronze_row["loaded_at"] != timestamp
    ):
        raise ValueError("quality row facts do not match Bronze")
    record_json = quality["record_json"]
    if type(record_json) is not str:
        raise ValueError("quality record_json is not exact")
    parsed = DataQualityIssue.model_validate_json(record_json)
    expected = serialize_table_row(TABLE_SPEC_BY_NAME["silver_quality_issue"], parsed)
    if dict(expected) != dict(quality):
        raise ValueError("quality record_json and typed projection disagree")


def _quality_contract_error() -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.SERIALIZATION_FAILED,
        operation_id="quality-relation",
    )
