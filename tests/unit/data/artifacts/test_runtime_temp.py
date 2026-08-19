"""CP7A private runtime workspace boundaries."""

from pathlib import Path
from typing import Any, cast

import pytest

from tests.helpers.artifacts import write_empty_database_artifact_tree


def test_database_verifier_rejects_symlink_runtime_root_before_copy(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.database import verify_database_against_parquet
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    trusted = tmp_path / "trusted"
    trusted.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(trusted, target_is_directory=True)
    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        from finproof.data.artifacts.errors import (
            ArtifactContractError,
            ArtifactErrorCode,
        )

        with pytest.raises(ArtifactContractError) as raised:
            verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
                runtime_tmp_root=alias,
            )
        assert raised.value.code is ArtifactErrorCode.DATABASE_VALIDATION_FAILED
        assert raised.value.internal_context["reason"] == "unsafe_runtime_temp_root"
    assert tuple(trusted.iterdir()) == ()


def test_database_verifier_removes_exact_private_workspace(tmp_path: Path) -> None:
    from finproof.data.artifacts.database import verify_database_against_parquet
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        verify_database_against_parquet(
            inventory=inventory,
            database_entry=inventory.declared_entries[0],
            tables=tables,
            runtime_tmp_root=runtime,
        )
    assert tuple(runtime.iterdir()) == ()


def test_database_verifier_completes_bounded_copy_after_partial_os_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from finproof.data.artifacts import database
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    real_write = os.write

    def partial_write(descriptor: int, payload: bytes) -> int:
        return real_write(descriptor, payload[: max(1, len(payload) // 2)])

    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(cast(Any, database).os, "write", partial_write)
        database.verify_database_against_parquet(
            inventory=inventory,
            database_entry=inventory.declared_entries[0],
            tables=tables,
        )


def test_database_verifier_retains_ambiguous_runtime_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import database
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        database_duckdb = cast(Any, database).duckdb
        real_connect = database_duckdb.connect

        def inject_unknown(path: str, **kwargs: object) -> Any:
            Path(path).with_name("unexpected").write_bytes(b"foreign")
            return real_connect(path, **kwargs)

        monkeypatch.setattr(database_duckdb, "connect", inject_unknown)
        from finproof.data.artifacts.errors import ArtifactContractError

        with pytest.raises(ArtifactContractError):
            database.verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
                runtime_tmp_root=runtime,
            )
    workspaces = tuple(runtime.iterdir())
    assert len(workspaces) == 1
    assert (workspaces[0] / "unexpected").read_bytes() == b"foreign"


def test_database_verifier_blocks_private_copy_substitution_before_first_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import database
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)

    class UnqueriedConnection:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("substituted database must fail before its first query")

        def close(self) -> None:
            return None

    def substitute(path: str, **_kwargs: object) -> UnqueriedConnection:
        copy = Path(path)
        payload = copy.read_bytes()
        copy.rename(copy.with_suffix(".owned"))
        copy.write_bytes(payload)
        return UnqueriedConnection()

    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(cast(Any, database).duckdb, "connect", substitute)
        with pytest.raises(ArtifactContractError):
            database.verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
                runtime_tmp_root=runtime,
            )


def test_database_verifier_maps_connection_close_fault_to_typed_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import database
    from finproof.data.artifacts.errors import (
        ArtifactContractError,
        ArtifactErrorCode,
    )
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    real_connect = cast(Any, database).duckdb.connect

    class CloseFaultConnection:
        def __init__(self, connection: Any) -> None:
            self._connection = connection

        def execute(self, *args: object, **kwargs: object) -> Any:
            return self._connection.execute(*args, **kwargs)

        def register(self, *args: object, **kwargs: object) -> Any:
            return self._connection.register(*args, **kwargs)

        def unregister(self, *args: object, **kwargs: object) -> Any:
            return self._connection.unregister(*args, **kwargs)

        def close(self) -> None:
            self._connection.close()
            raise OSError("injected close fault")

    def connect(path: str, **kwargs: object) -> CloseFaultConnection:
        return CloseFaultConnection(real_connect(path, **kwargs))

    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(cast(Any, database).duckdb, "connect", connect)
        with pytest.raises(ArtifactContractError) as raised:
            database.verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
            )
    assert raised.value.code is ArtifactErrorCode.DATABASE_VALIDATION_FAILED


def test_database_verifier_removes_owned_workspace_after_marker_write_fault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import database
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)

    def fail_write(_descriptor: int, _payload: bytes) -> int:
        raise OSError("injected marker write fault")

    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(cast(Any, database).os, "write", fail_write)
        with pytest.raises(ArtifactContractError):
            database.verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
                runtime_tmp_root=runtime,
            )
    assert tuple(runtime.iterdir()) == ()


def test_database_verifier_retains_substitution_at_cleanup_tombstone_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from finproof.data.artifacts import database
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    real_rename = os.rename
    substituted = False

    def substitute_before_tombstone(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal substituted
        if source == "database-copy.duckdb" and not substituted:
            substituted = True
            real_rename(
                source,
                "owned-database-copy.duckdb",
                src_dir_fd=src_dir_fd,
                dst_dir_fd=src_dir_fd,
            )
            descriptor = os.open(
                source,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=src_dir_fd,
            )
            try:
                os.write(descriptor, b"foreign")
            finally:
                os.close(descriptor)
        real_rename(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(cast(Any, database).os, "rename", substitute_before_tombstone)
        with pytest.raises(ArtifactContractError):
            database.verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
                runtime_tmp_root=runtime,
            )
    assert substituted
    assert any(path.read_bytes() == b"foreign" for path in runtime.rglob("*") if path.is_file())


def test_database_verifier_maps_private_copy_fsync_fault_to_typed_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from finproof.data.artifacts import database
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    real_fsync = os.fsync
    calls = 0

    def fail_copy_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected copy fsync fault")
        real_fsync(descriptor)

    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(cast(Any, database).os, "fsync", fail_copy_fsync)
        with pytest.raises(ArtifactContractError):
            database.verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
            )
