"""Capability-bound Parquet writing and verification."""

import hashlib
import os
import secrets
import stat
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

import duckdb
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.expected_contract import ExpectedLogicalTable
from finproof.data.artifacts.hashing import (
    canonical_json_bytes,
    schema_sha256,
    table_logical_hash,
)
from finproof.data.artifacts.manifest import (
    ArtifactManifest,
    ArtifactTable,
    TableVerificationResult,
    VerifiedPhysicalEntry,
    VerifiedPhysicalInventory,
)
from finproof.data.artifacts.serialization import logical_table_row, validate_physical_row
from finproof.data.artifacts.table_specs import (
    TABLE_SPECS,
    TableSpec,
    require_registered_table_spec,
)


class ManagedUniqueKeyIndex(Protocol):
    """Closed bounded unique-key index capability."""

    def insert_canonical_batch(self, keys: tuple[bytes, ...]) -> None: ...

    def assert_unique(self) -> None: ...


class OwnedParquetVerificationWorkspace(Protocol):
    """Owner-issued uniqueness workspace capability."""

    def create_unique_key_index(
        self, *, limits: "ParquetVerificationLimits"
    ) -> AbstractContextManager[ManagedUniqueKeyIndex]: ...

    def assert_unchanged(self) -> None: ...


class OwnedStageParquetLeaf(Protocol):
    """Owner-issued exact staged Parquet leaf capability."""

    @property
    def table_name(self) -> str: ...

    @property
    def relative_path(self) -> PurePosixPath: ...

    def create_exclusive(self) -> AbstractContextManager[BinaryIO]: ...

    def open_verified(self) -> AbstractContextManager[BinaryIO]: ...

    def create_verification_workspace(
        self,
    ) -> AbstractContextManager[OwnedParquetVerificationWorkspace]: ...

    def assert_unchanged(self) -> None: ...

    def unlink_if_exact_writer_owned(self) -> None: ...


class OwnedStageArtifactOwner(Protocol):
    """Owner of a live staged artifact tree."""

    @property
    def persistence_timestamp(self) -> datetime: ...

    def assert_live(self) -> None: ...

    def require_owned_parquet_leaf(self, leaf: OwnedStageParquetLeaf) -> None: ...

    def _register_staged_verification(self, value: object, handle: object) -> object: ...

    def _require_registered_staged_verification(
        self, value: object, handle: object, token: object
    ) -> None: ...

    def _require_registered_staged_handle(self, handle: object, token: object) -> None: ...

    def _register_staged_set(self, value: object) -> object: ...

    def _replace_registered_staged_set(self, previous: object, value: object) -> object: ...

    def _require_registered_staged_set(self, value: object, token: object) -> None: ...


class ParquetVerificationLimits:
    """Internal positive bounded-reader limits."""

    def __init__(self, *, batch_rows: int = 65_536, memory_limit_bytes: int = 1 << 30) -> None:
        if type(batch_rows) is not int or not 1 <= batch_rows <= 65_536:
            raise ValueError("batch_rows must be in 1..65536")
        if type(memory_limit_bytes) is not int or memory_limit_bytes <= 0:
            raise ValueError("memory_limit_bytes must be positive")
        self.batch_rows = batch_rows
        self.memory_limit_bytes = memory_limit_bytes


_FOCUSED_TEST_LIMITS: ParquetVerificationLimits | None = None


def _require_spec_fingerprint(spec: TableSpec) -> None:
    require_registered_table_spec(spec)


def _registered_spec_guard(spec: TableSpec) -> Callable[[], None]:
    def guard() -> None:
        _require_spec_fingerprint(spec)

    return guard


class ParquetBatchWriter:
    """Incremental single-table writer skeleton."""

    def __init__(self, spec: TableSpec, leaf: OwnedStageParquetLeaf) -> None:
        try:
            require_registered_table_spec(spec)
        except ValueError as exc:
            raise ValueError("writer requires the exact registered table spec") from exc
        if leaf.table_name != spec.table_name or leaf.relative_path != PurePosixPath(
            spec.parquet_path
        ):
            raise ValueError("leaf table/path does not match the registered spec")
        self._spec = spec
        self._leaf = leaf
        self._context = leaf.create_exclusive()
        try:
            self._sink = self._context.__enter__()
        except BaseException as exc:
            raise _serialization_error("enter-parquet-leaf", leaf) from exc
        try:
            self._writer = pq.ParquetWriter(
                self._sink,
                _arrow_schema(spec),
                compression="zstd",
                compression_level=3,
                write_statistics=True,
                data_page_size=1_048_576,
            )
        except BaseException as exc:
            self._closed = True
            try:
                self._context.__exit__(type(exc), exc, exc.__traceback__)
            except BaseException as exit_exc:
                raise _serialization_error("construct-parquet-writer", leaf) from exit_exc
            raise _serialization_error("construct-parquet-writer", leaf) from exc
        self._closed = False

    def write_batch(self, rows: object) -> None:
        if self._closed:
            raise RuntimeError("Parquet writer is already closed")
        require_registered_table_spec(self._spec)
        names = tuple(column.name for column in self._spec.columns)
        snapshot: list[dict[str, object]] = []
        for row in rows:  # type: ignore[attr-defined]
            if len(snapshot) == 65_536:
                raise ValueError("Parquet batch must contain 1..65536 rows")
            if not isinstance(row, Mapping):
                raise ValueError("Parquet row must be a mapping")
            keys = tuple(row)
            if keys != names or any(type(key) is not str for key in keys):
                raise ValueError("Parquet row columns/order must match the registered spec")
            frozen = {key: row[key] for key in keys}
            validate_physical_row(self._spec, frozen)
            snapshot.append(frozen)
        if not snapshot:
            raise ValueError("Parquet batch must contain 1..65536 rows")
        require_registered_table_spec(self._spec)
        try:
            table = pa.Table.from_pylist(snapshot, schema=_arrow_schema(self._spec))
            require_registered_table_spec(self._spec)
            self._writer.write_table(table, row_group_size=65_536)
        except BaseException as exc:
            self._closed = True
            with suppress(BaseException):
                self._writer.close()
            with suppress(BaseException):
                self._context.__exit__(type(exc), exc, exc.__traceback__)
            raise _serialization_error("write-parquet-batch", self._leaf) from exc

    def close(self) -> None:
        if self._closed:
            raise RuntimeError("Parquet writer is already closed")
        require_registered_table_spec(self._spec)
        self._closed = True
        try:
            self._writer.close()
        except BaseException as exc:
            with suppress(BaseException):
                self._context.__exit__(type(exc), exc, exc.__traceback__)
            raise _serialization_error("close-parquet-writer", self._leaf) from exc
        try:
            self._context.__exit__(None, None, None)
        except BaseException as exc:
            raise _serialization_error("exit-parquet-leaf", self._leaf) from exc

    def abort(self) -> None:
        if self._closed:
            raise RuntimeError("Parquet writer is already closed")
        require_registered_table_spec(self._spec)
        self._closed = True
        failure: BaseException | None = None
        try:
            self._writer.close()
        except BaseException as exc:
            failure = exc
        try:
            if failure is None:
                self._context.__exit__(None, None, None)
            else:
                self._context.__exit__(type(failure), failure, failure.__traceback__)
        except BaseException as exc:
            if failure is None:
                failure = exc
        if failure is not None:
            raise _serialization_error("abort-parquet-close-exit", self._leaf) from failure
        try:
            self._leaf.unlink_if_exact_writer_owned()
        except BaseException as exc:
            raise _serialization_error("abort-parquet-unlink", self._leaf) from exc


def _arrow_schema(spec: TableSpec) -> pa.Schema:
    types = {
        "string": pa.string(),
        "int64": pa.int64(),
        "date": pa.date32(),
        "timestamp": pa.timestamp("us"),
        "timestamp_utc": pa.timestamp("us", tz="UTC"),
        "decimal": pa.decimal128(38, 18),
        "bool": pa.bool_(),
    }
    return pa.schema(
        [
            pa.field(column.name, types[column.logical_type], nullable=column.nullable)
            for column in spec.columns
        ]
    )


def _serialization_error(operation_id: str, leaf: OwnedStageParquetLeaf) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.SERIALIZATION_FAILED,
        operation_id=operation_id,
        target_basename=leaf.relative_path.name,
    )


def _physical_digest(stream: BinaryIO) -> tuple[int, str]:
    stream.seek(0)
    digest = hashlib.sha256()
    size_bytes = 0
    while chunk := stream.read(1 << 20):
        size_bytes += len(chunk)
        digest.update(chunk)
    stream.seek(0)
    return size_bytes, digest.hexdigest()


def _stream_identity(stream: BinaryIO) -> tuple[int, int, int, int, int]:
    observed = os.fstat(stream.fileno())
    return (
        observed.st_dev,
        observed.st_ino,
        stat.S_IFMT(observed.st_mode),
        stat.S_IMODE(observed.st_mode),
        observed.st_nlink,
    )


@dataclass(frozen=True, init=False)
class _CheckedParquetFacts:
    """Authority-free facts independently recomputed from one held stream."""

    spec: TableSpec
    row_count: int
    schema_hash: str
    logical_hash: str
    physical_size_bytes: int
    physical_sha256: str
    leaf_identity: tuple[int, int, int, int, int]

    def __init__(self) -> None:
        raise TypeError("checked Parquet facts are issued only by the common checker")

    @classmethod
    def _from_checked(
        cls,
        *,
        spec: TableSpec,
        row_count: int,
        logical_hash: str,
        physical_size_bytes: int,
        physical_sha256: str,
        leaf_identity: tuple[int, int, int, int, int],
    ) -> "_CheckedParquetFacts":
        value = object.__new__(cls)
        object.__setattr__(value, "spec", spec)
        object.__setattr__(value, "row_count", row_count)
        object.__setattr__(value, "schema_hash", schema_sha256(spec))
        object.__setattr__(value, "logical_hash", logical_hash)
        object.__setattr__(value, "physical_size_bytes", physical_size_bytes)
        object.__setattr__(value, "physical_sha256", physical_sha256)
        object.__setattr__(value, "leaf_identity", leaf_identity)
        return value


@dataclass(frozen=True, init=False)
class _FinalVerificationSeal:
    """One-use local authority binding checked facts to one final inventory entry."""

    _authority: "_FinalVerificationAuthority"
    _inventory: VerifiedPhysicalInventory
    _entry: VerifiedPhysicalEntry
    _spec: TableSpec
    _facts: _CheckedParquetFacts

    def __init__(self) -> None:
        raise TypeError("final verification seals are issued only by a local authority")


class _FinalVerificationAuthority:
    """Invocation-local issuer whose exact seals cannot escape by value."""

    def __init__(self, inventory: VerifiedPhysicalInventory) -> None:
        self._inventory = inventory
        self._seals: dict[int, _FinalVerificationSeal] = {}

    def mint(
        self,
        *,
        entry: VerifiedPhysicalEntry,
        spec: TableSpec,
        facts: _CheckedParquetFacts,
    ) -> _FinalVerificationSeal:
        require_registered_table_spec(spec)
        if facts.spec is not spec:
            raise ValueError("checked facts do not bind the exact registered spec")
        value = object.__new__(_FinalVerificationSeal)
        object.__setattr__(value, "_authority", self)
        object.__setattr__(value, "_inventory", self._inventory)
        object.__setattr__(value, "_entry", entry)
        object.__setattr__(value, "_spec", spec)
        object.__setattr__(value, "_facts", facts)
        self._seals[id(value)] = value
        return value

    def validate(
        self,
        seal: _FinalVerificationSeal,
        inventory: VerifiedPhysicalInventory,
    ) -> tuple[VerifiedPhysicalEntry, TableSpec, _CheckedParquetFacts]:
        registered = self._seals.get(id(seal))
        if (
            type(seal) is not _FinalVerificationSeal
            or registered is not seal
            or seal._authority is not self
            or seal._inventory is not inventory
        ):
            raise ValueError("invalid final verification seal")
        require_registered_table_spec(seal._spec)
        if seal._facts.spec is not seal._spec:
            raise ValueError("final verification seal facts changed")
        return seal._entry, seal._spec, seal._facts

    def consume(
        self,
        seal: _FinalVerificationSeal,
        inventory: VerifiedPhysicalInventory,
    ) -> tuple[VerifiedPhysicalEntry, TableSpec, _CheckedParquetFacts]:
        result = self.validate(seal, inventory)
        del self._seals[id(seal)]
        return result


def _validate_final_verification_seal(
    seal: object, inventory: VerifiedPhysicalInventory
) -> tuple[VerifiedPhysicalEntry, TableSpec, _CheckedParquetFacts]:
    if type(seal) is not _FinalVerificationSeal:
        raise ValueError("invalid final verification seal")
    return seal._authority.validate(seal, inventory)


def _consume_final_verification_seal(
    seal: object, inventory: VerifiedPhysicalInventory
) -> tuple[VerifiedPhysicalEntry, TableSpec, _CheckedParquetFacts]:
    if type(seal) is not _FinalVerificationSeal:
        raise ValueError("invalid final verification seal")
    return seal._authority.consume(seal, inventory)


@dataclass(frozen=True, init=False)
class StagedParquetHandle:
    """Owner-bound reopened staged Parquet handle."""

    _owner: OwnedStageArtifactOwner
    _leaf: OwnedStageParquetLeaf
    _spec: TableSpec
    _relative_path: PurePosixPath
    _leaf_identity: tuple[int, int, int, int, int]
    _owner_registration_token: object
    table_name: str
    row_count: int
    schema_sha256: str
    logical_hash: str
    physical_size_bytes: int
    physical_sha256: str

    def __init__(self) -> None:
        raise TypeError("StagedParquetHandle is issued only by verification")

    def require_registered(self) -> None:
        """Require this exact live owner-issued handle and leaf."""
        require_registered_table_spec(self._spec)
        self._owner.assert_live()
        self._owner.require_owned_parquet_leaf(self._leaf)
        self._owner._require_registered_staged_handle(self, self._owner_registration_token)

    def _assert_physical_identity(self) -> None:
        self.require_registered()
        with self._leaf.open_verified() as stream:
            if _stream_identity(stream) != self._leaf_identity or _physical_digest(stream) != (
                self.physical_size_bytes,
                self.physical_sha256,
            ):
                raise ValueError("staged Parquet physical identity changed")
        self._leaf.assert_unchanged()

    @contextmanager
    def iter_batches(self, *, batch_size: int = 65_536) -> Iterator[Iterator[pa.RecordBatch]]:
        if type(batch_size) is not int or not 1 <= batch_size <= 65_536:
            raise ValueError("batch_size must be in 1..65536")
        self.require_registered()
        try:
            with self._leaf.open_verified() as stream:
                if _stream_identity(stream) != self._leaf_identity or _physical_digest(stream) != (
                    self.physical_size_bytes,
                    self.physical_sha256,
                ):
                    raise ValueError("staged Parquet physical identity changed")
                require_registered_table_spec(self._spec)
                parquet = pq.ParquetFile(stream)
                try:
                    yield parquet.iter_batches(batch_size=batch_size, use_threads=False)
                finally:
                    if _stream_identity(stream) != self._leaf_identity or _physical_digest(
                        stream
                    ) != (self.physical_size_bytes, self.physical_sha256):
                        raise ValueError("staged Parquet changed during iteration")
                    require_registered_table_spec(self._spec)
        finally:
            self._owner.require_owned_parquet_leaf(self._leaf)


@dataclass(frozen=True, init=False)
class StagedParquetVerification:
    """Physical and logical facts from one staged reopen."""

    _owner: OwnedStageArtifactOwner
    _leaf: OwnedStageParquetLeaf
    _spec: TableSpec
    _relative_path: PurePosixPath
    _leaf_identity: tuple[int, int, int, int, int]
    _owner_registration_token: object
    logical: ExpectedLogicalTable
    physical_size_bytes: int
    physical_sha256: str
    handle: StagedParquetHandle

    def __init__(self) -> None:
        raise TypeError("StagedParquetVerification is issued only by verification")

    def require_registered(self) -> None:
        """Require this exact owner-issued verification and handle pair."""
        require_registered_table_spec(self._spec)
        self._owner.assert_live()
        self._owner._require_registered_staged_verification(
            self, self.handle, self._owner_registration_token
        )


@dataclass(frozen=True, init=False)
class StagedParquetSet:
    """Owner-bound frozen staged Parquet collection."""

    _owner: OwnedStageArtifactOwner
    _registration_token: object
    verifications: tuple[StagedParquetVerification, ...]
    handles: tuple[StagedParquetHandle, ...]
    persistence_timestamp: datetime

    def __init__(self) -> None:
        raise TypeError("StagedParquetSet is issued only by its factory")

    @classmethod
    def from_verified(
        cls,
        *,
        owner: OwnedStageArtifactOwner,
        verifications: tuple[StagedParquetVerification, ...],
    ) -> "StagedParquetSet":
        owner.assert_live()
        persistence_timestamp = owner.persistence_timestamp
        offset = (
            persistence_timestamp.utcoffset() if type(persistence_timestamp) is datetime else None
        )
        if (
            type(persistence_timestamp) is not datetime
            or persistence_timestamp.tzinfo is None
            or offset is None
            or offset.total_seconds() != 0
        ):
            raise ValueError("staged persistence timestamp must be exact aware UTC")
        if type(verifications) is not tuple or not verifications:
            raise ValueError("staged verification tuple must be nonempty")
        for verification in verifications:
            if (
                type(verification) is not StagedParquetVerification
                or verification._owner is not owner
            ):
                raise ValueError("staged verifications require one exact owner")
            verification.require_registered()
        _require_staged_table_order(verifications)
        value = cls._construct(
            owner=owner,
            verifications=verifications,
            persistence_timestamp=persistence_timestamp,
        )
        token = owner._register_staged_set(value)
        object.__setattr__(value, "_registration_token", token)
        return value

    @classmethod
    def _construct(
        cls,
        *,
        owner: OwnedStageArtifactOwner,
        verifications: tuple[StagedParquetVerification, ...],
        persistence_timestamp: datetime,
    ) -> "StagedParquetSet":
        value = object.__new__(cls)
        object.__setattr__(value, "_owner", owner)
        object.__setattr__(value, "verifications", verifications)
        object.__setattr__(value, "handles", tuple(item.handle for item in verifications))
        object.__setattr__(value, "persistence_timestamp", persistence_timestamp)
        return value

    def extend_verified(
        self,
        *,
        owner: OwnedStageArtifactOwner,
        verifications: tuple[StagedParquetVerification, ...],
    ) -> "StagedParquetSet":
        """Return the next exact verified prefix."""
        self._validate_contents()
        if owner is not self._owner:
            raise ValueError("staged verification owner mismatch")
        if type(verifications) is not tuple or not verifications:
            raise ValueError("staged verification tuple must be nonempty")
        for verification in verifications:
            if (
                type(verification) is not StagedParquetVerification
                or verification._owner is not owner
            ):
                raise ValueError("staged verifications require one exact owner")
            verification.require_registered()
        combined = (*self.verifications, *verifications)
        _require_staged_table_order(combined)
        value = self._construct(
            owner=owner,
            verifications=combined,
            persistence_timestamp=self.persistence_timestamp,
        )
        token = owner._replace_registered_staged_set(self, value)
        object.__setattr__(value, "_registration_token", token)
        return value

    def require_complete(self) -> None:
        """Require the exact complete registered table set."""
        self._validate_contents()
        if len(self.verifications) != len(TABLE_SPECS):
            raise ValueError("staged Parquet set is not complete")

    def _validate_contents(self) -> None:
        self._owner.assert_live()
        self._owner._require_registered_staged_set(self, self._registration_token)
        owner_timestamp = self._owner.persistence_timestamp
        for timestamp in (owner_timestamp, self.persistence_timestamp):
            offset = timestamp.utcoffset() if type(timestamp) is datetime else None
            if (
                type(timestamp) is not datetime
                or timestamp.tzinfo is None
                or offset is None
                or offset.total_seconds() != 0
            ):
                raise ValueError("staged persistence timestamp must be exact aware UTC")
        if self.persistence_timestamp != owner_timestamp:
            raise ValueError("staged persistence timestamp changed")
        if type(self.verifications) is not tuple or type(self.handles) is not tuple:
            raise ValueError("staged set members must remain frozen tuples")
        if len(self.verifications) != len(self.handles):
            raise ValueError("staged verification/handle identity changed")
        for verification, handle in zip(self.verifications, self.handles, strict=True):
            if (
                verification.handle is not handle
                or verification._owner is not self._owner
                or handle._owner is not self._owner
            ):
                raise ValueError("staged verification/handle owner identity changed")
            verification.require_registered()
            handle.require_registered()
        _require_staged_table_order(self.verifications)

    def verification_for(self, table_name: str) -> StagedParquetVerification:
        self._validate_contents()
        for verification in self.verifications:
            if verification.logical.name == table_name:
                verification.handle._assert_physical_identity()
                return verification
        raise KeyError(table_name)

    def require_tables(self, names: tuple[str, ...]) -> None:
        self._validate_contents()
        available = tuple(item.logical.name for item in self.verifications)
        if any(name not in available for name in names):
            raise ValueError("required staged table is absent")

    def require_owned(self, handle: StagedParquetHandle) -> None:
        self._validate_contents()
        if not any(item is handle for item in self.handles):
            raise ValueError("foreign staged handle")

    def assert_live(self) -> None:
        self._validate_contents()

    def table_declarations(self) -> tuple[ArtifactTable, ...]:
        self._validate_contents()
        declarations: list[ArtifactTable] = []
        for verification, handle in zip(self.verifications, self.handles, strict=True):
            handle._assert_physical_identity()
            spec = next(
                item for item in TABLE_SPECS if item.table_name == verification.logical.name
            )
            declarations.append(
                ArtifactTable(
                    table_name=spec.table_name,
                    layer=spec.layer,
                    grain=spec.grain,
                    parquet_path=spec.parquet_path,
                    row_count=verification.logical.row_count,
                    schema_sha256=verification.logical.schema_hash,
                    sort_key=spec.sort_key,
                    unique_key=spec.unique_key,
                    logical_hash=verification.logical.logical_hash,
                )
            )
        return tuple(declarations)


def _require_staged_table_order(
    verifications: tuple[StagedParquetVerification, ...],
) -> None:
    expected = tuple(spec.table_name for spec in TABLE_SPECS[: len(verifications)])
    observed = tuple(item.logical.name for item in verifications)
    if observed != expected:
        raise ValueError("staged Parquet table order mismatch")


def _check_opened_parquet(
    *,
    spec: TableSpec,
    stream: BinaryIO,
    workspace: OwnedParquetVerificationWorkspace,
    limits: ParquetVerificationLimits,
    spec_guard: Callable[[], None] = lambda: None,
) -> _CheckedParquetFacts:
    spec_guard()
    before_identity = _stream_identity(stream)
    before_physical = _physical_digest(stream)
    parquet = pq.ParquetFile(stream)
    if not parquet.schema_arrow.equals(_arrow_schema(spec), check_metadata=True):
        raise ValueError("Parquet schema does not match table spec")
    if any(
        parquet.metadata.row_group(index).num_rows > 65_536
        for index in range(parquet.metadata.num_row_groups)
    ):
        raise ValueError("Parquet row group exceeds the frozen limit")
    row_count = parquet.metadata.num_rows
    observed_count = 0
    previous_sort: tuple[object, ...] | None = None
    workspace.assert_unchanged()

    with workspace.create_unique_key_index(limits=limits) as unique_index:

        def logical_rows() -> Iterator[dict[str, object]]:
            nonlocal observed_count, previous_sort
            for batch in parquet.iter_batches(batch_size=limits.batch_rows, use_threads=False):
                spec_guard()
                keys: list[bytes] = []
                for row in batch.to_pylist():
                    validate_physical_row(spec, row)
                    sort_key = tuple(row[name] for name in spec.sort_key)
                    if previous_sort is not None and sort_key < previous_sort:
                        raise ValueError("Parquet sort order mismatch")
                    previous_sort = sort_key
                    unique_key = tuple(row[name] for name in spec.unique_key)
                    keys.append(canonical_json_bytes(unique_key, terminal_newline=False))
                    observed_count += 1
                    yield dict(logical_table_row(spec, row))
                unique_index.insert_canonical_batch(tuple(keys))

        logical_hash = table_logical_hash(spec, row_count=row_count, rows=logical_rows())
        spec_guard()
        if observed_count != row_count:
            raise ValueError("physical row count differs from Parquet metadata")
        unique_index.assert_unique()
    workspace.assert_unchanged()
    after_physical = _physical_digest(stream)
    after_identity = _stream_identity(stream)
    spec_guard()
    if after_physical != before_physical or after_identity != before_identity:
        raise ValueError("Parquet physical identity changed during verification")
    return _CheckedParquetFacts._from_checked(
        spec=spec,
        row_count=row_count,
        logical_hash=logical_hash,
        physical_size_bytes=after_physical[0],
        physical_sha256=after_physical[1],
        leaf_identity=after_identity,
    )


def verify_staged_parquet_table(
    *, owner: OwnedStageArtifactOwner, leaf: OwnedStageParquetLeaf, spec: TableSpec
) -> StagedParquetVerification:
    """Reopen one owner-held staged Parquet leaf."""
    owner.assert_live()
    require_registered_table_spec(spec)
    owner.require_owned_parquet_leaf(leaf)
    if leaf.table_name != spec.table_name or leaf.relative_path != PurePosixPath(spec.parquet_path):
        raise ValueError("stage leaf does not match table spec")
    with (
        leaf.create_verification_workspace() as workspace,
        leaf.open_verified() as stream,
    ):
        limits = _FOCUSED_TEST_LIMITS or ParquetVerificationLimits()
        before = _physical_digest(stream)
        facts = _check_opened_parquet(
            spec=spec,
            stream=stream,
            workspace=workspace,
            limits=limits,
            spec_guard=_registered_spec_guard(spec),
        )
        physical_size_bytes, physical_sha256 = _physical_digest(stream)
        require_registered_table_spec(spec)
        if before != (physical_size_bytes, physical_sha256):
            raise ValueError("staged Parquet changed during verification")
    leaf.assert_unchanged()
    require_registered_table_spec(spec)
    logical = ExpectedLogicalTable(
        name=spec.table_name,
        grain=spec.grain,
        schema_hash=schema_sha256(spec),
        row_count=facts.row_count,
        sort_key=spec.sort_key,
        unique_key=spec.unique_key,
        logical_hash=facts.logical_hash,
    )
    handle = object.__new__(StagedParquetHandle)
    object.__setattr__(handle, "_owner", owner)
    object.__setattr__(handle, "_leaf", leaf)
    object.__setattr__(handle, "_spec", spec)
    object.__setattr__(handle, "_relative_path", leaf.relative_path)
    object.__setattr__(handle, "_leaf_identity", facts.leaf_identity)
    object.__setattr__(handle, "table_name", spec.table_name)
    object.__setattr__(handle, "row_count", facts.row_count)
    object.__setattr__(handle, "schema_sha256", logical.schema_hash)
    object.__setattr__(handle, "logical_hash", logical.logical_hash)
    object.__setattr__(handle, "physical_size_bytes", physical_size_bytes)
    object.__setattr__(handle, "physical_sha256", physical_sha256)
    verification = object.__new__(StagedParquetVerification)
    object.__setattr__(verification, "_owner", owner)
    object.__setattr__(verification, "_leaf", leaf)
    object.__setattr__(verification, "_spec", spec)
    object.__setattr__(verification, "_relative_path", leaf.relative_path)
    object.__setattr__(verification, "_leaf_identity", facts.leaf_identity)
    object.__setattr__(verification, "logical", logical)
    object.__setattr__(verification, "physical_size_bytes", physical_size_bytes)
    object.__setattr__(verification, "physical_sha256", physical_sha256)
    object.__setattr__(verification, "handle", handle)
    require_registered_table_spec(spec)
    token = owner._register_staged_verification(verification, handle)
    object.__setattr__(handle, "_owner_registration_token", token)
    object.__setattr__(verification, "_owner_registration_token", token)
    owner._require_registered_staged_verification(verification, handle, token)
    require_registered_table_spec(spec)
    return verification


class _DuckDBUniqueKeyIndex:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection
        try:
            connection.execute("CREATE TABLE artifact_keys(value BLOB NOT NULL)")
        except BaseException as exc:
            raise _workspace_error("unique_index_create_failed") from exc

    def insert_canonical_batch(self, keys: tuple[bytes, ...]) -> None:
        try:
            self._connection.executemany(
                "INSERT INTO artifact_keys(value) VALUES (?)", ((key,) for key in keys)
            )
        except BaseException as exc:
            raise _workspace_error("unique_index_insert_failed") from exc

    def assert_unique(self) -> None:
        try:
            duplicate = self._connection.execute(
                "SELECT 1 FROM artifact_keys GROUP BY value HAVING COUNT(*) > 1 LIMIT 1"
            ).fetchone()
        except BaseException as exc:
            raise _workspace_error("unique_index_query_failed") from exc
        if duplicate is not None:
            raise ArtifactContractError(
                ArtifactErrorCode.UNIQUE_KEY_MISMATCH,
                operation_id="verify-parquet-unique-key",
            )


_DescriptorIdentity = tuple[int, int, int, int, int]


def _descriptor_identity(descriptor: int, *, directory: bool) -> _DescriptorIdentity:
    observed = os.fstat(descriptor)
    if directory:
        if not stat.S_ISDIR(observed.st_mode):
            raise _workspace_error("workspace_entry_identity_invalid")
    elif not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise _workspace_error("workspace_entry_identity_invalid")
    return (
        observed.st_dev,
        observed.st_ino,
        stat.S_IFMT(observed.st_mode),
        stat.S_IMODE(observed.st_mode),
        0 if directory else observed.st_nlink,
    )


def _relative_identity(
    parent_descriptor: int,
    name: str,
    *,
    directory: bool,
    expected_mode: int,
) -> _DescriptorIdentity:
    observed = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    identity = (
        observed.st_dev,
        observed.st_ino,
        stat.S_IFMT(observed.st_mode),
        stat.S_IMODE(observed.st_mode),
        0 if directory else observed.st_nlink,
    )
    valid_type = stat.S_ISDIR(observed.st_mode) if directory else stat.S_ISREG(observed.st_mode)
    if (
        not valid_type
        or stat.S_IMODE(observed.st_mode) != expected_mode
        or (not directory and observed.st_nlink != 1)
    ):
        raise _workspace_error("workspace_entry_identity_invalid")
    return identity


def _open_relative_directory(parent_descriptor: int, name: str) -> int:
    return os.open(
        name,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_descriptor,
    )


@dataclass(frozen=True, init=False)
class _TrustedWorkspaceParent:
    """Single-use held parent directory capability for private workspaces."""

    _descriptor: int
    _identity: _DescriptorIdentity

    @classmethod
    def _from_open_descriptor(cls, descriptor: int) -> "_TrustedWorkspaceParent":
        duplicate = os.dup(descriptor)
        try:
            identity = _descriptor_identity(duplicate, directory=True)
        except BaseException:
            os.close(duplicate)
            raise
        value = object.__new__(cls)
        object.__setattr__(value, "_descriptor", duplicate)
        object.__setattr__(value, "_identity", identity)
        return value

    def _take(self) -> tuple[int, _DescriptorIdentity]:
        descriptor = self._descriptor
        if descriptor < 0 or _descriptor_identity(descriptor, directory=True) != self._identity:
            raise _workspace_error("workspace_parent_changed")
        object.__setattr__(self, "_descriptor", -1)
        return descriptor, self._identity


class _FinalVerificationWorkspace:
    _MARKER_BYTES = b"finproof-parquet-verification-v1\n"
    _MARKER_NAME = ".finproof-parquet-verification"
    _SPILL_NAME = "spill"
    _MARKER_TOMBSTONE = ".finproof-parquet-verification.cleanup"
    _SPILL_TOMBSTONE = ".finproof-parquet-spill.cleanup"

    def __init__(
        self,
        *,
        parent_fd: int,
        parent_identity: _DescriptorIdentity,
        root_name: str,
        root_fd: int,
        root_identity: _DescriptorIdentity,
        marker_identity: _DescriptorIdentity,
        spill_fd: int,
        spill_identity: _DescriptorIdentity,
    ) -> None:
        self._parent_fd = parent_fd
        self._parent_identity = parent_identity
        self._root_name = root_name
        self._root_fd = root_fd
        self._root_identity = root_identity
        self._marker_identity = marker_identity
        self._spill_fd = spill_fd
        self._spill_identity = spill_identity
        self._cleanup_safe = True
        self._marker_sha256 = hashlib.sha256(self._MARKER_BYTES).hexdigest()
        self._spill_entries: tuple[tuple[str, _DescriptorIdentity], ...] | None = None

    @property
    def _root(self) -> Path:
        return Path(f"/dev/fd/{self._root_fd}")

    @property
    def _marker(self) -> Path:
        return self._root / self._MARKER_NAME

    @property
    def _spill(self) -> Path:
        return Path(f"/dev/fd/{self._spill_fd}")

    @contextmanager
    def create_unique_key_index(
        self, *, limits: ParquetVerificationLimits
    ) -> Iterator[ManagedUniqueKeyIndex]:
        if limits.memory_limit_bytes != 1 << 30 or limits.batch_rows != 65_536:
            raise ValueError("final verification requires production limits")
        self.assert_unchanged()
        connection: duckdb.DuckDBPyConnection | None = None
        try:
            connection = duckdb.connect(":memory:")
            connection.execute("SET threads = 1")
            connection.execute("SET memory_limit = '1GiB'")
            connection.execute("SET temp_directory = ?", [f"/dev/fd/{self._spill_fd}"])
            connection.execute("SET enable_external_access = false")
            connection.execute("SET allow_unsigned_extensions = false")
            connection.execute("SET autoinstall_known_extensions = false")
            connection.execute("SET autoload_known_extensions = false")
        except BaseException as exc:
            if connection is not None:
                try:
                    connection.close()
                except BaseException as close_exc:
                    self._cleanup_safe = False
                    raise _workspace_error("connection_close_failed") from close_exc
            raise _workspace_error("workspace_configure_failed") from exc
        try:
            assert connection is not None
            yield _DuckDBUniqueKeyIndex(connection)
        finally:
            try:
                connection.close()
            except BaseException as exc:
                self._cleanup_safe = False
                raise _workspace_error("connection_close_failed") from exc
            self._spill_entries = tuple(
                (
                    name,
                    _relative_identity(self._spill_fd, name, directory=False, expected_mode=0o600),
                )
                for name in sorted(os.listdir(self._spill_fd))
            )

    def assert_unchanged(self) -> None:
        if _descriptor_identity(self._parent_fd, directory=True) != self._parent_identity:
            raise _workspace_error("workspace_parent_changed")
        if _descriptor_identity(self._root_fd, directory=True) != self._root_identity:
            raise _workspace_error("workspace_directory_changed")
        if (
            _relative_identity(
                self._parent_fd, self._root_name, directory=True, expected_mode=0o700
            )
            != self._root_identity
        ):
            raise _workspace_error("workspace_directory_changed")
        if (
            _relative_identity(
                self._root_fd, self._MARKER_NAME, directory=False, expected_mode=0o600
            )
            != self._marker_identity
        ):
            raise _workspace_error("workspace_marker_changed")
        marker_bytes = _read_owned_marker_at(
            self._root_fd, self._MARKER_NAME, self._marker_identity
        )
        if (
            marker_bytes != self._MARKER_BYTES
            or hashlib.sha256(marker_bytes).hexdigest() != self._marker_sha256
        ):
            raise _workspace_error("workspace_marker_content_changed")
        if (
            _descriptor_identity(self._spill_fd, directory=True) != self._spill_identity
            or _relative_identity(
                self._root_fd, self._SPILL_NAME, directory=True, expected_mode=0o700
            )
            != self._spill_identity
        ):
            raise _workspace_error("workspace_spill_changed")
        if set(os.listdir(self._root_fd)) != {self._MARKER_NAME, self._SPILL_NAME}:
            raise _workspace_error("workspace_entries_ambiguous")
        if self._spill_entries is not None:
            if tuple(sorted(os.listdir(self._spill_fd))) != tuple(
                sorted(name for name, _ in self._spill_entries)
            ):
                raise _workspace_error("workspace_spill_entries_ambiguous")
            for name, identity in self._spill_entries:
                if (
                    _relative_identity(self._spill_fd, name, directory=False, expected_mode=0o600)
                    != identity
                ):
                    raise _workspace_error("workspace_spill_entry_changed")

    def cleanup(self) -> None:
        if not self._cleanup_safe:
            raise _workspace_error("workspace_close_ambiguous")
        self.assert_unchanged()
        for index, (name, identity) in enumerate(self._spill_entries or ()):
            tombstone = f".finproof-spill-entry-{index}.cleanup"
            _rename_owned_for_cleanup(
                self._spill_fd,
                name,
                tombstone,
                identity=identity,
                directory=False,
                expected_mode=0o600,
            )
            os.unlink(tombstone, dir_fd=self._spill_fd)
        _rename_owned_for_cleanup(
            self._root_fd,
            self._SPILL_NAME,
            self._SPILL_TOMBSTONE,
            identity=self._spill_identity,
            directory=True,
            expected_mode=0o700,
        )
        os.close(self._spill_fd)
        self._spill_fd = -1
        os.rmdir(self._SPILL_TOMBSTONE, dir_fd=self._root_fd)
        _rename_owned_for_cleanup(
            self._root_fd,
            self._MARKER_NAME,
            self._MARKER_TOMBSTONE,
            identity=self._marker_identity,
            directory=False,
            expected_mode=0o600,
        )
        marker_bytes = _read_owned_marker_at(
            self._root_fd, self._MARKER_TOMBSTONE, self._marker_identity
        )
        if (
            marker_bytes != self._MARKER_BYTES
            or hashlib.sha256(marker_bytes).hexdigest() != self._marker_sha256
        ):
            raise _workspace_error("workspace_marker_content_changed")
        os.unlink(self._MARKER_TOMBSTONE, dir_fd=self._root_fd)
        if _descriptor_identity(self._root_fd, directory=True) != self._root_identity or os.listdir(
            self._root_fd
        ):
            raise _workspace_error("workspace_entries_ambiguous")
        root_tombstone = f"{self._root_name}.cleanup"
        _rename_owned_for_cleanup(
            self._parent_fd,
            self._root_name,
            root_tombstone,
            identity=self._root_identity,
            directory=True,
            expected_mode=0o700,
        )
        os.close(self._root_fd)
        self._root_fd = -1
        os.rmdir(root_tombstone, dir_fd=self._parent_fd)
        os.close(self._parent_fd)
        self._parent_fd = -1

    def _release_descriptors(self) -> None:
        for attribute in ("_spill_fd", "_root_fd", "_parent_fd"):
            descriptor = getattr(self, attribute)
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
                setattr(self, attribute, -1)


def _rename_owned_for_cleanup(
    parent_descriptor: int,
    source_name: str,
    tombstone_name: str,
    *,
    identity: _DescriptorIdentity,
    directory: bool,
    expected_mode: int,
) -> None:
    try:
        os.stat(tombstone_name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise _workspace_error("workspace_cleanup_tombstone_exists")
    os.rename(
        source_name,
        tombstone_name,
        src_dir_fd=parent_descriptor,
        dst_dir_fd=parent_descriptor,
    )
    if (
        _relative_identity(
            parent_descriptor,
            tombstone_name,
            directory=directory,
            expected_mode=expected_mode,
        )
        != identity
    ):
        raise _workspace_error("workspace_cleanup_identity_changed")


def _read_owned_marker_at(
    parent_descriptor: int, name: str, identity: _DescriptorIdentity
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        raise _workspace_error("workspace_marker_unavailable") from exc
    try:
        before = os.fstat(descriptor)
        observed = (
            before.st_dev,
            before.st_ino,
            stat.S_IFMT(before.st_mode),
            stat.S_IMODE(before.st_mode),
            before.st_nlink,
        )
        if observed != identity:
            raise _workspace_error("workspace_marker_changed")
        payload = os.read(descriptor, 4096)
        if os.read(descriptor, 1):
            raise _workspace_error("workspace_marker_content_changed")
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            stat.S_IFMT(after.st_mode),
            stat.S_IMODE(after.st_mode),
            after.st_nlink,
        ) != identity:
            raise _workspace_error("workspace_marker_changed")
        return payload
    finally:
        os.close(descriptor)


def _workspace_error(reason: str) -> ArtifactContractError:
    database_operations = {
        "workspace_configure_failed": "parquet-workspace-configure",
        "unique_index_create_failed": "parquet-unique-index-create",
        "unique_index_insert_failed": "parquet-unique-index-insert",
        "unique_index_query_failed": "parquet-unique-index-query",
        "connection_close_failed": "parquet-unique-index-close",
    }
    if reason in database_operations:
        code = ArtifactErrorCode.DATABASE_VALIDATION_FAILED
        operation_id = database_operations[reason]
    elif reason in {"workspace_cleanup_failed", "workspace_close_ambiguous"}:
        code = ArtifactErrorCode.STAGING_CLEANUP_FAILED
        operation_id = "parquet-workspace-cleanup"
    elif reason == "workspace_create_failed":
        code = ArtifactErrorCode.EXACT_TREE_MISMATCH
        operation_id = "parquet-workspace-create"
    elif reason == "workspace_open_failed":
        code = ArtifactErrorCode.EXACT_TREE_MISMATCH
        operation_id = "parquet-workspace-open"
    else:
        code = ArtifactErrorCode.EXACT_TREE_MISMATCH
        operation_id = "parquet-workspace-revalidate"
    return ArtifactContractError(
        code,
        operation_id=operation_id,
        internal_context={"reason": reason},
    )


@contextmanager
def _final_verification_workspace(
    *, trusted_parent: _TrustedWorkspaceParent | None = None
) -> Iterator[_FinalVerificationWorkspace]:
    if trusted_parent is None:
        parent_descriptor = os.open(
            tempfile.gettempdir(),
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            trusted_parent = _TrustedWorkspaceParent._from_open_descriptor(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    parent_fd, parent_identity = trusted_parent._take()
    root_name: str | None = None
    root_fd = -1
    spill_fd = -1
    setup_failure_reason = "workspace_create_failed"
    try:
        for _ in range(16):
            candidate = f"finproof-parquet-verify-{secrets.token_hex(12)}"
            try:
                os.mkdir(candidate, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                continue
            root_name = candidate
            break
        if root_name is None:
            raise _workspace_error("workspace_name_exhausted")
        setup_failure_reason = "workspace_open_failed"
        root_fd = _open_relative_directory(parent_fd, root_name)
        root_identity = _descriptor_identity(root_fd, directory=True)
        if root_identity != _relative_identity(
            parent_fd, root_name, directory=True, expected_mode=0o700
        ):
            raise _workspace_error("workspace_directory_changed")
        os.mkdir(_FinalVerificationWorkspace._SPILL_NAME, mode=0o700, dir_fd=root_fd)
        spill_fd = _open_relative_directory(root_fd, _FinalVerificationWorkspace._SPILL_NAME)
        spill_identity = _descriptor_identity(spill_fd, directory=True)
        if spill_identity != _relative_identity(
            root_fd,
            _FinalVerificationWorkspace._SPILL_NAME,
            directory=True,
            expected_mode=0o700,
        ):
            raise _workspace_error("workspace_spill_changed")
        marker_descriptor = os.open(
            _FinalVerificationWorkspace._MARKER_NAME,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=root_fd,
        )
        try:
            os.write(marker_descriptor, _FinalVerificationWorkspace._MARKER_BYTES)
            os.fsync(marker_descriptor)
            marker_identity = _descriptor_identity(marker_descriptor, directory=False)
        finally:
            os.close(marker_descriptor)
        workspace = _FinalVerificationWorkspace(
            parent_fd=parent_fd,
            parent_identity=parent_identity,
            root_name=root_name,
            root_fd=root_fd,
            root_identity=root_identity,
            marker_identity=marker_identity,
            spill_fd=spill_fd,
            spill_identity=spill_identity,
        )
        workspace.assert_unchanged()
    except BaseException as exc:
        for descriptor in (spill_fd, root_fd, parent_fd):
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
        if isinstance(exc, ArtifactContractError):
            raise
        raise _workspace_error(setup_failure_reason) from exc
    try:
        yield workspace
    finally:
        if workspace._cleanup_safe:
            try:
                workspace.cleanup()
            except BaseException as exc:
                workspace._cleanup_safe = False
                workspace._release_descriptors()
                if not isinstance(exc, ArtifactContractError):
                    raise _workspace_error("workspace_cleanup_failed") from exc
                raise
        else:
            workspace._release_descriptors()


@dataclass(frozen=True, init=False)
class VerifiedParquetTable:
    """Final-inventory-owned reopened Parquet handle."""

    entry: VerifiedPhysicalEntry
    table_name: str
    row_count: int
    schema_sha256: str
    logical_hash: str

    def __init__(self) -> None:
        raise TypeError("VerifiedParquetTable is issued only by final verification")


class ParquetArtifactTableVerifier:
    """Adapter from a complete final inventory to verified table facts."""

    def verify_tables(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        specs: tuple[TableSpec, ...],
    ) -> TableVerificationResult:
        if (
            type(specs) is not tuple
            or len(specs) != len(TABLE_SPECS)
            or any(
                supplied is not expected
                for supplied, expected in zip(specs, TABLE_SPECS, strict=True)
            )
        ):
            raise ValueError("final verifier requires the exact complete table registry")
        tables: list[ExpectedLogicalTable] = []
        handles: list[VerifiedParquetTable] = []
        authority = _FinalVerificationAuthority(inventory)
        for spec in TABLE_SPECS:
            require_registered_table_spec(spec)
            declared = manifest.tables.get(spec.table_name)
            if declared is None or declared.parquet_path != spec.parquet_path:
                raise ValueError("manifest table declaration is missing or mismatched")
            entry = next(
                (
                    candidate
                    for candidate in inventory.declared_entries
                    if candidate.path == PurePosixPath(spec.parquet_path)
                    and candidate.kind == "parquet"
                ),
                None,
            )
            if entry is None:
                raise ValueError("manifest-owned Parquet entry is missing")
            with (
                inventory.open_verified(entry) as stream,
                _final_verification_workspace() as workspace,
            ):
                facts = _check_opened_parquet(
                    spec=spec,
                    stream=stream,
                    workspace=workspace,
                    limits=ParquetVerificationLimits(),
                    spec_guard=_registered_spec_guard(spec),
                )
            require_registered_table_spec(spec)
            logical = ExpectedLogicalTable(
                name=spec.table_name,
                grain=spec.grain,
                schema_hash=facts.schema_hash,
                row_count=facts.row_count,
                sort_key=spec.sort_key,
                unique_key=spec.unique_key,
                logical_hash=facts.logical_hash,
            )
            if (
                declared.table_name != logical.name
                or declared.grain != logical.grain
                or declared.row_count != logical.row_count
                or declared.schema_sha256 != logical.schema_hash
                or declared.sort_key != logical.sort_key
                or declared.unique_key != logical.unique_key
                or declared.logical_hash != logical.logical_hash
            ):
                raise ValueError("manifest table declaration differs from reopened facts")
            inventory.assert_unchanged()
            require_registered_table_spec(spec)
            seal = authority.mint(entry=entry, spec=spec, facts=facts)
            require_registered_table_spec(spec)
            issued = inventory.issue_verified_table_handle(seal=seal)
            require_registered_table_spec(spec)
            if type(issued) is not VerifiedParquetTable:
                raise ValueError("inventory issued the wrong final handle type")
            handle = issued
            tables.append(logical)
            handles.append(handle)
        inventory.assert_unchanged()
        for spec in TABLE_SPECS:
            require_registered_table_spec(spec)
        return TableVerificationResult.from_verified(
            inventory=inventory,
            tables=tuple(tables),
            handles=tuple(handles),
        )
