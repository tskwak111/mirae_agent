"""Deterministic latency samples and nearest-rank summaries."""

from collections.abc import Mapping, Sequence
from math import ceil
from statistics import fmean
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Milliseconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class LatencySample(_FrozenModel):
    total_ms: Milliseconds
    stage_ms: Mapping[str, Milliseconds] = Field(default_factory=dict)
    succeeded: bool = True

    @model_validator(mode="after")
    def _validate_stage_accounting(self) -> Self:
        if any(value > self.total_ms for value in self.stage_ms.values()):
            raise ValueError("stage latency cannot exceed total latency")
        return self


class LatencySummary(_FrozenModel):
    count: int
    success_count: int
    failure_count: int
    total_ms: Milliseconds
    mean_ms: Milliseconds
    p95_ms: Milliseconds
    stage_mean_ms: Mapping[str, Milliseconds]
    stage_p95_ms: Mapping[str, Milliseconds]

    @classmethod
    def from_milliseconds(cls, samples: Sequence[int | float]) -> Self:
        return cls.from_samples(tuple(LatencySample(total_ms=value) for value in samples))

    @classmethod
    def from_samples(cls, samples: Sequence[LatencySample]) -> Self:
        if not samples:
            raise ValueError("at least one latency sample is required")
        totals = [sample.total_ms for sample in samples]
        stage_values = {
            stage: [sample.stage_ms[stage] for sample in samples if stage in sample.stage_ms]
            for stage in sorted({stage for sample in samples for stage in sample.stage_ms})
        }
        success_count = sum(sample.succeeded for sample in samples)
        return cls(
            count=len(samples),
            success_count=success_count,
            failure_count=len(samples) - success_count,
            total_ms=sum(totals),
            mean_ms=fmean(totals),
            p95_ms=_nearest_rank(totals, 95),
            stage_mean_ms={stage: fmean(values) for stage, values in stage_values.items()},
            stage_p95_ms={
                stage: _nearest_rank(values, 95) for stage, values in stage_values.items()
            },
        )


def _nearest_rank(values: Sequence[float], percentile: int) -> float:
    ordered = sorted(values)
    return ordered[ceil(percentile * len(ordered) / 100) - 1]
