"""Path-free artifact build orchestration contracts."""

from finproof.data.artifacts.staging import (
    ExpectedAcceptedCustodyReceiver,
)


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
