"""Focused deterministic Korean rendering contracts."""

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finproof.domain.query_plan import QueryPlan


def test_current_answer_names_2026_07_11_snapshot_not_realtime() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-current", question="현재 매수 가능한 채권은?"),
        plan=_plan(),
        evidence=EvidenceBundle(
            direct=(),
            derived=(),
            summaries=(),
            material_policy_limitations=(),
        ),
    )

    assert "2026-07-11 제공 스냅샷 기준" in draft.text
    assert "실시간" not in draft.text


def test_recommendation_request_renders_conditions_matching_candidates() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("buy_yield",),
            ),
        )
    )[0]

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-recommend", question="살 만한 채권 추천해줘"),
        plan=_plan(),
        evidence=EvidenceBundle(
            direct=record.direct,
            derived=(),
            summaries=(),
            material_policy_limitations=(),
        ),
    )

    assert "조건에 부합하는 후보: KR0000000001" in draft.text
    assert "추천" not in draft.text
    assert any(claim.kind is ClaimKind.CANDIDATE for claim in draft.claims)
    session._close()


def test_renderer_handles_joint_tie_dual_lens_currency_split_and_no_result() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import (
        EvidenceBundle,
        EvidenceSummary,
        EvidenceSummaryKind,
    )

    renderer = AnswerRenderer()
    request = AnswerRequest(question_id="q-policy", question="ETF를 비교해줘")
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(
            EvidenceSummary(
                summary_id="summary:tie",
                kind=EvidenceSummaryKind.TIE,
                included_count=2,
                excluded_count=0,
                evidence_ids=("evidence:1", "evidence:2"),
                policy_versions=("tie:1.0.0",),
                validated_plan_sha256="a" * 64,
                version_bundle_sha256="b" * 64,
                artifact_manifest_hash="c" * 64,
            ),
        ),
        material_policy_limitations=(
            "제공 데이터 기록값",
            "비교 가능 기준",
            "통화별로 결과를 분리했습니다.",
        ),
    )

    text = renderer.render(request=request, plan=_plan(), evidence=evidence).text
    no_result = renderer.render(
        request=request,
        plan=_plan(),
        evidence=EvidenceBundle(
            direct=(),
            derived=(),
            summaries=(
                EvidenceSummary(
                    summary_id="summary:count",
                    kind=EvidenceSummaryKind.COUNT,
                    included_count=0,
                    excluded_count=0,
                    evidence_ids=(),
                    policy_versions=("policy:1.0.0",),
                    validated_plan_sha256="a" * 64,
                    version_bundle_sha256="b" * 64,
                    artifact_manifest_hash="c" * 64,
                ),
            ),
            material_policy_limitations=(),
        ),
    ).text

    assert "공동순위" in text
    assert "제공 데이터 기록값" in text
    assert "비교 가능 기준" in text
    assert "통화별로 결과를 분리했습니다." in text
    assert "지정한 조건을 충족하는 상품을 찾지 못했습니다." in no_result


def _plan() -> "QueryPlan":
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )

    return QueryPlan(
        intent=Intent.SCREEN,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )
