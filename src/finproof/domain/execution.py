"""Validated execution contracts for the deterministic engine."""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from finproof.domain.query_plan import (
    AggregationSpec,
    FilterClause,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    SortSpec,
    TopKScope,
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ValidatedQueryPlan(_FrozenModel):
    _context: object = PrivateAttr()
    _resolutions: object = PrivateAttr()

    plan: QueryPlan

    @classmethod
    def _issue(
        cls,
        *,
        plan: QueryPlan,
        resolutions: object,
        context: object,
    ) -> "ValidatedQueryPlan":
        value = cls(plan=plan)
        value._resolutions = resolutions
        value._context = context
        return value

    @property
    def resolutions(self) -> object:
        return self._resolutions

    @property
    def context(self) -> object:
        return self._context


class ComparisonPartition(_FrozenModel):
    partition_id: str
    product_types: tuple[ProductType, ...]
    compatibility_key: str


class ExecutionSegment(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    filters: tuple[FilterClause, ...]
    metrics: tuple[str, ...]
    sort: tuple[SortSpec, ...]
    aggregation: AggregationSpec | None
    top_k: int


class ExecutionBundle(_FrozenModel):
    validated_plan: ValidatedQueryPlan
    top_k_scope: TopKScope
    segments: tuple[ExecutionSegment, ...]
    comparison_partitions: tuple[ComparisonPartition, ...]
    response_grain: ResultGrain


class TraceValidation(StrEnum):
    PASSED = "passed"
    CLARIFY = "clarify"
    UNSUPPORTED = "unsupported"
    SAFE_FAILURE = "safe_failure"


class ExecutionTraceSegment(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    partition_key: Annotated[str, Field(min_length=1, max_length=300)]
    candidate_counts: dict[str, Annotated[int, Field(ge=0)]]
    returned: Annotated[int, Field(ge=0)]


class ExecutionTrace(_FrozenModel):
    correlation_id: Annotated[str, Field(min_length=1, max_length=200)]
    intent: Intent
    product_types: Annotated[tuple[ProductType, ...], Field(max_length=6)]
    as_of_date: date
    result_grain: ResultGrain
    top_k_scope: TopKScope
    segments: Annotated[tuple[ExecutionTraceSegment, ...], Field(max_length=6)]
    candidate_counts: dict[str, Annotated[int, Field(ge=0)]]
    tools: Annotated[tuple[str, ...], Field(max_length=20)]
    policy_ids: Annotated[tuple[str, ...], Field(max_length=32)]
    validation: TraceValidation
    versions: dict[str, str]
    latency_ms: dict[str, Annotated[int, Field(ge=0)]]
