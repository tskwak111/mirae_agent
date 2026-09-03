"""Structured answer contracts for deterministic rendering and verification."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.domain.evidence import EvidenceSummaryValue
from finproof.domain.execution import ExecutionTrace
from finproof.domain.query_plan import ProductType, ResultGrain


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ClaimKind(StrEnum):
    NUMERIC = "numeric"
    TEXT = "text"
    LIMITATION = "limitation"
    CANDIDATE = "candidate"
    RECOMMENDATION = "recommendation"


class ValueSign(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    ZERO = "zero"


class AnswerRequest(_FrozenModel):
    question_id: Annotated[str, Field(min_length=1, max_length=200)]
    question: Annotated[str, Field(min_length=1, max_length=4_000)]


class AnswerClaim(_FrozenModel):
    claim_id: Annotated[str, Field(min_length=1, max_length=200)]
    kind: ClaimKind
    text: Annotated[str, Field(min_length=1, max_length=2_000)]
    product_type: ProductType | None = None
    product_types: Annotated[tuple[ProductType, ...], Field(max_length=6)] = ()
    native_result_grains: Annotated[tuple[ResultGrain, ...], Field(max_length=3)] = ()
    partition_key: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    field_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    value: Decimal | int | str | date | bool | None = None
    group_values: Annotated[tuple[EvidenceSummaryValue, ...], Field(max_length=2)] = ()
    evidence_ids: Annotated[tuple[str, ...], Field(max_length=100)] = ()
    sign: ValueSign | None = None


class AnswerDraft(_FrozenModel):
    text: Annotated[str, Field(min_length=1, max_length=12_000)]
    claims: Annotated[tuple[AnswerClaim, ...], Field(max_length=300)]


class VerifiedAnswer(_FrozenModel):
    text: Annotated[str, Field(min_length=1, max_length=12_000)]
    claims: Annotated[tuple[AnswerClaim, ...], Field(max_length=300)]


class AnswerResult(_FrozenModel):
    answer: VerifiedAnswer
    retrieved_context: str
    trace: ExecutionTrace


class SurfacePart(_FrozenModel):
    part_id: Annotated[str, Field(min_length=1, max_length=100)]
    text: Annotated[str, Field(min_length=1, max_length=12_000)]
    claim_ids: Annotated[tuple[str, ...], Field(max_length=300)]
    limitation_codes: Annotated[tuple[str, ...], Field(max_length=100)]

    @model_validator(mode="after")
    def _unique_references(self) -> Self:
        if len(set(self.claim_ids)) != len(self.claim_ids) or len(
            set(self.limitation_codes)
        ) != len(self.limitation_codes):
            raise ValueError("surface references must be unique")
        return self


class EntitySignature(_FrozenModel):
    product_type: ProductType
    product_id: Annotated[str, Field(min_length=1, max_length=300)]
    display_name: Annotated[str, Field(min_length=1, max_length=500)]


class ValueSignature(_FrozenModel):
    field_id: Annotated[str, Field(min_length=1, max_length=100)]
    canonical_normalized_json: Annotated[str, Field(min_length=1, max_length=2_000)]
    display_text: Annotated[str, Field(min_length=1, max_length=2_000)]
    unit: str | None


class ComparisonSignature(_FrozenModel):
    relation: Literal["gt", "lt", "eq"]
    left_product_id: Annotated[str, Field(min_length=1, max_length=300)]
    right_product_id: Annotated[str, Field(min_length=1, max_length=300)]
    left_value_json: Annotated[str, Field(min_length=1, max_length=2_000)]
    right_value_json: Annotated[str, Field(min_length=1, max_length=2_000)]


class ClaimSignature(_FrozenModel):
    claim_id: Annotated[str, Field(min_length=1, max_length=200)]
    kind: ClaimKind
    surface_text: Annotated[str, Field(min_length=1, max_length=2_000)]
    entities: Annotated[tuple[EntitySignature, ...], Field(max_length=10)]
    values: Annotated[tuple[ValueSignature, ...], Field(max_length=10)]
    rank: Annotated[int, Field(ge=1)] | None
    tie_count: Annotated[int, Field(ge=1)] | None
    partition: Annotated[str, Field(min_length=1, max_length=300)] | None
    comparison: ComparisonSignature | None
    evidence_ids: Annotated[tuple[str, ...], Field(max_length=100)]
    limitation_codes: Annotated[tuple[str, ...], Field(max_length=100)]


class FactPack(_FrozenModel):
    format: Literal["finproof.fact-pack.v1"] = "finproof.fact-pack.v1"
    surface_parts: Annotated[tuple[SurfacePart, ...], Field(min_length=1, max_length=1)]
    claim_signatures: Annotated[tuple[ClaimSignature, ...], Field(max_length=300)]
    required_claim_ids: Annotated[tuple[str, ...], Field(max_length=300)]
    required_limitation_codes: Annotated[tuple[str, ...], Field(max_length=100)]
    evidence_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_exact_surface(self) -> Self:
        part = self.surface_parts[0]
        if part.part_id != "surface:answer":
            raise ValueError("fact pack surface differs")
        if part.claim_ids != self.required_claim_ids or (
            part.limitation_codes != self.required_limitation_codes
        ):
            raise ValueError("fact pack required tuples differ")
        if tuple(item.claim_id for item in self.claim_signatures) != self.required_claim_ids:
            raise ValueError("fact pack claim signatures differ")
        for values in (
            self.required_claim_ids,
            self.required_limitation_codes,
        ):
            if len(set(values)) != len(values):
                raise ValueError("fact pack required IDs must be unique")
        return self


class ProviderWording(_FrozenModel):
    presentation: Literal["조회 결과입니다.", "확인 결과입니다."]


class PreparedAnswer(_FrozenModel):
    fact_pack: FactPack
    claims: Annotated[tuple[AnswerClaim, ...], Field(max_length=300)]
    trace: ExecutionTrace
    retrieved_context: Annotated[str, Field(min_length=1, max_length=24_000)]
