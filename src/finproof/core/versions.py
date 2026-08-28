"""Immutable versions attached to FinProof execution."""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, PrivateAttr

from finproof.core.settings import OFFICIAL_DISTRIBUTION_DATE, ExecutionMode
from finproof.data.artifacts.manifest import VerifiedArtifactSet
from finproof.registry.loader import RegistryBundle


class VersionBundle(BaseModel):
    """Version identifiers required to reproduce an execution."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    _runtime_issuance: object = PrivateAttr(default=None)

    dataset_version: date = OFFICIAL_DISTRIBUTION_DATE
    metric_registry_version: str = "1.0.0"
    state_rule_version: str = "1.1.0"
    quality_rule_version: str = "1.0.0"
    rating_rule_version: str = "1.0.0"
    answer_policy_version: str = "1.0.0"
    planner_version: str = "1.0.0"

    @classmethod
    def from_runtime(
        cls,
        *,
        verified: VerifiedArtifactSet,
        registries: RegistryBundle,
        execution_mode: ExecutionMode,
    ) -> Self:
        if (
            cls is not VersionBundle
            or type(verified) is not VerifiedArtifactSet
            or type(registries) is not RegistryBundle
            or type(execution_mode) is not ExecutionMode
        ):
            raise TypeError("runtime version inputs differ")
        registries.require_issued()
        if verified.dataset_version != registries.datasets.snapshot_date:
            raise ValueError("runtime dataset versions differ")
        value = cls(
            dataset_version=verified.dataset_version,
            metric_registry_version=registries.metrics.version,
            state_rule_version=registries.states.version,
            quality_rule_version=registries.quality.version,
            rating_rule_version=registries.ratings.version,
            answer_policy_version=registries.answers.version,
            planner_version=registries.planner.version,
        )
        value._runtime_issuance = _RuntimeVersionIssuance(
            value=value,
            verified=verified,
            registries=registries,
            execution_mode=execution_mode,
        )
        return value

    def require_runtime(
        self,
        *,
        verified: VerifiedArtifactSet,
        registries: RegistryBundle,
    ) -> None:
        issuance = self._runtime_issuance
        if (
            type(self) is not VersionBundle
            or type(issuance) is not _RuntimeVersionIssuance
            or issuance.value is not self
            or issuance.verified is not verified
            or issuance.registries is not registries
        ):
            raise TypeError("version bundle is not runtime-issued")
        registries.require_issued()
        if self.runtime_facts() != issuance.facts:
            raise ValueError("runtime version facts changed")

    def runtime_facts(self) -> dict[str, str]:
        issuance = self._require_runtime_issuance()
        return {
            "dataset_version": self.dataset_version.isoformat(),
            "artifact_manifest_hash": issuance.verified.overall_manifest_logical_hash,
            "dataset_registry_version": issuance.registries.datasets.version,
            "field_registry_version": issuance.registries.fields.version,
            "metric_registry_version": self.metric_registry_version,
            "state_rule_version": self.state_rule_version,
            "quality_rule_version": self.quality_rule_version,
            "rating_rule_version": self.rating_rule_version,
            "answer_policy_version": self.answer_policy_version,
            "planner_version": self.planner_version,
            "execution_mode": issuance.execution_mode.value,
        }

    @property
    def artifact_manifest_hash(self) -> str:
        return self._require_runtime_issuance().verified.overall_manifest_logical_hash

    @property
    def dataset_registry_version(self) -> str:
        return self._require_runtime_issuance().registries.datasets.version

    @property
    def field_registry_version(self) -> str:
        return self._require_runtime_issuance().registries.fields.version

    @property
    def execution_mode(self) -> ExecutionMode:
        return self._require_runtime_issuance().execution_mode

    def _require_runtime_issuance(self) -> "_RuntimeVersionIssuance":
        issuance = self._runtime_issuance
        if (
            type(self) is not VersionBundle
            or type(issuance) is not _RuntimeVersionIssuance
            or issuance.value is not self
        ):
            raise TypeError("version bundle is not runtime-issued")
        return issuance


class _RuntimeVersionIssuance:
    __slots__ = ("execution_mode", "facts", "registries", "value", "verified")

    def __init__(
        self,
        *,
        value: VersionBundle,
        verified: VerifiedArtifactSet,
        registries: RegistryBundle,
        execution_mode: ExecutionMode,
    ) -> None:
        self.value = value
        self.verified = verified
        self.registries = registries
        self.execution_mode = execution_mode
        self.facts = {
            "dataset_version": value.dataset_version.isoformat(),
            "artifact_manifest_hash": verified.overall_manifest_logical_hash,
            "dataset_registry_version": registries.datasets.version,
            "field_registry_version": registries.fields.version,
            "metric_registry_version": value.metric_registry_version,
            "state_rule_version": value.state_rule_version,
            "quality_rule_version": value.quality_rule_version,
            "rating_rule_version": value.rating_rule_version,
            "answer_policy_version": value.answer_policy_version,
            "planner_version": value.planner_version,
            "execution_mode": execution_mode.value,
        }
