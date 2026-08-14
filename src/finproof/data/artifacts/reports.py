"""Strict timestamp-free semantic artifact reports."""

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.domain.quality import IssueSeverity, QualityStatus

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmptyText = Annotated[str, Field(min_length=1)]


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
