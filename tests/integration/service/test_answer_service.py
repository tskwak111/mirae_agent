"""Focused deterministic answer-service composition contracts."""

from datetime import date

import pytest
from tests.integration.query.test_executor import _session


@pytest.mark.parametrize(
    ("intent", "needs_clarification"), [("clarify", True), ("unsupported", False)]
)
def test_clarify_and_unsupported_answers_execute_no_repository_query(
    intent: str,
    needs_clarification: bool,
) -> None:
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
    from finproof.service import AnswerService

    class Connection:
        calls = 0

        def execute(self, _sql: str, _parameters: object = ()) -> None:
            self.calls += 1
            raise AssertionError("terminal plans must not execute a repository query")

        def close(self) -> None: ...

    connection = Connection()
    session = _session(connection)  # type: ignore[arg-type]
    plan = QueryPlan(
        intent=Intent(intent),
        product_types=(),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=needs_clarification,
        clarification_reason="상품 조건을 확인해 주세요.",
    )

    from finproof.service.limits import RequestDeadline

    result = AnswerService(session).prepare_plan(
        AnswerRequest(question_id=f"q-{intent}", question="질문"),
        plan,
        RequestDeadline.start(),
    )

    assert connection.calls == 0
    assert result.fact_pack.surface_parts[0].text
    assert set(result.trace.latency_ms) == {"database", "evidence", "render"}
    session._close()


def test_trace_preserves_planned_product_type_with_no_comparable_metric_values() -> None:
    from decimal import Decimal

    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle, EvidenceSummary, EvidenceSummaryKind
    from finproof.domain.execution import (
        ComparisonPartition,
        ExecutionBundle,
        ExecutionSegment,
        ValidatedQueryPlan,
    )
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.quality import (
        CompatibilityPartition,
        MetricPolicyResult,
        MetricValue,
        PolicyExecutionResult,
    )
    from finproof.service import AnswerService
    from finproof.storage import RawExecutionResult, RawSegmentResult

    class Connection:
        def close(self) -> None: ...

    session = _session(Connection())  # type: ignore[arg-type]
    plan = QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=(ProductType.DOMESTIC_ETN, ProductType.OVERSEAS_ETN),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=("total_fee",),
        sort=(SortSpec(field="total_fee", direction=SortDirection.ASC),),
        aggregation=None,
        top_k=3,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )
    native = ResultGrain.LISTED_PRODUCT
    segments = tuple(
        ExecutionSegment(
            product_type=product_type,
            native_result_grain=native,
            filters=(),
            metrics=("total_fee",),
            sort=plan.sort,
            aggregation=None,
            top_k=3,
        )
        for product_type in plan.product_types
    )
    bundle = ExecutionBundle(
        validated_plan=ValidatedQueryPlan._issue(plan=plan, resolutions=(), context=()),
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        segments=segments,
        comparison_partitions=(
            ComparisonPartition(
                partition_id="partition-1",
                product_types=plan.product_types,
                compatibility_key="annual_fee:percent:annual_source_convention:none",
            ),
        ),
        response_grain=ResultGrain.PRODUCT,
    )
    raw = RawExecutionResult(
        segments=tuple(
            RawSegmentResult(
                product_type=product_type,
                native_result_grain=native,
                rows=(),
                candidate_count=count,
                max_batch_rows=0,
            )
            for product_type, count in zip(plan.product_types, (532, 59), strict=True)
        ),
        candidate_count=591,
    )
    overseas = MetricValue(
        metric_id="overseas_etf.total_fee",
        product_type=ProductType.OVERSEAS_ETN,
        product_id="OVERSEAS-VALID",
        value=Decimal("0.85"),
        quality_status="valid",
        period="annual_source_convention",
    )
    partition_key = "annual_fee:None:annual_source_convention:same_definition_with_source_caveat"
    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=532,
        metric_policy=MetricPolicyResult(
            recorded_values=(overseas,),
            comparison_valid_values=(overseas,),
            excluded_count=532,
            warnings=("metric values excluded from comparison",),
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(
            CompatibilityPartition(
                compatibility_key=partition_key,
                currency=None,
                period="annual_source_convention",
                values=(overseas,),
                selected_values=(overseas,),
                caveats=(),
            ),
        ),
        aggregates=(),
        ranks=(),
        warnings=("metric values excluded from comparison",),
    )
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(
            EvidenceSummary(
                summary_id="summary:partition:empty:domestic_etn",
                kind=EvidenceSummaryKind.PARTITION,
                included_count=0,
                excluded_count=532,
                evidence_ids=(),
                policy_versions=("metric:1.0.0",),
                validated_plan_sha256="a" * 64,
                version_bundle_sha256="b" * 64,
                artifact_manifest_hash="c" * 64,
                product_types=(ProductType.DOMESTIC_ETN,),
                native_result_grains=(native,),
                partition_key=partition_key,
                value=0,
            ),
        ),
        material_policy_limitations=(),
    )

    trace = AnswerService(session)._trace(
        request=AnswerRequest(question_id="q-empty-segment", question="ETN 유형별 하위 3개"),
        plan=plan,
        bundle=bundle,
        raw=raw,
        policy_result=policy,
        evidence=evidence,
    )

    assert tuple(segment.product_type for segment in trace.segments) == plan.product_types
    assert trace.segments[0].returned == 0
    session._close()


def test_answer_service_composes_exact_runtime_resolution_validation_execution_policy_evidence_render_verify_order() -> (  # noqa: E501
    None
):
    from finproof.domain.answers import (
        AnswerDraft,
        AnswerRequest,
        VerifiedAnswer,
    )
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import (
        EntityMention,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.entity import ResolutionCandidate, ResolutionMatchKind, ResolutionResult
    from finproof.service import AnswerService

    class Connection:
        def close(self) -> None: ...

    session = _session(Connection())  # type: ignore[arg-type]
    service = AnswerService(session)
    order: list[str] = []
    evidence = EvidenceBundle(direct=(), derived=(), summaries=(), material_policy_limitations=())
    draft = AnswerDraft(
        text="2026-07-11 제공 스냅샷 기준",
        claims=(),
    )
    verified = VerifiedAnswer(text=draft.text, claims=())
    candidate = ResolutionCandidate(
        product_id="KR0000000001",
        product_type=ProductType.DOMESTIC_BOND,
        name="테스트채권",
        match_kind=ResolutionMatchKind.EXACT_PRODUCT_ID,
        score=10_000,
    )

    class Resolver:
        def resolve(self, *_args: object, **_kwargs: object) -> ResolutionResult:
            order.append("resolution")
            return ResolutionResult(selected=candidate, candidates=(candidate,))

    class Validator:
        def validate(self, *_args: object, **_kwargs: object) -> object:
            order.append("validation")
            return object()

    class Segmenter:
        def build(self, *_args: object, **_kwargs: object) -> object:
            order.append("segmentation")
            return object()

    class Executor:
        def execute(self, *_args: object, **_kwargs: object) -> object:
            order.append("execution")
            return object()

    class Policy:
        def apply(self, *_args: object, **_kwargs: object) -> object:
            order.append("policy")
            return object()

    class Evidence:
        def build(self, *_args: object, **_kwargs: object) -> EvidenceBundle:
            order.append("evidence")
            return evidence

    class Renderer:
        def render(self, *_args: object, **_kwargs: object) -> AnswerDraft:
            order.append("render")
            return draft

    class Verifier:
        def verify(self, *_args: object, **_kwargs: object) -> VerifiedAnswer:
            order.append("verify")
            return verified

    service._resolver = Resolver()  # type: ignore[assignment]
    service._validator = Validator()  # type: ignore[assignment]
    service._segmenter = Segmenter()  # type: ignore[assignment]
    service._executor = Executor()  # type: ignore[assignment]
    service._policy = Policy()  # type: ignore[assignment]
    service._evidence_builder = Evidence()  # type: ignore[assignment]
    service._evidence_repository = object()  # type: ignore[assignment]
    service._renderer = Renderer()  # type: ignore[assignment]
    service._verifier = Verifier()  # type: ignore[assignment]
    plan = QueryPlan(
        intent=Intent.LOOKUP,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(EntityMention(text="KR0000000001"),),
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

    from finproof.service.limits import RequestDeadline

    result = service.prepare_plan(
        AnswerRequest(question_id="q-order", question="KR0000000001 알려줘"),
        plan,
        RequestDeadline.start(),
    )

    assert result.fact_pack.surface_parts[0].text == verified.text
    assert result.claims == verified.claims
    assert order == [
        "resolution",
        "validation",
        "segmentation",
        "execution",
        "policy",
        "evidence",
        "render",
        "verify",
    ]
    session._close()


def test_official_runtime_returns_one_verified_evidence_backed_answer_and_trace() -> None:
    import json
    from decimal import Decimal

    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.execution import TraceValidation
    from finproof.domain.query_plan import (
        EntityMention,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.service import AnswerService

    record_session, record = _bond_evidence_session()
    record_session._close()

    class Cursor:
        def __init__(self, rows: list[tuple[object, ...]]) -> None:
            self.rows = rows
            self.used = False

        def fetchall(self) -> list[tuple[object, ...]]:
            return self.rows

        def fetchmany(self, _size: int) -> list[tuple[object, ...]]:
            if self.used:
                return []
            self.used = True
            return self.rows

    class Connection:
        def execute(self, sql: str, _parameters: object = ()) -> Cursor:
            if sql.startswith("SELECT product_id, name, short_name "):
                return Cursor([("KR0000000001", "테스트채권", "테스트")])
            if sql.startswith("SELECT product_id, market_identifier, product_type"):
                return Cursor([])
            if sql.startswith("SELECT product_id, market_identifier, isin"):
                return Cursor([])
            if sql.startswith("SELECT fund_item_id"):
                return Cursor([])
            if '"record_json"' in sql:
                return Cursor([("KR0000000001", canonical_record_json(record))])
            if 'FROM "silver_bond_instrument"' in sql:
                return Cursor(
                    [
                        (
                            "KR0000000001",
                            "valid",
                            Decimal("2.25"),
                            "valid",
                            Decimal("10"),
                            "valid",
                            date(2027, 7, 11),
                            "valid",
                        )
                    ]
                )
            raise AssertionError(f"unexpected SQL shape: {sql[:80]}")

        def close(self) -> None: ...

    session = _session(Connection())  # type: ignore[arg-type]
    plan = QueryPlan(
        intent=Intent.LOOKUP,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(EntityMention(text="KR0000000001"),),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=("buy_yield",),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )

    from finproof.service.limits import RequestDeadline

    result = AnswerService(session).prepare_plan(
        AnswerRequest(question_id="q-official-runtime", question="이 채권 수익률 알려줘"),
        plan,
        RequestDeadline.start(),
    )

    context = json.loads(result.retrieved_context)
    numeric = tuple(claim for claim in result.claims if claim.kind is ClaimKind.NUMERIC)
    answer = result.fact_pack.surface_parts[0].text
    assert "KR0000000001" in answer
    assert "2.25" in answer
    assert numeric
    assert numeric[0].evidence_ids
    assert context["format"] == "finproof.fact-pack.v1"
    assert context["claim_signatures"]
    assert result.trace.validation is TraceValidation.PASSED
    assert tuple(segment.partition_key for segment in result.trace.segments) == (
        "bond_buy_yield:None:yield_to_maturity_like_source_field:"
        "not_equal_to_historical_period_return",
    )
    assert result.trace.candidate_counts == {"raw": 1, "eligible": 1, "returned": 1}
    assert (
        result.trace.versions["artifact_manifest_hash"] == session.versions.artifact_manifest_hash
    )
    session._close()


def test_comparison_fact_signature_binds_both_evidence_derived_entities() -> None:
    from decimal import Decimal
    from pathlib import PurePosixPath
    from typing import cast

    from finproof.domain.answers import AnswerClaim, ClaimKind
    from finproof.domain.evidence import DirectEvidence, EvidenceBundle
    from finproof.domain.locators import SourceCellLocator
    from finproof.domain.quality import QualityStatus
    from finproof.domain.query_plan import ProductType
    from finproof.domain.values import NormalizedValue
    from finproof.registry.loader import RegistryBundle
    from finproof.service.answer_service import _claim_signature

    def direct(product_id: str, field_id: str, value: str | Decimal) -> DirectEvidence[object]:
        return cast(
            DirectEvidence[object],
            DirectEvidence[str | Decimal](
                evidence_id=f"direct:{product_id}:{field_id}",
                product_type=ProductType.DOMESTIC_ETF,
                product_id=product_id,
                field_id=field_id,
                value=NormalizedValue[str | Decimal](
                    raw_value=str(value),
                    normalized_value=value,
                    quality_status=QualityStatus.VALID,
                    rule_id=f"domestic_etf.{field_id}",
                    rule_version="1.0.0",
                    source=SourceCellLocator(
                        source_table="PREF01N001",
                        source_file=PurePosixPath("domestic.xlsx"),
                        source_sheet="datarows",
                        source_row_number=2 if product_id == "ETF-1" else 3,
                        source_column_name=field_id,
                        source_column_number=1,
                        source_column_letter="A",
                        source_checksum="a" * 64,
                        source_snapshot_date=date(2026, 8, 24),
                        source_applicable_date=date(2026, 8, 22),
                    ),
                ),
            ),
        )

    names = (
        direct("ETF-1", "product_name", "첫 번째 ETF"),
        direct("ETF-2", "product_name", "두 번째 ETF"),
    )
    metrics = (
        direct("ETF-1", "return_1y", Decimal("3.10")),
        direct("ETF-2", "return_1y", Decimal("2.10")),
    )
    evidence = EvidenceBundle(
        direct=(*names, *metrics),
        derived=(),
        summaries=(),
        material_policy_limitations=(),
    )
    claim = AnswerClaim(
        claim_id="claim:comparison",
        kind=ClaimKind.NUMERIC,
        text="ETF-1의 1년 수익률이 ETF-2보다 1.00 높습니다.",
        product_type=ProductType.DOMESTIC_ETF,
        product_id="ETF-1",
        field_id="return_1y_difference",
        value=Decimal("1.00"),
        evidence_ids=("difference:return_1y",),
    )

    signature = _claim_signature(claim, (), evidence, RegistryBundle.from_package())

    assert tuple((item.product_id, item.display_name) for item in signature.entities) == (
        ("ETF-1", "첫 번째 ETF"),
        ("ETF-2", "두 번째 ETF"),
    )
    with pytest.raises(ValueError, match="entity name is missing or ambiguous"):
        _claim_signature(
            claim,
            (),
            evidence.model_copy(update={"direct": (*names[:1], *metrics)}),
            RegistryBundle.from_package(),
        )
