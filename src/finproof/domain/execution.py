"""Validated execution contracts for the deterministic engine."""

from pydantic import BaseModel, ConfigDict


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ValidatedQueryPlan(_FrozenModel):
    pass


class ComparisonPartition(_FrozenModel):
    pass


class ExecutionSegment(_FrozenModel):
    pass


class ExecutionBundle(_FrozenModel):
    pass


class ExecutionTrace(_FrozenModel):
    pass
