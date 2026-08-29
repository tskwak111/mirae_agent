"""Strict model-facing Phase 2 query contracts."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Intent(StrEnum):
    LOOKUP = "lookup"
    SCREEN = "screen"
    SCREEN_RANK = "screen_rank"
    COMPARE = "compare"
    AGGREGATE = "aggregate"
    EXPLAIN = "explain"
    CLARIFY = "clarify"
    UNSUPPORTED = "unsupported"


class ProductType(StrEnum):
    DOMESTIC_BOND = "domestic_bond"
    DOMESTIC_ETF = "domestic_etf"
    DOMESTIC_ETN = "domestic_etn"
    OVERSEAS_ETF = "overseas_etf"
    OVERSEAS_ETN = "overseas_etn"
    PUBLIC_FUND = "public_fund"


class ResultGrain(StrEnum):
    PRODUCT = "product"
    INSTRUMENT = "instrument"
    LISTED_PRODUCT = "listed_product"
    FUND_ITEM = "fund_item"
    FUND_ATTRIBUTE = "fund_attribute"
    FUND_FAMILY_CANDIDATE = "fund_family_candidate"


class TopKScope(StrEnum):
    GLOBAL = "global"
    PER_PRODUCT_TYPE = "per_product_type"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class AggregationFunction(StrEnum):
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    AVG = "avg"


class FilterOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    IS_MISSING = "is_missing"
    IS_NOT_MISSING = "is_not_missing"


class EntityIdentifierType(StrEnum):
    UNKNOWN = "unknown"
    PRODUCT_ID = "product_id"
    MARKET_IDENTIFIER = "market_identifier"
    ISIN = "isin"
    TICKER = "ticker"
    NAME = "name"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EntityMention(_FrozenModel):
    text: Annotated[str, Field(min_length=1, max_length=300)]
    identifier_type: EntityIdentifierType = EntityIdentifierType.UNKNOWN


class FilterClause(_FrozenModel):
    field: Annotated[str, Field(min_length=1, max_length=100)]
    operator: FilterOperator
    value: str | int | Decimal | bool | tuple[str | int | Decimal | bool, ...] | None = None

    @model_validator(mode="after")
    def _validate_value_shape(self) -> Self:
        has_value = "value" in self.model_fields_set
        scalar_operators = {
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.GT,
            FilterOperator.GTE,
            FilterOperator.LT,
            FilterOperator.LTE,
            FilterOperator.CONTAINS,
            FilterOperator.STARTS_WITH,
        }
        if self.operator in scalar_operators:
            if not has_value or self.value is None or isinstance(self.value, tuple):
                raise ValueError("operator requires one scalar value")
        elif self.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
            if not isinstance(self.value, tuple) or not 1 <= len(self.value) <= 50:
                raise ValueError("operator requires one to fifty scalar values")
        elif self.operator is FilterOperator.BETWEEN:
            if not isinstance(self.value, tuple) or len(self.value) != 2:
                raise ValueError("between requires exactly two scalar values")
        elif has_value:
            raise ValueError("missing-value operators prohibit a value")
        return self


class SortSpec(_FrozenModel):
    field: Annotated[str, Field(min_length=1, max_length=100)]
    direction: SortDirection


class AggregationSpec(_FrozenModel):
    function: AggregationFunction
    field: Annotated[str, Field(min_length=1, max_length=100)] | None
    group_by: tuple[Annotated[str, Field(min_length=1, max_length=100)], ...]

    @model_validator(mode="after")
    def _validate_function_shape(self) -> Self:
        if self.function is AggregationFunction.COUNT:
            if self.field is not None:
                raise ValueError("count prohibits a target field")
        elif self.field is None:
            raise ValueError("value aggregation requires a target field")
        if len(self.group_by) > 2 or len(set(self.group_by)) != len(self.group_by):
            raise ValueError("group_by requires at most two unique fields")
        return self


class MetricTarget(_FrozenModel):
    product_type: ProductType
    metrics: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=100)], ...],
        Field(min_length=1, max_length=20),
    ]

    @model_validator(mode="after")
    def _validate_metrics(self) -> Self:
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("target metrics must be unique")
        return self


class QueryPlan(_FrozenModel):
    intent: Intent
    product_types: Annotated[tuple[ProductType, ...], Field(max_length=6)]
    entities: Annotated[tuple[EntityMention, ...], Field(max_length=10)]
    as_of_date: date
    result_grain: ResultGrain
    filters: Annotated[tuple[FilterClause, ...], Field(max_length=20)]
    metrics: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=100)], ...],
        Field(max_length=20),
    ]
    metric_targets: Annotated[tuple[MetricTarget, ...], Field(max_length=6)] = ()
    sort: Annotated[tuple[SortSpec, ...], Field(max_length=5)]
    aggregation: AggregationSpec | None
    top_k: Annotated[int, Field(ge=1, le=50)]
    top_k_scope: TopKScope
    needs_clarification: bool
    clarification_reason: Annotated[str, Field(max_length=1000)]

    @model_validator(mode="after")
    def _validate_aggregation_intent(self) -> Self:
        if len(set(self.product_types)) != len(self.product_types):
            raise ValueError("product types must be unique")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("metrics must be unique")
        if self.metric_targets:
            if self.intent is not Intent.SCREEN_RANK:
                raise ValueError("metric targets require screen rank intent")
            if self.top_k_scope is not TopKScope.PER_PRODUCT_TYPE:
                raise ValueError("metric targets require per-product-type top-k")
            if tuple(target.product_type for target in self.metric_targets) != self.product_types:
                raise ValueError("metric targets must follow selected product types")
            if {metric for target in self.metric_targets for metric in target.metrics} != set(
                self.metrics
            ):
                raise ValueError("metric targets must cover plan metrics")
            if any(
                target.metrics
                != tuple(metric for metric in self.metrics if metric in target.metrics)
                for target in self.metric_targets
            ):
                raise ValueError("target metrics must preserve plan metric order")
        if (self.intent is Intent.AGGREGATE) != (self.aggregation is not None):
            raise ValueError("aggregation is present exactly for aggregate intent")
        terminal = self.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}
        if terminal:
            if self.filters or self.metrics or self.sort or self.aggregation is not None:
                raise ValueError("non-executable intents prohibit executable clauses")
            if not self.clarification_reason.strip():
                raise ValueError("non-executable intents require a reason")
            if (self.intent is Intent.CLARIFY) != self.needs_clarification:
                raise ValueError("clarify alone requires clarification")
        elif not self.product_types or self.needs_clarification or self.clarification_reason != "":
            raise ValueError("executable intents require products and no clarification")

        native_grains = {
            ResultGrain.INSTRUMENT
            if product is ProductType.DOMESTIC_BOND
            else ResultGrain.FUND_ITEM
            if product is ProductType.PUBLIC_FUND
            else ResultGrain.LISTED_PRODUCT
            for product in self.product_types
        }
        if len(native_grains) > 1 and self.result_grain is not ResultGrain.PRODUCT:
            raise ValueError("heterogeneous native grains require the product envelope")
        if (
            self.result_grain is ResultGrain.PRODUCT
            and len(self.product_types) < 2
            and not terminal
        ):
            raise ValueError("the product envelope requires heterogeneous native grains")
        return self
