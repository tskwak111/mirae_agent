from datetime import date
from decimal import Decimal

from finproof.domain.query_plan import (
    FilterClause,
    FilterOperator,
    Intent,
    MetricTarget,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.evaluation.latency import LatencySummary
from finproof.evaluation.models import (
    ExpectedValue,
    GoldenCase,
    ObservedCase,
    ObservedSegment,
    ObservedValue,
    ProductIdentity,
)
from finproof.evaluation.scoring import (
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


def _product(
    product_id: str,
    *,
    product_type: ProductType = ProductType.DOMESTIC_BOND,
    native_result_grain: ResultGrain = ResultGrain.INSTRUMENT,
) -> ProductIdentity:
    return ProductIdentity(
        product_type=product_type,
        native_result_grain=native_result_grain,
        product_id=product_id,
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
                "products": [
                    {
                        "product_type": "domestic_bond",
                        "native_result_grain": "instrument",
                        "product_id": product_id,
                    }
                    for product_id in ("A", "B")
                ],
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
    score = score_products(
        expected=[_product("A"), _product("B"), _product("C")],
        observed=[_product("B"), _product("A"), _product("C")],
    )

    assert score.set_f1 == 1.0
    assert score.order_accuracy < 1.0
    assert (score.set_numerator, score.set_denominator) == (6, 6)


def test_product_scoring_distinguishes_overlapping_ids_by_typed_identity() -> None:
    domestic = _product(
        "OVERLAP",
        product_type=ProductType.DOMESTIC_ETF,
        native_result_grain=ResultGrain.LISTED_PRODUCT,
    )
    overseas = _product(
        "OVERLAP",
        product_type=ProductType.OVERSEAS_ETF,
        native_result_grain=ResultGrain.LISTED_PRODUCT,
    )

    score = score_products(expected=(domestic, overseas), observed=(domestic,))

    assert (score.set_numerator, score.set_denominator) == (2, 3)


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


def test_typed_partitioned_aggregates_are_scored_independently_and_exactly() -> None:
    from finproof.evaluation.models import ExpectedAggregate, ObservedAggregate
    from finproof.evaluation.scoring import score_aggregates

    base = {
        "function": "avg",
        "field_id": "return_1y",
        "product_type": "domestic_etf",
        "native_result_grain": "listed_product",
        "group_values": [{"field_id": "currency", "value_type": "text", "value": "KRW"}],
        "value_type": "decimal",
    }
    expected = (
        ExpectedAggregate.model_validate({**base, "partition_key": "KRW:A", "value": "3.10"}),
        ExpectedAggregate.model_validate({**base, "partition_key": "KRW:B", "value": "4.20"}),
    )
    observed = (
        ObservedAggregate.model_validate({**base, "partition_key": "KRW:A", "value": "3.10"}),
        ObservedAggregate.model_validate({**base, "partition_key": "KRW:B", "value": "4.21"}),
    )

    score = score_aggregates(expected, observed)

    assert (score.numerator, score.denominator) == (1, 2)
    assert score.failures == ("aggregate value differs: KRW:B",)


def test_aggregate_scoring_rejects_duplicate_observations_without_last_wins() -> None:
    from finproof.evaluation.models import ExpectedAggregate, ObservedAggregate
    from finproof.evaluation.scoring import score_aggregates

    value: dict[str, object] = {
        "function": "count",
        "field_id": None,
        "product_type": "domestic_bond",
        "native_result_grain": "instrument",
        "partition_key": "bond:KRW",
        "group_values": [],
        "value_type": "integer",
        "value": 2,
    }
    expected = ExpectedAggregate.model_validate(value)
    observed = ObservedAggregate.model_validate(value)

    score = score_aggregates(
        (expected,),
        (observed, observed.model_copy(update={"value": 3})),
    )

    assert (score.numerator, score.denominator) == (0, 2)
    assert score.failures == ("duplicate aggregate observation: bond:KRW",)


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
        products=(_product("B"), _product("A")),
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


def test_typed_product_diversity_does_not_manufacture_an_observed_envelope() -> None:
    case = _case().model_copy(
        update={
            "expected_result": _case().expected_result.model_copy(
                update={"assembled_envelope": True}
            )
        }
    )
    observed = ObservedCase(
        products=(
            _product("BOND"),
            _product(
                "FUND",
                product_type=ProductType.PUBLIC_FUND,
                native_result_grain=ResultGrain.FUND_ITEM,
            ),
        )
    )

    score = score_case(case, observed)

    assert score.assembled_envelope.value == 0.0
    assert score.assembled_envelope.failures == ("assembled envelope differs",)


def test_missing_observed_plan_is_a_zero_score_not_an_invalid_ratio() -> None:
    score = score_case(_case(), ObservedCase())

    assert score.plan_fields.numerator == 0
    assert score.plan_fields.denominator >= 4
    assert "observed plan is missing" in score.failures


def test_plan_scoring_detects_different_metric_target_routing() -> None:
    case = GoldenCase.model_validate(
        {
            "case_id": "CROSS-TARGET-001",
            "category": "cross_product",
            "question": "ETF는 보수, 펀드는 수익률로 비교",
            "expected_plan": {
                "intent": "screen_rank",
                "product_types": ["domestic_etf", "public_fund"],
                "as_of_date": "2026-08-24",
                "result_grain": "product",
                "metrics": ["total_fee", "return_1y"],
                "metric_targets": [
                    {"product_type": "domestic_etf", "metrics": ["total_fee"]},
                    {"product_type": "public_fund", "metrics": ["return_1y"]},
                ],
                "top_k_scope": "per_product_type",
                "native_segments": [
                    {
                        "product_type": "domestic_etf",
                        "native_result_grain": "listed_product",
                    },
                    {
                        "product_type": "public_fund",
                        "native_result_grain": "fund_item",
                    },
                ],
            },
            "expected_result": {"assembled_envelope": True},
            "expected_answer": {"required_concepts": [], "forbidden_concepts": []},
            "review": {
                "reviewer": "human",
                "reviewed_at": "2026-08-29",
                "source": "reference-engine",
            },
        }
    )
    observed_plan = QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=(ProductType.DOMESTIC_ETF, ProductType.PUBLIC_FUND),
        entities=(),
        as_of_date=date(2026, 8, 24),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=("total_fee", "return_1y"),
        metric_targets=(
            MetricTarget(
                product_type=ProductType.DOMESTIC_ETF,
                metrics=("total_fee", "return_1y"),
            ),
            MetricTarget(
                product_type=ProductType.PUBLIC_FUND,
                metrics=("return_1y",),
            ),
        ),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )

    score = score_case(case, ObservedCase(plan=observed_plan))

    assert score.plan_fields.value < 1
    assert "metric_targets differs" in score.failures


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
