"""Evaluation orchestration failures remain deterministic and bounded."""

import asyncio
import json
import logging
from datetime import date
from threading import Event
from time import monotonic, sleep
from typing import Any, cast

import pytest
from tests.integration.planner.test_planner_service import ScriptedHcx, _planners, _provider_plan

from finproof.answer.hcx_verbalizer import ProviderWordingError
from finproof.core.settings import ExecutionMode
from finproof.domain.answers import (
    AnswerRequest,
    AnswerResult,
    FactPack,
    PreparedAnswer,
    ProviderWording,
    SurfacePart,
    VerifiedAnswer,
)
from finproof.domain.execution import ExecutionTrace, TraceValidation, ValidatedQueryPlan
from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
from finproof.evidence import ClaimVerifier
from finproof.planner.hcx_client import HcxHttpError, HcxRateLimitError, HcxTransportError
from finproof.planner.rate_limits import HcxRateLimitSnapshot
from finproof.planner.service import PlannedQuery, PlannerAttemptSummary, PlannerService
from finproof.service.limits import RequestDeadline, RequestLimiter
from finproof.service.orchestrator import EvaluationOrchestrator
from finproof.service.publication import build_safe_publication


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
    async def plan(self, _: object, *, deadline: RequestDeadline) -> PlannedQuery:
        del deadline
        await asyncio.sleep(0.05)
        return _planned_query()


class ImmediatePlanner:
    async def plan(self, _: object, *, deadline: RequestDeadline) -> PlannedQuery:
        del deadline
        return _planned_query()


class ImmediateAnswerService:
    def prepare_plan(
        self, _: AnswerRequest, __: QueryPlan, deadline: RequestDeadline
    ) -> PreparedAnswer:
        del deadline
        return _prepared_answer()


class SlowAnswerService:
    def prepare_plan(
        self, _: AnswerRequest, __: QueryPlan, deadline: RequestDeadline
    ) -> PreparedAnswer:
        del deadline
        sleep(0.05)
        return _prepared_answer()


class FailingAnswerService:
    def prepare_plan(
        self, _: AnswerRequest, __: QueryPlan, deadline: RequestDeadline
    ) -> PreparedAnswer:
        del deadline
        raise RuntimeError("database failed")


class TransportFallbackPlanner:
    async def plan(self, _: object, *, deadline: RequestDeadline) -> PlannedQuery:
        del deadline
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

    async def plan(self, request: object, *, deadline: RequestDeadline) -> PlannedQuery:
        planning_request = cast(Any, request)
        self.deadline_at = deadline.work_cutoff_at
        self.result = await self._planner.plan(planning_request, deadline=deadline)
        return self.result


class BlockingAnswerService:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.finished = Event()
        self.calls = 0

    def prepare_plan(
        self, _: AnswerRequest, __: QueryPlan, deadline: RequestDeadline
    ) -> PreparedAnswer:
        del deadline
        self.calls += 1
        self.started.set()
        self.release.wait()
        self.finished.set()
        return _prepared_answer()


class InterruptibleBlockingAnswerService(BlockingAnswerService):
    def __init__(self) -> None:
        super().__init__()
        self.interrupted = Event()

    def interrupt(self) -> None:
        self.interrupted.set()
        self.release.set()


def _deadline(seconds: float = 293.0) -> RequestDeadline:
    started = monotonic()
    return RequestDeadline(
        started_at=started,
        work_cutoff_at=started + seconds,
        outer_at=started + seconds + 2.0,
        _clock=monotonic,
    )


async def _answer(
    orchestrator: EvaluationOrchestrator,
    deadline: RequestDeadline | None = None,
) -> AnswerResult:
    active = deadline or _deadline()
    return await orchestrator.answer(_request(), deadline=active, safe_result=_SAFE_RESULT)


def _safe_result(deadline: RequestDeadline) -> AnswerResult:
    return build_safe_publication(
        _request(),
        correlation_id="safe-test",
        snapshot_date=date(2026, 7, 11),
        deadline=deadline,
    ).result


_SAFE_RESULT = _safe_result(RequestDeadline.start(clock=lambda: 0.0))


@pytest.mark.asyncio
async def test_request_over_deadline_returns_verified_safe_failure() -> None:
    orchestrator = EvaluationOrchestrator(
        planner=SlowPlanner(),
        answer_service=ImmediateAnswerService(),
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=8),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await _answer(orchestrator, _deadline(0.02))

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert "처리" in result.answer.text


@pytest.mark.asyncio
async def test_database_work_over_deadline_returns_verified_safe_failure() -> None:
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=SlowAnswerService(),
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=8),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await _answer(orchestrator, _deadline(0.02))

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert "처리" in result.answer.text


@pytest.mark.asyncio
async def test_database_timeout_interrupts_sync_work() -> None:
    answer_service = InterruptibleBlockingAnswerService()
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=answer_service,
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=1),
        execution_mode=ExecutionMode.EVALUATION,
    )

    try:
        result = await _answer(orchestrator, _deadline(0.05))

        assert result.trace.validation is TraceValidation.SAFE_FAILURE
        assert answer_service.interrupted.is_set()
        assert await asyncio.to_thread(answer_service.finished.wait, 1.0)
    finally:
        answer_service.release.set()
        await asyncio.to_thread(answer_service.finished.wait, 1.0)
        await orchestrator.aclose()


@pytest.mark.asyncio
async def test_timed_out_worker_keeps_permit_until_sync_work_finishes() -> None:
    answer_service = BlockingAnswerService()
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=answer_service,
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=1),
        execution_mode=ExecutionMode.EVALUATION,
    )

    first = asyncio.create_task(_answer(orchestrator, _deadline(0.05)))
    await asyncio.to_thread(answer_service.started.wait)
    assert (await first).trace.validation is TraceValidation.SAFE_FAILURE

    second = asyncio.create_task(_answer(orchestrator))
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
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=1),
        execution_mode=ExecutionMode.EVALUATION,
    )

    first = asyncio.create_task(_answer(orchestrator, _deadline(1.0)))
    await asyncio.to_thread(answer_service.started.wait)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    second = asyncio.create_task(_answer(orchestrator))
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
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=1),
        execution_mode=ExecutionMode.EVALUATION,
    )

    request = asyncio.create_task(_answer(orchestrator, _deadline(0.2)))
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
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=8),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await _answer(orchestrator, _deadline(0.02))

    event = cast(dict[str, object], capture.records[-1].__dict__)
    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert cast(dict[str, int], event["stage_latency_ms"])["planner"] > 0
    assert event["error_category"] == "planner_timeout"


@pytest.mark.asyncio
async def test_database_timeout_records_elapsed_stage_and_category(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=SlowAnswerService(),
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=8),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await _answer(orchestrator, _deadline(0.02))

    event = cast(dict[str, object], capture.records[-1].__dict__)
    stage_latency = cast(dict[str, int], event["stage_latency_ms"])
    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert stage_latency["database"] > 0
    assert stage_latency["planner"] >= 0
    assert stage_latency["evidence"] == 0
    assert stage_latency["render"] == 0
    assert event["error_category"] == "database_timeout"


@pytest.mark.asyncio
async def test_database_failure_is_logged_as_its_own_category(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=FailingAnswerService(),
        verbalizer=IdentityVerbalizer(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await _answer(orchestrator)

    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "database_failure"
    )


@pytest.mark.asyncio
async def test_success_does_not_publish_stale_planner_fallback_metadata(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=TransportFallbackPlanner(),
        answer_service=ImmediateAnswerService(),
        verbalizer=IdentityVerbalizer(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await _answer(orchestrator)

    event = cast(dict[str, object], capture.records[-1].__dict__)
    assert event["error_category"] is None
    assert event["fallback"] is None


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
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=8),
        execution_mode=ExecutionMode.EVALUATION,
        snapshot_date=date(2026, 7, 11),
    )

    active_deadline = _deadline(1.0)
    await _answer(orchestrator, active_deadline)

    assert delays == [0.001]
    assert len(client.requests) == 2
    assert planner.result is not None
    assert planner.deadline_at == active_deadline.work_cutoff_at
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
        verbalizer=IdentityVerbalizer(),
        limiter=RequestLimiter(max_in_flight=8),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await _answer(orchestrator, _deadline(0.05))

    assert len(client.requests) == 1
    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "planner_provider_failure"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("responses", "category"),
    [
        (["not-json", "not-json"], "planner_repair_output_invalid"),
        ([HcxTransportError(), HcxTransportError()], "planner_retry_provider_failure"),
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
        verbalizer=IdentityVerbalizer(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await _answer(orchestrator)

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
        verbalizer=IdentityVerbalizer(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    await _answer(orchestrator)

    assert len(client.requests) == 1
    assert (
        cast(dict[str, object], capture.records[-1].__dict__)["error_category"]
        == "planner_semantic_invalid"
    )


def _prepared_answer() -> PreparedAnswer:
    result = _answer_result()
    text = result.answer.text
    fact_pack = FactPack(
        surface_parts=(
            SurfacePart(
                part_id="surface:answer",
                text=text,
                claim_ids=(),
                limitation_codes=("clarification_required",),
            ),
        ),
        claim_signatures=(),
        required_claim_ids=(),
        required_limitation_codes=("clarification_required",),
        evidence_context_sha256="0" * 64,
    )
    return PreparedAnswer(
        fact_pack=fact_pack,
        claims=(),
        trace=result.trace,
        retrieved_context=json.dumps(fact_pack.model_dump(mode="json")),
    )


class IdentityPlanner:
    def __init__(self) -> None:
        self.deadline: RequestDeadline | None = None

    async def plan(self, _: object, *, deadline: RequestDeadline) -> PlannedQuery:
        self.deadline = deadline
        return _planned_query()


class IdentityPreparationService:
    def __init__(self) -> None:
        self.deadline: RequestDeadline | None = None

    def prepare_plan(
        self, _: AnswerRequest, __: QueryPlan, deadline: RequestDeadline
    ) -> PreparedAnswer:
        self.deadline = deadline
        return _prepared_answer()


class IdentityVerbalizer:
    def __init__(self, *, invalid_first: bool = False) -> None:
        self.invalid_first = invalid_first
        self.deadlines: list[RequestDeadline] = []
        self.calls: list[str] = []

    async def verbalize(
        self, fact_pack: FactPack, *, request_id: str, deadline: RequestDeadline
    ) -> ProviderWording:
        del request_id
        self.calls.append("verbalize")
        self.deadlines.append(deadline)
        wording = _provider_wording(fact_pack)
        if self.invalid_first:
            raise ProviderWordingError("{}")
        return wording

    async def repair(
        self,
        fact_pack: FactPack,
        *,
        invalid_content: str,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording:
        del invalid_content, request_id
        self.calls.append("repair")
        self.deadlines.append(deadline)
        return _provider_wording(fact_pack)


class ScriptedVerbalizer(IdentityVerbalizer):
    def __init__(self, responses: list[ProviderWording | Exception]) -> None:
        super().__init__()
        self.responses = responses
        self.fact_packs: list[FactPack] = []
        self.request_ids: list[str] = []

    async def verbalize(
        self, fact_pack: FactPack, *, request_id: str, deadline: RequestDeadline
    ) -> ProviderWording:
        self.calls.append("verbalize")
        self.deadlines.append(deadline)
        self.fact_packs.append(fact_pack)
        self.request_ids.append(request_id)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def repair(
        self,
        fact_pack: FactPack,
        *,
        invalid_content: str,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording:
        del fact_pack, invalid_content, request_id, deadline
        self.calls.append("repair")
        raise AssertionError("transport retry must not open a repair call")


def _provider_wording(fact_pack: FactPack) -> ProviderWording:
    del fact_pack
    return ProviderWording(presentation="조회 결과입니다.")


@pytest.mark.asyncio
async def test_one_deadline_identity_reaches_every_answer_stage() -> None:
    deadline = RequestDeadline.start(clock=lambda: 0.0)
    planner = IdentityPlanner()
    answer_service = IdentityPreparationService()
    verbalizer = IdentityVerbalizer()
    orchestrator = EvaluationOrchestrator(
        planner=planner,
        answer_service=answer_service,
        verbalizer=verbalizer,
        verifier=ClaimVerifier(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request(), deadline=deadline, safe_result=_answer_result())

    assert result.answer.text == (
        f"조회 결과입니다.\n{_prepared_answer().fact_pack.surface_parts[0].text}"
    )
    assert planner.deadline is deadline
    assert answer_service.deadline is deadline
    assert verbalizer.deadlines == [deadline]


@pytest.mark.asyncio
async def test_invalid_wording_gets_one_repair_with_the_same_deadline() -> None:
    deadline = RequestDeadline.start(clock=lambda: 0.0)
    verbalizer = IdentityVerbalizer(invalid_first=True)
    orchestrator = EvaluationOrchestrator(
        planner=IdentityPlanner(),
        answer_service=IdentityPreparationService(),
        verbalizer=verbalizer,
        verifier=ClaimVerifier(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request(), deadline=deadline, safe_result=_answer_result())

    assert result.answer.text == (
        f"조회 결과입니다.\n{_prepared_answer().fact_pack.surface_parts[0].text}"
    )
    assert verbalizer.calls == ["verbalize", "repair"]
    assert verbalizer.deadlines == [deadline, deadline]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        HcxTransportError(),
        HcxHttpError(503),
        HcxRateLimitError("42900", HcxRateLimitSnapshot(reset_requests_seconds=0.0)),
    ],
)
async def test_retryable_wording_provider_failure_gets_one_identical_retry(
    error: Exception,
) -> None:
    deadline = _deadline(1.0)
    verbalizer = ScriptedVerbalizer([error, _provider_wording(_prepared_answer().fact_pack)])
    orchestrator = EvaluationOrchestrator(
        planner=IdentityPlanner(),
        answer_service=IdentityPreparationService(),
        verbalizer=verbalizer,
        verifier=ClaimVerifier(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request(), deadline=deadline, safe_result=_SAFE_RESULT)

    assert result.trace.validation is TraceValidation.CLARIFY
    assert verbalizer.calls == ["verbalize", "verbalize"]
    assert verbalizer.fact_packs[0] is verbalizer.fact_packs[1]
    assert verbalizer.request_ids[0] == verbalizer.request_ids[1]
    assert verbalizer.deadlines == [deadline, deadline]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        HcxHttpError(400),
        HcxRateLimitError("42900", HcxRateLimitSnapshot()),
        HcxRateLimitError("42900", HcxRateLimitSnapshot(reset_requests_seconds=60.0)),
    ],
)
async def test_nonretryable_wording_provider_failure_fails_closed(error: Exception) -> None:
    verbalizer = ScriptedVerbalizer([error])
    orchestrator = EvaluationOrchestrator(
        planner=IdentityPlanner(),
        answer_service=IdentityPreparationService(),
        verbalizer=verbalizer,
        verifier=ClaimVerifier(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await _answer(orchestrator, _deadline(0.05))

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert verbalizer.calls == ["verbalize"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "second_response",
    [
        HcxTransportError(),
        ProviderWordingError("{}"),
        _provider_wording(_prepared_answer().fact_pack).model_copy(
            update={"presentation": "임의 문구"}
        ),
    ],
)
async def test_retry_second_call_failure_or_invalid_wording_never_opens_repair(
    second_response: ProviderWording | Exception,
) -> None:
    verbalizer = ScriptedVerbalizer([HcxTransportError(), second_response])
    orchestrator = EvaluationOrchestrator(
        planner=IdentityPlanner(),
        answer_service=IdentityPreparationService(),
        verbalizer=verbalizer,
        verifier=ClaimVerifier(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await _answer(orchestrator)

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert verbalizer.calls == ["verbalize", "verbalize"]


@pytest.mark.asyncio
async def test_initial_local_wording_verification_failure_does_not_retry_or_repair() -> None:
    invalid = _provider_wording(_prepared_answer().fact_pack).model_copy(
        update={"presentation": "임의 문구"}
    )
    verbalizer = ScriptedVerbalizer([invalid])
    orchestrator = EvaluationOrchestrator(
        planner=IdentityPlanner(),
        answer_service=IdentityPreparationService(),
        verbalizer=verbalizer,
        verifier=ClaimVerifier(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await _answer(orchestrator)

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert verbalizer.calls == ["verbalize"]
