import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from time import monotonic

import httpx
import pytest
from tests.e2e.test_evaluation_api import evaluation_app
from tests.integration.service.test_orchestrator_fallbacks import (
    FailingAnswerService,
    ImmediatePlanner,
    _request,
)

from finproof.api.app import create_app
from finproof.api.dependencies import ApiDependencies
from finproof.core.settings import ExecutionMode, Settings
from finproof.domain.execution import TraceValidation
from finproof.service.orchestrator import EvaluationOrchestrator


def _fault_handler(fault: str) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if fault == "timeout":
            raise httpx.ReadTimeout("private timeout detail", request=request)
        if fault == "429":
            return httpx.Response(
                429,
                json={"status": {"code": "42900", "message": "private quota detail"}},
            )
        if fault == "malformed_json":
            return httpx.Response(200, content=b"private-not-json")
        raise httpx.ConnectError("private DNS detail", request=request)

    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["timeout", "429", "malformed_json", "connection_error"])
async def test_fault_path_is_bounded_and_returns_safe_contract(
    fault: str,
    tmp_path: Path,
) -> None:
    app = evaluation_app(tmp_path, httpx.MockTransport(_fault_handler(fault)))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        started = monotonic()
        response = await client.get(
            "/answer",
            params={"question_id": f"FAULT-{fault}", "question": "국내 ETF 5개 보여줘"},
        )
        elapsed_seconds = monotonic() - started

    assert elapsed_seconds < 15.1
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert all(type(value) is str for value in payload.values())
    assert all(
        marker not in response.text.lower()
        for marker in ("private", "traceback", "readtimeout", "connecterror")
    )


@pytest.mark.asyncio
async def test_database_read_failure_returns_verified_safe_contract() -> None:
    orchestrator = EvaluationOrchestrator(
        planner=ImmediatePlanner(),
        answer_service=FailingAnswerService(),
        execution_mode=ExecutionMode.EVALUATION,
    )

    result = await orchestrator.answer(_request())

    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert "database failed" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_duckdb_open_failure_prevents_readiness() -> None:
    class FailedOpen(AbstractContextManager[object]):
        def __enter__(self) -> object:
            raise OSError("injected DuckDB open failure")

        def __exit__(self, *args: object) -> None:
            return None

    def failed_open(_: Settings) -> AbstractContextManager[object]:
        return FailedOpen()

    app = create_app(dependencies=ApiDependencies(open_session=failed_open))

    with pytest.raises(OSError, match="injected DuckDB open failure"):
        async with app.router.lifespan_context(app):
            raise AssertionError("startup must not become ready")


@pytest.mark.asyncio
async def test_process_restart_reopens_runtime_and_keeps_only_answer_public(tmp_path: Path) -> None:
    for restart in range(2):
        runtime_root = tmp_path / str(restart)
        runtime_root.mkdir()
        app = evaluation_app(
            runtime_root,
            httpx.MockTransport(lambda _: httpx.Response(500)),
            hcx_enabled=False,
        )
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            response = await client.get(
                "/answer",
                params={"question_id": f"RESTART-{restart}", "question": "국내 ETF 5개 보여줘"},
            )
            version = await client.get("/version")

        assert response.status_code == 200
        assert json.loads(response.json()["think_trace"])["validation"] == "passed"
        assert version.status_code == 404
