"""Path-free artifact build orchestration contracts."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.config import (
    ArtifactBuildConfig,
    ArtifactBuildOptions,
    ArtifactInputKind,
)
from finproof.data.artifacts.database import (
    _VerifierWorkspaceObservationSink,
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
    ArtifactExpectedVerificationResult,
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
    _FinalReportVerificationObservations,
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
    _ExpectedAcceptedReceiverAdmission,
)
from finproof.data.artifacts.table_specs import TABLE_SPECS
from finproof.registry.rating import RatingRegistry

NonNegativeInt = Annotated[int, Field(ge=0)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

_PHYSICAL_FILE_PATHS = tuple(
    sorted(
        (
            "finproof.duckdb",
            *(spec.parquet_path for spec in TABLE_SPECS),
            "reports/quality_summary.json",
            "reports/source_audit.json",
        )
    )
)


class ArtifactPhysicalFileHash(BaseModel):
    """One verified physical manifest entry without an artifact-root path."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    path: str
    kind: Literal["parquet", "report", "duckdb"]
    size_bytes: NonNegativeInt
    sha256: Sha256

    @model_validator(mode="after")
    def require_closed_path_kind(self) -> Self:
        if self.path not in _PHYSICAL_FILE_PATHS:
            raise ValueError("physical file path is outside the closed inventory")
        expected_kind = (
            "duckdb"
            if self.path == "finproof.duckdb"
            else "report"
            if self.path.startswith("reports/")
            else "parquet"
        )
        if self.kind != expected_kind:
            raise ValueError("physical file kind does not match its closed path")
        return self


class ArtifactManifestIdentity(BaseModel):
    """Verified logical identity of one generated manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    manifest_version: Literal["1.0.0"]
    artifact_contract_version: Literal["1.0.0"]
    artifact_set_id: Literal["finproof-data-artifacts/v1"]
    dataset_version: date
    logical_hash: Sha256

    @model_validator(mode="after")
    def require_snapshot(self) -> Self:
        if self.dataset_version != date(2026, 7, 11):
            raise ValueError("manifest telemetry requires the official snapshot")
        return self


class ArtifactWorkspaceTelemetry(BaseModel):
    """Path-free facts for one fully cleaned bounded workspace."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    mode: Literal[0o700]
    marker_owned: Literal[True]
    containment_verified: Literal[True]
    cleanup_completed: Literal[True]
    threads: Literal[1]
    memory_limit: Literal["1GiB"]


class ArtifactBuildTelemetry(BaseModel):
    """Strict bounded observations from one complete private transform."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    persistence_timestamp: datetime
    max_live_fund_group_rows: NonNegativeInt
    max_writer_batch_rows: NonNegativeInt
    max_verifier_batch_rows: NonNegativeInt
    max_bronze_reconstruction_cells: NonNegativeInt
    linked_domestic_record_json_parses: NonNegativeInt
    linked_fund_record_json_parses: NonNegativeInt
    max_live_link_keys: NonNegativeInt
    max_live_evidence_keys: NonNegativeInt
    staging_workspace: ArtifactWorkspaceTelemetry
    verifier_workspace: ArtifactWorkspaceTelemetry
    physical_files: tuple[ArtifactPhysicalFileHash, ...]
    manifest_identity: ArtifactManifestIdentity

    @model_validator(mode="after")
    def require_bounded_verified_observations(self) -> Self:
        if (
            self.persistence_timestamp.tzinfo is None
            or self.persistence_timestamp.utcoffset() != timedelta(0)
            or self.max_live_fund_group_rows > 16
            or self.max_writer_batch_rows > 65_536
            or self.max_verifier_batch_rows > 65_536
            or self.max_bronze_reconstruction_cells > 73
            or self.linked_domestic_record_json_parses > 47
            or self.linked_fund_record_json_parses > 47
            or self.max_live_link_keys > 47
            or self.max_live_evidence_keys > 371
            or tuple(value.path for value in self.physical_files) != _PHYSICAL_FILE_PATHS
        ):
            raise ValueError("artifact build telemetry is incomplete or unbounded")
        return self


class ArtifactCoreBuildOutcome(BaseModel):
    """Private verified core outcome; it carries no publication authority."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )

    manifest: ArtifactManifest
    logical_contract: ArtifactCoreVerificationResult
    telemetry: ArtifactBuildTelemetry

    @model_validator(mode="after")
    def require_one_verified_generation(self) -> Self:
        manifest = self.manifest
        logical = self.logical_contract
        telemetry = self.telemetry
        declared_reports = {
            value.report_id: value.logical_hash
            for value in manifest.files
            if value.report_id is not None
        }
        if (
            telemetry.persistence_timestamp != manifest.persistence_timestamp
            or telemetry.manifest_identity
            != ArtifactManifestIdentity(
                manifest_version=manifest.manifest_version,
                artifact_contract_version=manifest.artifact_contract_version,
                artifact_set_id=manifest.artifact_set_id,
                dataset_version=manifest.dataset_version,
                logical_hash=manifest.logical_hash,
            )
            or telemetry.physical_files
            != tuple(
                ArtifactPhysicalFileHash(
                    path=value.path,
                    kind=value.kind,
                    size_bytes=value.size_bytes,
                    sha256=value.sha256,
                )
                for value in manifest.files
            )
            or logical.artifact_contract_version != manifest.artifact_contract_version
            or logical.artifact_set_id != manifest.artifact_set_id
            or logical.dataset_version != manifest.dataset_version
            or logical.overall_manifest_logical_hash != manifest.logical_hash
            or logical.logical_inputs
            != tuple(
                ExpectedLogicalInput.model_validate(value.model_dump(), strict=True)
                for value in manifest.source_inputs
            )
            or any(
                logical_table.name != declaration.table_name
                or logical_table.grain != declaration.grain
                or logical_table.schema_hash != declaration.schema_sha256
                or logical_table.row_count != declaration.row_count
                or logical_table.sort_key != declaration.sort_key
                or logical_table.unique_key != declaration.unique_key
                or logical_table.logical_hash != declaration.logical_hash
                for logical_table, declaration in zip(
                    logical.tables,
                    (manifest.tables[spec.table_name] for spec in TABLE_SPECS),
                    strict=True,
                )
            )
            or any(
                declared_reports.get(report.report_id) != report.semantic_hash
                for report in logical.reports
            )
        ):
            raise ValueError("core outcome generations disagree")
        return self


class ArtifactBuildOutcome(BaseModel):
    """Expected-accepted published artifact result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )

    manifest: ArtifactManifest
    logical_contract: ArtifactExpectedVerificationResult
    telemetry: ArtifactBuildTelemetry

    @model_validator(mode="after")
    def require_one_published_generation(self) -> Self:
        ArtifactCoreBuildOutcome(
            manifest=self.manifest,
            logical_contract=ArtifactCoreVerificationResult.model_validate(
                self.logical_contract.model_dump(mode="python"),
                strict=True,
            ),
            telemetry=self.telemetry,
        )
        return self


@dataclass(frozen=True, slots=True)
class _CoreTelemetryObservations:
    max_live_fund_group_rows: int
    max_writer_batch_rows: int
    max_verifier_batch_rows: int
    max_bronze_reconstruction_cells: int
    linked_domestic_record_json_parses: int
    linked_fund_record_json_parses: int
    max_live_link_keys: int
    max_live_evidence_keys: int
    staging_mode: int
    verifier_workspace: ArtifactWorkspaceTelemetry


@dataclass(frozen=True, init=False, slots=True)
class _LiveArtifactBuildCandidate:
    """One provenance-bound live candidate with mutually exclusive terminal use."""

    _issuance: _LiveArtifactBuildCandidateIssuance

    def __new__(cls) -> _LiveArtifactBuildCandidate:
        raise TypeError("live candidate is builder-issued")

    def __copy__(self) -> _LiveArtifactBuildCandidate:
        raise TypeError("live candidate cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> _LiveArtifactBuildCandidate:
        del memo
        raise TypeError("live candidate cannot be copied")

    def __reduce__(self) -> str | tuple[object, ...]:
        raise TypeError("live candidate cannot be copied")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("live candidate cannot be copied")


class _LiveArtifactBuildCandidateIssuance:
    __slots__ = ("candidate", "observations", "state", "value")

    def __init__(
        self,
        value: _LiveArtifactBuildCandidate,
        *,
        candidate: CandidateArtifactSet,
        observations: _CoreTelemetryObservations,
    ) -> None:
        self.value = value
        self.candidate = candidate
        self.observations = observations
        self.state = "LIVE"


def _issue_live_artifact_build_candidate(
    *,
    candidate: CandidateArtifactSet,
    observations: _CoreTelemetryObservations,
) -> _LiveArtifactBuildCandidate:
    if (
        type(candidate) is not CandidateArtifactSet
        or type(observations) is not _CoreTelemetryObservations
    ):
        raise TypeError("live candidate requires exact finalization members")
    candidate._require_issued()
    value = object.__new__(_LiveArtifactBuildCandidate)
    object.__setattr__(
        value,
        "_issuance",
        _LiveArtifactBuildCandidateIssuance(
            value,
            candidate=candidate,
            observations=observations,
        ),
    )
    return value


def _require_live_artifact_build_candidate(
    value: object,
) -> _LiveArtifactBuildCandidateIssuance:
    if type(value) is not _LiveArtifactBuildCandidate:
        raise TypeError("live candidate requires the exact runtime type")
    try:
        issuance = object.__getattribute__(value, "_issuance")
    except AttributeError as exc:
        raise ValueError("live candidate issuance changed") from exc
    if (
        type(issuance) is not _LiveArtifactBuildCandidateIssuance
        or issuance.value is not value
        or type(issuance.candidate) is not CandidateArtifactSet
        or type(issuance.observations) is not _CoreTelemetryObservations
    ):
        raise ValueError("live candidate issuance changed")
    if issuance.state != "LIVE":
        raise ValueError("live candidate was already consumed")
    issuance.candidate._require_issued()
    return issuance


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
        admission: _ExpectedAcceptedReceiverAdmission,
    ) -> None:
        self._require_issued()
        self._custody.transfer_expected_accepted(
            expected_acceptance_seal=expected_acceptance_seal,
            admission=admission,
        )

    def issue_expected_accepted_receiver_admission(
        self,
        *,
        receiver: ExpectedAcceptedCustodyReceiver,
    ) -> _ExpectedAcceptedReceiverAdmission:
        self._require_issued()
        return self._custody.issue_expected_accepted_receiver_admission(receiver=receiver)

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
    if cast(object, custody._input_identity) is not input_identity:
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
) -> tuple[CandidateArtifactSet, _CoreTelemetryObservations]:
    complete = require_complete_artifact_build_result(complete)
    session.assert_live()
    staging_mode = cast(
        tuple[int, int, int, int],
        session.__getattribute__("_stage_identity"),
    )[3]
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
        report_observations = _FinalReportVerificationObservations()
        workspace_observations = _VerifierWorkspaceObservationSink()
        with custody.open_verification_root() as root:
            core = artifact_verification_kernel(
                report_observations=report_observations,
                workspace_observations=workspace_observations,
            ).verify_candidate_core_from_root(
                manifest=manifest,
                root=root,
            )
        candidate = _issue_candidate_artifact_set(
            custody=custody,
            manifest=manifest,
            core=core,
            input_identity=complete.silver_result.input_identity,
        )
        instrumentation = complete.silver_result.instrumentation
        exact = complete.exact_evidence_verification_observations
        workspace_facts = workspace_observations.require()
        observations = _CoreTelemetryObservations(
            max_live_fund_group_rows=instrumentation.max_live_fund_group_rows,
            max_writer_batch_rows=instrumentation.max_writer_batch_rows,
            max_verifier_batch_rows=max(
                instrumentation.max_relation_batch_rows,
                exact.max_relation_batch_rows,
                report_observations.require_max_batch_rows(),
            ),
            max_bronze_reconstruction_cells=max(
                value.observed_columns for value in complete.observations.source_tables
            ),
            linked_domestic_record_json_parses=exact.matched_left_records,
            linked_fund_record_json_parses=exact.matched_right_records,
            max_live_link_keys=len(complete.exact_link_build_result.links),
            max_live_evidence_keys=len(complete.exact_link_build_result.evidence),
            staging_mode=staging_mode,
            verifier_workspace=ArtifactWorkspaceTelemetry(
                mode=cast(Literal[0o700], workspace_facts.mode),
                marker_owned=cast(Literal[True], workspace_facts.marker_owned),
                containment_verified=cast(Literal[True], workspace_facts.containment_verified),
                cleanup_completed=cast(Literal[True], workspace_facts.cleanup_completed),
                threads=cast(Literal[1], workspace_facts.threads),
                memory_limit=cast(Literal["1GiB"], workspace_facts.memory_limit),
            ),
        )
        return candidate, observations
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
            candidate, _ = _finalize_complete_candidate(
                session=session,
                complete=complete,
                versions=versions,
            )
            return candidate
    except BaseException:
        identity.close()
        raise


def _build_private_live_candidate(
    settings: Settings,
    versions: VersionBundle,
    options: ArtifactBuildOptions,
) -> _LiveArtifactBuildCandidate:
    if (
        type(settings) is not Settings
        or type(versions) is not VersionBundle
        or type(options) is not ArtifactBuildOptions
    ):
        raise TypeError("private live-candidate builder requires exact inputs")
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
            from finproof.data.artifacts.publication import (
                _PublishedArtifactFilesystem,
                recover_owned_remnants,
            )

            recover_owned_remnants(
                settings,
                filesystem=_PublishedArtifactFilesystem._for_recovery(settings),
            )
            complete = build_complete_for_session(
                session=session,
                config=config,
                versions=versions,
            )
            candidate, observed = _finalize_complete_candidate(
                session=session,
                complete=complete,
                versions=versions,
            )
    except BaseException:
        identity.close()
        raise
    return _issue_live_artifact_build_candidate(
        candidate=candidate,
        observations=observed,
    )


def _discard_live_candidate_to_core_outcome(
    value: _LiveArtifactBuildCandidate,
) -> ArtifactCoreBuildOutcome:
    issuance = _require_live_artifact_build_candidate(value)
    candidate = issuance.candidate
    observed = issuance.observations
    manifest = candidate._manifest
    logical = candidate._core_result
    candidate._custody.discard_if_exact()
    issuance.state = "DISCARDED"
    telemetry = _artifact_build_telemetry(manifest=manifest, observed=observed)
    return ArtifactCoreBuildOutcome(
        manifest=manifest,
        logical_contract=logical,
        telemetry=telemetry,
    )


def _artifact_build_telemetry(
    *,
    manifest: ArtifactManifest,
    observed: _CoreTelemetryObservations,
) -> ArtifactBuildTelemetry:
    return ArtifactBuildTelemetry(
        persistence_timestamp=manifest.persistence_timestamp,
        max_live_fund_group_rows=observed.max_live_fund_group_rows,
        max_writer_batch_rows=observed.max_writer_batch_rows,
        max_verifier_batch_rows=observed.max_verifier_batch_rows,
        max_bronze_reconstruction_cells=observed.max_bronze_reconstruction_cells,
        linked_domestic_record_json_parses=observed.linked_domestic_record_json_parses,
        linked_fund_record_json_parses=observed.linked_fund_record_json_parses,
        max_live_link_keys=observed.max_live_link_keys,
        max_live_evidence_keys=observed.max_live_evidence_keys,
        staging_workspace=ArtifactWorkspaceTelemetry(
            mode=cast(Literal[0o700], observed.staging_mode),
            marker_owned=True,
            containment_verified=True,
            cleanup_completed=True,
            threads=1,
            memory_limit="1GiB",
        ),
        verifier_workspace=observed.verifier_workspace,
        physical_files=tuple(
            ArtifactPhysicalFileHash(
                path=file.path,
                kind=file.kind,
                size_bytes=file.size_bytes,
                sha256=file.sha256,
            )
            for file in manifest.files
        ),
        manifest_identity=ArtifactManifestIdentity(
            manifest_version=manifest.manifest_version,
            artifact_contract_version=manifest.artifact_contract_version,
            artifact_set_id=manifest.artifact_set_id,
            dataset_version=manifest.dataset_version,
            logical_hash=manifest.logical_hash,
        ),
    )


def _build_evaluation_artifacts_with_outcome(
    settings: Settings,
    versions: VersionBundle,
    *,
    options: ArtifactBuildOptions,
) -> ArtifactBuildOutcome:
    from finproof.data.artifacts.publication import (
        _PublishedArtifactFilesystem,
        authorize_candidate_for_publication,
        publish_verified_stage,
    )

    carrier = _build_private_live_candidate(settings, versions, options)
    issuance = _require_live_artifact_build_candidate(carrier)
    candidate = issuance.candidate
    try:
        with authorize_candidate_for_publication(candidate) as authorized:
            logical = publish_verified_stage(
                authorized,
                settings=settings,
                clean=options.clean,
                filesystem=_PublishedArtifactFilesystem(
                    settings=settings,
                    expected=authorized.expected_result,
                ),
            )
        issuance.state = "PUBLISHED"
        return ArtifactBuildOutcome(
            manifest=candidate._manifest,
            logical_contract=logical,
            telemetry=_artifact_build_telemetry(
                manifest=candidate._manifest,
                observed=issuance.observations,
            ),
        )
    except BaseException:
        try:
            candidate._custody.assert_live()
        except ArtifactContractError:
            pass
        else:
            candidate._custody.discard_if_exact()
        issuance.state = "DISCARDED"
        raise


def build_artifacts(
    settings: Settings,
    versions: VersionBundle,
    *,
    options: ArtifactBuildOptions,
) -> ArtifactManifest:
    """Build only after the packaged expected contract can authorize CP8."""
    if (
        type(settings) is not Settings
        or type(versions) is not VersionBundle
        or type(options) is not ArtifactBuildOptions
    ):
        raise TypeError("artifact builder requires exact settings, versions, and options")
    outcome = _build_evaluation_artifacts_with_outcome(
        settings,
        versions,
        options=options,
    )
    manifest = getattr(outcome, "manifest", None)
    if type(manifest) is not ArtifactManifest:
        raise ArtifactContractError(
            ArtifactErrorCode.VERIFICATION_INCOMPLETE,
            operation_id="build-artifacts",
            target_basename=settings.artifact_dir.name,
            internal_context={"reason": "expected_outcome_unavailable"},
        )
    return manifest
