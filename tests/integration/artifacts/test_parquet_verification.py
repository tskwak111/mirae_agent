# mypy: disable-error-code="arg-type,assignment,attr-defined,import-untyped,misc,no-untyped-def,unused-ignore"
# ruff: noqa: ANN001, ANN002, ANN003, ANN204, ARG002, ARG005, B017, E501, PT011, PT012, PT018, RUF043, SIM117
"""Owned staged and final Parquet verification contracts."""

import copy
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

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
    with _final_verification_workspace(parent=tmp_path) as workspace:
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
    with parquet_io._final_verification_workspace(parent=tmp_path) as workspace:
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
    retained: list[Path] = []

    def connect(target: str):
        nonlocal connected
        connected = True
        return parquet_io.duckdb.connect(target)

    original_connect = parquet_io.duckdb.connect

    def spy_connect(target: str):
        nonlocal connected
        connected = True
        return original_connect(target)

    monkeypatch.setattr(parquet_io.duckdb, "connect", spy_connect)
    with pytest.raises(Exception):
        with parquet_io._final_verification_workspace(parent=tmp_path) as workspace:
            retained.append(workspace._root)
            (workspace._root / "keys.duckdb").symlink_to(victim)
            with workspace.create_unique_key_index(limits=parquet_io.ParquetVerificationLimits()):
                yielded = True
    assert connected is False
    assert yielded is False
    assert victim.read_bytes() == original_bytes
    assert victim.stat().st_mode == original_mode
    assert retained[0].is_dir()


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
        with parquet_io._final_verification_workspace(parent=tmp_path) as workspace:
            if case == "root-mode":
                workspace._root.chmod(0o755)
            elif case == "marker-mode":
                workspace._marker.chmod(0o644)
            elif case == "spill-mode":
                workspace._spill.chmod(0o755)
            elif case == "marker-bytes":
                workspace._marker.write_bytes(b"forged-marker-same-inode\n")
            elif case == "root-aba":
                displaced = tmp_path / "displaced-root"
                workspace._root.rename(displaced)
                workspace._root.mkdir(mode=0o700)
                (workspace._root / "spill").mkdir(mode=0o700)
                marker = workspace._root / ".finproof-parquet-verification"
                marker.write_bytes(workspace._MARKER_BYTES)
                marker.chmod(0o600)
            elif case == "marker-aba":
                workspace._marker.unlink()
                workspace._marker.write_bytes(workspace._MARKER_BYTES)
                workspace._marker.chmod(0o600)
            else:
                workspace._spill.rmdir()
                workspace._spill.mkdir(mode=0o700)
            workspace.assert_unchanged()


def test_unique_workspace_closes_before_cleanup_and_rejects_aba_or_ambiguity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts import parquet_io

    events: list[str] = []

    class Connection:
        def execute(self, sql: str, parameters=None):
            if sql == "SET temp_directory = ?":
                spill = Path(parameters[0]) / "owned-spill.tmp"
                spill.write_bytes(b"spill")
                spill.chmod(0o600)
            return self

        def executemany(self, sql: str, parameters) -> None:
            del sql
            tuple(parameters)

        def fetchone(self):
            return None

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(parquet_io.duckdb, "connect", lambda target: Connection())
    roots: list[Path] = []
    with parquet_io._final_verification_workspace(parent=tmp_path) as workspace:
        roots.append(workspace._root)
        with workspace.create_unique_key_index(
            limits=parquet_io.ParquetVerificationLimits()
        ) as index:
            index.insert_canonical_batch((b"one",))
            index.assert_unique()
        assert events == ["close"]
        assert (workspace._spill / "owned-spill.tmp").is_file()
    assert events == ["close"]
    assert not roots[0].exists()


@pytest.mark.parametrize(
    "case", ["temp-root", "spill-setup", "marker-setup", "connect", "configure", "close"]
)
def test_unique_workspace_setup_and_close_failures_are_typed_and_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from finproof.data.artifacts import parquet_io

    roots: list[Path] = []
    original_mkdtemp = parquet_io.tempfile.mkdtemp

    def tracked_mkdtemp(*args, **kwargs):
        if case == "temp-root":
            raise OSError("injected temp-root failure")
        result = original_mkdtemp(*args, **kwargs)
        roots.append(Path(result))
        return result

    monkeypatch.setattr(parquet_io.tempfile, "mkdtemp", tracked_mkdtemp)
    if case == "spill-setup":
        original_mkdir = parquet_io.os.mkdir

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
        with parquet_io._final_verification_workspace(parent=tmp_path) as workspace:
            with workspace.create_unique_key_index(limits=parquet_io.ParquetVerificationLimits()):
                pass
    if case == "configure":
        assert close_calls == 1
    if case == "close":
        assert roots[0].is_dir()


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
    from finproof.data.artifacts.parquet_io import verify_staged_parquet_table

    class NonRegisteringOwner(TestStageArtifactOwner):
        def _register_staged_verification(self, value: object, handle: object) -> object:
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

    extended = staged.extend(second)

    assert extended.verifications == (first, second)
    assert extended.verifications[0] is first
    assert extended.verifications[1] is second
    assert extended.handles == (first.handle, second.handle)
    assert extended.persistence_timestamp is staged.persistence_timestamp
    with pytest.raises(ValueError, match="superseded|unregistered"):
        owner._require_registered_staged_set(staged, staged._registration_token)
    owner._require_registered_staged_set(extended, extended._registration_token)


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
