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
