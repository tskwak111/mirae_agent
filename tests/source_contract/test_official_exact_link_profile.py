"""Derived official exact-link profile over the frozen source generation."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = [pytest.mark.source_contract, pytest.mark.slow]


def test_official_exact_link_profile_is_47_371_and_frozen_pair_bytes() -> None:
    from finproof.core.settings import Settings
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.builder import build_complete_for_session
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.source_manifest import SourceFileManifest
    from finproof.data.xlsx_stream import iter_xlsx_rows
    from tests.helpers.artifacts import artifact_build_input_identity

    repository_root = Path(__file__).resolve().parents[2]
    source_root = repository_root / "source_material"
    settings = Settings(
        repository_root=repository_root,
        source_root=source_root,
        data_dir=source_root / "data",
        artifact_dir=repository_root / "artifacts",
        database_path=repository_root / "artifacts/finproof.duckdb",
        artifact_build_config_path=repository_root / "config/artifact_build.yaml",
        expected_artifact_contract_path=(repository_root / "config/expected_phase1_artifacts.json"),
    )
    versions = VersionBundle()
    config = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=repository_root,
        versions=versions,
    )
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        result = build_complete_for_session(
            session=session,
            config=config,
            versions=versions,
        )

        assert len(result.exact_link_build_result.links) == 47
        assert len(result.exact_link_build_result.evidence) == 371
        assert len(result.exact_link_build_result.canonical_pair_tsv) == 1_222
        assert (
            result.exact_link_build_result.pair_sha256
            == "8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962"
        )

        verified = SourceFileManifest.load(
            source_root / "input_manifest.json",
            source_root / "schema_catalog.json",
        ).verify(source_root)
        domestic_ids: dict[str, str] = {}
        for row in iter_xlsx_rows(verified.data_file("PREF01N001")):
            domestic_ids[row.cell("pd_itm_no").raw_value] = row.cell("pd_grp_no").raw_value
        raw_fund_ids: dict[str, set[str]] = {}
        trimmed_fund_ids: dict[str, set[str]] = {}
        for row in iter_xlsx_rows(verified.data_file("PRFD01N001")):
            fund_item_id = row.cell("itm_no").raw_value
            raw_identifier = row.cell("ksd_itm_no").raw_value
            raw_fund_ids.setdefault(raw_identifier, set()).add(fund_item_id)
            trimmed_fund_ids.setdefault(raw_identifier.strip(), set()).add(fund_item_id)
        raw_pairs = {
            (domestic_id, fund_item_id)
            for domestic_id, product_type in domestic_ids.items()
            if product_type == "ETF"
            for fund_item_id in raw_fund_ids.get(domestic_id, ())
        }
        trimmed_pairs = {
            (domestic_id, fund_item_id)
            for domestic_id, product_type in domestic_ids.items()
            if product_type == "ETF"
            for fund_item_id in trimmed_fund_ids.get(domestic_id.strip(), ())
        }
        emitted_pairs = {
            (link.left_product_id, link.right_product_id)
            for link in result.exact_link_build_result.links
        }

        assert raw_pairs == trimmed_pairs == emitted_pairs
        assert (
            sum(
                domestic_ids[link.left_product_id] == "ETN"
                for link in result.exact_link_build_result.links
            )
            == 0
        )
