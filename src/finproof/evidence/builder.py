"""Bounded evidence assembly."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from hashlib import sha256

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
from finproof.domain.query_plan import (
    FilterOperator,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    SortDirection,
    TopKScope,
)
from finproof.quality import MetricValue, PolicyExecutionResult, RankPolicyResult
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
        evidence_ids = (
            *(item.evidence_id for item in direct),
            *(item.evidence_id for item in derived),
        )[:100]
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
        native_grains = {
            row.raw.product_type: row.raw.native_result_grain for row in policy_result.included_rows
        }
        summaries = [
            _summary(
                summary_id="summary:count",
                kind=EvidenceSummaryKind.COUNT,
                included_count=len(policy_result.included_rows),
                excluded_count=excluded,
                value=len(policy_result.included_rows) + policy_result.excluded_state_count,
                evidence_ids=evidence_ids,
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
                    evidence_ids=evidence_ids,
                    policy_versions=policy_versions,
                    plan_hash=plan_hash,
                    version_hash=version_hash,
                    artifact_hash=artifact_hash,
                )
            )
        for index, partition in enumerate(policy_result.partitions):
            product_types = tuple(dict.fromkeys(value.product_type for value in partition.values))
            summaries.append(
                _summary(
                    summary_id=f"summary:partition:{index}",
                    kind=EvidenceSummaryKind.PARTITION,
                    included_count=len(partition.selected_values),
                    excluded_count=len(partition.values) - len(partition.selected_values),
                    evidence_ids=evidence_ids,
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
            field_id = original.sort[0].field
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
                summaries.append(
                    _summary(
                        summary_id=f"summary:tie:{index}",
                        kind=EvidenceSummaryKind.TIE,
                        included_count=rank.tie_count,
                        excluded_count=0,
                        evidence_ids=evidence_ids,
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
        for index, aggregate in enumerate(policy_result.aggregates):
            summaries.append(
                _summary(
                    summary_id=f"summary:aggregate:{index}",
                    kind=EvidenceSummaryKind.AGGREGATE,
                    included_count=aggregate.included_count,
                    excluded_count=aggregate.excluded_count,
                    evidence_ids=evidence_ids,
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
            if any(
                item.field == "credit_rating"
                and item.operator in {FilterOperator.GTE, FilterOperator.LTE}
                for item in original.filters
            )
            else ()
        )
        limitations = tuple(
            dict.fromkeys(
                (
                    "2026-07-11 제공 스냅샷 기준",
                    *dual_lens_labels,
                    *rating_limitations,
                    *(
                        (
                            "동률로 top-k 경계를 넘는 결과는 공동순위를 유지하고 "
                            "요청한 표시 개수까지만 제시했습니다.",
                        )
                        if len(ranks) < len(policy_result.ranks)
                        else ()
                    ),
                    *(("통화별로 결과를 분리했습니다.",) if len(currencies - {None}) > 1 else ()),
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
    sort = plan.sort[0]
    grouped: dict[tuple[ProductType | None, str | None], list[MetricValue]] = {}
    for value in policy_result.metric_policy.recorded_values:
        if (
            value in policy_result.metric_policy.comparison_valid_values
            or value.value is None
            or repository._fields.projection(sort.field, value.product_type).metric_id
            != value.metric_id
        ):
            continue
        key = (
            value.product_type if plan.top_k_scope is TopKScope.PER_PRODUCT_TYPE else None,
            value.currency,
        )
        grouped.setdefault(key, []).append(value)
    return tuple(
        value
        for values in grouped.values()
        for value in sorted(
            values,
            key=lambda item: (item.value or Decimal(0), item.product_id),
            reverse=sort.direction is SortDirection.DESC,
        )[: plan.top_k]
    )


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


def _warning_text(value: str) -> str:
    return {
        "recorded zero excluded from comparison": (
            "기록된 0값은 비교 가능 기준에서 제외했으며, 실제 무보수인지는 검증되지 않았습니다."
        ),
        "metric values excluded from comparison": "일부 지표값은 비교 가능 기준에서 제외했습니다.",
        "validated eligibility is unsupported": "검증된 매수 가능 여부는 지원하지 않습니다.",
    }.get(value, f"데이터 품질 정책 경고: {value}")
