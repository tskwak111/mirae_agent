import json
from datetime import date
from decimal import Decimal

import pytest

from finproof.cli.evaluate import _observed, _observed_aggregates, _observed_products
from finproof.domain.answers import (
    AnswerClaim,
    AnswerResult,
    ClaimKind,
    ClaimSignature,
    EntitySignature,
    FactPack,
    SurfacePart,
    VerifiedAnswer,
)
from finproof.domain.evidence import (
    EvidenceBundle,
    EvidenceSummary,
    EvidenceSummaryKind,
    EvidenceSummaryValue,
)
from finproof.domain.execution import ExecutionTrace, ExecutionTraceSegment, TraceValidation
from finproof.domain.query_plan import (
    AggregationFunction,
    AggregationSpec,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.evaluation.models import ExpectedAggregate, GoldenCase
from finproof.evidence.serializer import serialize_evidence_context


def _plan(
    *,
    intent: Intent,
    products: tuple[ProductType, ...],
    grain: ResultGrain,
    aggregation: AggregationSpec | None = None,
) -> QueryPlan:
    return QueryPlan(
        intent=intent,
        product_types=products,
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=grain,
        filters=(),
        metrics=("return_1y",) if aggregation is not None else (),
        sort=(),
        aggregation=aggregation,
        top_k=2,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )


def _summary(**updates: object) -> EvidenceSummary:
    values: dict[str, object] = {
        "summary_id": "summary:rank:0",
        "kind": EvidenceSummaryKind.RANK,
        "included_count": 1,
        "excluded_count": 0,
        "evidence_ids": (),
        "policy_versions": ("return_1y:rank",),
        "validated_plan_sha256": "a" * 64,
        "version_bundle_sha256": "b" * 64,
        "artifact_manifest_hash": "c" * 64,
        "product_types": (ProductType.DOMESTIC_ETF,),
        "native_result_grains": (ResultGrain.LISTED_PRODUCT,),
        "partition_key": "return_1y:KRW",
        "product_id": "SAME",
        "metric_id": "return_1y",
        "rank": 1,
        "tie_count": 1,
        "value": Decimal("3.10"),
    }
    values.update(updates)
    return EvidenceSummary.model_validate(values)


def _case_for_trace(plan: QueryPlan, *, assembled_envelope: bool) -> GoldenCase:
    native_segments = [
        {
            "product_type": product_type,
            "native_result_grain": (
                "instrument"
                if product_type is ProductType.DOMESTIC_BOND
                else "fund_item"
                if product_type is ProductType.PUBLIC_FUND
                else "listed_product"
            ),
        }
        for product_type in plan.product_types
    ]
    return GoldenCase.model_validate(
        {
            "case_id": "TRACE-ENVELOPE-001",
            "category": "cross_product",
            "question": "상품 유형별 결과",
            "expected_plan": {
                "intent": plan.intent,
                "product_types": plan.product_types,
                "as_of_date": "2026-07-11",
                "result_grain": plan.result_grain,
                "top_k_scope": plan.top_k_scope,
                "native_segments": native_segments,
            },
            "expected_result": {"assembled_envelope": assembled_envelope},
            "expected_answer": {"required_concepts": [], "forbidden_concepts": []},
            "review": {
                "reviewer": "test-reviewer",
                "reviewed_at": "2026-08-24",
                "source": "controlled-trace-fixture",
            },
        }
    )


def _answer_result(
    *,
    plan: QueryPlan,
    segments: tuple[ExecutionTraceSegment, ...],
    product: tuple[ProductType, str] | None,
) -> AnswerResult:
    claim = (
        None
        if product is None
        else AnswerClaim(
            claim_id=f"claim:{product[1]}",
            kind=ClaimKind.TEXT,
            text=f"{product[0].value} {product[1]}",
            product_type=product[0],
            product_id=product[1],
            evidence_ids=(f"evidence:{product[1]}",),
        )
    )
    claims = () if claim is None else (claim,)
    text = "2026-07-11 제공 스냅샷 기준"
    pack = FactPack(
        surface_parts=(
            SurfacePart(
                part_id="surface:answer",
                text=text,
                claim_ids=tuple(item.claim_id for item in claims),
                limitation_codes=("snapshot_assumption",),
            ),
        ),
        claim_signatures=tuple(
            ClaimSignature(
                claim_id=item.claim_id,
                kind=item.kind,
                surface_text=item.text,
                entities=(
                    EntitySignature(
                        product_type=item.product_type,
                        product_id=item.product_id,
                        display_name=item.product_id,
                    ),
                ),
                values=(),
                rank=None,
                tie_count=None,
                partition=None,
                comparison=None,
                evidence_ids=item.evidence_ids,
                limitation_codes=(),
            )
            for item in claims
            if item.product_type is not None and item.product_id is not None
        ),
        required_claim_ids=tuple(item.claim_id for item in claims),
        required_limitation_codes=("snapshot_assumption",),
        evidence_context_sha256="c" * 64,
    )
    return AnswerResult(
        answer=VerifiedAnswer(text=text, claims=claims),
        retrieved_context=pack.model_dump_json(),
        trace=ExecutionTrace(
            correlation_id="trace-envelope",
            intent=plan.intent,
            product_types=plan.product_types,
            as_of_date=plan.as_of_date,
            result_grain=plan.result_grain,
            top_k_scope=plan.top_k_scope,
            segments=segments,
            candidate_counts={},
            tools=(),
            policy_ids=(),
            validation=TraceValidation.PASSED,
            versions={},
            latency_ms={},
        ),
    )


@pytest.mark.parametrize("product", [None, (ProductType.DOMESTIC_BOND, "BOND-ONLY")])
def test_heterogeneous_execution_trace_records_envelope_for_empty_or_partial_results(
    product: tuple[ProductType, str] | None,
) -> None:
    plan = _plan(
        intent=Intent.SCREEN,
        products=(ProductType.DOMESTIC_BOND, ProductType.PUBLIC_FUND),
        grain=ResultGrain.PRODUCT,
    )
    segments = (
        ExecutionTraceSegment(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            partition_key="bond:KRW",
            candidate_counts={},
            returned=0 if product is None else 1,
        ),
        ExecutionTraceSegment(
            product_type=ProductType.PUBLIC_FUND,
            native_result_grain=ResultGrain.FUND_ITEM,
            partition_key="fund:KRW",
            candidate_counts={},
            returned=0,
        ),
    )

    observed = _observed(
        _case_for_trace(plan, assembled_envelope=True),
        plan,
        _answer_result(plan=plan, segments=segments, product=product),
        0,
    )

    assert observed.assembled_envelope is True
    assert len(observed.products) == (0 if product is None else 1)


def test_product_trace_with_only_one_native_grain_is_not_an_assembled_envelope() -> None:
    plan = _plan(
        intent=Intent.SCREEN,
        products=(ProductType.DOMESTIC_ETF, ProductType.DOMESTIC_ETN),
        grain=ResultGrain.PRODUCT,
    )
    segments = tuple(
        ExecutionTraceSegment(
            product_type=product_type,
            native_result_grain=ResultGrain.LISTED_PRODUCT,
            partition_key=f"{product_type.value}:KRW",
            candidate_counts={},
            returned=0,
        )
        for product_type in plan.product_types
    )

    observed = _observed(
        _case_for_trace(plan, assembled_envelope=False),
        plan,
        _answer_result(plan=plan, segments=segments, product=None),
        0,
    )

    assert observed.assembled_envelope is False


def test_end_to_end_observation_reads_verified_claims_from_fact_pack_result() -> None:
    from finproof.domain.answers import (
        AnswerClaim,
        ClaimKind,
        ClaimSignature,
        EntitySignature,
        FactPack,
        SurfacePart,
        ValueSignature,
    )

    plan = _plan(
        intent=Intent.SCREEN_RANK,
        products=(ProductType.DOMESTIC_ETF,),
        grain=ResultGrain.LISTED_PRODUCT,
    )
    claim = AnswerClaim(
        claim_id="claim:rank",
        kind=ClaimKind.NUMERIC,
        text="ETF-1 return_1y: 3.10 (1위)",
        product_type=ProductType.DOMESTIC_ETF,
        product_types=(ProductType.DOMESTIC_ETF,),
        native_result_grains=(ResultGrain.LISTED_PRODUCT,),
        partition_key="return_1y:KRW",
        product_id="ETF-1",
        field_id="return_1y",
        value=Decimal("3.10"),
        evidence_ids=("summary:rank:0", "direct:ETF-1:return_1y"),
    )
    pack = FactPack(
        surface_parts=(
            SurfacePart(
                part_id="surface:answer",
                text=claim.text,
                claim_ids=(claim.claim_id,),
                limitation_codes=("snapshot_assumption",),
            ),
        ),
        claim_signatures=(
            ClaimSignature(
                claim_id=claim.claim_id,
                kind=claim.kind,
                surface_text=claim.text,
                entities=(
                    EntitySignature(
                        product_type=ProductType.DOMESTIC_ETF,
                        product_id="ETF-1",
                        display_name="테스트 ETF",
                    ),
                ),
                values=(
                    ValueSignature(
                        field_id="return_1y",
                        canonical_normalized_json='"3.10"',
                        display_text="3.10",
                        unit="percent",
                    ),
                ),
                rank=1,
                tie_count=1,
                partition="return_1y:KRW",
                comparison=None,
                evidence_ids=claim.evidence_ids,
                limitation_codes=(),
            ),
        ),
        required_claim_ids=(claim.claim_id,),
        required_limitation_codes=("snapshot_assumption",),
        evidence_context_sha256="a" * 64,
    )
    case = GoldenCase.model_validate(
        {
            "case_id": "FACT-PACK-OBSERVATION-001",
            "category": "rank",
            "question": "1년 수익률 상위 ETF",
            "expected_plan": {
                "intent": "screen_rank",
                "product_types": ["domestic_etf"],
                "as_of_date": "2026-07-11",
                "result_grain": "listed_product",
                "top_k_scope": "global",
            },
            "expected_result": {
                "products": [
                    {
                        "product_type": "domestic_etf",
                        "native_result_grain": "listed_product",
                        "product_id": "ETF-1",
                    }
                ],
                "values": [
                    {
                        "product_id": "ETF-1",
                        "field_id": "return_1y",
                        "value_type": "decimal",
                        "value": "3.10",
                    }
                ],
            },
            "expected_answer": {
                "required_concepts": [],
                "forbidden_concepts": [],
                "expect_limitation": True,
            },
            "review": {
                "reviewer": "test-reviewer",
                "reviewed_at": "2026-08-29",
                "source": "fact-pack-observation-regression",
            },
        }
    )
    result = AnswerResult(
        answer=VerifiedAnswer(text=claim.text, claims=(claim,)),
        retrieved_context=pack.model_dump_json(),
        trace=ExecutionTrace(
            correlation_id="fact-pack-observation",
            intent=plan.intent,
            product_types=plan.product_types,
            as_of_date=plan.as_of_date,
            result_grain=plan.result_grain,
            top_k_scope=plan.top_k_scope,
            segments=(
                ExecutionTraceSegment(
                    product_type=ProductType.DOMESTIC_ETF,
                    native_result_grain=ResultGrain.LISTED_PRODUCT,
                    partition_key="return_1y:KRW",
                    candidate_counts={"raw": 1, "eligible": 1},
                    returned=1,
                ),
            ),
            candidate_counts={"raw": 1, "eligible": 1, "returned": 1},
            tools=(),
            policy_ids=(),
            validation=TraceValidation.PASSED,
            versions={},
            latency_ms={},
        ),
    )

    observed = _observed(case, plan, result, 0)

    assert tuple(item.product_id for item in observed.products) == ("ETF-1",)
    assert tuple(item.value for item in observed.values) == (Decimal("3.10"),)
    assert observed.evidence_ids == claim.evidence_ids
    assert observed.limitation_present is True


def test_end_to_end_observation_reads_aggregate_claim_from_fact_pack_result() -> None:
    from finproof.domain.answers import (
        AnswerClaim,
        ClaimKind,
        ClaimSignature,
        FactPack,
        SurfacePart,
        ValueSignature,
    )

    aggregation = AggregationSpec(
        function=AggregationFunction.AVG,
        field="return_1y",
        group_by=("currency",),
    )
    plan = _plan(
        intent=Intent.AGGREGATE,
        products=(ProductType.DOMESTIC_ETF,),
        grain=ResultGrain.LISTED_PRODUCT,
        aggregation=aggregation,
    )
    claim = AnswerClaim.model_validate(
        {
            "claim_id": "claim:aggregate",
            "kind": ClaimKind.NUMERIC,
            "text": "currency=KRW return_1y 평균: 3.10",
            "product_type": ProductType.DOMESTIC_ETF,
            "product_types": (ProductType.DOMESTIC_ETF,),
            "native_result_grains": (ResultGrain.LISTED_PRODUCT,),
            "partition_key": "return_1y:KRW",
            "field_id": "return_1y",
            "value": Decimal("3.10"),
            "group_values": ({"field_id": "currency", "value": "KRW"},),
            "evidence_ids": ("summary:aggregate:0",),
        }
    )
    pack = FactPack(
        surface_parts=(
            SurfacePart(
                part_id="surface:answer",
                text=claim.text,
                claim_ids=(claim.claim_id,),
                limitation_codes=(),
            ),
        ),
        claim_signatures=(
            ClaimSignature(
                claim_id=claim.claim_id,
                kind=claim.kind,
                surface_text=claim.text,
                entities=(),
                values=(
                    ValueSignature(
                        field_id="return_1y",
                        canonical_normalized_json='"3.10"',
                        display_text="3.10",
                        unit="percent",
                    ),
                ),
                rank=None,
                tie_count=None,
                partition="return_1y:KRW",
                comparison=None,
                evidence_ids=claim.evidence_ids,
                limitation_codes=(),
            ),
        ),
        required_claim_ids=(claim.claim_id,),
        required_limitation_codes=(),
        evidence_context_sha256="b" * 64,
    )
    case = GoldenCase.model_validate(
        {
            "case_id": "FACT-PACK-OBSERVATION-AGGREGATE-001",
            "category": "aggregate",
            "question": "통화별 1년 수익률 평균",
            "expected_plan": {
                "intent": "aggregate",
                "product_types": ["domestic_etf"],
                "as_of_date": "2026-07-11",
                "result_grain": "listed_product",
                "top_k_scope": "global",
                "aggregation": {
                    "function": "avg",
                    "field": "return_1y",
                    "group_by": ["currency"],
                },
            },
            "expected_result": {
                "aggregates": [
                    {
                        "function": "avg",
                        "field_id": "return_1y",
                        "product_type": "domestic_etf",
                        "native_result_grain": "listed_product",
                        "partition_key": "return_1y:KRW",
                        "group_values": [
                            {"field_id": "currency", "value_type": "text", "value": "KRW"}
                        ],
                        "value_type": "decimal",
                        "value": "3.10",
                    }
                ]
            },
            "expected_answer": {"required_concepts": [], "forbidden_concepts": []},
            "review": {
                "reviewer": "test-reviewer",
                "reviewed_at": "2026-08-29",
                "source": "fact-pack-aggregate-observation-regression",
            },
        }
    )
    result = AnswerResult(
        answer=VerifiedAnswer(text=claim.text, claims=(claim,)),
        retrieved_context=pack.model_dump_json(),
        trace=ExecutionTrace(
            correlation_id="fact-pack-aggregate-observation",
            intent=plan.intent,
            product_types=plan.product_types,
            as_of_date=plan.as_of_date,
            result_grain=plan.result_grain,
            top_k_scope=plan.top_k_scope,
            segments=(
                ExecutionTraceSegment(
                    product_type=ProductType.DOMESTIC_ETF,
                    native_result_grain=ResultGrain.LISTED_PRODUCT,
                    partition_key="return_1y:KRW",
                    candidate_counts={"raw": 1, "eligible": 1},
                    returned=1,
                ),
            ),
            candidate_counts={"raw": 1, "eligible": 1, "returned": 1},
            tools=(),
            policy_ids=(),
            validation=TraceValidation.PASSED,
            versions={},
            latency_ms={},
        ),
    )

    observed = _observed(case, plan, result, 0)

    assert len(observed.aggregates) == 1
    assert observed.aggregates[0].value == Decimal("3.10")
    assert observed.aggregates[0].group_values[0].value == "KRW"


def test_serialized_rank_summaries_preserve_compatible_multi_product_order() -> None:
    summaries = (
        _summary(product_types=(ProductType.OVERSEAS_ETF,)),
        _summary(summary_id="summary:rank:1", rank=2),
    )
    payload = json.loads(
        serialize_evidence_context(
            EvidenceBundle(
                direct=(), derived=(), summaries=summaries, material_policy_limitations=()
            )
        )
    )
    plan = _plan(
        intent=Intent.SCREEN_RANK,
        products=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        grain=ResultGrain.LISTED_PRODUCT,
    )

    products = _observed_products(plan, (), payload["summaries"])

    assert tuple(item.product_type for item in products) == (
        ProductType.OVERSEAS_ETF,
        ProductType.DOMESTIC_ETF,
    )
    assert tuple(item.product_id for item in products) == ("SAME", "SAME")


def test_serialized_aggregate_summary_is_typed_and_has_no_product_results() -> None:
    aggregation = AggregationSpec(
        function=AggregationFunction.AVG,
        field="return_1y",
        group_by=("currency",),
    )
    plan = _plan(
        intent=Intent.AGGREGATE,
        products=(ProductType.DOMESTIC_ETF,),
        grain=ResultGrain.LISTED_PRODUCT,
        aggregation=aggregation,
    )
    summary = _summary(
        summary_id="summary:aggregate:0",
        kind=EvidenceSummaryKind.AGGREGATE,
        policy_versions=("return_1y:avg",),
        rank=None,
        tie_count=None,
        product_id=None,
        group_values=(EvidenceSummaryValue(field_id="currency", value="KRW"),),
    )
    payload = json.loads(
        serialize_evidence_context(
            EvidenceBundle(
                direct=(), derived=(), summaries=(summary,), material_policy_limitations=()
            )
        )
    )
    expected = (
        ExpectedAggregate.model_validate(
            {
                "function": "avg",
                "field_id": "return_1y",
                "product_type": "domestic_etf",
                "native_result_grain": "listed_product",
                "partition_key": "return_1y:KRW",
                "group_values": [{"field_id": "currency", "value_type": "text", "value": "KRW"}],
                "value_type": "decimal",
                "value": "3.10",
            }
        ),
    )

    products = _observed_products(
        plan,
        ({"product_type": "domestic_etf", "product_id": "SELECTED"},),
        payload["summaries"],
    )
    aggregates = _observed_aggregates(expected, payload["summaries"])

    assert products == ()
    assert aggregates[0].value == Decimal("3.10")
