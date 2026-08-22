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
from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
from finproof.domain.query_plan import Intent, ProductType, QueryPlan
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
        for summary in evidence.summaries:
            if summary.kind is EvidenceSummaryKind.PARTITION and summary.value is not None:
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
            elif summary.kind is EvidenceSummaryKind.AGGREGATE and summary.value is not None:
                groups = " ".join(f"{item.field_id}={item.value}" for item in summary.group_values)
                operation = {
                    "avg": "평균",
                    "sum": "합계",
                    "min": "최솟값",
                    "max": "최댓값",
                    "count": "개수",
                }.get(summary.policy_versions[0].rsplit(":", 1)[-1], "집계")
                aggregate_text = (
                    f"{_summary_scope(summary)} {groups + ' ' if groups else ''}"
                    f"{summary.metric_id or '상품'} "
                    f"{operation}: {summary.value}"
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
        products = dict.fromkeys(
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
        for product_type, product_id in products:
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
                _append_value(
                    lines=lines,
                    claims=claims,
                    product_type=product_type,
                    product_id=product_id,
                    field_id=derived_item.field_id,
                    evidence_id=derived_item.evidence_id,
                    value=derived_item.value.value,
                )
        count_summary = next(
            (
                summary
                for summary in evidence.summaries
                if summary.kind is EvidenceSummaryKind.COUNT
            ),
            None,
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
