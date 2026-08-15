# mypy: disable-error-code="arg-type,assignment,func-returns-value,import-untyped,method-assign,no-untyped-def,return-value,type-arg"
# ruff: noqa: ANN001, ANN002, ANN204, E501
"""Capability-bound incremental Parquet writer contracts."""

from contextlib import contextmanager
from io import BytesIO
from pathlib import PurePosixPath

import pytest


class _Leaf:
    table_name = "bronze_source_column"
    relative_path = PurePosixPath("parquet/bronze_source_column.parquet")

    def __init__(self) -> None:
        self.buffer = BytesIO()
        self.create_calls = 0
        self.unlinked = False

    @contextmanager
    def create_exclusive(self):
        self.create_calls += 1
        yield self.buffer

    def unlink_if_exact_writer_owned(self) -> None:
        self.unlinked = True


class _FailingBytesIO(BytesIO):
    fail_writes = False

    def write(self, data) -> int:
        if self.fail_writes:
            raise OSError("injected sink write failure")
        return super().write(data)


def test_parquet_module_skeleton_rejects_valid_owned_leaf() -> None:
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    writer = ParquetBatchWriter(table_spec("bronze_source_column"), _Leaf())
    assert writer.close() is None


def test_writer_creates_only_exact_owned_leaf_exclusively_nofollow() -> None:
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import TableSpec, table_spec

    leaf = _Leaf()
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    assert leaf.create_calls == 1
    assert writer.close() is None

    foreign_table = _Leaf()
    foreign_table.table_name = "bronze_source_row"
    with pytest.raises(ValueError, match="leaf table/path"):
        ParquetBatchWriter(table_spec("bronze_source_column"), foreign_table)
    assert foreign_table.create_calls == 0

    foreign_path = _Leaf()
    foreign_path.relative_path = PurePosixPath("parquet/other.parquet")
    with pytest.raises(ValueError, match="leaf table/path"):
        ParquetBatchWriter(table_spec("bronze_source_column"), foreign_path)
    assert foreign_path.create_calls == 0

    spec = table_spec("bronze_source_column")
    forged = TableSpec.model_validate(spec.model_dump(), strict=True)
    untouched = _Leaf()
    with pytest.raises(ValueError, match="exact registered"):
        ParquetBatchWriter(forged, untouched)
    assert untouched.create_calls == 0


def _column_row(number: int) -> dict[str, object]:
    from datetime import date

    return {
        "catalog_version": "1.0.0",
        "source_snapshot_date": date(2026, 7, 11),
        "source_table_order": 0,
        "source_table": "PRBD01N001",
        "source_column_number": number,
        "source_column_letter": chr(64 + number),
        "source_column_name": f"COL{number}",
        "source_declared_type": "VARCHAR",
        "source_example": "x",
        "source_key_marker": "",
        "source_name_ko": "열",
        "schema_file": "schema.xlsx",
        "schema_excel_row": number + 1,
    }


def test_writer_uses_exact_schema_options_and_row_group_limit() -> None:
    import pyarrow.parquet as pq

    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    leaf = _Leaf()
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    writer.write_batch((_column_row(1), _column_row(2)))
    assert writer.close() is None

    parquet = pq.ParquetFile(BytesIO(leaf.buffer.getvalue()))
    assert parquet.schema_arrow.names == list(_column_row(1))
    assert parquet.metadata.num_rows == 2
    assert parquet.metadata.num_row_groups == 1
    for index in range(parquet.metadata.num_columns):
        column = parquet.metadata.row_group(0).column(index)
        assert column.compression == "ZSTD"
        assert column.statistics is not None


@pytest.mark.parametrize("case", ["wrong-columns", "empty", "over-limit"])
def test_writer_enforces_bounded_batches_without_early_logical_hash(case: str) -> None:
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    writer = ParquetBatchWriter(table_spec("bronze_source_column"), _Leaf())
    rows: object
    if case == "wrong-columns":
        rows = ({"wrong": 1},)
    elif case == "empty":
        rows = ()
    else:
        rows = (_column_row(1),) * 65_537
    with pytest.raises(ValueError, match=r"columns/order|1\.\.65536"):
        writer.write_batch(rows)
    assert not hasattr(writer, "logical_hash")
    writer.close()


@pytest.mark.parametrize(
    "case",
    ["lying-length", "mutating-sequence", "one-pass", "exact-limit", "over-limit"],
)
def test_writer_snapshots_lying_length_and_mutating_sequence_once_with_65537_cap(
    case: str,
) -> None:
    import pyarrow.parquet as pq

    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    class Rows:
        def __init__(self) -> None:
            self.iterations = 0

        def __len__(self) -> int:
            if case in {"lying-length", "mutating-sequence"}:
                return 1
            raise AssertionError("writer must not ask the caller for len")

        def __iter__(self):
            self.iterations += 1
            if self.iterations > 1:
                if case == "mutating-sequence":
                    yield _column_row(1)
                    yield _column_row(2)
                    return
                raise AssertionError("writer iterated caller rows twice")
            count = {
                "lying-length": 65_537,
                "mutating-sequence": 1,
                "one-pass": 2,
                "exact-limit": 65_536,
                "over-limit": 65_537,
            }[case]
            for number in range(count):
                yield _column_row(number % 26 + 1)

    rows = Rows()
    leaf = _Leaf()
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    if case in {"lying-length", "over-limit"}:
        with pytest.raises(ValueError, match=r"1\.\.65536"):
            writer.write_batch(rows)
        assert rows.iterations == 1
        writer.close()
        return

    writer.write_batch(rows)
    assert rows.iterations == 1
    writer.close()
    parquet = pq.ParquetFile(BytesIO(leaf.buffer.getvalue()))
    assert (
        parquet.metadata.num_rows
        == {
            "mutating-sequence": 1,
            "one-pass": 2,
            "exact-limit": 65_536,
        }[case]
    )


@pytest.mark.parametrize("case", ["reuse-write", "reuse-close", "write-failure", "close-failure"])
def test_writer_close_flush_failure_and_reuse_lifecycle(case: str) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    leaf = _Leaf()
    leaf.buffer = _FailingBytesIO()
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    if case == "write-failure":
        leaf.buffer.fail_writes = True
        with pytest.raises(ArtifactContractError) as captured:
            writer.write_batch((_column_row(1),))
        assert captured.value.code is ArtifactErrorCode.SERIALIZATION_FAILED
        return

    writer.write_batch((_column_row(1),))
    if case == "close-failure":
        leaf.buffer.fail_writes = True
        with pytest.raises(ArtifactContractError) as captured:
            writer.close()
        assert captured.value.code is ArtifactErrorCode.SERIALIZATION_FAILED
        return

    assert writer.close() is None
    operation = writer.write_batch if case == "reuse-write" else writer.close
    arguments = ((_column_row(2),),) if case == "reuse-write" else ()
    with pytest.raises(RuntimeError, match="already closed"):
        operation(*arguments)


def test_writer_leaf_enter_failure_is_typed_and_never_writes() -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    class EnterFailure:
        def __enter__(self):
            raise OSError("injected enter failure")

        def __exit__(self, *args):
            raise AssertionError("exit must not run when enter failed")

    leaf = _Leaf()
    leaf.create_exclusive = lambda: EnterFailure()
    with pytest.raises(ArtifactContractError) as captured:
        ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    assert captured.value.code is ArtifactErrorCode.SERIALIZATION_FAILED
    assert captured.value.operation_id == "enter-parquet-leaf"
    assert leaf.buffer.getvalue() == b""


def test_writer_leaf_exit_failure_is_typed_and_preserves_ambiguous_leaf() -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    leaf = _Leaf()

    class ExitFailure:
        def __enter__(self):
            return leaf.buffer

        def __exit__(self, *args):
            raise OSError("injected exit failure")

    leaf.create_exclusive = lambda: ExitFailure()
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    writer.write_batch((_column_row(1),))
    with pytest.raises(ArtifactContractError) as captured:
        writer.close()
    assert captured.value.code is ArtifactErrorCode.SERIALIZATION_FAILED
    assert captured.value.operation_id == "exit-parquet-leaf"
    assert leaf.unlinked is False


@pytest.mark.parametrize("case", ["owned", "substituted"])
def test_writer_abort_unlinks_only_exact_writer_created_inode(case: str) -> None:
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    leaf = _Leaf()
    if case == "substituted":

        def reject_substitution() -> None:
            raise ValueError("substituted writer leaf")

        leaf.unlink_if_exact_writer_owned = reject_substitution
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    if case == "substituted":
        from finproof.data.artifacts.errors import ArtifactContractError

        with pytest.raises(ArtifactContractError):
            writer.abort()
        assert leaf.unlinked is False
    else:
        assert writer.abort() is None
        assert leaf.unlinked is True
        with pytest.raises(RuntimeError, match="already closed"):
            writer.write_batch((_column_row(1),))


@pytest.mark.parametrize("case", ["close", "exit", "unlink"])
def test_writer_abort_close_exit_and_unlink_faults_are_typed_and_ordered(
    case: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.table_specs import table_spec

    events: list[str] = []
    leaf = _Leaf()
    leaf.buffer = _FailingBytesIO()

    class Context:
        def __enter__(self):
            return leaf.buffer

        def __exit__(self, *args):
            events.append("exit")
            if case == "exit":
                raise OSError("injected exit failure")

    leaf.create_exclusive = lambda: Context()

    def unlink() -> None:
        events.append("unlink")
        if case == "unlink":
            raise OSError("injected unlink failure")
        leaf.unlinked = True

    leaf.unlink_if_exact_writer_owned = unlink
    writer = ParquetBatchWriter(table_spec("bronze_source_column"), leaf)
    if case == "close":
        leaf.buffer.fail_writes = True
    with pytest.raises(ArtifactContractError) as captured:
        writer.abort()
    assert captured.value.code is ArtifactErrorCode.SERIALIZATION_FAILED
    assert events == (["exit", "unlink"] if case == "unlink" else ["exit"])
    assert leaf.unlinked is False
