"""CP7A self-contained DuckDB construction contracts."""

import copy
import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from tests.helpers.artifacts import (
    artifact_build_input_identity,
    artifact_staging_settings,
    write_database_artifact_tree,
)


@contextmanager
def _empty_stage(repository_root: Path) -> Iterator[tuple[Any, Any]]:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    settings = artifact_staging_settings(repository_root)
    identity = artifact_build_input_identity(settings)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=identity,
    ) as session:
        verifications = []
        for spec in TABLE_SPECS:
            leaf = session.claim_parquet_leaf(spec)
            ParquetBatchWriter(spec, leaf).close()
            verifications.append(verify_staged_parquet_table(owner=session, leaf=leaf, spec=spec))
        tables = StagedParquetSet.from_verified(
            owner=session,
            verifications=tuple(verifications),
        )
        yield session, tables


def test_database_module_skeleton_rejects_complete_owned_stage_fixture() -> None:
    from finproof.data.artifacts.database import build_self_contained_database

    with pytest.raises((NotImplementedError, TypeError)):
        build_self_contained_database(
            owner=object(),  # type: ignore[arg-type]
            tables=object(),  # type: ignore[arg-type]
            database_leaf=object(),  # type: ignore[arg-type]
        )


def test_database_builder_requires_canonical_complete_set_and_same_owner_leaf(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.database import build_self_contained_database
    from finproof.data.artifacts.errors import ArtifactContractError

    with (
        _empty_stage(tmp_path / "first") as (owner, tables),
        _empty_stage(tmp_path / "second") as (foreign_owner, _),
    ):
        leaf = owner.claim_database_leaf()
        foreign_leaf = foreign_owner.claim_database_leaf()
        with pytest.raises((ArtifactContractError, TypeError, ValueError)):
            build_self_contained_database(
                owner=owner,
                tables=object(),  # type: ignore[arg-type]
                database_leaf=leaf,
            )
        with pytest.raises((ArtifactContractError, TypeError, ValueError)):
            build_self_contained_database(
                owner=owner,
                tables=tables,
                database_leaf=foreign_leaf,
            )
        result = build_self_contained_database(
            owner=owner,
            tables=tables,
            database_leaf=leaf,
        )
        result.validate_against(owner)


def test_database_builder_materializes_exact_tables_through_cp4_managed_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb

    from finproof.data.artifacts import staging
    from finproof.data.artifacts.database import build_self_contained_database
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    connection = duckdb.connect(":memory:")

    class Workspace:
        def __enter__(self) -> "Workspace":
            return self

        def __exit__(self, *args: object) -> None:
            del args

        @contextmanager
        def open_writer(self) -> Iterator[Any]:
            yield connection

        def checkpoint_close_and_seal(self, *, leaf: object) -> None:
            del leaf
            raise NotImplementedError("CP7A database sealing is not implemented")

    workspace = Workspace()
    monkeypatch.setattr(
        staging.ArtifactBuildSession,
        "create_database_build_workspace",
        lambda _self: workspace,
    )
    with _empty_stage(tmp_path / "repository") as (owner, tables):
        leaf = owner.claim_database_leaf()
        with pytest.raises(NotImplementedError, match="CP7A database sealing"):
            build_self_contained_database(
                owner=owner,
                tables=tables,
                database_leaf=leaf,
            )

    observed = tuple(
        row[0]
        for row in connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
    )
    assert observed == tuple(sorted(spec.table_name for spec in TABLE_SPECS))
    for spec in TABLE_SPECS:
        columns = connection.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns WHERE table_name = ? "
            "ORDER BY ordinal_position",
            [spec.table_name],
        ).fetchall()
        assert columns == [
            (
                column.name,
                {
                    "TIMESTAMPTZ": "TIMESTAMP WITH TIME ZONE",
                    "TIMESTAMP": "TIMESTAMP",
                }.get(column.duckdb_type, column.duckdb_type),
                "YES" if column.nullable else "NO",
            )
            for column in spec.columns
        ]
        assert connection.execute(
            f'SELECT count(*) FROM "{spec.table_name}"'  # noqa: S608 -- closed TABLE_SPECS identifier
        ).fetchone() == (0,)
    connection.close()


def test_database_materializer_bounds_wide_arrow_batches_across_tables_under_low_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb
    import pyarrow as pa  # type: ignore[import-untyped]

    from finproof.data.artifacts import database

    class Column:
        nullable = False

        def __init__(self, name: str, duckdb_type: str) -> None:
            self.name = name
            self.duckdb_type = duckdb_type

    class Spec:
        columns = (
            Column("id", "BIGINT"),
            *(Column(f"payload_{index}", "VARCHAR") for index in range(12)),
        )
        sort_key = ("id",)

        def __init__(self, table_name: str) -> None:
            self.table_name = table_name

    specs = tuple(Spec(f"wide_{index}") for index in range(3))
    monkeypatch.setattr(database, "TABLE_SPECS", specs)
    observed_batch_sizes: list[int] = []

    class Handle:
        def __init__(self, table_index: int) -> None:
            self._table_index = table_index

        @contextmanager
        def iter_batches(self, *, batch_size: int = 65_536) -> Iterator[Iterator[pa.RecordBatch]]:
            observed_batch_sizes.append(batch_size)

            def batches() -> Iterator[pa.RecordBatch]:
                table_rows = 8_192
                start = self._table_index * table_rows
                for offset in range(0, table_rows, batch_size):
                    row_count = min(batch_size, table_rows - offset)
                    values = range(start + offset, start + offset + row_count)
                    payload = [
                        hashlib.sha256(str(value).encode()).hexdigest() * 4 for value in values
                    ]
                    yield pa.record_batch(
                        [
                            pa.array(values, type=pa.int64()),
                            *(pa.array(payload) for _ in range(12)),
                        ],
                        names=("id", *(f"payload_{index}" for index in range(12))),
                    )

            yield batches()

    class Verification:
        def __init__(self, table_index: int) -> None:
            self.handle = Handle(table_index)

    class Tables:
        def verification_for(self, table_name: str) -> Verification:
            return Verification(int(table_name.rsplit("_", 1)[1]))

    connection = duckdb.connect(str(tmp_path / "bounded.duckdb"))
    try:
        connection.execute("SET memory_limit = '32MiB'")
        connection.execute("SET temp_directory = ?", [str(tmp_path / "spill")])
        database._materialize_tables(connection, cast(Any, Tables()))
        assert observed_batch_sizes == [256, 256, 256]
        assert tuple(
            connection.execute(
                f'SELECT count(*) FROM "{spec.table_name}"'  # noqa: S608 -- closed test specs
            ).fetchone()
            for spec in specs
        ) == ((8_192,), (8_192,), (8_192,))
    finally:
        connection.close()


def test_database_verifier_streams_expected_batches_under_low_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb

    from finproof.data.artifacts import database
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    snapshot = timestamp.date()

    def payload(index: int) -> str:
        return hashlib.sha256(str(index).encode()).hexdigest() * 128

    rows_by_table = {
        "bronze_source_column": tuple(
            {
                "catalog_version": "v1",
                "source_snapshot_date": snapshot,
                "source_table_order": 0,
                "source_table": "PRBD01N001",
                "source_column_number": index + 1,
                "source_column_letter": f"C{index + 1}",
                "source_column_name": f"field_{index:04d}",
                "source_declared_type": "string",
                "source_example": payload(index),
                "source_key_marker": "",
                "source_name_ko": "채권",
                "schema_file": "schema.xlsx",
                "schema_excel_row": index + 2,
            }
            for index in range(1_536)
        ),
    }
    root = tmp_path / "artifacts"
    manifest = write_database_artifact_tree(root, rows_by_table)
    real_connect = duckdb.connect

    class BoundedConnection:
        def __init__(self, path: str, *, read_only: bool) -> None:
            self._connection = real_connect(path, read_only=read_only)

        def execute(self, query: str, parameters: object = None) -> Any:
            if query == "SET memory_limit = '1GiB'":
                return self._connection.execute("SET memory_limit = '40MiB'")
            if query.startswith("SELECT current_setting('threads')"):
                self._connection.execute(query)

                class RuntimeSettings:
                    @staticmethod
                    def fetchone() -> tuple[int, str]:
                        return (1, "1.0 GiB")

                return RuntimeSettings()
            if parameters is None:
                return self._connection.execute(query)
            return self._connection.execute(query, parameters)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._connection, name)

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(
            cast(Any, database).duckdb,
            "connect",
            lambda path, *, read_only: BoundedConnection(path, read_only=read_only),
        )
        database.verify_database_against_parquet(
            inventory=inventory,
            database_entry=inventory.declared_entries[0],
            tables=tables,
            runtime_tmp_root=runtime,
        )
    assert tuple(runtime.iterdir()) == ()


def test_database_builder_orchestrates_cp4_seal_then_cp7_verified_wrapper(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.database import (
        StagedDatabaseVerification,
        build_self_contained_database,
    )

    with _empty_stage(tmp_path / "repository") as (owner, tables):
        leaf = owner.claim_database_leaf()
        result = build_self_contained_database(
            owner=owner,
            tables=tables,
            database_leaf=leaf,
        )
        assert type(result) is StagedDatabaseVerification
        assert result.persistence_timestamp is owner.persistence_timestamp
        assert result.physical_size_bytes > 0
        assert len(result.physical_sha256) == 64


def test_staged_database_verification_wraps_only_exact_owner_registered_seal(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.database import StagedDatabaseVerification

    with pytest.raises(TypeError, match="requires from_sealed"):
        StagedDatabaseVerification()
    with (
        _empty_stage(tmp_path / "repository") as (owner, _),
        pytest.raises(TypeError, match="exact sealed database"),
    ):
        StagedDatabaseVerification.from_sealed(
            owner=owner,
            sealed=object(),  # type: ignore[arg-type]
        )


def test_staged_database_verification_revalidates_owner_timestamp_identity_and_hash(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.database import build_self_contained_database

    with _empty_stage(tmp_path / "repository") as (owner, tables):
        result = build_self_contained_database(
            owner=owner,
            tables=tables,
            database_leaf=owner.claim_database_leaf(),
        )
        result.validate_against(owner)
        digest = result.physical_sha256
        object.__setattr__(result, "physical_sha256", "0" * 64)
        with pytest.raises(ValueError, match="database verification changed"):
            result.validate_against(owner)
        object.__setattr__(result, "physical_sha256", digest)


def test_staged_database_verification_rejects_foreign_equal_copy_object_new_and_token_forge(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.database import (
        StagedDatabaseVerification,
        build_self_contained_database,
    )

    with (
        _empty_stage(tmp_path / "first") as (owner, tables),
        _empty_stage(tmp_path / "second") as (foreign_owner, _),
    ):
        result = build_self_contained_database(
            owner=owner,
            tables=tables,
            database_leaf=owner.claim_database_leaf(),
        )
        with pytest.raises(ValueError, match="database verification changed"):
            result.validate_against(foreign_owner)
        with pytest.raises(TypeError, match="requires from_sealed"):
            copy.copy(result)
        blank = object.__new__(StagedDatabaseVerification)
        with pytest.raises(ValueError, match="database verification changed"):
            blank.validate_against(owner)
        forged = object.__new__(StagedDatabaseVerification)
        for name in result.__dataclass_fields__:
            object.__setattr__(forged, name, getattr(result, name))
        with pytest.raises(ValueError, match="database verification changed"):
            forged.validate_against(owner)
        token = result._owner_registration
        object.__setattr__(result, "_owner_registration", object())
        with pytest.raises(ValueError, match="database verification changed"):
            result.validate_against(owner)
        object.__setattr__(result, "_owner_registration", token)


def test_open_read_only_database_rejects_mutation_external_access_and_unsafe_paths(
    tmp_path: Path,
) -> None:
    import duckdb

    from finproof.data.artifacts.database import open_read_only_database

    path = tmp_path / "artifact.duckdb"
    writer = duckdb.connect(str(path))
    writer.execute("CREATE TABLE exact_rows(id BIGINT NOT NULL)")
    writer.execute("INSERT INTO exact_rows VALUES (1)")
    writer.close()
    connection = open_read_only_database(path)
    try:
        assert connection.execute("SELECT * FROM exact_rows").fetchall() == [(1,)]
        for sql in (
            "INSERT INTO exact_rows VALUES (2)",
            "UPDATE exact_rows SET id = 2",
            "DELETE FROM exact_rows",
            "CREATE TABLE forbidden(id BIGINT)",
            f"ATTACH '{tmp_path / 'other.duckdb'}' AS other",
            f"COPY exact_rows TO '{tmp_path / 'rows.csv'}'",
        ):
            with pytest.raises(duckdb.Error):
                connection.execute(sql)
    finally:
        connection.close()
    assert not (tmp_path / "other.duckdb").exists()
    assert not (tmp_path / "rows.csv").exists()
    with pytest.raises((OSError, ValueError)):
        open_read_only_database(tmp_path / "missing.duckdb")
    with pytest.raises((OSError, ValueError)):
        open_read_only_database(tmp_path)
    symlink = tmp_path / "database-link"
    symlink.symlink_to(path)
    with pytest.raises((OSError, ValueError)):
        open_read_only_database(symlink)


def test_candidate_finalizer_stage_writes_only_closed_report_and_manifest_leaves(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = artifact_staging_settings(tmp_path / "repository")
    identity = artifact_build_input_identity(settings)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=identity,
    ) as session:
        source = session._write_final_artifact(
            relative_path="reports/source_audit.json",
            payload=b"source\n",
        )
        quality = session._write_final_artifact(
            relative_path="reports/quality_summary.json",
            payload=b"quality\n",
        )
        manifest = session._write_final_artifact(
            relative_path="manifest.json",
            payload=b"manifest\n",
        )
        assert source[0] == len(b"source\n")
        assert quality[0] == len(b"quality\n")
        assert manifest[0] == len(b"manifest\n")
        assert all(len(result[1]) == 64 for result in (source, quality, manifest))
        with pytest.raises(ArtifactContractError):
            session._write_final_artifact(
                relative_path="reports/source_audit.json",
                payload=b"duplicate\n",
            )
        with pytest.raises(ArtifactContractError):
            session._write_final_artifact(
                relative_path="outside.json",  # type: ignore[arg-type]
                payload=b"outside\n",
            )


def test_final_leaf_write_fault_removes_only_exact_partial_leaf_and_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import staging
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = artifact_staging_settings(tmp_path / "repository")
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))

    def fail_write(_descriptor: int, _payload: object) -> int:
        raise OSError("disk full")

    def write_faulting_final_leaf() -> None:
        with ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            options,
            input_identity=artifact_build_input_identity(settings),
        ) as session:
            monkeypatch.setattr(cast(Any, staging).os, "write", fail_write)
            session._write_final_artifact(
                relative_path="reports/source_audit.json",
                payload=b"partial\n",
            )

    with pytest.raises(ArtifactContractError):
        write_faulting_final_leaf()
    monkeypatch.undo()
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        options,
        input_identity=artifact_build_input_identity(settings),
    ):
        pass
