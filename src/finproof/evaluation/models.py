"""Typed authoring contracts for human-reviewed golden cases."""

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from finproof.domain.query_plan import (
    AggregationSpec,
    FilterClause,
    Intent,
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


class ExpectedPlan(_FrozenModel):
    """A checked expectation subset, never an executable partial QueryPlan."""

    intent: Intent
    product_types: tuple[ProductType, ...]
    as_of_date: date
    result_grain: ResultGrain
    top_k_scope: TopKScope
    filters: tuple[FilterClause, ...] | None = None
    metrics: tuple[Annotated[str, Field(min_length=1, max_length=100)], ...] | None = None
    sort: tuple[SortSpec, ...] | None = None
    top_k: Annotated[int, Field(ge=1, le=50)] | None = None
    needs_clarification: bool | None = None
    clarification_reason: Annotated[str, Field(max_length=1_000)] | None = None
    aggregation: AggregationSpec | None = None
    native_segments: tuple[ExpectedSegment, ...] = ()

    @field_validator("filters", mode="before")
    @classmethod
    def _parse_filters(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and all(type(item) is FilterClause for item in value):
            return tuple(value)
        return TypeAdapter(tuple[FilterClause, ...]).validate_json(json.dumps(value))

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
        if len(set(self.product_types)) != len(self.product_types):
            raise ValueError("expected product types must be unique")
        native_by_product = {
            product: ResultGrain.INSTRUMENT
            if product is ProductType.DOMESTIC_BOND
            else ResultGrain.FUND_ITEM
            if product is ProductType.PUBLIC_FUND
            else ResultGrain.LISTED_PRODUCT
            for product in self.product_types
        }
        native_grains = set(native_by_product.values())
        if len(native_grains) > 1 and self.result_grain is not ResultGrain.PRODUCT:
            raise ValueError("heterogeneous expected plans require the product envelope")
        if self.native_segments:
            segments = {segment.product_type: segment for segment in self.native_segments}
            if len(segments) != len(self.native_segments) or set(segments) != set(
                self.product_types
            ):
                raise ValueError("multi-product expectations require one native segment per type")
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


class _TypedValue(_FrozenModel):
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    field_id: Annotated[str, Field(min_length=1, max_length=100)]
    value_type: ValueType
    value: Decimal | date | str | bool | int

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
        }[self.value_type]
        if type(self.value) is not expected_type:
            raise ValueError("value does not match its declared type")
        return self


class ExpectedValue(_TypedValue):
    display_tolerance: Annotated[Decimal, Field(ge=0)] = Decimal(0)


class ObservedValue(_TypedValue):
    pass


class ExpectedResult(_FrozenModel):
    product_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    order_matters: bool = False
    values: tuple[ExpectedValue, ...] = ()
    required_evidence_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    required_compatibility_partitions: tuple[
        Annotated[str, Field(min_length=1, max_length=300)], ...
    ] = ()
    assembled_envelope: bool | None = None

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        if len(set(self.product_ids)) != len(self.product_ids):
            raise ValueError("expected product ordering cannot contain duplicates")
        if self.order_matters and not self.product_ids:
            raise ValueError("order_matters requires expected products")
        value_keys = {(value.product_id, value.field_id) for value in self.values}
        if len(value_keys) != len(self.values):
            raise ValueError("expected values must have unique product and field keys")
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
    expected_result: ExpectedResult
    expected_answer: ExpectedAnswerSemantics
    review: ReviewMetadata

    @field_validator("case_id", "question")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("golden-case text cannot be blank")
        return value


class ObservedSegment(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    compatibility_partition: Annotated[str, Field(min_length=1, max_length=300)]


class ObservedCase(_FrozenModel):
    plan: "QueryPlan | None" = None
    product_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    values: tuple[ObservedValue, ...] = ()
    answer_text: str = ""
    evidence_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    limitation_present: bool = False
    clarification_present: bool = False
    repeat_signatures: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    segments: tuple[ObservedSegment, ...] = ()
    compatibility_partitions: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...] = ()
    assembled_envelope: bool | None = None
    latency_ms: tuple[Annotated[int, Field(ge=0)], ...] = ()


from finproof.domain.query_plan import QueryPlan  # noqa: E402

ObservedCase.model_rebuild()
