"""Typed authoring contracts for human-reviewed golden cases."""

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from finproof.domain.query_plan import (
    AggregationFunction,
    AggregationSpec,
    EntityMention,
    FilterClause,
    Intent,
    MetricTarget,
    ProductType,
    ResultGrain,
    SortSpec,
    TopKScope,
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvaluationCategory(StrEnum):
    LOOKUP = "lookup"
    SCREEN = "screen"
    RANK = "rank"
    COMPARE = "compare"
    AGGREGATE = "aggregate"
    CROSS_PRODUCT = "cross_product"
    CLARIFICATION = "clarification"
    QUALITY = "quality"
    ADVERSARIAL = "adversarial"


class ExpectedSegment(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain


def native_result_grain(product_type: ProductType) -> ResultGrain:
    if product_type is ProductType.DOMESTIC_BOND:
        return ResultGrain.INSTRUMENT
    if product_type is ProductType.PUBLIC_FUND:
        return ResultGrain.FUND_ITEM
    return ResultGrain.LISTED_PRODUCT


class ExpectedPlan(_FrozenModel):
    """A checked expectation subset, never an executable partial QueryPlan."""

    intent: Intent
    product_types: Annotated[tuple[ProductType, ...], Field(max_length=6)]
    as_of_date: date
    result_grain: ResultGrain
    top_k_scope: TopKScope
    filters: Annotated[tuple[FilterClause, ...], Field(max_length=20)] | None = None
    metrics: (
        Annotated[
            tuple[Annotated[str, Field(min_length=1, max_length=100)], ...],
            Field(max_length=20),
        ]
        | None
    ) = None
    metric_targets: Annotated[tuple[MetricTarget, ...], Field(max_length=6)] | None = None
    sort: Annotated[tuple[SortSpec, ...], Field(max_length=5)] | None = None
    top_k: Annotated[int, Field(ge=1, le=50)] | None = None
    needs_clarification: bool | None = None
    clarification_reason: Annotated[str, Field(max_length=1_000)] | None = None
    aggregation: AggregationSpec | None = None
    native_segments: Annotated[tuple[ExpectedSegment, ...], Field(max_length=6)] = ()

    @field_validator("filters", mode="before")
    @classmethod
    def _parse_filters(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and all(type(item) is FilterClause for item in value):
            return tuple(value)
        if isinstance(value, (list, tuple)):
            value = [
                {key: child for key, child in item.items() if key != "value"}
                if isinstance(item, Mapping)
                and item.get("operator") in {"is_missing", "is_not_missing"}
                and item.get("value") is None
                else item
                for item in value
            ]
        return TypeAdapter(tuple[FilterClause, ...]).validate_json(json.dumps(value))

    @field_validator("metric_targets", mode="before")
    @classmethod
    def _parse_metric_targets(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and all(type(item) is MetricTarget for item in value):
            return tuple(value)
        return TypeAdapter(tuple[MetricTarget, ...]).validate_json(json.dumps(value))

    @field_validator("sort", mode="before")
    @classmethod
    def _parse_sort(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and all(type(item) is SortSpec for item in value):
            return tuple(value)
        return TypeAdapter(tuple[SortSpec, ...]).validate_json(json.dumps(value))

    @field_validator("aggregation", mode="before")
    @classmethod
    def _parse_aggregation(cls, value: object) -> object:
        if value is None or type(value) is AggregationSpec:
            return value
        return AggregationSpec.model_validate_json(json.dumps(value))

    @model_validator(mode="after")
    def _validate_grain_and_segments(self) -> Self:
        if (self.intent is Intent.AGGREGATE) != (self.aggregation is not None):
            raise ValueError("aggregate expectations require exactly one aggregation")
        terminal = self.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}
        if terminal:
            if not self.clarification_reason or not self.clarification_reason.strip():
                raise ValueError("terminal expectations require a reason")
            if (self.intent is Intent.CLARIFY) != self.needs_clarification:
                raise ValueError("clarify alone expects clarification")
            if self.filters or self.metrics or self.sort:
                raise ValueError("terminal expectations prohibit executable clauses")
        elif self.needs_clarification is True or self.clarification_reason not in {None, ""}:
            raise ValueError("executable expectations cannot require clarification")
        elif not self.product_types:
            raise ValueError("executable expectations require products")
        if len(set(self.product_types)) != len(self.product_types):
            raise ValueError("expected product types must be unique")
        if self.metrics is not None and len(set(self.metrics)) != len(self.metrics):
            raise ValueError("expected metrics must be unique")
        if self.metric_targets:
            if (
                self.intent is not Intent.SCREEN_RANK
                or self.top_k_scope is not TopKScope.PER_PRODUCT_TYPE
            ):
                raise ValueError("expected metric targets require per-product screen rank")
            if tuple(target.product_type for target in self.metric_targets) != self.product_types:
                raise ValueError("expected metric targets must follow product types")
            if self.metrics is None or {
                metric for target in self.metric_targets for metric in target.metrics
            } != set(self.metrics):
                raise ValueError("expected metric targets must cover metrics")
            if any(
                target.metrics
                != tuple(metric for metric in self.metrics if metric in target.metrics)
                for target in self.metric_targets
            ):
                raise ValueError("expected metric targets must preserve metric order")
        native_by_product = {
            product: native_result_grain(product) for product in self.product_types
        }
        native_grains = set(native_by_product.values())
        if len(native_grains) > 1 and self.result_grain is not ResultGrain.PRODUCT:
            raise ValueError("heterogeneous expected plans require the product envelope")
        if not terminal and len(native_grains) == 1:
            native_grain = next(iter(native_grains))
            allowed_grains = (
                {native_grain, ResultGrain.PRODUCT}
                if len(self.product_types) > 1
                else {native_grain}
            )
            if self.result_grain not in allowed_grains:
                raise ValueError("expected plan has the wrong result grain")
        if self.native_segments:
            segments = {segment.product_type: segment for segment in self.native_segments}
            selected = set(self.product_types)
            segment_products = set(segments)
            if len(segments) != len(self.native_segments) or not segment_products <= selected:
                raise ValueError("expected native segments must be selected product types")
            if any(
                segment.native_result_grain is not native_by_product[product]
                for product, segment in segments.items()
            ):
                raise ValueError("expected segment has the wrong native result grain")
        elif len(self.product_types) > 1:
            raise ValueError("multi-product expectations require native segments")
        return self


class ValueType(StrEnum):
    DECIMAL = "decimal"
    INTEGER = "integer"
    DATE = "date"
    TEXT = "text"
    BOOLEAN = "boolean"
    NULL = "null"


class _TypedScalar(_FrozenModel):
    value_type: ValueType
    value: Decimal | date | str | bool | int | None

    @model_validator(mode="before")
    @classmethod
    def _parse_declared_type(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        parsed = dict(value)
        declared = parsed.get("value_type")
        raw = parsed.get("value")
        if declared == ValueType.DECIMAL or declared == ValueType.DECIMAL.value:
            parsed["value"] = Decimal(str(raw))
        elif declared == ValueType.INTEGER or declared == ValueType.INTEGER.value:
            if type(raw) is int:
                parsed["value"] = raw
            elif type(raw) is str:
                parsed["value"] = int(raw)
            else:
                raise ValueError("integer expectation requires an integer")
        elif declared == ValueType.DATE or declared == ValueType.DATE.value:
            parsed["value"] = raw if type(raw) is date else date.fromisoformat(str(raw))
        return parsed

    @model_validator(mode="after")
    def _validate_declared_type(self) -> Self:
        expected_type = {
            ValueType.DECIMAL: Decimal,
            ValueType.INTEGER: int,
            ValueType.DATE: date,
            ValueType.TEXT: str,
            ValueType.BOOLEAN: bool,
            ValueType.NULL: type(None),
        }[self.value_type]
        if type(self.value) is not expected_type:
            raise ValueError("value does not match its declared type")
        return self


class _TypedValue(_TypedScalar):
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    field_id: Annotated[str, Field(min_length=1, max_length=100)]


class ExpectedValue(_TypedValue):
    display_tolerance: Annotated[Decimal, Field(ge=0)] = Decimal(0)


class ObservedValue(_TypedValue):
    pass


class ProductIdentity(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    product_id: Annotated[str, Field(min_length=1, max_length=300)]

    @model_validator(mode="after")
    def _validate_native_result_grain(self) -> Self:
        if self.native_result_grain is not native_result_grain(self.product_type):
            raise ValueError("product identity has the wrong native result grain")
        return self


class AggregateGroupValue(_TypedScalar):
    field_id: Annotated[str, Field(min_length=1, max_length=100)]


class _AggregateValue(_TypedScalar):
    function: AggregationFunction
    field_id: Annotated[str, Field(min_length=1, max_length=100)] | None
    product_type: ProductType
    native_result_grain: ResultGrain
    partition_key: Annotated[str, Field(min_length=1, max_length=300)]
    group_values: Annotated[tuple[AggregateGroupValue, ...], Field(max_length=2)] = ()

    @model_validator(mode="after")
    def _validate_aggregate_identity(self) -> Self:
        if self.function is AggregationFunction.COUNT:
            if self.field_id is not None:
                raise ValueError("count aggregate prohibits a target field")
        elif self.field_id is None:
            raise ValueError("value aggregate requires a target field")
        if self.native_result_grain is not native_result_grain(self.product_type):
            raise ValueError("aggregate has the wrong native result grain")
        if len({group.field_id for group in self.group_values}) != len(self.group_values):
            raise ValueError("aggregate group fields must be unique")
        return self


class ExpectedAggregate(_AggregateValue):
    pass


class ObservedAggregate(_AggregateValue):
    pass


def aggregate_key(value: _AggregateValue) -> tuple[object, ...]:
    return (
        value.function,
        value.field_id,
        value.product_type,
        value.native_result_grain,
        value.partition_key,
        tuple((group.field_id, group.value_type, group.value) for group in value.group_values),
    )


class ExpectedResult(_FrozenModel):
    products: tuple[ProductIdentity, ...] = ()
    order_matters: bool = False
    values: tuple[ExpectedValue, ...] = ()
    aggregates: tuple[ExpectedAggregate, ...] = ()
    required_evidence_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    required_compatibility_partitions: tuple[
        Annotated[str, Field(min_length=1, max_length=300)], ...
    ] = ()
    assembled_envelope: bool | None = None

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        if len(set(self.products)) != len(self.products):
            raise ValueError("expected results require unique full product identities")
        if self.order_matters and not self.products:
            raise ValueError("order_matters requires expected products")
        value_keys = {(value.product_id, value.field_id) for value in self.values}
        if len(value_keys) != len(self.values):
            raise ValueError("expected values must have unique product and field keys")
        aggregate_keys = {aggregate_key(value) for value in self.aggregates}
        if len(aggregate_keys) != len(self.aggregates):
            raise ValueError("expected aggregates must have unique full aggregate keys")
        return self


class ExpectedAnswerSemantics(_FrozenModel):
    required_concepts: tuple[Annotated[str, Field(min_length=1, max_length=500)], ...]
    forbidden_concepts: tuple[Annotated[str, Field(min_length=1, max_length=500)], ...]
    expect_limitation: bool | None = None
    expect_clarification: bool | None = None


class ReviewMetadata(_FrozenModel):
    reviewer: Annotated[str, Field(min_length=1, max_length=200)]
    reviewed_at: date
    source: Annotated[str, Field(min_length=1, max_length=1_000)]

    @field_validator("reviewer", "source")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("review metadata cannot be blank")
        return value


class GoldenCase(_FrozenModel):
    case_id: Annotated[str, Field(min_length=1, max_length=200)]
    category: EvaluationCategory
    question: Annotated[str, Field(min_length=1, max_length=4_000)]
    expected_plan: ExpectedPlan
    reviewed_entities: Annotated[tuple[EntityMention, ...], Field(max_length=20)] = ()
    expected_result: ExpectedResult
    expected_answer: ExpectedAnswerSemantics
    review: ReviewMetadata

    @field_validator("reviewed_entities", mode="before")
    @classmethod
    def _parse_reviewed_entities(cls, value: object) -> object:
        if isinstance(value, (list, tuple)) and all(type(item) is EntityMention for item in value):
            return tuple(value)
        return TypeAdapter(tuple[EntityMention, ...]).validate_json(json.dumps(value), strict=True)

    @field_validator("case_id", "question")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("golden-case text cannot be blank")
        return value

    @model_validator(mode="after")
    def _validate_envelope_expectation(self) -> Self:
        if (
            self.expected_plan.native_segments
            and len(self.expected_plan.native_segments) < len(self.expected_plan.product_types)
            and self.expected_answer.expect_limitation is not True
        ):
            raise ValueError("pruned native segments require an explicit limitation")
        expected = self.expected_result.assembled_envelope
        if expected is None:
            return self
        actual = (
            self.expected_plan.result_grain is ResultGrain.PRODUCT
            and len({segment.native_result_grain for segment in self.expected_plan.native_segments})
            > 1
        )
        if expected is not actual:
            raise ValueError("expected envelope must match the expected execution shape")
        return self


class ObservedSegment(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    compatibility_partition: Annotated[str, Field(min_length=1, max_length=300)]


class ObservedCase(_FrozenModel):
    plan: "QueryPlan | None" = None
    products: tuple[ProductIdentity, ...] = ()
    values: tuple[ObservedValue, ...] = ()
    aggregates: tuple[ObservedAggregate, ...] = ()
    answer_text: str = ""
    evidence_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    limitation_present: bool = False
    clarification_present: bool = False
    repeat_signatures: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    segments: tuple[ObservedSegment, ...] = ()
    compatibility_partitions: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    assembled_envelope: bool = False
    latency_ms: tuple[Annotated[int, Field(ge=0)], ...] = ()

    @model_validator(mode="after")
    def _validate_product_identities(self) -> Self:
        if len(set(self.products)) != len(self.products):
            raise ValueError("observations require unique full product identities")
        aggregate_keys = {aggregate_key(value) for value in self.aggregates}
        if len(aggregate_keys) != len(self.aggregates):
            raise ValueError("observations require unique full aggregate keys")
        return self


from finproof.domain.query_plan import QueryPlan  # noqa: E402

ObservedCase.model_rebuild()
