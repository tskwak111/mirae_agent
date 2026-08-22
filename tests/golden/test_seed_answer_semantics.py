"""Semantic-only checks for the unreviewed AI handoff seeds."""

import json
from pathlib import Path


def test_ai_handoff_seeds_assert_semantics_without_parsing_partial_expected_plans_as_queryplan() -> (  # noqa: E501
    None
):
    path = Path(__file__).with_name("seed_cases.jsonl")
    cases = tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())

    assert len(cases) == 13
    assert all(case["review"]["reviewer"] == "AI-handoff-seed" for case in cases)
    assert all(case["expected_answer"]["required_semantics"] for case in cases)
    assert all(case["expected_answer"]["forbidden_semantics"] for case in cases)
    canonical_fields = {
        "intent",
        "product_types",
        "entities",
        "as_of_date",
        "result_grain",
        "filters",
        "metrics",
        "sort",
        "aggregation",
        "top_k",
        "top_k_scope",
        "needs_clarification",
        "clarification_reason",
    }
    assert any(not canonical_fields <= set(case["expected_plan"]) for case in cases), (
        "AI handoff expected_plan objects must remain semantic partials"
    )
