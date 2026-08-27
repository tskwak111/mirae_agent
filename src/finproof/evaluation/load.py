"""Bounded async load measurement without response-body retention."""

import argparse
import asyncio
import json
import math
import sys
from collections.abc import Callable, Mapping
from hashlib import sha256
from itertools import cycle
from pathlib import Path
from time import perf_counter
from typing import Annotated, Self, cast
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from finproof.domain.execution import ExecutionTrace
from finproof.evaluation.latency import LatencySample, LatencySummary
from finproof.evaluation.loader import load_golden_cases


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class LoadCase(_FrozenModel):
    case_id: Annotated[str, Field(min_length=1, max_length=200)]
    question: Annotated[str, Field(min_length=1, max_length=4_000)]
    question_type: Annotated[str, Field(min_length=1, max_length=100)]
    weight: int = Field(default=1, ge=1, le=100)
    deterministic: bool = True


class LoadConfig(_FrozenModel):
    base_url: str
    cases: Annotated[tuple[LoadCase, ...], Field(min_length=1, max_length=1_000)]
    concurrency: int = Field(default=1, ge=1, le=64)
    rate_per_second: Annotated[float, Field(ge=0, le=1_000)] = 0
    duration_seconds: Annotated[float, Field(gt=0, le=172_800)]
    request_timeout_seconds: Annotated[float, Field(gt=0, le=15)] = 15
    max_requests: int | None = Field(default=None, ge=1, le=1_000_000)

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("load base URL must be an origin without credentials")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _validate_cases(self) -> Self:
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("load cases require unique IDs")
        return self


class LoadSample(_FrozenModel):
    request_index: int = Field(ge=0)
    case_id: str
    question_type: str
    status_code: int | None = Field(default=None, ge=100, le=599)
    total_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    stage_ms: Mapping[str, Annotated[float, Field(ge=0, allow_inf_nan=False)]]
    response_schema_valid: bool
    answer_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    version_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_category: str | None = None


class LoadReport(_FrozenModel):
    request_count: int = Field(ge=1)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    latency: LatencySummary
    samples: tuple[LoadSample, ...]


class LoadRunner:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._transport = transport
        self._clock = clock

    async def run(self, config: LoadConfig) -> LoadReport:
        weighted = tuple(case for case in config.cases for _ in range(case.weight))
        case_cycle = cycle(weighted)
        deadline = self._clock() + config.duration_seconds
        index = 0
        index_lock = asyncio.Lock()
        rate_lock = asyncio.Lock()
        next_start = self._clock()
        samples: list[LoadSample] = []

        async def next_request() -> tuple[int, LoadCase] | None:
            nonlocal index
            async with index_lock:
                if (config.max_requests is not None and index >= config.max_requests) or (
                    config.max_requests is None and self._clock() >= deadline
                ):
                    return None
                current = index
                index += 1
                return current, next(case_cycle)

        async def throttle() -> None:
            nonlocal next_start
            if config.rate_per_second == 0:
                return
            async with rate_lock:
                now = self._clock()
                wait_seconds = max(0.0, next_start - now)
                next_start = max(now, next_start) + 1 / config.rate_per_second
            if wait_seconds:
                await asyncio.sleep(wait_seconds)

        async with httpx.AsyncClient(
            base_url=config.base_url,
            transport=self._transport,
            timeout=config.request_timeout_seconds,
            follow_redirects=False,
        ) as client:

            async def worker() -> None:
                while request := await next_request():
                    request_index, case = request
                    await throttle()
                    samples.append(await self._request(client, request_index, case))

            await asyncio.gather(*(worker() for _ in range(config.concurrency)))

        ordered = tuple(sorted(samples, key=lambda sample: sample.request_index))
        latency = LatencySummary.from_samples(
            tuple(
                LatencySample(
                    total_ms=sample.total_ms,
                    stage_ms=sample.stage_ms,
                    succeeded=sample.status_code == 200 and sample.response_schema_valid,
                )
                for sample in ordered
            )
        )
        return LoadReport(
            request_count=len(ordered),
            success_count=latency.success_count,
            failure_count=latency.failure_count,
            latency=latency,
            samples=ordered,
        )

    async def _request(
        self,
        client: httpx.AsyncClient,
        request_index: int,
        case: LoadCase,
    ) -> LoadSample:
        request_id = f"LOAD-{request_index}-{case.case_id}"
        started = self._clock()
        try:
            response = await client.get(
                "/answer",
                params={"question_id": request_id, "question": case.question},
            )
        except httpx.RequestError as error:
            return LoadSample(
                request_index=request_index,
                case_id=case.case_id,
                question_type=case.question_type,
                total_ms=(self._clock() - started) * 1_000,
                stage_ms={},
                response_schema_valid=False,
                error_category=type(error).__name__,
            )
        total_ms = (self._clock() - started) * 1_000
        valid, answer_hash, version_hash, stages = _safe_response_measurement(
            response, request_id, case.question
        )
        return LoadSample(
            request_index=request_index,
            case_id=case.case_id,
            question_type=case.question_type,
            status_code=response.status_code,
            total_ms=total_ms,
            stage_ms=stages,
            response_schema_valid=valid,
            answer_sha256=answer_hash,
            version_sha256=version_hash,
            error_category=None if response.status_code == 200 and valid else "invalid_response",
        )


_RESPONSE_FIELDS = {
    "question_id",
    "question",
    "retrieved_context",
    "think_trace",
    "answer",
}
_STAGES = {"planner", "database", "evidence", "render"}


def _safe_response_measurement(
    response: httpx.Response,
    request_id: str,
    question: str,
) -> tuple[bool, str | None, str | None, dict[str, float]]:
    try:
        payload = response.json()
        if (
            response.status_code != 200
            or not isinstance(payload, dict)
            or set(payload) != _RESPONSE_FIELDS
            or not all(type(value) is str for value in payload.values())
            or payload["question_id"] != request_id
            or payload["question"] != question
        ):
            return False, None, None, {}
        trace = ExecutionTrace.model_validate_json(payload["think_trace"], strict=True)
        stages = trace.latency_ms
        if set(stages) != _STAGES or not all(
            type(value) in {int, float} and value >= 0 and math.isfinite(value)
            for value in stages.values()
        ):
            return False, None, None, {}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False, None, None, {}
    version_hash = sha256(
        json.dumps(trace.versions, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return True, sha256(payload["answer"].encode()).hexdigest(), version_hash, dict(stages)


def reviewed_benchmark_mix(repository_root: Path) -> tuple[LoadCase, ...]:
    selected = {
        "CQ-001-LOOKUP-002": ("lookup", 4),
        "CQ-003-010": ("multi_filter_rank", 3),
        "CQ-001-CROSS_PRODUCT-001": ("cross_product_split", 2),
        "CQ-001-QUALITY-001": ("quality_explanation", 1),
    }
    cases = load_golden_cases(
        tuple(sorted((repository_root / "evaluation" / "canonical").glob("*.jsonl")))
    )
    by_id = {case.case_id: case for case in cases}
    if not selected.keys() <= by_id.keys():
        raise ValueError("reviewed benchmark cases are missing")
    return tuple(
        LoadCase(
            case_id=case_id,
            question=by_id[case_id].question,
            question_type=question_type,
            weight=weight,
        )
        for case_id, (question_type, weight) in selected.items()
    )


def _write_report(path: Path, report: LoadReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded reviewed FinProof API load")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--duration-seconds", type=float, default=60)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--rate-per-second", type=float, default=0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation/load.json"))
    args = parser.parse_args(argv)
    config = LoadConfig(
        base_url=cast(str, args.base_url),
        cases=reviewed_benchmark_mix(Path.cwd()),
        concurrency=cast(int, args.concurrency),
        rate_per_second=cast(float, args.rate_per_second),
        duration_seconds=cast(float, args.duration_seconds),
    )
    report = asyncio.run(LoadRunner().run(config))
    output = cast(Path, args.output)
    _write_report(output, report)
    sys.stdout.write(
        json.dumps(
            {
                "failure_count": report.failure_count,
                "output": str(output),
                "p95_ms": report.latency.p95_ms,
                "request_count": report.request_count,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    return int(report.failure_count > 0)


if __name__ == "__main__":
    raise SystemExit(main())
