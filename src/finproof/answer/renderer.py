"""Deterministic Korean answer renderer."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import cast

from finproof.answer.templates import wording_text
from finproof.domain.answers import (
    AnswerClaim,
    AnswerDraft,
    AnswerRequest,
    ClaimKind,
    ValueSign,
)
from finproof.domain.evidence import (
    DerivedEvidence,
    DirectEvidence,
    EvidenceBundle,
    EvidenceSummary,
    EvidenceSummaryKind,
)
from finproof.domain.query_plan import AggregationFunction, Intent, ProductType, QueryPlan
from finproof.registry.loader import RegistryBundle


class AnswerRenderer:
    def __init__(self) -> None:
        wording = RegistryBundle.from_package().answers.document["wording"]
        if not isinstance(wording, Mapping):
            raise TypeError("answer wording registry differs")
        self._wording = wording

    def render(
        self,
        *,
        request: AnswerRequest,
        plan: QueryPlan,
        evidence: EvidenceBundle,
    ) -> AnswerDraft:
        if (
            type(request) is not AnswerRequest
            or type(plan) is not QueryPlan
            or type(evidence) is not EvidenceBundle
        ):
            raise TypeError("answer rendering inputs differ")
        if plan.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}:
            text = (
                plan.clarification_reason
                if plan.intent is Intent.CLARIFY
                else f"{wording_text(self._wording, 'unsupported')} {plan.clarification_reason}"
            )
            return AnswerDraft(
                text=text,
                claims=(
                    AnswerClaim(
                        claim_id=f"claim:{plan.intent.value}",
                        kind=ClaimKind.LIMITATION,
                        text=text,
                        value=text,
                    ),
                ),
            )
        snapshot = wording_text(self._wording, "snapshot_assumption")
        lines = [snapshot]
        claims = [
            AnswerClaim(
                claim_id="claim:snapshot",
                kind=ClaimKind.LIMITATION,
                text=snapshot,
                value=snapshot,
            )
        ]
        recommendation_request = "추천" in request.question
        if recommendation_request:
            lines.append(wording_text(self._wording, "matched_candidates"))
        count_summary = next(
            (
                summary
                for summary in evidence.summaries
                if summary.kind is EvidenceSummaryKind.COUNT
            ),
            None,
        )
        source_count = (
            count_summary
            if (
                count_summary is not None
                and type(count_summary.value) is int
                and (
                    any(
                        summary.kind is EvidenceSummaryKind.COUNT
                        and summary.partition_key is not None
                        and summary.partition_key.startswith("state-validated:")
                        for summary in evidence.summaries
                    )
                    or (
                        plan.intent is Intent.AGGREGATE
                        and plan.aggregation is not None
                        and plan.aggregation.function is AggregationFunction.COUNT
                        and not plan.aggregation.group_by
                        and any(
                            summary.kind is EvidenceSummaryKind.AGGREGATE
                            and summary.policy_versions[0].endswith(":count")
                            and summary.value != count_summary.value
                            for summary in evidence.summaries
                        )
                    )
                )
            )
            else None
        )
        for summary in evidence.summaries:
            if summary.kind is EvidenceSummaryKind.COUNT and summary is source_count:
                count_text = f"원천 기록 기준 상품 개수: {summary.value}"
                lines.append(count_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:summary:{summary.summary_id}",
                        kind=ClaimKind.NUMERIC,
                        text=count_text,
                        value=summary.value,
                        evidence_ids=(summary.summary_id,),
                        sign=_sign(summary.value),
                    )
                )
            elif (
                summary.kind is EvidenceSummaryKind.COUNT
                and summary.partition_key is not None
                and summary.value is not None
                and summary.partition_key.startswith("state-validated:")
            ):
                count_text = f"상태 검증 후 상품 개수: {summary.value}"
                lines.append(count_text)
                claims.append(_summary_numeric_claim(summary=summary, text=count_text))
            elif (
                summary.kind is EvidenceSummaryKind.COUNT
                and summary.partition_key is not None
                and summary.value is not None
                and summary.partition_key.startswith("state-difference:")
            ):
                count_text = f"원천 기록과 상태 검증 개수 차이: {summary.value}"
                lines.append(count_text)
                claims.append(_summary_numeric_claim(summary=summary, text=count_text))
            elif (
                summary.kind is EvidenceSummaryKind.COUNT
                and summary.partition_key is not None
                and summary.value is not None
                and summary.partition_key.startswith("policy:")
            ):
                population = summary.partition_key.rsplit(":", 1)[-1]
                label = {"included": "포함", "missing": "결측", "zero": "0값"}[population]
                count_text = (
                    f"{_summary_scope(summary)} {summary.metric_id} {label} 개수: {summary.value}"
                )
                lines.append(count_text)
                claims.append(_summary_numeric_claim(summary=summary, text=count_text))
            elif (
                summary.kind is EvidenceSummaryKind.PARTITION
                and summary.value is not None
                and plan.intent is not Intent.AGGREGATE
            ):
                partition_text = f"분할 {_summary_scope(summary)}: {summary.value}건"
                lines.append(partition_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:summary:{summary.summary_id}",
                        kind=ClaimKind.NUMERIC,
                        text=partition_text,
                        product_types=summary.product_types,
                        native_result_grains=summary.native_result_grains,
                        partition_key=summary.partition_key,
                        value=summary.value,
                        evidence_ids=(summary.summary_id,),
                        sign=_sign(summary.value),
                    )
                )
            elif summary.kind is EvidenceSummaryKind.RANK and summary.value is not None:
                rank_text = (
                    f"{_summary_scope(summary)} {summary.product_id} "
                    f"{summary.metric_id}: {summary.value} ({summary.rank}위)"
                )
                lines.append(rank_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:summary:{summary.summary_id}",
                        kind=ClaimKind.NUMERIC,
                        text=rank_text,
                        product_type=summary.product_types[0],
                        product_types=summary.product_types,
                        native_result_grains=summary.native_result_grains,
                        partition_key=summary.partition_key,
                        product_id=summary.product_id,
                        field_id=summary.metric_id,
                        value=summary.value,
                        evidence_ids=(summary.summary_id,),
                        sign=_sign(summary.value),
                    )
                )
            elif summary.kind is EvidenceSummaryKind.RECORDED:
                source_prefix = (
                    "원천 기록 기준"
                    if summary.partition_key is not None
                    and summary.partition_key.startswith("source-recorded:")
                    else "제공 데이터 기록값"
                )
                displayed = (
                    summary.value
                    if summary.value is not None
                    else "제공 데이터에서 값을 확인할 수 없습니다."
                )
                recorded_text = (
                    f"{source_prefix} {_summary_scope(summary)} {summary.product_id} "
                    f"{summary.metric_id}: {displayed}"
                )
                lines.append(recorded_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:summary:{summary.summary_id}",
                        kind=(
                            ClaimKind.NUMERIC
                            if type(summary.value) in {int, Decimal}
                            else ClaimKind.TEXT
                        ),
                        text=recorded_text,
                        product_type=summary.product_types[0],
                        product_types=summary.product_types,
                        native_result_grains=summary.native_result_grains,
                        partition_key=summary.partition_key,
                        product_id=summary.product_id,
                        field_id=summary.metric_id,
                        value=summary.value,
                        evidence_ids=(summary.summary_id,),
                        sign=_sign(summary.value),
                    )
                )
            elif summary.kind is EvidenceSummaryKind.AGGREGATE and summary.value is not None:
                groups = " ".join(f"{item.field_id}={item.value}" for item in summary.group_values)
                operation = {
                    "avg": "평균",
                    "sum": "합계",
                    "min": "최솟값",
                    "max": "최댓값",
                    "count": "개수",
                }.get(summary.policy_versions[0].rsplit(":", 1)[-1], "집계")
                subject = summary.metric_id or "상품"
                prefix = (
                    "원천 기록 기준 "
                    if summary.policy_versions[0].startswith("source-recorded:")
                    else "상태 검증 후 "
                    if source_count is not None
                    and any(
                        item.kind is EvidenceSummaryKind.AGGREGATE
                        and item.policy_versions[0].startswith("source-recorded:")
                        and item.metric_id == summary.metric_id
                        for item in evidence.summaries
                    )
                    else "상태 검증 후 "
                    if source_count is not None and operation == "개수"
                    else ""
                )
                aggregate_text = (
                    f"{_summary_scope(summary)} {groups + ' ' if groups else ''}"
                    f"{prefix}{subject} "
                    f"{operation}: {summary.value} "
                    f"(포함 {summary.included_count}건, 제외 {summary.excluded_count}건)"
                )
                lines.append(aggregate_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:summary:{summary.summary_id}",
                        kind=ClaimKind.NUMERIC,
                        text=aggregate_text,
                        product_type=summary.product_types[0],
                        product_types=summary.product_types,
                        native_result_grains=summary.native_result_grains,
                        partition_key=summary.partition_key,
                        field_id=summary.metric_id,
                        value=summary.value,
                        group_values=summary.group_values,
                        evidence_ids=(summary.summary_id,),
                        sign=_sign(summary.value),
                    )
                )
            if summary.kind is EvidenceSummaryKind.TIE:
                tie_text = wording_text(self._wording, "joint_rank")
                lines.append(tie_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:summary:{summary.summary_id}",
                        kind=ClaimKind.TEXT,
                        text=tie_text,
                        evidence_ids=(summary.summary_id,),
                    )
                )
        for index, limitation in enumerate(evidence.material_policy_limitations):
            if limitation == snapshot:
                continue
            lines.append(limitation)
            claims.append(
                AnswerClaim(
                    claim_id=f"claim:limitation:{index}",
                    kind=ClaimKind.LIMITATION,
                    text=limitation,
                    value=limitation,
                )
            )
        _append_comparison_conclusions(lines=lines, claims=claims, evidence=evidence)
        source_only = {
            (summary.product_types[0], summary.product_id)
            for summary in evidence.summaries
            if summary.kind is EvidenceSummaryKind.RECORDED
            and summary.partition_key is not None
            and summary.partition_key.startswith("source-recorded:")
            and len(summary.product_types) == 1
            and summary.product_id is not None
        }
        products = (
            {}
            if plan.intent is Intent.AGGREGATE
            else dict.fromkeys(
                (
                    *(
                        (item.product_type, item.product_id)
                        for item in evidence.direct
                        if item.product_id is not None
                    ),
                    *(
                        (item.product_type, item.product_id)
                        for item in evidence.derived
                        if item.product_id is not None
                    ),
                )
            )
        )
        for product_type, product_id in products:
            if (product_type, product_id) in source_only:
                continue
            direct = tuple(
                item
                for item in evidence.direct
                if (item.product_type, item.product_id) == (product_type, product_id)
            )
            derived = tuple(
                item
                for item in evidence.derived
                if (item.product_type, item.product_id) == (product_type, product_id)
            )
            if recommendation_request:
                candidate_text = f"조건에 부합하는 후보: {product_type.value} {product_id}"
                lines.append(candidate_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:candidate:{product_type.value}:{product_id}",
                        kind=ClaimKind.CANDIDATE,
                        text=candidate_text,
                        product_type=product_type,
                        product_id=product_id,
                        evidence_ids=(
                            *(direct_item.evidence_id for direct_item in direct),
                            *(derived_item.evidence_id for derived_item in derived),
                        ),
                    )
                )
            for direct_item in direct:
                _append_value(
                    lines=lines,
                    claims=claims,
                    product_type=product_type,
                    product_id=product_id,
                    field_id=direct_item.field_id,
                    evidence_id=direct_item.evidence_id,
                    value=direct_item.value.normalized_value,
                )
            for derived_item in derived:
                if derived_item.field_id.endswith("_difference"):
                    continue
                _append_value(
                    lines=lines,
                    claims=claims,
                    product_type=product_type,
                    product_id=product_id,
                    field_id=derived_item.field_id,
                    evidence_id=derived_item.evidence_id,
                    value=derived_item.value.value,
                )
        if (
            not evidence.direct
            and not evidence.derived
            and (
                not evidence.summaries
                or (count_summary is not None and count_summary.included_count == 0)
            )
        ):
            no_result = wording_text(self._wording, "no_result")
            lines.append(no_result)
            if count_summary is not None:
                claims.append(
                    AnswerClaim(
                        claim_id="claim:no-result",
                        kind=ClaimKind.TEXT,
                        text=no_result,
                        evidence_ids=(count_summary.summary_id,),
                    )
                )
        return AnswerDraft(
            text="\n".join(lines),
            claims=tuple(claims),
        )


def _append_comparison_conclusions(
    *,
    lines: list[str],
    claims: list[AnswerClaim],
    evidence: EvidenceBundle,
) -> None:
    all_evidence: tuple[DirectEvidence[object] | DerivedEvidence[object], ...] = (
        *evidence.direct,
        *evidence.derived,
    )
    for difference in (item for item in evidence.derived if item.field_id.endswith("_difference")):
        raw_value = difference.value.value
        if difference.product_id is None or type(raw_value) not in {int, Decimal}:
            continue
        value = cast(Decimal | int, raw_value)
        metric_id = (
            "remaining_days_at_as_of"
            if difference.field_id == "remaining_days_difference"
            else difference.field_id.removesuffix("_difference")
        )
        compared_ids = tuple(
            dict.fromkeys(
                item.product_id
                for item in all_evidence
                if item.field_id == metric_id
                and item.product_type is difference.product_type
                and item.product_id is not None
            )
        )
        if len(compared_ids) != 2 or difference.product_id not in compared_ids:
            continue
        other_id = next(item for item in compared_ids if item != difference.product_id)
        if value:
            relation = (
                "기준일 잔존일수가"
                if metric_id == "remaining_days_at_as_of"
                else "만기일이"
                if metric_id == "maturity_date"
                else f"{metric_id}가"
            )
            unit = "일 " if metric_id in {"remaining_days_at_as_of", "maturity_date"} else " "
            ending = (
                "깁니다"
                if metric_id == "remaining_days_at_as_of"
                else "늦습니다"
                if metric_id == "maturity_date"
                else "높습니다"
            )
            line = (
                f"- {difference.product_type.value} {difference.product_id}의 {relation} "
                f"{other_id}보다 {value}{unit}{ending}."
            )
        else:
            unit = "일" if metric_id in {"remaining_days_at_as_of", "maturity_date"} else ""
            line = (
                f"- {difference.product_type.value} {compared_ids[0]}과 {compared_ids[1]}의 "
                f"{metric_id} 차이는 0{unit}입니다."
            )
        lines.append(line)
        claims.append(
            AnswerClaim(
                claim_id=f"claim:value:{difference.evidence_id}",
                kind=ClaimKind.NUMERIC,
                text=line,
                product_type=difference.product_type,
                product_id=difference.product_id,
                field_id=difference.field_id,
                value=value,
                evidence_ids=(difference.evidence_id,),
                sign=_sign(value),
            )
        )


def _append_value(
    *,
    lines: list[str],
    claims: list[AnswerClaim],
    product_type: ProductType,
    product_id: str,
    field_id: str,
    evidence_id: str,
    value: object,
) -> None:
    scalar = _answer_scalar(value)
    if scalar is None:
        line = (
            f"- {product_type.value} {product_id} {field_id}: "
            "제공 데이터에서 값을 확인할 수 없습니다."
        )
        lines.append(line)
        claims.append(
            AnswerClaim(
                claim_id=f"claim:value:{evidence_id}",
                kind=ClaimKind.TEXT,
                text=line,
                product_type=product_type,
                product_id=product_id,
                field_id=field_id,
                value=None,
                evidence_ids=(evidence_id,),
            )
        )
        return
    line = f"- {product_type.value} {product_id} {field_id}: {scalar}"
    lines.append(line)
    claims.append(
        AnswerClaim(
            claim_id=f"claim:value:{evidence_id}",
            kind=ClaimKind.NUMERIC if type(scalar) in {int, Decimal} else ClaimKind.TEXT,
            text=line,
            product_type=product_type,
            product_id=product_id,
            field_id=field_id,
            value=scalar,
            evidence_ids=(evidence_id,),
            sign=_sign(scalar),
        )
    )


def _summary_numeric_claim(*, summary: EvidenceSummary, text: str) -> AnswerClaim:
    return AnswerClaim(
        claim_id=f"claim:summary:{summary.summary_id}",
        kind=ClaimKind.NUMERIC,
        text=text,
        product_types=summary.product_types,
        native_result_grains=summary.native_result_grains,
        partition_key=summary.partition_key,
        product_id=summary.product_id,
        field_id=summary.metric_id,
        value=summary.value,
        evidence_ids=(summary.summary_id,),
        sign=_sign(summary.value),
    )


def _summary_scope(summary: EvidenceSummary) -> str:
    product_types = ",".join(item.value for item in summary.product_types)
    grains = ",".join(item.value for item in summary.native_result_grains)
    return f"{product_types}/{grains} [{summary.partition_key}]"


def _answer_scalar(value: object) -> Decimal | int | str | date | bool | None:
    if value is None or type(value) in {Decimal, int, str, date, bool}:
        return cast(Decimal | int | str | date | bool | None, value)
    raise TypeError("answer evidence value differs")


def _sign(value: object) -> ValueSign | None:
    if type(value) not in {int, Decimal}:
        return None
    number = cast(int | Decimal, value)
    if number > 0:
        return ValueSign.POSITIVE
    if number < 0:
        return ValueSign.NEGATIVE
    return ValueSign.ZERO
