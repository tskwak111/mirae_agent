# mypy: disable-error-code="index,misc,no-untyped-def"
"""One-pass Bronze artifact ingestion contracts."""

import gc
import hashlib
import inspect
import io
import json
import weakref
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from finproof.domain.source import SourceRow
from tests.helpers.source_manifest import TABLE_COLUMNS, write_source_contract_fixture
from tests.helpers.source_rows import source_row


class _RecordingSink:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def enqueue(self, row: object) -> None:
        self.rows.append(row)


class _TrackedMapping(Mapping[str, object]):
    def __init__(self, ordinal: int) -> None:
        self.ordinal = ordinal

    def __getitem__(self, key: str) -> object:
        if key != "ordinal":
            raise KeyError(key)
        return self.ordinal

    def __iter__(self) -> Iterator[str]:
        yield "ordinal"

    def __len__(self) -> int:
        return 1


class _BatchWriter:
    def __init__(self) -> None:
        self.batches: list[tuple[int, ...]] = []
        self.closed = False

    def write_batch(self, rows: Sequence[Mapping[str, object]]) -> None:
        assert len(rows) <= 2
        self.batches.append(tuple(row["ordinal"] for row in rows))

    def close(self) -> None:
        self.closed = True

    def abort(self) -> None:
        self.closed = True


def _source_catalog(tmp_path: Path):
    from finproof.data.source_manifest import SourceFileManifest

    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    return SourceFileManifest.load(manifest_path, catalog_path).schema_catalog


def test_bronze_module_skeleton_rejects_complete_fixture() -> None:
    from finproof.data.artifacts.bronze import BronzeBuildResult

    with pytest.raises(TypeError):
        BronzeBuildResult(
            staged_tables=object(),
            observations=object(),
            input_identity=object(),
        )


def test_bronze_columns_follow_exact_manifest_catalog_order(tmp_path: Path) -> None:
    from finproof.data.artifacts.bronze import iter_bronze_columns

    catalog = _source_catalog(tmp_path)
    rows = tuple(iter_bronze_columns(catalog))

    assert len(rows) == sum(len(headers) for headers in TABLE_COLUMNS.values())
    offset = 0
    for table_order, (table_id, headers) in enumerate(TABLE_COLUMNS.items()):
        table = catalog.tables[table_id]
        for column_number, header in enumerate(headers, start=1):
            assert rows[offset] == {
                "catalog_version": "1.0.0",
                "source_snapshot_date": catalog.snapshot_date,
                "source_table_order": table_order,
                "source_table": table_id,
                "source_column_number": column_number,
                "source_column_letter": chr(ord("A") + column_number - 1),
                "source_column_name": header,
                "source_declared_type": "text",
                "source_example": "",
                "source_key_marker": "",
                "source_name_ko": "",
                "schema_file": table.schema_file,
                "schema_excel_row": column_number + 2,
            }
            offset += 1


def test_bronze_source_row_preserves_payload_hash_locator_and_timestamp() -> None:
    from finproof.data.artifacts.bronze import BronzeFanoutSink
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    value = source_row("PRBD01N001", {"PD_NO": "000123", "PD_NM": "테스트 채권"})
    timestamp = datetime(2026, 8, 15, 1, 2, 3, 456789, tzinfo=UTC)
    row_sink = _RecordingSink()
    sink = BronzeFanoutSink(
        row_sink=row_sink,
        cell_sink=None,
        persistence_timestamp=timestamp,
        consumer=None,
    )

    sink.consume_source_row(value)

    assert len(row_sink.rows) == 1
    row = row_sink.rows[0]
    assert isinstance(row, dict)
    assert tuple(row) == tuple(
        column.name for column in TABLE_SPEC_BY_NAME["bronze_source_row"].columns
    )
    assert row["source_table"] == value.source_table
    assert row["source_file"] == value.source_file.as_posix()
    assert row["source_sheet"] == value.source_sheet
    assert row["source_row_number"] == value.source_row_number
    assert row["source_checksum"] == value.source_checksum
    assert row["source_snapshot_date"] == value.source_snapshot_date
    assert row["raw_payload_json"] == json.dumps(
        value.raw_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert (
        row["raw_payload_sha256"]
        == hashlib.sha256("\0".join(value.raw_payload).encode("utf-8")).hexdigest()
    )
    assert row["loaded_at"] is timestamp


def test_bronze_source_cells_reconstruct_each_exact_source_row() -> None:
    from finproof.data.artifacts.bronze import BronzeFanoutSink
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    value = source_row("PRFD01N001", {"itm_no": "F0001", "itm_nm": "공모펀드"})
    row_sink = _RecordingSink()
    cell_sink = _RecordingSink()
    BronzeFanoutSink(
        row_sink=row_sink,
        cell_sink=cell_sink,
        persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
        consumer=None,
    ).consume_source_row(value)

    assert len(cell_sink.rows) == len(value.cells)
    assert tuple(cell["raw_value"] for cell in cell_sink.rows) == value.raw_payload
    for projected, source_cell in zip(cell_sink.rows, value.cells, strict=True):
        assert isinstance(projected, dict)
        assert tuple(projected) == tuple(
            column.name for column in TABLE_SPEC_BY_NAME["bronze_source_cell"].columns
        )
        assert projected == {
            "source_table_order": 3,
            "source_table": value.source_table,
            "source_file": value.source_file.as_posix(),
            "source_sheet": value.source_sheet,
            "source_row_number": value.source_row_number,
            "source_column_name": source_cell.column_name,
            "source_column_number": source_cell.excel_column_number,
            "source_column_letter": source_cell.excel_column_letter,
            "source_checksum": value.source_checksum,
            "source_snapshot_date": value.source_snapshot_date,
            "source_applicable_date": source_cell.applicable_date,
            "raw_value": source_cell.raw_value,
        }


@pytest.mark.parametrize("table_name", ["bronze_source_row", "bronze_source_cell"])
def test_bronze_sinks_flush_bounded_batches_in_manifest_order(table_name: str) -> None:
    from finproof.data.artifacts.bronze import BoundedBronzeBatchSink

    writer = _BatchWriter()
    sink = BoundedBronzeBatchSink(writer=writer, batch_limit=2, table_name=table_name)
    released: list[weakref.ReferenceType[_TrackedMapping]] = []
    for ordinal in range(5):
        row = _TrackedMapping(ordinal)
        released.append(weakref.ref(row))
        sink.enqueue(row)
        del row
        if ordinal % 2 == 1:
            gc.collect()
            assert released[ordinal - 1]() is None
            assert released[ordinal]() is None

    sink.close()

    assert writer.batches == [(0, 1), (2, 3), (4,)]
    assert writer.closed is True
    gc.collect()
    assert all(reference() is None for reference in released)


def test_bronze_fanout_enqueues_complete_row_before_one_consumer_call() -> None:
    from finproof.data.artifacts.bronze import BronzeFanoutSink, SourceRowConsumer

    value = source_row("PREF01N001")
    row_sink = _RecordingSink()
    cell_sink = _RecordingSink()
    calls: list[object] = []

    class Consumer:
        def consume(self, row: SourceRow) -> None:
            assert row_sink.rows
            assert len(cell_sink.rows) == len(value.cells)
            assert row is value
            calls.append(row)

    sink = BronzeFanoutSink(
        row_sink=row_sink,
        cell_sink=cell_sink,
        persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
        consumer=Consumer(),
    )

    sink.consume_source_row(value)

    assert calls == [value]
    assert tuple(inspect.signature(SourceRowConsumer.consume).parameters) == ("self", "row")
    assert tuple(inspect.signature(BronzeFanoutSink.consume_source_row).parameters) == (
        "self",
        "row",
    )


def test_bronze_uses_consumer_retained_rating_registry_without_reopening_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import bronze
    from finproof.data.artifacts.config import ArtifactInputKind
    from finproof.registry.rating import RatingRegistry

    opened: list[ArtifactInputKind] = []
    payloads = {
        ArtifactInputKind.SOURCE_MANIFEST: b"{}",
        ArtifactInputKind.SOURCE_SCHEMA_CATALOG: b"{}",
        ArtifactInputKind.ARTIFACT_BUILD_CONFIG: b"{}",
        ArtifactInputKind.DATASET_REGISTRY: (b'version: "1.0.0"\nsnapshot_date: "2026-07-11"\n'),
        ArtifactInputKind.QUALITY_RULE_REGISTRY: b'version: "1.0.0"\n',
        ArtifactInputKind.STATE_RULE_REGISTRY: b'version: "1.1.0"\n',
    }

    class Identity:
        @contextmanager
        def open_verified_input(self, *, kind: ArtifactInputKind):
            opened.append(kind)
            if kind is ArtifactInputKind.RATING_SCALE_REGISTRY:
                raise AssertionError("Bronze reopened the held-parsed rating registry")
            with io.BytesIO(payloads[kind]) as stream:
                yield stream

    class Manifest:
        def verify(self, source_root: object) -> None:
            del source_root
            raise RuntimeError("configuration boundary completed")

    class Session:
        _input_identity = Identity()
        _settings = type("SettingsStub", (), {"source_root": object()})()
        _versions = VersionBundle()

        def assert_live(self) -> None:
            return None

    rating = RatingRegistry(
        version="1.0.0",
        missing_tokens=("",),
        ratings={"AAA": 1},
        aliases={},
    )

    class Consumer:
        _held_rating_registry = rating

        def consume(self, row: SourceRow) -> None:
            del row

    monkeypatch.setattr(
        bronze.SourceFileManifest,  # type: ignore[attr-defined]
        "from_held_streams",
        lambda **_kwargs: Manifest(),
    )
    monkeypatch.setattr(
        bronze.ArtifactBuildConfig,  # type: ignore[attr-defined]
        "from_held_stream",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="configuration boundary completed"):
        bronze.ingest_bronze_for_session(Session(), consumer=Consumer())  # type: ignore[arg-type]

    assert ArtifactInputKind.RATING_SCALE_REGISTRY not in opened
    assert opened == [
        ArtifactInputKind.SOURCE_MANIFEST,
        ArtifactInputKind.SOURCE_SCHEMA_CATALOG,
        ArtifactInputKind.ARTIFACT_BUILD_CONFIG,
        ArtifactInputKind.DATASET_REGISTRY,
        ArtifactInputKind.QUALITY_RULE_REGISTRY,
        ArtifactInputKind.STATE_RULE_REGISTRY,
    ]
