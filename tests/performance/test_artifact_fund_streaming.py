"""Closed architectural bounds for one-group Silver fund streaming."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.performance


def test_silver_fund_and_relation_pipeline_stays_within_closed_streaming_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.normalization import public_funds
    from finproof.data.normalization.public_funds import normalize_public_fund_item_group
    from finproof.domain.source import SourceRow
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.source_rows import source_row
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    config = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    rows = tuple(
        source_row(
            "PRFD01N001",
            {
                "itm_no": f"KR{item:010d}",
                "prfd_attr_cd": f"C{attribute:03d}",
            },
            excel_row=item * 16 + attribute + 2,
        )
        for item in range(1, 101)
        for attribute in range(16)
    )
    expected = tuple(
        normalize_public_fund_item_group(rows[offset : offset + 16])
        for offset in range(0, len(rows), 16)
    )
    source_iterations = 0

    class OnePassRows:
        def __iter__(self) -> Iterator[SourceRow]:
            nonlocal source_iterations
            if source_iterations:
                raise AssertionError("source rows were iterated twice")
            source_iterations += 1
            yield from reversed(rows[::2])
            yield from reversed(rows[1::2])

        def __len__(self) -> int:
            raise AssertionError("source rows must not be sized")

    monkeypatch.setattr(
        public_funds,
        "normalize_public_funds",
        lambda *_args, **_kwargs: pytest.fail("global public-fund collapse was called"),
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
        for row in OnePassRows():
            emitter.consume(row)

        observed = tuple(emitter._iter_normalized_fund_groups())

        assert observed == expected
        assert emitter._max_live_fund_group_rows <= 16
        assert emitter._max_relation_batch_rows <= 65_536
        assert source_iterations == 1
