"""Canonical D-021 quality persistence and bounded staged verification."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError as JsonSchemaSchemaError
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.parquet_io import StagedParquetSet
from finproof.data.artifacts.reports import (
    ExactEvidenceBronzeJoinObservations,
    ExactLinkedSide,
    LinkedRecordJson,
    QualityJoinObservations,
)
from finproof.data.artifacts.resources import quality_issue_schema_bytes
from finproof.data.artifacts.serialization import serialize_table_row
from finproof.data.artifacts.staging import (
    ExactLinkCandidateStoreCustody,
    ExternalOrderJoinOperation,
    ExternalOrderJoinRow,
    ExternalOrderStore,
)
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.data.source_manifest import OFFICIAL_TABLE_IDS
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
    persisted = DataQualityIssue.model_validate(payload, strict=True)
    try:
        schema = json.loads(quality_issue_schema_bytes())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(persisted.model_dump(mode="json"))
    except (
        json.JSONDecodeError,
        JsonSchemaSchemaError,
        JsonSchemaValidationError,
        TypeError,
    ) as exc:
        raise ValueError("quality issue schema validation failed") from exc
    return persisted


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

    @classmethod
    def for_candidate_custody(
        cls,
        custody: ExactLinkCandidateStoreCustody,
    ) -> StagedBoundedRelationVerifier:
        del cls
        if type(custody) is not ExactLinkCandidateStoreCustody:
            raise TypeError("relation verifier requires exact candidate custody")
        custody._require_live()
        if (
            custody._candidate_state != "EXHAUSTED"
            or custody._evidence_state != "SEALED"
            or custody._verifier_issued
        ):
            raise ValueError("candidate custody is not sealed for verifier issuance")
        value = object.__new__(StagedBoundedRelationVerifier)
        value._store = custody._store
        custody._verifier_issued = True
        return value

    def verify_quality_to_bronze(
        self,
        *,
        tables: StagedParquetSet,
    ) -> QualityJoinObservations:
        try:
            total = affected = quarantined_issues = quarantined_rows = 0
            previous_key: tuple[str | int, ...] | None = None
            previous_source_key: tuple[str | int, ...] | None = None
            previous_quarantined_key: tuple[str | int, ...] | None = None
            for batch in self._store.iter_join_batches(
                operation=ExternalOrderJoinOperation.QUALITY_TO_BRONZE,
                tables=tables,
            ):
                if type(batch) is not tuple or len(batch) > 65_536:
                    raise ValueError("quality join batch is not bounded")
                for joined in batch:
                    if (
                        type(joined) is not ExternalOrderJoinRow
                        or len(joined.key) != 7
                        or len(joined.values) != 3
                    ):
                        raise ValueError("quality join row is not exact")
                    record_json, quarantined, matched = joined.values
                    if (
                        type(record_json) is not str
                        or type(quarantined) is not int
                        or quarantined not in (0, 1)
                        or type(matched) is not int
                        or matched != 1
                        or (previous_key is not None and joined.key <= previous_key)
                    ):
                        raise ValueError("quality join facts are invalid")
                    issue = DataQualityIssue.model_validate_json(record_json, strict=True)
                    source = issue.source
                    expected_key = (
                        OFFICIAL_TABLE_IDS.index(source.source_table),
                        source.source_file.as_posix(),
                        source.source_sheet,
                        source.source_row_number,
                        source.source_column_number,
                        issue.rule_id,
                        issue.issue_id,
                    )
                    expected = serialize_table_row(
                        TABLE_SPEC_BY_NAME["silver_quality_issue"],
                        issue,
                    )
                    if (
                        joined.key != expected_key
                        or quarantined != int(issue.quarantined)
                        or issue.first_detected_at != tables.persistence_timestamp
                        or expected["record_json"] != record_json
                    ):
                        raise ValueError("quality join projection is inconsistent")
                    total += 1
                    source_key = joined.key[:4]
                    if source_key != previous_source_key:
                        affected += 1
                        previous_source_key = source_key
                    if quarantined == 1:
                        quarantined_issues += 1
                        if source_key != previous_quarantined_key:
                            quarantined_rows += 1
                            previous_quarantined_key = source_key
                    previous_key = joined.key
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

    def verify_exact_evidence_to_bronze(
        self,
        *,
        tables: StagedParquetSet,
    ) -> ExactEvidenceBronzeJoinObservations:
        try:
            previous_key: tuple[str | int, ...] | None = None
            matched_bronze_cells = 0
            max_batch_rows = 0
            for batch in self._store.iter_join_batches(
                operation=ExternalOrderJoinOperation.EXACT_EVIDENCE_TO_BRONZE,
                tables=tables,
            ):
                if type(batch) is not tuple or len(batch) > 65_536:
                    raise ValueError("evidence join batch is not bounded")
                max_batch_rows = max(max_batch_rows, len(batch))
                for joined in batch:
                    if (
                        type(joined) is not ExternalOrderJoinRow
                        or len(joined.key) != 3
                        or type(joined.key[0]) is not str
                        or type(joined.key[1]) is not int
                        or type(joined.key[2]) is not int
                        or len(joined.values) != 2
                        or type(joined.values[0]) is not str
                        or type(joined.values[1]) is not int
                        or joined.values[1] != 1
                        or (previous_key is not None and joined.key <= previous_key)
                    ):
                        raise ValueError("evidence join row is invalid")
                    previous_key = joined.key
                    matched_bronze_cells += 1
            return ExactEvidenceBronzeJoinObservations(
                matched_bronze_cells=matched_bronze_cells,
                max_batch_rows=max_batch_rows,
            )
        except ArtifactContractError:
            raise
        except (AttributeError, TypeError, ValueError) as exc:
            raise _quality_contract_error() from exc

    def iter_linked_record_json(
        self,
        *,
        tables: StagedParquetSet,
        side: ExactLinkedSide,
        exact_ids: tuple[str, ...],
    ) -> Iterator[tuple[LinkedRecordJson, ...]]:
        try:
            if type(side) is not ExactLinkedSide:
                raise TypeError("linked side is not exact")
            if (
                type(exact_ids) is not tuple
                or any(type(value) is not str or not value for value in exact_ids)
                or tuple(sorted(set(exact_ids))) != exact_ids
            ):
                raise ValueError("linked IDs are not canonical")
            operation = (
                ExternalOrderJoinOperation.LINKED_DOMESTIC_RECORD_JSON
                if side is ExactLinkedSide.DOMESTIC
                else ExternalOrderJoinOperation.LINKED_FUND_RECORD_JSON
            )
            observed_ids: list[str] = []
            for batch in self._store.iter_join_batches(
                operation=operation,
                tables=tables,
                exact_ids=exact_ids,
            ):
                if type(batch) is not tuple or len(batch) > 65_536:
                    raise ValueError("linked record batch is not bounded")
                converted: list[LinkedRecordJson] = []
                for joined in batch:
                    if (
                        type(joined) is not ExternalOrderJoinRow
                        or len(joined.key) != 1
                        or type(joined.key[0]) is not str
                        or len(joined.values) != 1
                        or type(joined.values[0]) is not str
                        or (observed_ids and joined.key[0] <= observed_ids[-1])
                    ):
                        raise ValueError("linked record row is invalid")
                    observed_ids.append(joined.key[0])
                    converted.append(
                        LinkedRecordJson(
                            product_id=joined.key[0],
                            record_json=joined.values[0],
                        )
                    )
                yield tuple(converted)
            if tuple(observed_ids) != exact_ids:
                raise ValueError("linked record IDs are incomplete")
        except ArtifactContractError:
            raise
        except (AttributeError, TypeError, ValueError) as exc:
            raise _quality_contract_error() from exc


def _quality_contract_error() -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.SERIALIZATION_FAILED,
        operation_id="quality-relation",
    )
