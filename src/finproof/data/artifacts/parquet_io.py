"""Capability-bound Parquet writing and verification."""

import hashlib
import os
import stat
import tempfile
from collections.abc import Iterator
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
        self._writer = pq.ParquetWriter(
            self._sink,
            _arrow_schema(spec),
            compression="zstd",
            compression_level=3,
            write_statistics=True,
            data_page_size=1_048_576,
        )
        self._closed = False

    def write_batch(self, rows: object) -> None:
        if self._closed:
            raise RuntimeError("Parquet writer is already closed")
        names = tuple(column.name for column in self._spec.columns)
        snapshot: list[dict[str, object]] = []
        for row in rows:  # type: ignore[attr-defined]
            if len(snapshot) == 65_536:
                raise ValueError("Parquet batch must contain 1..65536 rows")
            if type(row) is not dict or tuple(row) != names:
                raise ValueError("Parquet row columns/order must match the registered spec")
            snapshot.append(row)
        if not snapshot:
            raise ValueError("Parquet batch must contain 1..65536 rows")
        try:
            table = pa.Table.from_pylist(snapshot, schema=_arrow_schema(self._spec))
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


@dataclass(frozen=True, init=False)
class StagedParquetHandle:
    """Owner-bound reopened staged Parquet handle."""

    _owner: OwnedStageArtifactOwner
    _leaf: OwnedStageParquetLeaf
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
        self._owner.assert_live()
        self._owner.require_owned_parquet_leaf(self._leaf)
        self._owner._require_registered_staged_handle(self, self._owner_registration_token)

    def _assert_physical_identity(self) -> None:
        self.require_registered()
        with self._leaf.open_verified() as stream:
            if _physical_digest(stream) != (
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
        with self._leaf.open_verified() as stream:
            if _physical_digest(stream) != (
                self.physical_size_bytes,
                self.physical_sha256,
            ):
                raise ValueError("staged Parquet physical identity changed")
            parquet = pq.ParquetFile(stream)
            yield parquet.iter_batches(batch_size=batch_size, use_threads=False)
            if _physical_digest(stream) != (
                self.physical_size_bytes,
                self.physical_sha256,
            ):
                raise ValueError("staged Parquet changed during iteration")
        self._leaf.assert_unchanged()


@dataclass(frozen=True, init=False)
class StagedParquetVerification:
    """Physical and logical facts from one staged reopen."""

    _owner: OwnedStageArtifactOwner
    _owner_registration_token: object
    logical: ExpectedLogicalTable
    physical_size_bytes: int
    physical_sha256: str
    handle: StagedParquetHandle

    def __init__(self) -> None:
        raise TypeError("StagedParquetVerification is issued only by verification")

    def require_registered(self) -> None:
        """Require this exact owner-issued verification and handle pair."""
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

    def extend(self, verification: StagedParquetVerification) -> "StagedParquetSet":
        """Append one same-owner verification and supersede this set."""
        self._owner.assert_live()
        self._owner._require_registered_staged_set(self, self._registration_token)
        if self.persistence_timestamp is not self._owner.persistence_timestamp:
            raise ValueError("staged persistence timestamp changed")
        if (
            type(verification) is not StagedParquetVerification
            or verification._owner is not self._owner
        ):
            raise ValueError("staged verification owner mismatch")
        verification.require_registered()
        combined = (*self.verifications, verification)
        _require_staged_table_order(combined)
        value = self._construct(
            owner=self._owner,
            verifications=combined,
            persistence_timestamp=self.persistence_timestamp,
        )
        token = self._owner._replace_registered_staged_set(self, value)
        object.__setattr__(value, "_registration_token", token)
        return value

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
        _require_staged_table_order(self.verifications)
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

    def verification_for(self, table_name: str) -> StagedParquetVerification:
        self._validate_contents()
        for verification in self.verifications:
            if verification.logical.name == table_name:
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
) -> tuple[int, str]:
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
        if observed_count != row_count:
            raise ValueError("physical row count differs from Parquet metadata")
        unique_index.assert_unique()
    workspace.assert_unchanged()
    return row_count, logical_hash


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
        row_count, logical_hash = _check_opened_parquet(
            spec=spec, stream=stream, workspace=workspace, limits=limits
        )
        physical_size_bytes, physical_sha256 = _physical_digest(stream)
        if before != (physical_size_bytes, physical_sha256):
            raise ValueError("staged Parquet changed during verification")
    leaf.assert_unchanged()
    logical = ExpectedLogicalTable(
        name=spec.table_name,
        grain=spec.grain,
        schema_hash=schema_sha256(spec),
        row_count=row_count,
        sort_key=spec.sort_key,
        unique_key=spec.unique_key,
        logical_hash=logical_hash,
    )
    handle = object.__new__(StagedParquetHandle)
    object.__setattr__(handle, "_owner", owner)
    object.__setattr__(handle, "_leaf", leaf)
    object.__setattr__(handle, "table_name", spec.table_name)
    object.__setattr__(handle, "row_count", row_count)
    object.__setattr__(handle, "schema_sha256", logical.schema_hash)
    object.__setattr__(handle, "logical_hash", logical.logical_hash)
    object.__setattr__(handle, "physical_size_bytes", physical_size_bytes)
    object.__setattr__(handle, "physical_sha256", physical_sha256)
    verification = object.__new__(StagedParquetVerification)
    object.__setattr__(verification, "_owner", owner)
    object.__setattr__(verification, "logical", logical)
    object.__setattr__(verification, "physical_size_bytes", physical_size_bytes)
    object.__setattr__(verification, "physical_sha256", physical_sha256)
    object.__setattr__(verification, "handle", handle)
    token = owner._register_staged_verification(verification, handle)
    object.__setattr__(handle, "_owner_registration_token", token)
    object.__setattr__(verification, "_owner_registration_token", token)
    owner._require_registered_staged_verification(verification, handle, token)
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


class _FinalVerificationWorkspace:
    _MARKER_BYTES = b"finproof-parquet-verification-v1\n"

    def __init__(self, root: Path) -> None:
        self._root = root
        self._marker = root / ".finproof-parquet-verification"
        self._spill = root / "spill"
        self._cleanup_safe = True
        self._identity = _owned_identity(root, expected_mode=0o700, directory=True)
        self._marker_identity = _owned_identity(self._marker, expected_mode=0o600, directory=False)
        self._spill_identity = _owned_identity(self._spill, expected_mode=0o700, directory=True)
        self._marker_sha256 = hashlib.sha256(self._MARKER_BYTES).hexdigest()
        self._spill_entries: tuple[tuple[str, tuple[int, int, int, int, int]], ...] | None = None

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
            connection.execute("SET temp_directory = ?", [os.fspath(self._spill)])
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
            raise _workspace_error("unique_index_setup_failed") from exc
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
                    entry.name,
                    _owned_identity(Path(entry.path), expected_mode=0o600, directory=False),
                )
                for entry in os.scandir(self._spill)
            )

    def assert_unchanged(self) -> None:
        if _owned_identity(self._root, expected_mode=0o700, directory=True) != self._identity:
            raise _workspace_error("workspace_directory_changed")
        if (
            _owned_identity(self._marker, expected_mode=0o600, directory=False)
            != self._marker_identity
        ):
            raise _workspace_error("workspace_marker_changed")
        marker_bytes = _read_owned_marker(self._marker, self._marker_identity)
        if (
            marker_bytes != self._MARKER_BYTES
            or hashlib.sha256(marker_bytes).hexdigest() != self._marker_sha256
        ):
            raise _workspace_error("workspace_marker_content_changed")
        if (
            _owned_identity(self._spill, expected_mode=0o700, directory=True)
            != self._spill_identity
        ):
            raise _workspace_error("workspace_spill_changed")
        if set(os.listdir(self._root)) != {self._marker.name, self._spill.name}:
            raise _workspace_error("workspace_entries_ambiguous")
        if self._spill_entries is not None:
            if tuple(sorted(os.listdir(self._spill))) != tuple(
                sorted(name for name, _ in self._spill_entries)
            ):
                raise _workspace_error("workspace_spill_entries_ambiguous")
            for name, identity in self._spill_entries:
                if (
                    _owned_identity(self._spill / name, expected_mode=0o600, directory=False)
                    != identity
                ):
                    raise _workspace_error("workspace_spill_entry_changed")

    def cleanup(self) -> None:
        if not self._cleanup_safe:
            raise _workspace_error("workspace_close_ambiguous")
        self.assert_unchanged()
        for name, _ in self._spill_entries or ():
            (self._spill / name).unlink()
        self._marker.unlink()
        self._spill.rmdir()
        self._root.rmdir()


def _owned_identity(
    path: Path, *, expected_mode: int | None, directory: bool
) -> tuple[int, int, int, int, int]:
    try:
        observed = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _workspace_error("workspace_entry_unavailable") from exc
    expected_type = stat.S_ISDIR(observed.st_mode) if directory else stat.S_ISREG(observed.st_mode)
    if (
        not expected_type
        or (expected_mode is not None and stat.S_IMODE(observed.st_mode) != expected_mode)
        or (not directory and observed.st_nlink != 1)
    ):
        raise _workspace_error("workspace_entry_identity_invalid")
    return (
        observed.st_dev,
        observed.st_ino,
        stat.S_IFMT(observed.st_mode),
        stat.S_IMODE(observed.st_mode),
        0 if directory else observed.st_nlink,
    )


def _read_owned_marker(path: Path, identity: tuple[int, int, int, int, int]) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
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
    return ArtifactContractError(
        ArtifactErrorCode.VERIFICATION_INCOMPLETE,
        operation_id="parquet-verification-workspace",
        internal_context={"reason": reason},
    )


@contextmanager
def _final_verification_workspace(
    *, parent: Path | None = None
) -> Iterator[_FinalVerificationWorkspace]:
    root: Path | None = None
    try:
        root = Path(
            tempfile.mkdtemp(
                prefix="finproof-parquet-verify-",
                dir=None if parent is None else os.fspath(parent),
            )
        )
        root_descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fchmod(root_descriptor, 0o700)
            os.mkdir("spill", mode=0o700, dir_fd=root_descriptor)
            marker_descriptor = os.open(
                ".finproof-parquet-verification",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=root_descriptor,
            )
            try:
                os.fchmod(marker_descriptor, 0o600)
                os.write(marker_descriptor, _FinalVerificationWorkspace._MARKER_BYTES)
                os.fsync(marker_descriptor)
            finally:
                os.close(marker_descriptor)
        finally:
            os.close(root_descriptor)
        workspace = _FinalVerificationWorkspace(root)
    except BaseException as exc:
        if isinstance(exc, ArtifactContractError):
            raise
        raise _workspace_error("workspace_setup_failed") from exc
    try:
        yield workspace
    finally:
        if workspace._cleanup_safe:
            workspace.cleanup()


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
        for spec in TABLE_SPECS:
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
                row_count, logical_hash = _check_opened_parquet(
                    spec=spec,
                    stream=stream,
                    workspace=workspace,
                    limits=ParquetVerificationLimits(),
                )
            logical = ExpectedLogicalTable(
                name=spec.table_name,
                grain=spec.grain,
                schema_hash=schema_sha256(spec),
                row_count=row_count,
                sort_key=spec.sort_key,
                unique_key=spec.unique_key,
                logical_hash=logical_hash,
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
            issued = inventory.issue_verified_table_handle(
                entry=entry,
                table_name=logical.name,
                row_count=logical.row_count,
                schema_sha256=logical.schema_hash,
                logical_hash=logical.logical_hash,
            )
            if type(issued) is not VerifiedParquetTable:
                raise ValueError("inventory issued the wrong final handle type")
            handle = issued
            tables.append(logical)
            handles.append(handle)
        inventory.assert_unchanged()
        return TableVerificationResult.from_verified(
            inventory=inventory,
            tables=tuple(tables),
            handles=tuple(handles),
        )
