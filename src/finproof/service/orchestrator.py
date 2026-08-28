"""Bounded evaluation composition over the planner and deterministic answer service."""

import asyncio
from collections.abc import Awaitable
from datetime import date
from time import monotonic
from typing import Protocol

from finproof.core.correlation import current_correlation_id
from finproof.core.logging import log_request_complete
from finproof.core.settings import OFFICIAL_DISTRIBUTION_DATE, ExecutionMode
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
from finproof.planner.service import PlannedQuery, PlannerProtocol, PlanningRequest
from finproof.service.limits import RequestContext, RequestLimiter


class AnswerPlanService(Protocol):
    """The deterministic Phase 2 answer boundary."""

    def answer_plan(self, request: AnswerRequest, plan: QueryPlan) -> AnswerResult: ...


class _DeadlineExceeded(TimeoutError):
    def __init__(self, stage: str) -> None:
        self.stage = stage


class _DatabaseFailure(Exception):
    """The deterministic answer stage failed without exposing its detail."""


class _PlannerFailure(Exception):
    """The planner boundary failed without exposing provider detail."""


class EvaluationOrchestrator:
    """Execute one evaluation request under one limiter-owned deadline."""

    def __init__(
        self,
        *,
        planner: PlannerProtocol,
        answer_service: AnswerPlanService,
        limiter: RequestLimiter | None = None,
        execution_mode: ExecutionMode,
        snapshot_date: date = OFFICIAL_DISTRIBUTION_DATE,
    ) -> None:
        self._planner = planner
        self._answer_service = answer_service
        self._limiter = limiter or RequestLimiter()
        self._execution_mode = execution_mode
        self._snapshot_date = snapshot_date
        self._database_workers: set[asyncio.Task[AnswerResult]] = set()

    async def aclose(self) -> None:
        """Drain detached database workers before their runtime session closes."""
        while self._database_workers:
            await asyncio.gather(*tuple(self._database_workers), return_exceptions=True)

    async def answer(self, request: AnswerRequest) -> AnswerResult:
        """Return a deterministic verified result or a safe, bounded failure."""
        correlation_id = current_correlation_id()
        stage_latency_ms = {"planner": 0, "database": 0, "evidence": 0, "render": 0}
        error_category: str | None = None
        fallback: str | None = None
        try:
            async with self._limiter.acquire(correlation_id=correlation_id) as context:
                result, fallback, error_category = await self._answer_within_deadline(
                    request, context, stage_latency_ms
                )
        except asyncio.CancelledError:
            raise
        except _DeadlineExceeded as error:
            error_category = f"{error.stage}_timeout"
            result = _safe_failure(correlation_id, self._snapshot_date, stage_latency_ms)
        except _DatabaseFailure:
            error_category = "database_failure"
            result = _safe_failure(correlation_id, self._snapshot_date, stage_latency_ms)
        except _PlannerFailure:
            error_category = "planner_failure"
            result = _safe_failure(correlation_id, self._snapshot_date, stage_latency_ms)
        except Exception:
            error_category = "orchestration_failure"
            result = _safe_failure(correlation_id, self._snapshot_date, stage_latency_ms)
        log_request_complete(
            correlation_id=correlation_id,
            stage_latency_ms=result.trace.latency_ms,
            candidate_counts=result.trace.candidate_counts,
            policy_ids=result.trace.policy_ids,
            fallback=fallback or _fallback(result),
            error_category=error_category,
        )
        return result

    async def _answer_within_deadline(
        self,
        request: AnswerRequest,
        context: RequestContext,
        stage_latency_ms: dict[str, int],
    ) -> tuple[AnswerResult, str | None, str | None]:
        try:
            planned = await _within_deadline(
                self._planner.plan(
                    PlanningRequest(
                        question=request.question,
                        request_id=context.correlation_id,
                        as_of_date=self._snapshot_date,
                        execution_mode=self._execution_mode,
                        deadline_at=context.deadline_at,
                    )
                ),
                context,
                stage="planner",
                stage_latency_ms=stage_latency_ms,
            )
        except _DeadlineExceeded:
            raise
        except Exception:
            raise _PlannerFailure from None
        worker = asyncio.create_task(
            asyncio.to_thread(self._answer_service.answer_plan, request, planned.plan)
        )
        self._database_workers.add(worker)
        worker.add_done_callback(self._database_workers.discard)
        try:
            result = await _within_deadline(
                asyncio.shield(worker),
                context,
                stage="database",
                stage_latency_ms=stage_latency_ms,
            )
        except (asyncio.CancelledError, _DeadlineExceeded):
            context.retain_permit_until_done(worker)
            raise
        except Exception:
            raise _DatabaseFailure from None
        latency_ms = {**stage_latency_ms, **result.trace.latency_ms}
        return (
            result.model_copy(
                update={
                    "trace": result.trace.model_copy(
                        update={"correlation_id": context.correlation_id, "latency_ms": latency_ms}
                    )
                }
            ),
            " > ".join(planned.fallback_path) if planned.attempts.fallback_used else None,
            _fallback_category(planned),
        )


async def _within_deadline[Result](
    operation: Awaitable[Result],
    context: RequestContext,
    *,
    stage: str,
    stage_latency_ms: dict[str, int],
) -> Result:
    started = monotonic()
    try:
        remaining = context.remaining_seconds()
        if remaining <= 0:
            if hasattr(operation, "close"):
                operation.close()
            raise _DeadlineExceeded(stage)
        try:
            return await asyncio.wait_for(operation, timeout=remaining)
        except TimeoutError:
            raise _DeadlineExceeded(stage) from None
    finally:
        stage_latency_ms[stage] = _elapsed_ms(started)


def _elapsed_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1000))


def _safe_failure(
    correlation_id: str, snapshot_date: date, stage_latency_ms: dict[str, int]
) -> AnswerResult:
    return AnswerResult(
        answer=VerifiedAnswer(text="요청을 처리할 수 없습니다.", claims=()),
        retrieved_context="{}",
        trace=ExecutionTrace(
            correlation_id=correlation_id,
            intent=Intent.CLARIFY,
            product_types=(),
            as_of_date=snapshot_date,
            result_grain=ResultGrain.PRODUCT,
            top_k_scope=TopKScope.GLOBAL,
            segments=(),
            candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
            tools=("safe_failure",),
            policy_ids=(),
            validation=TraceValidation.SAFE_FAILURE,
            versions={},
            latency_ms=stage_latency_ms,
        ),
    )


def _fallback(result: AnswerResult) -> str | None:
    return "safe_failure" if result.trace.validation is TraceValidation.SAFE_FAILURE else None


def _fallback_category(planned: PlannedQuery) -> str | None:
    attempts = planned.attempts
    if not attempts.fallback_used:
        return None
    if attempts.transport_failures:
        return "planner_transport_fallback"
    if attempts.parse_failures:
        return "planner_output_fallback"
    if attempts.semantic_failures:
        return "planner_semantic_fallback"
    return "planner_rule_fallback"
