"""Bounded in-process load acceptance for the production application graph."""

import asyncio
import json
import os
from pathlib import Path
from time import monotonic

import httpx
import pytest
from jsonschema import Draft202012Validator

from tests.e2e.test_evaluation_api import _recorded_hcx, evaluation_app


@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("FINPROOF_RUN_API_LOAD") != "1",
    reason="explicit bounded API load selector required",
)
async def test_eight_concurrent_requests_keep_verified_contract_and_stage_latency(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="finproof")
    app = evaluation_app(tmp_path, httpx.MockTransport(_recorded_hcx))
    schema = json.loads(Path("schemas/api_response.schema.json").read_bytes())
    validator = Draft202012Validator(schema)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        started = monotonic()
        responses = await asyncio.gather(
            *(
                client.get(
                    "/answer",
                    params={
                        "question_id": f"LOAD-{index}",
                        "question": "국내 ETF 중 추적오차가 낮은 5개",
                    },
                )
                for index in range(8)
            )
        )
        elapsed = monotonic() - started

    categories = [getattr(record, "error_category", None) for record in caplog.records]
    assert categories == [None] * 8, categories
    correlation_ids = set()
    for response in responses:
        assert response.status_code == 200
        payload = response.json()
        validator.validate(payload)
        assert set(payload) == {
            "question_id",
            "question",
            "retrieved_context",
            "think_trace",
            "answer",
        }
        trace = json.loads(payload["think_trace"])
        context = json.loads(payload["retrieved_context"])
        assert trace["validation"] == "passed"
        assert set(trace["latency_ms"]) == {"planner", "database", "evidence", "render"}
        assert all(type(value) is int and value >= 0 for value in trace["latency_ms"].values())
        assert context["direct"]
        correlation_ids.add(trace["correlation_id"])
    assert len(responses) == len(correlation_ids) == 8
    assert elapsed < 15
