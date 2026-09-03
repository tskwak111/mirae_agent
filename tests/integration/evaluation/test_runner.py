from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import (
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.evaluation.loader import suite_checksum
from finproof.evaluation.models import GoldenCase, ObservedCase, ProductIdentity
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
            "expected_result": {
                "products": [
                    {
                        "product_type": "domestic_bond",
                        "native_result_grain": "instrument",
                        "product_id": "A",
                    }
                ]
            },
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


def _versions() -> ReplayVersions:
    return ReplayVersions.from_configuration(
        artifact_version="artifact-sha256",
        config_versions={"metric": "1.0.0", "state": "1.1.0"},
        prompt_version="prompt-1.0.0",
        answer_prompt_version=None,
        answer_schema_sha256=None,
        wording_verification_mode=None,
        planner_version="planner-1.0.0",
        execution_mode=ExecutionMode.EXTENDED_DEMO,
        hcx_enabled=False,
        planner_model=None,
        fallback_enabled=True,
        structured_outputs_enabled=False,
    )


def test_code_commit_reads_symbolic_head_without_a_subprocess(tmp_path: Path) -> None:
    from finproof.evaluation.runner import _code_commit

    commit = "b" * 40
    git_dir = tmp_path / ".git"
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "refs" / "heads" / "main").write_text(commit + "\n", encoding="utf-8")

    assert _code_commit(tmp_path) == commit


def test_replay_versions_label_fallback_only_and_hash_actual_configuration() -> None:
    first = ReplayVersions.from_configuration(
        artifact_version="artifact-sha256",
        config_versions={"state": "1.1.0", "metric": "1.0.0"},
        prompt_version="prompt-1.0.0",
        answer_prompt_version=None,
        answer_schema_sha256=None,
        wording_verification_mode=None,
        planner_version="planner-1.0.0",
        execution_mode=ExecutionMode.EXTENDED_DEMO,
        hcx_enabled=False,
        planner_model=None,
        fallback_enabled=True,
        structured_outputs_enabled=False,
    )
    reordered = ReplayVersions.from_configuration(
        artifact_version="artifact-sha256",
        config_versions={"metric": "1.0.0", "state": "1.1.0"},
        prompt_version="prompt-1.0.0",
        answer_prompt_version=None,
        answer_schema_sha256=None,
        wording_verification_mode=None,
        planner_version="planner-1.0.0",
        execution_mode=ExecutionMode.EXTENDED_DEMO,
        hcx_enabled=False,
        planner_model=None,
        fallback_enabled=True,
        structured_outputs_enabled=False,
    )
    hcx = ReplayVersions.from_configuration(
        artifact_version="artifact-sha256",
        config_versions={"metric": "1.0.0", "state": "1.1.0"},
        prompt_version="prompt-1.0.0",
        answer_prompt_version="answer-prompt-v1",
        answer_schema_sha256="a" * 64,
        wording_verification_mode="allowlisted-presentation-plus-exact-surface-v1",
        planner_version="planner-1.0.0",
        execution_mode=ExecutionMode.EVALUATION,
        hcx_enabled=True,
        planner_model="HCX-007",
        fallback_enabled=False,
        structured_outputs_enabled=True,
    )

    assert first.planner_mode == "fallback-only"
    assert first.planner_provider == "local-rule-fallback"
    assert first.planner_model is None
    assert first.configuration_sha256 == reordered.configuration_sha256
    assert hcx.planner_mode == "hcx-structured-outputs-verified-wording"
    assert hcx.planner_provider == "naver-hyperclova-x"
    assert hcx.configuration_sha256 != first.configuration_sha256


def test_evaluation_replay_requires_both_hcx_stages_without_fallback() -> None:
    versions = ReplayVersions.from_configuration(
        artifact_version="artifact-sha256",
        config_versions={"metric": "1.0.0"},
        prompt_version="planner-prompt-v1",
        answer_prompt_version="answer-prompt-v1",
        answer_schema_sha256="a" * 64,
        wording_verification_mode="allowlisted-presentation-plus-exact-surface-v1",
        planner_version="planner-1.0.0",
        execution_mode=ExecutionMode.EVALUATION,
        hcx_enabled=True,
        planner_model="HCX-007",
        fallback_enabled=False,
        structured_outputs_enabled=True,
    )

    assert versions.planner_mode == "hcx-structured-outputs-verified-wording"
    assert versions.execution_mode is ExecutionMode.EVALUATION
    assert versions.answer_prompt_version == "answer-prompt-v1"
    assert versions.answer_schema_sha256 == "a" * 64
    with pytest.raises(ValueError, match="evaluation"):
        ReplayVersions.from_configuration(
            artifact_version="artifact-sha256",
            config_versions={"metric": "1.0.0"},
            prompt_version="planner-prompt-v1",
            answer_prompt_version="answer-prompt-v1",
            answer_schema_sha256="a" * 64,
            wording_verification_mode="allowlisted-presentation-plus-exact-surface-v1",
            planner_version="planner-1.0.0",
            execution_mode=ExecutionMode.EVALUATION,
            hcx_enabled=False,
            planner_model=None,
            fallback_enabled=True,
            structured_outputs_enabled=False,
        )

    with pytest.raises(ValueError, match="structured"):
        ReplayVersions.from_configuration(
            artifact_version="artifact-sha256",
            config_versions={"metric": "1.0.0"},
            prompt_version="planner-prompt-v1",
            answer_prompt_version="answer-prompt-v1",
            answer_schema_sha256="a" * 64,
            wording_verification_mode="allowlisted-presentation-plus-exact-surface-v1",
            planner_version="planner-1.0.0",
            execution_mode=ExecutionMode.EVALUATION,
            hcx_enabled=True,
            planner_model="HCX-007",
            fallback_enabled=False,
            structured_outputs_enabled=False,
        )

    with pytest.raises(ValueError, match="verified wording identities"):
        ReplayVersions.from_configuration(
            artifact_version="artifact-sha256",
            config_versions={"metric": "1.0.0"},
            prompt_version="planner-prompt-v1",
            answer_prompt_version="answer-prompt-v1",
            answer_schema_sha256="a" * 64,
            wording_verification_mode="exact-application-surface-v1",
            planner_version="planner-1.0.0",
            execution_mode=ExecutionMode.EVALUATION,
            hcx_enabled=True,
            planner_model="HCX-007",
            fallback_enabled=False,
            structured_outputs_enabled=True,
        )


def test_code_commit_resolves_linked_worktree_commondir_and_packed_refs(
    tmp_path: Path,
) -> None:
    from finproof.evaluation.runner import _code_commit

    commit = "c" * 40
    repository = tmp_path / "worktree"
    common = tmp_path / "common.git"
    worktree_git = common / "worktrees" / "evaluation"
    repository.mkdir()
    worktree_git.mkdir(parents=True)
    (repository / ".git").write_text(
        "gitdir: ../common.git/worktrees/evaluation\n", encoding="utf-8"
    )
    (worktree_git / "HEAD").write_text("ref: refs/heads/evaluation\n", encoding="utf-8")
    (worktree_git / "commondir").write_text("../..\n", encoding="utf-8")
    (common / "packed-refs").write_text(
        f"# pack-refs with: peeled fully-peeled sorted\n{commit} refs/heads/evaluation\n",
        encoding="utf-8",
    )

    assert _code_commit(repository) == commit


def test_runner_captures_commit_before_versions_and_observations() -> None:
    events: list[str] = []

    class Service:
        def replay_versions(self) -> ReplayVersions:
            events.append("versions")
            return _versions()

        def observe(self, _case: GoldenCase, _mode: EvaluationMode) -> ObservedCase:
            events.append("observe")
            return ObservedCase(plan=_plan())

    def code_commit() -> str:
        events.append("commit")
        return "a" * 40

    EvaluationRunner(
        code_commit=code_commit,
        environment=lambda: {"python": "3.12"},
    ).run((_case(),), Service())

    assert events == ["commit", "versions", "observe"]


@pytest.mark.parametrize("mode", tuple(EvaluationMode))
def test_runner_records_replay_metadata_and_ratio_aggregates(mode: EvaluationMode) -> None:
    case = _case()
    calls: list[tuple[str, EvaluationMode]] = []

    class Service:
        def replay_versions(self) -> ReplayVersions:
            return _versions()

        def observe(self, observed_case: GoldenCase, observed_mode: EvaluationMode) -> ObservedCase:
            calls.append((observed_case.case_id, observed_mode))
            return ObservedCase(
                plan=_plan(),
                products=(
                    ProductIdentity(
                        product_type=ProductType.DOMESTIC_BOND,
                        native_result_grain=ResultGrain.INSTRUMENT,
                        product_id="A",
                    ),
                ),
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
