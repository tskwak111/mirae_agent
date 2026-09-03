"""Fail-closed semantic validation over canonical QueryPlans."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from finproof.core.settings import ExecutionMode
from finproof.domain.execution import ValidatedQueryPlan
from finproof.domain.query_plan import Intent, ProductType, QueryPlan, ResultGrain
from finproof.entity.models import HoldingResolutionResult, ResolutionResult
from finproof.query.fields import FieldProjection, FieldRegistry


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ResolutionBundle(_FrozenModel):
    results: tuple[ResolutionResult, ...]
    holding_constituent: HoldingResolutionResult | None = None


class ValidationContext(_FrozenModel):
    as_of_date: date
    execution_mode: ExecutionMode


class SemanticValidator:
    def __init__(self, fields: FieldRegistry) -> None:
        if type(fields) is not FieldRegistry:
            raise TypeError("semantic validator requires exact query fields")
        self._fields = fields

    def validate(
        self,
        plan: QueryPlan,
        *,
        resolutions: ResolutionBundle,
        context: ValidationContext,
    ) -> ValidatedQueryPlan:
        if (
            type(plan) is not QueryPlan
            or type(resolutions) is not ResolutionBundle
            or type(context) is not ValidationContext
        ):
            raise TypeError("semantic validation inputs differ")
        if plan.as_of_date != context.as_of_date:
            raise ValueError("validation as-of date differs")
        if plan.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}:
            return ValidatedQueryPlan._issue(
                plan=plan,
                resolutions=resolutions,
                context=context,
            )
        expected_grain = (
            ResultGrain.PRODUCT
            if len(plan.product_types) > 1
            else _NATIVE_GRAIN[plan.product_types[0]]
        )
        if plan.result_grain is not expected_grain:
            raise ValueError("product type and result grain differ")
        requested_fields = {
            *(clause.field for clause in plan.filters),
            *plan.metrics,
            *(sort.field for sort in plan.sort),
        }
        if plan.aggregation is not None:
            requested_fields.update(plan.aggregation.group_by)
            if plan.aggregation.field is not None:
                requested_fields.add(plan.aggregation.field)
        if requested_fields & {"saleable", "mirae_saleable"} and set(plan.product_types) & {
            ProductType.OVERSEAS_ETF,
            ProductType.OVERSEAS_ETN,
            ProductType.PUBLIC_FUND,
        }:
            raise ValueError("validated eligibility is unsupported for product type")
        if len(resolutions.results) != len(plan.entities):
            raise ValueError("entity resolution count differs")
        for resolution in resolutions.results:
            if (
                resolution.selected is None
                or not resolution.candidates
                or resolution.selected is not resolution.candidates[0]
                or resolution.selected.product_type not in plan.product_types
            ):
                raise ValueError("entity resolution is not uniquely selected")

        registry_fields = self._fields._registries.fields.entries
        holding_filters = tuple(
            clause for clause in plan.filters if clause.field == "holding_constituent"
        )
        if len(holding_filters) > 1:
            raise ValueError("holding constituent filter cardinality differs")
        if holding_filters:
            if ProductType.DOMESTIC_BOND in plan.product_types:
                raise ValueError("holding constituent cannot be combined with domestic bond")
            holding_resolution = resolutions.holding_constituent
            if (
                type(holding_resolution) is not HoldingResolutionResult
                or holding_resolution.selected is None
                or len(holding_resolution.candidates) != 1
                or holding_resolution.selected is not holding_resolution.candidates[0]
            ):
                raise ValueError("holding resolution is not uniquely selected")
        elif resolutions.holding_constituent is not None:
            raise ValueError("holding resolution lacks a relation filter")
        for clause in plan.filters:
            definition = registry_fields.get(clause.field)
            if clause.field == "holding_constituent":
                if (
                    definition is None
                    or clause.operator not in definition.operators
                    or type(clause.value) is not str
                    or any(
                        product not in definition.product_types for product in plan.product_types
                    )
                ):
                    raise ValueError("holding filter differs")
                continue
            projections = _projections(self._fields, clause.field, plan.product_types)
            if definition is None or not projections:
                raise ValueError("filter field has no selected product target")
            if clause.operator not in definition.operators:
                raise ValueError("filter operator is not registered")
            if clause.value is not None:
                values = clause.value if isinstance(clause.value, tuple) else (clause.value,)
                if any(
                    not _value_matches(value, projection.value_type)
                    for projection in projections
                    for value in values
                ):
                    raise ValueError("filter value type differs")

        for metric in plan.metrics:
            if not _projections(self._fields, metric, plan.product_types):
                raise ValueError("metric has no selected product target")
        for target in plan.metric_targets:
            if any(
                (metric, target.product_type) not in self._fields.projections
                for metric in target.metrics
            ):
                raise ValueError("metric target is not registered")
        for sort in plan.sort:
            definition = registry_fields.get(sort.field)
            if (
                definition is None
                or not definition.sortable
                or not _projections(self._fields, sort.field, plan.product_types)
            ):
                raise ValueError("sort field is not registered")
        if plan.aggregation is not None:
            aggregation = plan.aggregation
            if aggregation.field is None:
                if (
                    aggregation.function
                    not in self._fields._registries.fields.targetless_aggregations
                ):
                    raise ValueError("aggregation operation is not registered")
            else:
                definition = registry_fields.get(aggregation.field)
                if (
                    definition is None
                    or aggregation.function not in definition.aggregations
                    or not _projections(self._fields, aggregation.field, plan.product_types)
                ):
                    raise ValueError("aggregation target is not registered")
            if any(
                not _projections(self._fields, group, plan.product_types)
                for group in aggregation.group_by
            ):
                raise ValueError("aggregation group is not registered")
        return ValidatedQueryPlan._issue(
            plan=plan,
            resolutions=resolutions,
            context=context,
        )


def _projections(
    fields: FieldRegistry,
    field_id: str,
    product_types: tuple[ProductType, ...],
) -> tuple[FieldProjection, ...]:
    return tuple(
        projection
        for product_type in product_types
        if (projection := fields.projections.get((field_id, product_type))) is not None
    )


def _value_matches(value: object, value_type: str) -> bool:
    if value_type in {"string", "ordinal_rating"}:
        return type(value) is str
    if value_type == "boolean":
        return type(value) is bool
    if value_type == "integer":
        return type(value) is int
    if value_type == "decimal":
        return type(value) in {int, Decimal}
    if value_type == "date":
        if type(value) is not str:
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    return False


_NATIVE_GRAIN = {
    ProductType.DOMESTIC_BOND: ResultGrain.INSTRUMENT,
    ProductType.DOMESTIC_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.DOMESTIC_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.PUBLIC_FUND: ResultGrain.FUND_ITEM,
}
