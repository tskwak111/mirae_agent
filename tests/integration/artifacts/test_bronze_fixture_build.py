# mypy: disable-error-code="attr-defined,no-untyped-def"
"""End-to-end one-pass Bronze fixture staging contracts."""

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from copy import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from finproof.core.settings import Settings
from finproof.data.source_manifest import VerifiedSourceFile
from finproof.domain.source import SourceRow
from tests.helpers.xlsx import write_complete_bronze_repository


def _build_identity(settings: Settings):
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        seal = held.issue_identity_seal()
    return BuildInputIdentity.from_verified(seal=seal)


def test_bronze_ingestion_opens_and_iterates_each_workbook_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import bronze
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = write_complete_bronze_repository(tmp_path / "repository")
    identity = _build_identity(settings)
    real_iter = bronze.iter_xlsx_rows
    opened: Counter[str] = Counter()

    def iter_once(source: VerifiedSourceFile) -> Iterator[SourceRow]:
        opened[source.table_id] += 1
        if opened[source.table_id] > 1:
            raise AssertionError("official workbook was opened twice")
        yield from real_iter(source)

    monkeypatch.setattr(bronze, "iter_xlsx_rows", iter_once)
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        options,
        input_identity=identity,
    ) as session:
        result = session.ingest_bronze()
        result.staged_tables.assert_live()
        assert tuple(
            verification.logical.name for verification in result.staged_tables.verifications
        ) == (
            "bronze_source_column",
            "bronze_source_row",
            "bronze_source_cell",
        )
        assert tuple(
            verification.logical.row_count for verification in result.staged_tables.verifications
        ) == (207, 4, 207)

    assert opened == {
        "PRBD01N001": 1,
        "PREF01N001": 1,
        "PREF02N001": 1,
        "PRFD01N001": 1,
    }


def test_bronze_ingestion_accepts_none_consumer_without_rescan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import bronze
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = write_complete_bronze_repository(tmp_path / "repository")
    identity = _build_identity(settings)
    real_iter = bronze.iter_xlsx_rows
    opened: Counter[str] = Counter()

    def one_pass(source: VerifiedSourceFile) -> Iterator[SourceRow]:
        opened[source.table_id] += 1
        if opened[source.table_id] != 1:
            raise AssertionError("Bronze-only build rescanned a workbook")
        yield from real_iter(source)

    monkeypatch.setattr(bronze, "iter_xlsx_rows", one_pass)
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        options,
        input_identity=identity,
    ) as session:
        result = session.ingest_bronze(consumer=None)
        result.staged_tables.assert_live()

    assert opened == Counter(
        dict.fromkeys(("PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"), 1)
    )


def test_bronze_result_retains_exact_session_build_input_identity(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = write_complete_bronze_repository(tmp_path / "repository")
    identity = _build_identity(settings)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=identity,
    ) as session:
        result = session.ingest_bronze()
        assert result.input_identity is identity
        assert not hasattr(result, "logical_inputs")
        assert not hasattr(result, "source_manifest_sha256")
        assert not hasattr(result, "schema_catalog_sha256")
        with pytest.raises(TypeError):
            copy(result)


@pytest.mark.parametrize("case", ["serialization", "checksum", "count", "consumer"])
def test_bronze_failure_aborts_once_without_retry_or_published_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from finproof.core.errors import SourceContractError, SourceErrorCode
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import bronze
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = write_complete_bronze_repository(tmp_path / "repository")
    identity = _build_identity(settings)
    real_sink_init = bronze.BoundedBronzeBatchSink.__init__
    real_iter = bronze.iter_xlsx_rows
    real_abort = ArtifactBuildSession._abort_initial_stage
    aborts = 0
    consumer_calls = 0

    def small_batch_init(
        self: Any,
        *,
        writer: Any,
        batch_limit: int,
        table_name: str,
    ) -> None:
        del batch_limit
        real_sink_init(self, writer=writer, batch_limit=1, table_name=table_name)

    def abort_once(self: Any) -> None:
        nonlocal aborts
        aborts += 1
        return real_abort(self)

    monkeypatch.setattr(bronze.BoundedBronzeBatchSink, "__init__", small_batch_init)
    monkeypatch.setattr(ArtifactBuildSession, "_abort_initial_stage", abort_once)

    if case == "serialization":
        real_write = ParquetBatchWriter.write_batch
        writes = 0

        def fail_second_write(
            self: Any,
            rows: Sequence[Mapping[str, object]],
        ) -> None:
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("injected serialization failure")
            return real_write(self, rows)

        monkeypatch.setattr(ParquetBatchWriter, "write_batch", fail_second_write)
    elif case in {"checksum", "count"}:

        def fail_after_one_row(source: VerifiedSourceFile) -> Iterator[SourceRow]:
            rows = real_iter(source)
            row = next(rows)
            yield row
            if case == "checksum":
                payload = bytearray(source.verified_absolute_path.read_bytes())
                payload[payload.index(b"PK\x01\x02") + 4] ^= 1
                source.verified_absolute_path.write_bytes(payload)
                yield from rows
            raise SourceContractError(
                SourceErrorCode.ROW_COUNT_MISMATCH,
                "injected fixture count mismatch",
                table_id=source.table_id,
            )

        monkeypatch.setattr(bronze, "iter_xlsx_rows", fail_after_one_row)

    class Consumer:
        def consume(self, row: SourceRow) -> None:
            nonlocal consumer_calls
            del row
            consumer_calls += 1
            if case == "consumer":
                raise RuntimeError("injected consumer failure")

    with (
        pytest.raises((OSError, RuntimeError, SourceContractError)),
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=identity,
        ) as session,
    ):
        session.ingest_bronze(consumer=Consumer())

    assert aborts == 1
    assert consumer_calls <= 1
    assert not settings.artifact_dir.exists()
    assert not tuple(
        path for path in settings.repository_root.iterdir() if "finproof-stage" in path.name
    )
