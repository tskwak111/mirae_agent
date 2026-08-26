"""Ordered deterministic policy composition."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from finproof.domain.execution import ExecutionBundle
from finproof.domain.query_plan import (
    AggregationFunction,
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    ResultGrain,
    SortDirection,
    SortSpec,
    TopKScope,
)
from finproof.quality.comparability import CompatibilityPartition, CompatibilityPartitioner
from finproof.quality.dual_lens import DualLensPolicy
from finproof.quality.metric_policy import (
    MetricPolicy,
    MetricPolicyResult,
    MetricValue,
    Operation,
)
from finproof.quality.state import PolicyProduct, StateEvaluation, StatePolicy
from finproof.quality.ties import TiePolicy
from finproof.query.fields import FieldRegistry
from finproof.registry.loader import RegistryBundle
from finproof.registry.rating import RatingRegistry
from finproof.storage import RawExecutionResult, RawFieldValue, RawProductRow


class PolicyRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    raw: RawProductRow
    state: StateEvaluation


class AggregatePolicyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    product_type: ProductType
    native_result_grain: ResultGrain
    partition_key: str
    field_id: str | None
    group_values: tuple[RawFieldValue, ...]
    value: Decimal | int | None
    included_count: int
    excluded_count: int
    policy_id: str
    evidence_requirements: tuple[str, ...]


class RankPolicyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    value: MetricValue
    native_result_grain: ResultGrain
    partition_key: str
    field_id: str
    rank: int
    tie_count: int
    policy_id: str
    evidence_requirements: tuple[str, ...]


class PolicyExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    included_rows: tuple[PolicyRow, ...]
    excluded_filter_count: int
    excluded_state_count: int
    excluded_metric_count: int
    metric_policy: MetricPolicyResult
    dual_lens_labels: tuple[str, ...]
    selected_rows: tuple[PolicyRow, ...]
    partitions: tuple[CompatibilityPartition, ...]
    aggregates: tuple[AggregatePolicyResult, ...]
    ranks: tuple[RankPolicyResult, ...]
    warnings: tuple[str, ...]


class PolicyEngine:
    def __init__(self) -> None:
        self._state = StatePolicy()
        registries = RegistryBundle.from_package()
        self._fields = FieldRegistry.from_bundle(registries)
        self._ratings = registries.ratings
        self._partitioner = CompatibilityPartitioner()

    def apply(
        self,
        raw: RawExecutionResult,
        *,
        bundle: ExecutionBundle,
    ) -> PolicyExecutionResult:
        if type(raw) is not RawExecutionResult or type(bundle) is not ExecutionBundle:
            raise TypeError("policy pipeline inputs differ")
        included: list[PolicyRow] = []
        excluded_filter = 0
        excluded_state = 0
        warnings: list[str] = []
        metric_values: list[MetricValue] = []
        for segment, raw_segment in zip(bundle.segments, raw.segments, strict=True):
            if segment.product_type is not raw_segment.product_type:
                raise ValueError("policy segment identity differs")
            for row in raw_segment.rows:
                if not all(
                    _matches(row, clause, ratings=self._ratings) for clause in segment.filters
                ):
                    excluded_filter += 1
                    continue
                product = PolicyProduct(
                    product_type=row.product_type,
                    product_id=row.product_id,
                    values=row.values,
                )
                if row.product_type in {
                    ProductType.OVERSEAS_ETF,
                    ProductType.OVERSEAS_ETN,
                    ProductType.PUBLIC_FUND,
                }:
                    state = StateEvaluation(
                        product_id=row.product_id,
                        eligible=True,
                        state_ids=("source_state_only",),
                        warnings=("validated eligibility is unsupported",),
                    )
                else:
                    state = self._state.evaluate(
                        product,
                        as_of=bundle.validated_plan.plan.as_of_date,
                    )
                warnings.extend(state.warnings)
                if not state.eligible:
                    excluded_state += 1
                    continue
                included.append(PolicyRow(raw=row, state=state))
                by_field = {item.field_id: item for item in row.values}
                currency = by_field.get("currency")
                metric_field_ids = dict.fromkeys(
                    (
                        *segment.metrics,
                        *(
                            (segment.aggregation.field,)
                            if segment.aggregation is not None
                            and segment.aggregation.field is not None
                            else ()
                        ),
                    )
                )
                for field_id in metric_field_ids:
                    projection = self._fields.projection(field_id, row.product_type)
                    item = by_field.get(field_id)
                    if item is None:
                        raise ValueError("policy metric projection differs")
                    if projection.metric_id is None:
                        continue
                    metric_value: Decimal | str | None
                    sort_value: Decimal | int | str | None = None
                    if (
                        projection.value_type == "ordinal_rating"
                        and bundle.validated_plan.plan.intent is Intent.SCREEN_RANK
                    ):
                        rating = (
                            self._ratings.resolve(item.value) if type(item.value) is str else None
                        )
                        metric_value = rating.normalized_value if rating is not None else None
                        sort_value = (
                            -rating.ordinal
                            if rating is not None and rating.ordinal is not None
                            else None
                        )
                    else:
                        metric_value = (
                            item.value
                            if type(item.value) is Decimal
                            else Decimal(item.value)
                            if type(item.value) is int
                            else None
                        )
                    metric_values.append(
                        MetricValue(
                            metric_id=projection.metric_id,
                            product_type=row.product_type,
                            product_id=row.product_id,
                            value=metric_value,
                            quality_status=item.quality_status,
                            currency=currency.value
                            if currency is not None and type(currency.value) is str
                            else None,
                            sort_value=sort_value,
                        )
                    )
        requested_period = next(
            (
                self._partitioner._metrics[value.metric_id].period
                for value in metric_values
                if self._partitioner._metrics[value.metric_id].comparability_group
                == "historical_total_return"
            ),
            None,
        )
        operation = (
            Operation.RANK
            if bundle.validated_plan.plan.intent is Intent.SCREEN_RANK
            else Operation.AGGREGATE
            if bundle.validated_plan.plan.intent is Intent.AGGREGATE
            else Operation.DISPLAY
        )
        metric_policy = MetricPolicy().apply(operation, tuple(metric_values))
        policy_values = (
            metric_policy.comparison_valid_values
            if operation in {Operation.RANK, Operation.AGGREGATE}
            else metric_policy.recorded_values
        )
        if bundle.top_k_scope is TopKScope.PER_PRODUCT_TYPE:
            partitions = tuple(
                partition
                for segment in bundle.segments
                for partition in self._partitioner.partition(
                    tuple(
                        value
                        for value in policy_values
                        if value.product_type is segment.product_type
                    ),
                    requested_period=requested_period,
                )
            )
        else:
            partitions = (
                self._partitioner.partition(policy_values, requested_period=requested_period)
                if policy_values
                else ()
            )
        if (
            operation in {Operation.RANK, Operation.AGGREGATE}
            and bundle.top_k_scope is TopKScope.GLOBAL
            and len(partitions) > 1
        ):
            raise ValueError("global scope requires one final partition")
        descending = bool(
            bundle.validated_plan.plan.sort
            and bundle.validated_plan.plan.sort[0].direction is SortDirection.DESC
        )
        selected_partitions: list[CompatibilityPartition] = []
        rank_results: list[RankPolicyResult] = []
        for partition in partitions:
            if bundle.validated_plan.plan.intent is Intent.SCREEN_RANK:
                ranked = TiePolicy().rank(partition.values, descending=descending)
                selected = tuple(
                    item for item in ranked if item.rank <= bundle.validated_plan.plan.top_k
                )
                selected_values = tuple(item.value for item in selected)
                rank_results.extend(
                    RankPolicyResult(
                        value=item.value,
                        native_result_grain=next(
                            segment.native_result_grain
                            for segment in bundle.segments
                            if segment.product_type is item.value.product_type
                        ),
                        partition_key=partition.compatibility_key,
                        field_id=next(
                            field_id
                            for segment in bundle.segments
                            if segment.product_type is item.value.product_type
                            for field_id in segment.metrics
                            if self._fields.projection(field_id, segment.product_type).metric_id
                            == item.value.metric_id
                        ),
                        rank=item.rank,
                        tie_count=item.tie_count,
                        policy_id=f"{item.value.metric_id}:rank",
                        evidence_requirements=("value", "quality", "tie"),
                    )
                    for item in selected
                )
            else:
                selected_values = tuple(
                    sorted(
                        partition.values,
                        key=lambda value: (value.value, value.product_id),
                        reverse=descending,
                    )[: bundle.validated_plan.plan.top_k]
                )
            selected_partitions.append(
                partition.model_copy(update={"selected_values": selected_values})
            )
        field_segments = tuple(
            segment
            for segment in bundle.segments
            if not any(
                self._fields.projection(field_id, segment.product_type).metric_id is not None
                for field_id in segment.metrics
            )
            or (
                operation is Operation.DISPLAY
                and any(
                    self._fields.projection(field_id, segment.product_type).value_type
                    not in {"decimal", "integer"}
                    for field_id in segment.metrics
                )
                and not any(
                    value.product_type is segment.product_type
                    for partition in selected_partitions
                    for value in partition.values
                )
            )
        )
        if bundle.top_k_scope is TopKScope.GLOBAL:
            field_rows = tuple(
                row
                for row in included
                if any(row.raw.product_type is segment.product_type for segment in field_segments)
            )
            selected_rows = _sort_rows(field_rows, bundle.validated_plan.plan.sort)[
                : bundle.validated_plan.plan.top_k
            ]
        else:
            selected_rows = tuple(
                row
                for segment in field_segments
                for row in _sort_rows(
                    tuple(
                        item for item in included if item.raw.product_type is segment.product_type
                    ),
                    segment.sort,
                )[: segment.top_k]
            )
        aggregates: list[AggregatePolicyResult] = []
        for segment in bundle.segments:
            aggregation = segment.aggregation
            if aggregation is None:
                continue
            segment_rows = tuple(
                row for row in included if row.raw.product_type is segment.product_type
            )
            applicable_partitions = (
                tuple(
                    partition
                    for partition in selected_partitions
                    if any(
                        value.product_type is segment.product_type
                        and value.metric_id
                        == self._fields.projection(
                            aggregation.field, segment.product_type
                        ).metric_id
                        for value in partition.values
                    )
                )
                if aggregation.field is not None
                else ()
            )
            partition_rows = (
                tuple(
                    (
                        partition.compatibility_key,
                        tuple(
                            row
                            for row in segment_rows
                            if _row_matches_partition(row, partition.currency)
                        ),
                    )
                    for partition in applicable_partitions
                )
                if applicable_partitions
                else (
                    (
                        f"count:{segment.native_result_grain.value}:{segment.product_type.value}",
                        segment_rows,
                    ),
                )
            )
            for partition_key, rows in partition_rows:
                segment_aggregates: list[AggregatePolicyResult] = []
                grouped: dict[
                    tuple[object, ...], tuple[tuple[RawFieldValue, ...], list[PolicyRow]]
                ] = {}
                for policy_row in rows:
                    by_field = {item.field_id: item for item in policy_row.raw.values}
                    group_values = tuple(by_field[field] for field in aggregation.group_by)
                    key = tuple(item.value for item in group_values)
                    grouped.setdefault(key, (group_values, []))[1].append(policy_row)
                if not grouped and not aggregation.group_by:
                    grouped[()] = ((), [])
                for _, (group_values, group_rows) in sorted(
                    grouped.items(), key=lambda item: tuple(str(value) for value in item[0])
                ):
                    if aggregation.field is None:
                        value: Decimal | int | None = len(group_rows)
                        included_count = len(group_rows)
                        metric_excluded = 0
                        policy_id = f"count:{aggregation.function.value}"
                    else:
                        projection = self._fields.projection(
                            aggregation.field, segment.product_type
                        )
                        product_ids = {row.raw.product_id for row in group_rows}
                        numbers = tuple(
                            item.value
                            for item in policy_values
                            if item.metric_id == projection.metric_id
                            and item.product_type is segment.product_type
                            and item.product_id in product_ids
                            and type(item.value) is Decimal
                        )
                        value = _aggregate(aggregation.function, numbers)
                        included_count = len(numbers)
                        metric_excluded = len(group_rows) - included_count
                        policy_id = f"{projection.metric_id}:{aggregation.function.value}"
                    segment_aggregates.append(
                        AggregatePolicyResult(
                            product_type=segment.product_type,
                            native_result_grain=segment.native_result_grain,
                            partition_key=partition_key,
                            field_id=aggregation.field,
                            group_values=group_values,
                            value=value,
                            included_count=included_count,
                            excluded_count=(
                                metric_excluded
                                + (
                                    excluded_filter + excluded_state
                                    if not aggregation.group_by
                                    else 0
                                )
                            ),
                            policy_id=policy_id,
                            evidence_requirements=("value", "quality", "count"),
                        )
                    )
                if segment.sort and segment.sort[0].field == aggregation.field:
                    valued = [item for item in segment_aggregates if item.value is not None]
                    valued.sort(
                        key=lambda item: cast(Decimal | int, item.value),
                        reverse=segment.sort[0].direction is SortDirection.DESC,
                    )
                    segment_aggregates = valued + [
                        item for item in segment_aggregates if item.value is None
                    ]
                aggregates.extend(segment_aggregates[: segment.top_k])
        return PolicyExecutionResult(
            included_rows=tuple(included),
            excluded_filter_count=excluded_filter,
            excluded_state_count=excluded_state,
            excluded_metric_count=len(metric_values) - len(policy_values),
            metric_policy=metric_policy,
            dual_lens_labels=DualLensPolicy().labels(metric_policy),
            selected_rows=selected_rows,
            partitions=tuple(selected_partitions),
            aggregates=tuple(aggregates),
            ranks=tuple(rank_results),
            warnings=tuple(dict.fromkeys((*warnings, *metric_policy.warnings))),
        )


def _aggregate(function: AggregationFunction, values: tuple[Decimal, ...]) -> Decimal | int | None:
    if not values:
        return None
    if function is AggregationFunction.MIN:
        return min(values)
    if function is AggregationFunction.MAX:
        return max(values)
    if function is AggregationFunction.SUM:
        return sum(values, Decimal(0))
    if function is AggregationFunction.AVG:
        return sum(values, Decimal(0)) / len(values)
    if function is AggregationFunction.COUNT:
        return len(values)
    raise ValueError("aggregation function differs")


def _row_matches_partition(row: PolicyRow, currency: str | None) -> bool:
    row_currency = next(
        (item.value for item in row.raw.values if item.field_id == "currency"), None
    )
    return currency is None or row_currency == currency


def _matches(
    row: RawProductRow,
    clause: FilterClause,
    *,
    ratings: RatingRegistry,
) -> bool:
    value = next((item.value for item in row.values if item.field_id == clause.field), None)
    target: object = clause.value
    if clause.operator is FilterOperator.IS_MISSING:
        return value is None
    if clause.operator is FilterOperator.IS_NOT_MISSING:
        return value is not None
    if value is None:
        return False
    if type(value) is date:
        if type(target) is str:
            target = date.fromisoformat(target)
        elif type(target) is tuple:
            target = tuple(
                date.fromisoformat(item) if type(item) is str else item for item in target
            )
    if clause.field == "credit_rating" and clause.operator in {
        FilterOperator.GTE,
        FilterOperator.LTE,
    }:
        if type(value) is not str or type(target) is not str:
            return False
        value_ordinal = ratings.resolve(value).ordinal
        target_ordinal = ratings.resolve(target).ordinal
        if value_ordinal is None or target_ordinal is None:
            return False
        return (
            value_ordinal <= target_ordinal
            if clause.operator is FilterOperator.GTE
            else value_ordinal >= target_ordinal
        )
    if clause.operator is FilterOperator.EQ:
        return value == target
    if clause.operator is FilterOperator.NE:
        return value != target
    if clause.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
        assert isinstance(target, tuple)
        contained = value in target
        return contained if clause.operator is FilterOperator.IN else not contained
    if clause.operator is FilterOperator.BETWEEN:
        assert isinstance(target, tuple)
        return bool(target[0] <= value <= target[1])
    if clause.operator is FilterOperator.CONTAINS:
        return type(value) is str and type(target) is str and target in value
    if clause.operator is FilterOperator.STARTS_WITH:
        return type(value) is str and type(target) is str and value.startswith(target)
    operations = {
        FilterOperator.GT: lambda left, right: left > right,
        FilterOperator.GTE: lambda left, right: left >= right,
        FilterOperator.LT: lambda left, right: left < right,
        FilterOperator.LTE: lambda left, right: left <= right,
    }
    return bool(operations[clause.operator](cast(Any, value), cast(Any, target)))


def _sort_rows(rows: tuple[PolicyRow, ...], sort: tuple[SortSpec, ...]) -> tuple[PolicyRow, ...]:
    ordered = sorted(rows, key=lambda row: row.raw.product_id)
    for item in reversed(sort):
        valued = [
            row
            for row in ordered
            if next(value.value for value in row.raw.values if value.field_id == item.field)
            is not None
        ]
        valued.sort(
            key=lambda row: cast(
                Any,
                next(value.value for value in row.raw.values if value.field_id == item.field),
            ),
            reverse=item.direction is SortDirection.DESC,
        )
        ordered = valued + [row for row in ordered if row not in valued]
    return tuple(ordered)
