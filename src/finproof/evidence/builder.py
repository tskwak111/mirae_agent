"""Bounded evidence assembly."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any, cast

from finproof.answer.templates import wording_text
from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.evidence import (
    DerivedEvidence,
    DirectEvidence,
    EvidenceBundle,
    EvidenceSummary,
    EvidenceSummaryKind,
    EvidenceSummaryValue,
)
from finproof.domain.execution import ValidatedQueryPlan
from finproof.domain.quality import QualityStatus
from finproof.domain.query_plan import (
    AggregationFunction,
    FilterOperator,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    SortDirection,
    SortSpec,
    TopKScope,
)
from finproof.domain.values import DerivedValue
from finproof.quality import MetricValue, PolicyExecutionResult, PolicyRow, RankPolicyResult
from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository


class EvidenceBuilder:
    def build(
        self,
        *,
        plan: ValidatedQueryPlan,
        policy_result: PolicyExecutionResult,
        repository: EvidenceRepository,
    ) -> EvidenceBundle:
        if (
            type(plan) is not ValidatedQueryPlan
            or type(policy_result) is not PolicyExecutionResult
            or type(repository) is not EvidenceRepository
        ):
            raise TypeError("evidence builder inputs differ")
        original = plan.plan
        ranks = _bounded_ranks(
            policy_result.ranks,
            top_k=original.top_k,
            scope=original.top_k_scope,
        )
        recorded_values = _bounded_recorded_values(
            plan=original,
            policy_result=policy_result,
            repository=repository,
        )
        selected: dict[tuple[ProductType, str], None] = {}
        for row in policy_result.selected_rows:
            selected[(row.raw.product_type, row.raw.product_id)] = None
        if not ranks:
            for partition in policy_result.partitions:
                for value in partition.selected_values:
                    selected[(value.product_type, value.product_id)] = None
        for rank in ranks:
            selected[(rank.value.product_type, rank.value.product_id)] = None
        recorded_values = _fit_recorded_values(selected, recorded_values)
        source_only_rows = _bounded_source_rows(
            plan=original,
            policy_result=policy_result,
            limit=max(0, 50 - len(selected)),
        )
        for row in source_only_rows:
            selected[(row.raw.product_type, row.raw.product_id)] = None

        field_ids = tuple(
            dict.fromkeys(
                (
                    "product_id",
                    *original.metrics,
                    *(item.field for item in original.sort),
                    *(original.aggregation.group_by if original.aggregation else ()),
                    *(
                        (original.aggregation.field,)
                        if original.aggregation is not None
                        and original.aggregation.field is not None
                        else ()
                    ),
                    *(item.field for item in original.filters),
                )
            )
        )
        if len(field_ids) > 20:
            raise ValueError("evidence field bound exceeded")
        requests = tuple(
            EvidenceLookup(
                product_type=product_type,
                product_ids=tuple(
                    product_id
                    for selected_type, product_id in selected
                    if selected_type is product_type
                ),
                field_ids=tuple(
                    field_id
                    for field_id in field_ids
                    if (field_id, product_type) in repository._fields.projections
                ),
            )
            for product_type in ProductType
            if any(selected_type is product_type for selected_type, _ in selected)
        )
        records = repository.fetch_final_record_evidence(requests) if requests else ()
        records_by_identity = {
            (record.product_type, record.product_id): record for record in records
        }
        if len(records_by_identity) != len(records) or set(records_by_identity) != set(selected):
            raise ValueError("selected evidence record identities differ")
        records = tuple(records_by_identity[identity] for identity in selected)
        direct = tuple(item for record in records for item in record.direct)
        derived = tuple(item for record in records for item in record.derived)
        derived = (
            *derived,
            *_comparison_evidence(
                plan=original,
                items=(*direct, *derived),
                allowed_identities={
                    (row.raw.product_type, row.raw.product_id)
                    for row in policy_result.included_rows
                },
                rule_version=repository._session.versions.answer_policy_version,
            ),
        )
        facts = repository._session.versions.runtime_facts()
        plan_hash = _hash(original.model_dump(mode="json"))
        version_hash = _hash(facts)
        artifact_hash = repository._session.versions.artifact_manifest_hash
        policy_versions = tuple(
            dict.fromkeys(
                (
                    f"state:{repository._session.versions.state_rule_version}",
                    f"metric:{repository._session.versions.metric_registry_version}",
                    f"answer:{repository._session.versions.answer_policy_version}",
                )
            )
        )
        excluded = (
            policy_result.excluded_filter_count
            + policy_result.excluded_state_count
            + policy_result.excluded_metric_count
        )
        source_lens = _requests_source_lens(original, policy_result=policy_result)
        source_count = (
            (
                len(policy_result.source_rows)
                if policy_result.source_rows
                else len(policy_result.included_rows) + policy_result.excluded_state_count
            )
            if source_lens
            else None
        )
        native_grains = {
            row.raw.product_type: row.raw.native_result_grain
            for row in (*policy_result.source_rows, *policy_result.included_rows)
        }
        summaries = [
            _summary(
                summary_id="summary:count",
                kind=EvidenceSummaryKind.COUNT,
                included_count=len(policy_result.included_rows),
                excluded_count=excluded,
                value=source_count,
                evidence_ids=(),
                policy_versions=policy_versions,
                plan_hash=plan_hash,
                version_hash=version_hash,
                artifact_hash=artifact_hash,
            )
        ]
        if excluded:
            summaries.append(
                _summary(
                    summary_id="summary:exclusion",
                    kind=EvidenceSummaryKind.EXCLUSION,
                    included_count=len(policy_result.included_rows),
                    excluded_count=excluded,
                    evidence_ids=(),
                    policy_versions=policy_versions,
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                )
            )
        summaries.extend(
            _source_lens_summaries(
                plan=original,
                policy_result=policy_result,
                source_only_rows=source_only_rows,
                items=(*direct, *derived),
                policy_versions=policy_versions,
                plan_hash=plan_hash,
                version_hash=version_hash,
                artifact_hash=artifact_hash,
            )
        )
        summaries.extend(
            _metric_population_summaries(
                plan=original,
                policy_result=policy_result,
                repository=repository,
                policy_versions=policy_versions,
                plan_hash=plan_hash,
                version_hash=version_hash,
                artifact_hash=artifact_hash,
            )
        )
        if (
            original.intent is Intent.SCREEN_RANK
            and original.top_k_scope is TopKScope.PER_PRODUCT_TYPE
            and original.sort
        ):
            partitioned_types = {
                value.product_type
                for partition in policy_result.partitions
                for value in partition.values
            }
            for product_type in original.product_types:
                if product_type in partitioned_types:
                    continue
                projection = repository._fields.projection(original.sort[0].field, product_type)
                if projection.metric_id is None:
                    raise ValueError("rank partition metric differs")
                metric = repository._session.registries.metrics.entries[projection.metric_id]
                summaries.append(
                    _summary(
                        summary_id=f"summary:partition:empty:{product_type.value}",
                        kind=EvidenceSummaryKind.PARTITION,
                        included_count=0,
                        excluded_count=sum(
                            row.raw.product_type is product_type
                            for row in policy_result.included_rows
                        ),
                        evidence_ids=(),
                        policy_versions=policy_versions,
                        plan_hash=plan_hash,
                        version_hash=version_hash,
                        artifact_hash=artifact_hash,
                        product_types=(product_type,),
                        native_result_grains=(
                            ResultGrain.INSTRUMENT
                            if product_type is ProductType.DOMESTIC_BOND
                            else ResultGrain.FUND_ITEM
                            if product_type is ProductType.PUBLIC_FUND
                            else ResultGrain.LISTED_PRODUCT,
                        ),
                        partition_key=":".join(
                            str(value)
                            for value in (
                                metric.comparability_group,
                                metric.currency,
                                metric.period,
                                metric.cross_product_policy,
                            )
                        ),
                        value=0,
                    )
                )
        for index, partition in enumerate(policy_result.partitions):
            product_types = tuple(dict.fromkeys(value.product_type for value in partition.values))
            partition_evidence_ids = tuple(
                dict.fromkeys(
                    evidence_id
                    for value in partition.selected_values
                    for evidence_id in _recorded_evidence_ids(
                        items=(*direct, *derived),
                        product_type=value.product_type,
                        product_id=value.product_id,
                        field_id="product_id",
                    )
                )
            )
            summaries.append(
                _summary(
                    summary_id=f"summary:partition:{index}",
                    kind=EvidenceSummaryKind.PARTITION,
                    included_count=len(partition.selected_values),
                    excluded_count=len(partition.values) - len(partition.selected_values),
                    evidence_ids=partition_evidence_ids,
                    policy_versions=policy_versions,
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=product_types,
                    native_result_grains=tuple(native_grains[item] for item in product_types),
                    partition_key=partition.compatibility_key,
                    value=len(partition.selected_values),
                )
            )
        for index, value in enumerate(recorded_values):
            sort = _recorded_value_sort(
                plan=original,
                value=value,
                repository=repository,
            )
            if sort is None:
                raise ValueError("recorded rank metric differs")
            field_id = sort.field
            recorded_evidence_ids = _recorded_evidence_ids(
                items=(*direct, *derived),
                product_type=value.product_type,
                product_id=value.product_id,
                field_id=field_id,
            )
            summaries.append(
                _summary(
                    summary_id=f"summary:recorded:{index}",
                    kind=EvidenceSummaryKind.RECORDED,
                    included_count=1,
                    excluded_count=0,
                    evidence_ids=recorded_evidence_ids,
                    policy_versions=(f"{value.metric_id}:recorded",),
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(value.product_type,),
                    native_result_grains=(native_grains[value.product_type],),
                    partition_key=(f"recorded:{value.metric_id}:{value.currency or 'none'}"),
                    product_id=value.product_id,
                    metric_id=field_id,
                    value=value.value,
                )
            )
        tie_groups: dict[tuple[object, ...], list[RankPolicyResult]] = {}
        for rank in ranks:
            if rank.tie_count > 1:
                tie_groups.setdefault(_rank_tie_key(rank, scope=original.top_k_scope), []).append(
                    rank
                )
        emitted_ties: set[tuple[object, ...]] = set()
        for index, rank in enumerate(ranks):
            rank_evidence_ids = (
                *(
                    item.evidence_id
                    for item in direct
                    if item.product_id == rank.value.product_id and item.field_id == rank.field_id
                ),
                *(
                    item.evidence_id
                    for item in derived
                    if item.product_id == rank.value.product_id and item.field_id == rank.field_id
                ),
            )
            summaries.append(
                _summary(
                    summary_id=f"summary:rank:{index}",
                    kind=EvidenceSummaryKind.RANK,
                    included_count=1,
                    excluded_count=0,
                    evidence_ids=rank_evidence_ids,
                    policy_versions=(rank.policy_id,),
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(rank.value.product_type,),
                    native_result_grains=(rank.native_result_grain,),
                    partition_key=rank.partition_key,
                    product_id=rank.value.product_id,
                    metric_id=rank.field_id,
                    rank=rank.rank,
                    tie_count=rank.tie_count,
                    value=rank.value.value,
                )
            )
            if rank.tie_count > 1:
                tie_key = _rank_tie_key(rank, scope=original.top_k_scope)
                if tie_key in emitted_ties:
                    continue
                emitted_ties.add(tie_key)
                tie_evidence_ids = tuple(
                    dict.fromkeys(
                        evidence_id
                        for tied_rank in tie_groups[tie_key]
                        for evidence_id in _recorded_evidence_ids(
                            items=(*direct, *derived),
                            product_type=tied_rank.value.product_type,
                            product_id=tied_rank.value.product_id,
                            field_id=tied_rank.field_id,
                        )
                    )
                )
                tied_ranks = tie_groups[tie_key]
                tied_product_types = tuple(
                    dict.fromkeys(item.value.product_type for item in tied_ranks)
                )
                summaries.append(
                    _summary(
                        summary_id=f"summary:tie:{index}",
                        kind=EvidenceSummaryKind.TIE,
                        included_count=rank.tie_count,
                        excluded_count=0,
                        evidence_ids=tie_evidence_ids,
                        policy_versions=tuple(dict.fromkeys(item.policy_id for item in tied_ranks)),
                        plan_hash=plan_hash,
                        version_hash=version_hash,
                        artifact_hash=artifact_hash,
                        product_types=tied_product_types,
                        native_result_grains=tuple(
                            native_grains[item] for item in tied_product_types
                        ),
                        partition_key=rank.partition_key,
                        metric_id=rank.field_id,
                        rank=rank.rank,
                        tie_count=rank.tie_count,
                        value=_rank_tie_identity(rank.value),
                    )
                )
        nonmetric_rank_summaries, nonmetric_rank_boundary = _nonmetric_rank_summaries(
            plan=original,
            policy_result=policy_result,
            repository=repository,
            items=(*direct, *derived),
            policy_versions=policy_versions,
            plan_hash=plan_hash,
            version_hash=version_hash,
            artifact_hash=artifact_hash,
        )
        summaries.extend(nonmetric_rank_summaries)
        for index, aggregate in enumerate(policy_result.aggregates):
            aggregate_field_ids = tuple(
                dict.fromkeys(
                    (
                        *((aggregate.field_id,) if aggregate.field_id is not None else ()),
                        *(item.field_id for item in aggregate.group_values),
                    )
                )
            )
            summaries.append(
                _summary(
                    summary_id=f"summary:aggregate:{index}",
                    kind=EvidenceSummaryKind.AGGREGATE,
                    included_count=aggregate.included_count,
                    excluded_count=aggregate.excluded_count,
                    evidence_ids=_aggregate_evidence_ids(
                        items=(*direct, *derived),
                        product_type=aggregate.product_type,
                        product_ids=aggregate.product_ids,
                        field_ids=aggregate_field_ids,
                    ),
                    policy_versions=(aggregate.policy_id,),
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(aggregate.product_type,),
                    native_result_grains=(aggregate.native_result_grain,),
                    partition_key=aggregate.partition_key,
                    metric_id=aggregate.field_id,
                    value=aggregate.value,
                    group_values=tuple(
                        EvidenceSummaryValue(
                            field_id=item.field_id,
                            value=item.value,
                        )
                        for item in aggregate.group_values
                    ),
                )
            )
        if len(summaries) > 200:
            raise ValueError("evidence summary bound exceeded")
        currencies = {partition.currency for partition in policy_result.partitions}
        wording = repository._session.registries.answers.document["wording"]
        if not isinstance(wording, Mapping):
            raise TypeError("answer wording differs")
        dual_lens_labels = tuple(
            wording_text(
                wording,
                {
                    "recorded": "recorded_view_label",
                    "comparison_valid": "comparison_view_label",
                }[label],
            )
            for label in policy_result.dual_lens_labels
        )
        rating_limitations = (
            (
                "신용등급 필터는 대표 정규화 등급의 레지스트리 순서를 사용하며, 미평가 등급은 "
                "제외합니다. 복수 평가기관 원문 등급은 보존하고, 불일치는 자동 통합하지 않습니다.",
            )
            if _requires_rating_policy_disclosure(original)
            else ()
        )
        incomplete_comparison = (
            ("상태 검증을 통과한 비교값이 2개 미만이어 비교 결론을 제공하지 않습니다.",)
            if original.intent is Intent.COMPARE
            and policy_result.excluded_state_count
            and len(policy_result.included_rows) < 2
            else ()
        )
        missing_rank = (
            ("결측 지표값은 순위에서 제외했습니다.",)
            if any(
                clause.operator in {FilterOperator.IS_MISSING, FilterOperator.IS_NOT_MISSING}
                for clause in original.filters
            )
            or (
                original.intent is Intent.SCREEN_RANK
                and any(
                    summary.kind is EvidenceSummaryKind.COUNT
                    and summary.partition_key is not None
                    and summary.partition_key.endswith(":missing")
                    and type(summary.value) is int
                    and summary.value > 0
                    for summary in summaries
                )
            )
            else ()
        )
        limitations = tuple(
            dict.fromkeys(
                (
                    "2026-07-11 제공 스냅샷 기준",
                    *dual_lens_labels,
                    *rating_limitations,
                    *incomplete_comparison,
                    *missing_rank,
                    *(
                        (
                            "동률로 top-k 경계를 넘는 결과는 공동순위를 유지하고 "
                            "요청한 표시 개수까지만 제시했습니다.",
                        )
                        if len(ranks) < len(policy_result.ranks) or nonmetric_rank_boundary
                        else ()
                    ),
                    *_cross_currency_limitations(currencies),
                    *_direct_recorded_zero_limitations(
                        direct,
                        existing_warnings=policy_result.warnings,
                    ),
                    *_recorded_zero_buyability_limitations(
                        plan=original,
                        policy_result=policy_result,
                    ),
                    *(_warning_text(item) for item in policy_result.warnings),
                )
            )
        )
        return EvidenceBundle(
            direct=direct,
            derived=derived,
            summaries=tuple(summaries),
            material_policy_limitations=limitations,
        )


def _requests_source_lens(plan: QueryPlan, *, policy_result: PolicyExecutionResult) -> bool:
    explicit_state_aggregate = bool(
        plan.intent is Intent.AGGREGATE
        and any(clause.field in {"buyable_quantity", "saleable"} for clause in plan.filters)
    )
    return explicit_state_aggregate or bool(
        policy_result.excluded_state_count
        and (
            plan.intent is Intent.COMPARE
            or (
                plan.intent is Intent.AGGREGATE
                and plan.aggregation is not None
                and plan.aggregation.function is AggregationFunction.COUNT
                and not plan.aggregation.group_by
            )
            or any(clause.field in {"buyable_quantity", "saleable"} for clause in plan.filters)
        )
    )


def _nonmetric_rank_summaries(
    *,
    plan: QueryPlan,
    policy_result: PolicyExecutionResult,
    repository: EvidenceRepository,
    items: tuple[DirectEvidence[object] | DerivedEvidence[object], ...],
    policy_versions: tuple[str, ...],
    plan_hash: str,
    version_hash: str,
    artifact_hash: str,
) -> tuple[tuple[EvidenceSummary, ...], bool]:
    if plan.intent is not Intent.SCREEN_RANK or not plan.sort:
        return (), False
    field_id = plan.sort[0].field
    if any(
        repository._fields.projection(field_id, product_type).metric_id is not None
        for product_type in plan.product_types
    ):
        return (), False
    descending = plan.sort[0].direction is SortDirection.DESC
    summaries: list[EvidenceSummary] = []
    emitted_ties: set[tuple[object, ...]] = set()
    boundary_truncated = False
    for index, selected_row in enumerate(policy_result.selected_rows):
        selected_value = _policy_row_value(selected_row, field_id)
        if selected_value is None:
            continue
        population = tuple(
            row
            for row in policy_result.included_rows
            if plan.top_k_scope is TopKScope.GLOBAL
            or row.raw.product_type is selected_row.raw.product_type
        )
        population_values = tuple(
            value for row in population if (value := _policy_row_value(row, field_id)) is not None
        )
        rank = 1 + sum(
            _sorts_before(value, selected_value, descending=descending)
            for value in population_values
        )
        tie_count = sum(value == selected_value for value in population_values)
        partition_key = (
            f"field-rank:{field_id}:global"
            if plan.top_k_scope is TopKScope.GLOBAL
            else f"field-rank:{field_id}:{selected_row.raw.product_type.value}"
        )
        evidence_ids = _recorded_evidence_ids(
            items=items,
            product_type=selected_row.raw.product_type,
            product_id=selected_row.raw.product_id,
            field_id=field_id,
        )
        summaries.append(
            _summary(
                summary_id=f"summary:field-rank:{index}",
                kind=EvidenceSummaryKind.RANK,
                included_count=1,
                excluded_count=0,
                evidence_ids=evidence_ids,
                policy_versions=(*policy_versions, f"field:{field_id}:rank"),
                plan_hash=plan_hash,
                version_hash=version_hash,
                artifact_hash=artifact_hash,
                product_types=(selected_row.raw.product_type,),
                native_result_grains=(selected_row.raw.native_result_grain,),
                partition_key=partition_key,
                product_id=selected_row.raw.product_id,
                metric_id=field_id,
                rank=rank,
                tie_count=tie_count,
                value=selected_value,
            )
        )
        tie_key = (partition_key, selected_value)
        if tie_count <= 1 or tie_key in emitted_ties:
            continue
        emitted_ties.add(tie_key)
        selected_tied_rows = tuple(
            row
            for row in policy_result.selected_rows
            if (
                plan.top_k_scope is TopKScope.GLOBAL
                or row.raw.product_type is selected_row.raw.product_type
            )
            and _policy_row_value(row, field_id) == selected_value
        )
        boundary_truncated |= len(selected_tied_rows) < tie_count
        tie_evidence_ids = tuple(
            dict.fromkeys(
                evidence_id
                for row in selected_tied_rows
                for evidence_id in _recorded_evidence_ids(
                    items=items,
                    product_type=row.raw.product_type,
                    product_id=row.raw.product_id,
                    field_id=field_id,
                )
            )
        )
        summaries.append(
            _summary(
                summary_id=f"summary:field-tie:{index}",
                kind=EvidenceSummaryKind.TIE,
                included_count=tie_count,
                excluded_count=0,
                evidence_ids=tie_evidence_ids,
                policy_versions=(*policy_versions, f"field:{field_id}:rank"),
                plan_hash=plan_hash,
                version_hash=version_hash,
                artifact_hash=artifact_hash,
                product_types=tuple(
                    dict.fromkeys(row.raw.product_type for row in selected_tied_rows)
                ),
                native_result_grains=tuple(
                    dict.fromkeys(row.raw.native_result_grain for row in selected_tied_rows)
                ),
                partition_key=partition_key,
                metric_id=field_id,
                rank=rank,
                tie_count=tie_count,
                value=selected_value,
            )
        )
    return tuple(summaries), boundary_truncated


def _policy_row_value(row: PolicyRow, field_id: str) -> Decimal | int | str | date | None:
    value = next((item.value for item in row.raw.values if item.field_id == field_id), None)
    return (
        cast(Decimal | int | str | date, value)
        if type(value) in {Decimal, int, str, date}
        else None
    )


def _sorts_before(
    left: Decimal | int | str | date,
    right: Decimal | int | str | date,
    *,
    descending: bool,
) -> bool:
    return bool(cast(Any, left) > right if descending else cast(Any, left) < right)


def _recorded_zero_buyability_limitations(
    *,
    plan: QueryPlan,
    policy_result: PolicyExecutionResult,
) -> tuple[str, ...]:
    requests_recorded_zero = any(
        clause.field == "buyable_quantity"
        and clause.operator is FilterOperator.EQ
        and clause.value == 0
        for clause in plan.filters
    )
    has_excluded_recorded_zero = any(
        row.raw.product_type is ProductType.DOMESTIC_BOND
        and not row.state.eligible
        and _policy_row_value(row, "buyable_quantity") == 0
        for row in policy_result.source_rows
    )
    return (
        (
            "원천에 기록된 매수 가능 수량 0인 채권은 검증된 매수 가능 결과와 순위에서 "
            "제외했으며, 이 기록은 매수 가능함의 근거가 아닙니다.",
        )
        if requests_recorded_zero and has_excluded_recorded_zero
        else ()
    )


def _source_aggregate(
    function: AggregationFunction,
    values: tuple[Decimal, ...],
) -> Decimal | int | None:
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
    raise ValueError("source aggregate function differs")


def _bounded_source_rows(
    *,
    plan: QueryPlan,
    policy_result: PolicyExecutionResult,
    limit: int | None = None,
) -> tuple[PolicyRow, ...]:
    if not _requests_source_lens(plan, policy_result=policy_result):
        return ()
    if not plan.metrics:
        return ()
    included = {(row.raw.product_type, row.raw.product_id) for row in policy_result.included_rows}
    source_only = tuple(
        row
        for row in policy_result.source_rows
        if (row.raw.product_type, row.raw.product_id) not in included
    )
    if plan.intent is Intent.AGGREGATE:
        return ()
    return source_only[: min(plan.top_k, limit if limit is not None else plan.top_k)]


def _source_lens_summaries(
    *,
    plan: QueryPlan,
    policy_result: PolicyExecutionResult,
    source_only_rows: tuple[PolicyRow, ...],
    items: tuple[DirectEvidence[object] | DerivedEvidence[object], ...],
    policy_versions: tuple[str, ...],
    plan_hash: str,
    version_hash: str,
    artifact_hash: str,
) -> tuple[EvidenceSummary, ...]:
    if not _requests_source_lens(plan, policy_result=policy_result):
        return ()
    summaries: list[EvidenceSummary] = []
    for product_type in plan.product_types:
        source_rows = tuple(
            row for row in policy_result.source_rows if row.raw.product_type is product_type
        )
        included_rows = tuple(
            row for row in policy_result.included_rows if row.raw.product_type is product_type
        )
        if not source_rows:
            continue
        grain = source_rows[0].raw.native_result_grain
        summaries.extend(
            (
                _summary(
                    summary_id=f"summary:state-validated:{product_type.value}",
                    kind=EvidenceSummaryKind.COUNT,
                    included_count=len(included_rows),
                    excluded_count=len(source_rows) - len(included_rows),
                    evidence_ids=(),
                    partition_key=f"state-validated:{product_type.value}",
                    value=len(included_rows),
                    policy_versions=policy_versions,
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(product_type,),
                    native_result_grains=(grain,),
                ),
                _summary(
                    summary_id=f"summary:state-difference:{product_type.value}",
                    kind=EvidenceSummaryKind.COUNT,
                    included_count=len(included_rows),
                    excluded_count=len(source_rows) - len(included_rows),
                    evidence_ids=(),
                    partition_key=f"state-difference:{product_type.value}",
                    value=len(source_rows) - len(included_rows),
                    policy_versions=policy_versions,
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(product_type,),
                    native_result_grains=(grain,),
                ),
            )
        )
        if plan.aggregation is not None and plan.aggregation.field is not None:
            field_id = plan.aggregation.field
            values = tuple(
                Decimal(item.value) if type(item.value) is int else item.value
                for row in source_rows
                for item in row.raw.values
                if item.field_id == field_id and type(item.value) in {Decimal, int}
            )
            numeric_values = tuple(cast(Decimal, item) for item in values)
            summaries.append(
                _summary(
                    summary_id=f"summary:source-aggregate:{product_type.value}:{field_id}",
                    kind=EvidenceSummaryKind.AGGREGATE,
                    included_count=len(numeric_values),
                    excluded_count=len(source_rows) - len(numeric_values),
                    evidence_ids=(),
                    partition_key=f"source-recorded:{product_type.value}:{field_id}",
                    metric_id=field_id,
                    value=_source_aggregate(plan.aggregation.function, numeric_values),
                    policy_versions=(
                        f"source-recorded:{field_id}:{plan.aggregation.function.value}",
                    ),
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(product_type,),
                    native_result_grains=(grain,),
                )
            )
    for index, row in enumerate(source_only_rows):
        by_field = {item.field_id: item for item in row.raw.values}
        for field_id in plan.metrics:
            item = by_field.get(field_id)
            if item is None:
                continue
            summaries.append(
                _summary(
                    summary_id=f"summary:source-recorded:{index}:{field_id}",
                    kind=EvidenceSummaryKind.RECORDED,
                    included_count=1,
                    excluded_count=0,
                    evidence_ids=_recorded_evidence_ids(
                        items=items,
                        product_type=row.raw.product_type,
                        product_id=row.raw.product_id,
                        field_id=field_id,
                    ),
                    policy_versions=("source-recorded:state:1.0.0",),
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(row.raw.product_type,),
                    native_result_grains=(row.raw.native_result_grain,),
                    partition_key=f"source-recorded:{row.raw.product_type.value}",
                    product_id=row.raw.product_id,
                    metric_id=field_id,
                    value=item.value,
                )
            )
    return tuple(summaries)


def _metric_population_summaries(
    *,
    plan: QueryPlan,
    policy_result: PolicyExecutionResult,
    repository: EvidenceRepository,
    policy_versions: tuple[str, ...],
    plan_hash: str,
    version_hash: str,
    artifact_hash: str,
) -> tuple[EvidenceSummary, ...]:
    explicit_fields = {
        clause.field
        for clause in plan.filters
        if clause.operator in {FilterOperator.IS_MISSING, FilterOperator.IS_NOT_MISSING}
    }
    valid_identities = {
        (value.product_type, value.product_id, value.metric_id)
        for value in policy_result.metric_policy.comparison_valid_values
    }
    grouped: dict[tuple[ProductType, str, str], list[MetricValue]] = {}
    for value in policy_result.metric_values:
        field_id = next(
            (
                field
                for field in (
                    *plan.metrics,
                    *(
                        (plan.aggregation.field,)
                        if plan.aggregation and plan.aggregation.field
                        else ()
                    ),
                    *(clause.field for clause in plan.filters),
                )
                if (field, value.product_type) in repository._fields.projections
                and repository._fields.projection(field, value.product_type).metric_id
                == value.metric_id
            ),
            None,
        )
        if field_id is not None:
            grouped.setdefault((value.product_type, field_id, value.metric_id), []).append(value)
    for field_id in explicit_fields:
        for product_type in plan.product_types:
            if (field_id, product_type) not in repository._fields.projections:
                continue
            metric_id = repository._fields.projection(field_id, product_type).metric_id
            if metric_id is not None:
                grouped.setdefault((product_type, field_id, metric_id), [])
    summaries: list[EvidenceSummary] = []
    for (product_type, field_id, metric_id), values in grouped.items():
        missing = sum(value.value is None for value in values)
        zero = sum(value.value == 0 for value in values)
        if not (
            field_id in explicit_fields
            or (plan.intent in {Intent.SCREEN_RANK, Intent.AGGREGATE} and (missing or zero))
        ):
            continue
        included = sum(
            (value.product_type, value.product_id, value.metric_id) in valid_identities
            for value in values
        )
        grain = next(
            (
                row.raw.native_result_grain
                for row in (*policy_result.source_rows, *policy_result.included_rows)
                if row.raw.product_type is product_type
            ),
            _native_grain(product_type),
        )
        for population, count in (
            ("included", included),
            ("missing", missing),
            ("zero", zero),
        ):
            summaries.append(
                _summary(
                    summary_id=f"summary:policy:{product_type.value}:{field_id}:{population}",
                    kind=EvidenceSummaryKind.COUNT,
                    included_count=included,
                    excluded_count=len(values) - included,
                    evidence_ids=(),
                    policy_versions=policy_versions,
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                    product_types=(product_type,),
                    native_result_grains=(grain,),
                    partition_key=f"policy:{metric_id}:{population}",
                    metric_id=field_id,
                    value=count,
                )
            )
    return tuple(summaries)


def _summary(
    *,
    summary_id: str,
    kind: EvidenceSummaryKind,
    included_count: int,
    excluded_count: int,
    evidence_ids: tuple[str, ...],
    policy_versions: tuple[str, ...],
    plan_hash: str,
    version_hash: str,
    artifact_hash: str,
    product_types: tuple[ProductType, ...] = (),
    native_result_grains: tuple[ResultGrain, ...] = (),
    partition_key: str | None = None,
    product_id: str | None = None,
    metric_id: str | None = None,
    rank: int | None = None,
    tie_count: int | None = None,
    value: Decimal | int | str | date | bool | None = None,
    group_values: tuple[EvidenceSummaryValue, ...] = (),
) -> EvidenceSummary:
    return EvidenceSummary(
        summary_id=summary_id,
        kind=kind,
        included_count=included_count,
        excluded_count=excluded_count,
        evidence_ids=evidence_ids,
        policy_versions=policy_versions,
        validated_plan_sha256=plan_hash,
        version_bundle_sha256=version_hash,
        artifact_manifest_hash=artifact_hash,
        product_types=product_types,
        native_result_grains=native_result_grains,
        partition_key=partition_key,
        product_id=product_id,
        metric_id=metric_id,
        rank=rank,
        tie_count=tie_count,
        value=value,
        group_values=group_values,
    )


def _hash(value: object) -> str:
    return sha256(canonical_json_bytes(value, terminal_newline=False)).hexdigest()


def _bounded_ranks(
    ranks: tuple[RankPolicyResult, ...],
    *,
    top_k: int,
    scope: TopKScope,
) -> tuple[RankPolicyResult, ...]:
    counts: dict[tuple[ProductType | None, str], int] = {}
    selected: list[RankPolicyResult] = []
    for rank in ranks:
        key = (
            rank.value.product_type if scope is TopKScope.PER_PRODUCT_TYPE else None,
            rank.partition_key,
        )
        count = counts.get(key, 0)
        if count < top_k:
            selected.append(rank)
            counts[key] = count + 1
    return tuple(selected)


def _bounded_recorded_values(
    *,
    plan: QueryPlan,
    policy_result: PolicyExecutionResult,
    repository: EvidenceRepository,
) -> tuple[MetricValue, ...]:
    if plan.intent is not Intent.SCREEN_RANK or not plan.sort:
        return ()
    grouped: dict[
        tuple[ProductType | None, str | None, str, SortDirection],
        list[MetricValue],
    ] = {}
    for value in policy_result.metric_policy.recorded_values:
        sort = _recorded_value_sort(plan=plan, value=value, repository=repository)
        if sort is None:
            continue
        key = (
            value.product_type if plan.top_k_scope is TopKScope.PER_PRODUCT_TYPE else None,
            value.currency,
            sort.field,
            sort.direction,
        )
        grouped.setdefault(key, []).append(value)
    valid = set(policy_result.metric_policy.comparison_valid_values)
    return tuple(
        value
        for (*_, direction), values in grouped.items()
        for value in sorted(
            values,
            key=lambda item: (_rank_tie_identity(item), item.product_id),
            reverse=direction is SortDirection.DESC,
        )[: plan.top_k]
        if value not in valid and value.value == 0
    )


def _recorded_value_sort(
    *,
    plan: QueryPlan,
    value: MetricValue,
    repository: EvidenceRepository,
) -> SortSpec | None:
    for sort in plan.sort:
        try:
            projection = repository._fields.projection(sort.field, value.product_type)
        except ValueError:
            continue
        if projection.metric_id == value.metric_id:
            return sort
    return None


def _rank_tie_identity(value: MetricValue) -> Decimal | int | str:
    identity = value.sort_value if value.sort_value is not None else value.value
    if type(identity) in {Decimal, int, str}:
        return cast(Decimal | int | str, identity)
    raise ValueError("rank identity differs")


def _rank_tie_key(
    rank: RankPolicyResult,
    *,
    scope: TopKScope,
) -> tuple[object, ...]:
    return (
        rank.value.product_type if scope is TopKScope.PER_PRODUCT_TYPE else None,
        rank.partition_key,
        rank.field_id,
        rank.rank,
        rank.tie_count,
        _rank_tie_identity(rank.value),
    )


def _native_grain(product_type: ProductType) -> ResultGrain:
    if product_type is ProductType.DOMESTIC_BOND:
        return ResultGrain.INSTRUMENT
    if product_type is ProductType.PUBLIC_FUND:
        return ResultGrain.FUND_ITEM
    return ResultGrain.LISTED_PRODUCT


def _aggregate_evidence_ids(
    *,
    items: tuple[DirectEvidence[object] | DerivedEvidence[object], ...],
    product_type: ProductType,
    product_ids: tuple[str, ...],
    field_ids: tuple[str, ...],
) -> tuple[str, ...]:
    identities = set(product_ids)
    fields = set(field_ids)
    return tuple(
        item.evidence_id
        for item in items
        if item.product_type is product_type
        and item.product_id in identities
        and item.field_id in fields
    )[:100]


def _fit_recorded_values(
    selected: dict[tuple[ProductType, str], None],
    values: tuple[MetricValue, ...],
) -> tuple[MetricValue, ...]:
    retained: list[MetricValue] = []
    for value in values:
        identity = (value.product_type, value.product_id)
        if identity in selected or len(selected) < 50:
            selected[identity] = None
            retained.append(value)
    return tuple(retained)


def _recorded_evidence_ids(
    *,
    items: tuple[DirectEvidence[object] | DerivedEvidence[object], ...],
    product_type: ProductType,
    product_id: str,
    field_id: str,
) -> tuple[str, ...]:
    return tuple(
        item.evidence_id
        for item in items
        if (item.product_type, item.product_id, item.field_id)
        == (product_type, product_id, field_id)
    )


def _remaining_days_difference(
    *,
    plan: QueryPlan,
    items: tuple[DerivedEvidence[object], ...],
    rule_version: str,
) -> tuple[DerivedEvidence[object], ...]:
    if plan.intent is not Intent.COMPARE or plan.metrics != ("remaining_days_at_as_of",):
        return ()
    values = tuple(
        item
        for item in items
        if item.field_id == "remaining_days_at_as_of"
        and item.product_id is not None
        and type(item.value.value) is int
        and item.value.quality_status is QualityStatus.VALID
    )
    if len(values) != 2 or values[0].product_type is not values[1].product_type:
        return ()
    first, second = values
    first_product_id = first.product_id
    second_product_id = second.product_id
    if first_product_id is None or second_product_id is None:
        return ()
    first_value = cast(int, first.value.value)
    second_value = cast(int, second.value.value)
    longer_product_id = second_product_id if second_value > first_value else first_product_id
    identity = "\0".join(
        (
            first.product_type.value,
            first_product_id,
            second_product_id,
            "remaining_days_difference",
        )
    )
    return (
        DerivedEvidence[object](
            evidence_id=f"comparison:{sha256(identity.encode()).hexdigest()}:remaining_days_difference",
            product_type=first.product_type,
            product_id=longer_product_id,
            field_id="remaining_days_difference",
            value=DerivedValue[object](
                value=abs(first_value - second_value),
                quality_status=QualityStatus.VALID,
                rule_id="comparison.remaining_days_difference",
                rule_version=rule_version,
                as_of_date=plan.as_of_date,
                inputs=(*first.value.inputs, *second.value.inputs),
            ),
        ),
    )


def _comparison_difference(
    first: Decimal | int | date | None,
    second: Decimal | int | date | None,
) -> Decimal | int | None:
    if first is None or second is None:
        return None
    if type(first) is date and type(second) is date:
        return abs((second - first).days)
    if type(first) is Decimal and type(second) is Decimal:
        return abs(second - first)
    if type(first) is int and type(second) is int:
        return abs(second - first)
    return None


def _comparison_evidence(
    *,
    plan: QueryPlan,
    items: tuple[DirectEvidence[object] | DerivedEvidence[object], ...],
    allowed_identities: set[tuple[ProductType, str]],
    rule_version: str,
) -> tuple[DerivedEvidence[object], ...]:
    if plan.intent is not Intent.COMPARE or len(plan.metrics) != 1:
        return ()
    metric_id = plan.metrics[0]
    values = tuple(
        item
        for item in items
        if item.field_id == metric_id
        and item.product_id is not None
        and (item.product_type, item.product_id) in allowed_identities
        and item.value.quality_status
        in {QualityStatus.VALID, QualityStatus.RECORDED_ZERO, QualityStatus.CONSTANT_METRIC}
    )
    if len(values) != 2 or values[0].product_type is not values[1].product_type:
        return ()
    first, second = values
    first_value = (
        first.value.normalized_value if isinstance(first, DirectEvidence) else first.value.value
    )
    second_value = (
        second.value.normalized_value if isinstance(second, DirectEvidence) else second.value.value
    )
    difference = _comparison_difference(
        cast(Decimal | int | date | None, first_value),
        cast(Decimal | int | date | None, second_value),
    )
    if difference is None or first.product_id is None or second.product_id is None:
        return ()
    later = bool(second_value > first_value)  # type: ignore[operator]
    selected = second if later else first
    selected_id = selected.product_id
    if selected_id is None:
        return ()
    inputs = tuple(
        locator
        for item in values
        for locator in (
            (item.value.source,) if isinstance(item, DirectEvidence) else item.value.inputs
        )
    )
    identity = "\0".join(
        (first.product_type.value, first.product_id, second.product_id, f"{metric_id}_difference")
    )
    return (
        DerivedEvidence[object](
            evidence_id=f"comparison:{sha256(identity.encode()).hexdigest()}:{metric_id}_difference",
            product_type=first.product_type,
            product_id=selected_id,
            field_id=f"{metric_id}_difference",
            value=DerivedValue[object](
                value=difference,
                quality_status=QualityStatus.VALID,
                rule_id=f"comparison.{metric_id}_difference",
                rule_version=rule_version,
                as_of_date=plan.as_of_date,
                inputs=inputs,
            ),
        ),
    )


def _requires_rating_policy_disclosure(plan: QueryPlan) -> bool:
    return bool(
        (plan.intent is Intent.SCREEN_RANK and "credit_rating" in plan.metrics)
        or any(
            clause.field == "credit_rating"
            and clause.operator
            in {
                FilterOperator.GTE,
                FilterOperator.LTE,
                FilterOperator.IS_NOT_MISSING,
            }
            for clause in plan.filters
        )
    )


def _direct_recorded_zero_limitations(
    items: tuple[DirectEvidence[object], ...],
    *,
    existing_warnings: tuple[str, ...],
) -> tuple[str, ...]:
    if "recorded zero excluded from comparison" in existing_warnings:
        return ()
    return (
        ("기록된 0값은 실제 0인지 검증되지 않았습니다.",)
        if any(
            item.value.normalized_value == 0
            and item.value.quality_status is QualityStatus.RECORDED_ZERO_UNVERIFIED
            for item in items
        )
        else ()
    )


def _cross_currency_limitations(currencies: set[str | None]) -> tuple[str, ...]:
    return (
        ("통화별로 결과를 분리했습니다. 고정 환율 기준이 없어 통합 순위는 제공하지 않습니다.",)
        if len(currencies - {None}) > 1
        else ()
    )


def _warning_text(value: str) -> str:
    return {
        "recorded zero excluded from comparison": (
            "기록된 0값은 비교 가능 기준에서 제외했으며, 실제 무보수인지는 검증되지 않았습니다."
        ),
        "metric values excluded from comparison": "일부 지표값은 비교 가능 기준에서 제외했습니다.",
        "validated eligibility is unsupported": "검증된 매수 가능 여부는 지원하지 않습니다.",
    }.get(value, f"데이터 품질 정책 경고: {value}")
