"""Evaluation orchestration failures remain deterministic and bounded."""

import asyncio
import json
import logging
from datetime import date
from threading import Event
from time import sleep
from typing import Any, cast

import pytest
from tests.integration.planner.test_planner_service import ScriptedHcx, _planners, _provider_plan

from finproof.core.settings import ExecutionMode
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation, ValidatedQueryPlan
from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
from finproof.planner.hcx_client import HcxRateLimitError, HcxTransportError
from finproof.planner.rate_limits import HcxRateLimitSnapshot
from finproof.planner.service import PlannedQuery, PlannerAttemptSummary, PlannerService
from finproof.service.limits import RequestLimiter
from finproof.service.orchestrator import EvaluationOrchestrator


def _request() -> AnswerRequest:
    return AnswerRequest(question_id="Q-001", question="미국 ETF 총보수 알려줘")


def _plan() -> QueryPlan:
    return QueryPlan(
        intent=Intent.CLARIFY,
        product_types=(),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=True,
        clarification_reason="조건을 확인해 주세요.",
    )


def _planned_query() -> PlannedQuery:
    plan = _plan()
    return PlannedQuery(
        plan=plan,
        validated_plan=ValidatedQueryPlan._issue(plan=plan, resolutions=(), context=object()),
        attempts=PlannerAttemptSummary(
            hcx_calls=0,
            repair_calls=0,
            parse_failures=0,
            semantic_failures=0,
            transport_failures=0,
            fallback_used=True,
        ),
        latency_ms=0,
        fallback_path=("rule_fallback",),
        safe_assumptions=(),
        request_deadline_at=0.0,
    )


def _answer_result() -> AnswerResult:
    return AnswerResult(
        answer=VerifiedAnswer(text="조건을 확인해 주세요.", claims=()),
        retrieved_context="{}",
        trace=ExecutionTrace(
            correlation_id="service",
            intent=Intent.CLARIFY,
            product_types=(),
            as_of_date=date(2026, 7, 11),
            result_grain=ResultGrain.PRODUCT,
            top_k_scope=TopKScope.GLOBAL,
            segments=(),
            candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
            tools=("claim_verifier",),
            policy_ids=("answer:1.0.0",),
            validation=TraceValidation.CLARIFY,
            versions={},
            latency_ms={"database": 0, "evidence": 0, "render": 0},
        ),
    )


class SlowPlanner:
    async def plan(self, _: object) -> PlannedQuery:
        await asyncio.sleep(0.05)
        return _planned_query()


class ImmediatePlanner:
    async def plan(self, _: object) -> PlannedQuery:
        return _planned_query()


class ImmediateAnswerService:
    def answer_plan(self, _: AnswerRequest, __: QueryPlan) -> AnswerResult:
        return _answer_result()


class SlowAnswerService:
    def answer_plan(self, _: AnswerRequest, __: QueryPlan) -> AnswerResult:
        sleep(0.05)
        return _answer_result()


class FailingAnswerService:
    def answer_plan(self, _: AnswerRequest, __: QueryPlan) -> AnswerResult:
        raise RuntimeError("database failed")


class TransportFallbackPlanner:
    async def plan(self, _: object) -> PlannedQuery:
        result = _planned_query()
        return result.model_copy(
            update={
                "attempts": result.attempts.model_copy(update={"transport_failures": 1}),
                "fallback_path": ("strict_json", "retry", "rule_fallback"),
            }
        )


class RecordingPlanner:
    def __init__(self, planner: PlannerService) -> None:
        self._planner = planner
        self.deadline_at: float | None = None
        self.result: PlannedQuery | None = None

    async def plan(self, request: object) -> PlannedQuery:
        planning_request = cast(Any, request)
        self.deadline_at = planning_request.deadline_at
        self.result = await self._planner.plan(planning_request)
        return self.result


class BlockingAnswerService:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.finished = Event()
        self.calls = 0

    def answer_plan(self, _: AnswerRequest, __: QueryPlan) -> AnswerResult:
        self.calls += 1
        self.started.set()
        self.release.wait()
        self.finished.set()
        return _answer_result()


@pytest.mark.asyncio
async def test_request_over_deadline_returns_verified_safe_failure() -> None:
    orchestrator = EvaluationOrchestrator(
        planner=SlowPlanner(),
        answer_service=ImmediateAnswerService(),
        limiter=RequestLimiter(max_in_flight=8, deadline_seconds=0.01),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request())

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert "처리" in result.answer.text


@pytest.mark.asyncio
async def test_database_work_over_deadline_returns_verified_safe_failure() -> None:
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=SlowAnswerService(),
        limiter=RequestLimiter(max_in_flight=8, deadline_seconds=0.01),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request())

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert "처리" in result.answer.text


@pytest.mark.asyncio
async def test_timed_out_worker_keeps_permit_until_sync_work_finishes() -> None:
    answer_service = BlockingAnswerService()
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=answer_service,
        limiter=RequestLimiter(max_in_flight=1, deadline_seconds=0.05),
        execution_mode=ExecutionMode.EVALUATION,
    )

    first = asyncio.create_task(orchestrator.answer(_request()))
    await asyncio.to_thread(answer_service.started.wait)
    assert (await first).trace.validation is TraceValidation.SAFE_FAILURE

    second = asyncio.create_task(orchestrator.answer(_request()))
    try:
        await asyncio.sleep(0.01)
        assert answer_service.calls == 1
    finally:
        answer_service.release.set()
        await asyncio.to_thread(answer_service.finished.wait)
    assert (await second).trace.validation is TraceValidation.CLARIFY


@pytest.mark.asyncio
async def test_cancelled_worker_keeps_permit_until_sync_work_finishes() -> None:
    answer_service = BlockingAnswerService()
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=answer_service,
        limiter=RequestLimiter(max_in_flight=1, deadline_seconds=1.0),
        execution_mode=ExecutionMode.EVALUATION,
    )

    first = asyncio.create_task(orchestrator.answer(_request()))
    await asyncio.to_thread(answer_service.started.wait)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    second = asyncio.create_task(orchestrator.answer(_request()))
    try:
        await asyncio.sleep(0.01)
        assert answer_service.calls == 1
    finally:
        answer_service.release.set()
    await asyncio.to_thread(answer_service.finished.wait)
    assert (await second).trace.validation is TraceValidation.CLARIFY


@pytest.mark.asyncio
async def test_orchestrator_close_waits_for_timed_out_database_worker() -> None:
    answer_service = BlockingAnswerService()
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=answer_service,
        limiter=RequestLimiter(max_in_flight=1, deadline_seconds=0.01),
        execution_mode=ExecutionMode.EVALUATION,
    )

    request = asyncio.create_task(orchestrator.answer(_request()))
    await asyncio.to_thread(answer_service.started.wait)
    assert (await request).trace.validation is TraceValidation.SAFE_FAILURE

    try:
        closing = asyncio.create_task(orchestrator.aclose())
        await asyncio.sleep(0.01)
        assert not closing.done()
    finally:
        answer_service.release.set()
        await asyncio.to_thread(answer_service.finished.wait)
    await closing


@pytest.mark.asyncio
async def test_planner_timeout_records_elapsed_stage_and_category(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=SlowPlanner(),
        answer_service=ImmediateAnswerService(),
        limiter=RequestLimiter(max_in_flight=8, deadline_seconds=0.01),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request())

    assert result.trace.latency_ms == {
        "planner": result.trace.latency_ms["planner"],
        "database": 0,
        "evidence": 0,
        "render": 0,
    }
    assert result.trace.latency_ms["planner"] > 0
    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"] == "planner_timeout"
    )


@pytest.mark.asyncio
async def test_database_timeout_records_elapsed_stage_and_category(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=SlowAnswerService(),
        limiter=RequestLimiter(max_in_flight=8, deadline_seconds=0.01),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request())

    assert result.trace.latency_ms["database"] > 0
    assert result.trace.latency_ms["planner"] >= 0
    assert result.trace.latency_ms["evidence"] == 0
    assert result.trace.latency_ms["render"] == 0
    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "database_timeout"
    )


@pytest.mark.asyncio
async def test_database_failure_is_logged_as_its_own_category(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=FailingAnswerService(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await orchestrator.answer(_request())

    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "database_failure"
    )


@pytest.mark.asyncio
async def test_planner_transport_fallback_is_logged_from_attempts(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=TransportFallbackPlanner(),
        answer_service=ImmediateAnswerService(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await orchestrator.answer(_request())

    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "planner_transport_fallback"
    )


@pytest.mark.asyncio
async def test_real_planner_retries_429_when_reset_fits_orchestrator_deadline() -> None:
    delays: list[float] = []

    async def bounded_sleep(delay: float) -> None:
        delays.append(delay)

    client = ScriptedHcx(
        [
            HcxRateLimitError("42901", HcxRateLimitSnapshot(reset_requests_seconds=0.001)),
            json.dumps(_provider_plan()),
        ]
    )
    _, _, planner_service = _planners(client, sleep=bounded_sleep)
    planner = RecordingPlanner(planner_service)
    orchestrator = EvaluationOrchestrator(
        planner=planner,
        answer_service=ImmediateAnswerService(),
        limiter=RequestLimiter(max_in_flight=8, deadline_seconds=0.1),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await orchestrator.answer(_request())

    assert delays == [0.001]
    assert len(client.requests) == 2
    assert planner.result is not None
    assert planner.deadline_at == planner.result.request_deadline_at


@pytest.mark.asyncio
async def test_real_planner_refuses_429_retry_outside_orchestrator_deadline(
    caplog: object,
) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")

    async def forbidden_sleep(_: float) -> None:
        raise AssertionError("retry sleep must fit the request deadline")

    client = ScriptedHcx(
        [HcxRateLimitError("42900", HcxRateLimitSnapshot(reset_requests_seconds=60.0))]
    )
    _, _, planner = _planners(client, sleep=forbidden_sleep)
    orchestrator = EvaluationOrchestrator(
        planner=planner,
        answer_service=ImmediateAnswerService(),
        limiter=RequestLimiter(max_in_flight=8, deadline_seconds=0.05),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await orchestrator.answer(_request())

    assert len(client.requests) == 1
    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "planner_transport_fallback"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("responses", "category"),
    [
        (["not-json", "not-json"], "planner_output_fallback"),
        ([HcxTransportError(), HcxTransportError()], "planner_transport_fallback"),
    ],
)
async def test_real_planner_fallbacks_stop_after_two_provider_calls(
    responses: list[str | Exception], category: str, caplog: object
) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    client = ScriptedHcx(responses)
    _, _, planner = _planners(client)
    orchestrator = EvaluationOrchestrator(
        planner=planner,
        answer_service=ImmediateAnswerService(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await orchestrator.answer(_request())

    assert len(client.requests) == 2
    assert cast(dict[str, object], capture.records[-1].__dict__)["error_category"] == category


@pytest.mark.asyncio
async def test_real_planner_semantic_fallback_is_logged_from_attempts(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    client = ScriptedHcx([json.dumps(_provider_plan(result_grain="fund_item"))])
    _, _, planner = _planners(client)
    orchestrator = EvaluationOrchestrator(
        planner=planner,
        answer_service=ImmediateAnswerService(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await orchestrator.answer(_request())

    assert len(client.requests) == 1
    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "planner_semantic_fallback"
    )
