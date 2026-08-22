"""Bounded evaluation composition over the planner and deterministic answer service."""

import asyncio
from collections.abc import Awaitable
from datetime import date
from time import monotonic
from typing import Protocol

from finproof.core.correlation import current_correlation_id
from finproof.core.logging import log_request_complete
from finproof.core.settings import EVALUATION_SNAPSHOT_DATE, ExecutionMode
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
from finproof.planner.service import PlannerProtocol, PlanningRequest
from finproof.service.limits import RequestContext, RequestLimiter


class AnswerPlanService(Protocol):
    """The deterministic Phase 2 answer boundary."""

    def answer_plan(self, request: AnswerRequest, plan: QueryPlan) -> AnswerResult: ...


class EvaluationOrchestrator:
    """Execute one evaluation request under one limiter-owned deadline."""

    def __init__(
        self,
        *,
        planner: PlannerProtocol,
        answer_service: AnswerPlanService,
        limiter: RequestLimiter | None = None,
        execution_mode: ExecutionMode,
        snapshot_date: date = EVALUATION_SNAPSHOT_DATE,
    ) -> None:
        self._planner = planner
        self._answer_service = answer_service
        self._limiter = limiter or RequestLimiter()
        self._execution_mode = execution_mode
        self._snapshot_date = snapshot_date

    async def answer(self, request: AnswerRequest) -> AnswerResult:
        """Return a deterministic verified result or a safe, bounded failure."""
        correlation_id = current_correlation_id()
        error_category: str | None = None
        fallback: str | None = None
        try:
            async with self._limiter.acquire(correlation_id=correlation_id) as context:
                result, fallback = await self._answer_within_deadline(request, context)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            error_category = "timeout"
            result = _safe_failure(correlation_id, self._snapshot_date)
        except Exception:
            error_category = "orchestration_failure"
            result = _safe_failure(correlation_id, self._snapshot_date)
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
        self, request: AnswerRequest, context: RequestContext
    ) -> tuple[AnswerResult, str | None]:
        planner_started = monotonic()
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
        )
        planner_latency = _elapsed_ms(planner_started)
        # ponytail: sync answer work cannot be force-cancelled; use a database interrupt hook if
        # physical query cancellation becomes necessary.
        result = await _within_deadline(
            asyncio.to_thread(self._answer_service.answer_plan, request, planned.plan), context
        )
        latency_ms = {"planner": planner_latency, **result.trace.latency_ms}
        return (
            result.model_copy(
                update={
                    "trace": result.trace.model_copy(
                        update={"correlation_id": context.correlation_id, "latency_ms": latency_ms}
                    )
                }
            ),
            " > ".join(planned.fallback_path) if planned.attempts.fallback_used else None,
        )


async def _within_deadline[Result](operation: Awaitable[Result], context: RequestContext) -> Result:
    remaining = context.remaining_seconds()
    if remaining <= 0:
        if hasattr(operation, "close"):
            operation.close()
        raise TimeoutError
    return await asyncio.wait_for(operation, timeout=remaining)


def _elapsed_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1000))


def _safe_failure(correlation_id: str, snapshot_date: date) -> AnswerResult:
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
            latency_ms={"planner": 0, "database": 0, "evidence": 0, "render": 0},
        ),
    )


def _fallback(result: AnswerResult) -> str | None:
    return "safe_failure" if result.trace.validation is TraceValidation.SAFE_FAILURE else None
