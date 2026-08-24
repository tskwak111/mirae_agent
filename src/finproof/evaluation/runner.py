"""Sequential deterministic replay runner for reviewed golden cases."""

import platform
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.evaluation.loader import suite_checksum
from finproof.evaluation.models import GoldenCase, ObservedCase
from finproof.evaluation.scoring import CaseScore, LatencySummary, RatioScore, score_case


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EvaluationMode(StrEnum):
    PLAN_ONLY = "plan-only"
    DETERMINISTIC_CORE = "deterministic-core"
    END_TO_END = "end-to-end"


class ReplayVersions(_FrozenModel):
    artifact_version: str = Field(min_length=1)
    config_versions: dict[str, str]
    prompt_version: str = Field(min_length=1)
    planner_version: str = Field(min_length=1)


class ReplayMetadata(ReplayVersions):
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    environment: dict[str, str]
    started_at: datetime
    ended_at: datetime
    case_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: EvaluationMode

    @model_validator(mode="after")
    def _validate_times(self) -> Self:
        if (
            self.started_at.tzinfo is None
            or self.ended_at.tzinfo is None
            or self.ended_at < self.started_at
        ):
            raise ValueError("replay timestamps must be ordered and timezone-aware")
        return self


class EvaluationReport(_FrozenModel):
    replay: ReplayMetadata
    case_scores: tuple[CaseScore, ...]
    aggregates: dict[str, RatioScore]
    latency: LatencySummary | None


class EvaluationService(Protocol):
    def replay_versions(self) -> ReplayVersions: ...

    def observe(self, case: GoldenCase, mode: EvaluationMode) -> ObservedCase: ...


_METRICS = (
    "plan_fields",
    "filter_slots",
    "top_k_scope",
    "segment_assignment",
    "compatibility_partitions",
    "assembled_envelope",
    "product_set",
    "product_order",
    "numeric_values",
    "evidence_coverage",
    "answer_semantics",
    "repeat_stability",
)


class EvaluationRunner:
    def __init__(
        self,
        *,
        mode: EvaluationMode = EvaluationMode.END_TO_END,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        code_commit: Callable[[], str] | None = None,
        environment: Callable[[], Mapping[str, str]] | None = None,
    ) -> None:
        self._mode = mode
        self._clock = clock
        self._code_commit = code_commit or _code_commit
        self._environment = environment or _environment

    def run(
        self,
        cases: Sequence[GoldenCase],
        service: EvaluationService,
    ) -> EvaluationReport:
        if not cases or len({case.case_id for case in cases}) != len(cases):
            raise ValueError("evaluation cases must be nonempty with unique IDs")
        started_at = self._clock()
        versions = service.replay_versions()
        observations = tuple(service.observe(case, self._mode) for case in cases)
        scores = tuple(
            _for_mode(score_case(case, observed), self._mode)
            for case, observed in zip(cases, observations, strict=True)
        )
        latency_samples = tuple(
            sample for observed in observations for sample in observed.latency_ms
        )
        ended_at = self._clock()
        return EvaluationReport(
            replay=ReplayMetadata(
                **versions.model_dump(),
                code_commit=self._code_commit(),
                environment=dict(self._environment()),
                started_at=started_at,
                ended_at=ended_at,
                case_checksum=suite_checksum(cases),
                mode=self._mode,
            ),
            case_scores=scores,
            aggregates={metric: _aggregate(metric, scores) for metric in _METRICS},
            latency=None
            if not latency_samples
            else LatencySummary.from_milliseconds(latency_samples),
        )


def _aggregate(metric: str, scores: Sequence[CaseScore]) -> RatioScore:
    values = tuple(getattr(score, metric) for score in scores)
    numerator = sum(value.numerator for value in values)
    denominator = sum(value.denominator for value in values)
    return RatioScore(
        value=1.0 if denominator == 0 else numerator / denominator,
        numerator=numerator,
        denominator=denominator,
        failures=tuple(
            f"{score.case_id}: {failure}"
            for score, value in zip(scores, values, strict=True)
            for failure in value.failures
        ),
    )


def _for_mode(score: CaseScore, mode: EvaluationMode) -> CaseScore:
    if mode is not EvaluationMode.PLAN_ONLY:
        return score
    skipped = {
        metric: RatioScore(value=1.0, numerator=0, denominator=0)
        for metric in (
            "segment_assignment",
            "compatibility_partitions",
            "assembled_envelope",
            "product_set",
            "product_order",
            "numeric_values",
            "evidence_coverage",
            "answer_semantics",
            "repeat_stability",
        )
    }
    retained = (score.plan_fields, score.filter_slots, score.top_k_scope)
    return score.model_copy(
        update={
            **skipped,
            "failures": tuple(failure for value in retained for failure in value.failures),
        }
    )


def _code_commit(root: Path | None = None) -> str:
    repository = root or Path(__file__).resolve().parents[3]
    marker = repository / ".git"
    if marker.is_dir():
        git_dir = marker
    elif marker.is_file():
        declaration = marker.read_text(encoding="utf-8").strip()
        if not declaration.startswith("gitdir: "):
            raise RuntimeError("git worktree metadata differs")
        candidate = Path(declaration.removeprefix("gitdir: "))
        git_dir = candidate if candidate.is_absolute() else repository / candidate
    else:
        raise RuntimeError("git metadata is missing")
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        reference = head.removeprefix("ref: ")
        if not reference.startswith("refs/") or ".." in Path(reference).parts:
            raise RuntimeError("git HEAD reference differs")
        ref_path = git_dir / reference
        if ref_path.is_file():
            commit = ref_path.read_text(encoding="utf-8").strip()
        else:
            packed = (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines()
            commit = next(
                (line.split(" ", 1)[0] for line in packed if line.endswith(f" {reference}")),
                "",
            )
    else:
        commit = head
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise RuntimeError("git commit identity differs")
    return commit


def _environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "platform": platform.platform(),
    }
