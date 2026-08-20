"""Strict timestamp-free semantic artifact reports."""

from __future__ import annotations

import hashlib
import re
import tempfile
from collections import defaultdict
from collections.abc import Generator, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Annotated, Literal, Protocol, Self, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.data.artifacts.expected_contract import ExpectedSemanticReport
from finproof.data.artifacts.hashing import report_logical_hash
from finproof.data.artifacts.manifest import (
    ArtifactManifest,
    ReportVerificationResult,
    TableVerificationResult,
    VerifiedPhysicalInventory,
)
from finproof.data.artifacts.parquet_io import (
    VerifiedParquetTable,
    _open_final_verified_batches,
)
from finproof.data.artifacts.serialization import (
    ExactCrossSourceLinkEvidenceRecord,
    logical_table_row,
    serialize_table_row,
)
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.data.source_manifest import OFFICIAL_TABLE_IDS
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus

if TYPE_CHECKING:
    from finproof.data.artifacts.parquet_io import StagedParquetSet
    from finproof.data.artifacts.serialization import ExactCrossSourceLinkEvidenceRecord

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmptyText = Annotated[str, Field(min_length=1)]


class ExactLinkedSide(StrEnum):
    """Closed link-side inventory used by the CP6-compatible verifier port."""

    DOMESTIC = "domestic"
    FUND = "fund"


@dataclass(frozen=True, slots=True)
class LinkedRecordJson:
    """One bounded linked-product record projection."""

    product_id: str
    record_json: str


class ExactEvidenceBronzeJoinObservations(BaseModel):
    """Measured bounded facts from the exact evidence-to-Bronze relation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    matched_bronze_cells: NonNegativeInt
    max_batch_rows: NonNegativeInt

    @model_validator(mode="after")
    def require_closed_batch_bound(self) -> Self:
        if self.max_batch_rows > 65_536:
            raise ValueError("exact evidence relation batch bound changed")
        return self


class BoundedRelationVerifier(Protocol):
    """Closed bounded verification port shared by CP5 and CP6."""

    def verify_quality_to_bronze(
        self,
        *,
        tables: StagedParquetSet,
    ) -> QualityJoinObservations: ...

    def verify_exact_evidence_to_bronze(
        self,
        *,
        tables: StagedParquetSet,
        gold_evidence: tuple[ExactCrossSourceLinkEvidenceRecord, ...],
    ) -> ExactEvidenceBronzeJoinObservations: ...

    def iter_linked_record_json(
        self,
        *,
        tables: StagedParquetSet,
        side: ExactLinkedSide,
        exact_ids: tuple[str, ...],
    ) -> Iterator[tuple[LinkedRecordJson, ...]]: ...


class _FinalRelationIssuance:
    __slots__ = ("inventory", "tables", "value")

    def __init__(
        self,
        value: _FinalInventoryRelationVerifier,
        *,
        inventory: VerifiedPhysicalInventory,
        tables: TableVerificationResult,
    ) -> None:
        self.value = value
        self.inventory = inventory
        self.tables = tables


class _FinalInventoryRelationVerifier:
    """Bounded relations issued only from exact final-inventory table handles."""

    __slots__ = ("_inventory", "_issuance", "_max_batch_rows", "_tables")

    _inventory: VerifiedPhysicalInventory
    _issuance: _FinalRelationIssuance
    _max_batch_rows: int
    _tables: TableVerificationResult

    def __new__(cls) -> _FinalInventoryRelationVerifier:
        raise TypeError("final inventory verifier requires _from_verified")

    @classmethod
    def _from_verified(
        cls,
        *,
        inventory: VerifiedPhysicalInventory,
        tables: TableVerificationResult,
    ) -> _FinalInventoryRelationVerifier:
        if (
            type(inventory) is not VerifiedPhysicalInventory
            or type(tables) is not TableVerificationResult
        ):
            raise TypeError("final inventory requires exact inventory and table result")
        tables.validate_against(inventory)
        if any(type(handle) is not VerifiedParquetTable for handle in tables.handles):
            raise TypeError("final inventory requires exact final table handles")
        value = object.__new__(cls)
        value._inventory = inventory
        value._tables = tables
        value._max_batch_rows = 0
        value._issuance = _FinalRelationIssuance(
            value,
            inventory=inventory,
            tables=tables,
        )
        return value

    def _require_live(self) -> None:
        if (
            type(self._issuance) is not _FinalRelationIssuance
            or self._issuance.value is not self
            or self._issuance.inventory is not self._inventory
            or self._issuance.tables is not self._tables
        ):
            raise ValueError("final inventory verifier changed")
        self._tables.validate_against(self._inventory)

    def _iter_rows(
        self,
        table_name: str,
        *,
        _batch_maximum: list[int] | None = None,
    ) -> Generator[dict[str, object], None, None]:
        self._require_live()
        spec = TABLE_SPEC_BY_NAME[table_name]
        handle = next(
            candidate for candidate in self._tables.handles if candidate.table_name == table_name
        )
        if type(handle) is not VerifiedParquetTable:
            raise TypeError("final inventory handle changed")
        with _open_final_verified_batches(
            inventory=self._inventory,
            tables=self._tables,
            spec=spec,
            handle=handle,
        ) as batches:
            for batch in batches:
                if batch.num_rows > 65_536:
                    raise ValueError("final relation batch is not bounded")
                self._max_batch_rows = max(self._max_batch_rows, batch.num_rows)
                if _batch_maximum is not None:
                    _batch_maximum[0] = max(_batch_maximum[0], batch.num_rows)
                for row in batch.to_pylist():
                    yield cast(dict[str, object], row)

    def _iter_exact_id_rows(
        self,
        *,
        table_name: str,
        id_column: str,
        exact_ids: tuple[str, ...],
    ) -> Generator[dict[str, object], None, None]:
        self._require_live()
        spec = TABLE_SPEC_BY_NAME[table_name]
        handle = next(
            candidate for candidate in self._tables.handles if candidate.table_name == table_name
        )
        if type(handle) is not VerifiedParquetTable:
            raise TypeError("final inventory handle changed")
        wanted = pa.array(exact_ids, type=pa.string())
        with _open_final_verified_batches(
            inventory=self._inventory,
            tables=self._tables,
            spec=spec,
            handle=handle,
        ) as batches:
            for batch in batches:
                if batch.num_rows > 65_536:
                    raise ValueError("final relation batch is not bounded")
                self._max_batch_rows = max(self._max_batch_rows, batch.num_rows)
                selected = batch.filter(pc.is_in(batch.column(id_column), value_set=wanted))
                for row in selected.to_pylist():
                    yield cast(dict[str, object], row)

    @property
    def max_batch_rows(self) -> int:
        """Largest reopened final relation batch observed by this verifier."""
        self._require_live()
        return self._max_batch_rows

    @staticmethod
    def _advance_to(
        iterator: Iterator[dict[str, object]],
        current: dict[str, object] | None,
        *,
        key: tuple[object, ...],
        fields: tuple[str, ...],
    ) -> dict[str, object] | None:
        while current is not None and tuple(current[field] for field in fields) < key:
            current = next(iterator, None)
        return current

    def verify_quality_to_bronze(self) -> QualityJoinObservations:
        self._require_live()
        row_fields = (
            "source_table_order",
            "source_file",
            "source_sheet",
            "source_row_number",
        )
        cell_fields = (*row_fields, "source_column_number")
        bronze_rows = self._iter_rows("bronze_source_row")
        bronze_cells = self._iter_rows("bronze_source_cell")
        quality_rows = self._iter_rows("silver_quality_issue")
        current_row = next(bronze_rows, None)
        current_cell = next(bronze_cells, None)
        total = affected = quarantined_issues = quarantined_rows = 0
        previous_source: tuple[object, ...] | None = None
        previous_quarantined: tuple[object, ...] | None = None
        timestamp: datetime | None = None
        previous_quality_key: tuple[object, ...] | None = None
        try:
            for physical in quality_rows:
                record_json = physical.get("record_json")
                if type(record_json) is not str:
                    raise ValueError("quality record_json is not exact")
                issue = DataQualityIssue.model_validate_json(record_json, strict=True)
                expected = serialize_table_row(
                    TABLE_SPEC_BY_NAME["silver_quality_issue"],
                    issue,
                )
                if expected != physical or issue.first_detected_at is None:
                    raise ValueError("quality physical and canonical rows differ")
                source = issue.source
                row_key = (
                    OFFICIAL_TABLE_IDS.index(source.source_table),
                    source.source_file.as_posix(),
                    source.source_sheet,
                    source.source_row_number,
                )
                cell_key = (*row_key, source.source_column_number)
                quality_key = (*cell_key, issue.rule_id, issue.issue_id)
                if previous_quality_key is not None and quality_key <= previous_quality_key:
                    raise ValueError("quality rows are not strictly ordered")
                current_row = self._advance_to(
                    bronze_rows,
                    current_row,
                    key=row_key,
                    fields=row_fields,
                )
                current_cell = self._advance_to(
                    bronze_cells,
                    current_cell,
                    key=cell_key,
                    fields=cell_fields,
                )
                if (
                    current_row is None
                    or current_cell is None
                    or tuple(current_row[field] for field in row_fields) != row_key
                    or tuple(current_cell[field] for field in cell_fields) != cell_key
                    or current_row["source_table"] != source.source_table
                    or current_cell["source_table"] != source.source_table
                    or current_row["source_checksum"] != source.source_checksum
                    or current_cell["source_checksum"] != source.source_checksum
                    or current_row["source_snapshot_date"] != source.source_snapshot_date
                    or current_cell["source_snapshot_date"] != source.source_snapshot_date
                    or current_cell["source_column_name"] != source.source_column_name
                    or current_cell["source_column_letter"] != source.source_column_letter
                    or current_cell["source_applicable_date"] != source.source_applicable_date
                    or current_row["raw_payload_sha256"] != physical["raw_payload_sha256"]
                    or current_row["loaded_at"] != issue.first_detected_at
                ):
                    raise ValueError("quality row does not match exact Bronze evidence")
                if timestamp is None:
                    timestamp = issue.first_detected_at
                elif timestamp != issue.first_detected_at:
                    raise ValueError("quality persistence timestamp changed")
                total += 1
                if row_key != previous_source:
                    affected += 1
                    previous_source = row_key
                if issue.quarantined:
                    quarantined_issues += 1
                    if row_key != previous_quarantined:
                        quarantined_rows += 1
                        previous_quarantined = row_key
                previous_quality_key = quality_key
        finally:
            quality_rows.close()
            bronze_rows.close()
            bronze_cells.close()
        if timestamp is None:
            empty_timestamp = None if current_row is None else current_row.get("loaded_at")
            if type(empty_timestamp) is not datetime:
                raise ValueError("quality relation has no persistence timestamp")
            timestamp = empty_timestamp
        quality_handle = next(
            handle for handle in self._tables.handles if handle.table_name == "silver_quality_issue"
        )
        return QualityJoinObservations(
            total_issues=total,
            distinct_issue_ids=total,
            matched_bronze_rows=total,
            matched_bronze_cells=total,
            distinct_affected_source_rows=affected,
            quarantined_issue_count=quarantined_issues,
            quarantined_source_row_count=quarantined_rows,
            persistence_timestamp=timestamp,
            quality_table_logical_hash=quality_handle.logical_hash,
        )

    def verify_exact_evidence_to_bronze(self) -> ExactEvidenceBronzeJoinObservations:
        self._require_live()
        batch_maximum = [0]
        cell_fields = (
            "source_table_order",
            "source_file",
            "source_sheet",
            "source_row_number",
            "source_column_number",
        )
        evidence_rows = self._iter_rows(
            "gold_exact_cross_source_link_evidence",
            _batch_maximum=batch_maximum,
        )
        previous: tuple[object, ...] | None = None
        evidence_by_cell: dict[tuple[object, ...], list[ExactCrossSourceLinkEvidenceRecord]] = {}
        try:
            for physical in evidence_rows:
                payload = dict(physical)
                payload["source_file"] = PurePosixPath(cast(str, payload["source_file"]))
                evidence = ExactCrossSourceLinkEvidenceRecord.model_validate(
                    payload,
                    strict=True,
                )
                if (
                    serialize_table_row(
                        TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"],
                        evidence,
                    )
                    != physical
                ):
                    raise ValueError("exact evidence physical row is not canonical")
                key = (
                    evidence.link_id,
                    evidence.evidence_role_order,
                    evidence.evidence_ordinal,
                )
                if previous is not None and key <= previous:
                    raise ValueError("exact evidence rows are not strictly ordered")
                cell_key = (
                    OFFICIAL_TABLE_IDS.index(evidence.source_table),
                    evidence.source_file.as_posix(),
                    evidence.source_sheet,
                    evidence.source_row_number,
                    evidence.source_column_number,
                )
                evidence_by_cell.setdefault(cell_key, []).append(evidence)
                if sum(map(len, evidence_by_cell.values())) > 371:
                    raise ValueError("exact evidence key bound exceeded")
                previous = key
        finally:
            evidence_rows.close()

        matched = 0
        bronze_cells = self._iter_rows(
            "bronze_source_cell",
            _batch_maximum=batch_maximum,
        )
        try:
            for current_cell in bronze_cells:
                bronze_key = tuple(current_cell[field] for field in cell_fields)
                expected = evidence_by_cell.pop(bronze_key, None)
                if expected is None:
                    continue
                for evidence in expected:
                    if (
                        current_cell["source_table"] != evidence.source_table
                        or current_cell["source_column_name"] != evidence.source_column_name
                        or current_cell["source_column_letter"] != evidence.source_column_letter
                        or current_cell["source_checksum"] != evidence.source_checksum
                        or current_cell["source_snapshot_date"] != evidence.source_snapshot_date
                        or current_cell["source_applicable_date"] != evidence.source_applicable_date
                        or current_cell["raw_value"] != evidence.raw_identifier
                    ):
                        raise ValueError("exact evidence does not match one Bronze cell")
                    matched += 1
        finally:
            bronze_cells.close()
        if evidence_by_cell:
            raise ValueError("exact evidence does not match one Bronze cell")
        return ExactEvidenceBronzeJoinObservations(
            matched_bronze_cells=matched,
            max_batch_rows=batch_maximum[0],
        )

    def iter_linked_record_json(
        self,
        *,
        side: ExactLinkedSide,
        exact_ids: tuple[str, ...],
    ) -> Iterator[tuple[LinkedRecordJson, ...]]:
        self._require_live()
        if type(side) is not ExactLinkedSide:
            raise TypeError("linked side is not exact")
        if (
            type(exact_ids) is not tuple
            or not exact_ids
            or len(exact_ids) > 47
            or any(type(value) is not str or not value for value in exact_ids)
            or tuple(sorted(set(exact_ids))) != exact_ids
        ):
            raise ValueError("linked IDs are not canonical")
        table_name, id_column = (
            ("silver_domestic_listed_product", "product_id")
            if side is ExactLinkedSide.DOMESTIC
            else ("silver_fund_item", "fund_item_id")
        )
        spec = TABLE_SPEC_BY_NAME[table_name]
        observed: list[str] = []
        output: list[LinkedRecordJson] = []
        rows = self._iter_exact_id_rows(
            table_name=table_name,
            id_column=id_column,
            exact_ids=exact_ids,
        )
        try:
            for physical in rows:
                product_id = physical[id_column]
                if type(product_id) is not str or type(physical["record_json"]) is not str:
                    raise ValueError("linked record projection changed")
                logical_table_row(spec, physical)
                if observed and product_id <= observed[-1]:
                    raise ValueError("linked records are not strictly ordered")
                observed.append(product_id)
                output.append(
                    LinkedRecordJson(
                        product_id=product_id,
                        record_json=physical["record_json"],
                    )
                )
        finally:
            rows.close()
        if tuple(observed) != exact_ids:
            raise ValueError("linked IDs are incomplete")
        yield tuple(output)


class QualityJoinObservations(BaseModel):
    """Strict bounded facts from the exact quality-to-Bronze relation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    total_issues: NonNegativeInt
    distinct_issue_ids: NonNegativeInt
    matched_bronze_rows: NonNegativeInt
    matched_bronze_cells: NonNegativeInt
    distinct_affected_source_rows: NonNegativeInt
    quarantined_issue_count: NonNegativeInt
    quarantined_source_row_count: NonNegativeInt
    persistence_timestamp: datetime
    quality_table_logical_hash: Sha256

    @model_validator(mode="after")
    def require_consistent_quality_join(self) -> Self:
        if (
            self.distinct_issue_ids != self.total_issues
            or self.matched_bronze_rows != self.total_issues
            or self.matched_bronze_cells != self.total_issues
        ):
            raise ValueError("quality issues must match exact Bronze rows and cells")
        if (
            self.distinct_affected_source_rows > self.total_issues
            or self.quarantined_issue_count > self.total_issues
            or self.quarantined_source_row_count > self.quarantined_issue_count
            or self.quarantined_source_row_count > self.distinct_affected_source_rows
        ):
            raise ValueError("quality observation counts are inconsistent")
        if (
            self.persistence_timestamp.tzinfo is None
            or self.persistence_timestamp.utcoffset() != timedelta(0)
        ):
            raise ValueError("quality persistence timestamp must be aware UTC")
        return self


class SourceTableAudit(BaseModel):
    """Expected and observed shape of one official source table."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_table: Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"]
    expected_rows: NonNegativeInt
    observed_rows: NonNegativeInt
    expected_columns: NonNegativeInt
    observed_columns: NonNegativeInt
    expected_cells: NonNegativeInt
    observed_cells: NonNegativeInt

    @model_validator(mode="after")
    def require_equal_shape(self) -> Self:
        if (
            self.expected_rows != self.observed_rows
            or self.expected_columns != self.observed_columns
            or self.expected_cells != self.observed_cells
        ):
            raise ValueError("source table expected and observed shape must match")
        return self


@dataclass(frozen=True, init=False, slots=True)
class BronzeSourceAuditObservations:
    """Exact CP4-only source-audit prefix issued from verified Bronze counts."""

    source_snapshot_date: date
    source_manifest_sha256: str
    schema_catalog_sha256: str
    source_tables: tuple[SourceTableAudit, ...]
    _issuance: _BronzeObservationIssuance

    def __new__(cls, *args: object, **kwargs: object) -> BronzeSourceAuditObservations:
        del args, kwargs
        raise TypeError("BronzeSourceAuditObservations is factory-issued")

    @classmethod
    def from_bronze(
        cls,
        *,
        source_snapshot_date: date,
        source_manifest_sha256: str,
        schema_catalog_sha256: str,
        source_tables: tuple[SourceTableAudit, ...],
    ) -> BronzeSourceAuditObservations:
        if type(source_snapshot_date) is not date or source_snapshot_date != date(2026, 7, 11):
            raise ValueError("Bronze observations require the official snapshot date")
        for digest in (source_manifest_sha256, schema_catalog_sha256):
            if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise ValueError("Bronze observations require lowercase SHA-256 values")
        if type(source_tables) is not tuple or tuple(
            entry.source_table for entry in source_tables
        ) != ("PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"):
            raise ValueError("Bronze source tables require the exact closed order")
        for entry in source_tables:
            if type(entry) is not SourceTableAudit:
                raise TypeError("Bronze source tables require exact SourceTableAudit values")
            validated = SourceTableAudit.model_validate(
                entry.model_dump(mode="python"),
                strict=True,
            )
            if validated != entry:
                raise ValueError("Bronze source-table facts changed during validation")
        value = object.__new__(cls)
        object.__setattr__(value, "source_snapshot_date", source_snapshot_date)
        object.__setattr__(value, "source_manifest_sha256", source_manifest_sha256)
        object.__setattr__(value, "schema_catalog_sha256", schema_catalog_sha256)
        object.__setattr__(value, "source_tables", source_tables)
        object.__setattr__(value, "_issuance", _BronzeObservationIssuance(value))
        return value

    def with_silver(
        self,
        silver_counts: tuple[NamedExpectedObservedCount, ...],
        quarantine_counts: ExpectedObservedCount,
    ) -> SilverSourceAuditObservations:
        """Advance this exact Bronze prefix once to the Silver observation type."""
        require_bronze_source_audit_observations(self)
        issuance = self._issuance
        if issuance.transitioned:
            raise ValueError("Bronze observations were already advanced")
        value = SilverSourceAuditObservations._from_bronze(
            predecessor=self,
            silver_tables=silver_counts,
            quarantine_source_rows=quarantine_counts,
        )
        issuance.transitioned = True
        return value


class _BronzeObservationIssuance:
    __slots__ = ("facts", "transitioned", "value")

    def __init__(self, value: BronzeSourceAuditObservations) -> None:
        self.value = value
        self.transitioned = False
        self.facts = (
            value.source_snapshot_date,
            value.source_manifest_sha256,
            value.schema_catalog_sha256,
            tuple(entry.model_dump_json() for entry in value.source_tables),
        )


def require_bronze_source_audit_observations(value: object) -> None:
    """Reject copied, forged, later-phase, or mutated Bronze observations."""
    try:
        if type(value) is not BronzeSourceAuditObservations:
            raise TypeError("observations must have the exact Bronze runtime type")
        issuance = value._issuance
        facts = (
            value.source_snapshot_date,
            value.source_manifest_sha256,
            value.schema_catalog_sha256,
            tuple(entry.model_dump_json() for entry in value.source_tables),
        )
        if (
            type(issuance) is not _BronzeObservationIssuance
            or issuance.value is not value
            or issuance.facts != facts
        ):
            raise ValueError("Bronze observation issuance changed")
        BronzeSourceAuditObservations.from_bronze(
            source_snapshot_date=value.source_snapshot_date,
            source_manifest_sha256=value.source_manifest_sha256,
            schema_catalog_sha256=value.schema_catalog_sha256,
            source_tables=value.source_tables,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid Bronze source-audit observations") from exc


class NamedExpectedObservedCount(BaseModel):
    """Named expected and observed count."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: Literal[
        "bond_instrument",
        "domestic_listed_product",
        "overseas_listed_product",
        "fund_item",
        "fund_item_attribute",
    ]
    expected: NonNegativeInt
    observed: NonNegativeInt

    @model_validator(mode="after")
    def require_equal_count(self) -> Self:
        if self.expected != self.observed:
            raise ValueError("expected and observed counts must match")
        return self


class ExpectedObservedCount(BaseModel):
    """Expected and observed count."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    expected: NonNegativeInt
    observed: NonNegativeInt

    @model_validator(mode="after")
    def require_equal_count(self) -> Self:
        if self.expected != self.observed:
            raise ValueError("expected and observed counts must match")
        return self


class ExpectedObservedSha256(BaseModel):
    """Expected and observed semantic digest."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    expected: Sha256
    observed: Sha256

    @model_validator(mode="after")
    def require_equal_digest(self) -> Self:
        if self.expected != self.observed:
            raise ValueError("expected and observed digests must match")
        return self


class _ExactEvidenceVerificationProvenance:
    __slots__ = ("_issuance",)

    _issuance: _ExactEvidenceVerificationIssuance


@dataclass(frozen=True, init=False, slots=True)
class ExactEvidenceVerificationObservations(_ExactEvidenceVerificationProvenance):
    """Factory-issued complete CP6 exact-link verification facts."""

    exact_links: ExpectedObservedCount
    exact_link_evidence: ExpectedObservedCount
    exact_link_pair_sha256: ExpectedObservedSha256
    matched_bronze_cells: int
    matched_left_records: int
    matched_right_records: int
    max_relation_batch_rows: int

    def __new__(cls, *args: object, **kwargs: object) -> ExactEvidenceVerificationObservations:
        del args, kwargs
        raise TypeError("ExactEvidenceVerificationObservations is verifier-issued")

    def __copy__(self) -> ExactEvidenceVerificationObservations:
        raise TypeError("ExactEvidenceVerificationObservations cannot be copied")

    def __deepcopy__(self, memo: object) -> ExactEvidenceVerificationObservations:
        del memo
        raise TypeError("ExactEvidenceVerificationObservations cannot be copied")


class _ExactEvidenceVerificationIssuance:
    __slots__ = ("facts", "owner", "value")

    def __init__(
        self,
        value: ExactEvidenceVerificationObservations,
        *,
        owner: object,
    ) -> None:
        self.value = value
        self.owner = owner
        self.facts = tuple(getattr(value, name) for name in value.__dataclass_fields__)


@dataclass(frozen=True, init=False, slots=True)
class SilverSourceAuditObservations:
    """Exact CP5 source-audit successor with no link-phase fields."""

    source_snapshot_date: date
    source_manifest_sha256: str
    schema_catalog_sha256: str
    source_tables: tuple[SourceTableAudit, ...]
    silver_tables: tuple[NamedExpectedObservedCount, ...]
    quarantine_source_rows: ExpectedObservedCount
    _issuance: _SilverObservationIssuance

    def __new__(cls, *args: object, **kwargs: object) -> SilverSourceAuditObservations:
        del args, kwargs
        raise TypeError("SilverSourceAuditObservations is predecessor-issued")

    @classmethod
    def _from_bronze(
        cls,
        *,
        predecessor: BronzeSourceAuditObservations,
        silver_tables: tuple[NamedExpectedObservedCount, ...],
        quarantine_source_rows: ExpectedObservedCount,
    ) -> SilverSourceAuditObservations:
        if type(predecessor) is not BronzeSourceAuditObservations:
            raise TypeError("Silver observations require exact Bronze observations")
        if (
            type(silver_tables) is not tuple
            or tuple(item.name for item in silver_tables)
            != (
                "bond_instrument",
                "domestic_listed_product",
                "overseas_listed_product",
                "fund_item",
                "fund_item_attribute",
            )
            or any(type(item) is not NamedExpectedObservedCount for item in silver_tables)
            or type(quarantine_source_rows) is not ExpectedObservedCount
        ):
            raise TypeError("Silver observations require exact ordered counts")
        for item in silver_tables:
            if (
                NamedExpectedObservedCount.model_validate(
                    item.model_dump(mode="python"), strict=True
                )
                != item
            ):
                raise ValueError("Silver count changed during validation")
        if (
            ExpectedObservedCount.model_validate(
                quarantine_source_rows.model_dump(mode="python"), strict=True
            )
            != quarantine_source_rows
        ):
            raise ValueError("quarantine count changed during validation")
        value = object.__new__(cls)
        object.__setattr__(value, "source_snapshot_date", predecessor.source_snapshot_date)
        object.__setattr__(value, "source_manifest_sha256", predecessor.source_manifest_sha256)
        object.__setattr__(value, "schema_catalog_sha256", predecessor.schema_catalog_sha256)
        object.__setattr__(value, "source_tables", predecessor.source_tables)
        object.__setattr__(value, "silver_tables", silver_tables)
        object.__setattr__(value, "quarantine_source_rows", quarantine_source_rows)
        object.__setattr__(
            value,
            "_issuance",
            _SilverObservationIssuance(value=value, predecessor=predecessor),
        )
        return value

    def with_links(
        self,
        *,
        verified: ExactEvidenceVerificationObservations,
    ) -> CompleteSourceAuditObservations:
        require_silver_source_audit_observations(self)
        issuance = self._issuance
        if issuance.transitioned:
            raise ValueError("Silver observations were already advanced")
        if type(verified) is not ExactEvidenceVerificationObservations:
            raise TypeError("Complete observations require exact verification facts")
        verified_issuance = object.__getattribute__(verified, "_issuance")
        if (
            type(verified_issuance) is not _ExactEvidenceVerificationIssuance
            or verified_issuance.value is not verified
            or verified_issuance.facts
            != tuple(getattr(verified, name) for name in verified.__dataclass_fields__)
        ):
            raise ValueError("exact evidence verification issuance changed")
        value = object.__new__(CompleteSourceAuditObservations)
        for name in (
            "source_snapshot_date",
            "source_manifest_sha256",
            "schema_catalog_sha256",
            "source_tables",
            "silver_tables",
            "quarantine_source_rows",
        ):
            object.__setattr__(value, name, getattr(self, name))
        object.__setattr__(value, "exact_links", verified.exact_links)
        object.__setattr__(value, "exact_link_evidence", verified.exact_link_evidence)
        object.__setattr__(value, "exact_link_pair_sha256", verified.exact_link_pair_sha256)
        object.__setattr__(
            value,
            "_issuance",
            _CompleteObservationIssuance(
                value=value,
                predecessor=self,
                verified=verified,
            ),
        )
        issuance.transitioned = True
        return value


class _SilverObservationIssuance:
    __slots__ = ("members", "predecessor", "transitioned", "value")

    def __init__(
        self,
        *,
        value: SilverSourceAuditObservations,
        predecessor: BronzeSourceAuditObservations,
    ) -> None:
        self.value = value
        self.predecessor = predecessor
        self.transitioned = False
        self.members = (
            value.source_snapshot_date,
            value.source_manifest_sha256,
            value.schema_catalog_sha256,
            value.source_tables,
            value.silver_tables,
            value.quarantine_source_rows,
        )


@dataclass(frozen=True, init=False, slots=True)
class CompleteSourceAuditObservations:
    """Exact CP6 source-audit successor including verified link facts."""

    source_snapshot_date: date
    source_manifest_sha256: str
    schema_catalog_sha256: str
    source_tables: tuple[SourceTableAudit, ...]
    silver_tables: tuple[NamedExpectedObservedCount, ...]
    quarantine_source_rows: ExpectedObservedCount
    exact_links: ExpectedObservedCount
    exact_link_evidence: ExpectedObservedCount
    exact_link_pair_sha256: ExpectedObservedSha256
    _issuance: _CompleteObservationIssuance

    def __new__(cls, *args: object, **kwargs: object) -> CompleteSourceAuditObservations:
        del args, kwargs
        raise TypeError("CompleteSourceAuditObservations is predecessor-issued")


class _CompleteObservationIssuance:
    __slots__ = ("predecessor", "value", "verified")

    def __init__(
        self,
        *,
        value: CompleteSourceAuditObservations,
        predecessor: SilverSourceAuditObservations,
        verified: ExactEvidenceVerificationObservations,
    ) -> None:
        self.value = value
        self.predecessor = predecessor
        self.verified = verified


def require_complete_source_audit_observations(value: object) -> None:
    if type(value) is not CompleteSourceAuditObservations:
        raise TypeError("observations must have the exact Complete runtime type")
    issuance = object.__getattribute__(value, "_issuance")
    if (
        type(issuance) is not _CompleteObservationIssuance
        or issuance.value is not value
        or type(issuance.predecessor) is not SilverSourceAuditObservations
        or type(issuance.verified) is not ExactEvidenceVerificationObservations
    ):
        raise ValueError("Complete observation issuance changed")
    require_silver_source_audit_observations(issuance.predecessor)
    verified_issuance = object.__getattribute__(issuance.verified, "_issuance")
    if (
        type(verified_issuance) is not _ExactEvidenceVerificationIssuance
        or verified_issuance.value is not issuance.verified
        or verified_issuance.facts
        != tuple(
            getattr(issuance.verified, name) for name in issuance.verified.__dataclass_fields__
        )
        or any(
            getattr(value, name) is not getattr(issuance.predecessor, name)
            for name in (
                "source_tables",
                "silver_tables",
                "quarantine_source_rows",
            )
        )
        or any(
            getattr(value, name) is not getattr(issuance.verified, name)
            for name in (
                "exact_links",
                "exact_link_evidence",
                "exact_link_pair_sha256",
            )
        )
        or value.source_snapshot_date != issuance.predecessor.source_snapshot_date
        or value.source_manifest_sha256 != issuance.predecessor.source_manifest_sha256
        or value.schema_catalog_sha256 != issuance.predecessor.schema_catalog_sha256
    ):
        raise ValueError("Complete observation members changed")
    _require_exact_evidence_verification_observations(issuance.verified)


def _require_exact_evidence_verification_observations(
    value: ExactEvidenceVerificationObservations,
) -> None:
    if type(value) is not ExactEvidenceVerificationObservations:
        raise TypeError("exact evidence observations must have the exact runtime type")
    issuance = object.__getattribute__(value, "_issuance")
    if (
        type(issuance) is not _ExactEvidenceVerificationIssuance
        or issuance.value is not value
        or issuance.facts != tuple(getattr(value, name) for name in value.__dataclass_fields__)
        or value.matched_bronze_cells != value.exact_link_evidence.observed
        or value.matched_left_records != value.exact_links.observed
        or value.matched_right_records != value.exact_links.observed
        or not 0 <= value.max_relation_batch_rows <= 65_536
    ):
        raise ValueError("exact evidence verification facts changed")
    for fact, model_type in (
        (value.exact_links, ExpectedObservedCount),
        (value.exact_link_evidence, ExpectedObservedCount),
        (value.exact_link_pair_sha256, ExpectedObservedSha256),
    ):
        if model_type.model_validate(fact.model_dump(mode="python"), strict=True) != fact:
            raise ValueError("exact evidence verification count or hash changed")


def require_silver_source_audit_observations(value: object) -> None:
    """Reject forged, copied, mutated, or later-phase Silver observations."""
    try:
        if type(value) is not SilverSourceAuditObservations:
            raise TypeError("observations must have the exact Silver runtime type")
        issuance = value._issuance
        members = (
            value.source_snapshot_date,
            value.source_manifest_sha256,
            value.schema_catalog_sha256,
            value.source_tables,
            value.silver_tables,
            value.quarantine_source_rows,
        )
        if (
            type(issuance) is not _SilverObservationIssuance
            or issuance.value is not value
            or issuance.members != members
            or issuance.members[3] is not value.source_tables
            or issuance.members[4] is not value.silver_tables
            or issuance.members[5] is not value.quarantine_source_rows
        ):
            raise ValueError("Silver observation issuance changed")
        require_bronze_source_audit_observations(issuance.predecessor)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid Silver source-audit observations") from exc


class SourceAuditReport(BaseModel):
    """Strict source-audit semantic report."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    report_id: Literal["source_audit"]
    report_contract_version: Literal["1.0.0"]
    artifact_contract_version: Literal["1.0.0"]
    source_snapshot_date: date
    source_manifest_sha256: Sha256
    schema_catalog_sha256: Sha256
    source_tables: tuple[SourceTableAudit, ...]
    silver_tables: tuple[NamedExpectedObservedCount, ...]
    quarantine_source_rows: ExpectedObservedCount
    exact_links: ExpectedObservedCount
    exact_link_evidence: ExpectedObservedCount
    exact_link_pair_sha256: ExpectedObservedSha256

    @classmethod
    def from_complete_observations(
        cls,
        *,
        config: object,
        observations: CompleteSourceAuditObservations,
    ) -> SourceAuditReport:
        from finproof.data.artifacts.config import ArtifactBuildConfig

        if type(config) is not ArtifactBuildConfig:
            raise TypeError("source-audit report requires exact build config")
        validated = ArtifactBuildConfig.model_validate(
            config.model_dump(mode="python"), strict=True
        )
        if validated != config:
            raise ValueError("source-audit build config changed")
        require_complete_source_audit_observations(observations)
        expected_source = tuple(
            (item.table, item.rows, item.columns, item.cells) for item in config.sources
        )
        observed_source = tuple(
            (
                item.source_table,
                item.expected_rows,
                item.expected_columns,
                item.expected_cells,
            )
            for item in observations.source_tables
        )
        configured_silver = (
            config.silver_counts.bond_instrument,
            config.silver_counts.domestic_listed_product,
            config.silver_counts.overseas_listed_product,
            config.silver_counts.fund_item,
            config.silver_counts.fund_item_attribute,
        )
        if (
            expected_source != observed_source
            or configured_silver != tuple(item.expected for item in observations.silver_tables)
            or config.quarantine_source_rows != observations.quarantine_source_rows.expected
            or config.exact_links.links != observations.exact_links.expected
            or config.exact_links.evidence != observations.exact_link_evidence.expected
            or config.exact_links.pair_sha256 != observations.exact_link_pair_sha256.expected
        ):
            raise ValueError("source-audit observations disagree with build config")
        report = cls(
            report_id="source_audit",
            report_contract_version="1.0.0",
            artifact_contract_version=cast(Literal["1.0.0"], config.artifact_contract_version),
            source_snapshot_date=observations.source_snapshot_date,
            source_manifest_sha256=observations.source_manifest_sha256,
            schema_catalog_sha256=observations.schema_catalog_sha256,
            source_tables=observations.source_tables,
            silver_tables=observations.silver_tables,
            quarantine_source_rows=observations.quarantine_source_rows,
            exact_links=observations.exact_links,
            exact_link_evidence=observations.exact_link_evidence,
            exact_link_pair_sha256=observations.exact_link_pair_sha256,
        )
        for name in (
            "source_tables",
            "silver_tables",
            "quarantine_source_rows",
            "exact_links",
            "exact_link_evidence",
            "exact_link_pair_sha256",
        ):
            object.__setattr__(report, name, getattr(observations, name))
        return report

    @model_validator(mode="after")
    def require_closed_inventory_order(self) -> Self:
        if self.source_snapshot_date != date(2026, 7, 11):
            raise ValueError("source_snapshot_date must be 2026-07-11")
        if tuple(entry.source_table for entry in self.source_tables) != (
            "PRBD01N001",
            "PREF01N001",
            "PREF02N001",
            "PRFD01N001",
        ):
            raise ValueError("source_tables must use the exact closed order")
        if tuple(entry.name for entry in self.silver_tables) != (
            "bond_instrument",
            "domestic_listed_product",
            "overseas_listed_product",
            "fund_item",
            "fund_item_attribute",
        ):
            raise ValueError("silver_tables must use the exact closed order")
        return self

    def semantic_projection(self) -> Mapping[str, object]:
        return self.model_dump(mode="python", warnings="none")


class SourceTableCount(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_table: Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"]
    count: PositiveInt


class RuleCount(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    rule_id: NonEmptyText
    rule_version: NonEmptyText
    count: PositiveInt


class SeverityCount(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    severity: IssueSeverity
    count: PositiveInt


class QualityStatusCount(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    quality_status: QualityStatus
    count: PositiveInt


class BooleanCount(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    value: bool
    count: NonNegativeInt


class ExcludedSilverCount(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    grain: Literal["instrument", "listed_product", "fund_item", "fund_attribute"]
    count: PositiveInt


class QualitySummaryReport(BaseModel):
    """Strict quality-summary semantic report."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    report_id: Literal["quality_summary"]
    report_contract_version: Literal["1.0.0"]
    artifact_contract_version: Literal["1.0.0"]
    total_issues: NonNegativeInt
    distinct_affected_source_rows: NonNegativeInt
    by_source_table: tuple[SourceTableCount, ...]
    by_rule: tuple[RuleCount, ...]
    by_severity: tuple[SeverityCount, ...]
    by_quality_status: tuple[QualityStatusCount, ...]
    by_quarantine_flag: tuple[BooleanCount, BooleanCount]
    quarantined_issue_count: NonNegativeInt
    quarantined_source_row_count: NonNegativeInt
    excluded_silver_records: tuple[ExcludedSilverCount, ...]
    quality_table_logical_hash: Sha256

    @classmethod
    def from_verified_quality(
        cls,
        *,
        issues: Iterable[DataQualityIssue],
        join_observations: QualityJoinObservations,
        excluded_silver_records: tuple[ExcludedSilverCount, ...],
    ) -> Self:
        """Build one timestamp-neutral report from a strict one-pass issue stream."""
        from finproof.data.artifacts.hashing import canonical_json_bytes, schema_sha256
        from finproof.data.artifacts.serialization import logical_table_row, serialize_table_row
        from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

        if type(join_observations) is not QualityJoinObservations:
            raise TypeError("quality report requires exact join observations")
        observed = QualityJoinObservations.model_validate(
            join_observations.model_dump(mode="python"),
            strict=True,
        )
        if type(excluded_silver_records) is not tuple or any(
            type(item) is not ExcludedSilverCount for item in excluded_silver_records
        ):
            raise TypeError("excluded Silver counts must be exact")
        excluded = tuple(
            ExcludedSilverCount.model_validate(item.model_dump(mode="python"), strict=True)
            for item in excluded_silver_records
        )
        if tuple(item.grain for item in excluded) != tuple(sorted(item.grain for item in excluded)):
            raise ValueError("excluded Silver counts must be sorted")

        spec = TABLE_SPEC_BY_NAME["silver_quality_issue"]
        by_source: dict[str, int] = defaultdict(int)
        by_rule: dict[tuple[str, str], int] = defaultdict(int)
        by_severity: dict[IssueSeverity, int] = defaultdict(int)
        by_status: dict[QualityStatus, int] = defaultdict(int)
        by_quarantine = {False: 0, True: 0}
        total = affected = quarantined_rows = 0
        previous_source: tuple[object, ...] | None = None
        previous_quarantined: tuple[object, ...] | None = None
        with tempfile.SpooledTemporaryFile(max_size=1 << 20) as logical_bytes:
            for issue in issues:
                if type(issue) is not DataQualityIssue or issue.first_detected_at is None:
                    raise TypeError("quality report requires exact persisted issues")
                validated = DataQualityIssue.model_validate(
                    issue.model_dump(mode="python"),
                    strict=True,
                )
                if validated != issue or issue.first_detected_at != observed.persistence_timestamp:
                    raise ValueError("quality issue changed or has a different timestamp")
                physical = serialize_table_row(spec, validated)
                logical = logical_table_row(spec, physical)
                logical_bytes.write(canonical_json_bytes(logical))
                source = issue.source
                source_key = (
                    source.source_table,
                    source.source_file.as_posix(),
                    source.source_sheet,
                    source.source_row_number,
                )
                total += 1
                by_source[source.source_table] += 1
                by_rule[(issue.rule_id, issue.rule_version)] += 1
                by_severity[issue.severity] += 1
                by_status[issue.quality_status] += 1
                by_quarantine[issue.quarantined] += 1
                if source_key != previous_source:
                    affected += 1
                    previous_source = source_key
                if issue.quarantined and source_key != previous_quarantined:
                    quarantined_rows += 1
                    previous_quarantined = source_key
            digest = hashlib.sha256()
            digest.update(
                canonical_json_bytes(
                    {
                        "schema_sha256": schema_sha256(spec),
                        "logical_projection": spec.logical_projection,
                        "row_count": total,
                    }
                )
            )
            logical_bytes.seek(0)
            while chunk := logical_bytes.read(1 << 20):
                digest.update(chunk)
            logical_hash = digest.hexdigest()

        if (
            total != observed.total_issues
            or affected != observed.distinct_affected_source_rows
            or by_quarantine[True] != observed.quarantined_issue_count
            or quarantined_rows != observed.quarantined_source_row_count
            or logical_hash != observed.quality_table_logical_hash
        ):
            raise ValueError("quality stream does not equal verified join observations")
        return cls(
            report_id="quality_summary",
            report_contract_version="1.0.0",
            artifact_contract_version="1.0.0",
            total_issues=total,
            distinct_affected_source_rows=affected,
            by_source_table=tuple(
                SourceTableCount(
                    source_table=cast(
                        Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"],
                        name,
                    ),
                    count=by_source[name],
                )
                for name in sorted(by_source)
            ),
            by_rule=tuple(
                RuleCount(rule_id=key[0], rule_version=key[1], count=by_rule[key])
                for key in sorted(by_rule)
            ),
            by_severity=tuple(
                SeverityCount(severity=key, count=by_severity[key])
                for key in sorted(by_severity, key=lambda item: item.value)
            ),
            by_quality_status=tuple(
                QualityStatusCount(quality_status=key, count=by_status[key])
                for key in sorted(by_status, key=lambda item: item.value)
            ),
            by_quarantine_flag=(
                BooleanCount(value=False, count=by_quarantine[False]),
                BooleanCount(value=True, count=by_quarantine[True]),
            ),
            quarantined_issue_count=by_quarantine[True],
            quarantined_source_row_count=quarantined_rows,
            excluded_silver_records=excluded,
            quality_table_logical_hash=logical_hash,
        )

    @model_validator(mode="after")
    def require_closed_groups_and_aggregates(self) -> Self:
        source_keys = tuple(entry.source_table for entry in self.by_source_table)
        rule_keys = tuple((entry.rule_id, entry.rule_version) for entry in self.by_rule)
        severity_keys = tuple(entry.severity.value for entry in self.by_severity)
        status_keys = tuple(entry.quality_status.value for entry in self.by_quality_status)
        excluded_keys = tuple(entry.grain for entry in self.excluded_silver_records)
        for keys, field in (
            (source_keys, "by_source_table"),
            (rule_keys, "by_rule"),
            (severity_keys, "by_severity"),
            (status_keys, "by_quality_status"),
            (excluded_keys, "excluded_silver_records"),
        ):
            if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                raise ValueError(f"{field} must be sorted and unique")
        if tuple(entry.value for entry in self.by_quarantine_flag) != (False, True):
            raise ValueError("by_quarantine_flag must be exactly False then True")
        grouped_counts = (
            sum(entry.count for entry in self.by_source_table),
            sum(entry.count for entry in self.by_rule),
            sum(entry.count for entry in self.by_severity),
            sum(entry.count for entry in self.by_quality_status),
            sum(entry.count for entry in self.by_quarantine_flag),
        )
        if any(count != self.total_issues for count in grouped_counts):
            raise ValueError("every issue group must sum to total_issues")
        if self.by_quarantine_flag[1].count != self.quarantined_issue_count:
            raise ValueError("true quarantine count must equal quarantined_issue_count")
        if self.distinct_affected_source_rows > self.total_issues:
            raise ValueError("affected source rows cannot exceed total issues")
        if self.quarantined_source_row_count > self.quarantined_issue_count:
            raise ValueError("quarantined source rows cannot exceed quarantined issues")
        return self

    def semantic_projection(self) -> Mapping[str, object]:
        return self.model_dump(mode="python", warnings="none")


class _FinalReportVerificationObservations:
    """One-shot path-free observations from successful final report verification."""

    __slots__ = ("_max_batch_rows",)

    def __init__(self) -> None:
        self._max_batch_rows: int | None = None

    def _record(self, *, max_batch_rows: int) -> None:
        if (
            self._max_batch_rows is not None
            or type(max_batch_rows) is not int
            or not 0 <= max_batch_rows <= 65_536
        ):
            raise ValueError("final report observations changed")
        self._max_batch_rows = max_batch_rows

    def require_max_batch_rows(self) -> int:
        if self._max_batch_rows is None:
            raise ValueError("final report observations are unavailable")
        return self._max_batch_rows


class StrictArtifactReportVerifier:
    """Rebuild both report semantics only from live final inventory handles."""

    __slots__ = ("_observations",)

    def __init__(
        self,
        *,
        observations: _FinalReportVerificationObservations | None = None,
    ) -> None:
        if (
            observations is not None
            and type(observations) is not _FinalReportVerificationObservations
        ):
            raise TypeError("final report observations changed")
        self._observations = observations

    @staticmethod
    def _read_report(
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        report_id: Literal["source_audit", "quality_summary"],
    ) -> SourceAuditReport | QualitySummaryReport:
        declaration = next(entry for entry in manifest.files if entry.report_id == report_id)
        entry = next(
            candidate
            for candidate in inventory.declared_entries
            if candidate.path.as_posix() == declaration.path
        )
        with inventory.open_verified(entry) as stream:
            payload = stream.read(8 * 1024 * 1024 + 1)
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError("artifact report exceeds its bounded size")
        model_type = SourceAuditReport if report_id == "source_audit" else QualitySummaryReport
        return model_type.model_validate_json(payload, strict=True)

    @staticmethod
    def _counts_by_source(
        relation: _FinalInventoryRelationVerifier,
        table_name: str,
    ) -> dict[str, int]:
        counts = dict.fromkeys(OFFICIAL_TABLE_IDS, 0)
        rows = relation._iter_rows(table_name)
        try:
            for row in rows:
                source_table = row.get("source_table")
                if source_table not in counts:
                    raise ValueError("Bronze row has an unknown source table")
                counts[source_table] += 1
        finally:
            rows.close()
        return counts

    def verify_reports(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        tables: TableVerificationResult,
    ) -> ReportVerificationResult:
        if type(manifest) is not ArtifactManifest:
            raise TypeError("report verifier requires the exact manifest")
        tables.validate_against(inventory)
        relation = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        )
        parsed_source = self._read_report(
            manifest=manifest,
            inventory=inventory,
            report_id="source_audit",
        )
        parsed_quality = self._read_report(
            manifest=manifest,
            inventory=inventory,
            report_id="quality_summary",
        )
        if (
            type(parsed_source) is not SourceAuditReport
            or type(parsed_quality) is not QualitySummaryReport
        ):
            raise TypeError("report parser returned the wrong strict model")
        row_counts = self._counts_by_source(relation, "bronze_source_row")
        column_counts = self._counts_by_source(relation, "bronze_source_column")
        cell_counts = self._counts_by_source(relation, "bronze_source_cell")
        source_tables = tuple(
            SourceTableAudit(
                source_table=cast(
                    Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"],
                    source_table,
                ),
                expected_rows=row_counts[source_table],
                observed_rows=row_counts[source_table],
                expected_columns=column_counts[source_table],
                observed_columns=column_counts[source_table],
                expected_cells=cell_counts[source_table],
                observed_cells=cell_counts[source_table],
            )
            for source_table in OFFICIAL_TABLE_IDS
        )
        handle_counts = {handle.table_name: handle.row_count for handle in tables.handles}
        silver_names = (
            ("bond_instrument", "silver_bond_instrument"),
            ("domestic_listed_product", "silver_domestic_listed_product"),
            ("overseas_listed_product", "silver_overseas_listed_product"),
            ("fund_item", "silver_fund_item"),
            ("fund_item_attribute", "silver_fund_item_attribute"),
        )
        silver_tables = tuple(
            NamedExpectedObservedCount(
                name=cast(
                    Literal[
                        "bond_instrument",
                        "domestic_listed_product",
                        "overseas_listed_product",
                        "fund_item",
                        "fund_item_attribute",
                    ],
                    name,
                ),
                expected=handle_counts[table_name],
                observed=handle_counts[table_name],
            )
            for name, table_name in silver_names
        )
        quality = relation.verify_quality_to_bronze()
        evidence = relation.verify_exact_evidence_to_bronze()
        from finproof.data.artifacts.links import (
            _verify_evidence_relationships,
            canonical_link_pair_tsv,
            exact_link_pair_sha256,
        )
        from finproof.data.artifacts.serialization import ExactCrossSourceLinkRecord

        link_rows = relation._iter_rows("gold_exact_cross_source_link")
        links: list[ExactCrossSourceLinkRecord] = []
        try:
            for row in link_rows:
                if len(links) == 47:
                    raise ValueError("exact linked-record bound exceeded")
                links.append(ExactCrossSourceLinkRecord.model_validate(row, strict=True))
        finally:
            link_rows.close()
        gold_evidence_rows = relation._iter_rows("gold_exact_cross_source_link_evidence")
        gold_evidence: list[ExactCrossSourceLinkEvidenceRecord] = []
        try:
            for row in gold_evidence_rows:
                payload = dict(row)
                payload["source_file"] = PurePosixPath(cast(str, payload["source_file"]))
                gold_evidence.append(
                    ExactCrossSourceLinkEvidenceRecord.model_validate(
                        payload,
                        strict=True,
                    )
                )
        finally:
            gold_evidence_rows.close()
        _verify_evidence_relationships(
            links=tuple(links),
            evidence=tuple(gold_evidence),
            bronze=evidence,
        )
        if links:
            linked_ids = (
                (
                    ExactLinkedSide.DOMESTIC,
                    tuple(sorted({link.left_product_id for link in links})),
                ),
                (
                    ExactLinkedSide.FUND,
                    tuple(sorted({link.right_product_id for link in links})),
                ),
            )
            for side, exact_ids in linked_ids:
                for _batch in relation.iter_linked_record_json(
                    side=side,
                    exact_ids=exact_ids,
                ):
                    pass
        pair_hash = exact_link_pair_sha256(
            canonical_link_pair_tsv(links, expected_links=len(links))
        )
        rebuilt_source = SourceAuditReport(
            report_id="source_audit",
            report_contract_version="1.0.0",
            artifact_contract_version=manifest.artifact_contract_version,
            source_snapshot_date=manifest.dataset_version,
            source_manifest_sha256=manifest.source_inputs[0].sha256,
            schema_catalog_sha256=manifest.source_inputs[1].sha256,
            source_tables=source_tables,
            silver_tables=silver_tables,
            quarantine_source_rows=ExpectedObservedCount(
                expected=quality.quarantined_source_row_count,
                observed=quality.quarantined_source_row_count,
            ),
            exact_links=ExpectedObservedCount(
                expected=len(links),
                observed=len(links),
            ),
            exact_link_evidence=ExpectedObservedCount(
                expected=evidence.matched_bronze_cells,
                observed=evidence.matched_bronze_cells,
            ),
            exact_link_pair_sha256=ExpectedObservedSha256(
                expected=pair_hash,
                observed=pair_hash,
            ),
        )

        def issues() -> Iterator[DataQualityIssue]:
            rows = relation._iter_rows("silver_quality_issue")
            try:
                for row in rows:
                    record_json = row.get("record_json")
                    if type(record_json) is not str:
                        raise ValueError("quality record_json changed")
                    yield DataQualityIssue.model_validate_json(record_json, strict=True)
            finally:
                rows.close()

        excluded = tuple(
            ExcludedSilverCount(
                grain=cast(
                    Literal["instrument", "listed_product", "fund_item", "fund_attribute"],
                    grain,
                ),
                count=count,
            )
            for grain, count in (
                (
                    "fund_attribute",
                    row_counts["PRFD01N001"] - handle_counts["silver_fund_item_attribute"],
                ),
                (
                    "instrument",
                    row_counts["PRBD01N001"] - handle_counts["silver_bond_instrument"],
                ),
                (
                    "listed_product",
                    row_counts["PREF01N001"]
                    + row_counts["PREF02N001"]
                    - handle_counts["silver_domestic_listed_product"]
                    - handle_counts["silver_overseas_listed_product"],
                ),
            )
            if count > 0
        )

        rebuilt_quality = QualitySummaryReport.from_verified_quality(
            issues=issues(),
            join_observations=quality,
            excluded_silver_records=excluded,
        )
        if (
            rebuilt_source != parsed_source
            or rebuilt_quality != parsed_quality
            or rebuilt_quality.quarantined_source_row_count
            != rebuilt_source.quarantine_source_rows.observed
        ):
            raise ValueError("artifact reports differ from rebuilt final relations")
        semantic = (
            ExpectedSemanticReport(
                report_id="source_audit",
                semantic_hash=report_logical_hash(rebuilt_source),
            ),
            ExpectedSemanticReport(
                report_id="quality_summary",
                semantic_hash=report_logical_hash(rebuilt_quality),
            ),
        )
        declared = {
            entry.report_id: entry.logical_hash
            for entry in manifest.files
            if entry.report_id is not None
        }
        if any(declared[item.report_id] != item.semantic_hash for item in semantic):
            raise ValueError("artifact report logical hash changed")
        tables.validate_against(inventory)
        if self._observations is not None:
            self._observations._record(max_batch_rows=relation.max_batch_rows)
        return ReportVerificationResult(
            reports=semantic,
            exact_link_pair_sha256=pair_hash,
            exact_link_evidence_count=evidence.matched_bronze_cells,
        )
