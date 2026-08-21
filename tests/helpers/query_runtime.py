"""Shared exact Phase 2 runtime test capabilities."""

from finproof.data.artifacts.manifest import (
    ArtifactExpectedVerificationResult,
    VerifiedArtifactSet,
)
from finproof.data.artifacts.resources import expected_phase1_contract_bytes


def verified_artifacts() -> VerifiedArtifactSet:
    result = ArtifactExpectedVerificationResult.model_validate_json(
        expected_phase1_contract_bytes(),
        strict=True,
    )
    return VerifiedArtifactSet._from_expected(result)
