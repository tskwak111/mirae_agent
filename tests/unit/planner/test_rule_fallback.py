from datetime import date
from decimal import Decimal

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import (
    FilterOperator,
    Intent,
    ProductType,
    SortDirection,
    TopKScope,
)
from finproof.entity import EntityResolver
from finproof.entity.index import EntityIndex, _IndexedProduct
from finproof.planner.rule_fallback import RuleFallbackPlanner
from finproof.planner.service import LocalPlanValidator, PlanningRequest
from finproof.query import FieldRegistry, SemanticValidator
from finproof.registry.loader import RegistryBundle


def _planner() -> RuleFallbackPlanner:
    from finproof.domain.query_plan import EntityIdentifierType

    index = EntityIndex._from_entries(
        (
            _IndexedProduct(
                product_id="O-SPY",
                product_type=ProductType.OVERSEAS_ETF,
                name="SPDR S&P 500 ETF Trust",
                identifiers=(
                    (EntityIdentifierType.PRODUCT_ID, "o-spy"),
                    (EntityIdentifierType.TICKER, "spy"),
                ),
                names=("spdr s&p 500 etf trust",),
            ),
        )
    )
    registries = RegistryBundle.from_package()
    validator = LocalPlanValidator(
        SemanticValidator(FieldRegistry.from_bundle(registries)),
        entity_resolver=EntityResolver(index),
    )
    return RuleFallbackPlanner(validator=validator)


def _request(question: str) -> PlanningRequest:
    return PlanningRequest.start(
        question=question,
        request_id="rule-test",
        as_of_date=date(2026, 7, 11),
        execution_mode=ExecutionMode.EVALUATION,
        deadline_seconds=1.0,
    )


@pytest.mark.asyncio
async def test_rule_fallback_resolves_exact_ticker_lookup() -> None:
    result = await _planner().plan(_request("SPY 총보수 알려줘"))

    assert result.plan.intent is Intent.LOOKUP
    assert result.plan.product_types == (ProductType.OVERSEAS_ETF,)
    assert result.plan.metrics == ("total_fee",)
    assert result.validated_plan.resolutions is not None


@pytest.mark.asyncio
async def test_rule_fallback_parses_simple_numeric_filter() -> None:
    result = await _planner().plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"))

    assert result.plan.intent is Intent.SCREEN
    assert result.plan.product_types == (ProductType.OVERSEAS_ETF,)
    assert result.plan.filters[0].field == "total_fee"
    assert result.plan.filters[0].operator is FilterOperator.LTE
    assert result.plan.filters[0].value == Decimal("0.2")
    assert result.plan.top_k == 5


@pytest.mark.asyncio
async def test_rule_fallback_plain_etf_top_k_excludes_etn() -> None:
    result = await _planner().plan(_request("국내 ETF 중 추적오차가 낮은 5개"))

    assert result.plan.intent is Intent.SCREEN_RANK
    assert result.plan.product_types == (ProductType.DOMESTIC_ETF,)
    assert ProductType.DOMESTIC_ETN not in result.plan.product_types
    assert result.plan.metrics == ("tracking_error",)
    assert result.plan.sort[0].direction is SortDirection.ASC


@pytest.mark.asyncio
async def test_rule_fallback_current_uses_frozen_snapshot_assumption() -> None:
    result = await _planner().plan(_request("현재 국내 ETF만 보여줘"))

    assert result.plan.as_of_date == date(2026, 7, 11)
    assert result.safe_assumptions == ("snapshot_date=2026-07-11",)


@pytest.mark.asyncio
async def test_rule_fallback_ambiguous_return_period_fails_closed() -> None:
    result = await _planner().plan(_request("수익률 높은 상품 알려줘"))

    assert result.plan.intent is Intent.CLARIFY
    assert result.plan.needs_clarification is True
    assert result.plan.filters == ()
    assert result.plan.metrics == ()
    assert result.plan.sort == ()
    assert "period" in result.plan.clarification_reason


@pytest.mark.asyncio
async def test_rule_fallback_unknown_field_never_becomes_executable() -> None:
    result = await _planner().plan(_request("국내 ETF 중 샤프지수가 높은 5개"))

    assert result.plan.intent is Intent.CLARIFY
    assert result.plan.filters == ()
    assert result.plan.metrics == ()
    assert result.plan.sort == ()
    assert "field" in result.plan.clarification_reason


@pytest.mark.parametrize(
    "question",
    [
        "무조건 사야 할 ETF 추천해줘",
        "미래 수익률이 가장 높을 ETF를 예측해줘",
        "무조건 추천해줘",
    ],
)
@pytest.mark.asyncio
async def test_rule_fallback_advice_and_forecast_are_unsupported(question: str) -> None:
    result = await _planner().plan(_request(question))

    assert result.plan.intent is Intent.UNSUPPORTED
    assert result.plan.needs_clarification is False
    assert result.plan.top_k_scope is TopKScope.GLOBAL
    assert result.plan.filters == ()
    assert result.plan.metrics == ()
    assert result.plan.sort == ()
