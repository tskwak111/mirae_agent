"""Organizer evaluation endpoint contract."""

import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from tests.integration.service.test_orchestrator_fallbacks import (
    IdentityVerbalizer,
    ImmediateAnswerService,
    ImmediatePlanner,
)

from finproof.api.app import create_app
from finproof.api.dependencies import AnswerOrchestrator, ApiDependencies
from finproof.core.settings import ExecutionMode, Settings
from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
from finproof.service.limits import RequestDeadline
from finproof.service.orchestrator import EvaluationOrchestrator


class StubOrchestrator:
    def __init__(self, *, failure: bool = False) -> None:
        self.failure = failure
        self.calls: list[AnswerRequest] = []
        self.deadlines: list[RequestDeadline] = []
        self.safe_results: list[AnswerResult] = []

    async def answer(
        self,
        request: AnswerRequest,
        *,
        deadline: RequestDeadline,
        safe_result: AnswerResult,
    ) -> AnswerResult:
        self.calls.append(request)
        self.deadlines.append(deadline)
        self.safe_results.append(safe_result)
        if self.failure:
            raise RuntimeError("/Users/example/secret-path")
        return AnswerResult(
            answer=VerifiedAnswer(text="결정적 답변", claims=()),
            retrieved_context="{}",
            trace=ExecutionTrace(
                correlation_id="service-correlation",
                intent=Intent.LOOKUP,
                product_types=(),
                as_of_date=date(2026, 7, 11),
                result_grain=ResultGrain.PRODUCT,
                top_k_scope=TopKScope.GLOBAL,
                segments=(),
                candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
                tools=("semantic_validator",),
                policy_ids=("answer:1.0.0",),
                validation=TraceValidation.PASSED,
                versions={},
                latency_ms={},
            ),
        )


class InvalidResultOrchestrator:
    def __init__(self, result: object) -> None:
        self._result = result

    async def answer(
        self,
        _: AnswerRequest,
        *,
        deadline: RequestDeadline,
        safe_result: AnswerResult,
    ) -> AnswerResult:
        del deadline, safe_result
        return cast(AnswerResult, self._result)


class DeterministicAnswerService:
    def answer_plan(self, _: AnswerRequest, __: QueryPlan) -> AnswerResult:
        return AnswerResult(
            answer=VerifiedAnswer(text="결정적 답변", claims=()),
            retrieved_context="{}",
            trace=_trace(),
        )


def _trace(*, versions: dict[str, str] | None = None) -> ExecutionTrace:
    return ExecutionTrace(
        correlation_id="service-correlation",
        intent=Intent.LOOKUP,
        product_types=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        top_k_scope=TopKScope.GLOBAL,
        segments=(),
        candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
        tools=("semantic_validator",),
        policy_ids=("answer:1.0.0",),
        validation=TraceValidation.PASSED,
        versions=versions or {},
        latency_ms={},
    )


def _client_for(orchestrator: AnswerOrchestrator) -> TestClient:
    @contextmanager
    def open_session(_: Settings) -> Generator[object, None, None]:
        yield object()

    return TestClient(
        create_app(
            Settings(execution_mode=ExecutionMode.EXTENDED_DEMO),
            dependencies=ApiDependencies(
                open_session=open_session,
                create_orchestrator=lambda _: orchestrator,
            ),
        ),
        raise_server_exceptions=False,
    )


@pytest.fixture
def stub_orchestrator() -> StubOrchestrator:
    return StubOrchestrator()


@pytest.fixture
def test_client(stub_orchestrator: StubOrchestrator) -> Generator[TestClient, None, None]:
    @contextmanager
    def open_session(_: Settings) -> Generator[object, None, None]:
        yield object()

    def create_orchestrator(_: object) -> AnswerOrchestrator:
        return stub_orchestrator

    app = create_app(
        Settings(execution_mode=ExecutionMode.EXTENDED_DEMO),
        dependencies=ApiDependencies(
            open_session=open_session,
            create_orchestrator=create_orchestrator,
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_answer_echoes_raw_request_and_returns_exact_schema(
    test_client: TestClient, stub_orchestrator: StubOrchestrator
) -> None:
    response = test_client.get(
        "/answer", params={"question_id": "Q-001", "question": "미국 ETF 총보수 알려줘"}
    )

    assert response.status_code == 200
    assert response.json()["question_id"] == "Q-001"
    assert response.json()["question"] == "미국 ETF 총보수 알려줘"
    assert set(response.json()) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert stub_orchestrator.calls[0] == AnswerRequest(
        question_id="Q-001", question="미국 ETF 총보수 알려줘"
    )
    assert (
        stub_orchestrator.deadlines[0].outer_at - stub_orchestrator.deadlines[0].started_at == 295
    )
    assert stub_orchestrator.safe_results[0].answer.text == "요청을 처리할 수 없습니다."
    trace = json.loads(response.json()["think_trace"])
    assert set(trace) == set(ExecutionTrace.model_fields)
    assert trace["correlation_id"] != "service-correlation"
    assert "prompt" not in trace
    assert "reasoning" not in trace
    assert response.content == canonical_json_bytes(response.json(), terminal_newline=False)


def test_api_orchestrator_trace_and_structured_log_share_one_correlation_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="finproof")
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=ImmediateAnswerService(),
        verbalizer=IdentityVerbalizer(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    with _client_for(orchestrator) as client:
        response = client.get(
            "/answer", params={"question_id": "Q-001", "question": "미국 ETF 총보수 알려줘"}
        )

    trace = json.loads(response.json()["think_trace"])
    event = cast(dict[str, object], caplog.records[-1].__dict__)
    assert response.status_code == 200
    assert trace["correlation_id"] == event["correlation_id"]


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/health/live",
        "/health/ready",
        "/ready",
        "/version",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/answer/",
    ],
)
def test_non_evaluation_routes_are_not_public(test_client: TestClient, path: str) -> None:
    assert test_client.get(path).status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"question_id": "Q"},
        {"question": "질문"},
        {"question_id": "q" * 201, "question": "질문"},
        {"question_id": "Q", "question": ""},
        {"question_id": "Q", "question": "x" * 4_001},
    ],
)
def test_answer_validation_failures_are_framework_422(
    test_client: TestClient, params: dict[str, str]
) -> None:
    response = test_client.get("/answer", params=params)

    assert response.status_code == 422
    assert len(response.content) < 4_000


def test_answer_internal_error_reuses_route_correlation_and_logs_redacted_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @contextmanager
    def open_session(_: Settings) -> Generator[object, None, None]:
        yield object()

    orchestrator = StubOrchestrator(failure=True)

    def create_orchestrator(_: object) -> AnswerOrchestrator:
        return orchestrator

    app = create_app(
        Settings(execution_mode=ExecutionMode.EXTENDED_DEMO),
        dependencies=ApiDependencies(
            open_session=open_session,
            create_orchestrator=create_orchestrator,
        ),
    )
    caplog.set_level(logging.ERROR, logger="finproof.api")
    question = "비공개 질문"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/answer", params={"question_id": "Q", "question": question})

    assert response.status_code == 500
    assert set(response.json()) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    correlation_id = json.loads(response.json()["think_trace"])["correlation_id"]
    assert len(caplog.records) == 1
    record = cast(dict[str, object], caplog.records[0].__dict__)
    assert record["correlation_id"] == correlation_id
    assert record["exception_type"] == "RuntimeError"
    assert "/Users/" not in caplog.text
    assert "RuntimeError" not in caplog.text
    assert question not in caplog.text


def test_pre_orchestrator_failure_logs_the_safe_response_correlation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @contextmanager
    def open_session(_: Settings) -> Generator[object, None, None]:
        yield object()

    app = create_app(
        Settings(execution_mode=ExecutionMode.EXTENDED_DEMO),
        dependencies=ApiDependencies(
            open_session=open_session,
            create_orchestrator=lambda _: cast(AnswerOrchestrator, object()),
        ),
    )
    caplog.set_level(logging.ERROR, logger="finproof.api")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/answer", params={"question_id": "Q", "question": "질문"})

    correlation_id = json.loads(response.json()["think_trace"])["correlation_id"]
    assert isinstance(correlation_id, str)
    assert correlation_id
    assert cast(dict[str, object], caplog.records[0].__dict__)["correlation_id"] == correlation_id


def test_lifespan_opens_before_orchestrator_and_closes_after_client_shutdown() -> None:
    events: list[str] = []

    @contextmanager
    def open_session(_: Settings) -> Generator[object, None, None]:
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    def create_orchestrator(_: object) -> AnswerOrchestrator:
        events.append("create")
        return StubOrchestrator()

    app = create_app(
        Settings(execution_mode=ExecutionMode.EXTENDED_DEMO),
        dependencies=ApiDependencies(
            open_session=open_session,
            create_orchestrator=create_orchestrator,
        ),
    )

    assert events == []
    with TestClient(app) as client:
        assert events == ["open", "create"]
        assert (
            client.get("/answer", params={"question_id": "Q", "question": "질문"}).status_code
            == 200
        )
    assert events == ["open", "create", "close"]


def test_lifespan_startup_failure_never_creates_orchestrator() -> None:
    events: list[str] = []

    @contextmanager
    def open_session(_: Settings, *, fail: bool = True) -> Generator[object, None, None]:
        events.append("open")
        if fail:
            raise RuntimeError("artifact verification failed")
        yield object()

    def create_orchestrator(_: object) -> AnswerOrchestrator:
        events.append("create")
        return StubOrchestrator()

    app = create_app(
        Settings(execution_mode=ExecutionMode.EXTENDED_DEMO),
        dependencies=ApiDependencies(
            open_session=open_session,
            create_orchestrator=create_orchestrator,
        ),
    )

    with pytest.raises(RuntimeError, match="artifact verification failed"), TestClient(app):
        pass
    assert events == ["open"]


@pytest.mark.asyncio
async def test_evaluation_dependency_requires_exact_hcx_007_model() -> None:
    settings = Settings(
        execution_mode=ExecutionMode.EVALUATION,
        hcx_enabled=True,
        hcx_api_key=SecretStr("test-key"),
        hcx_model_name="HCX-DASH-002",
    )

    with pytest.raises(RuntimeError, match="HCX-007"):
        async with ApiDependencies().open_orchestrator(object(), settings):
            raise AssertionError("invalid model must not open evaluation")


@pytest.mark.parametrize(
    ("result", "params"),
    [
        (
            SimpleNamespace(
                answer=SimpleNamespace(text="답변"), retrieved_context="x" * 24_001, trace=_trace()
            ),
            {"question_id": "Q", "question": "질문"},
        ),
        (
            SimpleNamespace(
                answer=SimpleNamespace(text="답변"),
                retrieved_context="{}",
                trace=_trace(versions={"x": "y" * 16_000}),
            ),
            {"question_id": "Q", "question": "질문"},
        ),
        (
            SimpleNamespace(
                answer=SimpleNamespace(text="x" * 12_001), retrieved_context="{}", trace=_trace()
            ),
            {"question_id": "Q", "question": "질문"},
        ),
        (
            SimpleNamespace(
                answer=SimpleNamespace(text="😀" * 12_000),
                retrieved_context="x" * 24_000,
                trace=_trace(versions={"x": "y" * 15_000}),
            ),
            {"question_id": "😀" * 200, "question": "😀" * 4_000},
        ),
    ],
    ids=["context", "trace", "answer", "whole-response"],
)
def test_oversized_orchestrator_output_fails_safely_with_exact_schema(
    result: object, params: dict[str, str]
) -> None:
    with _client_for(InvalidResultOrchestrator(result)) as client:
        response = client.get("/answer", params=params)

    assert response.status_code == 500
    assert set(response.json()) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
