import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import date
from time import monotonic
from typing import Any, cast

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import (
    AggregationFunction,
    Intent,
    ProductType,
    ResultGrain,
    TopKScope,
)
from finproof.entity import EntityResolver, HoldingResolver
from finproof.entity.index import EntityIndex
from finproof.planner.hcx_client import (
    HcxMalformedResponseError,
    HcxNoContentError,
    HcxRateLimitError,
    HcxTimeoutKind,
    HcxTransportError,
)
from finproof.planner.models import HcxRequest, HcxResponse, HcxUsage
from finproof.planner.provider_schema import (
    ProviderPlanError,
    ProviderPlanValidationStage,
    build_hcx_query_plan_schema,
    parse_provider_plan,
)
from finproof.planner.rate_limits import HcxRateLimitSnapshot
from finproof.planner.rule_fallback import RuleFallbackPlanner
from finproof.planner.service import (
    LocalPlanValidator,
    PlannerOutputError,
    PlannerSemanticError,
    PlannerService,
    PlannerTerminalError,
    PlanningRequest,
)
from finproof.planner.structured_planner import StructuredOutputPlanner
from finproof.query import FieldRegistry, SemanticValidator
from finproof.registry.loader import RegistryBundle
from finproof.service.limits import RequestDeadline


class ScriptedHcx:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.requests: list[HcxRequest] = []

    async def generate(
        self, request: HcxRequest, request_id: str, *, deadline: RequestDeadline
    ) -> HcxResponse:
        del request_id
        assert deadline.remaining_work_seconds() > 0
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
        "metric_targets": [],
        "sort": [],
        "aggregation": {"function": "none", "field": "", "group_by": []},
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }
    value.update(updates)
    return value


def _request(question: str) -> PlanningRequest:
    return PlanningRequest(
        question=question,
        request_id="planner-test",
        as_of_date=date(2026, 7, 11),
        execution_mode=ExecutionMode.EVALUATION,
    )


def _deadline(seconds: float = 1.0) -> RequestDeadline:
    now = monotonic()
    return RequestDeadline(
        started_at=now,
        work_cutoff_at=now + seconds,
        outer_at=now + seconds + 2.0,
        _clock=monotonic,
    )


def _validator() -> LocalPlanValidator:
    registries = RegistryBundle.from_package()
    return LocalPlanValidator(
        SemanticValidator(FieldRegistry.from_bundle(registries)),
        entity_resolver=EntityResolver(EntityIndex._from_entries(())),
    )


def test_local_plan_validator_requires_and_passes_separate_holding_resolution() -> None:
    from finproof.domain.query_plan import (
        FilterClause,
        FilterOperator,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.query import ResolutionBundle

    registries = RegistryBundle.from_package()
    plan = QueryPlan(
        intent=Intent.SCREEN,
        product_types=(ProductType.DOMESTIC_ETF,),
        entities=(),
        as_of_date=date(2026, 8, 24),
        result_grain=ResultGrain.LISTED_PRODUCT,
        filters=(
            FilterClause(
                field="holding_constituent",
                operator=FilterOperator.EQ,
                value="삼성전자",
            ),
        ),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )
    request = PlanningRequest(
        question="삼성전자 보유 ETF",
        request_id="holding-planner",
        as_of_date=plan.as_of_date,
        execution_mode=ExecutionMode.EVALUATION,
    )
    semantic = SemanticValidator(FieldRegistry.from_bundle(registries))
    with pytest.raises(ValueError, match="holding resolver"):
        LocalPlanValidator(semantic).validate(plan, request)

    validated = LocalPlanValidator(
        semantic,
        holding_resolver=HoldingResolver._from_rows((("KR7005930003", "isin", "삼성전자"),)),
    ).validate(plan, request)

    resolutions = validated.resolutions
    assert isinstance(resolutions, ResolutionBundle)
    assert resolutions.holding_constituent is not None
    assert resolutions.holding_constituent.selected is not None
    assert resolutions.holding_constituent.selected.constituent_identifier == "KR7005930003"


def _planners(
    client: ScriptedHcx,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> tuple[StructuredOutputPlanner, RuleFallbackPlanner, PlannerService]:
    registries = RegistryBundle.from_package()
    validator = _validator()
    structured = StructuredOutputPlanner(
        generator=client,
        validator=validator,
        registries=registries,
        model_name="HCX-007",
    )
    fallback = RuleFallbackPlanner(validator=validator)
    service = (
        PlannerService(strict_json_planner=structured)
        if sleep is None
        else PlannerService(
            strict_json_planner=structured,
            sleep=sleep,
        )
    )
    return structured, fallback, service


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

    result = await planner.plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"), deadline=_deadline())

    assert result.fallback_path == ("structured",)
    assert result.validated_plan.plan is result.plan
    assert result.validated_plan.plan.top_k == 5
    assert client.requests[0].response_schema_json is not None
    assert client.requests[0].to_payload()["thinking"] == {"effort": "none"}


@pytest.mark.asyncio
async def test_invalid_provider_plan_logs_only_its_validation_stage(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    client = ScriptedHcx(["not-json"])
    planner = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    with pytest.raises(PlannerOutputError):
        await planner.plan(_request("국내 ETF만 보여줘"), deadline=_deadline())

    events = [
        record.__dict__
        for record in reversed(capture.records)
        if getattr(record, "event", None) == "hcx_output_invalid"
    ]
    assert len(events) == 1
    event = events[0]
    assert event["provider_request_id"] == "planner-test-structured"
    assert event["validation_stage"] == "invalid_json"
    serialized = json.dumps(event, default=str, ensure_ascii=False)
    assert "not-json" not in serialized
    assert "국내 ETF만 보여줘" not in serialized


@pytest.mark.parametrize(
    ("question", "intent", "needs_clarification", "expected_reason"),
    [
        (
            "공모펀드의 prfd_attr_cd 코드별 한글 의미와 공식 코드명을 모두 알려줘.",
            "unsupported",
            False,
            "공식 코드 값 테이블이 제공되지 않아 코드의 의미를 추정하거나 공식 명칭으로 "
            "매핑할 수 없습니다.",
        ),
        (
            "앞으로 1년 동안 수익률이 가장 높을 ETF를 확실하게 예측해줘.",
            "unsupported",
            False,
            "제공 데이터는 미래 수익률 예측이나 확정적 전망을 뒷받침하지 않습니다.",
        ),
        (
            "손실 가능성이 전혀 없고 반드시 돈을 버는 상품 하나만 추천해줘.",
            "unsupported",
            False,
            "무손실 보장이나 확정적 투자 추천은 제공 데이터로 검증할 수 없습니다.",
        ),
        (
            "지금 이 순간의 해외 ETF 실시간 가격과 수익률을 알려줘.",
            "unsupported",
            False,
            "평가 모드는 2026-08-24 공식 스냅샷만 사용하므로 실시간 값은 제공할 수 없습니다.",
        ),
        (
            "수익률 좋은 상품을 알려줘.",
            "clarify",
            True,
            "상품 유형과 수익률 기간을 지정해 주세요.",
        ),
        (
            "지원하지 않는 계산을 대신해줘.",
            "unsupported",
            False,
            "요청한 내용은 제공 데이터로 검증할 수 없습니다.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_structured_terminal_reason_ignores_provider_wording(
    question: str,
    intent: str,
    needs_clarification: bool,
    expected_reason: str,
) -> None:
    observed: set[str] = set()
    for provider_reason in ("첫 번째 HCX 표현", "의미는 같지만 다른 두 번째 HCX 표현"):
        payload = _provider_plan(
            intent=intent,
            product_types=["public_fund"],
            as_of_date="2026-08-24",
            result_grain="fund_item",
            filters=[],
            metrics=[],
            metric_targets=[],
            sort=[],
            top_k=10,
            top_k_scope="per_product_type",
            needs_clarification=needs_clarification,
            clarification_reason=provider_reason,
        )
        client = ScriptedHcx([json.dumps(payload)])
        planner = StructuredOutputPlanner(
            generator=client,
            validator=_validator(),
            registries=RegistryBundle.from_package(),
            model_name="HCX-007",
        )
        request = PlanningRequest(
            question=question,
            request_id="terminal-reason-test",
            as_of_date=date(2026, 8, 24),
            execution_mode=ExecutionMode.EVALUATION,
        )

        result = await planner.plan(request, deadline=_deadline())

        observed.add(result.plan.clarification_reason)
        assert result.validated_plan.plan is result.plan
        assert result.plan.product_types == ()
        assert result.plan.result_grain is ResultGrain.PRODUCT

    assert observed == {expected_reason}


@pytest.mark.asyncio
async def test_structured_terminal_discards_provider_execution_fields_before_validation() -> None:
    payload = _provider_plan(
        intent="unsupported",
        product_types=["public_fund"],
        result_grain="fund_item",
        filters=[{"field": "product_name", "operator": "contains", "value": "코드"}],
        metrics=["product_name"],
        sort=[{"field": "product_name", "direction": "asc"}],
        needs_clarification=False,
        clarification_reason="provider terminal reason",
    )
    planner = StructuredOutputPlanner(
        generator=ScriptedHcx([json.dumps(payload)]),
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    result = await planner.plan(
        _request("공모펀드의 prfd_attr_cd 코드별 한글 의미와 공식 코드명을 모두 알려줘."),
        deadline=_deadline(),
    )

    assert result.plan.intent is Intent.UNSUPPORTED
    assert result.plan.product_types == ()
    assert result.plan.filters == ()
    assert result.plan.metrics == ()
    assert result.plan.sort == ()


@pytest.mark.asyncio
async def test_structured_terminal_accepts_the_prompted_empty_product_types() -> None:
    payload = _provider_plan(
        intent="unsupported",
        product_types=[],
        result_grain="product",
        filters=[],
        metrics=[],
        sort=[],
        needs_clarification=False,
        clarification_reason="provider terminal reason",
    )
    planner = StructuredOutputPlanner(
        generator=ScriptedHcx([json.dumps(payload)]),
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    result = await planner.plan(
        _request("공모펀드의 prfd_attr_cd 코드별 한글 의미와 공식 코드명을 모두 알려줘."),
        deadline=_deadline(),
    )

    assert result.plan.intent is Intent.UNSUPPORTED
    assert result.plan.product_types == ()


def test_provider_none_sentinel_becomes_canonical_none() -> None:
    plan = parse_provider_plan(json.dumps(_provider_plan()))
    assert plan.aggregation is None


@pytest.mark.parametrize(
    "updates",
    [
        {"filters": [{"field": "provider-secret-field", "operator": "eq", "value": "x"}]},
        {"metrics": ["provider-secret-field"]},
        {"sort": [{"field": "provider-secret-field", "direction": "asc"}]},
        {
            "intent": "aggregate",
            "aggregation": {
                "function": "avg",
                "field": "provider-secret-field",
                "group_by": [],
            },
        },
        {
            "intent": "aggregate",
            "aggregation": {
                "function": "count",
                "field": "",
                "group_by": ["provider-secret-field"],
            },
        },
    ],
)
def test_provider_field_allowlist_rejects_unregistered_ids(updates: dict[str, object]) -> None:
    with pytest.raises(ProviderPlanError) as caught:
        parse_provider_plan(json.dumps(_provider_plan(**updates)))

    assert caught.value.stage is ProviderPlanValidationStage.PROVIDER_SCHEMA
    assert "provider-secret-field" not in str(caught.value)


@pytest.mark.parametrize(
    ("content", "expected_stage"),
    [
        ("not-json", ProviderPlanValidationStage.INVALID_JSON),
        (
            json.dumps({key: value for key, value in _provider_plan().items() if key != "top_k"}),
            ProviderPlanValidationStage.PROVIDER_SCHEMA,
        ),
        (
            json.dumps(_provider_plan(unexpected=True)),
            ProviderPlanValidationStage.CANONICAL_SCHEMA,
        ),
    ],
)
def test_provider_plan_failure_exposes_only_validation_stage(
    content: str, expected_stage: ProviderPlanValidationStage
) -> None:
    with pytest.raises(ProviderPlanError) as caught:
        parse_provider_plan(content)

    assert caught.value.stage is expected_stage
    assert content not in str(caught.value)


@pytest.mark.parametrize(
    ("content", "expected_substage", "expected_path", "expected_keyword"),
    [
        (
            json.dumps(
                _provider_plan(
                    aggregation={
                        "function": "none",
                        "field": "tracking_error",
                        "group_by": [],
                    }
                )
            ),
            "adaptation",
            "/aggregation",
            None,
        ),
        (
            json.dumps(_provider_plan(unexpected="provider-value-must-not-leak")),
            "schema",
            "/",
            "additionalProperties",
        ),
        (
            json.dumps(_provider_plan(product_types=["overseas_etf", "overseas_etf"])),
            "schema",
            "/product_types",
            "uniqueItems",
        ),
        (
            json.dumps(_provider_plan(result_grain="product")),
            "schema",
            "/product_types",
            "minItems",
        ),
    ],
)
def test_canonical_failure_exposes_only_substage_and_json_path(
    content: str,
    expected_substage: str,
    expected_path: str,
    expected_keyword: str | None,
) -> None:
    with pytest.raises(ProviderPlanError) as caught:
        parse_provider_plan(content)

    assert caught.value.canonical_substage == expected_substage
    assert caught.value.canonical_path == expected_path
    assert caught.value.canonical_keyword == expected_keyword
    assert content not in str(caught.value)
    assert "provider-value-must-not-leak" not in str(caught.value)


@pytest.mark.asyncio
async def test_structured_planner_propagates_sanitized_validation_stage() -> None:
    invalid_content = json.dumps(_provider_plan(result_grain="product"))
    client = ScriptedHcx([invalid_content])
    planner = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    with pytest.raises(PlannerOutputError) as caught:
        await planner.plan(_request("국내 ETF 5개"), deadline=_deadline())

    assert caught.value.validation_stage == ProviderPlanValidationStage.CANONICAL_SCHEMA.value
    assert caught.value.canonical_substage == "schema"
    assert caught.value.canonical_path == "/product_types"
    assert caught.value.canonical_keyword == "minItems"
    assert invalid_content not in str(caught.value)


@pytest.mark.parametrize(
    ("operator", "value", "expected_category"),
    [
        ("lte", [0.2], "scalar_operator_with_array"),
        ("in", "provider-value-must-not-leak", "set_operator_with_scalar"),
        ("between", [0.1], "range_arity"),
        ("is_not_missing", "provider-value-must-not-leak", "missing_operator_with_value"),
    ],
)
@pytest.mark.asyncio
async def test_filter_shape_category_exposes_only_allowlisted_structure(
    operator: str,
    value: object,
    expected_category: str,
) -> None:
    invalid_content = json.dumps(
        _provider_plan(filters=[{"field": "total_fee", "operator": operator, "value": value}])
    )
    client = ScriptedHcx([invalid_content])
    planner = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    with pytest.raises(PlannerOutputError) as caught:
        await planner.plan(_request("미국 ETF 5개"), deadline=_deadline())

    assert caught.value.filter_shape_category == expected_category
    assert "provider-value-must-not-leak" not in str(caught.value)


@pytest.mark.asyncio
async def test_structured_planner_exposes_only_allowlisted_semantic_reason(
    caplog: object,
) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    invalid_content = json.dumps(_provider_plan(result_grain="fund_item"))
    client = ScriptedHcx([invalid_content])
    planner = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    with pytest.raises(PlannerSemanticError) as caught:
        await planner.plan(_request("미국 ETF 5개"), deadline=_deadline())

    assert caught.value.reason_code == "result_grain_mismatch"
    assert invalid_content not in str(caught.value)
    event = next(
        record.__dict__
        for record in reversed(capture.records)
        if getattr(record, "event", None) == "hcx_output_invalid"
    )
    assert event["validation_stage"] == "semantic"
    assert event["semantic_reason_code"] == "result_grain_mismatch"
    assert "미국 ETF 5개" not in json.dumps(event, default=str, ensure_ascii=False)
    assert invalid_content not in json.dumps(event, default=str, ensure_ascii=False)


@pytest.mark.asyncio
async def test_filter_semantic_detail_exposes_only_registered_metadata() -> None:
    field_id = "risk_grade"
    invalid_content = json.dumps(
        _provider_plan(filters=[{"field": field_id, "operator": "eq", "value": "x"}])
    )
    client = ScriptedHcx([invalid_content])
    planner = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    with pytest.raises(PlannerSemanticError) as caught:
        await planner.plan(_request("미국 ETF 5개"), deadline=_deadline())

    assert caught.value.reason_code == "filter_field_unavailable"
    assert caught.value.detail == "product_inapplicable"
    assert caught.value.registry_field_id == field_id
    assert "provider-secret-field" not in str(caught.value)


@pytest.mark.asyncio
async def test_eligibility_semantic_detail_exposes_only_registered_location() -> None:
    invalid_content = json.dumps(_provider_plan(metrics=["total_fee", "saleable"]))
    client = ScriptedHcx([invalid_content])
    planner = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    with pytest.raises(PlannerSemanticError) as caught:
        await planner.plan(_request("미국 ETF 5개"), deadline=_deadline())

    assert caught.value.reason_code == "eligibility_unsupported"
    assert caught.value.detail == "metric"
    assert caught.value.registry_field_id == "saleable"
    assert invalid_content not in str(caught.value)


@pytest.mark.asyncio
async def test_organizer_purchaseable_heterogeneous_plan_drops_eligibility_filter() -> None:
    payload = _provider_plan(
        intent="screen_rank",
        product_types=["domestic_bond", "domestic_etf", "public_fund"],
        result_grain="product",
        filters=[{"field": "saleable", "operator": "eq", "value": True}],
        metrics=["buy_yield", "total_fee", "return_1y"],
        metric_targets=[
            {"product_type": "domestic_bond", "metrics": ["buy_yield"]},
            {"product_type": "domestic_etf", "metrics": ["total_fee"]},
            {"product_type": "public_fund", "metrics": ["return_1y"]},
        ],
        sort=[
            {"field": "buy_yield", "direction": "desc"},
            {"field": "total_fee", "direction": "asc"},
            {"field": "return_1y", "direction": "desc"},
        ],
        top_k=3,
        top_k_scope="per_product_type",
    )
    planner = StructuredOutputPlanner(
        generator=ScriptedHcx([json.dumps(payload)]),
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    planned = await planner.plan(
        _request(
            "현재 구매 가능한 국내채권과 국내 ETF, 공모펀드에서 채권은 매수수익률, "
            "ETF는 총보수, 펀드는 1년 수익률 기준으로 3개씩 알려줘."
        ),
        deadline=_deadline(),
    )

    assert planned.plan.filters == ()
    assert planned.plan.metrics == ("buy_yield", "total_fee", "return_1y")


@pytest.mark.asyncio
async def test_explicit_per_product_count_canonicalizes_global_scope() -> None:
    payload = _provider_plan(
        product_types=["domestic_etf", "overseas_etf", "public_fund"],
        result_grain="product",
        filters=[{"field": "aum", "operator": "eq", "value": 0}],
        metrics=["aum", "currency"],
        sort=[{"field": "product_name", "direction": "asc"}],
        top_k=10,
        top_k_scope="global",
    )
    planner = StructuredOutputPlanner(
        generator=ScriptedHcx([json.dumps(payload)]),
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    planned = await planner.plan(
        _request("AUM이 0으로 기록된 국내 ETF, 해외 ETF와 공모펀드를 상품 유형별로 10개씩 알려줘."),
        deadline=_deadline(),
    )

    assert planned.plan.top_k_scope is TopKScope.PER_PRODUCT_TYPE


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


def test_evaluation_service_accepts_structured_planner_repair_interface() -> None:
    client = ScriptedHcx([])
    _planners(client)
    structured = StructuredOutputPlanner(
        generator=client,
        validator=_validator(),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    PlannerService(strict_json_planner=structured)


@pytest.mark.asyncio
async def test_native_grain_failure_repair_restates_the_exact_mapping() -> None:
    invalid = _provider_plan(result_grain="product")
    corrected = _provider_plan(result_grain="listed_product")
    client = ScriptedHcx([json.dumps(invalid), json.dumps(corrected)])
    _, _, service = _planners(client)

    result = await service.plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"), deadline=_deadline())

    repair_instruction = client.requests[1].messages[-1].content
    assert "One product_type must use its native result_grain" in repair_instruction
    assert "result_grain=product only for heterogeneous native grains" in repair_instruction
    assert result.fallback_path == ("structured", "repair")


@pytest.mark.asyncio
async def test_qualitative_rank_repair_forbids_a_synthetic_threshold() -> None:
    common = {
        "product_types": ["domestic_etf"],
        "metrics": ["tracking_error"],
        "sort": [{"field": "tracking_error", "direction": "asc"}],
    }
    invalid = _provider_plan(**common, result_grain="product")
    corrected = _provider_plan(**common, result_grain="listed_product")
    client = ScriptedHcx([json.dumps(invalid), json.dumps(corrected)])
    _, _, service = _planners(client)

    result = await service.plan(_request("국내 ETF 중 추적오차가 낮은 5개"), deadline=_deadline())

    repair_instruction = client.requests[1].messages[-1].content
    assert "낮은/높은 with top-k define sort direction, not a filter" in repair_instruction
    assert "emit filters=[]; never invent a threshold" in repair_instruction
    assert result.plan.filters == ()


@pytest.mark.asyncio
async def test_nonaggregate_repair_restates_the_exact_aggregation_sentinel() -> None:
    invalid = _provider_plan(aggregation={"function": "none", "field": "total_fee", "group_by": []})
    corrected = _provider_plan()
    client = ScriptedHcx([json.dumps(invalid), json.dumps(corrected)])
    _, _, service = _planners(client)

    result = await service.plan(
        _request("국내 ETF 중 총보수가 낮은 상품 5개"), deadline=_deadline()
    )

    repair_instruction = client.requests[1].messages[-1].content
    assert 'aggregation={"function":"none","field":"","group_by":[]}' in repair_instruction
    assert "exactly these three keys" in repair_instruction
    assert result.plan.aggregation is None


@pytest.mark.asyncio
async def test_metric_target_repair_restates_the_exact_cross_product_rules() -> None:
    common = {
        "intent": "screen_rank",
        "product_types": ["domestic_bond", "domestic_etf", "public_fund"],
        "result_grain": "product",
        "metrics": ["buy_yield", "total_fee", "return_1y"],
        "sort": [
            {"field": "buy_yield", "direction": "desc"},
            {"field": "total_fee", "direction": "asc"},
            {"field": "return_1y", "direction": "desc"},
        ],
        "top_k": 3,
        "top_k_scope": "per_product_type",
    }
    corrected_targets = [
        {"product_type": "domestic_bond", "metrics": ["buy_yield"]},
        {"product_type": "domestic_etf", "metrics": ["total_fee"]},
        {"product_type": "public_fund", "metrics": ["return_1y"]},
    ]
    invalid = _provider_plan(**common, metric_targets=list(reversed(corrected_targets)))
    corrected = _provider_plan(**common, metric_targets=corrected_targets)
    client = ScriptedHcx([json.dumps(invalid), json.dumps(corrected)])
    _, _, service = _planners(client)

    result = await service.plan(_request("상품별로 다른 지표 기준 3개씩"), deadline=_deadline())

    repair_instruction = client.requests[1].messages[-1].content
    assert "otherwise metric_targets=[]" in repair_instruction
    assert "one target per product_type in product_types order" in repair_instruction
    assert "union must exactly equal metrics" in repair_instruction
    assert result.plan.metric_targets[0].product_type is ProductType.DOMESTIC_BOND


@pytest.mark.asyncio
async def test_malformed_json_gets_one_repair_then_fails_closed() -> None:
    semantically_invalid = _provider_plan(result_grain="fund_item")
    client = ScriptedHcx(["not-json", json.dumps(semantically_invalid)])
    _, _, service = _planners(client)

    with pytest.raises(PlannerTerminalError) as caught:
        await service.plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"), deadline=_deadline())

    assert caught.value.attempts.hcx_calls == 2
    assert caught.value.attempts.repair_calls == 1
    assert all(
        json.loads(request.response_schema_json or "null") == build_hcx_query_plan_schema()
        for request in client.requests
    )


@pytest.mark.asyncio
async def test_semantic_failure_skips_repair_and_never_executes() -> None:
    client = ScriptedHcx([json.dumps(_provider_plan(result_grain="fund_item"))])
    _, _, service = _planners(client)

    with pytest.raises(PlannerTerminalError) as caught:
        await service.plan(_request("미국 ETF 중 총보수 0.2% 이하 5개"), deadline=_deadline())

    assert caught.value.attempts.hcx_calls == 1
    assert caught.value.attempts.repair_calls == 0


@pytest.mark.parametrize(
    ("provider_error", "expected_calls"),
    [
        (HcxNoContentError("20400"), 1),
        (HcxTransportError(HcxTimeoutKind.READ), 2),
        (HcxMalformedResponseError("invalid_json"), 1),
    ],
)
@pytest.mark.asyncio
async def test_retryable_provider_failure_uses_at_most_two_hcx_calls(
    provider_error: Exception,
    expected_calls: int,
) -> None:
    client = ScriptedHcx([provider_error] * expected_calls)
    _, _, service = _planners(client)

    with pytest.raises(PlannerTerminalError) as caught:
        await service.plan(_request("국내 ETF만 보여줘"), deadline=_deadline())

    assert caught.value.attempts.hcx_calls == expected_calls
    assert len(client.requests) == expected_calls


@pytest.mark.asyncio
async def test_rate_limit_delay_outside_shared_deadline_fails_without_sleep() -> None:
    async def forbidden_sleep(_: float) -> None:
        raise AssertionError("sleep must not exceed the shared deadline")

    rate_limits = HcxRateLimitSnapshot(reset_requests_seconds=60.0)
    client = ScriptedHcx([HcxRateLimitError("42900", rate_limits)])
    _, _, service = _planners(client, sleep=forbidden_sleep)

    with pytest.raises(PlannerTerminalError) as caught:
        await service.plan(_request("국내 ETF만 보여줘"), deadline=_deadline(0.05))

    assert caught.value.attempts.hcx_calls == 1


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

    result = await service.plan(_request("미국 ETF 총보수 알려줘"), deadline=_deadline())

    assert result.attempts.hcx_calls == 2
    assert result.fallback_path == ("structured", "retry")
    assert monotonic() <= result.request_deadline_at + 0.1


@pytest.mark.asyncio
async def test_rate_limit_backoff_timeout_fails_closed() -> None:
    async def stalled_sleep(_: float) -> None:
        await asyncio.Event().wait()

    client = ScriptedHcx(
        [HcxRateLimitError("42900", HcxRateLimitSnapshot(reset_requests_seconds=0.001))]
    )
    _, _, service = _planners(client, sleep=stalled_sleep)

    with pytest.raises(PlannerTerminalError) as caught:
        await service.plan(_request("국내 ETF만 보여줘"), deadline=_deadline(0.01))

    assert caught.value.attempts.hcx_calls == 1


@pytest.mark.asyncio
async def test_evaluation_planner_has_no_rule_fallback_path() -> None:
    client = ScriptedHcx([json.dumps(_provider_plan(result_grain="fund_item"))])
    strict, _, _ = _planners(client)
    service = PlannerService(strict_json_planner=strict)

    with pytest.raises(PlannerTerminalError, match="semantic"):
        await service.plan(
            _request("미국 ETF 중 총보수 0.2% 이하 5개"),
            deadline=_deadline(),
        )

    assert len(client.requests) == 1
