"""Evaluation orchestration failures remain deterministic and bounded."""

import asyncio
from datetime import date
from time import sleep

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation, ValidatedQueryPlan
from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
from finproof.planner.service import PlannedQuery, PlannerAttemptSummary
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
