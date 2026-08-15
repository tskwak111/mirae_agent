# mypy: disable-error-code="assignment,attr-defined,has-type,misc,union-attr"
"""Descriptor-owned build staging capabilities.

Private capability objects use guarded ``object.__new__`` ownership transfers. Mypy
cannot model those slot-only transfers; public boundaries remain explicitly typed.
"""

import fcntl
import hashlib
import heapq
import json
import os
import re
import secrets
import stat
from collections.abc import Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from types import TracebackType
from typing import TYPE_CHECKING, Any, BinaryIO, Protocol, Self, cast

import duckdb

from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.input_identity import BuildInputIdentity
from finproof.data.artifacts.manifest import (
    ManagedArtifactVerificationRoot,
    _issue_held_artifact_root_adoption,
    adopt_held_artifact_root,
)
from finproof.data.artifacts.parquet_io import (
    OwnedParquetVerificationWorkspace,
    OwnedStageArtifactOwner,
)
from finproof.data.artifacts.table_specs import (
    TableSpec,
    require_registered_table_spec,
)

if TYPE_CHECKING:
    from finproof.data.artifacts.bronze import BronzeBuildResult, SourceRowConsumer

_TRANSFERRED_STAGE_SLOTS = (
    "_database_claimed",
    "_database_leaf",
    "_input_identity",
    "_lock_fd",
    "_marker_identity",
    "_marker_name",
    "_marker_payload",
    "_operation_id",
    "_parent_fd",
    "_parquet_fd",
    "_registered_parquet_names",
    "_registered_stage_names",
    "_sealed_database",
    "_sealed_issuance",
    "_sealed_leaf_token",
    "_sealed_owner_token",
    "_stage_fd",
    "_stage_identity",
    "_stage_name",
    "_target_basename",
    "_timestamp",
    "_claimed_specs",
    "_leaf_objects",
    "_staged_pairs",
    "_staged_sets",
)


class ArtifactBuildSession:
    """Sole owner of one pre-publication artifact staging session."""

    _settings: Settings

    __slots__ = (
        "_claimed_specs",
        "_closed",
        "_database_claimed",
        "_database_leaf",
        "_input_identity",
        "_leaf_objects",
        "_lock_fd",
        "_marker_identity",
        "_marker_name",
        "_marker_payload",
        "_operation_id",
        "_parent_fd",
        "_parquet_fd",
        "_registered_parquet_names",
        "_registered_stage_names",
        "_sealed_database",
        "_sealed_issuance",
        "_sealed_leaf_token",
        "_sealed_owner_token",
        "_settings",
        "_stage_fd",
        "_stage_identity",
        "_stage_name",
        "_staged_pairs",
        "_staged_sets",
        "_state",
        "_target_basename",
        "_timestamp",
    )

    def __new__(cls) -> "ArtifactBuildSession":
        raise TypeError("ArtifactBuildSession is factory-owned")

    @classmethod
    def initialize(
        cls,
        settings: Settings,
        versions: VersionBundle,
        options: ArtifactBuildOptions,
        *,
        input_identity: BuildInputIdentity,
    ) -> AbstractContextManager["ArtifactBuildSession"]:
        del cls
        return _initialize_session(settings, versions, options, input_identity)

    @property
    def persistence_timestamp(self) -> datetime:
        self.assert_live()
        return cast(datetime, self._timestamp)

    def __enter__(self) -> Self:
        self.assert_live()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self._abort_initial_stage()

    def assert_live(self) -> None:
        if self._state != "LIVE" or self._closed:
            raise _staging_error("session_not_live")

    def abort(self) -> None:
        self.assert_live()
        self._abort_initial_stage()

    def ingest_bronze(
        self,
        *,
        consumer: "SourceRowConsumer | None" = None,
    ) -> "BronzeBuildResult":
        from finproof.data.artifacts.bronze import ingest_bronze_for_session

        return ingest_bronze_for_session(self, consumer=consumer)

    def transfer_candidate_stage(self) -> "OwnedCandidateStage":
        self.assert_live()
        _require_session_generation(self)
        value = object.__new__(OwnedCandidateStage)
        for name in _TRANSFERRED_STAGE_SLOTS:
            setattr(value, name, getattr(self, name))
        value._closed = False
        value._state = "LIVE"
        self._parquet_fd = -1
        self._stage_fd = -1
        self._lock_fd = -1
        self._parent_fd = -1
        self._input_identity = None
        self._closed = True
        self._state = "CLOSED"
        return value

    def claim_parquet_leaf(self, spec: TableSpec) -> "_OwnedParquetLeaf":
        self.assert_live()
        try:
            registered = require_registered_table_spec(spec)
            if registered.table_name in self._claimed_specs:
                raise ValueError("Parquet leaf was already claimed")
            relative = PurePosixPath(registered.parquet_path)
            if relative.parent != PurePosixPath("parquet"):
                raise ValueError("Parquet leaf is outside the fixed directory")
            value = _OwnedParquetLeaf._issue(self, registered)
            self._claimed_specs.add(registered.table_name)
            self._leaf_objects[registered.table_name] = value
            return value
        except (AttributeError, TypeError, ValueError) as exc:
            raise _stage_contract_error("invalid_parquet_leaf_claim") from exc

    def require_owned_parquet_leaf(self, leaf: object) -> None:
        self.assert_live()
        try:
            if (
                type(leaf) is not _OwnedParquetLeaf
                or leaf._owner is not self
                or type(leaf._issuance) is not _ParquetLeafIssuance
                or leaf._issuance.owner is not self
                or leaf._issuance.leaf is not leaf
                or self._leaf_objects.get(leaf._spec.table_name) is not leaf
            ):
                raise ValueError("Parquet leaf is not owned by this session")
        except (AttributeError, TypeError, ValueError) as exc:
            raise _stage_contract_error("unowned_parquet_leaf") from exc

    def _register_staged_verification(self, value: object, handle: object) -> object:
        self.assert_live()
        token = object()
        self._staged_pairs[id(value)] = (value, handle, token)
        return token

    def _require_registered_staged_verification(
        self,
        value: object,
        handle: object,
        token: object,
    ) -> None:
        self.assert_live()
        pair = self._staged_pairs.get(id(value))
        if (
            pair is None
            or pair != (value, handle, token)
            or pair[0] is not value
            or pair[1] is not handle
            or pair[2] is not token
        ):
            raise _stage_contract_error("unregistered_staged_verification")

    def _require_registered_staged_handle(self, handle: object, token: object) -> None:
        self.assert_live()
        if not any(pair[1] is handle and pair[2] is token for pair in self._staged_pairs.values()):
            raise _stage_contract_error("unregistered_staged_handle")

    def _register_staged_set(self, value: object) -> object:
        self.assert_live()
        token = object()
        self._staged_sets[id(value)] = (value, token)
        return token

    def _replace_registered_staged_set(self, previous: object, value: object) -> object:
        self.assert_live()
        prior = self._staged_sets.get(id(previous))
        if prior is None or prior[0] is not previous:
            raise _stage_contract_error("unregistered_staged_set")
        token = self._register_staged_set(value)
        del self._staged_sets[id(previous)]
        return token

    def _require_registered_staged_set(self, value: object, token: object) -> None:
        self.assert_live()
        pair = self._staged_sets.get(id(value))
        if pair is None or pair[0] is not value or pair[1] is not token:
            raise _stage_contract_error("unregistered_staged_set")

    def open_external_order_store(
        self,
        *,
        config: ArtifactBuildConfig,
    ) -> AbstractContextManager["ExternalOrderStore"]:
        return _open_external_order_store_for_test(
            owner=self,
            config=config,
            limits=ExternalOrderStoreTestLimits(
                batch_rows=65_536,
                memory_limit_bytes=1 << 30,
            ),
        )

    def claim_database_leaf(self) -> "OwnedStageDatabaseLeaf":
        self.assert_live()
        if self._database_claimed:
            raise _stage_contract_error("database_leaf_already_claimed")
        value = _OwnedDatabaseLeaf._issue(self)
        self._database_claimed = True
        self._database_leaf = value
        return value

    def create_database_build_workspace(
        self,
    ) -> AbstractContextManager["ManagedStageDatabaseBuild"]:
        self.assert_live()
        return _open_managed_stage_database_build(self)

    def require_owned_database_leaf(self, leaf: "OwnedStageDatabaseLeaf") -> None:
        self.assert_live()
        try:
            if (
                type(leaf) is not _OwnedDatabaseLeaf
                or self._database_leaf is not leaf
                or leaf._owner is not self
                or type(leaf._issuance) is not _DatabaseLeafIssuance
                or leaf._issuance.owner is not self
                or leaf._issuance.leaf is not leaf
            ):
                raise ValueError("database leaf is not exact-owner issued")
        except (AttributeError, TypeError, ValueError) as exc:
            raise _stage_contract_error("unowned_database_leaf") from exc

    def _register_sealed_database(
        self,
        value: "SealedStageDatabase",
        leaf: "OwnedStageDatabaseLeaf",
    ) -> tuple[object, object]:
        self.assert_live()
        self.require_owned_database_leaf(leaf)
        if type(value) is not SealedStageDatabase or self._sealed_database is not None:
            raise _stage_contract_error("invalid_sealed_database_registration")
        owner_token = object()
        leaf_token = object()
        self._sealed_database = value
        self._sealed_owner_token = owner_token
        self._sealed_leaf_token = leaf_token
        issuance = _SealedDatabaseIssuance(
            owner=self,
            leaf=leaf,
            seal=value,
            owner_token=owner_token,
            leaf_token=leaf_token,
        )
        self._sealed_issuance = issuance
        object.__setattr__(value, "_issuance", issuance)
        return owner_token, leaf_token

    def _require_registered_sealed_database(
        self,
        value: "SealedStageDatabase",
        leaf: "OwnedStageDatabaseLeaf",
        owner_token: object,
        leaf_token: object,
    ) -> None:
        self.assert_live()
        self.require_owned_database_leaf(leaf)
        if (
            type(value) is not SealedStageDatabase
            or self._sealed_database is not value
            or self._sealed_owner_token is not owner_token
            or self._sealed_leaf_token is not leaf_token
            or type(value._issuance) is not _SealedDatabaseIssuance
            or self._sealed_issuance is not value._issuance
            or value._issuance.owner is not self
            or value._issuance.leaf is not leaf
            or value._issuance.seal is not value
            or value._issuance.owner_token is not owner_token
            or value._issuance.leaf_token is not leaf_token
            or value._issuance.persistence_timestamp is not value.persistence_timestamp
            or value._issuance.physical_size_bytes != value.physical_size_bytes
            or value._issuance.physical_sha256 != value.physical_sha256
        ):
            raise _stage_contract_error("unregistered_sealed_database")
        leaf.assert_unchanged()

    def _abort_initial_stage(self) -> None:
        if self._closed:
            return
        self._state = "CLOSING"
        failed = False
        try:
            _require_session_generation(self)
            for leaf in reversed(tuple(self._leaf_objects.values())):
                if not leaf._created or leaf._identity is None:
                    continue
                leaf_name = PurePosixPath(leaf._spec.parquet_path).name
                named = os.stat(leaf_name, dir_fd=self._parquet_fd, follow_symlinks=False)
                if _leaf_identity(named) != leaf._identity:
                    raise ValueError("owned Parquet leaf changed before abort")
                os.unlink(leaf_name, dir_fd=self._parquet_fd)
                self._registered_parquet_names.remove(leaf_name)
                leaf._created = False
                leaf._identity = None
            os.close(self._parquet_fd)
            self._parquet_fd = -1
            os.rmdir("parquet", dir_fd=self._stage_fd)
            os.close(self._stage_fd)
            self._stage_fd = -1
            os.rmdir(self._stage_name, dir_fd=self._parent_fd)
            os.unlink(self._marker_name, dir_fd=self._parent_fd)
        except (ArtifactContractError, OSError, TypeError, ValueError):
            failed = True
        finally:
            for descriptor_name in ("_parquet_fd", "_stage_fd"):
                descriptor = getattr(self, descriptor_name)
                if descriptor >= 0:
                    with suppress(OSError):
                        os.close(descriptor)
                    setattr(self, descriptor_name, -1)
            self._input_identity.close()
            with suppress(OSError):
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            with suppress(OSError):
                os.close(self._lock_fd)
            with suppress(OSError):
                os.close(self._parent_fd)
            self._closed = True
            self._state = "CLOSED"
        if failed:
            raise _staging_error("initial_stage_cleanup_failed")


class OwnedCandidateStage:
    """Transferred owner of one complete unpublished stage."""

    __slots__ = (
        "_claimed_specs",
        "_closed",
        "_database_claimed",
        "_database_leaf",
        "_input_identity",
        "_leaf_objects",
        "_lock_fd",
        "_marker_identity",
        "_marker_name",
        "_marker_payload",
        "_operation_id",
        "_parent_fd",
        "_parquet_fd",
        "_registered_parquet_names",
        "_registered_stage_names",
        "_sealed_database",
        "_sealed_issuance",
        "_sealed_leaf_token",
        "_sealed_owner_token",
        "_stage_fd",
        "_stage_identity",
        "_stage_name",
        "_staged_pairs",
        "_staged_sets",
        "_state",
        "_target_basename",
        "_timestamp",
    )

    def __new__(cls) -> "OwnedCandidateStage":
        raise TypeError("OwnedCandidateStage is session-owned")

    @property
    def persistence_timestamp(self) -> datetime:
        self.assert_live()
        return cast(datetime, self._timestamp)

    def assert_live(self) -> None:
        if self._closed or self._state != "LIVE":
            raise _staging_error("candidate_stage_not_live")
        try:
            _require_session_generation(self)
        except (OSError, TypeError, ValueError) as exc:
            raise _staging_error("candidate_stage_generation_changed") from exc

    def issue_candidate_custody(self) -> "CandidateStageCustody":
        self.assert_live()
        value = object.__new__(CandidateStageCustody)
        for name in _TRANSFERRED_STAGE_SLOTS:
            setattr(value, name, getattr(self, name))
        value._closed = False
        value._state = "LIVE"
        self._parquet_fd = -1
        self._stage_fd = -1
        self._lock_fd = -1
        self._parent_fd = -1
        self._input_identity = None
        self._closed = True
        self._state = "CLOSED"
        return value

    def close(self) -> None:
        self.assert_live()
        self._state = "CLOSING"
        failed = False
        try:
            os.close(self._parquet_fd)
            self._parquet_fd = -1
            os.rmdir("parquet", dir_fd=self._stage_fd)
            os.close(self._stage_fd)
            self._stage_fd = -1
            os.rmdir(self._stage_name, dir_fd=self._parent_fd)
            os.unlink(self._marker_name, dir_fd=self._parent_fd)
        except (OSError, TypeError, ValueError):
            failed = True
        finally:
            for descriptor in (self._parquet_fd, self._stage_fd):
                if descriptor >= 0:
                    with suppress(OSError):
                        os.close(descriptor)
            self._input_identity.close()
            with suppress(OSError):
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            for descriptor in (self._lock_fd, self._parent_fd):
                with suppress(OSError):
                    os.close(descriptor)
            self._closed = True
            self._state = "CLOSED"
        if failed:
            raise _staging_error("candidate_stage_cleanup_failed")

    def __copy__(self) -> "OwnedCandidateStage":
        raise TypeError("OwnedCandidateStage cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "OwnedCandidateStage":
        del memo
        raise TypeError("OwnedCandidateStage cannot be copied")

    def __reduce__(self) -> str | tuple[Any, ...]:
        raise TypeError("OwnedCandidateStage cannot be copied")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("OwnedCandidateStage cannot be subclassed")


class CandidateStageCustody:
    """Opaque one-use candidate-stage custody."""

    __slots__ = OwnedCandidateStage.__slots__

    def __new__(cls) -> "CandidateStageCustody":
        raise TypeError("CandidateStageCustody is stage-owned")

    def assert_live(self) -> None:
        try:
            if self._closed or self._state != "LIVE":
                raise ValueError("candidate custody is closed")
            _require_session_generation(self)
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            raise _staging_error("candidate_custody_not_live") from exc

    def open_verification_root(
        self,
    ) -> AbstractContextManager[ManagedArtifactVerificationRoot]:
        self.assert_live()
        try:
            adoption = _issue_held_artifact_root_adoption(
                parent_fd=os.dup(self._parent_fd),
                basename=self._stage_name,
                root_fd=os.dup(self._stage_fd),
            )
            return adopt_held_artifact_root(adoption)
        except (ArtifactContractError, OSError, TypeError, ValueError) as exc:
            raise _staging_error("candidate_verification_root_unavailable") from exc

    def discard_if_exact(self) -> None:
        self.close()

    def close(self) -> None:
        self.assert_live()
        self._state = "CLOSING"
        failed = False
        try:
            os.close(self._parquet_fd)
            self._parquet_fd = -1
            os.rmdir("parquet", dir_fd=self._stage_fd)
            os.close(self._stage_fd)
            self._stage_fd = -1
            os.rmdir(self._stage_name, dir_fd=self._parent_fd)
            os.unlink(self._marker_name, dir_fd=self._parent_fd)
        except (OSError, TypeError, ValueError):
            failed = True
        finally:
            for descriptor in (self._parquet_fd, self._stage_fd):
                if descriptor >= 0:
                    with suppress(OSError):
                        os.close(descriptor)
            self._input_identity.close()
            with suppress(OSError):
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            for descriptor in (self._lock_fd, self._parent_fd):
                with suppress(OSError):
                    os.close(descriptor)
            self._closed = True
            self._state = "CLOSED"
        if failed:
            raise _staging_error("candidate_custody_cleanup_failed")

    def transfer_expected_accepted(
        self,
        *,
        expected_acceptance_seal: object,
        receiver: "ExpectedAcceptedCustodyReceiver",
    ) -> None:
        del expected_acceptance_seal, receiver
        self.assert_live()
        raise _staging_error("expected_accepted_transfer_unavailable")

    def __copy__(self) -> "CandidateStageCustody":
        raise TypeError("CandidateStageCustody cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "CandidateStageCustody":
        del memo
        raise TypeError("CandidateStageCustody cannot be copied")

    def __reduce__(self) -> str | tuple[Any, ...]:
        raise TypeError("CandidateStageCustody cannot be copied")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("CandidateStageCustody cannot be subclassed")


@dataclass(frozen=True, slots=True)
class ExternalOrderStoreTestLimits:
    """Private bounded-state overrides used only by focused tests."""

    batch_rows: int
    memory_limit_bytes: int

    def __post_init__(self) -> None:
        if (
            type(self.batch_rows) is not int
            or not 1 <= self.batch_rows <= 65_536
            or type(self.memory_limit_bytes) is not int
            or self.memory_limit_bytes <= 0
        ):
            raise ValueError("external order limits must be strict positive integers")


class ExternalOrderRelation(StrEnum):
    """Closed CP4 relation names accepted by the bounded order store."""

    BRONZE_SOURCE_ROW = "bronze_source_row"


class OwnedStageDatabaseLeaf(Protocol):
    """Owner-bound final database leaf capability."""

    @property
    def relative_path(self) -> PurePosixPath: ...

    def create_exclusive(self) -> AbstractContextManager[BinaryIO]: ...

    def open_verified(self) -> AbstractContextManager[BinaryIO]: ...

    def assert_unchanged(self) -> None: ...

    def unlink_if_exact_writer_owned(self) -> None: ...


class OwnedStageDatabaseOwner(OwnedStageArtifactOwner, Protocol):
    """Exact CP4 owner interface consumed by the CP7 database writer."""

    def claim_database_leaf(self) -> OwnedStageDatabaseLeaf: ...

    def create_database_build_workspace(
        self,
    ) -> AbstractContextManager["ManagedStageDatabaseBuild"]: ...

    def require_owned_database_leaf(self, leaf: OwnedStageDatabaseLeaf) -> None: ...

    def _register_sealed_database(
        self,
        value: "SealedStageDatabase",
        leaf: OwnedStageDatabaseLeaf,
    ) -> tuple[object, object]: ...

    def _require_registered_sealed_database(
        self,
        value: "SealedStageDatabase",
        leaf: OwnedStageDatabaseLeaf,
        owner_token: object,
        leaf_token: object,
    ) -> None: ...


class ManagedStageDatabaseBuild(Protocol):
    """Pathless managed scratch database contract."""

    def open_writer(self) -> AbstractContextManager[duckdb.DuckDBPyConnection]: ...

    def checkpoint_close_and_seal(
        self,
        *,
        leaf: OwnedStageDatabaseLeaf,
    ) -> "SealedStageDatabase": ...


@dataclass(frozen=True, init=False, slots=True)
class SealedStageDatabase:
    """Neutral exact owner/leaf-registered database physical seal."""

    _owner: OwnedStageDatabaseOwner
    _leaf: OwnedStageDatabaseLeaf
    _owner_registration: object
    _leaf_issuance_token: object
    _issuance: "_SealedDatabaseIssuance"
    persistence_timestamp: datetime
    physical_size_bytes: int
    physical_sha256: str

    def __new__(cls) -> "SealedStageDatabase":
        raise TypeError("SealedStageDatabase is owner-issued")

    def validate_against(self, owner: OwnedStageDatabaseOwner) -> None:
        try:
            if (
                type(self.persistence_timestamp) is not datetime
                or self.persistence_timestamp.tzinfo is None
                or self.persistence_timestamp.utcoffset() is None
                or type(self.physical_size_bytes) is not int
                or self.physical_size_bytes <= 0
                or re.fullmatch(r"[0-9a-f]{64}", self.physical_sha256) is None
            ):
                raise ValueError("sealed database facts are invalid")
            owner._require_registered_sealed_database(
                self,
                self._leaf,
                self._owner_registration,
                self._leaf_issuance_token,
            )
            if self._owner is not owner:
                raise ValueError("sealed database owner changed")
        except (AttributeError, TypeError, ValueError) as exc:
            raise _stage_contract_error("invalid_sealed_database") from exc


class _SealedDatabaseIssuance:
    __slots__ = (
        "leaf",
        "leaf_token",
        "owner",
        "owner_token",
        "persistence_timestamp",
        "physical_sha256",
        "physical_size_bytes",
        "seal",
    )

    def __init__(
        self,
        *,
        owner: ArtifactBuildSession,
        leaf: OwnedStageDatabaseLeaf,
        seal: SealedStageDatabase,
        owner_token: object,
        leaf_token: object,
    ) -> None:
        self.owner = owner
        self.leaf = leaf
        self.seal = seal
        self.owner_token = owner_token
        self.leaf_token = leaf_token
        self.persistence_timestamp = seal.persistence_timestamp
        self.physical_size_bytes = seal.physical_size_bytes
        self.physical_sha256 = seal.physical_sha256


class _DatabaseLeafIssuance:
    __slots__ = ("leaf", "owner")

    def __init__(self, owner: ArtifactBuildSession) -> None:
        self.owner = owner
        self.leaf: _OwnedDatabaseLeaf | None = None


class _OwnedDatabaseLeaf:
    __slots__ = ("_created", "_identity", "_issuance", "_owner", "_parent_mutation")

    def __new__(cls) -> "_OwnedDatabaseLeaf":
        raise TypeError("database leaves are owner-issued")

    @classmethod
    def _issue(cls, owner: ArtifactBuildSession) -> "_OwnedDatabaseLeaf":
        value = object.__new__(cls)
        issuance = _DatabaseLeafIssuance(owner)
        value._owner = owner
        value._issuance = issuance
        issuance.leaf = value
        value._created = False
        value._identity: tuple[int, int, int, int, int] | None = None
        value._parent_mutation: tuple[int, int] | None = None
        return value

    @property
    def relative_path(self) -> PurePosixPath:
        self._owner.require_owned_database_leaf(self)
        return PurePosixPath("finproof.duckdb")

    @contextmanager
    def create_exclusive(self) -> Iterator[BinaryIO]:
        self._owner.require_owned_database_leaf(self)
        if self._created:
            raise _stage_contract_error("database_leaf_already_created")
        descriptor = -1
        try:
            descriptor = os.open(
                "finproof.duckdb",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=self._owner._stage_fd,
            )
            os.fchmod(descriptor, 0o600)
            self._identity = _leaf_identity(os.fstat(descriptor))
            self._created = True
            self._owner._registered_stage_names.add("finproof.duckdb")
            _refresh_owned_database_mutation(self._owner)
            with os.fdopen(descriptor, "w+b", closefd=True) as stream:
                descriptor = -1
                yield cast(BinaryIO, stream)
                stream.flush()
                os.fsync(stream.fileno())
            self._require_unchanged()
        except ArtifactContractError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("database_leaf_create_failed") from exc
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)

    def open_verified(self) -> AbstractContextManager[BinaryIO]:
        return self._open_verified()

    @contextmanager
    def _open_verified(self) -> Iterator[BinaryIO]:
        self._require_unchanged()
        descriptor = -1
        try:
            descriptor = os.open(
                "finproof.duckdb",
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=self._owner._stage_fd,
            )
            if _leaf_identity(os.fstat(descriptor)) != self._identity:
                raise ValueError("database leaf changed while opening")
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                yield cast(BinaryIO, stream)
            self._require_unchanged()
        except ArtifactContractError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("database_leaf_open_failed") from exc
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)

    def assert_unchanged(self) -> None:
        self._require_unchanged()

    def unlink_if_exact_writer_owned(self) -> None:
        self._require_unchanged()
        try:
            os.unlink("finproof.duckdb", dir_fd=self._owner._stage_fd)
            self._owner._registered_stage_names.remove("finproof.duckdb")
            self._created = False
            self._identity = None
            self._parent_mutation = None
            _refresh_owned_database_mutation(self._owner)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("database_leaf_unlink_failed") from exc

    def _require_unchanged(self) -> None:
        self._owner.require_owned_database_leaf(self)
        if not self._created or self._identity is None:
            raise _stage_contract_error("database_leaf_not_created")
        try:
            named = os.stat(
                "finproof.duckdb",
                dir_fd=self._owner._stage_fd,
                follow_symlinks=False,
            )
            if (
                _leaf_identity(named) != self._identity
                or _directory_mutation(os.fstat(self._owner._stage_fd)) != self._parent_mutation
            ):
                raise ValueError("database leaf generation changed")
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("database_leaf_generation_changed") from exc

    def __copy__(self) -> "_OwnedDatabaseLeaf":
        raise TypeError("OwnedStageDatabaseLeaf cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "_OwnedDatabaseLeaf":
        del memo
        raise TypeError("OwnedStageDatabaseLeaf cannot be copied")

    def __reduce__(self) -> str | tuple[Any, ...]:
        raise TypeError("OwnedStageDatabaseLeaf cannot be copied")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("OwnedStageDatabaseLeaf cannot be subclassed")


class _ManagedDatabaseBuild:
    __slots__ = (
        "_connection",
        "_connection_closed",
        "_marker_identity",
        "_marker_payload",
        "_owner",
        "_physical_sha256",
        "_physical_size_bytes",
        "_rescanned_tables",
        "_scratch_identity",
        "_spill_fd",
        "_spill_identity",
        "_state",
        "_workspace_fd",
        "_workspace_identity",
        "_workspace_name",
        "_writer_issued",
    )

    def __new__(cls) -> "_ManagedDatabaseBuild":
        raise TypeError("database build workspaces are owner-issued")

    def __enter__(self) -> Self:
        self._require_live()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        if self._state == "AMBIGUOUS":
            raise _staging_error("database_workspace_cleanup_ambiguous")
        if self._state in {"LIVE", "CHECKPOINTED", "COPIED", "VERIFIED", "SEALED"}:
            self._discard()

    @contextmanager
    def open_writer(self) -> Iterator[duckdb.DuckDBPyConnection]:
        self._require_live()
        if self._writer_issued:
            raise _stage_contract_error("database_writer_already_issued")
        self._writer_issued = True
        yield self._connection

    def checkpoint_close_and_seal(
        self,
        *,
        leaf: OwnedStageDatabaseLeaf,
    ) -> SealedStageDatabase:
        self._require_live()
        self._owner.require_owned_database_leaf(leaf)
        if not self._writer_issued:
            raise _stage_contract_error("database_writer_not_issued")
        try:
            self._connection.execute("CHECKPOINT")
            self._connection.close()
            self._connection_closed = True
        except BaseException as exc:
            self._state = "AMBIGUOUS"
            raise _stage_contract_error("database_checkpoint_close_failed") from exc
        try:
            os.stat(
                "scratch.duckdb.wal",
                dir_fd=self._workspace_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            self._state = "AMBIGUOUS"
            raise _stage_contract_error("database_wal_present")
        self._state = "CHECKPOINTED"
        source_descriptor = -1
        try:
            source_descriptor = os.open(
                "scratch.duckdb",
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=self._workspace_fd,
            )
            if _leaf_identity(os.fstat(source_descriptor)) != self._scratch_identity:
                raise ValueError("scratch database generation changed")
            with os.fdopen(source_descriptor, "rb", closefd=True) as source:
                source_descriptor = -1
                with leaf.create_exclusive() as target:
                    while True:
                        payload = source.read(1024 * 1024)
                        if not payload:
                            break
                        target.write(payload)
            self._state = "COPIED"
        except BaseException as exc:
            self._state = "AMBIGUOUS"
            raise _stage_contract_error("database_final_copy_failed") from exc
        finally:
            if source_descriptor >= 0:
                with suppress(OSError):
                    os.close(source_descriptor)
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with leaf.open_verified() as stream:
                while True:
                    payload = stream.read(1024 * 1024)
                    if not payload:
                        break
                    size_bytes += len(payload)
                    digest.update(payload)
            final_path = f"{_descriptor_path(self._owner._stage_fd)}/finproof.duckdb"
            verification = duckdb.connect(final_path, read_only=True)
            try:
                verification.execute("SET threads = 1")
                verification.execute("SET enable_external_access = false")
                verification.execute("SET allow_unsigned_extensions = false")
                verification.execute("SET autoinstall_known_extensions = false")
                verification.execute("SET autoload_known_extensions = false")
                rows = verification.execute(
                    "SELECT table_name, estimated_size FROM duckdb_tables() "
                    "WHERE database_name = current_database() AND schema_name = 'main' "
                    "ORDER BY table_name"
                ).fetchall()
            finally:
                verification.close()
            leaf.assert_unchanged()
            self._physical_size_bytes = size_bytes
            self._physical_sha256 = digest.hexdigest()
            self._rescanned_tables = tuple((str(row[0]), int(row[1])) for row in rows)
            self._state = "VERIFIED"
        except BaseException as exc:
            self._state = "AMBIGUOUS"
            raise _stage_contract_error("database_final_reopen_failed") from exc
        value = object.__new__(SealedStageDatabase)
        object.__setattr__(value, "_owner", self._owner)
        object.__setattr__(value, "_leaf", leaf)
        object.__setattr__(
            value,
            "persistence_timestamp",
            self._owner.persistence_timestamp,
        )
        object.__setattr__(value, "physical_size_bytes", self._physical_size_bytes)
        object.__setattr__(value, "physical_sha256", self._physical_sha256)
        owner_token, leaf_token = self._owner._register_sealed_database(value, leaf)
        object.__setattr__(value, "_owner_registration", owner_token)
        object.__setattr__(value, "_leaf_issuance_token", leaf_token)
        value.validate_against(self._owner)
        self._state = "SEALED"
        return value

    def _require_live(self) -> None:
        if self._state != "LIVE":
            raise _stage_contract_error("database_workspace_not_live")
        self._owner.assert_live()

    def _discard(self) -> None:
        if self._state not in {
            "LIVE",
            "CHECKPOINTED",
            "COPIED",
            "VERIFIED",
            "SEALED",
        }:
            raise _stage_contract_error("database_workspace_not_discardable")
        self._owner.assert_live()
        failed = False
        try:
            if not self._connection_closed:
                self._connection.close()
                self._connection_closed = True
            _require_database_workspace(self)
            if self._state in {"VERIFIED", "SEALED"}:
                leaf = self._owner._database_leaf
                if leaf is None:
                    raise ValueError("verified database leaf is missing")
                leaf._require_unchanged()
            with os.scandir(self._spill_fd) as entries:
                spill_names = tuple(
                    entry.name
                    for entry in entries
                    if _leaf_identity(entry.stat(follow_symlinks=False))
                )
            for name in spill_names:
                os.unlink(name, dir_fd=self._spill_fd)
            os.close(self._spill_fd)
            self._spill_fd = -1
            os.rmdir("spill", dir_fd=self._workspace_fd)
            for name in ("scratch.duckdb.wal", "scratch.duckdb"):
                with suppress(FileNotFoundError):
                    os.unlink(name, dir_fd=self._workspace_fd)
            os.unlink(".marker", dir_fd=self._workspace_fd)
            os.close(self._workspace_fd)
            self._workspace_fd = -1
            os.rmdir(self._workspace_name, dir_fd=self._owner._stage_fd)
            self._owner._registered_stage_names.remove(self._workspace_name)
            _refresh_owned_database_mutation(self._owner)
            self._state = "CLOSED"
        except BaseException:
            self._state = "AMBIGUOUS"
            failed = True
        finally:
            for descriptor_name in ("_spill_fd", "_workspace_fd"):
                descriptor = getattr(self, descriptor_name)
                if descriptor >= 0:
                    with suppress(OSError):
                        os.close(descriptor)
                    setattr(self, descriptor_name, -1)
        if failed:
            raise _staging_error("database_workspace_cleanup_failed")


def _open_managed_stage_database_build(
    owner: ArtifactBuildSession,
) -> AbstractContextManager[ManagedStageDatabaseBuild]:
    owner.assert_live()
    workspace_name = f".finproof-database-build-{secrets.token_hex(16)}"
    workspace_fd = -1
    spill_fd = -1
    marker_fd = -1
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        os.mkdir(workspace_name, 0o700, dir_fd=owner._stage_fd)
        owner._registered_stage_names.add(workspace_name)
        workspace_fd = os.open(
            workspace_name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=owner._stage_fd,
        )
        os.fchmod(workspace_fd, 0o700)
        os.mkdir("spill", 0o700, dir_fd=workspace_fd)
        spill_fd = os.open(
            "spill",
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=workspace_fd,
        )
        os.fchmod(spill_fd, 0o700)
        marker_payload = json.dumps(
            {"operation_id": owner._operation_id, "workspace": workspace_name},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        marker_fd = os.open(
            ".marker",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=workspace_fd,
        )
        os.fchmod(marker_fd, 0o600)
        os.write(marker_fd, marker_payload)
        os.fsync(marker_fd)
        marker_identity = _leaf_identity(os.fstat(marker_fd))
        os.close(marker_fd)
        marker_fd = -1
        workspace_path = f"{_descriptor_path(owner._stage_fd)}/{workspace_name}"
        connection = duckdb.connect(f"{workspace_path}/scratch.duckdb")
        _configure_stage_database_connection(
            connection,
            temp_directory=f"{workspace_path}/spill",
        )
        value = object.__new__(_ManagedDatabaseBuild)
        value._connection = connection
        value._connection_closed = False
        value._marker_identity = marker_identity
        value._marker_payload = marker_payload
        value._owner = owner
        value._physical_sha256 = ""
        value._physical_size_bytes = 0
        value._rescanned_tables = ()
        value._scratch_identity = _leaf_identity(
            os.stat("scratch.duckdb", dir_fd=workspace_fd, follow_symlinks=False)
        )
        value._spill_fd = spill_fd
        value._spill_identity = _directory_identity(os.fstat(spill_fd))
        value._state = "LIVE"
        value._workspace_fd = workspace_fd
        value._workspace_identity = _directory_identity(os.fstat(workspace_fd))
        value._workspace_name = workspace_name
        value._writer_issued = False
        return value
    except BaseException as exc:
        if connection is not None:
            with suppress(BaseException):
                connection.close()
        for descriptor in (marker_fd, spill_fd, workspace_fd):
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
        raise _stage_contract_error("open_database_workspace_failed") from exc


def _configure_stage_database_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    temp_directory: str,
) -> None:
    connection.execute("SET threads = 1")
    connection.execute("SET memory_limit = '1GiB'")
    connection.execute("SET preserve_insertion_order = true")
    connection.execute("SET TimeZone = 'UTC'")
    connection.execute("SET temp_directory = ?", [temp_directory])
    connection.execute("SET enable_external_access = false")
    connection.execute("SET allow_unsigned_extensions = false")
    connection.execute("SET autoinstall_known_extensions = false")
    connection.execute("SET autoload_known_extensions = false")


def _require_database_workspace(build: _ManagedDatabaseBuild) -> None:
    named = os.stat(
        build._workspace_name,
        dir_fd=build._owner._stage_fd,
        follow_symlinks=False,
    )
    spill_named = os.stat(
        "spill",
        dir_fd=build._workspace_fd,
        follow_symlinks=False,
    )
    scratch_named = os.stat(
        "scratch.duckdb",
        dir_fd=build._workspace_fd,
        follow_symlinks=False,
    )
    if (
        _directory_identity(named) != build._workspace_identity
        or _directory_identity(os.fstat(build._workspace_fd)) != build._workspace_identity
        or _directory_identity(spill_named) != build._spill_identity
        or _directory_identity(os.fstat(build._spill_fd)) != build._spill_identity
        or _leaf_identity(scratch_named) != build._scratch_identity
    ):
        raise ValueError("database workspace generation changed")
    with os.scandir(build._workspace_fd) as entries:
        names = {entry.name for entry in entries}
    if names != {".marker", "spill", "scratch.duckdb"}:
        raise ValueError("database workspace inventory changed")
    marker = os.open(
        ".marker",
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=build._workspace_fd,
    )
    try:
        if (
            _leaf_identity(os.fstat(marker)) != build._marker_identity
            or _read_bounded_descriptor(marker) != build._marker_payload
        ):
            raise ValueError("database workspace marker changed")
    finally:
        os.close(marker)


class ExternalOrderStore:
    """Pathless owner-managed external ordering store."""

    __slots__ = (
        "_cleanup_state",
        "_closed",
        "_connection",
        "_database_identity",
        "_forced_spill_names",
        "_limits",
        "_marker_identity",
        "_marker_payload",
        "_owner",
        "_spill_fd",
        "_spill_identity",
        "_workspace_fd",
        "_workspace_identity",
        "_workspace_name",
    )

    def __new__(cls) -> "ExternalOrderStore":
        raise TypeError("ExternalOrderStore is session-owned")

    def __enter__(self) -> Self:
        self._require_live()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close_and_remove_working_state()

    def close_and_remove_working_state(self) -> None:
        """Close first, then remove only this exact store-owned generation."""
        self._close_working_state()

    def insert_batch(
        self,
        *,
        relation: ExternalOrderRelation,
        rows: Iterable[tuple[str, str]],
    ) -> None:
        self._require_live()
        table_name = _external_order_table(relation)
        if self._limits.memory_limit_bytes != 1 << 30:
            self._insert_forced_spill_runs(rows)
            return
        try:
            iterator = iter(rows)
            while True:
                batch: list[tuple[str, str]] = []
                for _ in range(self._limits.batch_rows):
                    try:
                        row = next(iterator)
                    except StopIteration:
                        break
                    if (
                        type(row) is not tuple
                        or len(row) != 2
                        or type(row[0]) is not str
                        or type(row[1]) is not str
                    ):
                        raise ValueError("external order row is not canonical")
                    batch.append(row)
                if not batch:
                    return
                self._connection.executemany(
                    f"INSERT INTO {table_name} VALUES (?, ?)",  # noqa: S608 -- enum allowlist
                    batch,
                )
                if len(batch) < self._limits.batch_rows:
                    return
        except (duckdb.Error, TypeError, ValueError) as exc:
            raise _stage_contract_error("external_order_insert_failed") from exc

    def iter_ordered_batches(
        self,
        *,
        relation: ExternalOrderRelation,
    ) -> Iterator[tuple[tuple[str, str], ...]]:
        self._require_live()
        table_name = _external_order_table(relation)
        if self._forced_spill_names:
            yield from self._iter_forced_spill_batches()
            return
        try:
            cursor = self._connection.execute(
                f"SELECT sort_key, payload FROM {table_name} ORDER BY sort_key, payload"  # noqa: S608 -- enum allowlist
            )
            while True:
                rows = cursor.fetchmany(self._limits.batch_rows)
                if not rows:
                    return
                yield tuple((str(row[0]), str(row[1])) for row in rows)
        except (duckdb.Error, TypeError, ValueError) as exc:
            raise _stage_contract_error("external_order_read_failed") from exc

    def _insert_forced_spill_runs(
        self,
        rows: Iterable[tuple[str, str]],
    ) -> None:
        try:
            iterator = iter(rows)
            while True:
                batch: list[tuple[str, str]] = []
                for _ in range(self._limits.batch_rows):
                    try:
                        row = next(iterator)
                    except StopIteration:
                        break
                    if (
                        type(row) is not tuple
                        or len(row) != 2
                        or type(row[0]) is not str
                        or type(row[1]) is not str
                    ):
                        raise ValueError("external order row is not canonical")
                    batch.append(row)
                if not batch:
                    return
                batch.sort()
                name = f"run-{len(self._forced_spill_names):08d}.jsonl"
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=self._spill_fd,
                )
                try:
                    os.fchmod(descriptor, 0o600)
                    with os.fdopen(descriptor, "wb", closefd=True) as stream:
                        descriptor = -1
                        for row in batch:
                            stream.write(
                                json.dumps(
                                    row,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ).encode("utf-8")
                                + b"\n"
                            )
                        stream.flush()
                        os.fsync(stream.fileno())
                    self._forced_spill_names.append(name)
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                if len(batch) < self._limits.batch_rows:
                    return
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("external_order_insert_failed") from exc

    def _iter_forced_spill_batches(
        self,
    ) -> Iterator[tuple[tuple[str, str], ...]]:
        streams: list[BinaryIO] = []
        try:
            heap: list[tuple[str, str, int]] = []
            for index, name in enumerate(self._forced_spill_names):
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=self._spill_fd,
                )
                stream = cast(BinaryIO, os.fdopen(descriptor, "rb", closefd=True))
                streams.append(stream)
                row = _read_external_spill_row(stream)
                if row is not None:
                    heapq.heappush(heap, (row[0], row[1], index))
            output: list[tuple[str, str]] = []
            previous_key: str | None = None
            while heap:
                key, payload, index = heapq.heappop(heap)
                if key == previous_key:
                    raise ValueError("external order key is not unique")
                previous_key = key
                output.append((key, payload))
                next_row = _read_external_spill_row(streams[index])
                if next_row is not None:
                    heapq.heappush(heap, (next_row[0], next_row[1], index))
                if len(output) == self._limits.batch_rows:
                    yield tuple(output)
                    output.clear()
            if output:
                yield tuple(output)
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("external_order_read_failed") from exc
        finally:
            for stream in streams:
                with suppress(OSError):
                    stream.close()

    def _require_live(self) -> None:
        if self._closed:
            raise _stage_contract_error("external_order_store_closed")
        self._owner.assert_live()

    def _close_working_state(self) -> None:
        if self._cleanup_state == "CLEANED":
            return
        if self._cleanup_state != "LIVE":
            raise _staging_error("external_order_store_cleanup_ambiguous")
        self._cleanup_state = "CLOSING"
        try:
            self._connection.close()
            _require_external_order_workspace(self)
            with os.scandir(self._spill_fd) as entries:
                spill_names = tuple(
                    entry.name
                    for entry in entries
                    if _leaf_identity(entry.stat(follow_symlinks=False))
                )
            for name in spill_names:
                os.unlink(name, dir_fd=self._spill_fd)
            os.close(self._spill_fd)
            self._spill_fd = -1
            os.rmdir("spill", dir_fd=self._workspace_fd)
            for name in ("store.duckdb.wal", "store.duckdb"):
                with suppress(FileNotFoundError):
                    os.unlink(name, dir_fd=self._workspace_fd)
            os.unlink(".marker", dir_fd=self._workspace_fd)
            os.close(self._workspace_fd)
            self._workspace_fd = -1
            os.rmdir(self._workspace_name, dir_fd=self._owner._stage_fd)
            self._owner._registered_stage_names.remove(self._workspace_name)
            self._cleanup_state = "CLEANED"
        except (
            ArtifactContractError,
            BaseException,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            self._cleanup_state = "AMBIGUOUS"
            raise _staging_error("external_order_store_cleanup_failed") from exc
        finally:
            for descriptor_name in ("_spill_fd", "_workspace_fd"):
                descriptor = getattr(self, descriptor_name)
                if descriptor >= 0:
                    with suppress(OSError):
                        os.close(descriptor)
                    setattr(self, descriptor_name, -1)
            self._closed = True


def _open_external_order_store_for_test(
    *,
    owner: ArtifactBuildSession,
    config: ArtifactBuildConfig,
    limits: ExternalOrderStoreTestLimits,
) -> AbstractContextManager[ExternalOrderStore]:
    owner.assert_live()
    if (
        type(owner) is not ArtifactBuildSession
        or type(config) is not ArtifactBuildConfig
        or type(limits) is not ExternalOrderStoreTestLimits
        or config.staging.threads != 1
        or config.staging.memory_limit != "1GiB"
    ):
        raise _stage_contract_error("invalid_external_order_store_contract")
    workspace_name = f".finproof-order-store-{secrets.token_hex(16)}"
    workspace_fd = -1
    spill_fd = -1
    marker_fd = -1
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        os.mkdir(workspace_name, 0o700, dir_fd=owner._stage_fd)
        owner._registered_stage_names.add(workspace_name)
        workspace_fd = os.open(
            workspace_name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=owner._stage_fd,
        )
        os.fchmod(workspace_fd, 0o700)
        os.mkdir("spill", 0o700, dir_fd=workspace_fd)
        spill_fd = os.open(
            "spill",
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=workspace_fd,
        )
        os.fchmod(spill_fd, 0o700)
        marker_payload = json.dumps(
            {
                "operation_id": owner._operation_id,
                "workspace": workspace_name,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        marker_fd = os.open(
            ".marker",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=workspace_fd,
        )
        os.fchmod(marker_fd, 0o600)
        os.write(marker_fd, marker_payload)
        os.fsync(marker_fd)
        marker_identity = _leaf_identity(os.fstat(marker_fd))
        os.close(marker_fd)
        marker_fd = -1
        workspace_path = f"{_descriptor_path(owner._stage_fd)}/{workspace_name}"
        connection = duckdb.connect(f"{workspace_path}/store.duckdb")
        _configure_external_order_connection(
            connection,
            temp_directory=f"{workspace_path}/spill",
        )
        if limits.memory_limit_bytes != 1 << 30:
            _configure_external_order_test_limits(
                connection,
                memory_limit_bytes=limits.memory_limit_bytes,
            )
        connection.execute(
            "CREATE TABLE order_bronze_source_row "
            "(sort_key VARCHAR NOT NULL, payload VARCHAR NOT NULL)"
        )
        value = object.__new__(ExternalOrderStore)
        value._cleanup_state = "LIVE"
        value._closed = False
        value._connection = connection
        value._database_identity = _leaf_identity(
            os.stat("store.duckdb", dir_fd=workspace_fd, follow_symlinks=False)
        )
        value._forced_spill_names = []
        value._limits = limits
        value._marker_identity = marker_identity
        value._marker_payload = marker_payload
        value._owner = owner
        value._spill_fd = spill_fd
        value._spill_identity = _directory_identity(os.fstat(spill_fd))
        value._workspace_fd = workspace_fd
        value._workspace_identity = _directory_identity(os.fstat(workspace_fd))
        value._workspace_name = workspace_name
        _require_external_order_workspace(value)
        return value
    except BaseException as exc:
        if connection is not None:
            with suppress(BaseException):
                connection.close()
        for descriptor in (marker_fd, spill_fd, workspace_fd):
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
        raise _stage_contract_error("open_external_order_store_failed") from exc


def _configure_external_order_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    temp_directory: str,
) -> None:
    connection.execute("SET threads = 1")
    connection.execute("SET memory_limit = '1GiB'")
    connection.execute("SET preserve_insertion_order = false")
    connection.execute("SET temp_directory = ?", [temp_directory])
    connection.execute("SET enable_external_access = false")
    connection.execute("SET allow_unsigned_extensions = false")
    connection.execute("SET autoinstall_known_extensions = false")
    connection.execute("SET autoload_known_extensions = false")


def _configure_external_order_test_limits(
    connection: duckdb.DuckDBPyConnection,
    *,
    memory_limit_bytes: int,
) -> None:
    connection.execute(f"SET memory_limit = '{memory_limit_bytes}B'")
    connection.execute("SET debug_force_external = true")


def _read_external_spill_row(stream: BinaryIO) -> tuple[str, str] | None:
    line = stream.readline()
    if line == b"":
        return None
    payload = json.loads(line.decode("utf-8"))
    if (
        type(payload) is not list
        or len(payload) != 2
        or type(payload[0]) is not str
        or type(payload[1]) is not str
    ):
        raise ValueError("external order spill row is invalid")
    return payload[0], payload[1]


def _descriptor_path(descriptor: int) -> str:
    if not hasattr(fcntl, "F_GETPATH"):
        raise OSError("descriptor path lookup is unavailable")
    value = fcntl.fcntl(descriptor, fcntl.F_GETPATH, b"\0" * 1024)
    raw = bytes(value).split(b"\0", 1)[0]
    return os.fsdecode(raw)


def _external_order_table(relation: ExternalOrderRelation) -> str:
    if type(relation) is not ExternalOrderRelation:
        raise _stage_contract_error("unknown_external_order_relation")
    if relation is ExternalOrderRelation.BRONZE_SOURCE_ROW:
        return "order_bronze_source_row"
    raise _stage_contract_error("unknown_external_order_relation")


def _require_external_order_workspace(store: ExternalOrderStore) -> None:
    store._owner.assert_live()
    named = os.stat(
        store._workspace_name,
        dir_fd=store._owner._stage_fd,
        follow_symlinks=False,
    )
    if (
        _directory_identity(named) != store._workspace_identity
        or _directory_identity(os.fstat(store._workspace_fd)) != store._workspace_identity
        or _directory_identity(os.stat("spill", dir_fd=store._workspace_fd, follow_symlinks=False))
        != store._spill_identity
        or _directory_identity(os.fstat(store._spill_fd)) != store._spill_identity
        or _leaf_identity(
            os.stat(
                "store.duckdb",
                dir_fd=store._workspace_fd,
                follow_symlinks=False,
            )
        )
        != store._database_identity
    ):
        raise ValueError("external order workspace changed")
    with os.scandir(store._workspace_fd) as entries:
        names = {entry.name for entry in entries}
    if not {".marker", "spill", "store.duckdb"}.issubset(names) or not names.issubset(
        {".marker", "spill", "store.duckdb", "store.duckdb.wal"}
    ):
        raise ValueError("external order workspace inventory changed")
    if "store.duckdb.wal" in names:
        _leaf_identity(
            os.stat(
                "store.duckdb.wal",
                dir_fd=store._workspace_fd,
                follow_symlinks=False,
            )
        )
    marker = os.open(
        ".marker",
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=store._workspace_fd,
    )
    try:
        if (
            _leaf_identity(os.fstat(marker)) != store._marker_identity
            or _read_bounded_descriptor(marker) != store._marker_payload
        ):
            raise ValueError("external order marker changed")
    finally:
        os.close(marker)


class _ParquetLeafIssuance:
    __slots__ = ("leaf", "owner")

    def __init__(self, owner: ArtifactBuildSession) -> None:
        self.owner = owner
        self.leaf: _OwnedParquetLeaf | None = None


class _OwnedParquetLeaf:
    __slots__ = (
        "_created",
        "_identity",
        "_issuance",
        "_owner",
        "_parent_mutation",
        "_spec",
    )

    def __new__(cls) -> "_OwnedParquetLeaf":
        raise TypeError("staged Parquet leaves are owner-issued")

    @classmethod
    def _issue(
        cls,
        owner: ArtifactBuildSession,
        spec: TableSpec,
    ) -> "_OwnedParquetLeaf":
        value = object.__new__(cls)
        issuance = _ParquetLeafIssuance(owner)
        value._owner = owner
        value._spec = spec
        value._issuance = issuance
        issuance.leaf = value
        value._created = False
        value._identity: tuple[int, int, int, int, int] | None = None
        value._parent_mutation: tuple[int, int] | None = None
        return value

    @property
    def table_name(self) -> str:
        self._require_owner()
        return cast(str, self._spec.table_name)

    @property
    def relative_path(self) -> PurePosixPath:
        self._require_owner()
        return PurePosixPath(self._spec.parquet_path)

    @contextmanager
    def create_exclusive(self) -> Iterator[BinaryIO]:
        self._require_owner()
        if self._created:
            raise _stage_contract_error("parquet_leaf_already_created")
        leaf_name = PurePosixPath(self._spec.parquet_path).name
        descriptor = -1
        try:
            descriptor = os.open(
                leaf_name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=self._owner._parquet_fd,
            )
            os.fchmod(descriptor, 0o600)
            self._identity = _leaf_identity(os.fstat(descriptor))
            self._created = True
            self._owner._registered_parquet_names.add(leaf_name)
            _refresh_owned_parquet_mutations(self._owner)
            with os.fdopen(descriptor, "w+b", closefd=True) as stream:
                descriptor = -1
                yield cast(BinaryIO, stream)
                stream.flush()
                os.fsync(stream.fileno())
            self.assert_unchanged()
        except ArtifactContractError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("create_parquet_leaf_failed") from exc
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)

    @contextmanager
    def open_verified(self) -> Iterator[BinaryIO]:
        self.assert_unchanged()
        descriptor = -1
        try:
            descriptor = os.open(
                self.relative_path.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=self._owner._parquet_fd,
            )
            if _leaf_identity(os.fstat(descriptor)) != self._identity:
                raise ValueError("Parquet leaf changed while opening")
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                yield cast(BinaryIO, stream)
            self.assert_unchanged()
        except ArtifactContractError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("open_parquet_leaf_failed") from exc
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)

    def create_verification_workspace(
        self,
    ) -> AbstractContextManager[OwnedParquetVerificationWorkspace]:
        self._require_owner()
        from finproof.data.artifacts.parquet_io import (
            _final_verification_workspace,
            _TrustedWorkspaceParent,
        )

        trusted_parent = _TrustedWorkspaceParent._from_open_descriptor(self._owner._stage_fd)
        return _final_verification_workspace(trusted_parent=trusted_parent)

    def assert_unchanged(self) -> None:
        self._require_owner()
        if not self._created or self._identity is None:
            raise _stage_contract_error("parquet_leaf_not_created")
        try:
            named = os.stat(
                self.relative_path.name,
                dir_fd=self._owner._parquet_fd,
                follow_symlinks=False,
            )
            if _leaf_identity(named) != self._identity:
                raise ValueError("Parquet leaf generation changed")
            if _directory_mutation(os.fstat(self._owner._parquet_fd)) != self._parent_mutation:
                raise ValueError("Parquet leaf parent generation changed")
        except (OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("parquet_leaf_generation_changed") from exc

    def unlink_if_exact_writer_owned(self) -> None:
        self.assert_unchanged()
        leaf_name = PurePosixPath(self._spec.parquet_path).name
        try:
            os.unlink(leaf_name, dir_fd=self._owner._parquet_fd)
            self._owner._registered_parquet_names.remove(leaf_name)
            self._created = False
            self._identity = None
            self._parent_mutation = None
            _refresh_owned_parquet_mutations(self._owner)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise _stage_contract_error("unlink_parquet_leaf_failed") from exc

    def _require_owner(self) -> None:
        self._owner.require_owned_parquet_leaf(self)

    def __copy__(self) -> "_OwnedParquetLeaf":
        raise TypeError("OwnedStageParquetLeaf cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "_OwnedParquetLeaf":
        del memo
        raise TypeError("OwnedStageParquetLeaf cannot be copied")

    def __reduce__(self) -> str | tuple[Any, ...]:
        raise TypeError("OwnedStageParquetLeaf cannot be copied")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("OwnedStageParquetLeaf cannot be subclassed")


class TransferredCandidateCustody:
    """Opaque ownership moved into the future expected-accepted receiver."""

    def __new__(cls) -> "TransferredCandidateCustody":
        raise TypeError("TransferredCandidateCustody is transfer-owned")


class ExpectedAcceptedCustodyReceiver(Protocol):
    """Narrow non-fallible receiver slot for the CP8 ownership move."""

    def accept_transferred_custody(
        self,
        custody: TransferredCandidateCustody,
    ) -> None: ...


def _initialize_session(
    settings: Settings,
    versions: VersionBundle,
    options: ArtifactBuildOptions,
    input_identity: BuildInputIdentity,
) -> ArtifactBuildSession:
    parent_fd = -1
    lock_fd = -1
    stage_fd = -1
    parquet_fd = -1
    marker_created = False
    stage_created = False
    operation_id = secrets.token_hex(16)
    target_basename = settings.artifact_dir.name
    lock_name = f".{target_basename}.finproof-build.lock"
    stage_name = f".{target_basename}.finproof-stage-{operation_id}"
    marker_name = f"{stage_name}.marker"
    try:
        if (
            type(settings) is not Settings
            or type(versions) is not VersionBundle
            or type(options) is not ArtifactBuildOptions
            or type(input_identity) is not BuildInputIdentity
            or settings.artifact_dir.parent != settings.repository_root
            or settings.artifact_dir.exists()
        ):
            raise ValueError("invalid session initialization contract")
        input_identity.assert_unchanged()
        directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
        parent_fd = os.open(settings.repository_root, directory_flags)
        lock_fd = os.open(
            lock_name,
            os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        os.fchmod(lock_fd, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.LOCK_HELD,
                operation_id=operation_id,
                target_basename=target_basename,
                internal_context={"reason": "build_lock_held"},
            ) from exc
        _reject_ambiguous_orphan_stage(parent_fd, target_basename, operation_id)
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        stage_created = True
        stage_fd = os.open(stage_name, directory_flags, dir_fd=parent_fd)
        os.mkdir("parquet", 0o700, dir_fd=stage_fd)
        parquet_fd = os.open("parquet", directory_flags, dir_fd=stage_fd)
        marker_payload = json.dumps(
            {
                "artifact_contract_version": "1.0.0",
                "artifact_set_id": "finproof-data-artifacts/v1",
                "operation_id": operation_id,
                "target_basename": target_basename,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        marker_fd = os.open(
            marker_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        marker_created = True
        try:
            os.fchmod(marker_fd, 0o600)
            os.write(marker_fd, marker_payload)
            os.fsync(marker_fd)
            marker_identity = _leaf_identity(os.fstat(marker_fd))
        finally:
            os.close(marker_fd)
        value = object.__new__(ArtifactBuildSession)
        value._closed = False
        value._input_identity = input_identity
        value._settings = settings
        value._lock_fd = lock_fd
        value._marker_identity = marker_identity
        value._marker_name = marker_name
        value._marker_payload = marker_payload
        value._operation_id = operation_id
        value._parent_fd = parent_fd
        value._parquet_fd = parquet_fd
        value._stage_fd = stage_fd
        value._stage_identity = _directory_identity(os.fstat(stage_fd))
        value._stage_name = stage_name
        value._state = "LIVE"
        value._target_basename = target_basename
        value._timestamp = options.persistence_timestamp
        value._registered_parquet_names = set()
        value._registered_stage_names = {"parquet"}
        value._claimed_specs = set()
        value._leaf_objects = {}
        value._staged_pairs = {}
        value._staged_sets = {}
        value._database_claimed = False
        value._database_leaf = None
        value._sealed_database = None
        value._sealed_issuance = None
        value._sealed_leaf_token = None
        value._sealed_owner_token = None
        _require_session_generation(value)
        return value
    except BaseException:
        for descriptor in (parquet_fd, stage_fd):
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
        if stage_created and parent_fd >= 0:
            with suppress(OSError):
                os.rmdir(f"{stage_name}/parquet", dir_fd=parent_fd)
            with suppress(OSError):
                os.rmdir(stage_name, dir_fd=parent_fd)
        if marker_created and parent_fd >= 0:
            with suppress(OSError):
                os.unlink(marker_name, dir_fd=parent_fd)
        if lock_fd >= 0:
            with suppress(OSError):
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            with suppress(OSError):
                os.close(lock_fd)
        if parent_fd >= 0:
            with suppress(OSError):
                os.close(parent_fd)
        raise


def _require_session_generation(
    session: ArtifactBuildSession | OwnedCandidateStage | CandidateStageCustody,
) -> None:
    stage_named = os.stat(
        session._stage_name,
        dir_fd=session._parent_fd,
        follow_symlinks=False,
    )
    marker_named = os.stat(
        session._marker_name,
        dir_fd=session._parent_fd,
        follow_symlinks=False,
    )
    if (
        _directory_identity(os.fstat(session._stage_fd)) != session._stage_identity
        or _directory_identity(stage_named) != session._stage_identity
        or _leaf_identity(marker_named) != session._marker_identity
    ):
        raise ValueError("staging generation changed")
    marker_fd = os.open(
        session._marker_name,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=session._parent_fd,
    )
    try:
        if _leaf_identity(os.fstat(marker_fd)) != session._marker_identity:
            raise ValueError("staging marker descriptor changed")
        marker_payload = _read_bounded_descriptor(marker_fd)
    finally:
        os.close(marker_fd)
    marker_after = os.stat(
        session._marker_name,
        dir_fd=session._parent_fd,
        follow_symlinks=False,
    )
    if (
        _leaf_identity(marker_after) != session._marker_identity
        or marker_payload != session._marker_payload
    ):
        raise ValueError("staging marker bytes changed")
    with os.scandir(session._stage_fd) as entries:
        stage_names = {entry.name for entry in entries}
    with os.scandir(session._parquet_fd) as entries:
        parquet_names = {entry.name for entry in entries}
    if (
        stage_names != session._registered_stage_names
        or parquet_names != session._registered_parquet_names
    ):
        raise ValueError("staging inventory is ambiguous")


def _directory_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    if stat.S_IFMT(value.st_mode) != stat.S_IFDIR:
        raise ValueError("staging entry is not a directory")
    return value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode), stat.S_IMODE(value.st_mode)


def _leaf_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    if stat.S_IFMT(value.st_mode) != stat.S_IFREG or value.st_nlink != 1:
        raise ValueError("staging marker is not a single-link regular file")
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        stat.S_IMODE(value.st_mode),
        value.st_nlink,
    )


def _read_bounded_descriptor(descriptor: int, limit: int = 16 * 1024) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    payload = os.read(descriptor, limit + 1)
    if len(payload) > limit:
        raise ValueError("staging marker exceeds its bound")
    return payload


def _directory_mutation(value: os.stat_result) -> tuple[int, int]:
    if stat.S_IFMT(value.st_mode) != stat.S_IFDIR:
        raise ValueError("Parquet parent is not a directory")
    return value.st_mtime_ns, value.st_ctime_ns


def _refresh_owned_parquet_mutations(owner: ArtifactBuildSession) -> None:
    mutation = _directory_mutation(os.fstat(owner._parquet_fd))
    for leaf in owner._leaf_objects.values():
        if leaf._created:
            leaf._parent_mutation = mutation


def _refresh_owned_database_mutation(owner: ArtifactBuildSession) -> None:
    leaf = owner._database_leaf
    if leaf is not None and leaf._created:
        leaf._parent_mutation = _directory_mutation(os.fstat(owner._stage_fd))


def _staging_error(reason: str) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.STAGING_CLEANUP_FAILED,
        operation_id="build-session",
        internal_context={"reason": reason},
    )


def _stage_contract_error(reason: str) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.SERIALIZATION_FAILED,
        operation_id="stage-artifact",
        internal_context={"reason": reason},
    )


def _reject_ambiguous_orphan_stage(
    parent_fd: int,
    target_basename: str,
    operation_id: str,
) -> None:
    prefix = f".{target_basename}.finproof-stage-"
    with os.scandir(parent_fd) as entries:
        if any(entry.name.startswith(prefix) for entry in entries):
            raise ArtifactContractError(
                ArtifactErrorCode.UNRECOGNIZED_ORPHAN_STAGE,
                operation_id=operation_id,
                target_basename=target_basename,
                internal_context={"reason": "ambiguous_orphan_stage"},
            )
