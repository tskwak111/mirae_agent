"""Evidence contracts for deterministic Phase 2 claims."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.data.holdings import HoldingCoverageState
from finproof.domain.query_plan import ProductType, ResultGrain
from finproof.domain.values import DerivedValue, NormalizedValue


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class DirectEvidence[ValueT](_FrozenModel):
    evidence_id: Annotated[str, Field(min_length=1, max_length=200)]
    product_type: ProductType
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None
    field_id: Annotated[str, Field(min_length=1, max_length=100)]
    value: NormalizedValue[ValueT]


class DerivedEvidence[ValueT](_FrozenModel):
    evidence_id: Annotated[str, Field(min_length=1, max_length=200)]
    product_type: ProductType
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None
    field_id: Annotated[str, Field(min_length=1, max_length=100)]
    value: DerivedValue[ValueT]


class EvidenceSummaryKind(StrEnum):
    COUNT = "count"
    EXCLUSION = "exclusion"
    RANK = "rank"
    TIE = "tie"
    PARTITION = "partition"
    AGGREGATE = "aggregate"
    RECORDED = "recorded"
    COVERAGE = "coverage"


class EvidenceSummaryValue(_FrozenModel):
    field_id: Annotated[str, Field(min_length=1, max_length=100)]
    value: Decimal | int | str | date | bool | None


class EvidenceSummary(_FrozenModel):
    summary_id: Annotated[str, Field(min_length=1, max_length=200)]
    kind: EvidenceSummaryKind
    included_count: Annotated[int, Field(ge=0)]
    excluded_count: Annotated[int, Field(ge=0)]
    evidence_ids: Annotated[tuple[str, ...], Field(max_length=100)]
    policy_versions: Annotated[tuple[str, ...], Field(min_length=1, max_length=32)]
    validated_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    version_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    product_types: Annotated[tuple[ProductType, ...], Field(max_length=6)] = ()
    native_result_grains: Annotated[tuple[ResultGrain, ...], Field(max_length=3)] = ()
    partition_key: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    metric_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    rank: Annotated[int, Field(ge=1)] | None = None
    tie_count: Annotated[int, Field(ge=1)] | None = None
    value: Decimal | int | str | date | bool | None = None
    group_values: Annotated[tuple[EvidenceSummaryValue, ...], Field(max_length=2)] = ()

    @model_validator(mode="after")
    def _validate_unique_references(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence IDs must be unique")
        if len(set(self.policy_versions)) != len(self.policy_versions):
            raise ValueError("policy versions must be unique")
        return self


class HoldingRecordEvidenceRef(_FrozenModel):
    evidence_id: Annotated[str, Field(min_length=1, max_length=200)]
    owner_product_type: ProductType
    owner_product_id: Annotated[str, Field(min_length=1, max_length=300)]
    generation_id: Annotated[str, Field(min_length=1, max_length=300)]
    constituent_identifier: Annotated[str, Field(min_length=1, max_length=300)]
    constituent_identifier_type: Annotated[str, Field(min_length=1, max_length=100)]
    display_name: Annotated[str, Field(min_length=1, max_length=500)]
    source_kind: Annotated[str, Field(min_length=1, max_length=200)]
    source_as_of_date: date
    source_row_ordinal: Annotated[int, Field(gt=0)]


class HoldingCoverageEvidenceRef(_FrozenModel):
    evidence_id: Annotated[str, Field(min_length=1, max_length=200)]
    owner_product_type: ProductType
    owner_product_id: Annotated[str, Field(min_length=1, max_length=300)]
    coverage_state: HoldingCoverageState
    source_generation_id: Annotated[str, Field(min_length=1, max_length=300)] | None
    observed_holding_count: Annotated[int, Field(ge=0)]
    limitation_code: str
    source_kind: Annotated[str, Field(min_length=1, max_length=200)] | None
    source_as_of_date: date | None

    @model_validator(mode="after")
    def _validate_coverage_shape(self) -> Self:
        if self.coverage_state is HoldingCoverageState.UNAVAILABLE:
            if (
                self.source_generation_id is not None
                or self.source_kind is not None
                or self.source_as_of_date is not None
                or self.observed_holding_count != 0
                or self.limitation_code != "source_unavailable"
            ):
                raise ValueError("unavailable holding coverage reference differs")
        elif (
            self.source_generation_id is None
            or self.source_kind is None
            or self.source_as_of_date is None
        ):
            raise ValueError("admitted holding coverage reference differs")
        return self


class EvidenceBundle(_FrozenModel):
    direct: Annotated[tuple[DirectEvidence[object], ...], Field(max_length=100)]
    derived: Annotated[tuple[DerivedEvidence[object], ...], Field(max_length=100)]
    summaries: Annotated[tuple[EvidenceSummary, ...], Field(max_length=200)]
    material_policy_limitations: Annotated[tuple[str, ...], Field(max_length=100)]
    holding_records: Annotated[tuple[HoldingRecordEvidenceRef, ...], Field(max_length=50)] = ()
    holding_coverage: Annotated[tuple[HoldingCoverageEvidenceRef, ...], Field(max_length=50)] = ()

    @model_validator(mode="after")
    def _validate_global_evidence_ids(self) -> Self:
        evidence_ids = (
            *(item.evidence_id for item in self.direct),
            *(item.evidence_id for item in self.derived),
            *(item.summary_id for item in self.summaries),
            *(item.evidence_id for item in self.holding_records),
            *(item.evidence_id for item in self.holding_coverage),
        )
        if len(evidence_ids) > 500:
            raise ValueError("global evidence ID bound exceeded")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence IDs must be globally unique")
        return self
