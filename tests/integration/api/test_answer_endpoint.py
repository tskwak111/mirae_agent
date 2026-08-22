"""Organizer evaluation endpoint contract."""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finproof.api.app import create_app
from finproof.api.dependencies import AnswerOrchestrator, ApiDependencies
from finproof.core.settings import ExecutionMode, Settings
from finproof.domain.answers import AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import Intent, ResultGrain, TopKScope


class StubOrchestrator:
    def __init__(self, *, failure: bool = False) -> None:
        self.failure = failure
        self.calls: list[tuple[str, str, str]] = []

    async def answer(self, *, question_id: str, question: str, correlation_id: str) -> AnswerResult:
        self.calls.append((question_id, question, correlation_id))
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
        Settings(execution_mode=ExecutionMode.EVALUATION),
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
    assert stub_orchestrator.calls[0][:2] == ("Q-001", "미국 ETF 총보수 알려줘")
    assert "correlation_id" in response.json()["think_trace"]
    assert "service-correlation" not in response.json()["think_trace"]


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


def test_answer_internal_error_is_redacted_to_safe_five_fields() -> None:
    @contextmanager
    def open_session(_: Settings) -> Generator[object, None, None]:
        yield object()

    def create_orchestrator(_: object) -> AnswerOrchestrator:
        return StubOrchestrator(failure=True)

    app = create_app(
        Settings(),
        dependencies=ApiDependencies(
            open_session=open_session,
            create_orchestrator=create_orchestrator,
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/answer", params={"question_id": "Q", "question": "질문"})

    assert response.status_code == 500
    assert set(response.json()) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert "/Users/" not in response.text
    assert "RuntimeError" not in response.text
    assert "correlation_id" in response.json()["think_trace"]
