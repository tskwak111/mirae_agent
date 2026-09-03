"""Official artifact entity-resolution and exact-link profile."""

from tests.helpers.official_artifact_subprocess import OfficialArtifactSession


def test_official_resolution_and_exact_link_profile_is_217(
    official_artifact_session: OfficialArtifactSession,
) -> None:
    from finproof.entity import ExactCrossSourceLinkRepository

    assert hasattr(ExactCrossSourceLinkRepository, "all_links")

    from tests.helpers.query_runtime import verified_artifacts

    from finproof.core.settings import ExecutionMode
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.database import open_read_only_database
    from finproof.domain.query_plan import EntityMention, ProductType
    from finproof.entity import EntityIndex, EntityResolver, ResolutionMatchKind
    from finproof.registry.loader import RegistryBundle
    from finproof.runtime.session import RuntimeArtifactSession

    official = official_artifact_session
    verified = verified_artifacts()
    registries = RegistryBundle.from_package()
    versions = VersionBundle.from_runtime(
        verified=verified,
        registries=registries,
        execution_mode=ExecutionMode.EVALUATION,
    )
    session = RuntimeArtifactSession._issue(
        connection=open_read_only_database(official.root / "finproof.duckdb"),
        verified=verified,
        registries=registries,
        versions=versions,
    )
    try:
        resolver = EntityResolver(EntityIndex.from_session(session))
        links = ExactCrossSourceLinkRepository(session).all_links()
        assert len(links) == 217
        assert len({(link.left_product_id, link.right_product_id) for link in links}) == 217

        first = links[0]
        left = resolver.resolve(
            EntityMention(text=first.matched_raw_identifier),
            product_types=(ProductType.DOMESTIC_ETF,),
        )
        right = resolver.resolve(
            EntityMention(text=first.matched_raw_identifier),
            product_types=(ProductType.PUBLIC_FUND,),
        )
        combined = resolver.resolve(
            EntityMention(text=first.matched_raw_identifier),
            product_types=(ProductType.DOMESTIC_ETF, ProductType.PUBLIC_FUND),
        )
        assert left.selected is not None
        assert left.selected.product_id == first.left_product_id
        assert left.selected.match_kind is ResolutionMatchKind.EXACT_PRODUCT_ID
        assert right.selected is not None
        assert right.selected.product_id == first.right_product_id
        assert right.selected.match_kind is ResolutionMatchKind.EXACT_IDENTIFIER
        assert combined.selected == left.selected
    finally:
        session._close()
