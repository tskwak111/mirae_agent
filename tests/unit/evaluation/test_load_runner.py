import hashlib
import json
import time
from pathlib import Path

import httpx
import pytest

from finproof.evaluation import load
from finproof.evaluation.load import LoadCase, LoadConfig, LoadRunner, reviewed_suite_mix


def _write_blind_suite_fixture(root: Path) -> list[dict[str, object]]:
    template = json.loads(
        Path("evaluation/canonical/rank.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    cases = [
        {
            **template,
            "case_id": f"CQ-{batch:03d}-{number:03d}",
            "question": f"blind {batch:03d} {number:03d}",
        }
        for batch in range(12, 18)
        for number in range(1, 25)
    ]
    path = root / "evaluation/blind_development/rank.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )
    return cases


def test_reviewed_suite_mix_uses_every_blind_case_once(tmp_path: Path) -> None:
    cases = _write_blind_suite_fixture(tmp_path)

    mix = reviewed_suite_mix(tmp_path, "blind_development")

    assert [case.case_id for case in mix] == [case["case_id"] for case in cases]
    assert {case.weight for case in mix} == {1}


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
                "latency_ms": {
                    "planner": 1,
                    "database": 2,
                    "evidence": 1,
                    "render": 1,
                    "wording": 3,
                },
            }
        ),
        "answer": "검증된 답변",
    }
    return httpx.Response(200, json=payload)


def test_load_client_waits_through_the_official_physical_response_boundary() -> None:
    config = LoadConfig(
        base_url="http://test",
        cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup"),),
        duration_seconds=60,
    )

    assert config.request_timeout_seconds == 300


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
        "wording": 3,
    }
    assert report.samples[0].answer_sha256 == hashlib.sha256("검증된 답변".encode()).hexdigest()
    assert "검증된 답변" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_load_runner_hashes_both_allowed_presentations_as_one_material_answer() -> None:
    answers = iter(("조회 결과입니다.\n동일 본문", "확인 결과입니다.\n동일 본문"))

    def response(request: httpx.Request) -> httpx.Response:
        payload = _response(request).json()
        payload["answer"] = next(answers)
        return httpx.Response(200, json=payload)

    report = await LoadRunner(transport=httpx.MockTransport(response)).run(
        LoadConfig(
            base_url="http://test",
            cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup", weight=2),),
            duration_seconds=60,
            max_requests=2,
        )
    )

    assert {sample.answer_sha256 for sample in report.samples} == {
        hashlib.sha256("동일 본문".encode()).hexdigest()
    }


@pytest.mark.asyncio
async def test_load_runner_material_hash_still_changes_when_surface_changes() -> None:
    answers = iter(("조회 결과입니다.\n본문 A", "확인 결과입니다.\n본문 B"))

    def response(request: httpx.Request) -> httpx.Response:
        payload = _response(request).json()
        payload["answer"] = next(answers)
        return httpx.Response(200, json=payload)

    report = await LoadRunner(transport=httpx.MockTransport(response)).run(
        LoadConfig(
            base_url="http://test",
            cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup", weight=2),),
            duration_seconds=60,
            max_requests=2,
        )
    )

    assert len({sample.answer_sha256 for sample in report.samples}) == 2


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


@pytest.mark.asyncio
async def test_load_runner_does_not_start_rate_limited_work_after_deadline() -> None:
    requests = 0

    def response(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return _response(request)

    config = LoadConfig(
        base_url="http://test",
        cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup"),),
        concurrency=2,
        rate_per_second=20,
        duration_seconds=0.01,
        max_requests=2,
    )

    report = await LoadRunner(transport=httpx.MockTransport(response)).run(config)

    assert report.request_count == requests == 1


@pytest.mark.asyncio
async def test_load_runner_counts_schema_valid_safe_failure_as_failed_request() -> None:
    def safe_failure(request: httpx.Request) -> httpx.Response:
        response = _response(request)
        payload = response.json()
        trace = json.loads(payload["think_trace"])
        trace["validation"] = "safe_failure"
        payload["think_trace"] = json.dumps(trace)
        return httpx.Response(200, json=payload)

    config = LoadConfig(
        base_url="http://test",
        cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup"),),
        duration_seconds=60,
        max_requests=1,
    )

    report = await LoadRunner(transport=httpx.MockTransport(safe_failure)).run(config)

    assert report.success_count == 0
    assert report.failure_count == 1
    assert report.samples[0].response_schema_valid
    assert not report.samples[0].request_succeeded
    assert report.samples[0].error_category == "safe_failure"


@pytest.mark.asyncio
async def test_load_runner_accepts_the_published_empty_latency_safe_failure() -> None:
    def safe_failure(request: httpx.Request) -> httpx.Response:
        response = _response(request)
        payload = response.json()
        trace = json.loads(payload["think_trace"])
        trace["validation"] = "safe_failure"
        trace["latency_ms"] = {}
        payload["think_trace"] = json.dumps(trace)
        return httpx.Response(200, json=payload)

    config = LoadConfig(
        base_url="http://test",
        cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup"),),
        duration_seconds=60,
        max_requests=1,
    )

    report = await LoadRunner(transport=httpx.MockTransport(safe_failure)).run(config)

    assert report.samples[0].response_schema_valid
    assert report.samples[0].stage_ms == {}
    assert report.samples[0].error_category == "safe_failure"


def test_load_cli_forwards_an_explicit_request_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExpectedStop(Exception):
        pass

    async def stop_after_config(_: LoadRunner, config: LoadConfig) -> None:
        assert config.max_requests == 4
        raise ExpectedStop

    monkeypatch.setattr(LoadRunner, "run", stop_after_config)

    with pytest.raises(ExpectedStop):
        load.main(
            [
                "--base-url",
                "http://test",
                "--duration-seconds",
                "60",
                "--max-requests",
                "4",
            ]
        )
