from datetime import date
from decimal import Decimal

from finproof.domain.query_plan import (
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.evaluation.models import (
    ExpectedValue,
    GoldenCase,
    ObservedCase,
    ObservedSegment,
    ObservedValue,
)
from finproof.evaluation.scoring import (
    LatencySummary,
    score_case,
    score_evidence,
    score_filters,
    score_products,
    score_repeated_stability,
    score_values,
)


def _plan(*, filters: tuple[FilterClause, ...] = ()) -> QueryPlan:
    return QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=filters,
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )


def _case() -> GoldenCase:
    return GoldenCase.model_validate(
        {
            "case_id": "BOND-RANK-001",
            "category": "rank",
            "question": "채권 1개",
            "expected_plan": {
                "intent": "screen_rank",
                "product_types": ["domestic_bond"],
                "as_of_date": "2026-07-11",
                "result_grain": "instrument",
                "filters": [{"field": "buyable_quantity", "operator": "gt", "value": 0}],
                "top_k": 5,
                "top_k_scope": "global",
                "needs_clarification": False,
            },
            "expected_result": {
                "product_ids": ["A", "B"],
                "order_matters": True,
                "values": [
                    {
                        "product_id": "A",
                        "field_id": "buy_yield",
                        "value_type": "decimal",
                        "value": "3.25",
                    }
                ],
                "required_evidence_ids": ["e-A-yield"],
                "assembled_envelope": False,
            },
            "expected_answer": {
                "required_concepts": ["2026-07-11"],
                "forbidden_concepts": ["실시간"],
                "expect_limitation": True,
                "expect_clarification": False,
            },
            "review": {
                "reviewer": "human",
                "reviewed_at": "2026-08-20",
                "source": "reference-engine",
            },
        }
    )


def test_product_set_f1_and_order_accuracy_are_separate() -> None:
    score = score_products(expected=["A", "B", "C"], observed=["B", "A", "C"])

    assert score.set_f1 == 1.0
    assert score.order_accuracy < 1.0
    assert (score.set_numerator, score.set_denominator) == (6, 6)


def test_decimal_and_date_values_are_exact_unless_display_tolerance_is_declared() -> None:
    expected = (
        ExpectedValue.model_validate(
            {
                "product_id": "A",
                "field_id": "yield",
                "value_type": "decimal",
                "value": "3.250",
            }
        ),
        ExpectedValue.model_validate(
            {
                "product_id": "A",
                "field_id": "as_of",
                "value_type": "date",
                "value": "2026-07-11",
            }
        ),
    )
    observed = (
        expected[0].model_copy(update={"value": Decimal("3.251")}),
        expected[1].model_copy(update={"value": date(2026, 7, 12)}),
    )

    assert score_values(expected, observed).numerator == 0

    tolerant = expected[0].model_copy(update={"display_tolerance": Decimal("0.01")})
    assert score_values((tolerant,), (observed[0],)).numerator == 1


def test_filter_slot_f1_scores_literal_operator_and_value() -> None:
    expected = (
        FilterClause(field="buyable_quantity", operator=FilterOperator.GT, value=0),
        FilterClause(field="credit_rating", operator=FilterOperator.GTE, value="AA-"),
    )
    observed = (
        expected[0],
        FilterClause(field="credit_rating", operator=FilterOperator.GTE, value="A"),
    )

    score = score_filters(expected, observed)
    assert score.numerator == 2
    assert score.denominator == 4
    assert score.value == 0.5


def test_evidence_stability_and_latency_keep_explicit_denominators() -> None:
    evidence = score_evidence(("e1", "e2"), ("e2", "other"))
    stability = score_repeated_stability(("same", "same", "different"))
    latency = LatencySummary.from_milliseconds((10, 40, 20, 30))

    assert (evidence.numerator, evidence.denominator) == (1, 2)
    assert (stability.numerator, stability.denominator) == (1, 2)
    assert latency.count == 4
    assert latency.mean_ms == 25.0
    assert latency.p95_ms == 40


def test_score_case_keeps_contract_dimensions_and_failures_separate() -> None:
    expected_filter = FilterClause(field="buyable_quantity", operator=FilterOperator.GT, value=0)
    case = _case()
    observed = ObservedCase(
        plan=_plan(filters=(expected_filter,)),
        product_ids=("B", "A"),
        values=(
            ObservedValue.model_validate(
                {
                    "product_id": "A",
                    "field_id": "buy_yield",
                    "value_type": "decimal",
                    "value": "3.25",
                }
            ),
        ),
        answer_text="2026-07-11 기준 제공 데이터이며 실시간 가용성은 확인할 수 없습니다.",
        evidence_ids=("e-A-yield",),
        limitation_present=True,
        clarification_present=False,
        repeat_signatures=("stable", "stable"),
        assembled_envelope=False,
        latency_ms=(25, 20),
    )

    score = score_case(case, observed)

    assert score.product_set.value == 1.0
    assert score.product_order.value == 0.0
    assert score.filter_slots.value == 1.0
    assert score.numeric_values.value == 1.0
    assert score.evidence_coverage.value == 1.0
    assert score.top_k_scope.value == 1.0
    assert score.segment_assignment.denominator == 0
    assert score.assembled_envelope.value == 1.0
    assert any("forbidden concept" in failure for failure in score.failures)


def test_missing_observed_plan_is_a_zero_score_not_an_invalid_ratio() -> None:
    score = score_case(_case(), ObservedCase())

    assert score.plan_fields.numerator == 0
    assert score.plan_fields.denominator >= 4
    assert "observed plan is missing" in score.failures


def test_segment_assignment_and_compatibility_partitions_are_scored_separately() -> None:
    case = GoldenCase.model_validate(
        {
            "case_id": "CROSS-001",
            "category": "cross_product",
            "question": "채권과 펀드를 각각 보여줘",
            "expected_plan": {
                "intent": "screen",
                "product_types": ["domestic_bond", "public_fund"],
                "as_of_date": "2026-07-11",
                "result_grain": "product",
                "top_k_scope": "per_product_type",
                "native_segments": [
                    {"product_type": "domestic_bond", "native_result_grain": "instrument"},
                    {"product_type": "public_fund", "native_result_grain": "fund_item"},
                ],
            },
            "expected_result": {"required_compatibility_partitions": ["bond:KRW", "fund:KRW"]},
            "expected_answer": {"required_concepts": [], "forbidden_concepts": []},
            "review": {
                "reviewer": "human",
                "reviewed_at": "2026-08-20",
                "source": "reference-engine",
            },
        }
    )
    observed = ObservedCase(
        segments=(
            ObservedSegment(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                compatibility_partition="wrong-bond-partition",
            ),
            ObservedSegment(
                product_type=ProductType.PUBLIC_FUND,
                native_result_grain=ResultGrain.FUND_ITEM,
                compatibility_partition="wrong-fund-partition",
            ),
        ),
        compatibility_partitions=("wrong-bond-partition", "wrong-fund-partition"),
    )

    score = score_case(case, observed)
    assert score.segment_assignment.value == 1.0
    assert score.compatibility_partitions.value == 0.0
