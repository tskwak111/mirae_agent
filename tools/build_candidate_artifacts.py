"""Repository-only candidate bootstrap and review output."""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.builder import (
    ArtifactCoreBuildOutcome,
    _build_private_core_outcome,
)
from finproof.data.artifacts.config import ArtifactBuildOptions
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.manifest import (
    ArtifactCoreVerificationResult,
)
from finproof.data.artifacts.resources import (
    CandidateBaselineProbe,
    _expected_contract_resource_exists,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.build_candidate_artifacts")
    parser.add_argument("--persistence-timestamp", required=True)
    return parser


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


def _build_candidate_artifacts_with_probe(
    settings: Settings,
    versions: VersionBundle,
    *,
    options: ArtifactBuildOptions,
    probe: CandidateBaselineProbe,
    transform: Callable[
        [Settings, VersionBundle, ArtifactBuildOptions],
        ArtifactCoreBuildOutcome,
    ],
    stdout: TextIO,
    stderr: TextIO,
) -> ArtifactCoreVerificationResult:
    """Run the closed two-check candidate sequence with no publication authority."""
    assert_candidate_bootstrap_allowed(probe)
    outcome = transform(settings, versions, options)
    if type(outcome) is not ArtifactCoreBuildOutcome:
        raise TypeError("candidate transform returned an invalid core outcome")
    validated = ArtifactCoreBuildOutcome.model_validate(
        outcome.model_dump(mode="python"),
        strict=True,
    )
    if validated != outcome:
        raise TypeError("candidate transform returned an invalid core outcome")
    probe.second_check()
    stdout.write(outcome.logical_contract.model_dump_json() + "\n")
    stderr.write(outcome.telemetry.model_dump_json() + "\n")
    return outcome.logical_contract


def build_candidate_artifacts(
    settings: Settings,
    versions: VersionBundle,
    *,
    options: ArtifactBuildOptions,
) -> ArtifactCoreVerificationResult:
    """Build and emit one reviewed unpublished core contract while baseline is absent."""
    return _build_candidate_artifacts_with_probe(
        settings,
        versions,
        options=options,
        probe=_ProductionCandidateBaselineProbe(settings),
        transform=_build_private_core_outcome,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        timestamp = datetime.fromisoformat(args.persistence_timestamp.replace("Z", "+00:00"))
        build_candidate_artifacts(
            Settings(),
            VersionBundle(),
            options=ArtifactBuildOptions(persistence_timestamp=timestamp),
        )
        return 0
    except (ArtifactContractError, TypeError, ValueError) as error:
        message = (
            error.safe_message if isinstance(error, ArtifactContractError) else "invalid input"
        )
        sys.stderr.write(f"error: {message}\n")
        return 2


def _entry_exists_fail_closed(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


if __name__ == "__main__":
    raise SystemExit(main())
