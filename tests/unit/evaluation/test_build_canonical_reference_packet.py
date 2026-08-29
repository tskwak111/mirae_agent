"""Focused tests for deterministic noncanonical reference-packet authoring."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from tools import build_canonical_reference_packet as authoring

from finproof.core.settings import ExecutionMode, Settings
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import (
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)


def _plan() -> dict[str, object]:
    return {
        "intent": "screen_rank",
        "product_types": ["domestic_etf"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "listed_product",
        "filters": [],
        "metrics": ["return_ytd"],
        "sort": [{"field": "return_ytd", "direction": "desc"}],
        "aggregation": None,
        "top_k": 3,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }


def _approved_packet() -> dict[str, object]:
    return {
        "batch_id": "001",
        "review_status": "human_approved_questions",
        "reviewer": "곽태성",
        "reviewed_at": "2026-08-24",
        "source_question_packet_sha256": "a" * 64,
        "cases": [
            {
                "case_id": "CQ-001-RANK-001",
                "category": "rank",
                "question": "국내 ETF 연초이후 수익률 상위 3개를 찾아주세요.",
                "plan": _plan(),
            },
            {
                "case_id": "CQ-001-QUALITY-001",
                "category": "quality",
                "question": "국내 ETF 추적오차 공동순위를 확인해 주세요.",
                "plan": _plan(),
            },
        ],
    }


def _answer(case_id: str) -> AnswerResult:
    return AnswerResult(
        answer=VerifiedAnswer(text=f"{case_id} 답변", claims=()),
        retrieved_context=json.dumps(
            {
                "format": "evidence_context.v2",
                "sources": [],
                "direct_fields": [],
                "direct": [],
                "derived_fields": [],
                "derived": [],
                "locator_fields": [],
                "summaries": [],
                "material_policy_limitations": [],
            }
        ),
        trace=ExecutionTrace(
            correlation_id=f"trace-{case_id}",
            intent=Intent.SCREEN_RANK,
            product_types=(ProductType.DOMESTIC_ETF,),
            as_of_date=date(2026, 7, 11),
            result_grain=ResultGrain.LISTED_PRODUCT,
            top_k_scope=TopKScope.GLOBAL,
            segments=(),
            candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
            tools=("claim_verifier",),
            policy_ids=("answer:1.0.0",),
            validation=TraceValidation.PASSED,
            versions={"dataset_version": "2026-07-11"},
            latency_ms={"database": 91},
        ),
    )


def test_builds_one_reproducible_pending_packet_with_one_session_and_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    artifact_dir = tmp_path / "published-artifact"
    input_path = repository / "evaluation" / "review_batches" / "approved-plans.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(
        json.dumps(_approved_packet(), ensure_ascii=False),
        encoding="utf-8",
    )
    output = input_path.with_name("reference-packet.json")
    secret = "must-not-enter-reference-authoring"  # noqa: S105 - redaction sentinel.
    monkeypatch.setenv("FINPROOF_HCX_ENABLED", "true")
    monkeypatch.setenv("FINPROOF_HCX_API_KEY", secret)
    events: list[str] = []
    session = SimpleNamespace(
        verified_artifacts=SimpleNamespace(
            artifact_set_id="finproof-data-artifacts/v1",
            artifact_contract_version="1.0.0",
            dataset_version=date(2026, 7, 11),
            overall_manifest_logical_hash="b" * 64,
        )
    )

    @contextmanager
    def open_session(settings: Settings) -> Iterator[SimpleNamespace]:
        assert settings.hcx_enabled is False
        assert settings.hcx_api_key is None
        assert settings.execution_mode is ExecutionMode.EXTENDED_DEMO
        events.append(f"open:{settings.__class__.__name__}")
        yield session
        events.append("close")

    class Service:
        def __init__(self, received_session: object) -> None:
            assert received_session is session
            events.append("service")

        def answer_plan(self, request: AnswerRequest, plan: QueryPlan) -> AnswerResult:
            case_id = request.question_id
            assert plan.intent is Intent.SCREEN_RANK
            events.append(f"answer:{case_id}")
            return _answer(case_id)

        def prepare_plan(self, *_args: object) -> object:
            raise AssertionError("offline authoring bypassed the demo publication boundary")

    monkeypatch.setattr(authoring, "open_runtime_artifact_session", open_session)
    monkeypatch.setattr(authoring, "AnswerService", Service)

    authoring.build_reference_packet(
        input_path,
        output,
        artifact_dir=artifact_dir,
        repository_root=repository,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert secret not in output.read_text(encoding="utf-8")
    assert payload["batch_id"] == "001"
    assert payload["review_status"] == "pending_human_plan_and_expectation_review"
    assert payload["artifact_identity"] == {
        "artifact_set_id": "finproof-data-artifacts/v1",
        "artifact_contract_version": "1.0.0",
        "dataset_version": "2026-07-11",
        "manifest_logical_hash": "b" * 64,
    }
    assert payload["question_review"] == {
        "reviewer": "곽태성",
        "reviewed_at": "2026-08-24",
    }
    assert payload["source_question_packet_sha256"] == "a" * 64
    assert len(cast(str, payload["question_and_draft_plan_packet_sha256"])) == 64
    assert "approved_plan_packet_sha256" not in payload
    cases = cast(list[dict[str, object]], payload["cases"])
    assert [case["case_id"] for case in cases] == [
        "CQ-001-RANK-001",
        "CQ-001-QUALITY-001",
    ]
    assert cases[0]["answer"] == {"text": "CQ-001-RANK-001 답변", "claims": []}
    assert cast(dict[str, object], cases[0]["retrieved_context"])["format"] == (
        "evidence_context.v2"
    )
    assert cast(dict[str, object], cases[0]["trace"])["latency_ms"] == {}
    assert events == [
        "open:Settings",
        "service",
        "answer:CQ-001-RANK-001",
        "answer:CQ-001-QUALITY-001",
        "close",
    ]


def test_reference_plan_omits_unset_missing_value_filter_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    input_path = repository / "review" / "approved-plans.json"
    input_path.parent.mkdir()
    packet = _approved_packet()
    case = cast(list[dict[str, object]], packet["cases"])[0]
    plan = cast(dict[str, object], case["plan"])
    plan["intent"] = "screen"
    plan["metrics"] = []
    plan["sort"] = []
    plan["filters"] = [
        {"field": "total_fee", "operator": "lte", "value": 0.1},
        {"field": "risk_grade", "operator": "is_not_missing"},
    ]
    input_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    session = SimpleNamespace(
        verified_artifacts=SimpleNamespace(
            artifact_set_id="finproof-data-artifacts/v1",
            artifact_contract_version="1.0.0",
            dataset_version=date(2026, 7, 11),
            overall_manifest_logical_hash="b" * 64,
        )
    )

    @contextmanager
    def open_session(_settings: Settings) -> Iterator[SimpleNamespace]:
        yield session

    class Service:
        def __init__(self, _session: object) -> None:
            pass

        def answer_plan(self, request: AnswerRequest, _plan: QueryPlan) -> AnswerResult:
            return _answer(request.question_id)

        def prepare_plan(self, *_args: object) -> object:
            raise AssertionError("offline authoring bypassed the demo publication boundary")

    monkeypatch.setattr(authoring, "open_runtime_artifact_session", open_session)
    monkeypatch.setattr(authoring, "AnswerService", Service)
    output = input_path.with_name("reference.json")
    authoring.build_reference_packet(
        input_path, output, artifact_dir=tmp_path / "artifact", repository_root=repository
    )

    emitted_plan = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["plan"]
    assert emitted_plan == plan
    assert "value" not in emitted_plan["filters"][1]
    QueryPlan.model_validate_json(json.dumps(emitted_plan), strict=True)


@pytest.mark.parametrize(
    "case",
    [
        "extra-root-key",
        "unapproved-status",
        "oversized-reviewer",
        "invalid-source-checksum",
        "empty-cases",
        "extra-case-key",
        "duplicate-case-id",
        "unknown-category",
        "oversized-question",
        "oversized-case-id",
        "invalid-query-plan",
        "duplicate-json-key",
    ],
)
def test_rejects_inexact_or_unapproved_plan_packets_before_artifact_open(
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    input_path = repository / "review" / "approved-plans.json"
    input_path.parent.mkdir()
    packet = deepcopy(_approved_packet())
    cases = cast(list[dict[str, object]], packet["cases"])
    if case == "extra-root-key":
        packet["unexpected"] = True
    elif case == "unapproved-status":
        packet["review_status"] = "pending_human_review"
    elif case == "oversized-reviewer":
        packet["reviewer"] = "가" * 201
    elif case == "invalid-source-checksum":
        packet["source_question_packet_sha256"] = "A" * 64
    elif case == "empty-cases":
        packet["cases"] = []
    elif case == "extra-case-key":
        cases[0]["expected_answer"] = "unsafe"
    elif case == "duplicate-case-id":
        cases[1]["case_id"] = cases[0]["case_id"]
    elif case == "unknown-category":
        cases[0]["category"] = "forecast"
    elif case == "oversized-question":
        cases[0]["question"] = "가" * 4_001
    elif case == "oversized-case-id":
        cases[0]["case_id"] = "C" * 201
    elif case == "invalid-query-plan":
        cast(dict[str, object], cases[0]["plan"])["sql"] = "SELECT 1"

    raw = json.dumps(packet, ensure_ascii=False)
    if case == "duplicate-json-key":
        raw = raw.replace('"batch_id": "001"', '"batch_id": "001", "batch_id": "002"')
    input_path.write_text(raw, encoding="utf-8")
    output = input_path.with_name("reference.json")

    def forbidden_open(_settings: object) -> None:
        raise AssertionError("invalid authoring input reached artifact verification")

    monkeypatch.setattr(authoring, "open_runtime_artifact_session", forbidden_open)

    with pytest.raises(
        ValueError,
        match=(
            r"question-and-draft-plan|approved question|draft-plan|"
            r"JSON object keys|validation error"
        ),
    ):
        authoring.build_reference_packet(
            input_path,
            output,
            artifact_dir=tmp_path / "artifact",
            repository_root=repository,
        )

    assert not output.exists()


@pytest.mark.parametrize("unsafe", ["canonical-input", "canonical-output", "non-json"])
def test_refuses_noncanonical_contract_violations_before_artifact_open(
    unsafe: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    review_root = repository / "evaluation" / "review_batches"
    canonical_root = repository / "evaluation" / "canonical"
    input_path = (
        canonical_root / "approved-plans.json"
        if unsafe == "canonical-input"
        else review_root / "approved-plans.json"
    )
    input_path.parent.mkdir(parents=True)
    input_path.write_text(
        json.dumps(_approved_packet(), ensure_ascii=False),
        encoding="utf-8",
    )
    output = (
        canonical_root / "reference.json"
        if unsafe == "canonical-output"
        else review_root / "reference.txt"
        if unsafe == "non-json"
        else review_root / "reference.json"
    )

    def forbidden_open(_settings: object) -> None:
        raise AssertionError("unsafe path reached artifact verification")

    monkeypatch.setattr(authoring, "open_runtime_artifact_session", forbidden_open)

    with pytest.raises(ValueError, match=r"canonical|\.json"):
        authoring.build_reference_packet(
            input_path,
            output,
            artifact_dir=tmp_path / "artifact",
            repository_root=repository,
        )

    assert not output.exists()


def test_existing_output_is_never_overwritten_and_leaves_no_temporary_file(
    tmp_path: Path,
) -> None:
    output = tmp_path / "reference.json"
    output.write_text("original", encoding="utf-8")

    with pytest.raises(FileExistsError):
        authoring._write_new_json(output, {"unsafe": "replacement"})

    assert output.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []
