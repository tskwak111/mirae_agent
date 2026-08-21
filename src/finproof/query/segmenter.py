"""Native execution-segment construction."""

from finproof.domain.execution import (
    ComparisonPartition,
    ExecutionBundle,
    ExecutionSegment,
    ValidatedQueryPlan,
)
from finproof.domain.query_plan import Intent, ProductType, ResultGrain, TopKScope
from finproof.query.fields import FieldRegistry
from finproof.query.semantic_validator import ValidationContext


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
        segments = tuple(
            ExecutionSegment(
                product_type=product_type,
                native_result_grain=_NATIVE_GRAIN[product_type],
                filters=tuple(
                    clause
                    for clause in original.filters
                    if (clause.field, product_type) in self._fields.projections
                ),
                metrics=tuple(
                    metric
                    for metric in original.metrics
                    if (metric, product_type) in self._fields.projections
                ),
                sort=tuple(
                    sort
                    for sort in original.sort
                    if (sort.field, product_type) in self._fields.projections
                ),
                aggregation=original.aggregation,
                top_k=original.top_k,
            )
            for product_type in ProductType
            if product_type in original.product_types
        )
        partitions = self._comparison_partitions(segments)
        if (
            original.top_k_scope is TopKScope.GLOBAL
            and original.intent in {Intent.SCREEN_RANK, Intent.AGGREGATE}
            and len(partitions) != 1
        ):
            raise ValueError("global rank or aggregate requires one compatible partition")
        return ExecutionBundle(
            validated_plan=plan,
            top_k_scope=original.top_k_scope,
            segments=segments,
            comparison_partitions=partitions,
            response_grain=original.result_grain,
        )

    def _comparison_partitions(
        self, segments: tuple[ExecutionSegment, ...]
    ) -> tuple[ComparisonPartition, ...]:
        groups: dict[str, list[ProductType]] = {}
        for segment in segments:
            if segment.aggregation is not None and segment.aggregation.field is None:
                groups[
                    f"count:{segment.native_result_grain.value}:{segment.product_type.value}"
                ] = [segment.product_type]
            field_ids = set(segment.metrics)
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


_NATIVE_GRAIN = {
    ProductType.DOMESTIC_BOND: ResultGrain.INSTRUMENT,
    ProductType.DOMESTIC_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.DOMESTIC_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.PUBLIC_FUND: ResultGrain.FUND_ITEM,
}
