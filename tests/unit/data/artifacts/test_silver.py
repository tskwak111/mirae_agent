"""One-pass Silver artifact emission contracts."""

# ruff: noqa: ANN001, ANN002, ANN003
# mypy: disable-error-code="arg-type,attr-defined,no-untyped-def,unreachable"

from __future__ import annotations

import hashlib
import json
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
        "bond_sale_lot": 1,
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
    }
    payload["quarantine_source_rows"] = 0
    return ArtifactBuildConfig.model_validate(payload, strict=True)


def test_refreshed_emitter_stages_bond_lots_by_parent_source_key_and_funds_directly(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession, ExternalOrderRelation
    from finproof.domain.bonds import BondSaleLot
    from finproof.domain.public_funds import PublicFundItem
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    registry = RatingRegistry.from_yaml(settings.repository_root / "config/rating_scale.yaml")
    rows = (
        source_row(
            "PRBD01N001",
            {
                "pd_no": "KR0000000001",
                "pd_exg_mkt": "장외",
                "info_base_dt": "20260822",
                "info_seq": "1",
            },
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601001", "ksd_itm_no": "KR7000000001"},
        ),
    )
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session, config=config, versions=versions, rating_registry=registry
        )
        for row in rows:
            emitter.consume(row)

        bond = next(
            emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.SILVER_BOND_SALE_LOT
            )
        )[0]
        fund = next(
            emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.SILVER_FUND_ITEM
            )
        )[0]
        assert bond.key == ("KR0000000001", "장외", "20260822", "1", 2)
        assert BondSaleLot.model_validate_json(bond.payload_json).source_row == rows[0]
        assert fund.key == ("KR5114601001", 2)
        assert PublicFundItem.model_validate_json(fund.payload_json).source_row == rows[1]


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
    from finproof.data.normalization.bonds import normalize_bond_lot
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
        source_row("PRBD01N001", {"pd_no": "KR0000000002"}),
        source_row("PREF01N001", {"pd_itm_no": "KR7000000002"}),
    )
    expected = (
        normalize_overseas_listed(rows[0]),
        normalize_bond_lot(rows[1], rating_registry),
        normalize_domestic_listed(rows[2], versions.dataset_version),
    )
    calls: list[tuple[str, object]] = []

    def wrapped_overseas(row):
        calls.append(("overseas", row))
        return normalize_overseas_listed(row)

    def wrapped_bond(row, registry):
        assert registry is rating_registry
        calls.append(("bond", row))
        return normalize_bond_lot(row, registry)

    def wrapped_domestic(row, as_of):
        assert as_of == versions.dataset_version
        calls.append(("domestic", row))
        return normalize_domestic_listed(row, as_of)

    monkeypatch.setattr(silver, "normalize_overseas_listed", wrapped_overseas)
    monkeypatch.setattr(silver, "normalize_bond_lot", wrapped_bond)
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
            ExternalOrderRelation.SILVER_BOND_SALE_LOT,
            ExternalOrderRelation.SILVER_DOMESTIC_LISTED_PRODUCT,
        )
        for relation, result in zip(relation_by_index, expected, strict=True):
            batches = tuple(emitter._order_store.iter_ordered_batches(relation=relation))
            assert len(batches) == 1
            assert len(batches[0]) == 1
            assert result.record is not None
            assert batches[0][0].payload_json == canonical_record_json(result.record)


def test_silver_emitter_stages_only_domestic_etf_exact_raw_identifier_candidates(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        DomesticExactLinkCandidate,
        ExactLinkIdentifierSource,
        ExternalOrderRelation,
    )
    from finproof.data.normalization.domestic_listed import normalize_domestic_listed
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    valid = source_row("PREF01N001", {"pd_itm_no": "KR7000000009"}, excel_row=2)
    excluded = (
        source_row(
            "PREF01N001",
            {"pd_itm_no": "RAW-ETN", "pd_grp_no": "ETN"},
            excel_row=3,
        ),
        source_row("PREF01N001", {"pd_itm_no": ""}, excel_row=4),
        source_row("PREF02N001", {"pd_itm_no": "RAW-OVERSEAS"}, excel_row=5),
    )
    normalized = normalize_domestic_listed(valid, versions.dataset_version)
    assert normalized.record is not None
    expected = DomesticExactLinkCandidate(
        left_product_id=str(normalized.record.product_id.normalized_value),
        source_product_type="ETF",
        identifier=ExactLinkIdentifierSource(
            raw_identifier=valid.cell("pd_itm_no").raw_value,
            locator=normalized.record.product_id.source,
        ),
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
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        for row in (valid, *excluded):
            emitter.consume(row)

        candidates = tuple(
            row
            for batch in emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE
            )
            for row in batch
        )
        assert candidates == (
            type(candidates[0])(
                key=("KR7000000009", str(normalized.record.product_id.normalized_value)),
                payload_json=canonical_record_json(expected),
            ),
        )


def test_silver_emitter_stages_fund_representative_and_every_equal_ordered_locator(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkIdentifierSource,
        ExternalOrderRelation,
        FundExactLinkCandidate,
    )
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rows = (
        source_row(
            "PRFD01N001",
            {
                "itm_no": "KR5114601001",
                "ksd_itm_no": "KR7000000009",
                "prfd_attr_cds": "A101,B101",
            },
            excel_row=2,
        ),
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
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        for row in rows:
            emitter.consume(row)
        staged_items = tuple(
            staged
            for batch in emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.SILVER_FUND_ITEM
            )
            for staged in batch
        )
        from finproof.domain.public_funds import PublicFundItem

        item = PublicFundItem.model_validate_json(staged_items[0].payload_json)
        expected = FundExactLinkCandidate(
            right_product_id=str(item.fund_item_id.normalized_value),
            identifiers=(
                ExactLinkIdentifierSource(
                    raw_identifier=item.ksd_id.raw_value,
                    locator=item.ksd_id.source,
                ),
            ),
        )
        candidates = tuple(
            row
            for batch in emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE
            )
            for row in batch
        )
        assert len(candidates) == 1
        assert candidates[0].key == (
            "KR7000000009",
            str(item.fund_item_id.normalized_value),
        )
        assert candidates[0].payload_json == canonical_record_json(expected)
        assert tuple(source.locator for source in expected.identifiers) == (item.ksd_id.source,)


def test_silver_emitter_retains_fund_item_but_skips_empty_exact_link_identifier_candidate(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession, ExternalOrderRelation
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    row = source_row(
        "PRFD01N001",
        {
            "itm_no": "KR5114601001",
            "ksd_itm_no": "",
            "prfd_attr_cds": "A101",
        },
        excel_row=2,
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
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        emitter.consume(row)

        funds = tuple(
            staged
            for batch in emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.SILVER_FUND_ITEM
            )
            for staged in batch
        )
        candidates = tuple(
            staged
            for batch in emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE
            )
            for staged in batch
        )

        assert len(funds) == 1
        assert candidates == ()


def test_issue_bearing_silver_build_uses_numeric_source_table_order_key_end_to_end(
    tmp_path: Path,
) -> None:
    import hashlib
    import json

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.source_rows import REFRESHED_BOND_COLUMNS
    from tests.helpers.xlsx import write_complete_bronze_repository, write_xlsx

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    issue_row = source_row("PRBD01N001", {"pd_no": '"'})
    workbook = settings.source_root / "data/PRBD01N001_data.xlsx"
    write_xlsx(workbook, rows=(REFRESHED_BOND_COLUMNS, issue_row.raw_payload))
    manifest_path = settings.source_root / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["files"] if item.get("table_id") == "PRBD01N001")
    payload = workbook.read_bytes()
    entry["size_bytes"] = len(payload)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    base_config = _silver_fixture_config(settings, versions)
    config_payload = base_config.model_dump(mode="python")
    config_payload["silver_counts"]["bond_instrument"] = 0
    config_payload["silver_counts"]["bond_sale_lot"] = 0
    config_payload["quarantine_source_rows"] = 1
    config = ArtifactBuildConfig.model_validate(config_payload, strict=True)
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

        assert result.quality_join_observations.total_issues == 1
        assert result.quality_join_observations.quarantined_source_row_count == 1
        assert result.quality_report.by_source_table[0].source_table == "PRBD01N001"


def test_silver_emitter_consumes_each_row_once_only_after_bronze_enqueue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import silver
    from finproof.data.artifacts.bronze import BronzeFanoutSink
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.normalization.bonds import normalize_bond_lot
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = _silver_fixture_config(settings, versions)
    rating_registry = RatingRegistry.from_yaml(
        settings.repository_root / "config/rating_scale.yaml"
    )
    row = source_row("PRBD01N001", {"pd_no": "KR0000000001"})
    row_sink = type(
        "Sink", (), {"rows": [], "enqueue": lambda self, value: self.rows.append(value)}
    )()
    cell_sink = type(
        "Sink", (), {"rows": [], "enqueue": lambda self, value: self.rows.append(value)}
    )()
    calls = 0

    def wrapped(source, registry):
        nonlocal calls
        assert row_sink.rows
        assert len(cell_sink.rows) == len(row.cells)
        assert source is row
        calls += 1
        return normalize_bond_lot(source, registry)

    monkeypatch.setattr(silver, "normalize_bond_lot", wrapped)
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
        source_row("PRFD01N001", {"itm_no": "KR5114601004", "prfd_attr_cds": "B"}, excel_row=5),
        source_row("PRFD01N001", {"itm_no": "KR5114601001", "prfd_attr_cds": "A"}, excel_row=2),
        source_row("PRFD01N001", {"itm_no": "KR5114601003", "prfd_attr_cds": "A"}, excel_row=4),
        source_row("PRFD01N001", {"itm_no": "KR5114601002", "prfd_attr_cds": "B"}, excel_row=3),
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
                relation=ExternalOrderRelation.SILVER_FUND_ITEM
            )
            for row in batch
        )
        assert tuple(row.key for row in ordered) == (
            ("KR5114601001", 2),
            ("KR5114601002", 3),
            ("KR5114601003", 4),
            ("KR5114601004", 5),
        )
        from finproof.data.normalization.public_funds import normalize_public_fund_item

        expected_by_key = {}
        for source in rows:
            normalized = normalize_public_fund_item(source)
            assert normalized.record is not None
            expected_by_key[(source.cell("itm_no").raw_value, source.source_row_number)] = (
                canonical_record_json(normalized.record)
            )
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


def test_silver_finalize_drains_relations_and_extends_exact_set_from_three_to_eleven(
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
            "silver_bond_sale_lot",
            "silver_bond_instrument",
            "silver_domestic_listed_product",
            "silver_overseas_listed_product",
            "silver_fund_item",
            "silver_quality_issue",
            "silver_product_holding",
            "silver_product_holding_coverage",
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

        assert tuple(
            name for name in SilverBuildResult.__annotations__ if not name.startswith("_")
        ) == (
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


def test_silver_result_preserves_exact_six_fields_and_retains_only_private_candidate_custody(
    tmp_path: Path,
) -> None:
    from dataclasses import fields

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter, SilverBuildResult
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateStoreCustody,
    )
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

        assert tuple(field.name for field in fields(SilverBuildResult)) == (
            "input_identity",
            "staged_tables",
            "observations",
            "quality_join_observations",
            "quality_report",
            "instrumentation",
        )
        assert not hasattr(result, "candidate_custody")
        issuance = object.__getattribute__(result, "_issuance")
        assert type(issuance.candidate_custody) is ExactLinkCandidateStoreCustody
        assert issuance.candidate_custody._owner is session
        assert tuple(session._live_external_order_stores.values()) == (emitter._order_store,)


def test_take_exact_link_candidate_store_is_same_result_instance_bound_and_one_use(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import (
        SilverArtifactEmitter,
        require_silver_build_result,
        take_exact_link_candidate_store,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateStoreCustody,
    )
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
        retained = result._issuance.candidate_custody

        custody = take_exact_link_candidate_store(silver_result=result)

        assert type(custody) is ExactLinkCandidateStoreCustody
        assert custody is retained
        assert result._issuance.candidate_custody is None
        assert require_silver_build_result(result) is result
        with pytest.raises(ValueError, match="already taken"):
            take_exact_link_candidate_store(silver_result=result)


def test_take_exact_link_candidate_store_rejects_copy_equal_forge_foreign_and_mutated_result_without_slot_move(  # noqa: E501
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.silver import (
        SilverArtifactEmitter,
        SilverBuildResult,
        take_exact_link_candidate_store,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateStoreCustody,
    )
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
        retained = result._issuance.candidate_custody

        forged = object.__new__(SilverBuildResult)
        for name in SilverBuildResult.__annotations__:
            object.__setattr__(forged, name, getattr(result, name))
        object.__setattr__(forged, "_issuance", result._issuance)
        with pytest.raises(ValueError, match=r"provenance|changed"):
            take_exact_link_candidate_store(silver_result=forged)
        assert result._issuance.candidate_custody is retained

        original_report = result.quality_report
        object.__setattr__(result, "quality_report", original_report.model_copy())
        with pytest.raises(ValueError, match=r"provenance|changed"):
            take_exact_link_candidate_store(silver_result=result)
        assert result._issuance.candidate_custody is retained
        object.__setattr__(result, "quality_report", original_report)

        foreign_context = session.open_external_order_store(config=config)
        foreign_store = foreign_context.__enter__()
        foreign = ExactLinkCandidateStoreCustody._issue(
            owner=session,
            store=foreign_store,
        )
        result._issuance.candidate_custody = foreign
        with pytest.raises(ValueError, match="changed"):
            take_exact_link_candidate_store(silver_result=result)
        assert result._issuance.candidate_custody is foreign
        result._issuance.candidate_custody = retained

        assert take_exact_link_candidate_store(silver_result=result) is retained


def test_silver_build_result_is_frozen_finalizer_issued_and_revalidates_predecessor_relationships(
    tmp_path: Path,
) -> None:
    import inspect
    from dataclasses import fields, is_dataclass, replace

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.bronze import BronzeBuildResult
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.parquet_io import StagedParquetSet
    from finproof.data.artifacts.reports import QualitySummaryReport
    from finproof.data.artifacts.silver import SilverArtifactEmitter, SilverBuildResult
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

        assert is_dataclass(SilverBuildResult)
        assert SilverBuildResult.__dataclass_params__.frozen is True
        assert SilverBuildResult.__dataclass_params__.init is False
        assert tuple(field.name for field in fields(SilverBuildResult)) == (
            "input_identity",
            "staged_tables",
            "observations",
            "quality_join_observations",
            "quality_report",
            "instrumentation",
        )
        assert tuple(inspect.signature(SilverBuildResult._issue_from_finalizer).parameters) == (
            "bronze_result",
            "staged_tables",
            "observations",
            "quality_join_observations",
            "quality_report",
            "instrumentation",
        )
        prefix = StagedParquetSet.from_verified(
            owner=session,
            verifications=result.staged_tables.verifications[:3],
        )
        fresh_bronze = BronzeBuildResult._issue(
            staged_tables=prefix,
            observations=bronze_result.observations,
            input_identity=bronze_result.input_identity,
        )
        with pytest.raises((ArtifactContractError, TypeError, ValueError)):
            SilverBuildResult._issue_from_finalizer(
                bronze_result=fresh_bronze,
                staged_tables=prefix,
                observations=result.observations,
                quality_join_observations=result.quality_join_observations,
                quality_report=result.quality_report,
                instrumentation=result.instrumentation,
            )
        with pytest.raises((TypeError, ValueError)):
            SilverBuildResult._issue_from_finalizer(
                bronze_result=fresh_bronze,
                staged_tables=result.staged_tables,
                observations=result.observations,
                quality_join_observations=result.quality_join_observations,
                quality_report=result.quality_report,
                instrumentation=replace(
                    result.instrumentation,
                    staged_relation_rows=(
                        *result.instrumentation.staged_relation_rows[:3],
                        replace(
                            result.instrumentation.staged_relation_rows[3],
                            observed=result.instrumentation.staged_relation_rows[3].observed + 1,
                        ),
                        result.instrumentation.staged_relation_rows[4],
                    ),
                ),
            )
        reconstructed_report = QualitySummaryReport.model_validate(
            result.quality_report.model_dump(mode="python"),
            strict=True,
        )
        assert reconstructed_report == result.quality_report
        assert reconstructed_report is not result.quality_report
        with pytest.raises((TypeError, ValueError)):
            SilverBuildResult._issue_from_finalizer(
                bronze_result=fresh_bronze,
                staged_tables=result.staged_tables,
                observations=result.observations,
                quality_join_observations=result.quality_join_observations,
                quality_report=reconstructed_report,
                instrumentation=result.instrumentation,
            )


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
        "SILVER_BOND_SALE_LOT",
        "SILVER_DOMESTIC_LISTED_PRODUCT",
        "SILVER_OVERSEAS_LISTED_PRODUCT",
        "SILVER_FUND_ITEM",
        "SILVER_QUALITY_ISSUE",
        "SILVER_PRODUCT_HOLDING",
        "SILVER_PRODUCT_HOLDING_COVERAGE",
    )
    staged = {item.name: item.observed for item in instrumentation.staged_relation_rows}
    assert staged["SILVER_PRODUCT_HOLDING"] == 0
    assert staged["SILVER_PRODUCT_HOLDING_COVERAGE"] == 3
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


def test_silver_finalizer_accepts_unstaged_malformed_fund_row_backed_by_quality_issue(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.source_rows import PUBLIC_FUND_COLUMNS
    from tests.helpers.xlsx import write_complete_bronze_repository, write_xlsx

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    malformed = source_row("PRFD01N001", {"itm_no": '"'}, excel_row=2)
    workbook = settings.source_root / "data/PRFD01N001_data.xlsx"
    write_xlsx(workbook, rows=(PUBLIC_FUND_COLUMNS, malformed.raw_payload))
    payload = workbook.read_bytes()
    manifest_path = settings.source_root / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["files"] if item["path"] == "data/PRFD01N001_data.xlsx")
    entry["size_bytes"] = len(payload)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    config_payload = _silver_fixture_config(settings, versions).model_dump(mode="python")
    config_payload["silver_counts"]["fund_item"] = 0
    config_payload["quarantine_source_rows"] = 1
    config = ArtifactBuildConfig.model_validate(config_payload, strict=True)

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

    staged = {item.name: item.observed for item in result.instrumentation.staged_relation_rows}
    assert result.instrumentation.source_consume_counts[-1].observed == 1
    assert staged["SILVER_FUND_ITEM"] == 0
    assert staged["SILVER_QUALITY_ISSUE"] == 1
    assert result.quality_join_observations.total_issues == 1
    assert tuple(
        (item.grain, item.count) for item in result.quality_report.excluded_silver_records
    ) == (("fund_item", 1),)


def test_silver_result_successor_validator_accepts_only_exact_registered_thirteen_table_successor(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.silver import (
        SilverArtifactEmitter,
        require_silver_build_result_successor,
    )
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
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
        prefix_verifications = result.staged_tables.verifications
        prefix_handles = result.staged_tables.handles
        specs = (
            TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"],
            TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"],
        )
        leaves = tuple(session.claim_parquet_leaf(spec) for spec in specs)
        for spec, leaf in zip(specs, leaves, strict=True):
            ParquetBatchWriter(spec, leaf).close()
        gold = tuple(
            verify_staged_parquet_table(owner=session, leaf=leaf, spec=spec)
            for spec, leaf in zip(specs, leaves, strict=True)
        )
        successor = result.staged_tables.extend_verified(
            owner=session,
            verifications=gold,
        )

        assert (
            require_silver_build_result_successor(
                silver_result=result,
                successor=successor,
            )
            is result
        )
        assert all(
            actual is expected
            for actual, expected in zip(
                successor.verifications[:11], prefix_verifications, strict=True
            )
        )
        assert all(
            actual is expected
            for actual, expected in zip(successor.handles[:11], prefix_handles, strict=True)
        )
