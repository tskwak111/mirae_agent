from pathlib import Path

import pytest

import finproof.evaluation.ablation as ablation
from finproof.evaluation.ablation import (
    AblationMeasurement,
    AblationRunner,
    AblationVariant,
    main,
)
from finproof.evaluation.ablation_experiment import _approved_plans
from finproof.evaluation.latency import LatencySummary
from finproof.evaluation.loader import load_golden_cases, suite_checksum
from finproof.evaluation.models import GoldenCase


def _measurement(
    variant: AblationVariant,
    case_count: int,
    case_checksum: str,
) -> AblationMeasurement:
    return AblationMeasurement(
        variant=variant,
        case_checksum=case_checksum,
        code_commit="b" * 40,
        artifact_version="artifact-v1",
        configuration_sha256="c" * 64,
        prompt_version="1.0.0",
        planner_model="HCX-007",
        environment={"python": "3.12"},
        case_count=case_count,
        product_set_f1=1.0,
        order_accuracy=1.0,
        numeric_exact_match=1.0,
        evidence_coverage=1.0,
        limitation_accuracy=1.0,
        repeat_stability=1.0,
        latency=LatencySummary.from_milliseconds((10, 20)),
        prompt_tokens=10,
        completion_tokens=5,
        error_count=0,
    )


def test_ablation_runner_uses_the_same_cases_and_identity_for_exact_variants() -> None:
    cases = load_golden_cases((Path("evaluation/canonical/lookup.jsonl"),))[:2]
    observed_case_ids: list[tuple[str, ...]] = []

    def measure(
        variant: AblationVariant,
        measured_cases: tuple[GoldenCase, ...],
    ) -> AblationMeasurement:
        observed_case_ids.append(tuple(case.case_id for case in measured_cases))
        return _measurement(variant, len(measured_cases), suite_checksum(cases))

    report = AblationRunner(measure).run(tuple(AblationVariant), cases)

    assert tuple(result.variant for result in report.results) == tuple(AblationVariant)
    assert observed_case_ids == [tuple(case.case_id for case in cases)] * 5
    assert report.case_checksum == suite_checksum(cases)


def test_ablation_runner_keeps_actual_token_latency_and_error_measurements() -> None:
    cases = load_golden_cases((Path("evaluation/canonical/lookup.jsonl"),))[:1]

    def measure(
        variant: AblationVariant,
        measured_cases: tuple[GoldenCase, ...],
    ) -> AblationMeasurement:
        return _measurement(variant, len(measured_cases), suite_checksum(cases)).model_copy(
            update={"error_count": 1 if variant is AblationVariant.A_DIRECT_HCX else 0}
        )

    report = AblationRunner(measure).run(tuple(AblationVariant), cases)

    direct = report.results[0]
    assert direct.prompt_tokens == 10
    assert direct.completion_tokens == 5
    assert direct.latency.p95_ms == 20
    assert direct.error_count == 1


def test_ablation_runner_rejects_measurements_from_other_cases() -> None:
    cases = load_golden_cases((Path("evaluation/canonical/lookup.jsonl"),))[:1]

    def measure(
        variant: AblationVariant,
        measured_cases: tuple[GoldenCase, ...],
    ) -> AblationMeasurement:
        return _measurement(variant, len(measured_cases), "d" * 64)

    with pytest.raises(ValueError, match="case checksum differs"):
        AblationRunner(measure).run(tuple(AblationVariant), cases)


def test_ablation_command_validates_raw_variant_measurements(tmp_path: Path) -> None:
    cases = load_golden_cases(tuple(sorted(Path("evaluation/canonical").glob("*.jsonl"))))
    measurement_dir = tmp_path / "raw"
    measurement_dir.mkdir()
    for variant in AblationVariant:
        (measurement_dir / f"{variant.name}.json").write_text(
            _measurement(variant, len(cases), suite_checksum(cases)).model_dump_json(),
            encoding="utf-8",
        )
    output = tmp_path / "ablation.json"

    assert (
        main(
            [
                "--repository-root",
                str(Path.cwd()),
                "--measurement-dir",
                str(measurement_dir),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert len(output.read_text(encoding="utf-8")) > 0


def test_ablation_command_can_produce_then_validate_raw_measurements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = load_golden_cases(tuple(sorted(Path("evaluation/canonical").glob("*.jsonl"))))
    measurement_dir = tmp_path / "raw"
    output = tmp_path / "ablation.json"
    observed: list[tuple[Path, Path, int]] = []

    def produce_raw_measurements(
        repository_root: Path,
        destination: Path,
        *,
        artifact_dir: Path,
        repeats: int,
    ) -> None:
        observed.append((repository_root, artifact_dir, repeats))
        destination.mkdir()
        for variant in AblationVariant:
            (destination / f"{variant.name}.json").write_text(
                _measurement(variant, len(cases), suite_checksum(cases)).model_dump_json(),
                encoding="utf-8",
            )

    monkeypatch.setattr(ablation, "produce_raw_measurements", produce_raw_measurements)

    assert (
        main(
            [
                "--repository-root",
                str(Path.cwd()),
                "--measurement-dir",
                str(measurement_dir),
                "--output",
                str(output),
                "--produce",
                "--artifact-dir",
                str(tmp_path / "official-artifacts"),
                "--repeats",
                "2",
            ]
        )
        == 0
    )
    assert observed == [(Path.cwd(), tmp_path / "official-artifacts", 2)]


def test_ablation_experiment_loads_an_approved_plan_for_every_canonical_case() -> None:
    cases = load_golden_cases(tuple(sorted(Path("evaluation/canonical").glob("*.jsonl"))))

    plans = _approved_plans(Path.cwd(), cases)

    assert set(plans) == {case.case_id for case in cases}
