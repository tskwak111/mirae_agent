import hashlib
import json
import time

import httpx
import pytest

from finproof.evaluation.load import LoadCase, LoadConfig, LoadRunner


def _response(request: httpx.Request) -> httpx.Response:
    time.sleep(0.003)
    question_id = request.url.params["question_id"]
    payload = {
        "question_id": question_id,
        "question": request.url.params["question"],
        "retrieved_context": "{}",
        "think_trace": json.dumps(
            {
                "correlation_id": question_id,
                "intent": "screen",
                "product_types": ["domestic_etf"],
                "as_of_date": "2026-07-11",
                "result_grain": "listed_product",
                "top_k_scope": "global",
                "segments": [],
                "candidate_counts": {},
                "tools": ["claim_verifier"],
                "policy_ids": [],
                "validation": "passed",
                "versions": {"dataset_version": "2026-07-11"},
                "latency_ms": {"planner": 1, "database": 2, "evidence": 1, "render": 1},
            }
        ),
        "answer": "검증된 답변",
    }
    return httpx.Response(200, json=payload)


@pytest.mark.asyncio
async def test_load_runner_records_safe_schema_latency_and_answer_hash() -> None:
    config = LoadConfig(
        base_url="http://test",
        cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup"),),
        concurrency=2,
        rate_per_second=0,
        duration_seconds=60,
        max_requests=2,
    )

    report = await LoadRunner(transport=httpx.MockTransport(_response)).run(config)

    assert report.request_count == 2
    assert report.success_count == 2
    assert report.failure_count == 0
    assert report.latency.count == 2
    assert report.samples[0].question_type == "lookup"
    assert report.samples[0].response_schema_valid
    assert report.samples[0].stage_ms == {
        "planner": 1,
        "database": 2,
        "evidence": 1,
        "render": 1,
    }
    assert report.samples[0].answer_sha256 == hashlib.sha256("검증된 답변".encode()).hexdigest()
    assert "검증된 답변" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_load_runner_counts_http_and_schema_failures_without_response_body() -> None:
    def failure(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="secret internal stack trace")

    config = LoadConfig(
        base_url="http://test",
        cases=(LoadCase(case_id="rank", question="질문", question_type="rank"),),
        duration_seconds=60,
        max_requests=1,
    )

    report = await LoadRunner(transport=httpx.MockTransport(failure)).run(config)

    assert report.success_count == 0
    assert report.failure_count == 1
    assert report.samples[0].status_code == 500
    assert not report.samples[0].response_schema_valid
    assert report.samples[0].answer_sha256 is None
    assert "secret internal stack trace" not in report.model_dump_json()
