"""One-pass Silver artifact emission contracts."""

# ruff: noqa: ANN001, ANN002, ANN003
# mypy: disable-error-code="arg-type,attr-defined,no-untyped-def,unreachable"

from __future__ import annotations

from copy import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.helpers.source_rows import source_row

if TYPE_CHECKING:
    from finproof.core.settings import Settings
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig


def _silver_fixture_config(
    settings: Settings,
    versions: VersionBundle,
) -> ArtifactBuildConfig:
    from finproof.data.artifacts.config import ArtifactBuildConfig

    config = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    payload = config.model_dump(mode="python")
    payload["silver_counts"] = {
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
        "fund_item_attribute": 1,
    }
    payload["quarantine_source_rows"] = 0
    return ArtifactBuildConfig.model_validate(payload, strict=True)


def test_silver_emitter_factory_accepts_exact_live_session_and_held_rating_registry(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rating_registry = RatingRegistry.from_yaml(
        settings.repository_root / "config/rating_scale.yaml"
    )
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))

    with ArtifactBuildSession.initialize(
        settings,
        versions,
        options,
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=rating_registry,
        )

        assert type(emitter) is SilverArtifactEmitter
        assert emitter._session is session
        assert emitter._config is config
        assert emitter._versions is versions
        assert emitter._held_rating_registry is rating_registry


def test_silver_emitter_uses_exact_nonfund_normalizers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import silver
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderRelation,
    )
    from finproof.data.normalization.bonds import normalize_bond
    from finproof.data.normalization.domestic_listed import normalize_domestic_listed
    from finproof.data.normalization.overseas_listed import normalize_overseas_listed
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rating_registry = RatingRegistry.from_yaml(
        settings.repository_root / "config/rating_scale.yaml"
    )
    rows = (
        source_row("PREF02N001"),
        source_row("PRBD01N001", {"PD_NO": "KR0000000002"}),
        source_row("PREF01N001", {"pd_itm_no": "KR7000000002"}),
    )
    expected = (
        normalize_overseas_listed(rows[0]),
        normalize_bond(rows[1], versions.dataset_version, rating_registry),
        normalize_domestic_listed(rows[2], versions.dataset_version),
    )
    calls: list[tuple[str, object]] = []

    def wrapped_overseas(row):
        calls.append(("overseas", row))
        return normalize_overseas_listed(row)

    def wrapped_bond(row, as_of, registry):
        assert as_of == versions.dataset_version
        assert registry is rating_registry
        calls.append(("bond", row))
        return normalize_bond(row, as_of, registry)

    def wrapped_domestic(row, as_of):
        assert as_of == versions.dataset_version
        calls.append(("domestic", row))
        return normalize_domestic_listed(row, as_of)

    monkeypatch.setattr(silver, "normalize_overseas_listed", wrapped_overseas)
    monkeypatch.setattr(silver, "normalize_bond", wrapped_bond)
    monkeypatch.setattr(silver, "normalize_domestic_listed", wrapped_domestic)

    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = silver.SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=rating_registry,
        )
        for row in rows:
            emitter.consume(row)

        assert calls == [
            ("overseas", rows[0]),
            ("bond", rows[1]),
            ("domestic", rows[2]),
        ]
        relation_by_index = (
            ExternalOrderRelation.SILVER_OVERSEAS_LISTED_PRODUCT,
            ExternalOrderRelation.SILVER_BOND_INSTRUMENT,
            ExternalOrderRelation.SILVER_DOMESTIC_LISTED_PRODUCT,
        )
        for relation, result in zip(relation_by_index, expected, strict=True):
            batches = tuple(emitter._order_store.iter_ordered_batches(relation=relation))
            assert len(batches) == 1
            assert len(batches[0]) == 1
            assert result.record is not None
            assert batches[0][0].payload_json == canonical_record_json(result.record)


def test_silver_emitter_consumes_each_row_once_only_after_bronze_enqueue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import silver
    from finproof.data.artifacts.bronze import BronzeFanoutSink
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.normalization.bonds import normalize_bond
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rating_registry = RatingRegistry.from_yaml(
        settings.repository_root / "config/rating_scale.yaml"
    )
    row = source_row("PRBD01N001")
    row_sink = type(
        "Sink", (), {"rows": [], "enqueue": lambda self, value: self.rows.append(value)}
    )()
    cell_sink = type(
        "Sink", (), {"rows": [], "enqueue": lambda self, value: self.rows.append(value)}
    )()
    calls = 0

    def wrapped(source, as_of, registry):
        nonlocal calls
        assert row_sink.rows
        assert len(cell_sink.rows) == len(row.cells)
        assert source is row
        calls += 1
        return normalize_bond(source, as_of, registry)

    monkeypatch.setattr(silver, "normalize_bond", wrapped)
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = silver.SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=rating_registry,
        )
        BronzeFanoutSink(
            row_sink=row_sink,
            cell_sink=cell_sink,
            persistence_timestamp=session.persistence_timestamp,
            consumer=emitter,
        ).consume_source_row(row)

    assert calls == 1


def test_silver_emitter_stages_fund_keys_and_keeps_only_one_group_live(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderRelation,
    )
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rating_registry = RatingRegistry.from_yaml(
        settings.repository_root / "config/rating_scale.yaml"
    )
    rows = (
        source_row("PRFD01N001", {"itm_no": "KR5114601002", "prfd_attr_cd": "B"}, excel_row=5),
        source_row("PRFD01N001", {"itm_no": "KR5114601001", "prfd_attr_cd": "A"}, excel_row=2),
        source_row("PRFD01N001", {"itm_no": "KR5114601002", "prfd_attr_cd": "A"}, excel_row=4),
        source_row("PRFD01N001", {"itm_no": "KR5114601001", "prfd_attr_cd": "B"}, excel_row=3),
    )

    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=rating_registry,
        )
        for row in rows:
            emitter.consume(row)

        ordered = tuple(
            row
            for batch in emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW
            )
            for row in batch
        )
        assert tuple(row.key for row in ordered) == (
            ("KR5114601001", 2),
            ("KR5114601001", 3),
            ("KR5114601002", 4),
            ("KR5114601002", 5),
        )
        expected_by_key = {
            (row.cell("itm_no").raw_value, row.source_row_number): canonical_record_json(row)
            for row in rows
        }
        assert tuple(row.payload_json for row in ordered) == tuple(
            expected_by_key[row.key]  # type: ignore[index]
            for row in ordered
        )
        assert not hasattr(emitter, "_fund_rows")
        assert not hasattr(emitter, "_fund_groups")
        assert not hasattr(emitter, "_source_rows")


def test_silver_finalize_requires_exact_bronze_result_owner_input_set_observations_and_timestamp(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.bronze import BronzeBuildResult
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rating_registry = RatingRegistry.from_yaml(
        settings.repository_root / "config/rating_scale.yaml"
    )
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=rating_registry,
        )
        bronze_result = session.ingest_bronze(consumer=emitter)
        with pytest.raises(TypeError):
            copy(bronze_result)
        forged = object.__new__(BronzeBuildResult)
        object.__setattr__(forged, "staged_tables", bronze_result.staged_tables)
        object.__setattr__(forged, "observations", bronze_result.observations)
        object.__setattr__(forged, "input_identity", object())

        for invalid in (object(), forged):
            with pytest.raises((TypeError, ValueError)):
                emitter.finalize(bronze_result=invalid)

        result = emitter.finalize(bronze_result=bronze_result)
        assert result.input_identity is bronze_result.input_identity


def test_silver_finalize_drains_relations_and_extends_exact_set_from_three_to_nine(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rating_registry = RatingRegistry.from_yaml(
        settings.repository_root / "config/rating_scale.yaml"
    )
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=rating_registry,
        )
        bronze_result = session.ingest_bronze(consumer=emitter)

        result = emitter.finalize(bronze_result=bronze_result)
        assert result.staged_tables is emitter._staged_tables

        emitter._staged_tables.assert_live()
        assert tuple(
            verification.logical.name for verification in emitter._staged_tables.verifications
        ) == (
            "bronze_source_column",
            "bronze_source_row",
            "bronze_source_cell",
            "silver_bond_instrument",
            "silver_domestic_listed_product",
            "silver_overseas_listed_product",
            "silver_fund_item",
            "silver_fund_item_attribute",
            "silver_quality_issue",
        )


def test_silver_finalize_faults_issue_no_result_and_leave_cleanup_with_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        bronze_result = session.ingest_bronze(consumer=emitter)

        def fail_drain(*args, **kwargs):
            del args, kwargs
            raise RuntimeError("injected Silver drain failure")

        monkeypatch.setattr(SilverArtifactEmitter, "_drain_model_relation", fail_drain)
        with pytest.raises(RuntimeError, match="injected Silver drain failure"):
            emitter.finalize(bronze_result=bronze_result)

        assert emitter._staged_tables is None
        session.assert_live()
        assert session._live_parquet_writers == {}
        assert tuple(session._live_external_order_stores.values()) == (emitter._order_store,)


def test_silver_build_result_is_factory_only_with_exact_six_field_order_and_object_identity(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import (
        SilverArtifactEmitter,
        SilverBuildResult,
        require_silver_build_result,
    )
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        bronze_result = session.ingest_bronze(consumer=emitter)
        result = emitter.finalize(bronze_result=bronze_result)

        assert tuple(SilverBuildResult.__annotations__) == (
            "input_identity",
            "staged_tables",
            "observations",
            "quality_join_observations",
            "quality_report",
            "instrumentation",
        )
        assert result.input_identity is bronze_result.input_identity
        assert result.staged_tables is emitter._staged_tables
        assert result.observations is emitter._observations
        assert result.quality_join_observations is emitter._quality_join_observations
        assert result.quality_report is emitter._quality_report
        assert result.instrumentation is emitter._instrumentation
        assert require_silver_build_result(result) is result
        with pytest.raises(TypeError):
            SilverBuildResult()
        with pytest.raises(TypeError):
            copy(result)

        forged = object.__new__(SilverBuildResult)
        for name in SilverBuildResult.__annotations__:
            object.__setattr__(forged, name, getattr(result, name))
        for invalid in (forged, object()):
            with pytest.raises((TypeError, ValueError)):
                require_silver_build_result(invalid)

        original_report = result.quality_report
        object.__setattr__(result, "quality_report", original_report.model_copy())
        with pytest.raises(ValueError, match="issuance changed"):
            require_silver_build_result(result)
        object.__setattr__(result, "quality_report", original_report)
        assert require_silver_build_result(result) is result


def test_silver_instrumentation_has_exact_names_counts_and_bounds(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import (
        NamedObservedCount,
        SilverArtifactEmitter,
        SilverBuildInstrumentation,
    )
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        bronze_result = session.ingest_bronze(consumer=emitter)
        instrumentation = emitter.finalize(bronze_result=bronze_result).instrumentation

    assert type(instrumentation) is SilverBuildInstrumentation
    assert instrumentation.source_rows_consumed == 4
    assert tuple(item.name for item in instrumentation.source_consume_counts) == (
        "PRBD01N001",
        "PREF01N001",
        "PREF02N001",
        "PRFD01N001",
    )
    assert tuple(item.observed for item in instrumentation.source_consume_counts) == (
        1,
        1,
        1,
        1,
    )
    assert instrumentation.normalizer_call_counts == instrumentation.source_consume_counts
    assert tuple(item.name for item in instrumentation.staged_relation_rows) == (
        "SILVER_BOND_INSTRUMENT",
        "SILVER_DOMESTIC_LISTED_PRODUCT",
        "SILVER_OVERSEAS_LISTED_PRODUCT",
        "PUBLIC_FUND_SOURCE_ROW",
        "SILVER_QUALITY_ISSUE",
    )
    assert 0 <= instrumentation.max_live_fund_group_rows <= 16
    assert 0 <= instrumentation.max_writer_batch_rows <= 65_536
    assert 0 <= instrumentation.max_relation_batch_rows <= 65_536

    with pytest.raises((TypeError, ValueError)):
        NamedObservedCount(name="PRBD01N001", observed=True)
    with pytest.raises((TypeError, ValueError)):
        SilverBuildInstrumentation(
            source_rows_consumed=4,
            source_consume_counts=instrumentation.source_consume_counts[::-1],
            normalizer_call_counts=instrumentation.normalizer_call_counts,
            staged_relation_rows=instrumentation.staged_relation_rows,
            max_live_fund_group_rows=0,
            max_writer_batch_rows=0,
            max_relation_batch_rows=0,
        )
