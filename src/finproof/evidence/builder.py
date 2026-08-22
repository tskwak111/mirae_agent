"""Bounded evidence assembly."""

from datetime import date
from decimal import Decimal
from hashlib import sha256

from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.evidence import (
    EvidenceBundle,
    EvidenceSummary,
    EvidenceSummaryKind,
    EvidenceSummaryValue,
)
from finproof.domain.execution import ValidatedQueryPlan
from finproof.domain.query_plan import ProductType, ResultGrain
from finproof.quality import PolicyExecutionResult
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
        selected: dict[tuple[ProductType, str], None] = {}
        for row in policy_result.selected_rows:
            selected[(row.raw.product_type, row.raw.product_id)] = None
        for partition in policy_result.partitions:
            for value in partition.selected_values:
                selected[(value.product_type, value.product_id)] = None
        for rank in policy_result.ranks:
            selected[(rank.value.product_type, rank.value.product_id)] = None

        original = plan.plan
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
                )
            )
        for index, rank in enumerate(policy_result.ranks):
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
        limitations = tuple(
            dict.fromkeys(
                (
                    "2026-07-11 제공 스냅샷 기준",
                    *policy_result.dual_lens_labels,
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


def _warning_text(value: str) -> str:
    return {
        "recorded zero excluded from comparison": "기록된 0값은 비교 가능 기준에서 제외했습니다.",
        "metric values excluded from comparison": "일부 지표값은 비교 가능 기준에서 제외했습니다.",
        "validated eligibility is unsupported": "검증된 매수 가능 여부는 지원하지 않습니다.",
    }.get(value, f"데이터 품질 정책 경고: {value}")
