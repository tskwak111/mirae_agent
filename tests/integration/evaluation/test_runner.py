from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from finproof.domain.query_plan import (
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.evaluation.loader import suite_checksum
from finproof.evaluation.models import GoldenCase, ObservedCase
from finproof.evaluation.runner import EvaluationMode, EvaluationRunner, ReplayVersions


def _case() -> GoldenCase:
    return GoldenCase.model_validate(
        {
            "case_id": "BOND-LOOKUP-001",
            "category": "lookup",
            "question": "채권 A",
            "expected_plan": {
                "intent": "lookup",
                "product_types": ["domestic_bond"],
                "as_of_date": "2026-07-11",
                "result_grain": "instrument",
                "top_k_scope": "global",
            },
            "expected_result": {"product_ids": ["A"]},
            "expected_answer": {
                "required_concepts": ["2026-07-11"],
                "forbidden_concepts": ["실시간"],
            },
            "review": {
                "reviewer": "human",
                "reviewed_at": "2026-08-20",
                "source": "reference-engine",
            },
        }
    )


def _plan() -> QueryPlan:
    return QueryPlan(
        intent=Intent.LOOKUP,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )


def test_code_commit_reads_symbolic_head_without_a_subprocess(tmp_path: Path) -> None:
    from finproof.evaluation.runner import _code_commit

    commit = "b" * 40
    git_dir = tmp_path / ".git"
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "refs" / "heads" / "main").write_text(commit + "\n", encoding="utf-8")

    assert _code_commit(tmp_path) == commit


@pytest.mark.parametrize("mode", tuple(EvaluationMode))
def test_runner_records_replay_metadata_and_ratio_aggregates(mode: EvaluationMode) -> None:
    case = _case()
    calls: list[tuple[str, EvaluationMode]] = []

    class Service:
        def replay_versions(self) -> ReplayVersions:
            return ReplayVersions(
                artifact_version="artifact-sha256",
                config_versions={"metric": "1.0.0", "state": "1.1.0"},
                prompt_version="prompt-1.0.0",
                planner_version="planner-1.0.0",
            )

        def observe(self, observed_case: GoldenCase, observed_mode: EvaluationMode) -> ObservedCase:
            calls.append((observed_case.case_id, observed_mode))
            return ObservedCase(
                plan=_plan(),
                product_ids=("A",),
                answer_text="2026-07-11 기준",
                repeat_signatures=("same", "same"),
                latency_ms=(12,),
            )

    instants = iter(
        (
            datetime(2026, 8, 24, 1, 2, 3, tzinfo=UTC),
            datetime(2026, 8, 24, 1, 2, 4, tzinfo=UTC),
        )
    )
    report = EvaluationRunner(
        mode=mode,
        clock=lambda: next(instants),
        code_commit=lambda: "a" * 40,
        environment=lambda: {"python": "3.12", "platform": "test"},
    ).run((case,), Service())

    assert calls == [(case.case_id, mode)]
    assert report.replay.code_commit == "a" * 40
    assert report.replay.case_checksum == suite_checksum((case,))
    assert report.replay.started_at < report.replay.ended_at
    assert report.replay.artifact_version == "artifact-sha256"
    assert report.replay.config_versions == {"metric": "1.0.0", "state": "1.1.0"}
    assert report.replay.environment["python"] == "3.12"
    assert report.case_scores[0].case_id == case.case_id
    if mode is EvaluationMode.PLAN_ONLY:
        assert report.aggregates["product_set"].denominator == 0
        assert report.aggregates["answer_semantics"].denominator == 0
    else:
        assert report.aggregates["product_set"].numerator == 2
        assert report.aggregates["product_set"].denominator == 2
    assert report.latency is not None
    assert report.latency.p95_ms == 12
    assert report.model_dump_json()
