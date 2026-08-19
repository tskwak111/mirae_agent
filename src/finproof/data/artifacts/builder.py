"""Path-free artifact build orchestration contracts."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass

from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.config import (
    ArtifactBuildConfig,
    ArtifactBuildOptions,
    ArtifactInputKind,
)
from finproof.data.artifacts.database import (
    artifact_verification_kernel,
    build_self_contained_database,
)
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.expected_contract import (
    ExpectedLogicalInput,
    ExpectedLogicalTable,
    ExpectedSemanticReport,
)
from finproof.data.artifacts.hashing import manifest_logical_hash, report_logical_hash
from finproof.data.artifacts.input_identity import (
    BuildInputIdentity,
    ResolvedBuildInputBundle,
    verify_build_inputs,
)
from finproof.data.artifacts.links import (
    ExactLinkBuildResult,
    _build_and_extend_exact_links,
    _require_exact_link_build_result_facts,
    verify_exact_link_evidence,
)
from finproof.data.artifacts.manifest import (
    ArtifactCoreVerificationResult,
    ArtifactFile,
    ArtifactManifest,
    ArtifactVersions,
    ManagedArtifactVerificationRoot,
    _ManifestLogicalProjection,
)
from finproof.data.artifacts.parquet_io import StagedParquetSet
from finproof.data.artifacts.quality_persistence import StagedBoundedRelationVerifier
from finproof.data.artifacts.reports import (
    CompleteSourceAuditObservations,
    ExactEvidenceVerificationObservations,
    QualitySummaryReport,
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
    CandidateStageCustody,
    ExpectedAcceptedCustodyReceiver,
)
from finproof.data.artifacts.table_specs import TABLE_SPECS
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
    _require_exact_link_build_result_facts(value.exact_link_build_result)
    require_complete_source_audit_observations(value.observations)
    if (
        value.observations.exact_links.observed != len(value.exact_link_build_result.links)
        or value.observations.exact_link_evidence.observed
        != len(value.exact_link_build_result.evidence)
        or value.observations.exact_link_pair_sha256.observed
        != value.exact_link_build_result.pair_sha256
        or value.exact_evidence_verification_observations.exact_links
        is not value.observations.exact_links
        or value.exact_evidence_verification_observations.exact_link_evidence
        is not value.observations.exact_link_evidence
        or value.exact_evidence_verification_observations.exact_link_pair_sha256
        is not value.observations.exact_link_pair_sha256
    ):
        raise ValueError("complete artifact exact-link facts disagree")
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
    try:
        try:
            link_result, successor = _build_and_extend_exact_links(
                silver_result=silver_result,
                custody=custody,
                config=config,
                owner=session,
            )
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
        finally:
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

    __slots__ = (
        "_core_result",
        "_custody",
        "_input_identity",
        "_issuance",
        "_manifest",
    )

    _core_result: ArtifactCoreVerificationResult
    _custody: CandidateStageCustody
    _input_identity: BuildInputIdentity
    _issuance: _CandidateArtifactSetIssuance
    _manifest: ArtifactManifest

    def __new__(cls) -> CandidateArtifactSet:
        raise TypeError("CandidateArtifactSet is builder-owned")

    def open_verification_root(
        self,
    ) -> AbstractContextManager[ManagedArtifactVerificationRoot]:
        self._require_issued()
        return self._custody.open_verification_root()

    def transfer_expected_accepted_custody(
        self,
        *,
        expected_acceptance_seal: object,
        receiver: ExpectedAcceptedCustodyReceiver,
    ) -> None:
        self._require_issued()
        self._custody.transfer_expected_accepted(
            expected_acceptance_seal=expected_acceptance_seal,
            receiver=receiver,
        )

    def _require_issued(self) -> None:
        if (
            type(self._issuance) is not _CandidateArtifactSetIssuance
            or self._issuance.value is not self
            or self._issuance.custody is not self._custody
            or self._issuance.manifest is not self._manifest
            or self._issuance.core is not self._core_result
            or self._issuance.input_identity is not self._input_identity
        ):
            raise ValueError("candidate artifact set issuance changed")
        self._custody.assert_live()
        self._manifest.require_build_input_identity(self._input_identity)


class _CandidateArtifactSetIssuance:
    __slots__ = ("core", "custody", "input_identity", "manifest", "value")

    def __init__(
        self,
        value: CandidateArtifactSet,
        *,
        custody: CandidateStageCustody,
        manifest: ArtifactManifest,
        core: ArtifactCoreVerificationResult,
        input_identity: BuildInputIdentity,
    ) -> None:
        self.value = value
        self.custody = custody
        self.manifest = manifest
        self.core = core
        self.input_identity = input_identity


def _issue_candidate_artifact_set(
    *,
    custody: CandidateStageCustody,
    manifest: ArtifactManifest,
    core: ArtifactCoreVerificationResult,
    input_identity: BuildInputIdentity,
) -> CandidateArtifactSet:
    if (
        type(custody) is not CandidateStageCustody
        or type(manifest) is not ArtifactManifest
        or type(core) is not ArtifactCoreVerificationResult
        or type(input_identity) is not BuildInputIdentity
    ):
        raise TypeError("candidate artifact set requires exact issued inputs")
    custody.assert_live()
    if custody._input_identity is not input_identity:  # type: ignore[attr-defined]
        raise ValueError("candidate build input identity changed")
    manifest.require_build_input_identity(input_identity)
    value = object.__new__(CandidateArtifactSet)
    value._custody = custody
    value._manifest = manifest
    value._core_result = core
    value._input_identity = input_identity
    value._issuance = _CandidateArtifactSetIssuance(
        value,
        custody=custody,
        manifest=manifest,
        core=core,
        input_identity=input_identity,
    )
    return value


def _report_bytes(report: SourceAuditReport | QualitySummaryReport) -> bytes:
    return (report.model_dump_json(indent=2) + "\n").encode("utf-8")


def _finalize_complete_candidate(
    *,
    session: ArtifactBuildSession,
    complete: CompleteArtifactBuildResult,
    versions: VersionBundle,
) -> CandidateArtifactSet:
    complete = require_complete_artifact_build_result(complete)
    tables = complete.staged_tables
    tables.require_complete()
    if tables.persistence_timestamp != session.persistence_timestamp:
        raise ValueError("candidate table timestamp changed")
    database = build_self_contained_database(
        owner=session,
        tables=tables,
        database_leaf=session.claim_database_leaf(),
    )
    database.validate_against(session)
    source_report = complete.source_audit_report
    quality_report = complete.silver_result.quality_report
    report_facts: dict[str, tuple[int, str]] = {}
    for report in (source_report, quality_report):
        report_facts[report.report_id] = session._write_final_artifact(
            relative_path=(
                "reports/source_audit.json"
                if report.report_id == "source_audit"
                else "reports/quality_summary.json"
            ),
            payload=_report_bytes(report),
        )
    declarations = tables.table_declarations()
    table_by_name = {value.table_name: value for value in declarations}
    files = [
        ArtifactFile(
            path="finproof.duckdb",
            kind="duckdb",
            size_bytes=database.physical_size_bytes,
            sha256=database.physical_sha256,
            report_id=None,
            logical_hash=None,
        )
    ]
    for spec in TABLE_SPECS:
        verification = tables.verification_for(spec.table_name)
        files.append(
            ArtifactFile(
                path=spec.parquet_path,
                kind="parquet",
                size_bytes=verification.physical_size_bytes,
                sha256=verification.physical_sha256,
                report_id=None,
                logical_hash=None,
            )
        )
    for report in (source_report, quality_report):
        size_bytes, sha256 = report_facts[report.report_id]
        files.append(
            ArtifactFile(
                path=f"reports/{report.report_id}.json",
                kind="report",
                size_bytes=size_bytes,
                sha256=sha256,
                report_id=report.report_id,
                logical_hash=report_logical_hash(report),
            )
        )
    ordered_files = tuple(sorted(files, key=lambda value: value.path))
    artifact_versions = ArtifactVersions.model_validate(
        versions.model_dump(mode="python"),
        strict=True,
    )
    logical_inputs = tuple(
        ExpectedLogicalInput.model_validate(value.model_dump(mode="python"), strict=True)
        for value in complete.silver_result.input_identity.logical_inputs
    )
    logical_tables = tuple(
        ExpectedLogicalTable(
            name=value.table_name,
            grain=value.grain,
            schema_hash=value.schema_sha256,
            row_count=value.row_count,
            sort_key=value.sort_key,
            unique_key=value.unique_key,
            logical_hash=value.logical_hash,
        )
        for value in declarations
    )
    logical_reports = (
        ExpectedSemanticReport(
            report_id="source_audit",
            semantic_hash=report_logical_hash(source_report),
        ),
        ExpectedSemanticReport(
            report_id="quality_summary",
            semantic_hash=report_logical_hash(quality_report),
        ),
    )
    logical_hash = manifest_logical_hash(
        _ManifestLogicalProjection(
            manifest_version="1.0.0",
            artifact_contract_version="1.0.0",
            artifact_set_id="finproof-data-artifacts/v1",
            dataset_version=versions.dataset_version,
            logical_inputs=logical_inputs,
            versions=artifact_versions,
            tables=logical_tables,
            reports=logical_reports,
        )
    )
    manifest = ArtifactManifest.from_build(
        input_identity=complete.silver_result.input_identity,
        persistence_timestamp=tables.persistence_timestamp,
        versions=artifact_versions,
        files=ordered_files,
        database_sha256=database.physical_sha256,
        tables={name: table_by_name[name] for name in sorted(table_by_name)},
        logical_hash=logical_hash,
    )
    manifest_payload = (manifest.model_dump_json(indent=2) + "\n").encode("utf-8")
    if ArtifactManifest._from_bytes(manifest_payload) != manifest:
        raise ValueError("candidate manifest changed during strict reparse")
    session._write_final_artifact(
        relative_path="manifest.json",
        payload=manifest_payload,
    )
    database.validate_against(session)
    tables.require_complete()
    transferred = session.transfer_candidate_stage()
    custody = transferred.issue_candidate_custody()
    try:
        with custody.open_verification_root() as root:
            core = artifact_verification_kernel().verify_candidate_core_from_root(
                manifest=manifest,
                root=root,
            )
        return _issue_candidate_artifact_set(
            custody=custody,
            manifest=manifest,
            core=core,
            input_identity=complete.silver_result.input_identity,
        )
    except BaseException:
        custody.close()
        raise


def build_verified_candidate_stage(
    settings: Settings,
    versions: VersionBundle,
    options: ArtifactBuildOptions,
) -> CandidateArtifactSet:
    """Build and core-verify one unpublished candidate through retained custody."""
    if (
        type(settings) is not Settings
        or type(versions) is not VersionBundle
        or type(options) is not ArtifactBuildOptions
    ):
        raise TypeError("candidate builder requires exact settings, versions, and options")
    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        identity = BuildInputIdentity.from_verified(seal=held.issue_identity_seal())
    try:
        with identity.open_verified_input(kind=ArtifactInputKind.ARTIFACT_BUILD_CONFIG) as stream:
            config = ArtifactBuildConfig.from_held_stream(stream, versions=versions)
        with ArtifactBuildSession.initialize(
            settings,
            versions,
            options,
            input_identity=identity,
        ) as session:
            complete = build_complete_for_session(
                session=session,
                config=config,
                versions=versions,
            )
            return _finalize_complete_candidate(
                session=session,
                complete=complete,
                versions=versions,
            )
    except BaseException:
        identity.close()
        raise
