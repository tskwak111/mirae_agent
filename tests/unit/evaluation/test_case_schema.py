import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from finproof.domain.query_plan import FilterClause, FilterOperator
from finproof.evaluation.loader import load_golden_cases, suite_checksum
from finproof.evaluation.models import GoldenCase


def _case(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "case_id": "BOND-RANK-001",
        "category": "rank",
        "question": "2026-07-11 기준 AA- 이상 매수 가능 채권 5개",
        "expected_plan": {
            "intent": "screen_rank",
            "product_types": ["domestic_bond"],
            "as_of_date": "2026-07-11",
            "result_grain": "instrument",
            "top_k_scope": "global",
        },
        "expected_result": {"product_ids": ["B1"], "order_matters": True},
        "expected_answer": {
            "required_concepts": ["2026-07-11"],
            "forbidden_concepts": ["실시간"],
        },
        "review": {
            "reviewer": "human",
            "reviewed_at": "2026-08-20",
            "source": "reference-engine",
        },
    }
    value.update(updates)
    return value


def test_golden_case_requires_review_metadata_and_expected_semantics() -> None:
    case = GoldenCase.model_validate(_case())

    assert case.review.reviewer == "human"
    assert case.expected_answer.required_concepts == ("2026-07-11",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question", "   "),
        ("category", "unknown"),
        (
            "expected_plan",
            {
                "intent": "screen_rank",
                "product_types": ["domestic_bond"],
                "as_of_date": "2026-07-11",
                "result_grain": "instrument",
                "top_k_scope": "everywhere",
            },
        ),
    ],
)
def test_golden_case_rejects_unsafe_case_shape(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(_case(**{field: value}))


def test_golden_case_rejects_missing_review_metadata() -> None:
    value = _case()
    value["review"] = {"reviewer": "human", "reviewed_at": "2026-08-20"}

    with pytest.raises(ValidationError):
        GoldenCase.model_validate(value)


def test_expected_result_rejects_impossible_ordering() -> None:
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(_case(expected_result={"product_ids": [], "order_matters": True}))


def test_heterogeneous_plan_requires_product_envelope_and_native_segments() -> None:
    plan: dict[str, object] = {
        "intent": "screen_rank",
        "product_types": ["domestic_bond", "public_fund"],
        "as_of_date": "2026-07-11",
        "result_grain": "instrument",
        "top_k_scope": "per_product_type",
    }

    with pytest.raises(ValidationError):
        GoldenCase.model_validate(_case(expected_plan=plan))

    plan["result_grain"] = "product"
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(_case(expected_plan=plan))

    plan["native_segments"] = [
        {
            "product_type": "domestic_bond",
            "native_result_grain": "instrument",
        },
        {
            "product_type": "public_fund",
            "native_result_grain": "fund_item",
        },
    ]
    case = GoldenCase.model_validate(_case(expected_plan=plan))
    assert len(case.expected_plan.native_segments) == 2


def test_expected_plan_accepts_typed_filters_and_requires_aggregate_semantics() -> None:
    plan: dict[str, object] = {
        "intent": "aggregate",
        "product_types": ["domestic_bond"],
        "as_of_date": "2026-07-11",
        "result_grain": "instrument",
        "top_k_scope": "global",
        "filters": (FilterClause(field="buyable_quantity", operator=FilterOperator.GT, value=0),),
    }
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(_case(expected_plan=plan))

    plan["aggregation"] = {"function": "count", "field": None, "group_by": []}
    case = GoldenCase.model_validate(_case(expected_plan=plan))
    assert case.expected_plan.aggregation is not None


def test_terminal_expected_plan_requires_explicit_clarification_semantics() -> None:
    plan: dict[str, object] = {
        "intent": "clarify",
        "product_types": [],
        "as_of_date": "2026-07-11",
        "result_grain": "product",
        "top_k_scope": "global",
    }
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(_case(expected_plan=plan))

    plan.update(
        needs_clarification=True,
        clarification_reason="return period is unresolved",
    )
    case = GoldenCase.model_validate(_case(expected_plan=plan))
    assert case.expected_plan.clarification_reason == "return period is unresolved"


def test_loader_rejects_duplicate_case_ids_across_files(tmp_path: Path) -> None:
    first = tmp_path / "rank-a.jsonl"
    second = tmp_path / "rank-b.jsonl"
    payload = json.dumps(_case(), ensure_ascii=False)
    first.write_text(payload + "\n", encoding="utf-8")
    second.write_text(payload + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate golden case id"):
        load_golden_cases((first, second))


def test_loader_requires_one_category_per_jsonl_and_stable_checksum(tmp_path: Path) -> None:
    path = tmp_path / "rank.jsonl"
    second = _case(case_id="BOND-RANK-002")
    path.write_text(
        "\n".join(
            [
                json.dumps(second, ensure_ascii=False),
                json.dumps(_case(), ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cases = load_golden_cases((path,))
    assert tuple(case.case_id for case in cases) == ("BOND-RANK-002", "BOND-RANK-001")
    assert suite_checksum(cases) == suite_checksum(tuple(reversed(cases)))

    mixed = tmp_path / "mixed.jsonl"
    mixed.write_text(
        json.dumps(_case(category="lookup"), ensure_ascii=False)
        + "\n"
        + json.dumps(_case(case_id="BOND-RANK-003"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="one category"):
        load_golden_cases((mixed,))
