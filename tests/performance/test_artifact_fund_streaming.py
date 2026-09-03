"""Closed architectural bounds for one-group Silver fund streaming."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.performance


def test_silver_fund_and_relation_pipeline_stays_within_closed_streaming_bounds(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession, ExternalOrderRelation
    from finproof.data.normalization.public_funds import normalize_public_fund_item
    from finproof.domain.public_funds import PublicFundItem
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
                "prfd_attr_cds": ",".join(f"C{attribute:03d}" for attribute in range(16)),
                "prfd_attr_cnt": "16",
            },
            excel_row=item + 2,
        )
        for item in range(1, 1601)
    )
    expected = tuple(
        result.record
        for row in rows
        if (result := normalize_public_fund_item(row)).record is not None
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

        batches = tuple(
            emitter._order_store.iter_ordered_batches(
                relation=ExternalOrderRelation.SILVER_FUND_ITEM
            )
        )
        observed = tuple(
            PublicFundItem.model_validate_json(staged.payload_json)
            for batch in batches
            for staged in batch
        )

        assert observed == expected
        assert emitter._max_live_fund_group_rows == 0
        assert max(map(len, batches)) <= 65_536
        assert source_iterations == 1
