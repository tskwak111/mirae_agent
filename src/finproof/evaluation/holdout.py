"""Aggregate-only contracts for the separately custodied blind holdout."""

from datetime import datetime, timedelta
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.core.settings import ExecutionMode
from finproof.evaluation.latency import LatencySummary
from finproof.evaluation.load import LoadReport
from finproof.evaluation.runner import EvaluationMode, EvaluationReport, PlannerRuntimeMode
from finproof.evaluation.scoring import RatioScore


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


_FAMILY_COUNTS = {
    "cross_metric": 14,
    "holding_sector": 12,
    "missing_zero": 8,
    "unsupported": 8,
    "entity_variant": 6,
}
_AGGREGATE_KEYS = frozenset(
    {
        "plan_fields",
        "filter_slots",
        "top_k_scope",
        "segment_assignment",
        "compatibility_partitions",
        "assembled_envelope",
        "product_set",
        "product_order",
        "numeric_values",
        "aggregate_values",
        "evidence_coverage",
        "answer_semantics",
        "repeat_stability",
    }
)


def _is_utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


class HoldoutManifest(_FrozenModel):
    protocol_version: Literal["blind-holdout-manifest.v1"]
    suite_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: Literal[48]
    family_counts: dict[str, int]
    curator_identity: str = Field(min_length=1)
    authoring_version: str = Field(min_length=1)
    reference_version: str = Field(min_length=1)
    artifact_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def _validate_manifest(self) -> Self:
        if self.family_counts != _FAMILY_COUNTS:
            raise ValueError("holdout family counts differ")
        if not _is_utc(self.created_at):
            raise ValueError("holdout creation time must be UTC")
        return self


class HoldoutCandidateIdentity(_FrozenModel):
    protocol_version: Literal["blind-holdout-candidate.v1"]
    suite_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    artifact_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_version: str = Field(min_length=1)
    answer_prompt_version: str = Field(min_length=1)
    answer_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    planner_version: str = Field(min_length=1)
    planner_model: Literal["HCX-007"]
    response_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_at: datetime

    @model_validator(mode="after")
    def _validate_freeze_time(self) -> Self:
        if not _is_utc(self.frozen_at):
            raise ValueError("holdout freeze time must be UTC")
        return self


class HoldoutSummary(_FrozenModel):
    protocol_version: Literal["blind-holdout-summary.v1"]
    suite_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    load_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    artifact_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: Literal[48]
    family_counts: dict[str, int]
    aggregates: dict[str, RatioScore]
    request_failure_count: int = Field(ge=0)
    latency: LatencySummary

    @model_validator(mode="after")
    def _validate_minimized_aggregates(self) -> Self:
        if self.family_counts != _FAMILY_COUNTS:
            raise ValueError("holdout family counts differ")
        if set(self.aggregates) != _AGGREGATE_KEYS:
            raise ValueError("holdout aggregate keys differ")
        if any(score.failures for score in self.aggregates.values()):
            raise ValueError("holdout summary cannot contain per-case failures")
        return self


def summarize_holdout(
    manifest: HoldoutManifest,
    candidate: HoldoutCandidateIdentity,
    evaluation: EvaluationReport,
    load: LoadReport,
    *,
    evaluation_sha256: str,
    load_sha256: str,
) -> HoldoutSummary:
    """Validate a frozen replay and return only aggregate holdout evidence."""
    replay = evaluation.replay
    if (
        manifest.suite_checksum != candidate.suite_checksum
        or manifest.artifact_version != candidate.artifact_version
        or replay.case_checksum != candidate.suite_checksum
        or replay.code_commit != candidate.code_commit
        or replay.artifact_version != candidate.artifact_version
        or replay.configuration_sha256 != candidate.configuration_sha256
        or replay.prompt_version != candidate.prompt_version
        or replay.answer_prompt_version != candidate.answer_prompt_version
        or replay.answer_schema_sha256 != candidate.answer_schema_sha256
        or replay.planner_version != candidate.planner_version
        or replay.planner_model != candidate.planner_model
        or replay.execution_mode is not ExecutionMode.EVALUATION
        or replay.mode is not EvaluationMode.END_TO_END
        or replay.planner_mode is not PlannerRuntimeMode.HCX_STRUCTURED_OUTPUTS_VERIFIED_WORDING
        or replay.planner_provider != "naver-hyperclova-x"
        or not replay.hcx_enabled
        or replay.fallback_enabled
        or not replay.structured_outputs_enabled
        or not _is_utc(replay.started_at)
        or not _is_utc(replay.ended_at)
        or candidate.frozen_at > replay.started_at
        or len(evaluation.case_scores) != manifest.case_count
    ):
        raise ValueError("holdout identity differs")
    if set(evaluation.aggregates) != _AGGREGATE_KEYS:
        raise ValueError("holdout aggregate keys differ")
    if any(not sample.response_schema_valid for sample in load.samples):
        raise ValueError("holdout load contains invalid-schema response")
    if (
        load.request_count != manifest.case_count
        or len(load.samples) != manifest.case_count
        or load.latency.count != manifest.case_count
        or load.success_count + load.failure_count != manifest.case_count
        or load.success_count != load.latency.success_count
        or load.failure_count != load.latency.failure_count
        or sum(sample.request_succeeded for sample in load.samples) != load.success_count
        or {sample.request_index for sample in load.samples} != set(range(manifest.case_count))
    ):
        raise ValueError("holdout identity differs")
    response_versions = {sample.version_sha256 for sample in load.samples}
    if None in response_versions or len(response_versions) != 1:
        raise ValueError("holdout response version differs")
    (response_version,) = response_versions
    if response_version != candidate.response_version_sha256:
        raise ValueError("holdout response version differs")
    aggregates = {
        key: value.model_copy(update={"failures": ()})
        for key, value in evaluation.aggregates.items()
    }
    return HoldoutSummary(
        protocol_version="blind-holdout-summary.v1",
        suite_checksum=manifest.suite_checksum,
        evaluation_report_sha256=evaluation_sha256,
        load_report_sha256=load_sha256,
        code_commit=candidate.code_commit,
        image_digest=candidate.image_digest,
        artifact_version=candidate.artifact_version,
        configuration_sha256=candidate.configuration_sha256,
        response_version_sha256=response_version,
        case_count=manifest.case_count,
        family_counts=dict(manifest.family_counts),
        aggregates=aggregates,
        request_failure_count=load.failure_count,
        latency=load.latency,
    )
