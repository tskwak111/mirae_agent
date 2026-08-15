# mypy: disable-error-code="arg-type,assignment,attr-defined,import-untyped,misc,no-untyped-def,unused-ignore"
# ruff: noqa: ANN001, ANN002, ANN003, ANN204, ARG002, ARG005, B017, E501, PT011, PT012, PT018, RUF043, SIM117
"""Owned staged and final Parquet verification contracts."""

import copy
import inspect
import os
import stat
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from finproof.data.artifacts.parquet_io import ParquetBatchWriter
from finproof.data.artifacts.table_specs import table_spec
from tests.helpers.artifacts import (
    TestStageArtifactOwner,
    write_empty_parquet_artifact_tree,
)
from tests.unit.data.artifacts.test_parquet_io import _column_row


def _written(tmp_path: Path):
    owner = TestStageArtifactOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf("bronze_source_column")
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    writer.write_batch((_column_row(1), _column_row(2)))
    writer.close()
    return owner, leaf


def _empty_staged_verifications(owner: TestStageArtifactOwner):
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    values = []
    for spec in TABLE_SPECS:
        leaf = owner.claim_parquet_leaf(spec.table_name)
        ParquetBatchWriter(spec, leaf).close()
        values.append(verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec))
    return tuple(values)


def _trusted_workspace_parent(path: Path):
    from finproof.data.artifacts.parquet_io import _TrustedWorkspaceParent

    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        return _TrustedWorkspaceParent._from_open_descriptor(descriptor)
    finally:
        os.close(descriptor)


def test_staged_reopen_keeps_stream_and_parquetfile_inside_owned_context(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    verification = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    assert verification.logical.row_count == 2
    with verification.handle.iter_batches(batch_size=1) as batches:
        assert sum(batch.num_rows for batch in batches) == 2
    with __import__("pytest").raises(ValueError, match="batch_size"):
        with verification.handle.iter_batches(batch_size=0):
            pass


@pytest.mark.parametrize("case", ["wrong-schema", "schema-metadata", "oversized-row-group"])
def test_staged_reopen_checks_exact_schema_metadata_row_groups_and_count(
    tmp_path: Path, case: str
) -> None:
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    from finproof.data.artifacts.parquet_io import _arrow_schema, verify_staged_parquet_table

    owner = TestStageArtifactOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf("bronze_source_column")
    spec = table_spec("bronze_source_column")
    if case == "wrong-schema":
        table = pa.table({"wrong": [1]})
    else:
        schema = _arrow_schema(spec)
        if case == "schema-metadata":
            schema = schema.with_metadata({b"forged": b"1"})
        count = 65_537 if case == "oversized-row-group" else 1
        table = pa.Table.from_pylist(
            [_column_row(index % 26 + 1) for index in range(count)], schema=schema
        )
    with leaf.create_exclusive() as sink:
        pq.write_table(table, sink, row_group_size=65_537)

    with pytest.raises(ValueError, match="schema|row group"):
        verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)


@pytest.mark.parametrize(
    "case", ["string", "int64", "date", "local-timestamp", "utc-timestamp", "decimal", "bool"]
)
def test_reopened_rows_enforce_every_exact_physical_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:

    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.serialization import (
        serialize_bronze_source_row,
        serialize_table_row,
    )
    from tests.helpers.source_rows import source_row
    from tests.unit.data.artifacts.test_serialization import _bond_record, _domestic_record

    if case in {"string", "int64", "date"}:
        spec = table_spec("bronze_source_column")
        row = _column_row(1)
        field, invalid = {
            "string": ("catalog_version", 1),
            "int64": ("source_table_order", True),
            "date": ("source_snapshot_date", datetime(2026, 7, 11)),
        }[case]
    elif case in {"local-timestamp", "bool"}:
        if case == "local-timestamp":
            spec = table_spec("silver_domestic_listed_product")
            row = dict(serialize_table_row(spec, _domestic_record()))
            field, invalid = "daily_update_at", datetime(2026, 7, 11, tzinfo=UTC)
        else:
            spec = table_spec("silver_bond_instrument")
            row = dict(serialize_table_row(spec, _bond_record()))
            field, invalid = "is_matured_at_as_of", 1
    elif case == "utc-timestamp":
        spec = table_spec("bronze_source_row")
        row = dict(
            serialize_bronze_source_row(
                spec,
                source_row("PRBD01N001"),
                persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
            )
        )
        field, invalid = "loaded_at", datetime(2026, 8, 15)
    else:
        spec = table_spec("silver_bond_instrument")
        row = dict(serialize_table_row(spec, _bond_record()))
        field, invalid = "coupon_rate", "1.23"

    owner = TestStageArtifactOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf(spec.table_name)
    writer = ParquetBatchWriter(spec, leaf)
    writer.write_batch((row,))
    writer.close()
    forged = {**row, field: invalid}
    original = parquet_io.pq.ParquetFile

    class FakeBatch:
        def to_pylist(self):
            return [forged]

    class ForgedParquetFile:
        def __init__(self, stream):
            self._inner = original(stream)
            self.schema_arrow = self._inner.schema_arrow
            self.metadata = self._inner.metadata

        def iter_batches(self, **kwargs):
            del kwargs
            return iter((FakeBatch(),))

    monkeypatch.setattr(parquet_io.pq, "ParquetFile", ForgedParquetFile)
    with pytest.raises(ValueError, match="physical|timestamp|Decimal"):
        parquet_io.verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)


def test_staged_reopen_hashes_known_count_header_before_bounded_rows(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.hashing import table_logical_hash
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    spec = table_spec("bronze_source_column")
    verified = verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
    expected = table_logical_hash(spec, row_count=2, rows=(_column_row(1), _column_row(2)))
    assert verified.logical.logical_hash == expected


def test_staged_reopen_checks_canonical_sort_with_previous_key_only(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner = TestStageArtifactOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf("bronze_source_column")
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    writer.write_batch((_column_row(2),))
    writer.write_batch((_column_row(1),))
    writer.close()
    with pytest.raises(ValueError, match="sort order"):
        verify_staged_parquet_table(owner=owner, leaf=leaf, spec=table_spec("bronze_source_column"))


def test_bounded_unique_index_rejects_nonadjacent_duplicate_beyond_two_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io

    spec = table_spec("bronze_source_column")
    first = _column_row(1)
    middle = tuple(_column_row(number) for number in range(2, 7))
    duplicate = {**_column_row(1), "source_table_order": 1}
    owner = TestStageArtifactOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf(spec.table_name)
    writer = ParquetBatchWriter(spec, leaf)
    writer.write_batch((first, *middle, duplicate))
    writer.close()
    monkeypatch.setattr(
        parquet_io,
        "_FOCUSED_TEST_LIMITS",
        parquet_io.ParquetVerificationLimits(batch_rows=2, memory_limit_bytes=1 << 20),
    )
    with pytest.raises(ValueError, match="duplicate unique key"):
        parquet_io.verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)


def test_quality_issue_unique_index_rejects_same_issue_id_at_nonadjacent_sorted_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
    from tests.helpers.source_rows import source_row

    spec = table_spec("silver_quality_issue")
    issues = []
    for excel_row in range(2, 9):
        pure = DataQualityIssue.from_row(
            source_row("PREF01N001", excel_row=excel_row),
            "pd_itm_no",
            rule_id="test.rule",
            rule_version="1.0.0",
            severity=IssueSeverity.WARNING,
            quality_status=QualityStatus.INVALID_FORMAT,
            reason="test",
            quarantined=True,
        )
        issues.append(
            DataQualityIssue.model_validate(
                {
                    **pure.model_dump(mode="python"),
                    "first_detected_at": datetime(2026, 8, 15, tzinfo=UTC),
                },
                strict=True,
            )
        )
    issues[-1] = issues[-1].model_copy(update={"issue_id": issues[0].issue_id})
    rows = tuple(dict(serialize_table_row(spec, issue)) for issue in issues)
    owner = TestStageArtifactOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf(spec.table_name)
    writer = ParquetBatchWriter(spec, leaf)
    writer.write_batch(rows)
    writer.close()
    monkeypatch.setattr(
        parquet_io,
        "_FOCUSED_TEST_LIMITS",
        parquet_io.ParquetVerificationLimits(batch_rows=2, memory_limit_bytes=1 << 20),
    )
    with pytest.raises(ValueError, match="duplicate unique key"):
        parquet_io.verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)


def test_staged_unique_index_is_managed_pathless_spillable_and_exact_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    from finproof.data.artifacts import parquet_io
    from tests.helpers.artifacts import TestUniqueKeyIndex

    owner, leaf = _written(tmp_path)

    class SpyIndex(TestUniqueKeyIndex):
        def __init__(self) -> None:
            super().__init__()
            self.batch_sizes: list[int] = []

        def insert_canonical_batch(self, keys: tuple[bytes, ...]) -> None:
            self.batch_sizes.append(len(keys))
            super().insert_canonical_batch(keys)

    class SpyWorkspace:
        def __init__(self) -> None:
            self.assertions = 0
            self.index = SpyIndex()

        @contextmanager
        def create_unique_key_index(self, *, limits):
            assert limits.memory_limit_bytes == 1 << 20
            yield self.index

        def assert_unchanged(self) -> None:
            self.assertions += 1

    workspace = SpyWorkspace()

    @contextmanager
    def opened_workspace():
        yield workspace

    leaf.create_verification_workspace = opened_workspace
    monkeypatch.setattr(
        parquet_io,
        "_FOCUSED_TEST_LIMITS",
        parquet_io.ParquetVerificationLimits(batch_rows=1, memory_limit_bytes=1 << 20),
    )
    parquet_io.verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    assert workspace.assertions == 2
    assert workspace.index.batch_sizes == [1, 1]
    assert not tuple(tmp_path.glob("unique-*"))


def test_final_unique_index_is_managed_pathless_spillable_and_exact_owned(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        ParquetVerificationLimits,
        _final_verification_workspace,
    )

    roots: list[Path] = []
    with _final_verification_workspace(
        trusted_parent=_trusted_workspace_parent(tmp_path)
    ) as workspace:
        roots.append(workspace._root)
        with workspace.create_unique_key_index(limits=ParquetVerificationLimits()) as index:
            index.insert_canonical_batch((b"one", b"two"))
            index.assert_unique()
        assert not (workspace._root / "keys.duckdb").exists()
        workspace.assert_unchanged()
    assert not roots[0].exists()


@pytest.mark.parametrize(
    "statement",
    [
        "SET enable_external_access = false",
        "SET allow_unsigned_extensions = false",
        "SET autoinstall_known_extensions = false",
        "SET autoload_known_extensions = false",
    ],
)
def test_unique_workspace_disables_external_access_install_and_autoload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, statement: str
) -> None:
    from finproof.data.artifacts import parquet_io

    observed: list[str] = []

    class Connection:
        def execute(self, sql: str, parameters=None):
            del parameters
            observed.append(sql)
            return self

        def executemany(self, sql: str, parameters) -> None:
            del sql
            tuple(parameters)

        def fetchone(self):
            return None

        def close(self) -> None:
            pass

    monkeypatch.setattr(parquet_io.duckdb, "connect", lambda target: Connection())
    with parquet_io._final_verification_workspace(
        trusted_parent=_trusted_workspace_parent(tmp_path)
    ) as workspace:
        with workspace.create_unique_key_index(
            limits=parquet_io.ParquetVerificationLimits()
        ) as index:
            index.insert_canonical_batch((b"one",))
            index.assert_unique()
    assert statement in observed


def test_unique_workspace_preserves_external_symlink_victim_bytes_and_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io

    victim = tmp_path / "external-victim.duckdb"
    victim.write_bytes(b"external-victim")
    victim.chmod(0o640)
    original_bytes = victim.read_bytes()
    original_mode = victim.stat().st_mode
    connected = False
    yielded = False
    retained: list[str] = []

    original_connect = parquet_io.duckdb.connect

    def spy_connect(target: str):
        nonlocal connected
        connected = True
        return original_connect(target)

    monkeypatch.setattr(parquet_io.duckdb, "connect", spy_connect)
    with pytest.raises(Exception):
        with parquet_io._final_verification_workspace(
            trusted_parent=_trusted_workspace_parent(tmp_path)
        ) as workspace:
            retained.append(workspace._root_name)
            os.symlink(os.fspath(victim), "keys.duckdb", dir_fd=workspace._root_fd)
            with workspace.create_unique_key_index(limits=parquet_io.ParquetVerificationLimits()):
                yielded = True
    assert connected is False
    assert yielded is False
    assert victim.read_bytes() == original_bytes
    assert victim.stat().st_mode == original_mode
    assert (tmp_path / retained[0]).is_dir()


@pytest.mark.parametrize(
    "case",
    [
        "root-mode",
        "marker-mode",
        "spill-mode",
        "marker-bytes",
        "root-aba",
        "marker-aba",
        "spill-aba",
    ],
)
def test_unique_workspace_revalidates_exact_modes_marker_bytes_and_every_identity(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts import parquet_io

    with pytest.raises(parquet_io.ArtifactContractError):
        with parquet_io._final_verification_workspace(
            trusted_parent=_trusted_workspace_parent(tmp_path)
        ) as workspace:
            if case == "root-mode":
                os.fchmod(workspace._root_fd, 0o755)
            elif case == "marker-mode":
                marker = os.open(workspace._MARKER_NAME, os.O_RDONLY, dir_fd=workspace._root_fd)
                try:
                    os.fchmod(marker, 0o644)
                finally:
                    os.close(marker)
            elif case == "spill-mode":
                os.fchmod(workspace._spill_fd, 0o755)
            elif case == "marker-bytes":
                marker = os.open(workspace._MARKER_NAME, os.O_WRONLY, dir_fd=workspace._root_fd)
                try:
                    os.ftruncate(marker, 0)
                    os.write(marker, b"forged-marker-same-inode\n")
                finally:
                    os.close(marker)
            elif case == "root-aba":
                os.rename(
                    workspace._root_name,
                    "displaced-root",
                    src_dir_fd=workspace._parent_fd,
                    dst_dir_fd=workspace._parent_fd,
                )
                os.mkdir(workspace._root_name, mode=0o700, dir_fd=workspace._parent_fd)
            elif case == "marker-aba":
                os.unlink(workspace._MARKER_NAME, dir_fd=workspace._root_fd)
                marker = os.open(
                    workspace._MARKER_NAME,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=workspace._root_fd,
                )
                try:
                    os.write(marker, workspace._MARKER_BYTES)
                finally:
                    os.close(marker)
            else:
                os.rmdir(workspace._SPILL_NAME, dir_fd=workspace._root_fd)
                os.mkdir(workspace._SPILL_NAME, mode=0o700, dir_fd=workspace._root_fd)
            workspace.assert_unchanged()


def test_unique_workspace_closes_before_cleanup_and_rejects_aba_or_ambiguity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io

    events: list[str] = []

    class Connection:
        def execute(self, sql: str, parameters=None):
            if sql == "SET temp_directory = ?":
                descriptor = os.open(
                    "owned-spill.tmp",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=workspace._spill_fd,
                )
                try:
                    os.write(descriptor, b"spill")
                finally:
                    os.close(descriptor)
            return self

        def executemany(self, sql: str, parameters) -> None:
            del sql
            tuple(parameters)

        def fetchone(self):
            return None

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(parquet_io.duckdb, "connect", lambda target: Connection())
    roots: list[str] = []
    with parquet_io._final_verification_workspace(
        trusted_parent=_trusted_workspace_parent(tmp_path)
    ) as workspace:
        roots.append(workspace._root_name)
        with workspace.create_unique_key_index(
            limits=parquet_io.ParquetVerificationLimits()
        ) as index:
            index.insert_canonical_batch((b"one",))
            index.assert_unique()
        assert events == ["close"]
        assert stat.S_ISREG(os.stat("owned-spill.tmp", dir_fd=workspace._spill_fd).st_mode)
    assert events == ["close"]
    assert not (tmp_path / roots[0]).exists()


@pytest.mark.parametrize(
    "case", ["temp-root", "spill-setup", "marker-setup", "connect", "configure", "close"]
)
def test_unique_workspace_setup_and_close_failures_are_typed_and_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from finproof.data.artifacts import parquet_io

    roots: list[str] = []
    original_mkdir = parquet_io.os.mkdir
    if case == "temp-root":

        def fail_root(path, *args, **kwargs):
            if isinstance(path, str) and path.startswith("finproof-parquet-verify-"):
                raise OSError("injected temp-root failure")
            return original_mkdir(path, *args, **kwargs)

        monkeypatch.setattr(parquet_io.os, "mkdir", fail_root)
    if case == "spill-setup":

        def fail_spill(path, *args, **kwargs):
            if path == "spill":
                raise OSError("injected spill failure")
            return original_mkdir(path, *args, **kwargs)

        monkeypatch.setattr(parquet_io.os, "mkdir", fail_spill)
    if case == "marker-setup":
        original_open = parquet_io.os.open

        def fail_marker(path, *args, **kwargs):
            if path == ".finproof-parquet-verification":
                raise OSError("injected marker failure")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(parquet_io.os, "open", fail_marker)

    close_calls = 0

    class Connection:
        def execute(self, sql: str, parameters=None):
            del parameters
            if case == "configure" and sql == "SET memory_limit = '1GiB'":
                raise OSError("injected configuration failure")
            return self

        def close(self) -> None:
            nonlocal close_calls
            close_calls += 1
            if case == "close":
                raise OSError("injected close failure")

    def connect(target: str):
        del target
        if case == "connect":
            raise OSError("injected connect failure")
        return Connection()

    monkeypatch.setattr(parquet_io.duckdb, "connect", connect)
    with pytest.raises(parquet_io.ArtifactContractError):
        with parquet_io._final_verification_workspace(
            trusted_parent=_trusted_workspace_parent(tmp_path)
        ) as workspace:
            roots.append(workspace._root_name)
            with workspace.create_unique_key_index(limits=parquet_io.ParquetVerificationLimits()):
                pass
    if case == "configure":
        assert close_calls == 1
    if case == "close":
        assert (tmp_path / roots[0]).is_dir()


def test_common_checker_rejects_noncanonical_record_json(tmp_path: Path) -> None:
    import json

    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table
    from finproof.data.artifacts.serialization import serialize_table_row
    from tests.unit.data.artifacts.test_serialization import _bond_record

    spec = table_spec("silver_bond_instrument")
    row = dict(serialize_table_row(spec, _bond_record()))
    row["record_json"] = json.dumps(json.loads(row["record_json"]), ensure_ascii=False)
    owner = TestStageArtifactOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf(spec.table_name)
    writer = ParquetBatchWriter(spec, leaf)
    writer.write_batch((row,))
    writer.close()
    with pytest.raises(ValueError, match="record_json"):
        verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)


@pytest.mark.parametrize("boundary", ["writer", "verifier"])
def test_writer_and_verifier_reject_mutated_registered_spec_fingerprint(
    tmp_path: Path, boundary: str
) -> None:
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    spec = table_spec("bronze_source_column")
    owner: TestStageArtifactOwner | None = None
    leaf = None
    if boundary == "verifier":
        owner, leaf = _written(tmp_path)
    original = spec.columns[0].arrow_type
    try:
        object.__setattr__(spec.columns[0], "arrow_type", "forged")
        with pytest.raises(ValueError, match="registered|fingerprint"):
            if boundary == "writer":
                ParquetBatchWriter(spec, _LeafForTypingOnly())
            else:
                assert owner is not None and leaf is not None
                verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
    finally:
        object.__setattr__(spec.columns[0], "arrow_type", original)


class _LeafForTypingOnly:
    table_name = "bronze_source_column"
    relative_path = __import__("pathlib").PurePosixPath("parquet/bronze_source_column.parquet")


def test_staged_reopen_detects_logical_mutation_but_ignores_physical_reencoding(
    tmp_path: Path,
) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    from finproof.data.artifacts.parquet_io import _arrow_schema, verify_staged_parquet_table

    spec = table_spec("bronze_source_column")
    hashes: list[str] = []
    rows_by_case = (
        (_column_row(1), _column_row(2)),
        (_column_row(1), _column_row(2)),
        (_column_row(1), {**_column_row(2), "source_example": "changed"}),
    )
    for index, rows in enumerate(rows_by_case):
        root = tmp_path / str(index)
        root.mkdir()
        owner = TestStageArtifactOwner(root, datetime(2026, 8, 15, tzinfo=UTC))
        leaf = owner.claim_parquet_leaf(spec.table_name)
        if index == 1:
            with leaf.create_exclusive() as sink:
                pq.write_table(
                    pa.Table.from_pylist(list(rows), schema=_arrow_schema(spec)),
                    sink,
                    compression="snappy",
                )
        else:
            writer = ParquetBatchWriter(spec, leaf)
            writer.write_batch(rows)
            writer.close()
        hashes.append(
            verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec).logical.logical_hash
        )
    assert hashes[0] == hashes[1]
    assert hashes[0] != hashes[2]


def test_staged_verification_rejects_unissued_facts_and_forged_registration_token(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetHandle,
        StagedParquetVerification,
        verify_staged_parquet_table,
    )

    with pytest.raises(TypeError, match="issued only"):
        StagedParquetVerification()
    with pytest.raises(TypeError, match="issued only"):
        StagedParquetHandle()
    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    object.__setattr__(verified.handle, "_owner_registration_token", object())
    with (
        pytest.raises(ValueError, match="unregistered staged handle"),
        verified.handle.iter_batches() as batches,
    ):
        next(batches)


def test_staged_verification_atomically_registers_exact_verification_and_handle_objects(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetHandle,
        StagedParquetVerification,
        verify_staged_parquet_table,
    )

    class NonRegisteringOwner(TestStageArtifactOwner):
        def _register_staged_verification(
            self,
            value: StagedParquetVerification,
            handle: StagedParquetHandle,
        ) -> object:
            return object()

    owner = NonRegisteringOwner(tmp_path, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf("bronze_source_column")
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    writer.write_batch((_column_row(1),))
    writer.close()

    with pytest.raises(ValueError, match="unregistered staged verification"):
        verify_staged_parquet_table(owner=owner, leaf=leaf, spec=table_spec("bronze_source_column"))


@pytest.mark.parametrize("case", ["copy", "object-new"])
def test_staged_verification_rejects_copied_equal_and_object_new_forge(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetVerification,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    if case == "copy":
        forged = copy.copy(verified)
        assert forged == verified and forged is not verified
    else:
        forged = object.__new__(StagedParquetVerification)
        for name in (
            "_owner",
            "_leaf",
            "_spec",
            "_relative_path",
            "_leaf_identity",
            "_owner_registration_token",
            "logical",
            "physical_size_bytes",
            "physical_sha256",
            "handle",
        ):
            object.__setattr__(forged, name, getattr(verified, name))
        assert forged == verified and forged is not verified

    with pytest.raises(ValueError, match="unregistered staged verification"):
        forged.require_registered()


@pytest.mark.parametrize("case", ["copy", "foreign-owner", "closed-owner", "leaf-substitution"])
def test_staged_handle_rejects_foreign_copy_closed_owner_and_leaf_substitution(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    candidate = copy.copy(verified.handle)
    if case != "copy":
        candidate = verified.handle
    if case == "foreign-owner":
        foreign = TestStageArtifactOwner(tmp_path / "foreign", datetime(2026, 8, 15, tzinfo=UTC))
        object.__setattr__(candidate, "_owner", foreign)
    elif case == "closed-owner":
        owner.close()
    elif case == "leaf-substitution":
        object.__setattr__(
            candidate,
            "_leaf",
            owner.claim_parquet_leaf("bronze_source_column"),
        )

    with pytest.raises(ValueError, match="unregistered|foreign|closed|changed"):
        candidate.require_registered()


@pytest.mark.parametrize(
    "case",
    [
        "handle-size",
        "handle-sha",
        "handle-row-count",
        "verification-size",
        "verification-sha",
        "verification-logical",
        "registration-token",
    ],
)
def test_staged_handle_freezes_physical_facts_and_owner_registration(
    tmp_path: Path, case: str
) -> None:
    import hashlib

    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    payload = leaf._path().read_bytes()
    expected_sha = hashlib.sha256(payload).hexdigest()
    assert verified.physical_size_bytes == len(payload)
    assert verified.physical_sha256 == expected_sha
    assert verified.handle.physical_size_bytes == len(payload)
    assert verified.handle.physical_sha256 == expected_sha

    target = verified.handle if case.startswith("handle-") else verified
    field = {
        "handle-size": "physical_size_bytes",
        "handle-sha": "physical_sha256",
        "handle-row-count": "row_count",
        "verification-size": "physical_size_bytes",
        "verification-sha": "physical_sha256",
        "verification-logical": "logical",
        "registration-token": "_owner_registration_token",
    }[case]
    original = getattr(target, field)
    replacement = (
        object()
        if case in {"verification-logical", "registration-token"}
        else ("0" * 64 if field == "physical_sha256" else original + 1)
    )
    object.__setattr__(target, field, replacement)

    with pytest.raises(ValueError, match="unregistered"):
        if target is verified.handle:
            verified.handle.require_registered()
        else:
            verified.require_registered()


def test_staged_handle_detects_same_inode_same_size_mutation_during_read(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    path = leaf._path()
    original_size = path.stat().st_size

    with pytest.raises(ValueError, match="changed during iteration"):
        with verified.handle.iter_batches(batch_size=1) as batches:
            assert next(batches).num_rows == 1
            with path.open("r+b") as stream:
                stream.seek(4)
                original = stream.read(1)
                stream.seek(4)
                stream.write(bytes((original[0] ^ 1,)))
    assert path.stat().st_size == original_size


def test_staged_handle_detects_same_inode_same_size_mutation_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    with verified.handle.iter_batches() as batches:
        assert sum(batch.num_rows for batch in batches) == 2

    path = leaf._path()
    original_size = path.stat().st_size
    with path.open("r+b") as stream:
        stream.seek(4)
        original = stream.read(1)
        stream.seek(4)
        stream.write(bytes((original[0] ^ 1,)))
    assert path.stat().st_size == original_size

    def reject_open(*args: object, **kwargs: object) -> object:
        raise AssertionError("ParquetFile opened before physical identity validation")

    monkeypatch.setattr(parquet_io.pq, "ParquetFile", reject_open)
    with pytest.raises(ValueError, match="physical identity changed"):
        with verified.handle.iter_batches():
            pass


def test_staged_set_skeleton_rejects_valid_verified_fixture(tmp_path: Path) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    with pytest.raises(TypeError, match="factory"):
        StagedParquetSet()
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(verified,))
    assert staged.verification_for("bronze_source_column") is verified
    staged.require_tables(("bronze_source_column",))


def test_staged_set_factory_binds_owner_timestamp_and_exact_verifications(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(verified,))

    assert staged.verifications == (verified,)
    assert staged.verifications[0] is verified
    assert staged.handles == (verified.handle,)
    assert staged.handles[0] is verified.handle
    assert staged.persistence_timestamp is owner.persistence_timestamp
    owner._require_registered_staged_set(staged, staged._registration_token)


@pytest.mark.parametrize(
    "timestamp",
    [
        pytest.param(datetime(2026, 8, 15), id="naive"),
        pytest.param(
            datetime(2026, 8, 15, tzinfo=timezone(timedelta(hours=9))),
            id="nonzero-offset",
        ),
        pytest.param("2026-08-15T00:00:00Z", id="string"),
        pytest.param(0, id="non-datetime"),
    ],
)
def test_staged_set_rejects_naive_nonzero_offset_and_non_datetime_timestamp(
    tmp_path: Path, timestamp: object
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner = TestStageArtifactOwner(tmp_path, timestamp)  # type: ignore[arg-type]
    leaf = owner.claim_parquet_leaf("bronze_source_column")
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    writer.write_batch((_column_row(1),))
    writer.close()
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )

    with pytest.raises(ValueError, match="persistence timestamp"):
        StagedParquetSet.from_verified(owner=owner, verifications=(verified,))


def test_staged_set_extension_supersedes_predecessor_and_preserves_frozen_order(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, first_leaf = _written(tmp_path)
    first = verify_staged_parquet_table(
        owner=owner,
        leaf=first_leaf,
        spec=table_spec("bronze_source_column"),
    )
    second_leaf = owner.claim_parquet_leaf("bronze_source_row")
    ParquetBatchWriter(table_spec("bronze_source_row"), second_leaf).close()
    second = verify_staged_parquet_table(
        owner=owner, leaf=second_leaf, spec=table_spec("bronze_source_row")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(first,))

    extended = staged.extend_verified(owner=owner, verifications=(second,))

    assert extended.verifications == (first, second)
    assert extended.verifications[0] is first
    assert extended.verifications[1] is second
    assert extended.handles == (first.handle, second.handle)
    assert extended.persistence_timestamp is staged.persistence_timestamp
    with pytest.raises(ValueError, match="superseded|unregistered"):
        owner._require_registered_staged_set(staged, staged._registration_token)
    owner._require_registered_staged_set(extended, extended._registration_token)


def test_staged_set_exposes_only_exact_extend_verified_and_require_complete_signatures() -> None:
    from finproof.data.artifacts.parquet_io import (
        OwnedStageArtifactOwner,
        StagedParquetSet,
        StagedParquetVerification,
    )

    assert "extend" not in StagedParquetSet.__dict__
    assert inspect.signature(StagedParquetSet.extend_verified) == inspect.Signature(
        parameters=(
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter(
                "owner", inspect.Parameter.KEYWORD_ONLY, annotation=OwnedStageArtifactOwner
            ),
            inspect.Parameter(
                "verifications",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=tuple[StagedParquetVerification, ...],
            ),
        ),
        return_annotation="StagedParquetSet",
    )
    assert inspect.signature(StagedParquetSet.require_complete) == inspect.Signature(
        parameters=(inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),),
        return_annotation=None,
    )


def test_extend_verified_requires_explicit_owner_tuple_and_accepts_distinct_value_equal_utc(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, first_leaf = _written(tmp_path)
    first = verify_staged_parquet_table(
        owner=owner, leaf=first_leaf, spec=table_spec("bronze_source_column")
    )
    second_leaf = owner.claim_parquet_leaf("bronze_source_row")
    ParquetBatchWriter(table_spec("bronze_source_row"), second_leaf).close()
    second = verify_staged_parquet_table(
        owner=owner, leaf=second_leaf, spec=table_spec("bronze_source_row")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(first,))
    equal_timestamp = datetime.fromisoformat(staged.persistence_timestamp.isoformat())
    assert equal_timestamp == owner.persistence_timestamp
    assert equal_timestamp is not owner.persistence_timestamp
    object.__setattr__(staged, "persistence_timestamp", equal_timestamp)

    with pytest.raises(TypeError):
        staged.extend_verified(verifications=(second,))  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="tuple"):
        staged.extend_verified(owner=owner, verifications=second)  # type: ignore[arg-type]

    extended = staged.extend_verified(owner=owner, verifications=(second,))

    assert extended.verifications == (first, second)
    assert extended.persistence_timestamp == owner.persistence_timestamp
    owner._require_registered_staged_set(extended, extended._registration_token)


@pytest.mark.parametrize("fault", ["validation", "owner-registration"])
def test_extend_verified_supersession_is_atomic_on_validation_and_owner_registration_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, first_leaf = _written(tmp_path)
    first = verify_staged_parquet_table(
        owner=owner, leaf=first_leaf, spec=table_spec("bronze_source_column")
    )
    second_leaf = owner.claim_parquet_leaf("bronze_source_row")
    ParquetBatchWriter(table_spec("bronze_source_row"), second_leaf).close()
    second = verify_staged_parquet_table(
        owner=owner, leaf=second_leaf, spec=table_spec("bronze_source_row")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(first,))

    if fault == "validation":
        supplied = [second]
    else:
        supplied = (second,)

        def fail_register(value: object) -> object:
            raise OSError("injected owner registration failure")

        monkeypatch.setattr(owner, "_register_staged_set", fail_register)

    with pytest.raises((ValueError, OSError)):
        staged.extend_verified(owner=owner, verifications=supplied)  # type: ignore[arg-type]

    owner._require_registered_staged_set(staged, staged._registration_token)


@pytest.mark.parametrize("case", ["partial", "reordered", "duplicate", "complete"])
def test_require_complete_accepts_only_exact_eleven_registered_tables_in_frozen_order(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import StagedParquetSet

    owner = TestStageArtifactOwner(tmp_path / case, datetime(2026, 8, 15, tzinfo=UTC))
    verifications = _empty_staged_verifications(owner)
    supplied = verifications[:-1] if case == "partial" else verifications
    staged = StagedParquetSet.from_verified(owner=owner, verifications=supplied)
    if case == "reordered":
        changed = (verifications[1], verifications[0], *verifications[2:])
        object.__setattr__(staged, "verifications", changed)
        object.__setattr__(staged, "handles", tuple(item.handle for item in changed))
    elif case == "duplicate":
        changed = (verifications[0], verifications[0], *verifications[2:])
        object.__setattr__(staged, "verifications", changed)
        object.__setattr__(staged, "handles", tuple(item.handle for item in changed))

    if case == "complete":
        staged.require_complete()
    else:
        with pytest.raises(ValueError, match="complete|order|duplicate"):
            staged.require_complete()


@pytest.mark.parametrize(
    "case",
    [
        "handle-leaf",
        "verification-leaf",
        "handle-relative-path",
        "verification-relative-path",
        "handle-identity",
        "verification-identity",
    ],
)
def test_staged_handle_and_verification_retain_exact_frozen_leaf_identity(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    verification = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    handle = verification.handle
    with leaf.open_verified() as stream:
        observed = os.fstat(stream.fileno())
    expected_identity = (
        observed.st_dev,
        observed.st_ino,
        stat.S_IFMT(observed.st_mode),
        stat.S_IMODE(observed.st_mode),
        observed.st_nlink,
    )
    assert handle._leaf is leaf
    assert verification._leaf is leaf
    assert handle._relative_path == leaf.relative_path
    assert verification._relative_path == leaf.relative_path
    assert handle._leaf_identity == expected_identity
    assert verification._leaf_identity == expected_identity

    target = verification if case.startswith("verification") else handle
    if case.endswith("leaf"):
        attribute, changed = "_leaf", object()
    elif case.endswith("relative-path"):
        attribute, changed = "_relative_path", Path("forged.parquet")
    else:
        attribute, changed = "_leaf_identity", (0, 0, 0, 0, 0)
    object.__setattr__(target, attribute, changed)
    with pytest.raises(ValueError, match="unregistered|foreign stage leaf"):
        target.require_registered()


@pytest.mark.parametrize("case", ["every-call", "same-inode-byte-mutation"])
def test_verification_for_reopens_and_rechecks_exact_bytes_and_leaf_identity_on_every_call(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verification = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(verification,))
    opens = 0
    original_open = leaf.open_verified

    class TrackedOpen:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            nonlocal opens
            opens += 1
            return self._inner.__enter__()

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

    leaf.open_verified = lambda: TrackedOpen(original_open())  # type: ignore[no-untyped-call]
    if case == "every-call":
        assert staged.verification_for("bronze_source_column") is verification
        assert staged.verification_for("bronze_source_column") is verification
        assert opens == 2
    else:
        path = leaf._path()
        with path.open("r+b") as stream:
            stream.seek(8)
            original = stream.read(1)
            stream.seek(8)
            stream.write(bytes((original[0] ^ 1,)))
        with pytest.raises(ValueError, match="physical identity"):
            staged.verification_for("bronze_source_column")
        assert opens == 1


@pytest.mark.parametrize(
    "case",
    [
        "consumer-before-first",
        "consumer-between-batches",
        "consumer-after-final",
        "post-digest-fault",
        "post-rescan-fault",
        "context-exit-fault",
    ],
)
def test_staged_consumers_run_post_read_checks_and_context_exit_in_finally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    owner, leaf = _written(tmp_path)
    verification = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    handle = verification.handle
    original_open = leaf.open_verified
    original_digest = parquet_io._physical_digest
    original_require = owner.require_owned_parquet_leaf
    exit_calls = 0
    digest_calls = 0
    owner_rescans = 0

    class TrackedOpen:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            return self._inner.__enter__()

        def __exit__(self, *args):
            nonlocal exit_calls
            exit_calls += 1
            result = self._inner.__exit__(*args)
            if case == "context-exit-fault":
                raise OSError("injected context exit failure")
            return result

    def tracked_digest(stream):
        nonlocal digest_calls
        digest_calls += 1
        if case == "post-digest-fault" and digest_calls == 2:
            raise OSError("injected post-digest failure")
        return original_digest(stream)

    def tracked_require(candidate):
        nonlocal owner_rescans
        owner_rescans += 1
        if case == "post-rescan-fault" and owner_rescans == 2:
            raise OSError("injected owner rescan failure")
        return original_require(candidate)

    leaf.open_verified = lambda: TrackedOpen(original_open())  # type: ignore[no-untyped-call]
    monkeypatch.setattr(parquet_io, "_physical_digest", tracked_digest)
    monkeypatch.setattr(owner, "require_owned_parquet_leaf", tracked_require)

    if case.startswith("consumer-"):
        with pytest.raises(RuntimeError, match="consumer stopped"):
            with handle.iter_batches(batch_size=1) as batches:
                if case == "consumer-before-first":
                    raise RuntimeError("consumer stopped")
                if case == "consumer-between-batches":
                    next(batches)
                    raise RuntimeError("consumer stopped")
                tuple(batches)
                raise RuntimeError("consumer stopped")
    else:
        with pytest.raises(OSError, match="injected"):
            with handle.iter_batches(batch_size=1) as batches:
                tuple(batches)

    assert digest_calls >= 2
    assert exit_calls == 1
    assert owner_rescans >= 2


def test_unique_workspace_root_is_created_and_held_beneath_a_trusted_parent_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io

    descriptor = os.open(tmp_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        trusted_parent = parquet_io._TrustedWorkspaceParent._from_open_descriptor(descriptor)
    finally:
        os.close(descriptor)

    monkeypatch.setattr(
        parquet_io.tempfile,
        "mkdtemp",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("workspace creation used a mutable path")
        ),
    )
    with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
        parent_identity = parquet_io._descriptor_identity(workspace._parent_fd, directory=True)
        root_identity = parquet_io._descriptor_identity(workspace._root_fd, directory=True)
        spill_identity = parquet_io._descriptor_identity(workspace._spill_fd, directory=True)
        marker_identity = os.stat(
            workspace._MARKER_NAME, dir_fd=workspace._root_fd, follow_symlinks=False
        )
        assert parent_identity == workspace._parent_identity
        assert root_identity == workspace._root_identity
        assert spill_identity == workspace._spill_identity
        assert stat.S_IMODE(root_identity[3]) == 0o700
        assert stat.S_IMODE(spill_identity[3]) == 0o700
        assert stat.S_IMODE(marker_identity.st_mode) == 0o600
        assert set(os.listdir(workspace._root_fd)) == {
            workspace._MARKER_NAME,
            workspace._SPILL_NAME,
        }
        assert all(not isinstance(value, Path) for value in vars(workspace).values())

    assert list(tmp_path.iterdir()) == []
    with pytest.raises(OSError):
        os.fstat(trusted_parent._descriptor)


@pytest.mark.parametrize("case", ["ordered-cleanup", "post-marker-root-mode-change"])
def test_unique_workspace_cleanup_is_descriptor_relative_preflighted_and_removes_marker_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.errors import ArtifactContractError

    descriptor = os.open(tmp_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        trusted_parent = parquet_io._TrustedWorkspaceParent._from_open_descriptor(descriptor)
    finally:
        os.close(descriptor)
    events: list[tuple[str, object, int | None]] = []
    changed = False
    workspace: Any = None
    original_unlink = os.unlink
    original_rmdir = os.rmdir
    original_close = os.close

    def tracked_unlink(name, *args, dir_fd=None, **kwargs):
        nonlocal changed
        events.append(("unlink", name, dir_fd))
        result = original_unlink(name, *args, dir_fd=dir_fd, **kwargs)
        if (
            case == "post-marker-root-mode-change"
            and workspace is not None
            and name == workspace._MARKER_TOMBSTONE
            and not changed
        ):
            changed = True
            os.fchmod(workspace._root_fd, 0o755)
        return result

    def tracked_rmdir(name, *args, dir_fd=None, **kwargs):
        events.append(("rmdir", name, dir_fd))
        return original_rmdir(name, *args, dir_fd=dir_fd, **kwargs)

    def tracked_close(descriptor):
        events.append(("close", descriptor, None))
        return original_close(descriptor)

    monkeypatch.setattr(os, "unlink", tracked_unlink)
    monkeypatch.setattr(os, "rmdir", tracked_rmdir)
    monkeypatch.setattr(os, "close", tracked_close)

    if case == "ordered-cleanup":
        with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
            root_fd = workspace._root_fd
            spill_fd = workspace._spill_fd
            parent_fd = workspace._parent_fd
            root_name = workspace._root_name
        assert events.index(("close", spill_fd, None)) < events.index(
            ("rmdir", workspace._SPILL_TOMBSTONE, root_fd)
        )
        assert events.index(("rmdir", workspace._SPILL_TOMBSTONE, root_fd)) < events.index(
            ("unlink", workspace._MARKER_TOMBSTONE, root_fd)
        )
        assert events.index(("close", root_fd, None)) < events.index(
            ("rmdir", f"{root_name}.cleanup", parent_fd)
        )
        assert events[-1] == ("close", parent_fd, None)
        assert list(tmp_path.iterdir()) == []
    else:
        with pytest.raises(ArtifactContractError):
            with parquet_io._final_verification_workspace(
                trusted_parent=trusted_parent
            ) as workspace:
                pass
        assert workspace is not None
        assert (workspace._spill_fd, workspace._root_fd, workspace._parent_fd) == (
            -1,
            -1,
            -1,
        )
        retained_root = tmp_path / workspace._root_name
        assert retained_root.is_dir()
        assert stat.S_IMODE(retained_root.stat().st_mode) == 0o755


@pytest.mark.parametrize("target", ["root", "spill", "marker"])
def test_workspace_root_child_and_marker_substitution_never_touch_external_victims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.errors import ArtifactContractError

    parent = tmp_path / "trusted"
    parent.mkdir(mode=0o700)
    victim = tmp_path / "external-victim.bin"
    victim.write_bytes(b"external-victim-must-survive")
    victim.chmod(0o640)
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        trusted_parent = parquet_io._TrustedWorkspaceParent._from_open_descriptor(descriptor)
    finally:
        os.close(descriptor)
    workspace: Any = None
    substituted = False
    original_rename = os.rename

    def substituting_rename(
        source,
        destination,
        *args,
        src_dir_fd=None,
        dst_dir_fd=None,
        **kwargs,
    ):
        nonlocal substituted
        matches = workspace is not None and (
            (target == "root" and source == workspace._root_name)
            or (target == "spill" and source == workspace._SPILL_NAME)
            or (target == "marker" and source == workspace._MARKER_NAME)
        )
        if matches and not substituted:
            substituted = True
            saved = f"{source}.owned-saved"
            original_rename(
                source,
                saved,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=src_dir_fd,
            )
            os.symlink(os.fspath(victim), source, dir_fd=src_dir_fd)
        return original_rename(
            source,
            destination,
            *args,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            **kwargs,
        )

    with pytest.raises(ArtifactContractError):
        with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
            monkeypatch.setattr(os, "rename", substituting_rename)

    assert substituted
    assert victim.read_bytes() == b"external-victim-must-survive"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o640
    assert workspace is not None
    for descriptor in (workspace._spill_fd, workspace._root_fd, workspace._parent_fd):
        if descriptor >= 0:
            os.close(descriptor)


@pytest.mark.parametrize(
    "fault", ["connection-close", "spill-rmdir", "marker-unlink", "root-rmdir"]
)
def test_workspace_cleanup_fault_retains_ambiguous_owned_remainder_without_victim_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.errors import ArtifactContractError

    parent = tmp_path / "trusted"
    parent.mkdir(mode=0o700)
    victim = tmp_path / "external.bin"
    victim.write_bytes(b"untouched")
    victim.chmod(0o640)
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        trusted_parent = parquet_io._TrustedWorkspaceParent._from_open_descriptor(descriptor)
    finally:
        os.close(descriptor)
    workspace: Any = None
    original_unlink = os.unlink
    original_rmdir = os.rmdir
    fault_seen = False

    def faulting_unlink(name, *args, dir_fd=None, **kwargs):
        nonlocal fault_seen
        if (
            fault == "marker-unlink"
            and workspace is not None
            and name == workspace._MARKER_TOMBSTONE
        ):
            fault_seen = True
            raise OSError("injected marker unlink failure")
        return original_unlink(name, *args, dir_fd=dir_fd, **kwargs)

    def faulting_rmdir(name, *args, dir_fd=None, **kwargs):
        nonlocal fault_seen
        matches = workspace is not None and (
            (fault == "spill-rmdir" and name == workspace._SPILL_TOMBSTONE)
            or (fault == "root-rmdir" and name == f"{workspace._root_name}.cleanup")
        )
        if matches:
            fault_seen = True
            raise OSError("injected directory removal failure")
        return original_rmdir(name, *args, dir_fd=dir_fd, **kwargs)

    monkeypatch.setattr(os, "unlink", faulting_unlink)
    monkeypatch.setattr(os, "rmdir", faulting_rmdir)

    if fault == "connection-close":

        class CloseFailConnection:
            def execute(self, *args, **kwargs):
                return self

            def executemany(self, *args, **kwargs):
                return self

            def fetchone(self):
                return None

            def close(self):
                nonlocal fault_seen
                fault_seen = True
                raise OSError("injected connection close failure")

        monkeypatch.setattr(
            parquet_io.duckdb, "connect", lambda *args, **kwargs: CloseFailConnection()
        )

    with pytest.raises((ArtifactContractError, OSError)):
        with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
            if fault == "connection-close":
                with workspace.create_unique_key_index(
                    limits=parquet_io.ParquetVerificationLimits()
                ):
                    pass

    assert fault_seen
    assert workspace is not None
    for descriptor in (workspace._spill_fd, workspace._root_fd, workspace._parent_fd):
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert any(parent.iterdir())
    assert victim.read_bytes() == b"untouched"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o640


@pytest.mark.parametrize(
    ("fault", "expected_code", "expected_operation", "expected_reason"),
    [
        ("create", "exact_tree_mismatch", "parquet-workspace-create", "workspace_create_failed"),
        ("open", "exact_tree_mismatch", "parquet-workspace-open", "workspace_open_failed"),
        (
            "revalidate",
            "exact_tree_mismatch",
            "parquet-workspace-revalidate",
            "workspace_marker_content_changed",
        ),
        (
            "configure",
            "database_validation_failed",
            "parquet-workspace-configure",
            "workspace_configure_failed",
        ),
        (
            "index-create",
            "database_validation_failed",
            "parquet-unique-index-create",
            "unique_index_create_failed",
        ),
        (
            "insert",
            "database_validation_failed",
            "parquet-unique-index-insert",
            "unique_index_insert_failed",
        ),
        (
            "query",
            "database_validation_failed",
            "parquet-unique-index-query",
            "unique_index_query_failed",
        ),
        (
            "close",
            "database_validation_failed",
            "parquet-unique-index-close",
            "connection_close_failed",
        ),
        (
            "cleanup",
            "staging_cleanup_failed",
            "parquet-workspace-cleanup",
            "workspace_cleanup_failed",
        ),
    ],
)
def test_workspace_faults_have_exact_nonreserved_typed_operations_and_redacted_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    expected_code: str,
    expected_operation: str,
    expected_reason: str,
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.errors import ArtifactContractError

    parent = tmp_path / "trusted"
    parent.mkdir(mode=0o700)
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        trusted_parent = parquet_io._TrustedWorkspaceParent._from_open_descriptor(descriptor)
    finally:
        os.close(descriptor)
    original_mkdir = os.mkdir
    original_rmdir = os.rmdir
    workspace: Any = None

    if fault == "create":

        def fail_create(name, *args, mode=0o777, dir_fd=None, **kwargs):
            if isinstance(name, str) and name.startswith("finproof-parquet-verify-"):
                raise OSError("injected root create failure")
            return original_mkdir(name, *args, mode=mode, dir_fd=dir_fd, **kwargs)

        monkeypatch.setattr(os, "mkdir", fail_create)
    elif fault == "open":
        monkeypatch.setattr(
            parquet_io,
            "_open_relative_directory",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected open failure")),
        )

    class FaultConnection:
        def __init__(self) -> None:
            self._last = ""

        def execute(self, statement, *args, **kwargs):
            self._last = str(statement)
            if fault == "configure" and self._last.startswith("SET threads"):
                raise OSError("injected configure failure")
            if fault == "index-create" and self._last.startswith("CREATE TABLE"):
                raise OSError("injected index create failure")
            return self

        def executemany(self, *args, **kwargs):
            if fault == "insert":
                raise OSError("injected insert failure")
            return self

        def fetchone(self):
            if fault == "query":
                raise OSError("injected query failure")

        def close(self):
            if fault == "close":
                raise OSError("injected close failure")

    if fault in {"configure", "index-create", "insert", "query", "close"}:
        monkeypatch.setattr(parquet_io.duckdb, "connect", lambda *args, **kwargs: FaultConnection())

    def fail_cleanup(name, *args, dir_fd=None, **kwargs):
        if workspace is not None and name == workspace._SPILL_TOMBSTONE:
            raise OSError("injected cleanup failure")
        return original_rmdir(name, *args, dir_fd=dir_fd, **kwargs)

    if fault == "cleanup":
        monkeypatch.setattr(os, "rmdir", fail_cleanup)

    with pytest.raises(ArtifactContractError) as raised:
        with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
            if fault == "revalidate":
                marker = os.open(workspace._MARKER_NAME, os.O_WRONLY, dir_fd=workspace._root_fd)
                try:
                    os.ftruncate(marker, 0)
                    os.write(marker, b"changed\n")
                finally:
                    os.close(marker)
            elif fault in {"configure", "index-create", "insert", "query", "close"}:
                with workspace.create_unique_key_index(
                    limits=parquet_io.ParquetVerificationLimits()
                ) as index:
                    if fault == "insert":
                        index.insert_canonical_batch((b"one",))
                    elif fault == "query":
                        index.assert_unique()

    error = raised.value
    assert error.code.value == expected_code
    assert error.operation_id == expected_operation
    assert error.target_basename is None
    assert error.published is False
    expected_context = {"reason": expected_reason}
    if fault == "cleanup":
        expected_context["retained_state"] = (
            "root=owned;spill=tombstone;marker=owned;spill_entries=0;unexpected=0"
        )
    assert dict(error.internal_context) == expected_context
    assert "trusted" not in str(error)
    assert "CREATE TABLE" not in str(error)


def test_actual_install_and_load_fail_under_locked_workspace_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io

    parent = tmp_path / "trusted"
    parent.mkdir(mode=0o700)
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        trusted_parent = parquet_io._TrustedWorkspaceParent._from_open_descriptor(descriptor)
    finally:
        os.close(descriptor)
    real_connect = parquet_io.duckdb.connect
    attempted: list[tuple[str, BaseException | None]] = []

    class LockedConnectionProxy:
        def __init__(self):
            self._inner = real_connect(":memory:")

        def execute(self, statement, parameters=None):
            if parameters is None:
                self._inner.execute(statement)
            else:
                self._inner.execute(statement, parameters)
            if statement == "SET autoload_known_extensions = false":
                for attempted_statement in ("INSTALL httpfs", "LOAD httpfs"):
                    try:
                        self._inner.execute(attempted_statement)
                    except BaseException as exc:
                        attempted.append((attempted_statement, exc))
                    else:
                        attempted.append((attempted_statement, None))
            return self

        def executemany(self, statement, parameters):
            self._inner.executemany(statement, parameters)
            return self

        def fetchone(self):
            return self._inner.fetchone()

        def close(self):
            self._inner.close()

    monkeypatch.setattr(
        parquet_io.duckdb,
        "connect",
        lambda *args, **kwargs: LockedConnectionProxy(),  # type: ignore[no-untyped-call]
    )
    with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
        with workspace.create_unique_key_index(
            limits=parquet_io.ParquetVerificationLimits()
        ) as index:
            index.insert_canonical_batch((b"one",))
            index.assert_unique()

    assert tuple(statement for statement, _ in attempted) == (
        "INSTALL httpfs",
        "LOAD httpfs",
    )
    assert all(isinstance(error, parquet_io.duckdb.PermissionException) for _, error in attempted)


@pytest.mark.parametrize("fault", ["listdir", "stat", "open", "fstat"])
def test_post_close_spill_enumeration_os_fault_is_typed_exact_tree_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    parent = tmp_path / "trusted"
    parent.mkdir(mode=0o700)
    trusted_parent = _trusted_workspace_parent(parent)
    workspace: Any = None
    armed = False
    spill_entry_fd: int | None = None
    deletion_events: list[str] = []
    real_connect = parquet_io.duckdb.connect
    original_listdir = os.listdir
    original_stat = os.stat
    original_open = os.open
    original_fstat = os.fstat
    original_rename = os.rename
    original_unlink = os.unlink
    original_rmdir = os.rmdir

    class ConnectionProxy:
        def __init__(self) -> None:
            self._inner = real_connect(":memory:")

        def execute(self, statement, parameters=None):
            if parameters is None:
                self._inner.execute(statement)
            else:
                self._inner.execute(statement, parameters)
            return self

        def executemany(self, statement, parameters):
            self._inner.executemany(statement, parameters)
            return self

        def fetchone(self):
            return self._inner.fetchone()

        def close(self) -> None:
            nonlocal armed
            self._inner.close()
            armed = True

    def faulting_listdir(path):
        if armed and workspace is not None and path == workspace._spill_fd and fault == "listdir":
            raise OSError("injected post-close spill listdir failure")
        return original_listdir(path)

    def faulting_stat(path, *args, dir_fd=None, **kwargs):
        if (
            armed
            and workspace is not None
            and dir_fd == workspace._spill_fd
            and path == "spill-entry.bin"
            and fault == "stat"
        ):
            raise OSError("injected post-close spill stat failure")
        return original_stat(path, *args, dir_fd=dir_fd, **kwargs)

    def faulting_open(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal spill_entry_fd
        if (
            armed
            and workspace is not None
            and dir_fd == workspace._spill_fd
            and path == "spill-entry.bin"
        ):
            if fault == "open":
                raise OSError("injected post-close spill open failure")
            descriptor = original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
            spill_entry_fd = descriptor
            return descriptor
        return original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

    def faulting_fstat(descriptor):
        if armed and descriptor == spill_entry_fd and fault == "fstat":
            raise OSError("injected post-close spill fstat failure")
        return original_fstat(descriptor)

    def tracked_rename(*args, **kwargs):
        deletion_events.append("rename")
        return original_rename(*args, **kwargs)

    def tracked_unlink(*args, **kwargs):
        deletion_events.append("unlink")
        return original_unlink(*args, **kwargs)

    def tracked_rmdir(*args, **kwargs):
        deletion_events.append("rmdir")
        return original_rmdir(*args, **kwargs)

    monkeypatch.setattr(parquet_io.duckdb, "connect", lambda *args, **kwargs: ConnectionProxy())
    monkeypatch.setattr(os, "listdir", faulting_listdir)
    monkeypatch.setattr(os, "stat", faulting_stat)
    monkeypatch.setattr(os, "open", faulting_open)
    monkeypatch.setattr(os, "fstat", faulting_fstat)
    monkeypatch.setattr(os, "rename", tracked_rename)
    monkeypatch.setattr(os, "unlink", tracked_unlink)
    monkeypatch.setattr(os, "rmdir", tracked_rmdir)

    with pytest.raises(ArtifactContractError) as caught:
        with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
            descriptor = original_open(
                "spill-entry.bin",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=workspace._spill_fd,
            )
            try:
                os.write(descriptor, b"spill")
            finally:
                os.close(descriptor)
            with workspace.create_unique_key_index(limits=parquet_io.ParquetVerificationLimits()):
                pass

    assert caught.value.code is ArtifactErrorCode.EXACT_TREE_MISMATCH
    assert caught.value.operation_id == "parquet-workspace-revalidate"
    assert caught.value.published is False
    assert caught.value.target_basename is None
    assert dict(caught.value.internal_context) == {"reason": "workspace_spill_enumeration_failed"}
    assert deletion_events == []
    assert workspace is not None
    assert (parent / workspace._root_name).is_dir()
    assert "trusted" not in str(caught.value)


@pytest.mark.parametrize(
    "fault",
    [
        "parent-fstat",
        "root-fstat",
        "spill-fstat",
        "root-relative-stat",
        "spill-relative-stat",
        "marker-relative-stat",
        "root-listdir",
        "spill-listdir",
        "marker-open",
        "marker-read",
        "marker-close",
    ],
)
def test_workspace_parent_and_precleanup_revalidation_os_faults_are_typed_exact_tree_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    parent = tmp_path / "trusted"
    parent.mkdir(mode=0o700)
    trusted_parent = _trusted_workspace_parent(parent)
    workspace: Any = None
    armed = False
    marker_fd: int | None = None
    fault_seen = False
    deletion_events: list[str] = []
    original_fstat = os.fstat
    original_stat = os.stat
    original_listdir = os.listdir
    original_open = os.open
    original_read = os.read
    original_close = os.close
    original_rename = os.rename
    original_unlink = os.unlink
    original_rmdir = os.rmdir

    def fail(message: str) -> None:
        nonlocal fault_seen
        fault_seen = True
        raise OSError(message)

    def faulting_fstat(descriptor):
        if armed and workspace is not None:
            targets = {
                "parent-fstat": workspace._parent_fd,
                "root-fstat": workspace._root_fd,
                "spill-fstat": workspace._spill_fd,
            }
            if targets.get(fault) == descriptor:
                fail("injected pre-cleanup fstat failure")
        return original_fstat(descriptor)

    def faulting_stat(path, *args, dir_fd=None, **kwargs):
        if armed and workspace is not None:
            targets = {
                "root-relative-stat": (workspace._parent_fd, workspace._root_name),
                "spill-relative-stat": (workspace._root_fd, workspace._SPILL_NAME),
                "marker-relative-stat": (workspace._root_fd, workspace._MARKER_NAME),
            }
            if targets.get(fault) == (dir_fd, path):
                fail("injected pre-cleanup relative stat failure")
        return original_stat(path, *args, dir_fd=dir_fd, **kwargs)

    def faulting_listdir(path):
        if armed and workspace is not None:
            targets = {
                "root-listdir": workspace._root_fd,
                "spill-listdir": workspace._spill_fd,
            }
            if targets.get(fault) == path:
                fail("injected pre-cleanup listdir failure")
        return original_listdir(path)

    def faulting_open(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal marker_fd
        if (
            armed
            and workspace is not None
            and dir_fd == workspace._root_fd
            and path == workspace._MARKER_NAME
        ):
            if fault == "marker-open":
                fail("injected pre-cleanup marker open failure")
            descriptor = original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
            marker_fd = descriptor
            return descriptor
        return original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

    def faulting_read(descriptor, size):
        if armed and descriptor == marker_fd and fault == "marker-read":
            fail("injected pre-cleanup marker read failure")
        return original_read(descriptor, size)

    def faulting_close(descriptor):
        if armed and descriptor == marker_fd and fault == "marker-close" and not fault_seen:
            original_close(descriptor)
            fail("injected pre-cleanup marker close failure")
        return original_close(descriptor)

    def tracked_rename(*args, **kwargs):
        deletion_events.append("rename")
        return original_rename(*args, **kwargs)

    def tracked_unlink(*args, **kwargs):
        deletion_events.append("unlink")
        return original_unlink(*args, **kwargs)

    def tracked_rmdir(*args, **kwargs):
        deletion_events.append("rmdir")
        return original_rmdir(*args, **kwargs)

    monkeypatch.setattr(os, "fstat", faulting_fstat)
    monkeypatch.setattr(os, "stat", faulting_stat)
    monkeypatch.setattr(os, "listdir", faulting_listdir)
    monkeypatch.setattr(os, "open", faulting_open)
    monkeypatch.setattr(os, "read", faulting_read)
    monkeypatch.setattr(os, "close", faulting_close)
    monkeypatch.setattr(os, "rename", tracked_rename)
    monkeypatch.setattr(os, "unlink", tracked_unlink)
    monkeypatch.setattr(os, "rmdir", tracked_rmdir)

    with pytest.raises(ArtifactContractError) as caught:
        with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
            with workspace.create_unique_key_index(limits=parquet_io.ParquetVerificationLimits()):
                pass
            armed = True

    assert fault_seen
    assert caught.value.code is ArtifactErrorCode.EXACT_TREE_MISMATCH
    assert caught.value.operation_id == "parquet-workspace-revalidate"
    assert caught.value.published is False
    assert caught.value.target_basename is None
    assert dict(caught.value.internal_context) == {"reason": "workspace_revalidation_failed"}
    assert deletion_events == []
    assert workspace is not None
    assert (parent / workspace._root_name).is_dir()
    assert "trusted" not in str(caught.value)


@pytest.mark.parametrize(
    "fault",
    [
        "spill-entry-rename",
        "spill-entry-unlink",
        "spill-close",
        "spill-rmdir",
        "marker-rename",
        "marker-read",
        "marker-close",
        "marker-unlink",
        "empty-root-fstat",
        "empty-root-listdir",
        "root-rename",
        "root-close",
        "root-rmdir",
        "parent-fstat",
        "parent-close",
        "retained-remainder",
    ],
)
def test_workspace_cleanup_os_faults_are_typed_staging_cleanup_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    parent = tmp_path / "trusted"
    parent.mkdir(mode=0o700)
    victim = tmp_path / "external-victim.bin"
    victim.write_bytes(b"external-victim")
    victim.chmod(0o640)
    trusted_parent = _trusted_workspace_parent(parent)
    workspace: Any = None
    marker_tombstone_fd: int | None = None
    marker_removed = False
    root_removed = False
    fault_seen = False
    original_rename = os.rename
    original_unlink = os.unlink
    original_close = os.close
    original_rmdir = os.rmdir
    original_open = os.open
    original_read = os.read
    original_fstat = os.fstat
    original_listdir = os.listdir

    def fail(message: str) -> None:
        nonlocal fault_seen
        fault_seen = True
        raise OSError(message)

    def faulting_rename(source, destination, *args, src_dir_fd=None, dst_dir_fd=None, **kwargs):
        if workspace is not None:
            matches = {
                "spill-entry-rename": (
                    source == "spill-entry.bin" and src_dir_fd == workspace._spill_fd
                ),
                "marker-rename": (
                    source == workspace._MARKER_NAME and src_dir_fd == workspace._root_fd
                ),
                "root-rename": (
                    source == workspace._root_name and src_dir_fd == workspace._parent_fd
                ),
            }
            if matches.get(fault, False):
                fail("injected cleanup rename failure")
        return original_rename(
            source,
            destination,
            *args,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            **kwargs,
        )

    def faulting_unlink(path, *args, dir_fd=None, **kwargs):
        nonlocal marker_removed, fault_seen
        if workspace is not None:
            if (
                fault == "spill-entry-unlink"
                and dir_fd == workspace._spill_fd
                and path == ".finproof-spill-entry-0.cleanup"
            ):
                fail("injected cleanup spill unlink failure")
            if dir_fd == workspace._root_fd and path == workspace._MARKER_TOMBSTONE:
                if fault == "marker-unlink":
                    fail("injected cleanup marker unlink failure")
                result = original_unlink(path, *args, dir_fd=dir_fd, **kwargs)
                marker_removed = True
                if fault == "retained-remainder":
                    descriptor = original_open(
                        "unexpected",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=workspace._root_fd,
                    )
                    original_close(descriptor)
                    fault_seen = True
                return result
        return original_unlink(path, *args, dir_fd=dir_fd, **kwargs)

    def faulting_close(descriptor):
        if workspace is not None and not fault_seen:
            targets = {
                "spill-close": workspace._spill_fd,
                "marker-close": marker_tombstone_fd,
                "root-close": workspace._root_fd,
                "parent-close": workspace._parent_fd,
            }
            if targets.get(fault) == descriptor:
                original_close(descriptor)
                fail("injected cleanup descriptor close failure")
        return original_close(descriptor)

    def faulting_rmdir(path, *args, dir_fd=None, **kwargs):
        nonlocal root_removed
        if workspace is not None:
            if (
                fault == "spill-rmdir"
                and dir_fd == workspace._root_fd
                and path == workspace._SPILL_TOMBSTONE
            ):
                fail("injected cleanup spill rmdir failure")
            if dir_fd == workspace._parent_fd and path == f"{workspace._root_name}.cleanup":
                if fault == "root-rmdir":
                    fail("injected cleanup root rmdir failure")
                result = original_rmdir(path, *args, dir_fd=dir_fd, **kwargs)
                root_removed = True
                return result
        return original_rmdir(path, *args, dir_fd=dir_fd, **kwargs)

    def faulting_open(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal marker_tombstone_fd
        descriptor = original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
        if (
            workspace is not None
            and dir_fd == workspace._root_fd
            and path == workspace._MARKER_TOMBSTONE
        ):
            marker_tombstone_fd = descriptor
        return descriptor

    def faulting_read(descriptor, size):
        if descriptor == marker_tombstone_fd and fault == "marker-read":
            fail("injected cleanup marker read failure")
        return original_read(descriptor, size)

    def faulting_fstat(descriptor):
        if workspace is not None:
            if fault == "empty-root-fstat" and marker_removed and descriptor == workspace._root_fd:
                fail("injected cleanup empty-root fstat failure")
            if fault == "parent-fstat" and root_removed and descriptor == workspace._parent_fd:
                fail("injected cleanup parent fstat failure")
        return original_fstat(descriptor)

    def faulting_listdir(path):
        if (
            workspace is not None
            and fault == "empty-root-listdir"
            and marker_removed
            and path == workspace._root_fd
        ):
            fail("injected cleanup empty-root listdir failure")
        return original_listdir(path)

    monkeypatch.setattr(os, "rename", faulting_rename)
    monkeypatch.setattr(os, "unlink", faulting_unlink)
    monkeypatch.setattr(os, "close", faulting_close)
    monkeypatch.setattr(os, "rmdir", faulting_rmdir)
    monkeypatch.setattr(os, "open", faulting_open)
    monkeypatch.setattr(os, "read", faulting_read)
    monkeypatch.setattr(os, "fstat", faulting_fstat)
    monkeypatch.setattr(os, "listdir", faulting_listdir)

    with pytest.raises(ArtifactContractError) as caught:
        with parquet_io._final_verification_workspace(trusted_parent=trusted_parent) as workspace:
            descriptor = original_open(
                "spill-entry.bin",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=workspace._spill_fd,
            )
            try:
                os.write(descriptor, b"spill")
            finally:
                original_close(descriptor)
            with workspace.create_unique_key_index(limits=parquet_io.ParquetVerificationLimits()):
                pass

    expected_state = {
        "spill-entry-rename": "root=owned;spill=owned;marker=owned;spill_entries=1;unexpected=0",
        "spill-entry-unlink": "root=owned;spill=owned;marker=owned;spill_entries=1;unexpected=0",
        "spill-close": "root=owned;spill=tombstone;marker=owned;spill_entries=0;unexpected=0",
        "spill-rmdir": "root=owned;spill=tombstone;marker=owned;spill_entries=0;unexpected=0",
        "marker-rename": "root=owned;spill=removed;marker=owned;spill_entries=0;unexpected=0",
        "marker-read": "root=owned;spill=removed;marker=tombstone;spill_entries=0;unexpected=0",
        "marker-close": "root=owned;spill=removed;marker=tombstone;spill_entries=0;unexpected=0",
        "marker-unlink": "root=owned;spill=removed;marker=tombstone;spill_entries=0;unexpected=0",
        "empty-root-fstat": "root=owned;spill=removed;marker=removed;spill_entries=0;unexpected=0",
        "empty-root-listdir": "root=owned;spill=removed;marker=removed;spill_entries=0;unexpected=0",
        "root-rename": "root=owned;spill=removed;marker=removed;spill_entries=0;unexpected=0",
        "root-close": "root=tombstone;spill=removed;marker=removed;spill_entries=0;unexpected=0",
        "root-rmdir": "root=tombstone;spill=removed;marker=removed;spill_entries=0;unexpected=0",
        "parent-fstat": "root=removed;spill=removed;marker=removed;spill_entries=0;unexpected=0",
        "parent-close": "root=removed;spill=removed;marker=removed;spill_entries=0;unexpected=0",
        "retained-remainder": "root=owned;spill=removed;marker=removed;spill_entries=0;unexpected=1",
    }[fault]
    assert fault_seen
    assert caught.value.code is ArtifactErrorCode.STAGING_CLEANUP_FAILED
    assert caught.value.operation_id == "parquet-workspace-cleanup"
    assert caught.value.published is False
    assert caught.value.target_basename is None
    assert dict(caught.value.internal_context) == {
        "reason": "workspace_cleanup_failed",
        "retained_state": expected_state,
    }
    assert victim.read_bytes() == b"external-victim"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o640
    assert "trusted" not in str(caught.value)
    assert "external-victim" not in str(caught.value)


@pytest.mark.parametrize("case", ["reordered", "duplicate"])
def test_staged_set_rejects_reordered_and_duplicate_verified_tables(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, first_leaf = _written(tmp_path)
    first = verify_staged_parquet_table(
        owner=owner,
        leaf=first_leaf,
        spec=table_spec("bronze_source_column"),
    )
    second_leaf = owner.claim_parquet_leaf("bronze_source_row")
    ParquetBatchWriter(table_spec("bronze_source_row"), second_leaf).close()
    second = verify_staged_parquet_table(
        owner=owner, leaf=second_leaf, spec=table_spec("bronze_source_row")
    )
    supplied = (second, first) if case == "reordered" else (first, first)

    with pytest.raises(ValueError, match="table order"):
        StagedParquetSet.from_verified(owner=owner, verifications=supplied)


@pytest.mark.parametrize(
    "method", ["verification_for", "require_tables", "require_owned", "assert_live"]
)
def test_staged_set_require_methods_revalidate_registration_and_verified_facts(
    tmp_path: Path, method: str
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(verified,))
    object.__setattr__(verified.handle, "row_count", verified.handle.row_count + 1)

    with pytest.raises(ValueError, match="unregistered"):
        if method == "verification_for":
            staged.verification_for("bronze_source_column")
        elif method == "require_tables":
            staged.require_tables(("bronze_source_column",))
        elif method == "require_owned":
            staged.require_owned(verified.handle)
        else:
            staged.assert_live()


@pytest.mark.parametrize("case", ["copy", "object-new", "equal-forge", "mixed-owner"])
def test_staged_set_rejects_copy_object_new_equal_forge_and_mixed_owner(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(verified,))
    if case == "copy":
        candidate = copy.copy(staged)
    elif case in {"object-new", "equal-forge"}:
        candidate = object.__new__(StagedParquetSet)
        for name in (
            "_owner",
            "_registration_token",
            "verifications",
            "handles",
            "persistence_timestamp",
        ):
            value = getattr(staged, name)
            if case == "equal-forge" and name in {"verifications", "handles"}:
                value = tuple(item for item in value)
            object.__setattr__(candidate, name, value)
        assert candidate == staged and candidate is not staged
    else:
        candidate = staged
        foreign = TestStageArtifactOwner(tmp_path / "foreign", owner.persistence_timestamp)
        object.__setattr__(candidate, "_owner", foreign)

    with pytest.raises(ValueError, match="unregistered|owner"):
        candidate.assert_live()


def test_staged_set_rejects_closed_or_substituted_owner_and_leaf(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(verified,))

    owner.close()
    with pytest.raises(ValueError, match="closed"):
        staged.assert_live()
    owner._live = True

    replacement = copy.copy(leaf)
    owner._leaves.append(replacement)
    object.__setattr__(verified.handle, "_leaf", replacement)
    with pytest.raises(ValueError, match="unregistered|substituted"):
        staged.assert_live()


def test_staged_set_manifest_declarations_revalidate_physical_facts(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    owner, leaf = _written(tmp_path)
    verified = verify_staged_parquet_table(
        owner=owner, leaf=leaf, spec=table_spec("bronze_source_column")
    )
    staged = StagedParquetSet.from_verified(owner=owner, verifications=(verified,))

    declarations = staged.table_declarations()
    assert len(declarations) == 1
    assert declarations[0].table_name == "bronze_source_column"
    assert declarations[0].parquet_path == "parquet/bronze_source_column.parquet"
    assert declarations[0].row_count == 2
    assert declarations[0].logical_hash == verified.logical.logical_hash

    path = leaf._path()
    with path.open("r+b") as stream:
        stream.seek(4)
        original = stream.read(1)
        stream.seek(4)
        stream.write(bytes((original[0] ^ 1,)))
    with pytest.raises(ValueError, match="physical identity changed"):
        staged.table_declarations()


def test_final_adapter_requires_complete_manifest_inventory_and_declared_entry(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifact"
    manifest = write_empty_parquet_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        with pytest.raises(ValueError, match="exact complete table registry"):
            ParquetArtifactTableVerifier().verify_tables(
                manifest=manifest,
                inventory=inventory,
                specs=TABLE_SPECS[:-1],
            )

        entries = inventory._declared_entries
        inventory._declared_entries = tuple(
            entry
            for entry in entries
            if entry.path.as_posix() != "parquet/bronze_source_column.parquet"
        )
        with pytest.raises(ValueError, match="entry is missing"):
            ParquetArtifactTableVerifier().verify_tables(
                manifest=manifest,
                inventory=inventory,
                specs=TABLE_SPECS,
            )
        inventory._declared_entries = entries

        result = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        assert tuple(table.name for table in result.tables) == tuple(
            spec.table_name for spec in TABLE_SPECS
        )
        assert len(result.handles) == 11


def test_final_adapter_independently_rechecks_all_facts_and_returns_inventory_owned_result(
    tmp_path: Path,
) -> None:
    from types import MappingProxyType

    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifact"
    manifest = write_empty_parquet_artifact_tree(root)
    forged_tables = dict(manifest.tables)
    first = forged_tables["bronze_source_column"]
    forged_tables["bronze_source_column"] = first.model_copy(update={"row_count": 1})
    forged_manifest = manifest.model_copy(update={"tables": MappingProxyType(forged_tables)})

    with verify_declared_inventory(manifest, root) as inventory:
        with pytest.raises(ValueError, match="reopened facts"):
            ParquetArtifactTableVerifier().verify_tables(
                manifest=forged_manifest,
                inventory=inventory,
                specs=TABLE_SPECS,
            )

        result = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        result.validate_against(inventory)
        assert all(handle.entry in inventory.declared_entries for handle in result.handles)


@pytest.mark.parametrize(
    "case",
    [
        "copied-final",
        "object-new-final",
        "staged-injected-entry",
        "copied-staged",
        "relabeled-staged",
    ],
)
def test_complete_final_result_requires_inventory_issued_registered_exact_handle_objects(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.manifest import (
        TableVerificationResult,
        verify_declared_inventory,
    )
    from finproof.data.artifacts.parquet_io import (
        ParquetArtifactTableVerifier,
        ParquetBatchWriter,
        StagedParquetHandle,
        VerifiedParquetTable,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifact"
    manifest = write_empty_parquet_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        result = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        control = result.handles[0]
        if case == "copied-final":
            forged = copy.copy(control)
        elif case == "object-new-final":
            forged = object.__new__(VerifiedParquetTable)
            for name in (
                "entry",
                "table_name",
                "row_count",
                "schema_sha256",
                "logical_hash",
            ):
                object.__setattr__(forged, name, getattr(control, name))
        else:
            source_name = (
                "bronze_source_row" if case == "relabeled-staged" else "bronze_source_column"
            )
            owner = TestStageArtifactOwner(
                tmp_path / f"stage-{case}", datetime(2026, 8, 15, tzinfo=UTC)
            )
            leaf = owner.claim_parquet_leaf(source_name)
            ParquetBatchWriter(table_spec(source_name), leaf).close()
            staged = verify_staged_parquet_table(
                owner=owner, leaf=leaf, spec=table_spec(source_name)
            ).handle
            assert type(staged) is StagedParquetHandle
            if case == "copied-staged":
                staged = copy.copy(staged)
            for name in ("table_name", "row_count", "schema_sha256", "logical_hash"):
                object.__setattr__(staged, name, getattr(control, name))
            object.__setattr__(staged, "entry", control.entry)
            forged = staged

        handles = (forged, *result.handles[1:])
        with pytest.raises(ArtifactContractError) as caught:
            TableVerificationResult.from_verified(
                inventory=inventory,
                tables=result.tables,
                handles=handles,
            )
        assert caught.value.internal_context == {"reason": "unowned_verified_table_handle"}


def test_common_checker_returns_facts_only_and_final_adapter_mints_local_seal_after_clean_entry_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.manifest import (
        VerifiedPhysicalInventory,
        verify_declared_inventory,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifact"
    manifest = write_empty_parquet_artifact_tree(root)
    events: list[str] = []
    open_depth = 0
    original_check = parquet_io._check_opened_parquet
    original_open = VerifiedPhysicalInventory.open_verified

    def checked(**kwargs):
        result = original_check(**kwargs)
        assert type(result).__name__ == "_CheckedParquetFacts"
        assert not any("seal" in name or "issue" in name for name in dir(result))
        events.append("facts")
        return result

    class TrackedContext:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            nonlocal open_depth
            open_depth += 1
            events.append("entry-enter")
            return self._inner.__enter__()

        def __exit__(self, exc_type, exc, traceback):
            nonlocal open_depth
            result = self._inner.__exit__(exc_type, exc, traceback)
            open_depth -= 1
            events.append("entry-exit")
            return result

    def opened(self, entry):
        return TrackedContext(original_open(self, entry))  # type: ignore[no-untyped-call]

    class StopAfterSeal(Exception):
        pass

    def issued(self, **kwargs):
        assert tuple(kwargs) == ("seal",)
        seal = kwargs["seal"]
        assert type(seal).__name__ == "_FinalVerificationSeal"
        assert "facts" in events
        assert open_depth == 0
        self.assert_unchanged()
        events.append("seal-issued")
        raise StopAfterSeal

    monkeypatch.setattr(parquet_io, "_check_opened_parquet", checked)
    monkeypatch.setattr(VerifiedPhysicalInventory, "open_verified", opened)
    monkeypatch.setattr(VerifiedPhysicalInventory, "issue_verified_table_handle", issued)

    with verify_declared_inventory(manifest, root) as inventory:
        with pytest.raises(StopAfterSeal):
            parquet_io.ParquetArtifactTableVerifier().verify_tables(
                manifest=manifest,
                inventory=inventory,
                specs=TABLE_SPECS,
            )
    assert events[-1] == "seal-issued"


@pytest.mark.parametrize(
    "case", ["copy", "equal", "object-new", "staged", "foreign", "second-consumption"]
)
def test_final_seal_rejects_copy_equal_object_new_staged_foreign_and_second_consumption(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import (
        _CheckedParquetFacts,
        _FinalVerificationAuthority,
        _FinalVerificationSeal,
    )
    from finproof.data.artifacts.table_specs import table_spec

    root = tmp_path / "artifact"
    manifest = write_empty_parquet_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        entry = next(item for item in inventory.declared_entries if item.kind == "parquet")
        spec = table_spec(entry.path.stem)
        declared = manifest.tables[spec.table_name]
        facts = _CheckedParquetFacts._from_checked(
            spec=spec,
            row_count=declared.row_count,
            logical_hash=declared.logical_hash,
            physical_size_bytes=entry.size_bytes,
            physical_sha256=entry.sha256,
            leaf_identity=(
                entry.st_dev,
                entry.st_ino,
                entry.file_type,
                0o644,
                entry.st_nlink,
            ),
        )
        seal = _FinalVerificationAuthority(inventory).mint(entry=entry, spec=spec, facts=facts)
        target_inventory = inventory
        foreign_context = None
        if case == "copy":
            forged: object = copy.copy(seal)
        elif case == "equal":
            forged = object.__new__(_FinalVerificationSeal)
            for name in ("_authority", "_inventory", "_entry", "_spec", "_facts"):
                object.__setattr__(forged, name, getattr(seal, name))
        elif case == "object-new":
            forged = object.__new__(_FinalVerificationSeal)
        elif case == "staged":
            forged = object()
        elif case == "foreign":
            other_root = tmp_path / "other"
            other_manifest = write_empty_parquet_artifact_tree(other_root)
            foreign_context = verify_declared_inventory(other_manifest, other_root)
            target_inventory = foreign_context.__enter__()
            forged = seal
        else:
            target_inventory.issue_verified_table_handle(seal=seal)
            forged = seal

        try:
            with pytest.raises(ArtifactContractError) as caught:
                target_inventory.issue_verified_table_handle(seal=forged)
            assert caught.value.internal_context == {"reason": "invalid_final_table_seal"}
        finally:
            if foreign_context is not None:
                foreign_context.__exit__(None, None, None)


@pytest.mark.parametrize("case", ["quality", "fund-attribute"])
def test_common_checker_rejects_each_quality_and_fund_attribute_physical_json_mismatch(
    tmp_path: Path, case: str
) -> None:
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.normalization.public_funds import (
        collapse_fund_items,
        normalize_fund_attribute,
    )
    from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
    from tests.helpers.source_rows import source_row

    if case == "quality":
        pure = DataQualityIssue.from_row(
            source_row("PREF01N001"),
            "pd_itm_no",
            rule_id="test.rule",
            rule_version="1.0.0",
            severity=IssueSeverity.WARNING,
            quality_status=QualityStatus.INVALID_FORMAT,
            reason="test",
            quarantined=True,
        )
        value = DataQualityIssue.model_validate(
            {
                **pure.model_dump(mode="python"),
                "first_detected_at": datetime(2026, 8, 15, tzinfo=UTC),
            },
            strict=True,
        )
        spec = table_spec("silver_quality_issue")
        row = dict(serialize_table_row(spec, value))
        row["reason"] = "forged"
    else:
        normalized = normalize_fund_attribute(source_row("PRFD01N001"))
        assert normalized.record is not None
        value = collapse_fund_items([normalized.record]).attributes[0]
        spec = table_spec("silver_fund_item_attribute")
        row = dict(serialize_table_row(spec, value))
        row["attribute_code_raw"] = "FORGED"

    owner = TestStageArtifactOwner(tmp_path / case, datetime(2026, 8, 15, tzinfo=UTC))
    leaf = owner.claim_parquet_leaf(spec.table_name)
    writer = ParquetBatchWriter(spec, leaf)
    writer.write_batch((row,))
    writer.close()
    with pytest.raises(ValueError, match="typed/JSON"):
        verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)


@pytest.mark.parametrize("boundary", ["snapshot", "arrow", "close", "abort"])
@pytest.mark.parametrize(
    "field",
    [
        "table_name",
        "layer",
        "grain",
        "columns",
        "unique_key",
        "sort_key",
        "logical_projection",
        "parquet_path",
        "column.name",
        "column.logical_type",
        "column.arrow_type",
        "column.duckdb_type",
        "column.nullable",
    ],
)
def test_writer_rechecks_deep_spec_fingerprint_at_each_uncovered_post_construction_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    field: str,
) -> None:
    from finproof.data.artifacts import parquet_io

    spec = table_spec("bronze_source_column")
    owner = TestStageArtifactOwner(
        tmp_path / f"{boundary}-{field.replace('.', '-')}",
        datetime(2026, 8, 15, tzinfo=UTC),
    )
    leaf = owner.claim_parquet_leaf(spec.table_name)
    writer = ParquetBatchWriter(spec, leaf)
    target = spec.columns[0] if field.startswith("column.") else spec
    attribute = field.removeprefix("column.")
    original = getattr(target, attribute)
    changed = not original if attribute == "nullable" else "forged"
    if isinstance(original, tuple):
        changed = tuple(reversed(original)) if len(original) > 1 else ("forged",)
    iterations = 0

    def mutate() -> None:
        object.__setattr__(target, attribute, changed)

    class Rows:
        def __iter__(self):
            nonlocal iterations
            iterations += 1
            yield _column_row(1)

    try:
        if boundary == "snapshot":
            mutate()
            with pytest.raises(ValueError, match="fingerprint"):
                writer.write_batch(Rows())
            assert iterations == 0
        elif boundary == "arrow":
            original_validate = parquet_io.validate_physical_row

            def validate_then_mutate(*args, **kwargs):
                result = original_validate(*args, **kwargs)
                mutate()
                return result

            monkeypatch.setattr(parquet_io, "validate_physical_row", validate_then_mutate)
            with pytest.raises(ValueError, match="fingerprint"):
                writer.write_batch((_column_row(1),))
        elif boundary == "close":
            writer.write_batch((_column_row(1),))
            mutate()
            with pytest.raises(ValueError, match="fingerprint"):
                writer.close()
        else:
            mutate()
            with pytest.raises(ValueError, match="fingerprint"):
                writer.abort()
    finally:
        object.__setattr__(target, attribute, original)
        monkeypatch.undo()
        if not writer._closed:
            writer.close()


@pytest.mark.parametrize(
    "boundary",
    [
        "after-open",
        "before-batch",
        "after-last-read",
        "before-registration",
        "handle-batch",
        "set-lookup",
        "set-declaration",
    ],
)
@pytest.mark.parametrize(
    "field",
    [
        "table_name",
        "layer",
        "grain",
        "columns",
        "unique_key",
        "sort_key",
        "logical_projection",
        "parquet_path",
        "column.name",
        "column.logical_type",
        "column.arrow_type",
        "column.duckdb_type",
        "column.nullable",
    ],
)
def test_staged_verifier_rechecks_deep_spec_fingerprint_at_each_uncovered_post_open_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    field: str,
) -> None:
    from contextlib import contextmanager

    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.parquet_io import (
        StagedParquetSet,
        verify_staged_parquet_table,
    )

    spec = table_spec("bronze_source_column")
    owner, leaf = _written(tmp_path / f"{boundary}-{field.replace('.', '-')}")
    target = spec.columns[0] if field.startswith("column.") else spec
    attribute = field.removeprefix("column.")
    original = getattr(target, attribute)
    changed = not original if attribute == "nullable" else "forged"
    if isinstance(original, tuple):
        changed = tuple(reversed(original)) if len(original) > 1 else ("forged",)

    def mutate() -> None:
        object.__setattr__(target, attribute, changed)

    converted = 0
    try:
        if boundary == "after-open":
            original_open = leaf.open_verified
            original_parquet = parquet_io.pq.ParquetFile
            parquet_constructions = 0

            def tracked_parquet(*args, **kwargs):
                nonlocal parquet_constructions
                parquet_constructions += 1
                return original_parquet(*args, **kwargs)

            @contextmanager
            def mutating_open():
                with original_open() as stream:
                    mutate()
                    yield stream

            leaf.open_verified = mutating_open
            monkeypatch.setattr(parquet_io.pq, "ParquetFile", tracked_parquet)
            with pytest.raises(ValueError, match="fingerprint"):
                verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
            assert parquet_constructions == 0
        elif boundary == "before-batch":
            original_parquet = parquet_io.pq.ParquetFile

            class BatchView:
                def __init__(self, batch):
                    self._batch = batch

                def to_pylist(self):
                    nonlocal converted
                    converted += 1
                    return self._batch.to_pylist()

            class ParquetView:
                def __init__(self, stream):
                    self._inner = original_parquet(stream)
                    self.schema_arrow = self._inner.schema_arrow
                    self.metadata = self._inner.metadata

                def iter_batches(self, **kwargs):
                    for batch in self._inner.iter_batches(**kwargs):
                        mutate()
                        yield BatchView(batch)  # type: ignore[no-untyped-call]

            monkeypatch.setattr(parquet_io.pq, "ParquetFile", ParquetView)
            with pytest.raises(ValueError, match="fingerprint"):
                verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
            assert converted == 0
        elif boundary == "after-last-read":
            original_check = parquet_io._check_opened_parquet

            def check_then_mutate(**kwargs):
                facts = original_check(**kwargs)
                mutate()
                return facts

            monkeypatch.setattr(parquet_io, "_check_opened_parquet", check_then_mutate)
            with pytest.raises(ValueError, match="fingerprint"):
                verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
        elif boundary == "before-registration":
            original_register = owner._register_staged_verification
            original_logical = parquet_io.ExpectedLogicalTable
            registration_calls = 0

            def register(value, handle):
                nonlocal registration_calls
                registration_calls += 1
                return original_register(value, handle)

            def logical_then_mutate(*args, **kwargs):
                value = original_logical(*args, **kwargs)
                mutate()
                return value

            owner._register_staged_verification = register
            monkeypatch.setattr(parquet_io, "ExpectedLogicalTable", logical_then_mutate)
            with pytest.raises(ValueError, match="fingerprint"):
                verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
            assert registration_calls == 0
        else:
            verification = verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
            staged = StagedParquetSet.from_verified(owner=owner, verifications=(verification,))
            mutate()
            if boundary == "handle-batch":
                with (
                    pytest.raises(ValueError, match="fingerprint"),
                    verification.handle.iter_batches() as batches,
                ):
                    next(batches)
            elif boundary == "set-lookup":
                with pytest.raises(ValueError, match="fingerprint"):
                    staged.verification_for(spec.table_name)
            else:
                with pytest.raises(ValueError, match="fingerprint"):
                    staged.table_declarations()
    finally:
        object.__setattr__(target, attribute, original)
        monkeypatch.undo()


@pytest.mark.parametrize(
    "boundary",
    ["after-open", "before-batch", "facts-return", "seal-mint", "issuance", "result"],
)
@pytest.mark.parametrize(
    "field",
    [
        "table_name",
        "layer",
        "grain",
        "columns",
        "unique_key",
        "sort_key",
        "logical_projection",
        "parquet_path",
        "column.name",
        "column.logical_type",
        "column.arrow_type",
        "column.duckdb_type",
        "column.nullable",
    ],
)
def test_final_verifier_rechecks_deep_spec_fingerprint_at_each_uncovered_post_open_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    field: str,
) -> None:
    from finproof.data.artifacts import parquet_io
    from finproof.data.artifacts.manifest import (
        verify_declared_inventory,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / f"{boundary}-{field.replace('.', '-')}"
    manifest = write_empty_parquet_artifact_tree(root)
    spec = TABLE_SPECS[-1] if boundary == "result" else TABLE_SPECS[0]
    target = spec.columns[0] if field.startswith("column.") else spec
    attribute = field.removeprefix("column.")
    original = getattr(target, attribute)
    changed = not original if attribute == "nullable" else "forged"
    if isinstance(original, tuple):
        changed = tuple(reversed(original)) if len(original) > 1 else ("forged",)

    def mutate() -> None:
        object.__setattr__(target, attribute, changed)

    converted = 0
    try:
        with verify_declared_inventory(manifest, root) as inventory:
            if boundary == "after-open":
                original_open = inventory.open_verified
                original_parquet = parquet_io.pq.ParquetFile
                parquet_constructions = 0

                class TrackedContext:
                    def __init__(self, inner, should_mutate):
                        self._inner = inner
                        self._should_mutate = should_mutate

                    def __enter__(self):
                        stream = self._inner.__enter__()
                        if self._should_mutate:
                            mutate()
                        return stream

                    def __exit__(self, *args):
                        return self._inner.__exit__(*args)

                def opened(entry):
                    return TrackedContext(  # type: ignore[no-untyped-call]
                        original_open(entry), entry.path.as_posix() == spec.parquet_path
                    )

                def tracked_parquet(*args, **kwargs):
                    nonlocal parquet_constructions
                    parquet_constructions += 1
                    return original_parquet(*args, **kwargs)

                inventory.open_verified = opened
                monkeypatch.setattr(parquet_io.pq, "ParquetFile", tracked_parquet)
                with pytest.raises(ValueError, match="fingerprint"):
                    parquet_io.ParquetArtifactTableVerifier().verify_tables(
                        manifest=manifest, inventory=inventory, specs=TABLE_SPECS
                    )
                assert parquet_constructions == 0
            elif boundary == "before-batch":
                original_parquet = parquet_io.pq.ParquetFile

                class BatchView:
                    def __init__(self, batch):
                        self._batch = batch

                    def to_pylist(self):
                        nonlocal converted
                        converted += 1
                        return self._batch.to_pylist()

                class ParquetView:
                    def __init__(self, stream):
                        self._inner = original_parquet(stream)
                        self.schema_arrow = self._inner.schema_arrow
                        self.metadata = self._inner.metadata

                    def iter_batches(self, **kwargs):
                        mutate()
                        for batch in self._inner.iter_batches(**kwargs):
                            yield BatchView(batch)  # type: ignore[no-untyped-call]

                monkeypatch.setattr(parquet_io.pq, "ParquetFile", ParquetView)
                with pytest.raises(ValueError, match="fingerprint"):
                    parquet_io.ParquetArtifactTableVerifier().verify_tables(
                        manifest=manifest, inventory=inventory, specs=TABLE_SPECS
                    )
                assert converted == 0
            elif boundary == "facts-return":
                original_check = parquet_io._check_opened_parquet

                def check_then_mutate(**kwargs):
                    facts = original_check(**kwargs)
                    if kwargs["spec"] is spec:
                        mutate()
                    return facts

                monkeypatch.setattr(parquet_io, "_check_opened_parquet", check_then_mutate)
                with pytest.raises(ValueError, match="fingerprint"):
                    parquet_io.ParquetArtifactTableVerifier().verify_tables(
                        manifest=manifest, inventory=inventory, specs=TABLE_SPECS
                    )
            elif boundary == "seal-mint":
                original_unchanged = inventory.assert_unchanged
                original_mint = parquet_io._FinalVerificationAuthority.mint
                mint_calls = 0

                def unchanged_then_mutate():
                    original_unchanged()
                    mutate()

                def mint(*args, **kwargs):
                    nonlocal mint_calls
                    mint_calls += 1
                    return original_mint(*args, **kwargs)

                inventory.assert_unchanged = unchanged_then_mutate
                monkeypatch.setattr(parquet_io._FinalVerificationAuthority, "mint", mint)
                with pytest.raises(ValueError, match="fingerprint"):
                    parquet_io.ParquetArtifactTableVerifier().verify_tables(
                        manifest=manifest, inventory=inventory, specs=TABLE_SPECS
                    )
                assert mint_calls == 0
            elif boundary == "issuance":
                original_mint = parquet_io._FinalVerificationAuthority.mint
                issue_calls = 0

                def mint_then_mutate(*args, **kwargs):
                    seal = original_mint(*args, **kwargs)
                    mutate()
                    return seal

                original_issue = inventory.issue_verified_table_handle

                def issue(**kwargs):
                    nonlocal issue_calls
                    issue_calls += 1
                    return original_issue(**kwargs)

                monkeypatch.setattr(
                    parquet_io._FinalVerificationAuthority, "mint", mint_then_mutate
                )
                inventory.issue_verified_table_handle = issue
                with pytest.raises(ValueError, match="fingerprint"):
                    parquet_io.ParquetArtifactTableVerifier().verify_tables(
                        manifest=manifest, inventory=inventory, specs=TABLE_SPECS
                    )
                assert issue_calls == 0
            else:
                original_issue = inventory.issue_verified_table_handle
                issue_calls = 0

                def issue(**kwargs):
                    nonlocal issue_calls
                    handle = original_issue(**kwargs)
                    issue_calls += 1
                    if issue_calls == len(TABLE_SPECS):
                        mutate()
                    return handle

                inventory.issue_verified_table_handle = issue
                with pytest.raises(ValueError, match="fingerprint"):
                    parquet_io.ParquetArtifactTableVerifier().verify_tables(
                        manifest=manifest, inventory=inventory, specs=TABLE_SPECS
                    )
    finally:
        object.__setattr__(target, attribute, original)
        monkeypatch.undo()
