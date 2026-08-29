"""Bounded evaluation composition over mandatory HCX planning and wording."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from time import monotonic
from typing import Protocol

from finproof.answer.hcx_verbalizer import ProviderWordingError
from finproof.core.correlation import current_correlation_id
from finproof.core.logging import log_request_complete
from finproof.core.settings import OFFICIAL_DISTRIBUTION_DATE, ExecutionMode
from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.answers import (
    AnswerRequest,
    AnswerResult,
    FactPack,
    PreparedAnswer,
    ProviderWording,
    VerifiedAnswer,
)
from finproof.domain.query_plan import QueryPlan
from finproof.evidence import ClaimVerificationError, ClaimVerifier
from finproof.planner.service import (
    PlannedQuery,
    PlannerProtocol,
    PlannerTerminalError,
    PlanningRequest,
)
from finproof.service.limits import RequestContext, RequestDeadline, RequestLimiter


class AnswerPreparationService(Protocol):
    def prepare_plan(
        self, request: AnswerRequest, plan: QueryPlan, deadline: RequestDeadline
    ) -> PreparedAnswer: ...


class WordingService(Protocol):
    async def verbalize(
        self,
        fact_pack: FactPack,
        *,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording: ...

    async def repair(
        self,
        fact_pack: FactPack,
        *,
        invalid_content: str,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording: ...


class WordingVerifier(Protocol):
    def verify_wording(
        self,
        wording: ProviderWording,
        prepared: PreparedAnswer,
        deadline: RequestDeadline,
    ) -> VerifiedAnswer: ...


class _DeadlineExceeded(TimeoutError):
    def __init__(self, stage: str) -> None:
        self.stage = stage


class _DatabaseFailure(Exception):
    """Deterministic preparation failed without exposing its detail."""


class _PlannerFailure(Exception):
    def __init__(self, category: str = "planner_failure") -> None:
        self.category = category


class _WordingFailure(Exception):
    def __init__(self, category: str) -> None:
        self.category = category


class EvaluationOrchestrator:
    """Execute one evaluation request with one ingress-issued deadline."""

    def __init__(
        self,
        *,
        planner: PlannerProtocol,
        answer_service: AnswerPreparationService,
        verbalizer: WordingService,
        verifier: WordingVerifier | None = None,
        limiter: RequestLimiter | None = None,
        execution_mode: ExecutionMode,
        snapshot_date: date = OFFICIAL_DISTRIBUTION_DATE,
    ) -> None:
        self._planner = planner
        self._answer_service = answer_service
        self._verbalizer = verbalizer
        self._verifier = verifier or ClaimVerifier()
        self._limiter = limiter or RequestLimiter()
        self._execution_mode = execution_mode
        self._snapshot_date = snapshot_date
        self._database_workers: set[asyncio.Task[PreparedAnswer]] = set()

    async def aclose(self) -> None:
        """Drain detached database workers before dependency teardown."""
        while self._database_workers:
            await asyncio.gather(*tuple(self._database_workers), return_exceptions=True)

    async def plan(self, request: PlanningRequest, *, deadline: RequestDeadline) -> PlannedQuery:
        """Expose the mandatory HCX planning stage for CLI plan-only scoring."""
        remaining = deadline.remaining_work_seconds()
        if remaining <= 0:
            raise TimeoutError("planning deadline exceeded")
        return await asyncio.wait_for(
            self._planner.plan(request, deadline=deadline), timeout=remaining
        )

    async def answer(
        self,
        request: AnswerRequest,
        *,
        deadline: RequestDeadline,
        safe_result: AnswerResult,
    ) -> AnswerResult:
        """Return verified HCX wording or the exact prebuilt safe result."""
        _, result = await self.answer_with_plan(request, deadline=deadline, safe_result=safe_result)
        return result

    async def answer_with_plan(
        self,
        request: AnswerRequest,
        *,
        deadline: RequestDeadline,
        safe_result: AnswerResult,
    ) -> tuple[PlannedQuery | None, AnswerResult]:
        """Run the same pipeline while exposing its one HCX plan to CLI scoring."""
        correlation_id = current_correlation_id()
        planned: PlannedQuery | None = None
        stage_latency_ms = {
            "planner": 0,
            "database": 0,
            "evidence": 0,
            "render": 0,
            "wording": 0,
        }
        error_category: str | None = None
        try:
            async with self._limiter.acquire(
                correlation_id=correlation_id, deadline=deadline
            ) as context:
                planned, result = await self._answer_within_deadline(
                    request, context, stage_latency_ms
                )
        except asyncio.CancelledError:
            raise
        except _DeadlineExceeded as error:
            error_category = f"{error.stage}_timeout"
            result = safe_result
        except _PlannerFailure as error:
            error_category = error.category
            result = safe_result
        except _DatabaseFailure:
            error_category = "database_failure"
            result = safe_result
        except _WordingFailure as error:
            error_category = error.category
            result = safe_result
        except Exception:
            error_category = "orchestration_failure"
            result = safe_result
        log_request_complete(
            correlation_id=correlation_id,
            stage_latency_ms=(
                stage_latency_ms if result is safe_result else result.trace.latency_ms
            ),
            candidate_counts=result.trace.candidate_counts,
            policy_ids=result.trace.policy_ids,
            fallback="safe_failure" if result is safe_result else None,
            error_category=error_category,
        )
        return planned, result

    async def _answer_within_deadline(
        self,
        request: AnswerRequest,
        context: RequestContext,
        stage_latency_ms: dict[str, int],
    ) -> tuple[PlannedQuery, AnswerResult]:
        planning_request = PlanningRequest(
            question=request.question,
            request_id=context.correlation_id,
            as_of_date=self._snapshot_date,
            execution_mode=self._execution_mode,
        )
        try:
            planned = await _within_deadline(
                lambda: self._planner.plan(planning_request, deadline=context.deadline),
                context,
                stage="planner",
                stage_latency_ms=stage_latency_ms,
            )
        except _DeadlineExceeded:
            raise
        except PlannerTerminalError as error:
            raise _PlannerFailure(f"planner_{error.category}") from None
        except Exception:
            raise _PlannerFailure() from None

        if context.remaining_work_seconds() <= 0:
            raise _DeadlineExceeded("database")
        worker = asyncio.create_task(
            asyncio.to_thread(
                self._answer_service.prepare_plan,
                request,
                planned.plan,
                context.deadline,
            )
        )
        self._database_workers.add(worker)
        worker.add_done_callback(self._database_workers.discard)
        try:
            prepared = await _within_deadline(
                lambda: asyncio.shield(worker),
                context,
                stage="database",
                stage_latency_ms=stage_latency_ms,
            )
        except (asyncio.CancelledError, _DeadlineExceeded):
            context.retain_permit_until_done(worker)
            raise
        except Exception:
            raise _DatabaseFailure from None

        try:
            wording = await _within_deadline(
                lambda: self._verbalizer.verbalize(
                    prepared.fact_pack,
                    request_id=context.correlation_id,
                    deadline=context.deadline,
                ),
                context,
                stage="wording",
                stage_latency_ms=stage_latency_ms,
            )
        except ProviderWordingError as error:
            return (
                planned,
                await self._repair_wording(
                    prepared,
                    invalid_content=error.invalid_content,
                    context=context,
                    stage_latency_ms=stage_latency_ms,
                ),
            )
        except _DeadlineExceeded:
            raise
        except Exception:
            raise _WordingFailure("wording_provider_failure") from None

        try:
            verified = self._verifier.verify_wording(wording, prepared, context.deadline)
        except ClaimVerificationError:
            return (
                planned,
                await self._repair_wording(
                    prepared,
                    invalid_content=canonical_json_bytes(
                        wording.model_dump(mode="json"), terminal_newline=False
                    ).decode(),
                    context=context,
                    stage_latency_ms=stage_latency_ms,
                ),
            )
        except Exception:
            raise _WordingFailure("wording_verification_failure") from None
        return (
            planned,
            _result(
                prepared,
                verified,
                correlation_id=context.correlation_id,
                stage_latency_ms=stage_latency_ms,
            ),
        )

    async def _repair_wording(
        self,
        prepared: PreparedAnswer,
        *,
        invalid_content: str,
        context: RequestContext,
        stage_latency_ms: dict[str, int],
    ) -> AnswerResult:
        try:
            repaired = await _within_deadline(
                lambda: self._verbalizer.repair(
                    prepared.fact_pack,
                    invalid_content=invalid_content,
                    request_id=context.correlation_id,
                    deadline=context.deadline,
                ),
                context,
                stage="wording",
                stage_latency_ms=stage_latency_ms,
            )
            verified = self._verifier.verify_wording(repaired, prepared, context.deadline)
        except _DeadlineExceeded:
            raise
        except Exception:
            raise _WordingFailure("wording_repair_failure") from None
        return _result(
            prepared,
            verified,
            correlation_id=context.correlation_id,
            stage_latency_ms=stage_latency_ms,
        )


async def _within_deadline[Result](
    operation: Callable[[], Awaitable[Result]],
    context: RequestContext,
    *,
    stage: str,
    stage_latency_ms: dict[str, int],
) -> Result:
    started = monotonic()
    try:
        remaining = context.remaining_work_seconds()
        if remaining <= 0:
            raise _DeadlineExceeded(stage)
        try:
            return await asyncio.wait_for(operation(), timeout=remaining)
        except TimeoutError:
            raise _DeadlineExceeded(stage) from None
    finally:
        stage_latency_ms[stage] = stage_latency_ms.get(stage, 0) + _elapsed_ms(started)


def _result(
    prepared: PreparedAnswer,
    verified: VerifiedAnswer,
    *,
    correlation_id: str,
    stage_latency_ms: dict[str, int],
) -> AnswerResult:
    latency_ms = {**prepared.trace.latency_ms, **stage_latency_ms}
    return AnswerResult(
        answer=verified,
        retrieved_context=prepared.retrieved_context,
        trace=prepared.trace.model_copy(
            update={"correlation_id": correlation_id, "latency_ms": latency_ms}
        ),
    )


def _elapsed_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1_000))
