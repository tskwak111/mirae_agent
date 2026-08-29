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
        self._registries = RegistryBundle.from_package()
        wording = self._registries.answers.document["wording"]
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
        ranked_values = {
            (summary.product_types[0], summary.product_id, summary.metric_id)
            for summary in evidence.summaries
            if summary.kind is EvidenceSummaryKind.RANK
            and len(summary.product_types) == 1
            and summary.product_id is not None
            and summary.metric_id is not None
        }
        ranked_partitions = {
            summary.partition_key
            for summary in evidence.summaries
            if summary.kind is EvidenceSummaryKind.RANK and summary.partition_key is not None
        }
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
                count_text = (
                    f"{_summary_scope(summary, self._registries)} "
                    f"상태 검증 후 상품 개수: {summary.value}"
                )
                lines.append(count_text)
                claims.append(_summary_numeric_claim(summary=summary, text=count_text))
            elif (
                summary.kind is EvidenceSummaryKind.COUNT
                and summary.partition_key is not None
                and summary.value is not None
                and summary.partition_key.startswith("state-difference:")
            ):
                count_text = (
                    f"{_summary_scope(summary, self._registries)} "
                    f"원천 기록과 상태 검증 개수 차이: {summary.value}"
                )
                lines.append(count_text)
                claims.append(_summary_numeric_claim(summary=summary, text=count_text))
            elif (
                summary.kind is EvidenceSummaryKind.COUNT
                and summary.partition_key is not None
                and summary.value is not None
                and summary.partition_key.startswith("policy:")
                and plan.intent is not Intent.SCREEN_RANK
            ):
                population = summary.partition_key.rsplit(":", 1)[-1]
                label = {"included": "포함", "missing": "결측", "zero": "0값"}[population]
                product_type = summary.product_types[0]
                metric_label, _ = _field_display(summary.metric_id, product_type, self._registries)
                count_text = (
                    f"{_summary_scope(summary, self._registries)} {metric_label} "
                    f"{label} 개수: {summary.value}"
                )
                lines.append(count_text)
                claims.append(_summary_numeric_claim(summary=summary, text=count_text))
            elif (
                summary.kind is EvidenceSummaryKind.PARTITION
                and summary.value is not None
                and plan.intent is not Intent.AGGREGATE
                and (summary.value == 0 or summary.partition_key not in ranked_partitions)
            ):
                partition_text = (
                    f"{_summary_scope(summary, self._registries)} 비교 가능 결과: {summary.value}건"
                )
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
                rank_text = _rank_text(summary, evidence, self._registries)
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
                        evidence_ids=(
                            summary.summary_id,
                            *_holding_owner_evidence_ids(
                                evidence,
                                summary.product_types[0],
                                summary.product_id,
                            ),
                        ),
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
                product_type = summary.product_types[0]
                field_label, unit = _field_display(
                    summary.metric_id, product_type, self._registries
                )
                displayed = (
                    _display_value(
                        summary.value,
                        unit=unit,
                        currency=_partition_currency(summary.partition_key),
                    )
                    if summary.value is not None
                    else "제공 데이터에서 값을 확인할 수 없습니다."
                )
                product = _product_display_name(evidence, product_type, summary.product_id)
                recorded_text = (
                    f"{source_prefix}: {_summary_scope(summary, self._registries)} {product}"
                    f" — {field_label} {displayed}"
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
                product_type = summary.product_types[0]
                groups = " ".join(
                    f"{_field_display(item.field_id, product_type, self._registries)[0]}="
                    f"{_display_value(item.value, unit=None, currency=None)}"
                    for item in summary.group_values
                )
                operation = {
                    "avg": "평균",
                    "sum": "합계",
                    "min": "최솟값",
                    "max": "최댓값",
                    "count": "개수",
                }.get(summary.policy_versions[0].rsplit(":", 1)[-1], "집계")
                subject, unit = _field_display(summary.metric_id, product_type, self._registries)
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
                displayed_value = _display_value(
                    summary.value,
                    unit=unit,
                    currency=_partition_currency(summary.partition_key),
                )
                aggregate_text = (
                    f"{_summary_scope(summary, self._registries)} "
                    f"{groups + ' ' if groups else ''}"
                    f"{prefix}{subject} "
                    f"{operation}: "
                    f"{displayed_value} "
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
            displayed_limitation = _display_limitation(limitation)
            lines.append(displayed_limitation)
            claims.append(
                AnswerClaim(
                    claim_id=f"claim:limitation:{index}",
                    kind=ClaimKind.LIMITATION,
                    text=displayed_limitation,
                    value=limitation,
                    evidence_ids=_limitation_evidence_ids(limitation, evidence),
                )
            )
        _append_comparison_conclusions(
            lines=lines,
            claims=claims,
            evidence=evidence,
            registries=self._registries,
        )
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
        requested_field_ids = {
            *plan.metrics,
            *(item.field for item in plan.filters),
            *(item.field for item in plan.sort),
            *(plan.aggregation.group_by if plan.aggregation is not None else ()),
            *(
                (plan.aggregation.field,)
                if plan.aggregation is not None and plan.aggregation.field is not None
                else ()
            ),
        }
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
                candidate_text = (
                    f"조건에 부합하는 후보: "
                    f"{_product_type_label(product_type, self._registries)} "
                    f"{_product_display_name(evidence, product_type, product_id)}"
                )
                lines.append(candidate_text)
                claims.append(
                    AnswerClaim(
                        claim_id=f"claim:candidate:{product_type.value}:{product_id}",
                        kind=ClaimKind.CANDIDATE,
                        text=candidate_text,
                        product_type=product_type,
                        product_id=product_id,
                        evidence_ids=tuple(
                            dict.fromkeys(
                                (
                                    *(direct_item.evidence_id for direct_item in direct),
                                    *(derived_item.evidence_id for derived_item in derived),
                                    *_holding_owner_evidence_ids(
                                        evidence,
                                        product_type,
                                        product_id,
                                    ),
                                )
                            )
                        ),
                    )
                )
            for direct_item in direct:
                if (
                    direct_item.field_id in {"product_id", "product_name"}
                    and direct_item.field_id not in requested_field_ids
                ) or (
                    product_type,
                    product_id,
                    direct_item.field_id,
                ) in ranked_values:
                    continue
                _append_value(
                    lines=lines,
                    claims=claims,
                    evidence=evidence,
                    registries=self._registries,
                    product_type=product_type,
                    product_id=product_id,
                    field_id=direct_item.field_id,
                    evidence_id=direct_item.evidence_id,
                    value=direct_item.value.normalized_value,
                )
            for derived_item in derived:
                if (
                    derived_item.field_id == "buy_yield_range"
                    or derived_item.field_id.endswith("_difference")
                    or (product_type, product_id, derived_item.field_id) in ranked_values
                ):
                    continue
                _append_value(
                    lines=lines,
                    claims=claims,
                    evidence=evidence,
                    registries=self._registries,
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
    registries: RegistryBundle,
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
            product_type_label = _product_type_label(difference.product_type, registries)
            relation = (
                "기준일 잔존일수가"
                if metric_id == "remaining_days_at_as_of"
                else "만기일이"
                if metric_id == "maturity_date"
                else f"{_field_display(metric_id, difference.product_type, registries)[0]}이"
            )
            is_days = metric_id in {"remaining_days_at_as_of", "maturity_date"}
            left = _product_display_name(evidence, difference.product_type, difference.product_id)
            right = _product_display_name(evidence, difference.product_type, other_id)
            ending = (
                "깁니다"
                if metric_id == "remaining_days_at_as_of"
                else "늦습니다"
                if metric_id == "maturity_date"
                else "높습니다"
            )
            line = (
                f"- {product_type_label} "
                f"{left}의 {relation} {right}보다 "
                f"{_display_value(value, unit='day' if is_days else None, currency=None)} {ending}."
            )
        else:
            unit = "일" if metric_id in {"remaining_days_at_as_of", "maturity_date"} else ""
            line = (
                f"- {_product_type_label(difference.product_type, registries)} "
                f"{_product_display_name(evidence, difference.product_type, compared_ids[0])}과 "
                f"{_product_display_name(evidence, difference.product_type, compared_ids[1])}의 "
                f"{_field_display(metric_id, difference.product_type, registries)[0]} "
                f"차이는 0{unit}입니다."
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
    evidence: EvidenceBundle,
    registries: RegistryBundle,
    product_type: ProductType,
    product_id: str,
    field_id: str,
    evidence_id: str,
    value: object,
) -> None:
    scalar = _answer_scalar(value)
    product = _product_display_name(evidence, product_type, product_id)
    field_label, unit = _field_display(field_id, product_type, registries)
    prefix = f"- {_product_type_label(product_type, registries)} {product} — {field_label}"
    if scalar is None:
        line = f"{prefix}: 제공 데이터에서 값을 확인할 수 없습니다."
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
    line = f"{prefix} {_display_value(scalar, unit=unit, currency=None)}"
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


def _holding_owner_evidence_ids(
    evidence: EvidenceBundle,
    product_type: ProductType,
    product_id: str | None,
) -> tuple[str, ...]:
    if product_id is None:
        return ()
    return (
        *(
            item.evidence_id
            for item in evidence.direct
            if (item.product_type, item.product_id, item.field_id)
            == (product_type, product_id, "product_id")
        ),
        *(
            item.evidence_id
            for item in evidence.holding_records
            if (item.owner_product_type, item.owner_product_id) == (product_type, product_id)
        ),
        *(
            item.evidence_id
            for item in evidence.holding_coverage
            if (item.owner_product_type, item.owner_product_id) == (product_type, product_id)
        ),
    )


def _limitation_evidence_ids(
    limitation: str,
    evidence: EvidenceBundle,
) -> tuple[str, ...]:
    if limitation.startswith("해외 ETF/ETN의 1년 수익률"):
        return tuple(
            item.summary_id
            for item in evidence.summaries
            if item.partition_key == "limitation:overseas-return-1y"
        )
    if "상위 10개 부분 자료" in limitation:
        return tuple(
            item.evidence_id
            for item in evidence.holding_coverage
            if item.coverage_state.value == "partial_top_10"
        )
    if "구성종목 자료" in limitation:
        state = (
            "unavailable"
            if "제공되지 않아" in limitation
            else "partial_top_10"
            if "부분 범위" in limitation
            else None
        )
        return tuple(
            item.summary_id
            for item in evidence.summaries
            if item.kind is EvidenceSummaryKind.COVERAGE
            and item.product_types
            and limitation.startswith(item.product_types[0].value)
            and (
                state is None
                or (item.partition_key is not None and item.partition_key.endswith(f":{state}"))
            )
        )
    return ()


def _summary_scope(summary: EvidenceSummary, registries: RegistryBundle) -> str:
    return (
        "·".join(_product_type_label(item, registries) for item in summary.product_types) or "상품"
    )


def _rank_text(
    summary: EvidenceSummary,
    evidence: EvidenceBundle,
    registries: RegistryBundle,
) -> str:
    product_type = summary.product_types[0]
    product = _product_display_name(evidence, product_type, summary.product_id)
    if summary.metric_id == "product_name" and type(summary.value) is str:
        product = _product_display_name(
            evidence,
            product_type,
            summary.product_id,
            fallback=summary.value,
        )
        return f"{summary.rank}위. {_product_type_label(product_type, registries)} {product}"
    field_label, unit = _field_display(summary.metric_id, product_type, registries)
    value = _display_value(
        summary.value,
        unit=unit,
        currency=_partition_currency(summary.partition_key),
    )
    return (
        f"{summary.rank}위. {_product_type_label(product_type, registries)} {product}"
        f" — {field_label} {value}"
    )


def _product_display_name(
    evidence: EvidenceBundle,
    product_type: ProductType,
    product_id: str | None,
    *,
    fallback: str | None = None,
) -> str:
    names = {
        item.value.normalized_value
        for item in evidence.direct
        if item.product_type is product_type
        and item.product_id == product_id
        and item.field_id == "product_name"
        and type(item.value.normalized_value) is str
        and item.value.normalized_value
    }
    name = next(iter(names)) if len(names) == 1 else fallback
    if product_id is None:
        return name or "상품"
    if name is None or name == product_id:
        return product_id
    return f"{name} ({product_id})"


def _product_type_label(product_type: ProductType, registries: RegistryBundle) -> str:
    aliases = registries.planner.product_type_aliases[product_type.value]
    return aliases[0]


def _field_display(
    field_id: str | None,
    product_type: ProductType,
    registries: RegistryBundle,
) -> tuple[str, str | None]:
    if field_id is None:
        return "상품", None
    field = registries.fields.entries.get(field_id)
    if field is not None:
        for metric_id in field.metric_ids:
            metric = registries.metrics.entries[metric_id]
            if product_type in metric.product_types:
                return metric.label_ko, metric.unit
    aliases = registries.planner.field_aliases.get(field_id)
    if aliases:
        return aliases[0], None
    return {
        "currency": "통화",
        "product_id": "상품코드",
        "product_name": "상품명",
    }.get(field_id, field_id), None


def _display_value(value: object, *, unit: str | None, currency: str | None) -> str:
    if type(value) is Decimal:
        decimal = value
        rendered = format(decimal, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        if not decimal:
            rendered = "0"
        if unit == "currency":
            rendered = f"{Decimal(rendered):,f}"
        suffix = "%" if unit == "percent" else "일" if unit == "day" else ""
        return f"{rendered}{suffix}{f' {currency}' if unit == 'currency' and currency else ''}"
    if type(value) is bool:
        return "예" if value else "아니요"
    if type(value) is int:
        return f"{value}{'일' if unit == 'day' else ''}"
    return str(value)


def _partition_currency(partition_key: str | None) -> str | None:
    if partition_key is None:
        return None
    parts = partition_key.split(":")
    return parts[1] if len(parts) > 1 and parts[1] in {"KRW", "USD"} else None


def _display_limitation(limitation: str) -> str:
    replacements = {
        "domestic_bond": "국내채권",
        "domestic_etf": "국내 ETF",
        "domestic_etn": "국내 ETN",
        "overseas_etf": "해외 ETF",
        "overseas_etn": "해외 ETN",
        "public_fund": "공모펀드",
        "bond end state is not source-verifiable": (
            "채권의 종료 상태는 원천 데이터로 검증할 수 없습니다."
        ),
    }
    displayed = limitation
    for internal, korean in replacements.items():
        displayed = displayed.replace(internal, korean)
    return displayed


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
