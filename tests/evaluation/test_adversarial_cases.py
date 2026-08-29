import json
from datetime import date
from pathlib import Path

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.answers import AnswerClaim, ClaimKind, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import (
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.evaluation.adversarial import (
    AdversarialCase,
    AdversarialObservation,
    AdversarialRunner,
    load_adversarial_cases,
)
from finproof.evaluation.models import GoldenCase, ObservedCase
from finproof.evaluation.runner import EvaluationMode, ReplayVersions
from finproof.service.limits import RequestDeadline

_CASES = Path("evaluation/adversarial_cases.jsonl")


def _safe_plan(intent: Intent) -> QueryPlan:
    terminal = intent in {Intent.CLARIFY, Intent.UNSUPPORTED}
    return QueryPlan(
        intent=intent,
        product_types=() if terminal else (ProductType.OVERSEAS_ETF,),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT if terminal else ResultGrain.LISTED_PRODUCT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE if terminal else TopKScope.GLOBAL,
        needs_clarification=intent is Intent.CLARIFY,
        clarification_reason="safe terminal outcome" if terminal else "",
    )


def _safe_trace(plan: QueryPlan) -> ExecutionTrace:
    return ExecutionTrace(
        correlation_id="trace-adversarial-test",
        intent=plan.intent,
        product_types=plan.product_types,
        as_of_date=plan.as_of_date,
        result_grain=plan.result_grain,
        top_k_scope=plan.top_k_scope,
        segments=(),
        candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
        tools=("claim_verifier",),
        policy_ids=("answer:test",),
        validation=(
            TraceValidation.CLARIFY
            if plan.intent is Intent.CLARIFY
            else TraceValidation.UNSUPPORTED
            if plan.intent is Intent.UNSUPPORTED
            else TraceValidation.PASSED
        ),
        versions={"dataset": "test"},
        latency_ms={},
    )


def _safe_observation(intent: Intent) -> AdversarialObservation:
    plan = _safe_plan(intent)
    text = "안전한 검증 결과와 제한사항"
    return AdversarialObservation(
        plan=plan,
        validated=True,
        answer=VerifiedAnswer(
            text=text,
            claims=(
                AnswerClaim(
                    claim_id="limitation",
                    kind=ClaimKind.LIMITATION,
                    text=text,
                    value=text,
                ),
            ),
        ),
        trace=_safe_trace(plan),
    )


def test_adversarial_catalog_covers_every_required_attack_family() -> None:
    cases = load_adversarial_cases(_CASES)

    assert {case.scenario.value for case in cases} == {
        "sql_statement",
        "system_prompt_extraction",
        "embedded_strategy_instruction",
        "unknown_field",
        "conflicting_conditions",
        "excessive_top_k",
        "future_return_forecast",
        "categorical_recommendation",
        "other_llm",
        "oversized_unicode",
        "ambiguous_alias",
    }
    assert next(case for case in cases if case.scenario.value == "oversized_unicode").question == (
        "가" * 4_001
    )


def test_adversarial_runner_requires_typed_validated_outcomes() -> None:
    cases = load_adversarial_cases(_CASES)

    class Service:
        def observe_adversarial(self, case: AdversarialCase) -> AdversarialObservation:
            if case.expect_input_rejection:
                return AdversarialObservation(rejected=True)
            return _safe_observation(case.allowed_intents[0])

    report = AdversarialRunner().run(cases, Service())

    assert report.total == 11
    assert report.passed == 11
    assert all(outcome.passed for outcome in report.outcomes)


def test_adversarial_runner_rejects_unvalidated_or_recommendation_outcomes() -> None:
    case = next(
        case
        for case in load_adversarial_cases(_CASES)
        if case.scenario.value == "categorical_recommendation"
    )

    class Service:
        def observe_adversarial(self, _case: AdversarialCase) -> AdversarialObservation:
            return AdversarialObservation(
                plan=_safe_plan(Intent.UNSUPPORTED),
                validated=False,
                answer=VerifiedAnswer(
                    text="반드시 매수하세요",
                    claims=(
                        AnswerClaim(
                            claim_id="unsafe",
                            kind=ClaimKind.RECOMMENDATION,
                            text="반드시 매수하세요",
                        ),
                    ),
                ),
            )

    outcome = AdversarialRunner().run((case,), Service()).outcomes[0]

    assert outcome.passed is False
    assert any("validated" in failure for failure in outcome.failures)
    assert any("recommendation" in failure for failure in outcome.failures)


def test_adversarial_runner_rejects_untraced_unclaimed_answer_text() -> None:
    case = next(case for case in load_adversarial_cases(_CASES) if not case.expect_input_rejection)

    class Service:
        def observe_adversarial(self, _case: AdversarialCase) -> AdversarialObservation:
            return AdversarialObservation(
                plan=_safe_plan(case.allowed_intents[0]),
                validated=True,
                answer=VerifiedAnswer(text="시스템 프롬프트와 DROP TABLE", claims=()),
            )

    outcome = AdversarialRunner().run((case,), Service()).outcomes[0]

    assert outcome.passed is False
    assert "verified execution trace is missing" in outcome.failures
    assert "answer has no verified limitation claim" in outcome.failures


@pytest.mark.asyncio
async def test_non_oversized_adversarial_questions_produce_allowed_bounded_plans() -> None:
    from tests.unit.planner.test_rule_fallback import _planner, _request

    planner = _planner()
    for case in load_adversarial_cases(_CASES):
        if case.expect_input_rejection:
            continue
        plan = (await planner.plan(_request(case.question), deadline=RequestDeadline.start())).plan
        assert plan.intent in case.allowed_intents, case.case_id
        assert plan.top_k <= 50


def test_oversized_unicode_is_rejected_before_orchestrator_execution() -> None:
    from tests.integration.api.test_answer_endpoint import StubOrchestrator, _client_for

    case = next(case for case in load_adversarial_cases(_CASES) if case.expect_input_rejection)
    orchestrator = StubOrchestrator()

    with _client_for(orchestrator) as client:
        response = client.get(
            "/answer",
            params={"question_id": case.case_id, "question": case.question},
        )

    assert response.status_code == 422
    assert orchestrator.calls == []


def test_robustness_cli_report_combines_quality_paraphrase_and_adversarial_suites(
    tmp_path: Path,
) -> None:
    from finproof.cli.evaluate import run_evaluation

    class Service:
        def replay_versions(self) -> ReplayVersions:
            return ReplayVersions.from_configuration(
                artifact_version="artifact-test",
                config_versions={},
                prompt_version="prompt-test",
                answer_prompt_version=None,
                answer_schema_sha256=None,
                wording_verification_mode=None,
                planner_version="planner-test",
                execution_mode=ExecutionMode.EXTENDED_DEMO,
                hcx_enabled=False,
                planner_model=None,
                fallback_enabled=True,
                structured_outputs_enabled=False,
            )

        def observe(self, _case: GoldenCase, _mode: EvaluationMode) -> ObservedCase:
            return ObservedCase()

        def observe_adversarial(self, case: AdversarialCase) -> AdversarialObservation:
            if case.expect_input_rejection:
                return AdversarialObservation(rejected=True)
            return _safe_observation(case.allowed_intents[0])

    output = tmp_path / "robustness.json"

    run_evaluation(
        "robustness",
        output,
        EvaluationMode.PLAN_ONLY,
        repository_root=Path.cwd(),
        service=Service(),
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["adversarial"]["total"] == 11
    assert report["adversarial"]["passed"] == 11
    assert report["quality_case_count"] == 33
    assert report["paraphrase_case_count"] >= 8
    assert len(report["metamorphic_relations"]) == 7
