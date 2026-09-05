import json
from asyncio import new_event_loop
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import SecretStr

from finproof.cli import evaluate as cli_evaluate
from finproof.cli.evaluate import run_evaluation
from finproof.cli.main import _parser, _run_main
from finproof.core.settings import ExecutionMode, Settings
from finproof.evaluation.loader import load_golden_cases
from finproof.evaluation.models import GoldenCase, ObservedCase
from finproof.evaluation.runner import EvaluationMode, ReplayVersions
from finproof.runtime.session import RuntimeArtifactSession
from finproof.service.orchestrator import EvaluationOrchestrator


def test_parser_accepts_canonical_evaluate_command() -> None:
    args = _parser().parse_args(
        [
            "evaluate",
            "--suite",
            "canonical",
            "--output",
            "artifacts/evaluation/canonical.json",
        ]
    )

    assert vars(args) == {
        "command": "evaluate",
        "suite": "canonical",
        "output": Path("artifacts/evaluation/canonical.json"),
        "mode": EvaluationMode.END_TO_END,
    }


def test_parser_accepts_robustness_evaluate_command() -> None:
    args = _parser().parse_args(
        [
            "evaluate",
            "--suite",
            "robustness",
            "--output",
            "artifacts/evaluation/robustness.json",
        ]
    )

    assert args.suite == "robustness"


def test_parser_accepts_blind_development_evaluation() -> None:
    args = _parser().parse_args(
        ["evaluate", "--suite", "blind_development", "--output", "report.json"]
    )

    assert args.suite == "blind_development"


@pytest.mark.parametrize("suite", ["blind_development", "blind_holdout"])
def test_evaluation_routes_blind_suites_only_through_blind_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suite: str,
) -> None:
    case = load_golden_cases((Path("evaluation/canonical/clarification.jsonl"),))[0]
    calls: list[tuple[str, Path]] = []

    class Service:
        def replay_versions(self) -> ReplayVersions:
            return ReplayVersions.from_configuration(
                artifact_version="artifact",
                config_versions={},
                prompt_version="prompt",
                answer_prompt_version=None,
                answer_schema_sha256=None,
                wording_verification_mode=None,
                planner_version="planner",
                execution_mode=ExecutionMode.EXTENDED_DEMO,
                hcx_enabled=False,
                planner_model=None,
                fallback_enabled=True,
                structured_outputs_enabled=False,
            )

        def observe(self, observed_case: GoldenCase, mode: EvaluationMode) -> ObservedCase:
            assert observed_case is case
            assert mode is EvaluationMode.PLAN_ONLY
            return ObservedCase()

    def blind_loader(name: str, *, repository_root: Path) -> tuple[GoldenCase, ...]:
        calls.append((name, repository_root))
        return (case,)

    monkeypatch.setattr(cli_evaluate, "load_blind_suite", blind_loader)
    monkeypatch.setattr(
        cli_evaluate,
        "load_golden_cases",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("canonical loader used")),
    )
    monkeypatch.setattr(
        cli_evaluate,
        "load_suite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("organizer loader used")),
    )

    run_evaluation(
        suite,
        tmp_path / f"{suite}.json",
        EvaluationMode.PLAN_ONLY,
        repository_root=tmp_path,
        service=cast(cli_evaluate.RobustnessService, Service()),
    )

    assert calls == [(suite, tmp_path)]


def test_parser_accepts_organizer_deterministic_core_command() -> None:
    args = _parser().parse_args(
        [
            "evaluate",
            "--suite",
            "organizer_20260824",
            "--output",
            "artifacts/evaluation/organizer-20260824.json",
            "--mode",
            "deterministic-core",
        ]
    )

    assert args.suite == "organizer_20260824"
    assert args.mode is EvaluationMode.DETERMINISTIC_CORE


def test_cli_evaluation_replay_rejects_non_hcx_007_model() -> None:
    from finproof.cli.evaluate import _LocalEvaluationService

    versions = SimpleNamespace(
        runtime_facts=lambda: {
            "artifact_manifest_hash": "artifact",
            "planner_version": "planner",
        },
        execution_mode=ExecutionMode.EVALUATION,
    )
    loop = new_event_loop()
    try:
        service = _LocalEvaluationService(
            session=cast(RuntimeArtifactSession, SimpleNamespace(versions=versions)),
            orchestrator=cast(EvaluationOrchestrator, object()),
            loop=loop,
            settings=Settings(
                hcx_enabled=True,
                hcx_api_key=SecretStr("test-key"),
                hcx_model_name="HCX-DASH-002",
            ),
        )

        with pytest.raises(ValueError, match="HCX-007"):
            service.replay_versions()
    finally:
        loop.close()


def test_evaluate_dispatches_exact_suite_mode_and_output(
    tmp_path: Path,
    capsys: object,
) -> None:
    output = tmp_path / "report.json"
    calls: list[tuple[str, Path, EvaluationMode]] = []

    def evaluator(suite: str, destination: Path, mode: EvaluationMode) -> None:
        calls.append((suite, destination, mode))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"suite": suite}) + "\n", encoding="utf-8")

    assert (
        _run_main(
            [
                "evaluate",
                "--suite",
                "canonical",
                "--output",
                str(output),
                "--mode",
                "plan-only",
            ],
            evaluator=evaluator,
        )
        == 0
    )
    assert calls == [("canonical", output, EvaluationMode.PLAN_ONLY)]
    assert json.loads(output.read_text(encoding="utf-8")) == {"suite": "canonical"}


def test_selected_products_follow_compatible_cross_product_rank_summaries() -> None:
    from finproof.cli.evaluate import _observed_products
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )

    plan = QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.LISTED_PRODUCT,
        filters=(),
        metrics=("return_1y",),
        sort=(),
        aggregation=None,
        top_k=2,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )
    evidence = (
        {"product_type": "domestic_etf", "product_id": "SAME"},
        {"product_type": "overseas_etf", "product_id": "SAME"},
    )
    summaries = (
        {
            "kind": "rank",
            "product_types": ["overseas_etf"],
            "native_result_grains": ["listed_product"],
            "product_id": "SAME",
            "rank": 1,
        },
        {
            "kind": "rank",
            "product_types": ["domestic_etf"],
            "native_result_grains": ["listed_product"],
            "product_id": "SAME",
            "rank": 2,
        },
    )

    observed = _observed_products(plan, evidence, summaries)

    assert tuple(item.product_type for item in observed) == (
        ProductType.OVERSEAS_ETF,
        ProductType.DOMESTIC_ETF,
    )
    assert tuple(item.product_id for item in observed) == ("SAME", "SAME")


def test_aggregate_observations_parse_verified_summary_identity_and_exact_value() -> None:
    from decimal import Decimal

    from finproof.cli.evaluate import _observed_aggregates
    from finproof.evaluation.models import ExpectedAggregate

    expected = (
        ExpectedAggregate.model_validate(
            {
                "function": "avg",
                "field_id": "return_1y",
                "product_type": "domestic_etf",
                "native_result_grain": "listed_product",
                "partition_key": "return_1y:KRW",
                "group_values": [{"field_id": "currency", "value_type": "text", "value": "KRW"}],
                "value_type": "decimal",
                "value": "3.10",
            }
        ),
    )
    summaries = (
        {
            "kind": "aggregate",
            "policy_versions": ["return_1y:avg"],
            "product_types": ["domestic_etf"],
            "native_result_grains": ["listed_product"],
            "partition_key": "return_1y:KRW",
            "metric_id": "return_1y",
            "group_values": [{"field_id": "currency", "value": "KRW"}],
            "value": "3.10",
        },
    )

    observed = _observed_aggregates(expected, summaries)

    assert observed[0].value == Decimal("3.10")
    assert observed[0].group_values[0].value == "KRW"


def test_unexpected_missing_aggregate_value_remains_a_typed_observation() -> None:
    from finproof.cli.evaluate import _observed_aggregates
    from finproof.evaluation.models import ValueType

    summaries = (
        {
            "kind": "aggregate",
            "policy_versions": ["return_1y:avg"],
            "product_types": ["domestic_etf"],
            "native_result_grains": ["listed_product"],
            "partition_key": "return_1y:KRW",
            "metric_id": "return_1y",
            "group_values": [],
            "value": None,
        },
    )

    observed = _observed_aggregates((), summaries)

    assert observed[0].value_type is ValueType.NULL
    assert observed[0].value is None
