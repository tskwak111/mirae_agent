import json
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import ProductType
from finproof.entity import EntityResolver
from finproof.entity.index import EntityIndex
from finproof.planner.rule_fallback import RuleFallbackPlanner
from finproof.planner.service import LocalPlanValidator, PlanningRequest
from finproof.query import FieldRegistry, SemanticValidator
from finproof.registry.loader import RegistryBundle

_D030_STALE_GRAINS = {
    "SEED-POLICY-008": "listed_product",
    "SEED-POLICY-012": "listed_product",
}


def _planner() -> RuleFallbackPlanner:
    registries = RegistryBundle.from_package()
    return RuleFallbackPlanner(
        validator=LocalPlanValidator(
            SemanticValidator(FieldRegistry.from_bundle(registries)),
            entity_resolver=EntityResolver(EntityIndex._from_entries(())),
        )
    )


def _cases() -> tuple[dict[str, Any], ...]:
    path = Path(__file__).with_name("seed_cases.jsonl")
    return tuple(
        cast(dict[str, Any], json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
    )


@pytest.mark.asyncio
async def test_seed_partial_plan_semantics_follow_canonical_d030_contract() -> None:
    planner = _planner()

    for case in _cases():
        expected = cast(dict[str, Any], case["expected_plan"])
        result = await planner.plan(
            PlanningRequest.start(
                question=cast(str, case["question"]),
                request_id=cast(str, case["case_id"]),
                as_of_date=date(2026, 7, 11),
                execution_mode=ExecutionMode.EVALUATION,
                deadline_seconds=1.0,
            )
        )
        plan = result.plan

        assert plan.intent.value == expected["intent"], case["case_id"]
        assert [product.value for product in plan.product_types] == expected["product_types"], case[
            "case_id"
        ]
        assert plan.as_of_date.isoformat() == expected["as_of_date"], case["case_id"]
        case_id = cast(str, case["case_id"])
        if case_id in _D030_STALE_GRAINS:
            # D-030 records these AI-handoff partials as non-canonical. Preserve
            # the mismatch visibly while enforcing the frozen product envelope.
            assert expected["result_grain"] == _D030_STALE_GRAINS[case_id]
            assert plan.result_grain.value == "product", case_id
        else:
            assert plan.result_grain.value == expected["result_grain"], case_id
        assert plan.top_k == expected["top_k"], case["case_id"]
        assert plan.top_k_scope.value == expected["top_k_scope"], case["case_id"]
        assert plan.needs_clarification is expected["needs_clarification"], case["case_id"]

        if "clarification_reason" in expected:
            assert plan.clarification_reason == expected["clarification_reason"], case["case_id"]
        if "metrics" in expected:
            assert list(plan.metrics) == expected["metrics"], case["case_id"]
        if "filters" in expected:
            observed_filters = [
                {
                    "field": clause.field,
                    "operator": clause.operator.value,
                    "value": clause.value,
                }
                for clause in plan.filters
            ]
            assert observed_filters == expected["filters"], case["case_id"]
        if "sort" in expected:
            assert [
                {"field": item.field, "direction": item.direction.value} for item in plan.sort
            ] == expected["sort"], case["case_id"]

        assert all(type(product) is ProductType for product in plan.product_types)
