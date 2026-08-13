"""Immutable versions attached to FinProof execution."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class VersionBundle(BaseModel):
    """Version identifiers required to reproduce an execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: date = date(2026, 7, 11)
    metric_registry_version: str = "1.0.0"
    state_rule_version: str = "1.0.0"
    quality_rule_version: str = "1.0.0"
    rating_rule_version: str = "1.0.0"
    answer_policy_version: str = "1.0.0"
    planner_version: str = "1.0.0"
