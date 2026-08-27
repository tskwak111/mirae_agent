"""Evaluation-only A-E ablation contracts and identity checks."""

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.evaluation.latency import LatencySummary
from finproof.evaluation.loader import load_golden_cases, suite_checksum
from finproof.evaluation.models import GoldenCase


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class AblationVariant(StrEnum):
    A_DIRECT_HCX = "A_direct_hcx_over_retrieved_rows"
    B_CONSTRAINED_PLAN = "B_constrained_query_plan"
    C_DETERMINISTIC_EXECUTOR = "C_deterministic_executor"
    D_DOMAIN_POLICY = "D_grain_time_state_metric_policy"
    E_VERIFIED_ANSWER = "E_evidence_verifier_conditional_dual_lens"


class AblationMeasurement(_FrozenModel):
    variant: AblationVariant
    case_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    artifact_version: str = Field(min_length=1)
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_version: str = Field(min_length=1)
    planner_model: str = Field(min_length=1)
    environment: Mapping[str, str]
    case_count: int = Field(ge=1)
    product_set_f1: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    order_accuracy: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    numeric_exact_match: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    evidence_coverage: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    limitation_accuracy: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    repeat_stability: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    latency: LatencySummary
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    error_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_counts(self) -> Self:
        if self.error_count > self.case_count:
            raise ValueError("ablation errors cannot exceed the case count")
        return self


class AblationReport(_FrozenModel):
    case_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    results: tuple[AblationMeasurement, ...]


AblationMeasure = Callable[
    [AblationVariant, tuple[GoldenCase, ...]],
    AblationMeasurement,
]


class AblationRunner:
    def __init__(self, measure: AblationMeasure) -> None:
        self._measure = measure

    def run(
        self,
        variants: Sequence[AblationVariant],
        cases: Sequence[GoldenCase],
    ) -> AblationReport:
        frozen_cases = tuple(cases)
        if tuple(variants) != tuple(AblationVariant):
            raise ValueError("ablation requires the exact ordered A-E variants")
        if not frozen_cases or len({case.case_id for case in frozen_cases}) != len(frozen_cases):
            raise ValueError("ablation cases must be nonempty with unique IDs")
        results = tuple(self._measure(variant, frozen_cases) for variant in variants)
        if any(
            result.variant is not variant for variant, result in zip(variants, results, strict=True)
        ):
            raise ValueError("ablation result variant differs")
        if any(result.case_count != len(frozen_cases) for result in results):
            raise ValueError("ablation variants must use the same cases")
        if any(result.case_checksum != suite_checksum(frozen_cases) for result in results):
            raise ValueError("ablation case checksum differs from the reviewed cases")
        identity = _identity(results[0])
        if any(_identity(result) != identity for result in results[1:]):
            raise ValueError("ablation variants must share one recorded environment")
        return AblationReport(case_checksum=results[0].case_checksum, results=results)


def _identity(result: AblationMeasurement) -> tuple[object, ...]:
    return (
        result.case_checksum,
        result.code_commit,
        result.artifact_version,
        result.configuration_sha256,
        result.prompt_version,
        result.planner_model,
        dict(result.environment),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and bind raw A-E ablation results")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--measurement-dir",
        type=Path,
        default=Path("artifacts/evaluation/ablation_raw"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/ablation.json"),
    )
    args = parser.parse_args(argv)
    repository_root: Path = args.repository_root
    measurement_dir: Path = args.measurement_dir
    cases = load_golden_cases(
        tuple(sorted((repository_root / "evaluation" / "canonical").glob("*.jsonl")))
    )

    def measure(
        variant: AblationVariant,
        _: tuple[GoldenCase, ...],
    ) -> AblationMeasurement:
        path = measurement_dir / f"{variant.name}.json"
        return AblationMeasurement.model_validate_json(
            path.read_text(encoding="utf-8"), strict=True
        )

    report = AblationRunner(measure).run(tuple(AblationVariant), cases)
    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    error_count = sum(result.error_count for result in report.results)
    sys.stdout.write(
        json.dumps(
            {
                "case_count": report.results[0].case_count,
                "error_count": error_count,
                "output": str(output),
                "variants": len(report.results),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    return int(error_count > 0)


if __name__ == "__main__":
    raise SystemExit(main())
