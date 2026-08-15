"""Strict timestamp-free semantic artifact reports."""

from __future__ import annotations

import hashlib
import re
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus

if TYPE_CHECKING:
    from finproof.data.artifacts.parquet_io import StagedParquetSet

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


class BoundedRelationVerifier(Protocol):
    """Closed bounded verification port shared by CP5 and CP6."""

    def verify_quality_to_bronze(
        self,
        *,
        tables: StagedParquetSet,
    ) -> QualityJoinObservations: ...

    def verify_exact_evidence_to_bronze(self, *, tables: StagedParquetSet) -> None: ...

    def iter_linked_record_json(
        self,
        *,
        tables: StagedParquetSet,
        side: ExactLinkedSide,
        exact_ids: tuple[str, ...],
    ) -> Iterator[tuple[LinkedRecordJson, ...]]: ...


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


class _SilverObservationIssuance:
    __slots__ = ("members", "predecessor", "value")

    def __init__(
        self,
        *,
        value: SilverSourceAuditObservations,
        predecessor: BronzeSourceAuditObservations,
    ) -> None:
        self.value = value
        self.predecessor = predecessor
        self.members = (
            value.source_snapshot_date,
            value.source_manifest_sha256,
            value.schema_catalog_sha256,
            value.source_tables,
            value.silver_tables,
            value.quarantine_source_rows,
        )


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
