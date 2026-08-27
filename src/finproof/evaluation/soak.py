"""Resumable `/answer` soak measurement with version-bound drift detection."""

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Self, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.evaluation.load import (
    LoadCase,
    LoadConfig,
    LoadRunner,
    reviewed_benchmark_mix,
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class SoakConfig(_FrozenModel):
    base_url: str
    cases: Annotated[tuple[LoadCase, ...], Field(min_length=1, max_length=1_000)]
    duration_seconds: Annotated[float, Field(gt=0, le=172_800)]
    interval_seconds: Annotated[float, Field(ge=0, le=3_600)]
    report_path: Path
    request_timeout_seconds: Annotated[float, Field(gt=0, le=15)] = 15
    max_cycles: int | None = Field(default=None, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def _validate_runtime(self) -> Self:
        LoadConfig(
            base_url=self.base_url,
            cases=self.cases,
            duration_seconds=1,
            request_timeout_seconds=self.request_timeout_seconds,
            max_requests=1,
        )
        if self.interval_seconds == 0 and self.max_cycles is None:
            raise ValueError("zero-interval soak requires an explicit cycle bound")
        return self


class SoakObservation(_FrozenModel):
    cycle: int = Field(ge=1)
    case_id: str
    question_type: str
    status_code: int | None
    response_schema_valid: bool
    answer_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    version_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    drift_detected: bool
    total_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]


class SoakReport(_FrozenModel):
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: datetime
    updated_at: datetime
    cycles_completed: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    drift_count: int = Field(ge=0)
    baseline_answers: Mapping[str, str]
    observations: tuple[SoakObservation, ...]

    @model_validator(mode="after")
    def _validate_timestamps(self) -> Self:
        if (
            self.started_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.started_at
        ):
            raise ValueError("soak timestamps must be ordered and timezone-aware")
        return self


class SoakRunner:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._load_runner = LoadRunner(transport=transport)
        self._clock = clock

    async def run(self, config: SoakConfig) -> SoakReport:
        identity = _configuration_sha256(config)
        report = self._resume(config.report_path, identity)
        deadline = report.started_at + timedelta(seconds=config.duration_seconds)
        case_by_id = {case.case_id: case for case in config.cases}
        while self._clock() < deadline and (
            config.max_cycles is None or report.cycles_completed < config.max_cycles
        ):
            load = await self._load_runner.run(
                LoadConfig(
                    base_url=config.base_url,
                    cases=config.cases,
                    concurrency=1,
                    rate_per_second=0,
                    duration_seconds=config.request_timeout_seconds * len(config.cases),
                    request_timeout_seconds=config.request_timeout_seconds,
                    max_requests=len(config.cases),
                )
            )
            cycle = report.cycles_completed + 1
            baselines = dict(report.baseline_answers)
            observations = list(report.observations)
            for sample in load.samples:
                deterministic = case_by_id[sample.case_id].deterministic
                baseline_key = (
                    f"{sample.case_id}:{sample.version_sha256}"
                    if deterministic and sample.version_sha256 and sample.answer_sha256
                    else None
                )
                drift = bool(
                    baseline_key
                    and baseline_key in baselines
                    and baselines[baseline_key] != sample.answer_sha256
                )
                if baseline_key and baseline_key not in baselines and sample.answer_sha256:
                    baselines[baseline_key] = sample.answer_sha256
                observations.append(
                    SoakObservation(
                        cycle=cycle,
                        case_id=sample.case_id,
                        question_type=sample.question_type,
                        status_code=sample.status_code,
                        response_schema_valid=sample.response_schema_valid,
                        answer_sha256=sample.answer_sha256,
                        version_sha256=sample.version_sha256,
                        drift_detected=drift,
                        total_ms=sample.total_ms,
                    )
                )
            report = report.model_copy(
                update={
                    "updated_at": self._clock(),
                    "cycles_completed": cycle,
                    "failure_count": sum(not item.response_schema_valid for item in observations),
                    "drift_count": sum(item.drift_detected for item in observations),
                    "baseline_answers": baselines,
                    "observations": tuple(observations),
                }
            )
            _write_atomic(config.report_path, report)
            if (
                self._clock() < deadline
                and (config.max_cycles is None or cycle < config.max_cycles)
                and config.interval_seconds
            ):
                await asyncio.sleep(config.interval_seconds)
        return report

    def _resume(self, path: Path, identity: str) -> SoakReport:
        if path.is_file():
            report = SoakReport.model_validate_json(path.read_text(encoding="utf-8"), strict=True)
            if report.configuration_sha256 != identity:
                raise ValueError("soak report configuration differs")
            return report
        now = self._clock()
        return SoakReport(
            configuration_sha256=identity,
            started_at=now,
            updated_at=now,
            cycles_completed=0,
            failure_count=0,
            drift_count=0,
            baseline_answers={},
            observations=(),
        )


def _configuration_sha256(config: SoakConfig) -> str:
    payload = {
        "base_url": config.base_url,
        "cases": [case.model_dump(mode="json") for case in config.cases],
        "interval_seconds": config.interval_seconds,
        "request_timeout_seconds": config.request_timeout_seconds,
    }
    return sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _write_atomic(path: Path, report: SoakReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run resumable reviewed FinProof API soak")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--interval-seconds", type=float, default=60)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation/soak.json"))
    args = parser.parse_args(argv)
    report = asyncio.run(
        SoakRunner().run(
            SoakConfig(
                base_url=cast(str, args.base_url),
                cases=reviewed_benchmark_mix(Path.cwd()),
                duration_seconds=cast(float, args.hours) * 3_600,
                interval_seconds=cast(float, args.interval_seconds),
                report_path=cast(Path, args.output),
            )
        )
    )
    sys.stdout.write(
        json.dumps(
            {
                "cycles_completed": report.cycles_completed,
                "drift_count": report.drift_count,
                "failure_count": report.failure_count,
                "output": str(args.output),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    return int(report.failure_count > 0 or report.drift_count > 0)


if __name__ == "__main__":
    raise SystemExit(main())
