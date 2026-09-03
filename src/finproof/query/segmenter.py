"""Native execution-segment construction."""

from finproof.domain.execution import (
    ComparisonPartition,
    ExecutionBundle,
    ExecutionLimitationCode,
    ExecutionSegment,
    HoldingConstituentFilter,
    ValidatedQueryPlan,
)
from finproof.domain.query_plan import (
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    ResultGrain,
    TopKScope,
)
from finproof.query.fields import FieldRegistry
from finproof.query.semantic_validator import ResolutionBundle, ValidationContext


class ExecutionBundleBuilder:
    def __init__(self, fields: FieldRegistry) -> None:
        if type(fields) is not FieldRegistry:
            raise TypeError("segment builder requires exact query fields")
        self._fields = fields

    def build(
        self,
        plan: ValidatedQueryPlan,
        *,
        context: ValidationContext,
    ) -> ExecutionBundle:
        if type(plan) is not ValidatedQueryPlan or type(context) is not ValidationContext:
            raise TypeError("segment builder inputs differ")
        if plan.context != context:
            raise ValueError("segment validation context differs")
        original = plan.plan
        resolutions = plan.resolutions
        if type(resolutions) is not ResolutionBundle:
            raise TypeError("segment entity resolutions differ")
        metric_targets = {target.product_type: target.metrics for target in original.metric_targets}
        entity_ids = {
            product_type: tuple(
                result.selected.product_id
                for result in resolutions.results
                if result.selected is not None and result.selected.product_type is product_type
            )
            for product_type in ProductType
        }
        holding_resolution = resolutions.holding_constituent
        holding_filter = (
            HoldingConstituentFilter(
                constituent_identifier=holding_resolution.selected.constituent_identifier,
                constituent_identifier_type=(
                    holding_resolution.selected.constituent_identifier_type
                ),
            )
            if holding_resolution is not None and holding_resolution.selected is not None
            else None
        )
        requested_fields = {
            *(clause.field for clause in original.filters),
            *original.metrics,
            *(sort.field for sort in original.sort),
            *(original.aggregation.group_by if original.aggregation is not None else ()),
            *(
                (original.aggregation.field,)
                if original.aggregation is not None and original.aggregation.field is not None
                else ()
            ),
        }
        prune_overseas_1y = (
            not metric_targets
            and "return_1y" in requested_fields
            and any(
                product_type in {ProductType.OVERSEAS_ETF, ProductType.OVERSEAS_ETN}
                for product_type in original.product_types
            )
        )
        segments = tuple(
            ExecutionSegment(
                product_type=product_type,
                native_result_grain=_NATIVE_GRAIN[product_type],
                filters=(
                    *(
                        _canonical_filter_literal(clause, product_type=product_type)
                        for clause in original.filters
                        if (clause.field, product_type) in self._fields.projections
                    ),
                    *(
                        (
                            FilterClause(
                                field="product_id",
                                operator=FilterOperator.IN,
                                value=entity_ids[product_type],
                            ),
                        )
                        if entity_ids[product_type]
                        else ()
                    ),
                ),
                metrics=metric_targets.get(
                    product_type,
                    tuple(
                        metric
                        for metric in original.metrics
                        if (metric, product_type) in self._fields.projections
                    ),
                ),
                sort=tuple(
                    sort
                    for sort in original.sort
                    if (sort.field, product_type) in self._fields.projections
                    and (
                        not metric_targets
                        or sort.field not in original.metrics
                        or sort.field in metric_targets[product_type]
                    )
                ),
                aggregation=original.aggregation,
                top_k=original.top_k,
                holding_constituent_filter=holding_filter,
            )
            for product_type in ProductType
            if product_type in original.product_types
            and not (
                prune_overseas_1y
                and product_type in {ProductType.OVERSEAS_ETF, ProductType.OVERSEAS_ETN}
            )
        )
        partitions = self._comparison_partitions(segments)
        if (
            original.top_k_scope is TopKScope.GLOBAL
            and (original.sort or original.intent is Intent.AGGREGATE)
            and len(partitions) != 1
        ):
            raise ValueError("global sort or aggregate requires one compatible partition")
        return ExecutionBundle(
            validated_plan=plan,
            top_k_scope=original.top_k_scope,
            segments=segments,
            comparison_partitions=partitions,
            response_grain=original.result_grain,
            limitations=(
                (ExecutionLimitationCode.OVERSEAS_RETURN_1Y_UNAVAILABLE,)
                if prune_overseas_1y
                else ()
            ),
        )

    def _comparison_partitions(
        self, segments: tuple[ExecutionSegment, ...]
    ) -> tuple[ComparisonPartition, ...]:
        groups: dict[str, list[ProductType]] = {}
        for segment in segments:
            targetless_count = segment.aggregation is not None and segment.aggregation.field is None
            if targetless_count:
                groups[
                    f"count:{segment.native_result_grain.value}:{segment.product_type.value}"
                ] = [segment.product_type]
            field_ids = set() if targetless_count else set(segment.metrics)
            field_ids.update(sort.field for sort in segment.sort)
            if segment.aggregation is not None and segment.aggregation.field is not None:
                field_ids.add(segment.aggregation.field)
            for field_id in sorted(field_ids):
                projection = self._fields.projection(field_id, segment.product_type)
                if projection.metric_id is None:
                    key = f"field:{field_id}:{projection.value_type}"
                else:
                    metric = self._fields._registries.metrics.entries[projection.metric_id]
                    key = ":".join(
                        str(value)
                        for value in (
                            metric.comparability_group,
                            metric.unit,
                            metric.period,
                            metric.currency,
                            metric.cross_product_policy,
                        )
                    )
                products = groups.setdefault(key, [])
                if segment.product_type not in products:
                    products.append(segment.product_type)
        return tuple(
            ComparisonPartition(
                partition_id=f"partition-{index}",
                product_types=tuple(product_types),
                compatibility_key=key,
            )
            for index, (key, product_types) in enumerate(groups.items(), start=1)
        )


def execution_literal_policy_ids(bundle: ExecutionBundle) -> tuple[str, ...]:
    """Return deterministic identities for reviewed literal bindings used by execution."""
    if type(bundle) is not ExecutionBundle:
        raise TypeError("literal policy input differs")
    original = bundle.validated_plan.plan.filters
    return (
        ("literal:region-ko-us:1.0.0",)
        if any(clause.field == "region" and clause.value == "미국" for clause in original)
        and any(
            clause.field == "region" and clause.value == "United States of America"
            for segment in bundle.segments
            for clause in segment.filters
        )
        else ()
    )


def _canonical_filter_literal(
    clause: FilterClause,
    *,
    product_type: ProductType,
) -> FilterClause:
    if (
        product_type in {ProductType.OVERSEAS_ETF, ProductType.OVERSEAS_ETN}
        and clause.field == "region"
        and clause.operator is FilterOperator.EQ
        and clause.value == "미국"
    ):
        return clause.model_copy(update={"value": "United States of America"})
    return clause


_NATIVE_GRAIN = {
    ProductType.DOMESTIC_BOND: ResultGrain.INSTRUMENT,
    ProductType.DOMESTIC_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.DOMESTIC_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.PUBLIC_FUND: ResultGrain.FUND_ITEM,
}
