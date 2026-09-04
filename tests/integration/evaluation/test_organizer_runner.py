"""Focused organizer-suite CLI routing contract."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from finproof.cli import evaluate as cli_evaluate
from finproof.cli.evaluate import _reviewed_plan, run_evaluation
from finproof.core.settings import ExecutionMode, Settings
from finproof.evaluation.adversarial import AdversarialCase, AdversarialObservation
from finproof.evaluation.loader import load_blind_suite, load_suite
from finproof.evaluation.models import GoldenCase, ObservedCase
from finproof.evaluation.runner import EvaluationMode, ReplayVersions


class _ReviewedPlanService:
    def replay_versions(self) -> ReplayVersions:
        return ReplayVersions.from_configuration(
            artifact_version="artifact",
            config_versions={},
            prompt_version="prompt",
            answer_prompt_version=None,
            answer_schema_sha256=None,
            wording_verification_mode=None,
            planner_version="reviewed-plan",
            execution_mode=ExecutionMode.EXTENDED_DEMO,
            hcx_enabled=False,
            planner_model=None,
            fallback_enabled=True,
            structured_outputs_enabled=False,
        )

    def observe(self, _case: GoldenCase, mode: EvaluationMode) -> ObservedCase:
        assert mode is EvaluationMode.DETERMINISTIC_CORE
        return ObservedCase()

    def observe_adversarial(self, _case: AdversarialCase) -> AdversarialObservation:
        raise AssertionError("organizer replay reached adversarial evaluation")


def test_routes_all_35_organizer_cases_to_a_plain_evaluation_report(tmp_path: Path) -> None:
    output = tmp_path / "organizer.json"

    run_evaluation(
        "organizer_20260824",
        output,
        EvaluationMode.DETERMINISTIC_CORE,
        service=_ReviewedPlanService(),
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(report["case_scores"]) == 35
    assert "adversarial" not in report


def test_reconstructs_every_reviewed_plan_as_an_executable_query_plan() -> None:
    cases = load_suite("organizer_20260824")

    plans = tuple(_reviewed_plan(case) for case in cases)

    assert len(plans) == 35
    assert all(not plan.entities for plan in plans)
    holding = next(
        plan
        for case, plan in zip(cases, plans, strict=True)
        if case.case_id == "ORG-20260824-H-001"
    )
    assert tuple(product.value for product in holding.product_types) == (
        "domestic_etf",
        "overseas_etf",
        "public_fund",
    )


def test_reconstructs_serialized_decimal_filter_as_decimal() -> None:
    case = next(
        case for case in load_blind_suite("blind_development") if case.case_id == "CQ-012-006"
    )

    plan = _reviewed_plan(case)

    total_fee = next(clause for clause in plan.filters if clause.field == "total_fee")
    assert total_fee.value == Decimal("0.5")
    assert type(total_fee.value) is Decimal


def test_reconstructs_only_the_reviewed_entity_mentions() -> None:
    case = next(
        case for case in load_blind_suite("blind_development") if case.case_id == "CQ-012-001"
    )

    plan = _reviewed_plan(case)

    assert tuple((entity.text, entity.identifier_type.value) for entity in plan.entities) == (
        ("KR350103G9B0", "product_id"),
    )


def test_deterministic_organizer_uses_the_reviewed_plan_service_without_hcx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    @contextmanager
    def reviewed(settings: Settings) -> Iterator[_ReviewedPlanService]:
        assert settings.execution_mode is ExecutionMode.EXTENDED_DEMO
        assert settings.hcx_enabled is False
        yield _ReviewedPlanService()

    monkeypatch.setattr(cli_evaluate, "_open_reviewed_plan_service", reviewed)
    monkeypatch.setattr(
        cli_evaluate,
        "_open_local_service",
        lambda _settings: (_ for _ in ()).throw(AssertionError("HCX graph opened")),
    )

    run_evaluation(
        "organizer_20260824",
        tmp_path / "organizer.json",
        EvaluationMode.DETERMINISTIC_CORE,
    )


@pytest.mark.parametrize("suite", ["blind_development", "blind_holdout"])
def test_deterministic_blind_suite_uses_the_reviewed_plan_service_without_hcx(
    suite: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = load_suite("organizer_20260824")[0]

    @contextmanager
    def reviewed(settings: Settings) -> Iterator[_ReviewedPlanService]:
        assert settings.execution_mode is ExecutionMode.EXTENDED_DEMO
        assert settings.hcx_enabled is False
        yield _ReviewedPlanService()

    monkeypatch.setattr(cli_evaluate, "load_blind_suite", lambda *_args, **_kwargs: (case,))
    monkeypatch.setattr(cli_evaluate, "_open_reviewed_plan_service", reviewed)
    monkeypatch.setattr(
        cli_evaluate,
        "_open_local_service",
        lambda _settings: (_ for _ in ()).throw(AssertionError("HCX graph opened")),
    )

    run_evaluation(
        suite,
        tmp_path / f"{suite}.json",
        EvaluationMode.DETERMINISTIC_CORE,
    )
