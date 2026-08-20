"""Self-contained DuckDB construction and verification."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

import duckdb

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.expected_contract import ArtifactLogicalContractView
from finproof.data.artifacts.hashing import TableSpecIdentity
from finproof.data.artifacts.manifest import (
    ArtifactCoreVerificationResult,
    ArtifactDatabaseVerifier,
    ArtifactManifest,
    ArtifactTableVerifier,
    ArtifactVerificationKernel,
    TableVerificationResult,
    VerifiedPhysicalEntry,
    VerifiedPhysicalInventory,
)
from finproof.data.artifacts.parquet_io import (
    ParquetArtifactTableVerifier,
    StagedParquetSet,
    VerifiedParquetTable,
    _open_final_verified_batches,
)
from finproof.data.artifacts.reports import (
    StrictArtifactReportVerifier,
    _FinalReportVerificationObservations,
)
from finproof.data.artifacts.resources import _expected_contract_resource_exists
from finproof.data.artifacts.staging import (
    OwnedStageDatabaseLeaf,
    OwnedStageDatabaseOwner,
    SealedStageDatabase,
)
from finproof.data.artifacts.table_specs import (
    TABLE_SPECS,
    ClosedTableSpecRegistry,
    TableSpec,
)


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _create_table_sql(spec: TableSpec) -> str:
    columns = ", ".join(
        f"{_identifier(column.name)} {column.duckdb_type}"
        + ("" if column.nullable else " NOT NULL")
        for column in spec.columns
    )
    return f"CREATE TABLE {_identifier(spec.table_name)} ({columns})"


def _materialize_tables(connection: object, tables: StagedParquetSet) -> None:
    execute = connection.execute  # type: ignore[attr-defined]
    execute("SET threads = 1")
    execute("SET preserve_insertion_order = true")
    execute("SET TimeZone = 'UTC'")
    for spec in TABLE_SPECS:
        execute(_create_table_sql(spec))
        handle = tables.verification_for(spec.table_name).handle
        columns = ", ".join(_identifier(column.name) for column in spec.columns)
        order = ", ".join(_identifier(name) for name in spec.sort_key)
        with handle.iter_batches() as batches:
            for batch in batches:
                connection.register("_finproof_batch", batch)  # type: ignore[attr-defined]
                try:
                    execute(
                        f"INSERT INTO {_identifier(spec.table_name)} ({columns}) "  # noqa: S608 -- closed TABLE_SPECS identifiers
                        f"SELECT {columns} FROM _finproof_batch ORDER BY {order}"
                    )
                finally:
                    connection.unregister("_finproof_batch")  # type: ignore[attr-defined]


def open_read_only_database(path: Path) -> duckdb.DuckDBPyConnection:
    """Open one existing regular DuckDB artifact with external access locked off."""
    observed = os.lstat(path)
    if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise ValueError("artifact database must be a single-link regular file")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        connection.execute("SET enable_external_access = false")
        connection.execute("SET allow_unsigned_extensions = false")
        connection.execute("SET autoinstall_known_extensions = false")
        connection.execute("SET autoload_known_extensions = false")
        connection.execute("SET lock_configuration = true")
    except BaseException:
        connection.close()
        raise
    return connection


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("database copy write made no progress")
        view = view[written:]


def _runtime_failure(reason: str) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.DATABASE_VALIDATION_FAILED,
        operation_id="verify-artifact-database",
        target_basename="finproof.duckdb",
        internal_context={"reason": reason},
    )


def _runtime_tmp_parent(root: Path | None) -> str | None:
    if root is None:
        return None
    observed = os.lstat(root)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or stat.S_ISLNK(observed.st_mode)
        or observed.st_uid != os.getuid()
        or stat.S_IMODE(observed.st_mode) != 0o700
    ):
        raise _runtime_failure("unsafe_runtime_temp_root")
    return str(root)


def _directory_identity(
    path: str | Path,
    *,
    dir_fd: int | None = None,
) -> tuple[int, int, int, int]:
    observed = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
    return _directory_identity_from_stat(observed)


def _directory_identity_from_stat(observed: os.stat_result) -> tuple[int, int, int, int]:
    if not stat.S_ISDIR(observed.st_mode) or stat.S_ISLNK(observed.st_mode):
        raise _runtime_failure("runtime_workspace_directory_changed")
    return (
        observed.st_dev,
        observed.st_ino,
        stat.S_IFMT(observed.st_mode),
        stat.S_IMODE(observed.st_mode),
    )


def _file_identity(
    path: str | Path,
    *,
    dir_fd: int | None = None,
) -> tuple[int, int, int, int, int]:
    observed = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
    return _file_identity_from_stat(observed)


def _file_identity_from_stat(
    observed: os.stat_result,
) -> tuple[int, int, int, int, int]:
    if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise _runtime_failure("runtime_workspace_leaf_changed")
    return (
        observed.st_dev,
        observed.st_ino,
        stat.S_IFMT(observed.st_mode),
        stat.S_IMODE(observed.st_mode),
        observed.st_nlink,
    )


class _OwnedRuntimeWorkspace:
    _MARKER = b"finproof-runtime-workspace-v1\n"

    def __init__(self, parent: str | None) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="finproof-database-verify-", dir=parent))
        self._parent_fd = -1
        self._root_fd = -1
        self._copy_fd = -1
        self._root_name = self.root.name
        marker_created = False
        try:
            os.chmod(self.root, 0o700)
            self._parent_fd = os.open(
                self.root.parent,
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
            self._root_fd = os.open(
                self._root_name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=self._parent_fd,
            )
            self._root_identity = _directory_identity(
                self._root_name,
                dir_fd=self._parent_fd,
            )
            descriptor = os.open(
                ".finproof-runtime.marker",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=self._root_fd,
            )
            marker_created = True
            try:
                _write_all(descriptor, self._MARKER)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self._marker_identity = _file_identity(
                ".finproof-runtime.marker",
                dir_fd=self._root_fd,
            )
        except (ArtifactContractError, OSError, TypeError, ValueError) as exc:
            try:
                if marker_created and self._root_fd >= 0:
                    os.unlink(".finproof-runtime.marker", dir_fd=self._root_fd)
                if self._parent_fd >= 0:
                    os.rmdir(self._root_name, dir_fd=self._parent_fd)
                else:
                    os.rmdir(self.root)
            finally:
                if self._root_fd >= 0:
                    os.close(self._root_fd)
                if self._parent_fd >= 0:
                    os.close(self._parent_fd)
            raise _runtime_failure("runtime_workspace_create_failed") from exc
        self._copy_identity: tuple[int, int, int, int, int] | None = None
        self._spill_identity: tuple[int, int, int, int] | None = None

    def __enter__(self) -> _OwnedRuntimeWorkspace:
        self._validate()
        return self

    def __exit__(self, *args: object) -> None:
        del args
        try:
            try:
                self._cleanup()
            except ArtifactContractError:
                raise
            except (OSError, TypeError, ValueError) as exc:
                raise _runtime_failure("runtime_workspace_cleanup_failed") from exc
        finally:
            if self._copy_fd >= 0:
                os.close(self._copy_fd)
                self._copy_fd = -1
            os.close(self._root_fd)
            os.close(self._parent_fd)

    def create_database_copy(self) -> tuple[Path, int]:
        self._validate()
        try:
            descriptor = os.open(
                "database-copy.duckdb",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=self._root_fd,
            )
        except OSError as exc:
            raise _runtime_failure("runtime_database_copy_create_failed") from exc
        self._copy_identity = _file_identity(
            "database-copy.duckdb",
            dir_fd=self._root_fd,
        )
        return self.root / "database-copy.duckdb", descriptor

    def create_spill(self) -> Path:
        self._validate()
        try:
            os.mkdir("spill", mode=0o700, dir_fd=self._root_fd)
        except OSError as exc:
            raise _runtime_failure("runtime_spill_create_failed") from exc
        self._spill_identity = _directory_identity("spill", dir_fd=self._root_fd)
        return self.root / "spill"

    def validate_copy(self) -> None:
        self._validate()
        if self._copy_identity is None:
            raise _runtime_failure("runtime_database_copy_missing")
        if self._copy_fd < 0:
            self._copy_fd = os.open(
                "database-copy.duckdb",
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=self._root_fd,
            )
        if (
            _file_identity("database-copy.duckdb", dir_fd=self._root_fd) != self._copy_identity
            or _file_identity_from_stat(os.fstat(self._copy_fd)) != self._copy_identity
        ):
            raise _runtime_failure("runtime_database_copy_changed")

    def copy_digest(self) -> tuple[int, str]:
        self.validate_copy()
        digest = hashlib.sha256()
        size = 0
        offset = 0
        while payload := os.pread(self._copy_fd, 1024 * 1024, offset):
            size += len(payload)
            offset += len(payload)
            digest.update(payload)
        self.validate_copy()
        return size, digest.hexdigest()

    def _validate(self) -> None:
        if (
            _directory_identity(self._root_name, dir_fd=self._parent_fd) != self._root_identity
            or _directory_identity_from_stat(os.fstat(self._root_fd)) != self._root_identity
        ):
            raise _runtime_failure("runtime_workspace_directory_changed")
        marker_fd = os.open(
            ".finproof-runtime.marker",
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=self._root_fd,
        )
        try:
            marker_identity = _file_identity_from_stat(os.fstat(marker_fd))
            marker_payload = os.read(marker_fd, len(self._MARKER) + 1)
        finally:
            os.close(marker_fd)
        if marker_identity != self._marker_identity or marker_payload != self._MARKER:
            raise _runtime_failure("runtime_workspace_marker_changed")
        expected = {".finproof-runtime.marker"}
        if self._copy_identity is not None:
            expected.add("database-copy.duckdb")
        if self._spill_identity is not None:
            expected.add("spill")
        if {entry.name for entry in os.scandir(self._root_fd)} != expected:
            raise _runtime_failure("runtime_workspace_inventory_ambiguous")
        if (
            self._copy_identity is not None
            and _file_identity("database-copy.duckdb", dir_fd=self._root_fd) != self._copy_identity
        ):
            raise _runtime_failure("runtime_database_copy_changed")
        if (
            self._spill_identity is not None
            and _directory_identity("spill", dir_fd=self._root_fd) != self._spill_identity
        ):
            raise _runtime_failure("runtime_spill_changed")

    def _cleanup(self) -> None:
        self._validate()
        if self._spill_identity is not None:
            spill_fd = os.open(
                "spill",
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=self._root_fd,
            )
            entries = tuple(os.scandir(spill_fd))
            identities: dict[str, tuple[int, int, int, int, int]] = {}
            for entry in entries:
                observed = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
                    raise _runtime_failure("runtime_spill_inventory_ambiguous")
                identities[entry.name] = (
                    observed.st_dev,
                    observed.st_ino,
                    stat.S_IFMT(observed.st_mode),
                    stat.S_IMODE(observed.st_mode),
                    observed.st_nlink,
                )
            try:
                for entry in entries:
                    if _file_identity(entry.name, dir_fd=spill_fd) != identities[entry.name]:
                        raise _runtime_failure("runtime_spill_leaf_changed")
                    self._remove_owned_leaf(
                        directory_fd=spill_fd,
                        name=entry.name,
                        identity=identities[entry.name],
                    )
            finally:
                os.close(spill_fd)
            if _directory_identity("spill", dir_fd=self._root_fd) != self._spill_identity:
                raise _runtime_failure("runtime_spill_changed")
            self._remove_owned_directory(
                parent_fd=self._root_fd,
                name="spill",
                identity=self._spill_identity,
            )
        if self._copy_identity is not None:
            if _file_identity("database-copy.duckdb", dir_fd=self._root_fd) != self._copy_identity:
                raise _runtime_failure("runtime_database_copy_changed")
            self._remove_owned_leaf(
                directory_fd=self._root_fd,
                name="database-copy.duckdb",
                identity=self._copy_identity,
            )
        if (
            _file_identity(".finproof-runtime.marker", dir_fd=self._root_fd)
            != self._marker_identity
        ):
            raise _runtime_failure("runtime_workspace_marker_changed")
        self._remove_owned_leaf(
            directory_fd=self._root_fd,
            name=".finproof-runtime.marker",
            identity=self._marker_identity,
        )
        if _directory_identity(self._root_name, dir_fd=self._parent_fd) != self._root_identity:
            raise _runtime_failure("runtime_workspace_directory_changed")
        self._remove_owned_directory(
            parent_fd=self._parent_fd,
            name=self._root_name,
            identity=self._root_identity,
        )

    @staticmethod
    def _remove_owned_leaf(
        *,
        directory_fd: int,
        name: str,
        identity: tuple[int, int, int, int, int],
    ) -> None:
        tombstone = f".finproof-remove-{secrets.token_hex(16)}"
        os.rename(
            name,
            tombstone,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        if _file_identity(tombstone, dir_fd=directory_fd) != identity:
            raise _runtime_failure("runtime_cleanup_leaf_changed")
        os.unlink(tombstone, dir_fd=directory_fd)

    @staticmethod
    def _remove_owned_directory(
        *,
        parent_fd: int,
        name: str,
        identity: tuple[int, int, int, int],
    ) -> None:
        tombstone = f".finproof-remove-{secrets.token_hex(16)}"
        os.rename(
            name,
            tombstone,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        if _directory_identity(tombstone, dir_fd=parent_fd) != identity:
            raise _runtime_failure("runtime_cleanup_directory_changed")
        os.rmdir(tombstone, dir_fd=parent_fd)


@dataclass(frozen=True, slots=True)
class _VerifierWorkspaceObservations:
    mode: int
    marker_owned: bool
    containment_verified: bool
    cleanup_completed: bool
    threads: int
    memory_limit: str


class _VerifierWorkspaceObservationSink:
    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value: _VerifierWorkspaceObservations | None = None

    def _record(self, value: _VerifierWorkspaceObservations) -> None:
        if self._value is not None or type(value) is not _VerifierWorkspaceObservations:
            raise ValueError("verifier workspace observations changed")
        self._value = value

    def require(self) -> _VerifierWorkspaceObservations:
        if self._value is None:
            raise ValueError("verifier workspace observations are unavailable")
        return self._value


def _verify_database_against_parquet(
    *,
    inventory: VerifiedPhysicalInventory,
    database_entry: VerifiedPhysicalEntry,
    tables: TableVerificationResult,
    runtime_tmp_root: Path | None = None,
) -> _VerifierWorkspaceObservations:
    """Compare one inventory-owned database with all final Parquet handles."""
    tables.validate_against(inventory)
    inventory.require_owned(database_entry)
    if database_entry.path.as_posix() != "finproof.duckdb" or database_entry.kind != "duckdb":
        raise ValueError("database entry is not the exact manifest database")
    parent = _runtime_tmp_parent(runtime_tmp_root)
    with _OwnedRuntimeWorkspace(parent) as workspace:
        database_copy, descriptor = workspace.create_database_copy()
        try:
            with inventory.open_verified(database_entry) as source:
                while payload := source.read(1024 * 1024):
                    _write_all(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        workspace.validate_copy()
        if workspace.copy_digest() != (
            database_entry.size_bytes,
            database_entry.sha256,
        ):
            raise _runtime_failure("runtime_database_copy_digest_changed")
        spill = workspace.create_spill()
        try:
            connection = duckdb.connect(str(database_copy), read_only=True)
        except (duckdb.Error, OSError) as exc:
            raise _runtime_failure("runtime_database_open_failed") from exc
        try:
            workspace.validate_copy()
            connection.execute("SET threads = 1")
            connection.execute("SET memory_limit = '1GiB'")
            connection.execute("SET preserve_insertion_order = false")
            connection.execute("SET TimeZone = 'UTC'")
            connection.execute("SET temp_directory = ?", [str(spill)])
            runtime_settings = connection.execute(
                "SELECT current_setting('threads'), current_setting('memory_limit')"
            ).fetchone()
            if runtime_settings != (1, "1.0 GiB"):
                raise ValueError("DuckDB verifier runtime settings changed")
            observed_tables = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main' ORDER BY table_name"
                ).fetchall()
            )
            if observed_tables != tuple(sorted(spec.table_name for spec in TABLE_SPECS)):
                raise ValueError("DuckDB differs from Parquet table inventory")
            observed_views = connection.execute(
                "SELECT view_name FROM duckdb_views() "
                "WHERE schema_name = 'main' AND NOT internal ORDER BY view_name"
            ).fetchall()
            if observed_views:
                raise ValueError("DuckDB contains undeclared views")
            handles = {
                handle.table_name: handle
                for handle in tables.handles
                if type(handle) is VerifiedParquetTable
            }
            for index, spec in enumerate(TABLE_SPECS):
                columns_schema = connection.execute(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'main' AND table_name = ? "
                    "ORDER BY ordinal_position",
                    [spec.table_name],
                ).fetchall()
                expected_schema = [
                    (
                        column.name,
                        {
                            "TIMESTAMPTZ": "TIMESTAMP WITH TIME ZONE",
                        }.get(column.duckdb_type, column.duckdb_type),
                        "YES" if column.nullable else "NO",
                    )
                    for column in spec.columns
                ]
                if columns_schema != expected_schema:
                    raise ValueError("DuckDB differs from frozen table schema")
                handle = handles.get(spec.table_name)
                if handle is None:
                    raise ValueError("DuckDB differs from Parquet handle inventory")
                expected = f"_finproof_expected_{index}"
                quoted_expected = _identifier(expected)
                quoted_table = _identifier(spec.table_name)
                columns = ", ".join(_identifier(column.name) for column in spec.columns)
                connection.execute(
                    f"CREATE TEMP TABLE {quoted_expected} AS "  # noqa: S608 -- closed TABLE_SPECS identifiers
                    f"SELECT {columns} FROM {quoted_table} WHERE false"
                )
                with _open_final_verified_batches(
                    inventory=inventory,
                    tables=tables,
                    spec=spec,
                    handle=handle,
                ) as batches:
                    for batch in batches:
                        connection.register("_finproof_batch", batch)
                        try:
                            connection.execute(
                                f"INSERT INTO {quoted_expected} ({columns}) "  # noqa: S608 -- closed TABLE_SPECS identifiers
                                f"SELECT {columns} FROM _finproof_batch"
                            )
                        finally:
                            connection.unregister("_finproof_batch")
                difference = connection.execute(
                    "SELECT count(*) FROM ("  # noqa: S608 -- closed TABLE_SPECS identifiers
                    f"(SELECT {columns} FROM {quoted_table} EXCEPT ALL "
                    f"SELECT {columns} FROM {quoted_expected}) UNION ALL "
                    f"(SELECT {columns} FROM {quoted_expected} EXCEPT ALL "
                    f"SELECT {columns} FROM {quoted_table}))"
                ).fetchone()
                if difference != (0,):
                    raise ValueError("DuckDB differs from Parquet")
        except (duckdb.Error, OSError) as exc:
            raise _runtime_failure("runtime_database_query_failed") from exc
        finally:
            try:
                connection.close()
            except (duckdb.Error, OSError, TypeError, ValueError) as exc:
                raise _runtime_failure("runtime_database_close_failed") from exc
        workspace.validate_copy()
        if workspace.copy_digest() != (
            database_entry.size_bytes,
            database_entry.sha256,
        ):
            raise _runtime_failure("runtime_database_copy_digest_changed")
        inventory.assert_unchanged()
        workspace_mode = workspace._root_identity[3]
    return _VerifierWorkspaceObservations(
        mode=workspace_mode,
        marker_owned=True,
        containment_verified=True,
        cleanup_completed=True,
        threads=runtime_settings[0],
        memory_limit="1GiB",
    )


def verify_database_against_parquet(
    *,
    inventory: VerifiedPhysicalInventory,
    database_entry: VerifiedPhysicalEntry,
    tables: TableVerificationResult,
    runtime_tmp_root: Path | None = None,
    _observations: _VerifierWorkspaceObservationSink | None = None,
) -> None:
    """Compare one inventory-owned database with all final Parquet handles."""
    try:
        observed = _verify_database_against_parquet(
            inventory=inventory,
            database_entry=database_entry,
            tables=tables,
            runtime_tmp_root=runtime_tmp_root,
        )
    except ArtifactContractError:
        raise
    except OSError as exc:
        raise _runtime_failure("runtime_io_failed") from exc
    if _observations is not None:
        if type(_observations) is not _VerifierWorkspaceObservationSink:
            raise TypeError("verifier workspace observation sink changed")
        _observations._record(observed)


class DuckDBArtifactDatabaseVerifier:
    """Concrete CP2 database port bound to the final inventory and handles."""

    __slots__ = ("_observations",)

    def __init__(
        self,
        *,
        observations: _VerifierWorkspaceObservationSink | None = None,
    ) -> None:
        if observations is not None and type(observations) is not _VerifierWorkspaceObservationSink:
            raise TypeError("verifier workspace observation sink changed")
        self._observations = observations

    def verify_database(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        specs: tuple[TableSpecIdentity, ...],
        tables: TableVerificationResult,
        logical: ArtifactCoreVerificationResult,
    ) -> None:
        if (
            type(manifest) is not ArtifactManifest
            or type(inventory) is not VerifiedPhysicalInventory
            or type(tables) is not TableVerificationResult
            or type(logical) is not ArtifactCoreVerificationResult
            or specs is not TABLE_SPECS
            or logical.tables != tables.tables
            or logical.overall_manifest_logical_hash != manifest.logical_hash
        ):
            raise ValueError("database verifier requires the exact verified core")
        tables.validate_against(inventory)
        database_entry = next(
            (
                entry
                for entry in inventory.declared_entries
                if entry.path.as_posix() == manifest.database_path and entry.kind == "duckdb"
            ),
            None,
        )
        if database_entry is None or database_entry.sha256 != manifest.database_sha256:
            raise ValueError("manifest database entry changed")
        verify_database_against_parquet(
            inventory=inventory,
            database_entry=database_entry,
            tables=tables,
            _observations=self._observations,
        )


class PackagedArtifactExpectedComparator:
    """CP7 assembly shape; CP8 supplies the deliberately absent baseline bytes."""

    def compare(self, *, actual: ArtifactLogicalContractView) -> None:
        del actual
        reason = (
            "expected_contract_loader_unavailable"
            if _expected_contract_resource_exists()
            else "expected_contract_resource_absent"
        )
        raise ArtifactContractError(
            ArtifactErrorCode.BASELINE_MISSING,
            operation_id="compare-packaged-artifact-contract",
            internal_context={"reason": reason},
        )


def artifact_verification_kernel(
    *,
    report_observations: _FinalReportVerificationObservations | None = None,
    workspace_observations: _VerifierWorkspaceObservationSink | None = None,
) -> ArtifactVerificationKernel:
    """Assemble the closed CP7 core verifier and inactive expected route."""
    return ArtifactVerificationKernel(
        table_registry=ClosedTableSpecRegistry(TABLE_SPECS),
        table_verifier=cast(ArtifactTableVerifier, ParquetArtifactTableVerifier()),
        report_verifier=StrictArtifactReportVerifier(observations=report_observations),
        database_verifier=cast(
            ArtifactDatabaseVerifier,
            DuckDBArtifactDatabaseVerifier(observations=workspace_observations),
        ),
        expected_comparator=PackagedArtifactExpectedComparator(),
    )


class _StagedDatabaseVerificationIssuance:
    __slots__ = ("facts", "value")

    def __init__(self, value: StagedDatabaseVerification) -> None:
        self.value = value
        self.facts = tuple(
            getattr(value, name) for name in value.__dataclass_fields__ if name != "_issuance"
        )


@dataclass(frozen=True, init=False, slots=True)
class StagedDatabaseVerification:
    """Exact CP7 wrapper around one CP4 owner-registered database seal."""

    _owner: OwnedStageDatabaseOwner
    _sealed: SealedStageDatabase
    _owner_registration: object
    _leaf_issuance_token: object
    persistence_timestamp: datetime
    physical_size_bytes: int
    physical_sha256: str
    _issuance: _StagedDatabaseVerificationIssuance

    def __new__(cls) -> StagedDatabaseVerification:
        raise TypeError("StagedDatabaseVerification requires from_sealed")

    @classmethod
    def from_sealed(
        cls,
        *,
        owner: OwnedStageDatabaseOwner,
        sealed: SealedStageDatabase,
    ) -> StagedDatabaseVerification:
        if type(sealed) is not SealedStageDatabase:
            raise TypeError("StagedDatabaseVerification requires the exact sealed database")
        sealed.validate_against(owner)
        value = object.__new__(cls)
        object.__setattr__(value, "_owner", owner)
        object.__setattr__(value, "_sealed", sealed)
        object.__setattr__(value, "_owner_registration", sealed._owner_registration)
        object.__setattr__(value, "_leaf_issuance_token", sealed._leaf_issuance_token)
        object.__setattr__(value, "persistence_timestamp", sealed.persistence_timestamp)
        object.__setattr__(value, "physical_size_bytes", sealed.physical_size_bytes)
        object.__setattr__(value, "physical_sha256", sealed.physical_sha256)
        object.__setattr__(value, "_issuance", _StagedDatabaseVerificationIssuance(value))
        return value

    def validate_against(self, owner: OwnedStageDatabaseOwner) -> None:
        try:
            if (
                type(self._issuance) is not _StagedDatabaseVerificationIssuance
                or self._issuance.value is not self
                or self._issuance.facts
                != tuple(
                    getattr(self, name) for name in self.__dataclass_fields__ if name != "_issuance"
                )
                or owner is not self._owner
                or type(self._sealed) is not SealedStageDatabase
                or self._owner_registration is not self._sealed._owner_registration
                or self._leaf_issuance_token is not self._sealed._leaf_issuance_token
                or self.persistence_timestamp is not self._sealed.persistence_timestamp
                or self.physical_size_bytes != self._sealed.physical_size_bytes
                or self.physical_sha256 != self._sealed.physical_sha256
            ):
                raise ValueError("database verification changed")
            self._sealed.validate_against(owner)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("database verification changed") from exc


def build_self_contained_database(
    *,
    owner: OwnedStageDatabaseOwner,
    tables: StagedParquetSet,
    database_leaf: OwnedStageDatabaseLeaf,
) -> StagedDatabaseVerification:
    """Build the complete CP7 database from one live staged table set."""
    if type(tables) is not StagedParquetSet:
        raise TypeError("database builder requires the exact staged table set")
    tables.require_complete()
    if tables._owner is not owner:
        raise ValueError("database builder requires the staged table owner")
    owner.require_owned_database_leaf(database_leaf)
    with owner.create_database_build_workspace() as workspace:
        with workspace.open_writer() as connection:
            _materialize_tables(connection, tables)
        sealed = workspace.checkpoint_close_and_seal(leaf=database_leaf)
    sealed.validate_against(owner)
    return StagedDatabaseVerification.from_sealed(owner=owner, sealed=sealed)
