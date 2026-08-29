"""Focused authoring checks for the approved August organizer suite."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools import build_organizer_reference_packet as authoring

from finproof.core.settings import ExecutionMode, Settings
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import Intent, QueryPlan

_ROOT = Path(__file__).resolve().parents[3]
_REVIEW = _ROOT / "evaluation/organizer_20260824/review"


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repository = tmp_path / "repository"
    review = repository / "evaluation/organizer_20260824/review"
    review.mkdir(parents=True)
    packet = review / "question-plan-review-v1.json"
    approval = review / "question-plan-approval-v1.json"
    packet.write_bytes((_REVIEW / packet.name).read_bytes())
    approval.write_bytes((_REVIEW / approval.name).read_bytes())
    return repository, packet, approval, review / "expected-review-v1.json"


def _answer(request: AnswerRequest, plan: QueryPlan) -> AnswerResult:
    validation = (
        TraceValidation.CLARIFY
        if plan.intent is Intent.CLARIFY
        else TraceValidation.UNSUPPORTED
        if plan.intent is Intent.UNSUPPORTED
        else TraceValidation.PASSED
    )
    return AnswerResult(
        answer=VerifiedAnswer(text=f"{request.question_id} 검토 답변", claims=()),
        retrieved_context="{}",
        trace=ExecutionTrace(
            correlation_id=request.question_id,
            intent=plan.intent,
            product_types=plan.product_types,
            as_of_date=plan.as_of_date,
            result_grain=plan.result_grain,
            top_k_scope=plan.top_k_scope,
            segments=(),
            candidate_counts={},
            tools=(),
            policy_ids=(),
            validation=validation,
            versions={"dataset_version": "2026-08-24"},
            latency_ms={"database": 1},
        ),
    )


def test_builds_35_case_reference_bound_to_approval_code_and_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, packet, approval, output = _workspace(tmp_path)
    session = SimpleNamespace(
        verified_artifacts=SimpleNamespace(
            artifact_set_id="finproof-data-artifacts/v1",
            artifact_contract_version="1.0.0",
            dataset_version=date(2026, 8, 24),
            overall_manifest_logical_hash="977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8",
        )
    )

    @contextmanager
    def open_session(settings: Settings) -> Iterator[SimpleNamespace]:
        assert settings.execution_mode is ExecutionMode.EXTENDED_DEMO
        yield session

    class Service:
        def __init__(self, _session: object) -> None:
            pass

        def answer_plan(self, request: AnswerRequest, plan: QueryPlan) -> AnswerResult:
            return _answer(request, plan)

        def prepare_plan(self, *_args: object) -> object:
            raise AssertionError("offline authoring bypassed the demo publication boundary")

    monkeypatch.setattr(authoring, "open_runtime_artifact_session", open_session)
    monkeypatch.setattr(authoring, "AnswerService", Service)
    authoring.build_organizer_reference_packet(
        packet,
        approval,
        output,
        artifact_dir=tmp_path / "artifact",
        repository_root=repository,
        code_commit="a" * 40,
    )

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["review_status"] == "pending_human_expected_results_and_answers_review"
    assert result["code_commit"] == "a" * 40
    assert result["question_plan_approval"]["reviewer"] == "곽태성"
    assert result["artifact_identity"]["dataset_version"] == "2026-08-24"
    assert len(result["cases"]) == 35
    assert result["cases"][30]["difficulty"] == "unanswerable"
    assert all(case["trace"]["latency_ms"] == {} for case in result["cases"])


def test_rejects_unbound_approval_before_opening_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, packet, approval, output = _workspace(tmp_path)
    payload = json.loads(approval.read_text(encoding="utf-8"))
    payload["question_plan_packet_sha256"] = "0" * 64
    approval.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        authoring,
        "open_runtime_artifact_session",
        lambda _settings: (_ for _ in ()).throw(AssertionError("artifact opened")),
    )

    with pytest.raises(ValueError, match=r"approval.*checksum"):
        authoring.build_organizer_reference_packet(
            packet,
            approval,
            output,
            artifact_dir=tmp_path / "artifact",
            repository_root=repository,
            code_commit="a" * 40,
        )

    assert not output.exists()


def test_reports_the_failing_case_without_writing_partial_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, packet, approval, output = _workspace(tmp_path)
    session = SimpleNamespace(
        verified_artifacts=SimpleNamespace(
            artifact_set_id="finproof-data-artifacts/v1",
            artifact_contract_version="1.0.0",
            dataset_version=date(2026, 8, 24),
            overall_manifest_logical_hash="977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8",
        )
    )

    @contextmanager
    def open_session(_settings: object) -> Iterator[SimpleNamespace]:
        yield session

    monkeypatch.setattr(authoring, "open_runtime_artifact_session", open_session)
    calls: list[str] = []

    class Service:
        def __init__(self, _session: object) -> None:
            pass

        def answer_plan(self, request: AnswerRequest, _plan: QueryPlan) -> AnswerResult:
            calls.append(request.question_id)
            raise TypeError("bad value")

    monkeypatch.setattr(authoring, "AnswerService", Service)

    with pytest.raises(RuntimeError) as captured:
        authoring.build_organizer_reference_packet(
            packet,
            approval,
            output,
            artifact_dir=tmp_path / "artifact",
            repository_root=repository,
            code_commit="a" * 40,
        )

    assert "ORG-20260824-E-001" in str(captured.value)
    assert "ORG-20260824-U-005" in str(captured.value)
    assert len(calls) == 35
    assert not output.exists()
