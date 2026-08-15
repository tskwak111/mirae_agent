"""One-pass Bronze artifact ingestion contracts."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast

from finproof.core.settings import Settings
from finproof.data.artifacts.input_identity import BuildInputIdentity
from finproof.data.artifacts.parquet_io import (
    OwnedStageArtifactOwner,
    OwnedStageParquetLeaf,
    StagedParquetSet,
)
from finproof.data.artifacts.reports import BronzeSourceAuditObservations
from finproof.data.artifacts.serialization import serialize_bronze_source_row, validate_physical_row
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TableSpec
from finproof.data.source_manifest import (
    OFFICIAL_TABLE_IDS,
    SourceFileManifest,
    SourceSchemaCatalog,
)
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.source import SourceRow


class _BronzeRowSink(Protocol):
    def enqueue(self, row: Mapping[str, object]) -> None: ...


class _BronzeBatchWriter(Protocol):
    def write_batch(self, rows: Sequence[Mapping[str, object]]) -> None: ...

    def close(self) -> None: ...

    def abort(self) -> None: ...


class _BronzeSession(OwnedStageArtifactOwner, Protocol):
    _input_identity: BuildInputIdentity
    _settings: Settings

    def claim_parquet_leaf(self, spec: TableSpec) -> OwnedStageParquetLeaf: ...


class BoundedBronzeBatchSink:
    """Flush caller rows in fixed-size insertion-order batches without retention."""

    def __init__(
        self,
        *,
        writer: _BronzeBatchWriter,
        batch_limit: int,
        table_name: str,
    ) -> None:
        if type(batch_limit) is not int or not 1 <= batch_limit <= 65_536:
            raise ValueError("batch_limit must be in 1..65536")
        if table_name not in {
            "bronze_source_column",
            "bronze_source_row",
            "bronze_source_cell",
        }:
            raise ValueError("table_name must be a Bronze table")
        self._writer = writer
        self._batch_limit = batch_limit
        self._rows: list[Mapping[str, object]] = []
        self._closed = False

    def enqueue(self, row: Mapping[str, object]) -> None:
        if self._closed:
            raise ValueError("Bronze batch sink is closed")
        self._rows.append(row)
        if len(self._rows) == self._batch_limit:
            self._flush()

    def close(self) -> None:
        if self._closed:
            return
        self._flush()
        self._writer.close()
        self._closed = True

    def _flush(self) -> None:
        if not self._rows:
            return
        batch = tuple(self._rows)
        self._writer.write_batch(batch)
        self._rows.clear()


class SourceRowConsumer(Protocol):
    """One-pass downstream consumer of an already-enqueued exact source row."""

    def consume(self, row: SourceRow) -> None: ...


class BronzeFanoutSink:
    """Enqueue one complete Bronze lineage row before optional downstream fan-out."""

    def __init__(
        self,
        *,
        row_sink: _BronzeRowSink,
        cell_sink: _BronzeRowSink | None,
        persistence_timestamp: datetime,
        consumer: SourceRowConsumer | None,
    ) -> None:
        self._row_sink = row_sink
        self._cell_sink = cell_sink
        self._persistence_timestamp = persistence_timestamp
        self._consumer = consumer

    def consume_source_row(self, row: SourceRow) -> None:
        if type(row) is not SourceRow:
            raise TypeError("Bronze fan-out requires an exact SourceRow")
        projected = serialize_bronze_source_row(
            TABLE_SPEC_BY_NAME["bronze_source_row"],
            row,
            persistence_timestamp=self._persistence_timestamp,
        )
        self._row_sink.enqueue(projected)
        if self._cell_sink is not None:
            table_order = OFFICIAL_TABLE_IDS.index(row.source_table)
            spec = TABLE_SPEC_BY_NAME["bronze_source_cell"]
            for cell in row.cells:
                projected_cell: dict[str, object] = {
                    "source_table_order": table_order,
                    "source_table": row.source_table,
                    "source_file": row.source_file.as_posix(),
                    "source_sheet": row.source_sheet,
                    "source_row_number": row.source_row_number,
                    "source_column_name": cell.column_name,
                    "source_column_number": cell.excel_column_number,
                    "source_column_letter": cell.excel_column_letter,
                    "source_checksum": row.source_checksum,
                    "source_snapshot_date": row.source_snapshot_date,
                    "source_applicable_date": cell.applicable_date,
                    "raw_value": cell.raw_value,
                }
                validate_physical_row(spec, projected_cell)
                self._cell_sink.enqueue(projected_cell)
        if self._consumer is not None:
            self._consumer.consume(row)


def _excel_column_letter(number: int) -> str:
    letters: list[str] = []
    remaining = number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def iter_bronze_columns(
    catalog: SourceSchemaCatalog,
) -> Iterator[Mapping[str, object]]:
    """Yield the complete frozen source catalog in exact table/column order."""
    if type(catalog) is not SourceSchemaCatalog:
        raise TypeError("catalog must be an exact SourceSchemaCatalog")
    for table_order, table_id in enumerate(OFFICIAL_TABLE_IDS):
        table = catalog.tables[table_id]
        for column_number, column in enumerate(table.columns, start=1):
            yield {
                "catalog_version": catalog.catalog_version,
                "source_snapshot_date": catalog.snapshot_date,
                "source_table_order": table_order,
                "source_table": table_id,
                "source_column_number": column_number,
                "source_column_letter": _excel_column_letter(column_number),
                "source_column_name": column.column_name,
                "source_declared_type": column.column_type,
                "source_example": column.example,
                "source_key_marker": column.key,
                "source_name_ko": column.name_ko,
                "schema_file": table.schema_file,
                "schema_excel_row": column.schema_excel_row,
            }


@dataclass(frozen=True, init=False, slots=True)
class BronzeBuildResult:
    """Builder-issued result carrying the exact three-table Bronze state."""

    staged_tables: StagedParquetSet
    observations: BronzeSourceAuditObservations
    input_identity: BuildInputIdentity

    def __new__(cls, *args: object, **kwargs: object) -> BronzeBuildResult:
        del args, kwargs
        raise TypeError("BronzeBuildResult is builder-issued")

    @classmethod
    def _issue(
        cls,
        *,
        staged_tables: StagedParquetSet,
        observations: BronzeSourceAuditObservations,
        input_identity: BuildInputIdentity,
    ) -> BronzeBuildResult:
        value = object.__new__(cls)
        object.__setattr__(value, "staged_tables", staged_tables)
        object.__setattr__(value, "observations", observations)
        object.__setattr__(value, "input_identity", input_identity)
        return value


def ingest_bronze_for_session(
    session: _BronzeSession,
    *,
    consumer: SourceRowConsumer | None = None,
) -> BronzeBuildResult:
    """Stream the complete verified source set once into three staged Parquets."""
    from finproof.data.artifacts.config import ArtifactInputKind
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.reports import (
        BronzeSourceAuditObservations,
        SourceTableAudit,
    )

    session.assert_live()
    identity = session._input_identity
    with (
        identity.open_verified_input(kind=ArtifactInputKind.SOURCE_MANIFEST) as manifest_stream,
        identity.open_verified_input(
            kind=ArtifactInputKind.SOURCE_SCHEMA_CATALOG
        ) as catalog_stream,
    ):
        manifest = SourceFileManifest.from_held_streams(
            manifest_stream=manifest_stream,
            schema_catalog_stream=catalog_stream,
        )
    sources = manifest.verify(session._settings.source_root)
    specs = tuple(
        TABLE_SPEC_BY_NAME[name]
        for name in (
            "bronze_source_column",
            "bronze_source_row",
            "bronze_source_cell",
        )
    )
    leaves = tuple(session.claim_parquet_leaf(spec) for spec in specs)
    writers: list[ParquetBatchWriter] = []
    sinks: list[BoundedBronzeBatchSink] = []
    try:
        for spec, leaf in zip(specs, leaves, strict=True):
            writer = ParquetBatchWriter(spec, leaf)
            writers.append(writer)
            sinks.append(
                BoundedBronzeBatchSink(
                    writer=writer,
                    batch_limit=65_536,
                    table_name=spec.table_name,
                )
            )
        for column in iter_bronze_columns(manifest.schema_catalog):
            sinks[0].enqueue(column)
        fanout = BronzeFanoutSink(
            row_sink=sinks[1],
            cell_sink=sinks[2],
            persistence_timestamp=session.persistence_timestamp,
            consumer=consumer,
        )
        observed_rows: dict[str, int] = {}
        for source in sources.data_files:
            row_count = 0
            for row in iter_xlsx_rows(source):
                fanout.consume_source_row(row)
                row_count += 1
            observed_rows[source.table_id] = row_count
        for sink in sinks:
            sink.close()
        writers.clear()
        verifications = tuple(
            verify_staged_parquet_table(owner=session, leaf=leaf, spec=spec)
            for spec, leaf in zip(specs, leaves, strict=True)
        )
        staged_tables = StagedParquetSet.from_verified(
            owner=session,
            verifications=verifications,
        )
        source_tables = tuple(
            SourceTableAudit(
                source_table=cast(
                    Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"],
                    source.table_id,
                ),
                expected_rows=source.expected_rows,
                observed_rows=observed_rows[source.table_id],
                expected_columns=source.expected_columns,
                observed_columns=source.expected_columns,
                expected_cells=source.expected_rows * source.expected_columns,
                observed_cells=observed_rows[source.table_id] * source.expected_columns,
            )
            for source in sources.data_files
        )
        observations = BronzeSourceAuditObservations.from_bronze(
            source_snapshot_date=manifest.snapshot_date,
            source_manifest_sha256=identity.source_manifest_sha256,
            schema_catalog_sha256=identity.schema_catalog_sha256,
            source_tables=source_tables,
        )
        return BronzeBuildResult._issue(
            staged_tables=staged_tables,
            observations=observations,
            input_identity=identity,
        )
    except BaseException:
        for sink in reversed(sinks):
            if not sink._closed:
                with contextlib.suppress(BaseException):
                    sink._writer.abort()
        raise
