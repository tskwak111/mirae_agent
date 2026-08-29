"""Focused deterministic Korean rendering contracts."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from finproof.domain.query_plan import QueryPlan


def test_current_answer_reuses_issued_snapshot_assumption_not_realtime() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle
    from finproof.registry.loader import RegistryBundle

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

    wording = RegistryBundle.from_package().answers.document["wording"]
    assert isinstance(wording, dict) or hasattr(wording, "__getitem__")
    assert wording["snapshot_assumption"] in draft.text
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

    assert "조건에 부합하는 후보: 국내채권 KR0000000001" in draft.text
    assert "domestic_bond" not in draft.text
    assert "추천" not in draft.text
    assert any(claim.kind is ClaimKind.CANDIDATE for claim in draft.claims)
    session._close()


def test_renderer_projects_requested_null_as_grounded_field_unavailable_claim() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import Intent, ProductType
    from finproof.evidence import ClaimVerifier
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    direct = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("buy_yield",),
                ),
            )
        )[0]
        .direct[0]
    )
    direct = direct.model_copy(
        update={
            "value": direct.value.model_copy(
                update={
                    "raw_value": None,
                    "normalized_value": None,
                    "quality_status": "missing_blank",
                }
            )
        }
    )
    evidence = EvidenceBundle(
        direct=(direct,), derived=(), summaries=(), material_policy_limitations=()
    )
    plan = _plan().model_copy(update={"intent": Intent.COMPARE, "metrics": ("buy_yield",)})

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-null", question="매수수익률을 비교해줘"),
        plan=plan,
        evidence=evidence,
    )

    assert "매수수익률: 제공 데이터에서 값을 확인할 수 없습니다." in draft.text
    unavailable = next(claim for claim in draft.claims if claim.field_id == "buy_yield")
    assert unavailable.value is None
    assert unavailable.evidence_ids == (direct.evidence_id,)
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims
    session._close()


def test_renderer_keeps_buy_yield_range_as_a_limitation_not_a_scalar_claim() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session(lot_yields=("3.1", "4.2"))
    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("buy_yield",),
            ),
        )
    )[0]
    evidence = EvidenceBundle(
        direct=record.direct,
        derived=record.derived,
        summaries=(),
        material_policy_limitations=("매수수익률은 유효 로트 중 최댓값이며 범위는 3.1~4.2입니다.",),
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-yield-range", question="매수수익률을 알려줘"),
        plan=_plan(),
        evidence=evidence,
    )

    assert "매수수익률" in draft.text
    assert "buy_yield_range:" not in draft.text
    assert all(claim.field_id != "buy_yield_range" for claim in draft.claims)
    session._close()


def test_renderer_keeps_identity_evidence_for_signatures_without_duplicate_value_claims() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("product_id", "product_name", "buy_yield"),
            ),
        )
    )[0]
    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-identity", question="매수수익률을 알려줘"),
        plan=_plan(),
        evidence=EvidenceBundle(
            direct=record.direct,
            derived=record.derived,
            summaries=(),
            material_policy_limitations=(),
        ),
    )

    assert {claim.field_id for claim in draft.claims if claim.field_id is not None} == {"buy_yield"}
    session._close()


def test_rank_answer_does_not_repeat_duplicate_metric_or_internal_partition_counts() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.query_plan import Intent, ProductType, SortDirection, SortSpec
    from finproof.evidence import ClaimVerifier
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    direct = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("product_id", "product_name", "buy_yield"),
                ),
            )
        )[0]
        .direct
    )
    common: dict[str, Any] = {
        "included_count": 1,
        "excluded_count": 2,
        "evidence_ids": tuple(item.evidence_id for item in direct),
        "validated_plan_sha256": "a" * 64,
        "version_bundle_sha256": "b" * 64,
        "artifact_manifest_hash": "c" * 64,
        "product_types": (ProductType.DOMESTIC_BOND,),
        "native_result_grains": (_plan().result_grain,),
    }
    rank = EvidenceSummary(
        summary_id="summary:rank:0",
        kind=EvidenceSummaryKind.RANK,
        policy_versions=("bond.buy_yield:rank",),
        partition_key="yield:KRW",
        product_id="KR0000000001",
        metric_id="buy_yield",
        rank=1,
        tie_count=1,
        value=Decimal("2.25"),
        **common,
    )
    partition = rank.model_copy(
        update={
            "summary_id": "summary:partition:0",
            "kind": EvidenceSummaryKind.PARTITION,
            "product_id": None,
            "metric_id": None,
            "rank": None,
            "tie_count": None,
            "value": 1,
        }
    )
    policy_counts = tuple(
        rank.model_copy(
            update={
                "summary_id": f"summary:policy:buy_yield:{population}",
                "kind": EvidenceSummaryKind.COUNT,
                "policy_versions": ("state:1.2.0", "metric:1.2.0", "answer:1.0.0"),
                "evidence_ids": (),
                "partition_key": f"policy:bond.buy_yield:{population}",
                "product_id": None,
                "rank": None,
                "tie_count": None,
                "value": value,
            }
        )
        for population, value in (("included", 1), ("missing", 2), ("zero", 0))
    )
    evidence = EvidenceBundle(
        direct=direct,
        derived=(),
        summaries=(*policy_counts, partition, rank),
        material_policy_limitations=(),
    )
    plan = _plan().model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("buy_yield",),
            "sort": (SortSpec(field="buy_yield", direction=SortDirection.DESC),),
        }
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-rank-compact", question="매수수익률 상위 1개"),
        plan=plan,
        evidence=evidence,
    )

    metric_claims = tuple(claim for claim in draft.claims if claim.field_id == "buy_yield")
    assert len(metric_claims) == 1
    assert rank.summary_id in metric_claims[0].evidence_ids
    assert next(item.evidence_id for item in direct if item.field_id == "buy_yield") not in (
        metric_claims[0].evidence_ids
    )
    assert "1위." in draft.text
    assert "1위. 국내채권 테스트 채권 (KR0000000001) — 매수수익률 2.25%" in draft.text
    assert "domestic_bond/instrument" not in draft.text
    assert "buy_yield" not in draft.text
    assert "- domestic_bond KR0000000001 buy_yield" not in draft.text
    assert "포함 개수" not in draft.text
    assert "결측 개수" not in draft.text
    assert "0값 개수" not in draft.text
    assert "분할 domestic_bond" not in draft.text
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims
    session._close()


def test_renderer_keeps_same_product_id_separate_across_product_types() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    direct = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("buy_yield",),
                ),
            )
        )[0]
        .direct[0]
    )
    evidence = EvidenceBundle(
        direct=(
            direct,
            direct.model_copy(
                update={
                    "evidence_id": "domestic_etf:KR0000000001:buy_yield",
                    "product_type": ProductType.DOMESTIC_ETF,
                }
            ),
        ),
        derived=(),
        summaries=(),
        material_policy_limitations=(),
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-native", question="조건에 맞는 상품 추천"),
        plan=_plan(),
        evidence=evidence,
    )

    candidates = tuple(claim for claim in draft.claims if claim.kind is ClaimKind.CANDIDATE)
    assert tuple((claim.product_type, claim.product_id) for claim in candidates) == (
        (ProductType.DOMESTIC_BOND, "KR0000000001"),
        (ProductType.DOMESTIC_ETF, "KR0000000001"),
    )
    assert "국내채권 KR0000000001" in draft.text
    assert "국내 ETF KR0000000001" in draft.text
    assert "domestic_" not in draft.text
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
            "domestic_etf 구성종목 자료는 제공되지 않아 "
            "보유하지 않았다는 결론을 내리지 않았습니다.",
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
    assert "국내 ETF 구성종목 자료는 제공되지 않아" in text
    assert "domestic_etf" not in text
    assert "지정한 조건을 충족하는 상품을 찾지 못했습니다." in no_result


def test_renderer_projects_rank_and_aggregate_included_count_values() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.evidence import (
        EvidenceBundle,
        EvidenceSummary,
        EvidenceSummaryKind,
        EvidenceSummaryValue,
    )
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.evidence import ClaimVerifier

    common: dict[str, Any] = {
        "included_count": 2,
        "excluded_count": 1,
        "evidence_ids": (),
        "validated_plan_sha256": "a" * 64,
        "version_bundle_sha256": "b" * 64,
        "artifact_manifest_hash": "c" * 64,
    }
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(
            EvidenceSummary(
                summary_id="summary:rank:0",
                kind=EvidenceSummaryKind.RANK,
                policy_versions=("buy_yield:rank",),
                product_types=(ProductType.DOMESTIC_BOND,),
                native_result_grains=(ResultGrain.INSTRUMENT,),
                partition_key="yield:KRW",
                product_id="KR0000000001",
                metric_id="buy_yield",
                rank=1,
                tie_count=1,
                value=Decimal("2.25"),
                **common,
            ),
            EvidenceSummary(
                summary_id="summary:aggregate:0",
                kind=EvidenceSummaryKind.AGGREGATE,
                policy_versions=("buy_yield:avg",),
                product_types=(ProductType.DOMESTIC_BOND,),
                native_result_grains=(ResultGrain.INSTRUMENT,),
                partition_key="yield:KRW",
                metric_id="buy_yield",
                value=Decimal("2.10"),
                group_values=(EvidenceSummaryValue(field_id="currency", value="KRW"),),
                **common,
            ),
        ),
        material_policy_limitations=(),
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-summary", question="수익률 순위와 평균은?"),
        plan=_plan(),
        evidence=evidence,
    )

    assert "1위. 국내채권 KR0000000001 — 매수수익률 2.25%" in draft.text
    assert ("국내채권 통화=KRW 매수수익률 평균: 2.1% (포함 2건, 제외 1건)") in draft.text
    assert "domestic_bond" not in draft.text
    assert "buy_yield" not in draft.text
    assert tuple(claim.value for claim in draft.claims if claim.kind is ClaimKind.NUMERIC) == (
        Decimal("2.25"),
        Decimal("2.10"),
    )
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims


def test_aggregate_renderer_does_not_project_sample_product_rows() -> None:
    """Rendering bounded aggregate evidence as products would misstate the aggregate output."""
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.query_plan import AggregationFunction, AggregationSpec, Intent, ProductType
    from finproof.evidence import ClaimVerifier
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    direct = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("product_id", "buy_yield"),
                ),
            )
        )[0]
        .direct
    )
    summary = EvidenceSummary(
        summary_id="summary:aggregate:0",
        kind=EvidenceSummaryKind.AGGREGATE,
        included_count=254,
        excluded_count=0,
        evidence_ids=tuple(item.evidence_id for item in direct),
        policy_versions=("bond.buy_yield:avg",),
        validated_plan_sha256="a" * 64,
        version_bundle_sha256="b" * 64,
        artifact_manifest_hash="c" * 64,
        product_types=(ProductType.DOMESTIC_BOND,),
        native_result_grains=(_plan().result_grain,),
        partition_key="yield:None:source:same_metric_only",
        metric_id="buy_yield",
        value=Decimal("3.10"),
    )
    partition = summary.model_copy(
        update={
            "summary_id": "summary:partition:0",
            "kind": EvidenceSummaryKind.PARTITION,
            "included_count": 5,
            "excluded_count": 249,
            "value": 5,
        }
    )
    evidence = EvidenceBundle(
        direct=direct,
        derived=(),
        summaries=(partition, summary),
        material_policy_limitations=(),
    )
    plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": ("buy_yield",),
            "aggregation": AggregationSpec(
                function=AggregationFunction.AVG,
                field="buy_yield",
                group_by=(),
            ),
        }
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-aggregate-only", question="평균 매수수익률은?"),
        plan=plan,
        evidence=evidence,
    )

    assert "매수수익률 평균: 3.1%" in draft.text
    assert "분할" not in draft.text
    assert "- domestic_bond KR0000000001" not in draft.text
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims
    session._close()


def test_renderer_distinguishes_source_recorded_and_state_validated_count() -> None:
    """Removing either count lens would conceal the state exclusion."""
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        ResultGrain,
    )
    from finproof.evidence import ClaimVerifier

    common: dict[str, Any] = {
        "included_count": 254,
        "excluded_count": 71,
        "evidence_ids": (),
        "validated_plan_sha256": "a" * 64,
        "version_bundle_sha256": "b" * 64,
        "artifact_manifest_hash": "c" * 64,
    }
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(
            EvidenceSummary(
                summary_id="summary:count",
                kind=EvidenceSummaryKind.COUNT,
                policy_versions=("count:count",),
                value=325,
                **common,
            ),
            EvidenceSummary(
                summary_id="summary:aggregate:0",
                kind=EvidenceSummaryKind.AGGREGATE,
                policy_versions=("count:count",),
                product_types=(ProductType.DOMESTIC_BOND,),
                native_result_grains=(ResultGrain.INSTRUMENT,),
                partition_key="count:instrument:domestic_bond",
                value=254,
                **common,
            ),
        ),
        material_policy_limitations=(),
    )
    plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "aggregation": AggregationSpec(
                function=AggregationFunction.COUNT, field=None, group_by=()
            ),
        }
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-count-lenses", question="두 수를 집계해줘"),
        plan=plan,
        evidence=evidence,
    )

    assert "원천 기록 기준 상품 개수: 325" in draft.text
    assert "상태 검증 후 상품 개수: 254" in draft.text
    assert tuple(claim.value for claim in draft.claims if claim.kind is ClaimKind.NUMERIC) == (
        325,
        254,
    )
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims
    grouped = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-grouped-count", question="그룹별 수를 집계해줘"),
        plan=plan.model_copy(
            update={
                "aggregation": AggregationSpec(
                    function=AggregationFunction.COUNT, field=None, group_by=("currency",)
                )
            }
        ),
        evidence=evidence,
    )
    assert "원천 기록 기준 상품 개수" not in grouped.text


def test_renderer_projects_recorded_rank_lens_separately() -> None:
    """Removing recorded summaries would make a recorded zero disappear from the answer."""
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.evidence import ClaimVerifier

    common: dict[str, Any] = {
        "included_count": 1,
        "excluded_count": 0,
        "evidence_ids": (),
        "validated_plan_sha256": "a" * 64,
        "version_bundle_sha256": "b" * 64,
        "artifact_manifest_hash": "c" * 64,
        "product_types": (ProductType.OVERSEAS_ETN,),
        "native_result_grains": (ResultGrain.LISTED_PRODUCT,),
        "partition_key": "recorded:overseas_etn.total_fee:USD",
        "product_id": "NRGD.K",
        "metric_id": "total_fee",
        "value": Decimal("0"),
    }
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(
            EvidenceSummary(
                summary_id="summary:recorded:0",
                kind=EvidenceSummaryKind.RECORDED,
                policy_versions=("overseas_etn.total_fee:recorded",),
                **common,
            ),
        ),
        material_policy_limitations=(
            "기록된 0값은 비교 가능 기준에서 제외했으며, 실제 무보수인지는 검증되지 않았습니다.",
        ),
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-recorded", question="보수를 보여줘"),
        plan=_plan(),
        evidence=evidence,
    )

    assert "제공 데이터 기록값" in draft.text
    assert "해외 ETN NRGD.K — 총보수 0%" in draft.text
    assert "overseas_etn" not in draft.text
    assert "total_fee" not in draft.text
    assert "실제 무보수인지는 검증되지 않았습니다." in draft.text
    assert next(claim for claim in draft.claims if claim.kind is ClaimKind.NUMERIC).value == 0
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims


def test_renderer_projects_actual_compatibility_partition_identity() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.evidence import ClaimVerifier

    summary = EvidenceSummary(
        summary_id="summary:partition:0",
        kind=EvidenceSummaryKind.PARTITION,
        included_count=2,
        excluded_count=1,
        evidence_ids=(),
        policy_versions=("metric:1.0.0",),
        validated_plan_sha256="a" * 64,
        version_bundle_sha256="b" * 64,
        artifact_manifest_hash="c" * 64,
        product_types=(ProductType.DOMESTIC_BOND,),
        native_result_grains=(ResultGrain.INSTRUMENT,),
        partition_key="yield:KRW",
        value=2,
    )
    evidence = EvidenceBundle(
        direct=(), derived=(), summaries=(summary,), material_policy_limitations=()
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-partition", question="수익률 비교"),
        plan=_plan(),
        evidence=evidence,
    )

    assert "국내채권 비교 가능 결과: 2건" in draft.text
    assert "yield:KRW" not in draft.text
    partition_claim = next(claim for claim in draft.claims if claim.kind is ClaimKind.NUMERIC)
    assert partition_claim.partition_key == "yield:KRW"
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims


def test_renderer_formats_named_currency_rank_without_internal_tokens() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    direct = list(
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("product_id", "product_name"),
                ),
            )
        )[0]
        .direct
    )
    direct = [
        item.model_copy(
            update={
                "evidence_id": item.evidence_id.replace("domestic_bond", "domestic_etf"),
                "product_type": ProductType.DOMESTIC_ETF,
                "value": (
                    item.value.model_copy(
                        update={
                            "raw_value": "테스트 ETF",
                            "normalized_value": "테스트 ETF",
                        }
                    )
                    if item.field_id == "product_name"
                    else item.value
                ),
            }
        )
        for item in direct
    ]
    summary = EvidenceSummary(
        summary_id="summary:rank:aum",
        kind=EvidenceSummaryKind.RANK,
        included_count=1,
        excluded_count=0,
        evidence_ids=tuple(item.evidence_id for item in direct),
        policy_versions=("domestic_etf.aum:rank",),
        validated_plan_sha256="a" * 64,
        version_bundle_sha256="b" * 64,
        artifact_manifest_hash="c" * 64,
        product_types=(ProductType.DOMESTIC_ETF,),
        native_result_grains=(ResultGrain.LISTED_PRODUCT,),
        partition_key="aum:KRW:snapshot:same_currency_or_fixed_fx",
        product_id="KR0000000001",
        metric_id="aum",
        rank=1,
        tie_count=1,
        value=Decimal("25474814176500.000000000000000000"),
    )

    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-aum", question="순자산총액 1위"),
        plan=_plan(),
        evidence=EvidenceBundle(
            direct=tuple(direct),
            derived=(),
            summaries=(summary,),
            material_policy_limitations=(),
        ),
    )

    assert (
        "1위. 국내 ETF 테스트 ETF (KR0000000001) — 순자산총액 25,474,814,176,500 KRW"
    ) in draft.text
    assert "domestic_etf" not in draft.text
    assert "listed_product" not in draft.text
    session._close()


def test_renderer_labels_state_counts_by_product_type() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.query_plan import ProductType, ResultGrain

    common: dict[str, Any] = {
        "kind": EvidenceSummaryKind.COUNT,
        "included_count": 20_407,
        "excluded_count": 90,
        "evidence_ids": (),
        "policy_versions": ("state:count",),
        "validated_plan_sha256": "a" * 64,
        "version_bundle_sha256": "b" * 64,
        "artifact_manifest_hash": "c" * 64,
        "product_types": (ProductType.DOMESTIC_BOND,),
        "native_result_grains": (ResultGrain.INSTRUMENT,),
    }
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(
            EvidenceSummary(
                summary_id="summary:source:count",
                kind=EvidenceSummaryKind.COUNT,
                included_count=20_497,
                excluded_count=0,
                evidence_ids=(),
                policy_versions=("source:count",),
                validated_plan_sha256="a" * 64,
                version_bundle_sha256="b" * 64,
                artifact_manifest_hash="c" * 64,
                value=20_497,
            ),
            EvidenceSummary(
                summary_id="summary:state:count",
                partition_key="state-validated:domestic_bond",
                value=20_407,
                **common,
            ),
            EvidenceSummary(
                summary_id="summary:state:difference",
                partition_key="state-difference:domestic_bond",
                value=90,
                **common,
            ),
        ),
        material_policy_limitations=(),
    )

    text = (
        AnswerRenderer()
        .render(
            request=AnswerRequest(question_id="q-state-count", question="상품 수"),
            plan=_plan(),
            evidence=evidence,
        )
        .text
    )

    assert "국내채권 상태 검증 후 상품 개수: 20407" in text
    assert "국내채권 원천 기록과 상태 검증 개수 차이: 90" in text


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
