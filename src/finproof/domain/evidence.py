"""Evidence contracts for deterministic Phase 2 claims."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.domain.values import DerivedValue, NormalizedValue


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class DirectEvidence[ValueT](_FrozenModel):
    evidence_id: Annotated[str, Field(min_length=1, max_length=200)]
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None
    field_id: Annotated[str, Field(min_length=1, max_length=100)]
    value: NormalizedValue[ValueT]


class DerivedEvidence[ValueT](_FrozenModel):
    evidence_id: Annotated[str, Field(min_length=1, max_length=200)]
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

    @model_validator(mode="after")
    def _validate_unique_references(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence IDs must be unique")
        if len(set(self.policy_versions)) != len(self.policy_versions):
            raise ValueError("policy versions must be unique")
        return self
