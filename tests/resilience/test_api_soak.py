"""Duration-controlled representative API short soak."""

import asyncio
import gc
import json
import os
import tracemalloc
from pathlib import Path
from time import monotonic

import httpx
import pytest
from jsonschema import Draft202012Validator

from tests.e2e.test_evaluation_api import evaluation_app

_SECONDS = os.getenv("FINPROOF_SOAK_SECONDS")
_CASES = (
    ("lookup", "KR7000000000 추적오차 알려줘"),
    ("ranking", "국내 ETF 중 추적오차가 낮은 5개"),
    ("cross_product", "국내 ETF와 해외 ETF 각각 보여줘"),
    ("timeout", "국내 ETF만 보여줘 timeout"),
    ("rate_limit", "국내 ETF만 보여줘 429"),
    ("malformed", "국내 ETF만 보여줘 malformed"),
    ("fallback", "국내 ETF 미래 예측 fallback"),
)


def _plan(case: str) -> dict[str, object]:
    plan: dict[str, object] = {
        "intent": "screen",
        "product_types": ["domestic_etf"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "listed_product",
        "filters": [],
        "metrics": [],
        "sort": [],
        "aggregation": {"function": "none", "field": "", "group_by": []},
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }
    if case == "lookup":
        plan |= {
            "intent": "lookup",
            "entities": [{"text": "KR7000000000", "identifier_type": "product_id"}],
            "metrics": ["tracking_error"],
        }
    elif case == "ranking":
        plan |= {
            "intent": "screen_rank",
            "metrics": ["tracking_error"],
            "sort": [{"field": "tracking_error", "direction": "asc"}],
        }
    elif case == "cross_product":
        plan |= {
            "product_types": ["domestic_etf", "overseas_etf"],
            "top_k_scope": "per_product_type",
        }
    return plan


async def _recorded_resilience_hcx(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    question = next(
        message["content"] for message in payload["messages"] if message["role"] == "user"
    )
    case = next(name for name, marker in _CASES if marker == question)
    if case == "timeout":
        raise httpx.ReadTimeout("recorded timeout", request=request)
    if case == "rate_limit":
        return httpx.Response(
            429,
            json={"status": {"code": "42900", "message": "Too Many Requests"}},
        )
    if case in {"malformed", "fallback"}:
        return httpx.Response(200, content=b"not-json")
    return httpx.Response(
        200,
        json={
            "status": {"code": "20000", "message": "OK"},
            "result": {
                "message": {"role": "assistant", "content": json.dumps(_plan(case))},
                "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15},
            },
        },
    )


def _assert_contract(response: httpx.Response, validator: Draft202012Validator) -> None:
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
    assert all(type(value) is str for value in payload.values())


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.skipif(_SECONDS is None, reason="explicit short-soak duration required")
async def test_representative_traffic_has_no_contract_permit_or_memory_drift(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="finproof")
    assert _SECONDS is not None
    duration = float(_SECONDS)
    assert duration > 0
    app = evaluation_app(tmp_path, httpx.MockTransport(_recorded_resilience_hcx))
    validator = Draft202012Validator(
        json.loads(Path("schemas/api_response.schema.json").read_bytes())
    )
    seen = dict.fromkeys((name for name, _ in _CASES), 0)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        tracemalloc.start()
        gc.collect()
        baseline, _ = tracemalloc.get_traced_memory()
        started = monotonic()
        cycles = 0
        while monotonic() - started < duration:
            for case, question in _CASES:
                response = await client.get(
                    "/answer",
                    params={"question_id": f"SOAK-{cycles}-{case}", "question": question},
                )
                _assert_contract(response, validator)
                seen[case] += 1
            cycles += 1
        elapsed = monotonic() - started
        del response
        gc.collect()
        current, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        final_responses = await asyncio.gather(
            *(
                client.get(
                    "/answer",
                    params={
                        "question_id": f"PERMIT-{index}",
                        "question": "국내 ETF 중 추적오차가 낮은 5개",
                    },
                )
                for index in range(8)
            )
        )
        final_categories = [
            getattr(record, "error_category", None) for record in caplog.records[-8:]
        ]
        assert final_categories == [None] * 8, final_categories
        for response in final_responses:
            _assert_contract(response, validator)
            assert json.loads(response.json()["think_trace"])["validation"] == "passed"

    assert elapsed >= duration
    assert all(count > 0 for count in seen.values())
    assert current - baseline < 8_000_000
