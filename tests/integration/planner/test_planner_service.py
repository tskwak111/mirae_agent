import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import date
from time import monotonic
from typing import Any

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import AggregationFunction, Intent, ProductType
from finproof.entity import EntityResolver
from finproof.entity.index import EntityIndex
from finproof.planner.hcx_client import (
    HcxMalformedResponseError,
    HcxNoContentError,
    HcxRateLimitError,
    HcxTimeoutKind,
    HcxTransportError,
)
from finproof.planner.json_planner import StrictJsonPlanner
from finproof.planner.models import HcxRequest, HcxResponse, HcxUsage
from finproof.planner.provider_schema import parse_provider_plan
from finproof.planner.rate_limits import HcxRateLimitSnapshot
from finproof.planner.rule_fallback import RuleFallbackPlanner
from finproof.planner.service import (
    LocalPlanValidator,
    PlannerService,
    PlanningRequest,
)
from finproof.planner.structured_planner import StructuredOutputPlanner
from finproof.query import FieldRegistry, SemanticValidator
from finproof.registry.loader import RegistryBundle


class ScriptedHcx:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.requests: list[HcxRequest] = []

    async def generate(self, request: HcxRequest, request_id: str) -> HcxResponse:
        del request_id
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return HcxResponse(
            status_code="20000",
            status_message="OK",
            message_content=response,
            usage=HcxUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            rate_limits=HcxRateLimitSnapshot(),
        )


def _provider_plan(**updates: object) -> dict[str, Any]:
    value: dict[str, Any] = {
        "intent": "screen",
        "product_types": ["overseas_etf"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "listed_product",
        "filters": [],
        "metrics": ["total_fee"],
        "sort": [],
        "aggregation": {"function": "none", "field": "", "group_by": []},
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }
    value.update(updates)
    return value


def _request(question: str, *, seconds: float = 1.0) -> PlanningRequest:
    return PlanningRequest.start(
        question=question,
        request_id="planner-test",
        as_of_date=date(2026, 7, 11),
        execution_mode=ExecutionMode.EVALUATION,
        deadline_seconds=seconds,
    )


def _validator() -> LocalPlanValidator:
    registries = RegistryBundle.from_package()
    return LocalPlanValidator(
        SemanticValidator(FieldRegistry.from_bundle(registries)),
        entity_resolver=EntityResolver(EntityIndex._from_entries(())),
    )


def _planners(
    client: ScriptedHcx,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> tuple[StrictJsonPlanner, RuleFallbackPlanner, PlannerService]:
    registries = RegistryBundle.from_package()
    validator = _validator()
    strict = StrictJsonPlanner(
        generator=client,
        validator=validator,
        registries=registries,
        model_name="HCX-007",
    )
    fallback = RuleFallbackPlanner(validator=validator)
    service = (
        PlannerService(strict_json_planner=strict, rule_fallback=fallback)
        if sleep is None
        else PlannerService(
            strict_json_planner=strict,
            rule_fallback=fallback,
            sleep=sleep,
        )
    )
    return strict, fallback, service


@pytest.mark.asyncio
async def test_valid_structured_output_is_locally_validated_once() -> None:
    payload = _provider_plan(filters=[{"field": "total_fee", "operator": "lte", "value": 0.2}])
    client = ScriptedHcx([json.dumps(payload)])
    planner = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    result = await planner.plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"))

    assert result.fallback_path == ("structured",)
    assert result.validated_plan.plan is result.plan
    assert result.validated_plan.plan.top_k == 5
    assert client.requests[0].response_schema_json is not None


def test_provider_none_sentinel_becomes_canonical_none() -> None:
    plan = parse_provider_plan(json.dumps(_provider_plan()))
    assert plan.aggregation is None


def test_provider_count_aggregation_becomes_canonical_spec() -> None:
    plan = parse_provider_plan(
        json.dumps(
            _provider_plan(
                intent="aggregate",
                product_types=["public_fund"],
                result_grain="fund_item",
                metrics=["risk_grade"],
                aggregation={"function": "count", "field": "", "group_by": []},
            )
        )
    )

    assert plan.aggregation is not None
    assert plan.aggregation.function is AggregationFunction.COUNT
    assert plan.aggregation.field is None


@pytest.mark.parametrize(
    "aggregation",
    [
        {"function": "none", "field": "total_fee", "group_by": []},
        {"function": "none", "field": "", "group_by": ["currency"]},
        {"function": "count", "field": "total_fee", "group_by": []},
        {"function": "avg", "field": "", "group_by": []},
    ],
)
def test_invalid_provider_aggregation_shape_fails_before_queryplan(
    aggregation: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="aggregation"):
        parse_provider_plan(json.dumps(_provider_plan(aggregation=aggregation)))


def test_phase3_service_has_no_structured_planner_injection_path() -> None:
    client = ScriptedHcx([])
    _, fallback, _ = _planners(client)
    structured = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    with pytest.raises(TypeError, match="strict JSON"):
        PlannerService(
            strict_json_planner=structured,  # type: ignore[arg-type]
            rule_fallback=fallback,
        )


@pytest.mark.asyncio
async def test_malformed_json_gets_one_repair_then_rule_fallback() -> None:
    semantically_invalid = _provider_plan(result_grain="fund_item")
    client = ScriptedHcx(["not-json", json.dumps(semantically_invalid)])
    _, _, service = _planners(client)

    result = await service.plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"))

    assert result.attempts.hcx_calls == 2
    assert result.attempts.repair_calls == 1
    assert result.fallback_path == ("strict_json", "repair", "rule_fallback")
    assert result.validated_plan.plan.intent is Intent.SCREEN
    assert all(request.response_schema_json is None for request in client.requests)


@pytest.mark.asyncio
async def test_semantic_failure_skips_repair_and_never_executes() -> None:
    client = ScriptedHcx([json.dumps(_provider_plan(result_grain="fund_item"))])
    _, _, service = _planners(client)

    result = await service.plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"))

    assert result.attempts.hcx_calls == 1
    assert result.attempts.repair_calls == 0
    assert result.fallback_path == ("strict_json", "rule_fallback")
    assert result.plan.product_types == (ProductType.OVERSEAS_ETF,)


@pytest.mark.parametrize(
    "provider_error",
    [
        HcxNoContentError("20400"),
        HcxTransportError(HcxTimeoutKind.READ),
        HcxMalformedResponseError("invalid_json"),
    ],
)
@pytest.mark.asyncio
async def test_retryable_provider_failure_uses_at_most_two_hcx_calls(
    provider_error: Exception,
) -> None:
    client = ScriptedHcx([provider_error, provider_error])
    _, _, service = _planners(client)

    result = await service.plan(_request("국내 ETF만 보여줘"))

    assert result.attempts.hcx_calls == 2
    assert len(client.requests) == 2
    assert result.fallback_path == ("strict_json", "retry", "rule_fallback")


@pytest.mark.asyncio
async def test_rate_limit_delay_outside_shared_deadline_falls_back_without_sleep() -> None:
    async def forbidden_sleep(_: float) -> None:
        raise AssertionError("sleep must not exceed the shared deadline")

    rate_limits = HcxRateLimitSnapshot(reset_requests_seconds=60.0)
    client = ScriptedHcx([HcxRateLimitError("42900", rate_limits)])
    _, _, service = _planners(client, sleep=forbidden_sleep)

    result = await service.plan(_request("국내 ETF만 보여줘", seconds=0.05))

    assert result.attempts.hcx_calls == 1
    assert result.fallback_path == ("strict_json", "rule_fallback")


@pytest.mark.asyncio
async def test_rate_limit_zero_delay_can_retry_once_within_shared_deadline() -> None:
    async def immediate_sleep(_: float) -> None:
        return None

    client = ScriptedHcx(
        [
            HcxRateLimitError("42901", HcxRateLimitSnapshot(reset_requests_seconds=0.0)),
            json.dumps(_provider_plan()),
        ]
    )
    _, _, service = _planners(client, sleep=immediate_sleep)

    result = await service.plan(_request("미국 ETF 총보수 알려줘"))

    assert result.attempts.hcx_calls == 2
    assert result.fallback_path == ("strict_json", "retry")
    assert monotonic() <= result.request_deadline_at + 0.1


@pytest.mark.asyncio
async def test_rate_limit_backoff_timeout_falls_back() -> None:
    async def stalled_sleep(_: float) -> None:
        await asyncio.Event().wait()

    client = ScriptedHcx(
        [HcxRateLimitError("42900", HcxRateLimitSnapshot(reset_requests_seconds=0.001))]
    )
    _, _, service = _planners(client, sleep=stalled_sleep)

    result = await service.plan(_request("국내 ETF만 보여줘", seconds=0.01))

    assert result.attempts.hcx_calls == 1
    assert result.fallback_path == ("strict_json", "rule_fallback")
