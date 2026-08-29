import json
from enum import StrEnum

import pytest
from pydantic import BaseModel, ValidationError


def test_phase2_domain_contract_skeleton_exposes_exact_public_types() -> None:
    """The Phase 2 modules expose the closed public contract types."""
    from finproof.domain.answers import (
        AnswerClaim,
        AnswerDraft,
        AnswerRequest,
        AnswerResult,
        VerifiedAnswer,
    )
    from finproof.domain.evidence import DerivedEvidence, DirectEvidence, EvidenceSummary
    from finproof.domain.execution import (
        ComparisonPartition,
        ExecutionBundle,
        ExecutionSegment,
        ExecutionTrace,
        ValidatedQueryPlan,
    )
    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        EntityMention,
        FilterClause,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )

    enum_types = (
        AggregationFunction,
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        TopKScope,
    )
    model_types = (
        AggregationSpec,
        EntityMention,
        FilterClause,
        QueryPlan,
        SortSpec,
        DirectEvidence,
        DerivedEvidence,
        EvidenceSummary,
        ComparisonPartition,
        ExecutionBundle,
        ExecutionSegment,
        ExecutionTrace,
        ValidatedQueryPlan,
        AnswerClaim,
        AnswerDraft,
        AnswerRequest,
        AnswerResult,
        VerifiedAnswer,
    )

    assert all(issubclass(value, StrEnum) for value in enum_types)
    assert all(issubclass(value, BaseModel) for value in model_types)


def test_query_plan_accepts_one_complete_nonaggregate_plan_and_rejects_unknown_fields() -> None:
    """A canonical JSON plan is complete and closed to undeclared members."""
    from finproof.domain.query_plan import Intent, ProductType, QueryPlan, ResultGrain

    payload: dict[str, object] = {
        "intent": "screen",
        "product_types": ["domestic_bond"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "instrument",
        "filters": [],
        "metrics": ["buy_yield"],
        "sort": [],
        "aggregation": None,
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }

    plan = QueryPlan.model_validate_json(json.dumps(payload))

    assert plan.intent is Intent.SCREEN
    assert plan.product_types == (ProductType.DOMESTIC_BOND,)
    assert plan.result_grain is ResultGrain.INSTRUMENT
    assert plan.metrics == ("buy_yield",)

    with pytest.raises(ValidationError):
        QueryPlan.model_validate_json(json.dumps(payload | {"sql": "SELECT 1"}))


def test_query_plan_accepts_only_explicit_complete_ordered_metric_targets() -> None:
    """Product-specific metric routing is explicit, complete, and order preserving."""
    from finproof.domain.query_plan import ProductType, QueryPlan

    metric_targets: list[dict[str, object]] = [
        {"product_type": "domestic_bond", "metrics": ["buy_yield"]},
        {"product_type": "domestic_etf", "metrics": ["total_fee"]},
        {"product_type": "public_fund", "metrics": ["return_1y"]},
    ]
    payload: dict[str, object] = {
        "intent": "screen_rank",
        "product_types": ["domestic_bond", "domestic_etf", "public_fund"],
        "entities": [],
        "as_of_date": "2026-08-24",
        "result_grain": "product",
        "filters": [],
        "metrics": ["buy_yield", "total_fee", "return_1y"],
        "metric_targets": metric_targets,
        "sort": [],
        "aggregation": None,
        "top_k": 3,
        "top_k_scope": "per_product_type",
        "needs_clarification": False,
        "clarification_reason": "",
    }

    plan = QueryPlan.model_validate_json(json.dumps(payload))

    assert tuple(target.product_type for target in plan.metric_targets) == (
        ProductType.DOMESTIC_BOND,
        ProductType.DOMESTIC_ETF,
        ProductType.PUBLIC_FUND,
    )
    assert tuple(target.metrics for target in plan.metric_targets) == (
        ("buy_yield",),
        ("total_fee",),
        ("return_1y",),
    )

    invalid = (
        payload | {"intent": "screen"},
        payload | {"top_k_scope": "global"},
        payload | {"metric_targets": metric_targets[1:]},
        payload
        | {
            "metric_targets": [
                {"product_type": "domestic_bond", "metrics": ["buy_yield"]},
                {"product_type": "domestic_etf", "metrics": ["total_fee"]},
                {"product_type": "public_fund", "metrics": ["return_1y", "return_1y"]},
            ]
        },
    )
    for case in invalid:
        with pytest.raises(ValidationError):
            QueryPlan.model_validate_json(json.dumps(case))


@pytest.mark.parametrize(
    ("operator", "value"),
    [
        pytest.param("eq", "AA-", id="scalar"),
        pytest.param("in", ["AA-", "A+"], id="set"),
        pytest.param("between", [1, 2], id="range"),
        pytest.param("is_missing", ..., id="missing"),
    ],
)
def test_filter_operator_variants_require_or_forbid_exact_value_shapes(
    operator: str,
    value: object,
) -> None:
    """Each operator accepts only its closed scalar, tuple, range, or absent shape."""
    from finproof.domain.query_plan import FilterClause

    payload: dict[str, object] = {"field": "credit_rating", "operator": operator}
    if value is not ...:
        payload["value"] = value
    assert FilterClause.model_validate_json(json.dumps(payload)).operator == operator

    invalid = (
        {"field": "x", "operator": "eq"},
        {"field": "x", "operator": "eq", "value": [1]},
        {"field": "x", "operator": "in", "value": 1},
        {"field": "x", "operator": "in", "value": []},
        {"field": "x", "operator": "between", "value": [1]},
        {"field": "x", "operator": "between", "value": [1, 2, 3]},
        {"field": "x", "operator": "is_missing", "value": None},
        {"field": "x", "operator": "is_not_missing", "value": "forbidden"},
    )
    for case in invalid:
        with pytest.raises(ValidationError):
            FilterClause.model_validate_json(json.dumps(case))


def test_query_plan_aggregation_cross_field_contract_is_exact() -> None:
    """Aggregate intent, function target, and grouping shape agree exactly."""
    from finproof.domain.query_plan import AggregationFunction, QueryPlan

    base = {
        "intent": "aggregate",
        "product_types": ["domestic_etf"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "listed_product",
        "filters": [],
        "metrics": [],
        "sort": [],
        "aggregation": {"function": "count", "field": None, "group_by": []},
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }
    count_plan = QueryPlan.model_validate_json(json.dumps(base))
    value_plan = QueryPlan.model_validate_json(
        json.dumps(
            base
            | {
                "metrics": ["total_fee"],
                "aggregation": {
                    "function": "avg",
                    "field": "total_fee",
                    "group_by": ["currency"],
                },
            }
        )
    )
    assert count_plan.aggregation is not None
    assert count_plan.aggregation.function is AggregationFunction.COUNT
    assert value_plan.aggregation is not None
    assert value_plan.aggregation.field == "total_fee"

    invalid = (
        base | {"aggregation": None},
        base | {"intent": "screen"},
        base | {"aggregation": {"function": "count", "field": "id", "group_by": []}},
        base | {"aggregation": {"function": "sum", "field": None, "group_by": []}},
        base
        | {
            "aggregation": {
                "function": "count",
                "field": None,
                "group_by": ["currency", "market", "state"],
            }
        },
        base
        | {
            "aggregation": {
                "function": "count",
                "field": None,
                "group_by": ["currency", "currency"],
            }
        },
    )
    for case in invalid:
        with pytest.raises(ValidationError):
            QueryPlan.model_validate_json(json.dumps(case))


def test_clarify_unsupported_and_product_envelope_cross_field_contracts() -> None:
    """Non-executable intents and heterogeneous envelopes have closed shapes."""
    from finproof.domain.query_plan import QueryPlan, ResultGrain

    base = {
        "intent": "screen",
        "product_types": ["domestic_bond"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "instrument",
        "filters": [],
        "metrics": [],
        "sort": [],
        "aggregation": None,
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }
    clarify = base | {
        "intent": "clarify",
        "product_types": [],
        "result_grain": "product",
        "needs_clarification": True,
        "clarification_reason": "기간을 알려주세요.",
    }
    unsupported = clarify | {
        "intent": "unsupported",
        "needs_clarification": False,
        "clarification_reason": "개인화 추천은 지원하지 않습니다.",
    }
    heterogeneous = base | {
        "product_types": ["domestic_bond", "public_fund"],
        "result_grain": "product",
    }
    assert QueryPlan.model_validate_json(json.dumps(clarify)).needs_clarification
    assert not QueryPlan.model_validate_json(json.dumps(unsupported)).needs_clarification
    assert (
        QueryPlan.model_validate_json(json.dumps(heterogeneous)).result_grain is ResultGrain.PRODUCT
    )

    invalid = (
        clarify | {"clarification_reason": ""},
        clarify | {"needs_clarification": False},
        clarify | {"filters": [{"field": "x", "operator": "eq", "value": 1}]},
        unsupported | {"clarification_reason": ""},
        unsupported | {"needs_clarification": True},
        unsupported | {"metrics": ["buy_yield"]},
        base | {"product_types": []},
        base | {"needs_clarification": True, "clarification_reason": "why"},
        heterogeneous | {"result_grain": "instrument"},
        base | {"result_grain": "product"},
    )
    for case in invalid:
        with pytest.raises(ValidationError):
            QueryPlan.model_validate_json(json.dumps(case))
