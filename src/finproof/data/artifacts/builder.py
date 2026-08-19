"""Path-free artifact build orchestration contracts."""

from __future__ import annotations

from dataclasses import dataclass

from finproof.core.versions import VersionBundle
from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactInputKind
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.input_identity import BuildInputIdentity
from finproof.data.artifacts.links import (
    ExactLinkBuildResult,
    _build_and_extend_exact_links,
    verify_exact_link_evidence,
)
from finproof.data.artifacts.parquet_io import StagedParquetSet
from finproof.data.artifacts.quality_persistence import StagedBoundedRelationVerifier
from finproof.data.artifacts.reports import (
    CompleteSourceAuditObservations,
    ExactEvidenceVerificationObservations,
    SourceAuditReport,
    require_complete_source_audit_observations,
)
from finproof.data.artifacts.silver import (
    SilverArtifactEmitter,
    SilverBuildResult,
    require_silver_build_result_successor,
    take_exact_link_candidate_store,
)
from finproof.data.artifacts.staging import (
    ArtifactBuildSession,
    ExpectedAcceptedCustodyReceiver,
)
from finproof.registry.rating import RatingRegistry


class _CompleteArtifactBuildProvenance:
    __slots__ = ("_issuance",)

    _issuance: object


@dataclass(frozen=True, init=False, slots=True)
class CompleteArtifactBuildResult(_CompleteArtifactBuildProvenance):
    """Exact six-member CP7 handoff issued after complete CP6 verification."""

    silver_result: SilverBuildResult
    staged_tables: StagedParquetSet
    exact_link_build_result: ExactLinkBuildResult
    exact_evidence_verification_observations: ExactEvidenceVerificationObservations
    observations: CompleteSourceAuditObservations
    source_audit_report: SourceAuditReport

    def __new__(cls, *args: object, **kwargs: object) -> CompleteArtifactBuildResult:
        del args, kwargs
        raise TypeError("CompleteArtifactBuildResult is builder-issued")


class _CompleteArtifactBuildIssuance:
    __slots__ = ("custody", "members", "value")

    def __init__(self, value: CompleteArtifactBuildResult, *, custody: object) -> None:
        self.value = value
        self.custody = custody
        self.members = tuple(getattr(value, name) for name in value.__dataclass_fields__)


def require_complete_artifact_build_result(value: object) -> CompleteArtifactBuildResult:
    from finproof.data.artifacts.links import _ExactLinkBuildResultIssuance
    from finproof.data.artifacts.reports import _ExactEvidenceVerificationIssuance
    from finproof.data.artifacts.staging import ExactLinkCandidateStoreCustody

    if type(value) is not CompleteArtifactBuildResult:
        raise TypeError("complete artifact result must have the exact runtime type")
    issuance = object.__getattribute__(value, "_issuance")
    members = tuple(getattr(value, name) for name in value.__dataclass_fields__)
    if (
        type(issuance) is not _CompleteArtifactBuildIssuance
        or issuance.value is not value
        or any(
            actual is not expected
            for actual, expected in zip(issuance.members, members, strict=True)
        )
        or type(issuance.custody) is not ExactLinkCandidateStoreCustody
        or issuance.custody._candidate_state != "CLOSED"
    ):
        raise ValueError("complete artifact result issuance changed")
    require_silver_build_result_successor(
        silver_result=value.silver_result,
        successor=value.staged_tables,
    )
    link_issuance = object.__getattribute__(value.exact_link_build_result, "_issuance")
    verification_issuance = object.__getattribute__(
        value.exact_evidence_verification_observations,
        "_issuance",
    )
    if (
        type(link_issuance) is not _ExactLinkBuildResultIssuance
        or link_issuance.silver_result is not value.silver_result
        or link_issuance.custody is not issuance.custody
        or type(verification_issuance) is not _ExactEvidenceVerificationIssuance
        or verification_issuance.value is not value.exact_evidence_verification_observations
        or verification_issuance.owner is not value.exact_link_build_result
    ):
        raise ValueError("complete artifact link provenance changed")
    require_complete_source_audit_observations(value.observations)
    report = SourceAuditReport.model_validate(
        value.source_audit_report.model_dump(mode="python"),
        strict=True,
    )
    if (
        report != value.source_audit_report
        or value.source_audit_report.source_tables is not value.observations.source_tables
        or value.source_audit_report.silver_tables is not value.observations.silver_tables
        or value.source_audit_report.exact_links is not value.observations.exact_links
        or value.source_audit_report.exact_link_evidence
        is not value.observations.exact_link_evidence
        or value.source_audit_report.exact_link_pair_sha256
        is not value.observations.exact_link_pair_sha256
    ):
        raise ValueError("complete artifact report provenance changed")
    return value


def build_complete_for_session(
    *,
    session: ArtifactBuildSession,
    config: ArtifactBuildConfig,
    versions: VersionBundle,
) -> CompleteArtifactBuildResult:
    if (
        type(session) is not ArtifactBuildSession
        or type(config) is not ArtifactBuildConfig
        or type(versions) is not VersionBundle
        or session._versions is not versions
    ):
        raise TypeError("complete builder requires exact retained inputs")
    silver_result = build_silver_for_session(
        session=session,
        config=config,
        versions=versions,
    )
    custody = take_exact_link_candidate_store(silver_result=silver_result)
    link_result, successor = _build_and_extend_exact_links(
        silver_result=silver_result,
        custody=custody,
        config=config,
        owner=session,
    )
    try:
        relation_verifier = StagedBoundedRelationVerifier.for_candidate_custody(custody)
        verified = verify_exact_link_evidence(
            tables=successor,
            relation_verifier=relation_verifier,
            build_result=link_result,
            config=config,
        )
        observations = silver_result.observations.with_links(verified=verified)
        report = SourceAuditReport.from_complete_observations(
            config=config,
            observations=observations,
        )
        custody.close()
    except ArtifactContractError:
        raise
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        raise ArtifactContractError(
            ArtifactErrorCode.SERIALIZATION_FAILED,
            operation_id="build-complete-artifacts",
            internal_context={"reason": "postextension_verification_failed"},
        ) from exc
    value = object.__new__(CompleteArtifactBuildResult)
    for name, member in (
        ("silver_result", silver_result),
        ("staged_tables", successor),
        ("exact_link_build_result", link_result),
        ("exact_evidence_verification_observations", verified),
        ("observations", observations),
        ("source_audit_report", report),
    ):
        object.__setattr__(value, name, member)
    object.__setattr__(
        value,
        "_issuance",
        _CompleteArtifactBuildIssuance(value, custody=custody),
    )
    return value


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

    def __new__(cls) -> CandidateArtifactSet:
        raise TypeError("CandidateArtifactSet is builder-owned")

    def transfer_expected_accepted_custody(
        self,
        *,
        expected_acceptance_seal: object,
        receiver: ExpectedAcceptedCustodyReceiver,
    ) -> None:
        del expected_acceptance_seal, receiver
        raise NotImplementedError("expected-accepted custody transfer unavailable")
