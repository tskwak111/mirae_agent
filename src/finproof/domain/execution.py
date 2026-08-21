"""Validated execution contracts for the deterministic engine."""

from pydantic import BaseModel, ConfigDict, PrivateAttr

from finproof.domain.query_plan import (
    AggregationSpec,
    FilterClause,
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


class ExecutionTrace(_FrozenModel):
    pass
