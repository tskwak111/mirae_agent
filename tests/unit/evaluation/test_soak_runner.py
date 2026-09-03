import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from finproof.evaluation import soak
from finproof.evaluation.load import LoadCase
from finproof.evaluation.soak import SoakConfig, SoakReport, SoakRunner


def _trace() -> str:
    return json.dumps(
        {
            "correlation_id": "soak",
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
            "versions": {"dataset_version": "2026-07-11", "code_commit": "a" * 40},
            "latency_ms": {
                "planner": 0,
                "database": 0,
                "evidence": 0,
                "render": 0,
                "wording": 0,
            },
        }
    )


def test_soak_client_waits_through_the_official_physical_response_boundary(
    tmp_path: Path,
) -> None:
    config = SoakConfig(
        base_url="http://test",
        cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup"),),
        duration_seconds=60,
        interval_seconds=1,
        report_path=tmp_path / "soak.json",
    )

    assert config.request_timeout_seconds == 300


def test_soak_cli_forwards_an_explicit_cycle_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExpectedStop(Exception):
        pass

    async def stop_after_config(_: SoakRunner, config: SoakConfig) -> None:
        assert config.max_cycles == 1_440
        raise ExpectedStop

    monkeypatch.setattr(SoakRunner, "run", stop_after_config)

    with pytest.raises(ExpectedStop):
        soak.main(
            [
                "--base-url",
                "http://test",
                "--hours",
                "24",
                "--max-cycles",
                "1440",
            ]
        )


@pytest.mark.asyncio
async def test_soak_runner_resumes_and_detects_drift_only_within_one_version(
    tmp_path: Path,
) -> None:
    answers = iter(("기준 답변", "변경 답변"))

    def response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "question_id": request.url.params["question_id"],
                "question": request.url.params["question"],
                "retrieved_context": "{}",
                "think_trace": _trace(),
                "answer": next(answers),
            },
        )

    report_path = tmp_path / "soak.json"
    runner = SoakRunner(transport=httpx.MockTransport(response))

    def config(max_cycles: int) -> SoakConfig:
        return SoakConfig(
            base_url="http://test",
            cases=(LoadCase(case_id="lookup", question="질문", question_type="lookup"),),
            duration_seconds=60,
            interval_seconds=0,
            report_path=report_path,
            max_cycles=max_cycles,
        )

    first = await runner.run(config(1))
    stale = first.model_copy(
        update={
            "started_at": datetime(2000, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2000, 1, 1, tzinfo=UTC),
        }
    )
    report_path.write_text(stale.model_dump_json(), encoding="utf-8")
    resumed = await runner.run(config(2))

    assert first.cycles_completed == 1
    assert resumed.cycles_completed == 2
    assert resumed.active_seconds < 60
    assert resumed.drift_count == 1
    assert len(resumed.observations) == 2
    assert SoakReport.model_validate_json(report_path.read_text()) == resumed
    assert "기준 답변" not in report_path.read_text()
    assert "변경 답변" not in report_path.read_text()
    assert not report_path.with_name(".soak.json.tmp").exists()


@pytest.mark.asyncio
async def test_soak_cycle_runs_each_weighted_case_once(tmp_path: Path) -> None:
    def response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "question_id": request.url.params["question_id"],
                "question": request.url.params["question"],
                "retrieved_context": "{}",
                "think_trace": _trace(),
                "answer": "검증된 답변",
            },
        )

    cases = tuple(
        LoadCase(
            case_id=f"case-{index}",
            question=f"질문 {index}",
            question_type="representative",
            weight=weight,
        )
        for index, weight in enumerate((4, 3, 2, 1), 1)
    )
    report = await SoakRunner(transport=httpx.MockTransport(response)).run(
        SoakConfig(
            base_url="http://test",
            cases=cases,
            duration_seconds=60,
            interval_seconds=0,
            report_path=tmp_path / "soak.json",
            max_cycles=1,
        )
    )

    assert tuple(item.case_id for item in report.observations) == tuple(
        case.case_id for case in cases
    )
