"""Path-free artifact build orchestration contracts."""

from finproof.core.versions import VersionBundle
from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactInputKind
from finproof.data.artifacts.input_identity import BuildInputIdentity
from finproof.data.artifacts.silver import SilverArtifactEmitter, SilverBuildResult
from finproof.data.artifacts.staging import (
    ArtifactBuildSession,
    ExpectedAcceptedCustodyReceiver,
)
from finproof.registry.rating import RatingRegistry


def build_silver_for_session(
    *,
    session: ArtifactBuildSession,
    config: ArtifactBuildConfig,
    versions: VersionBundle,
) -> SilverBuildResult:
    """Build Silver through one held rating input and one Bronze-fed source pass."""
    input_identity = session._input_identity
    if (
        type(session) is not ArtifactBuildSession
        or type(config) is not ArtifactBuildConfig
        or type(versions) is not VersionBundle
        or session._versions is not versions
        or type(input_identity) is not BuildInputIdentity
    ):
        raise TypeError("Silver builder requires exact retained build inputs")
    session.assert_live()
    with input_identity.open_verified_input(
        kind=ArtifactInputKind.RATING_SCALE_REGISTRY
    ) as rating_stream:
        rating_registry = RatingRegistry.from_held_stream(rating_stream)
        input_identity.assert_unchanged()
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=rating_registry,
        )
        bronze_result = session.ingest_bronze(consumer=emitter)
        return emitter.finalize(bronze_result=bronze_result)


class CandidateArtifactSet:
    """Candidate bridge retaining one exact staging-owned custody capability."""

    def __new__(cls) -> "CandidateArtifactSet":
        raise TypeError("CandidateArtifactSet is builder-owned")

    def transfer_expected_accepted_custody(
        self,
        *,
        expected_acceptance_seal: object,
        receiver: ExpectedAcceptedCustodyReceiver,
    ) -> None:
        del expected_acceptance_seal, receiver
        raise NotImplementedError("expected-accepted custody transfer unavailable")
