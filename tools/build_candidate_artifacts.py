"""Repository-only candidate bootstrap guard; no artifact builder exists in CP1."""

from dataclasses import dataclass
from pathlib import Path

from finproof.core.settings import Settings
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.resources import (
    CandidateBaselineProbe,
    _expected_contract_resource_exists,
)


@dataclass(frozen=True)
class _ProductionCandidateBaselineProbe:
    """Check the two exact real baseline locations without exposing their paths."""

    settings: Settings

    def source_exists(self) -> bool:
        return _entry_exists_fail_closed(self.settings.expected_artifact_contract_path)

    def resource_exists(self) -> bool:
        return _expected_contract_resource_exists()

    def second_check(self) -> None:
        assert_candidate_bootstrap_allowed(self)


def assert_candidate_bootstrap_allowed(probe: CandidateBaselineProbe) -> None:
    """Accept an injected baseline probe before later candidate tooling exists."""
    if probe.source_exists() or probe.resource_exists():
        raise ArtifactContractError(
            ArtifactErrorCode.BASELINE_ALREADY_EXISTS,
            operation_id="build-candidate-artifacts",
        )


def _entry_exists_fail_closed(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True
