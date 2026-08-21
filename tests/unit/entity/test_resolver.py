"""Focused deterministic entity index and resolver tests."""

import inspect
from decimal import Decimal
from typing import Self

from tests.helpers.query_runtime import verified_artifacts

from finproof.core.settings import ExecutionMode
from finproof.core.versions import VersionBundle
from finproof.entity.index import EntityIndex, _IndexedProduct
from finproof.registry.loader import RegistryBundle
from finproof.runtime.session import RuntimeArtifactSession


def _runtime_session(connection: object) -> RuntimeArtifactSession:
    verified = verified_artifacts()
    registries = RegistryBundle.from_package()
    versions = VersionBundle.from_runtime(
        verified=verified,
        registries=registries,
        execution_mode=ExecutionMode.EVALUATION,
    )
    return RuntimeArtifactSession._issue(
        connection=connection,  # type: ignore[arg-type]
        verified=verified,
        registries=registries,
        versions=versions,
    )


def _index(
    *entries: tuple[str, str, str, tuple[str, ...], tuple[str, ...]],
) -> EntityIndex:
    from finproof.domain.query_plan import EntityIdentifierType, ProductType
    from finproof.entity.normalization import normalize_product_text

    return EntityIndex._from_entries(
        tuple(
            _IndexedProduct(
                product_id=product_id,
                product_type=ProductType(product_type),
                name=name,
                identifiers=tuple(
                    (kind, normalize_product_text(value))
                    for kind, value in zip(
                        (
                            EntityIdentifierType.PRODUCT_ID,
                            EntityIdentifierType.MARKET_IDENTIFIER,
                            EntityIdentifierType.ISIN,
                            EntityIdentifierType.TICKER,
                        ),
                        identifiers,
                        strict=False,
                    )
                ),
                names=tuple(normalize_product_text(value) for value in names),
            )
            for product_id, product_type, name, identifiers, names in entries
        )
    )


def test_entity_index_uses_only_closed_silver_projection_sources() -> None:
    from finproof.domain.query_plan import EntityIdentifierType
    from finproof.entity import EntityIndex

    rows = iter(
        (
            (("B1", "Bond Name", None),),
            (("D1", "KRX1", "ETF", "Domestic Name", "Domestic"),),
            (("O1", "NYSE1", None, "TICK", "ETF", "Overseas Name"),),
            (("F1", None, None, "Fund Name", None),),
        )
    )
    statements: list[str] = []

    class Connection:
        current: tuple[tuple[object, ...], ...] = ()

        def execute(self, statement: str) -> Self:
            statements.append(" ".join(statement.split()))
            self.current = next(rows)
            return self

        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return self.current

        def close(self) -> None: ...

    index = EntityIndex.from_session(_runtime_session(Connection()))

    assert len(index._entries) == 4
    assert index._entries[0].names == ("bond name",)
    assert index._entries[2].identifiers == (
        (EntityIdentifierType.PRODUCT_ID, "o1"),
        (EntityIdentifierType.MARKET_IDENTIFIER, "nyse1"),
        (EntityIdentifierType.TICKER, "tick"),
    )
    assert statements == [
        "SELECT product_id, name, short_name FROM silver_bond_instrument ORDER BY product_id",
        "SELECT product_id, market_identifier, product_type, name, short_name "
        "FROM silver_domestic_listed_product ORDER BY product_id",
        "SELECT product_id, market_identifier, isin, ticker, product_type, name "
        "FROM silver_overseas_listed_product ORDER BY product_id",
        "SELECT fund_item_id, ksd_id, standard_item_id, name, short_name "
        "FROM silver_fund_item ORDER BY fund_item_id",
    ]
    assert all("record_json" not in statement for statement in statements)


def test_exact_product_identifier_beats_every_other_match() -> None:
    from finproof.domain.query_plan import EntityMention, ProductType
    from finproof.entity import EntityResolver, ResolutionMatchKind

    resolver = EntityResolver(
        _index(
            ("MATCH", "domestic_bond", "Primary ID", ("MATCH",), ("Primary ID",)),
            ("D2", "domestic_etf", "MATCH", ("D2", "MATCH"), ("MATCH",)),
        )
    )
    result = resolver.resolve(
        EntityMention(text="match"),
        product_types=(ProductType.DOMESTIC_BOND, ProductType.DOMESTIC_ETF),
    )

    assert result.selected is not None
    assert result.selected.product_id == "MATCH"
    assert result.selected.match_kind is ResolutionMatchKind.EXACT_PRODUCT_ID
    assert result.candidates == (result.selected,)


def test_exact_market_isin_ticker_and_alias_priority_is_deterministic() -> None:
    from finproof.domain.query_plan import EntityMention, ProductType
    from finproof.entity import EntityResolver, ResolutionMatchKind

    resolver = EntityResolver(
        _index(
            (
                "O1",
                "overseas_etf",
                "Overseas One",
                ("O1", "MARKET", "ISIN1", "TICK1"),
                ("Overseas One",),
            ),
            ("D1", "domestic_etf", "Domestic One", ("D1", "KRX1"), ("Domestic One", "Alias")),
            ("D2", "domestic_etf", "MARKET", ("D2", "KRX2"), ("MARKET",)),
        )
    )
    product_types = (ProductType.OVERSEAS_ETF, ProductType.DOMESTIC_ETF)

    for text in ("market", "isin1", "tick1"):
        selected = resolver.resolve(
            EntityMention(text=text),
            product_types=product_types,
        ).selected
        assert selected is not None
        assert selected.product_id == "O1"
        assert selected.match_kind is ResolutionMatchKind.EXACT_IDENTIFIER

    alias = resolver.resolve(
        EntityMention(text="alias"),
        product_types=product_types,
    ).selected
    assert alias is not None
    assert alias.product_id == "D1"
    assert alias.match_kind is ResolutionMatchKind.EXACT_NAME


def test_unique_normalized_name_selects_only_within_requested_product_types() -> None:
    from finproof.domain.query_plan import EntityMention, ProductType
    from finproof.entity import EntityResolver, ResolutionMatchKind

    resolver = EntityResolver(
        _index(
            ("D1", "domestic_etf", "Same  Fund", ("D1",), ("Same  Fund",)),
            (
                "F1",
                "public_fund",
                "\uff33\uff21\uff2d\uff25 FUND",
                ("F1",),
                ("\uff33\uff21\uff2d\uff25 FUND",),
            ),
        )
    )
    result = resolver.resolve(
        EntityMention(text=" same fund "),
        product_types=(ProductType.PUBLIC_FUND,),
    )

    assert result.selected is not None
    assert result.selected.product_id == "F1"
    assert result.selected.match_kind is ResolutionMatchKind.EXACT_NAME


def test_fuzzy_candidates_are_top_five_deterministic_and_never_selected() -> None:
    from finproof.domain.query_plan import EntityMention, ProductType
    from finproof.entity import EntityResolver, ResolutionMatchKind

    resolver = EntityResolver(
        _index(
            ("D3", "domestic_etf", "Alpha Fund C", ("D3",), ("Alpha Fund C",)),
            ("F2", "public_fund", "Alpha Funds", ("F2",), ("Alpha Funds",)),
            ("D1", "domestic_etf", "Alpha Fund A", ("D1",), ("Alpha Fund A",)),
            ("F1", "public_fund", "Alpha Funding", ("F1",), ("Alpha Funding",)),
            ("D2", "domestic_etf", "Alpha Fund B", ("D2",), ("Alpha Fund B",)),
            ("F3", "public_fund", "Alpha Founder", ("F3",), ("Alpha Founder",)),
            ("D4", "domestic_etf", "Beta Product", ("D4",), ("Beta Product",)),
        )
    )
    result = resolver.resolve(
        EntityMention(text="alpha fund x"),
        product_types=(ProductType.PUBLIC_FUND, ProductType.DOMESTIC_ETF),
    )

    assert result.selected is None
    assert len(result.candidates) == 5
    assert all(
        candidate.match_kind is ResolutionMatchKind.FUZZY_CANDIDATE
        for candidate in result.candidates
    )
    canonical_order = {product_type: index for index, product_type in enumerate(ProductType)}
    assert result.candidates == tuple(
        sorted(
            result.candidates,
            key=lambda candidate: (
                -candidate.score,
                canonical_order[candidate.product_type],
                candidate.product_id,
            ),
        )
    )


def test_ambiguous_exact_name_returns_no_selected_product() -> None:
    from finproof.domain.query_plan import EntityMention, ProductType
    from finproof.entity import EntityResolver, ResolutionMatchKind

    resolver = EntityResolver(
        _index(
            ("F1", "public_fund", "Shared Name", ("F1",), ("Shared Name",)),
            ("D1", "domestic_etf", "Shared Name", ("D1",), ("Shared Name",)),
        )
    )
    result = resolver.resolve(
        EntityMention(text="shared name"),
        product_types=(ProductType.PUBLIC_FUND, ProductType.DOMESTIC_ETF),
    )

    assert result.selected is None
    assert tuple(candidate.product_id for candidate in result.candidates) == ("D1", "F1")
    assert all(
        candidate.match_kind is ResolutionMatchKind.EXACT_NAME for candidate in result.candidates
    )


def test_unresolved_identifier_is_not_found_without_fuzzy_promotion() -> None:
    from finproof.domain.query_plan import EntityIdentifierType, EntityMention, ProductType
    from finproof.entity import EntityResolver

    resolver = EntityResolver(
        _index(
            (
                "O1",
                "overseas_etf",
                "Overseas One",
                ("O1", "MARKET1", "ISIN1", "TICK1"),
                ("Overseas One",),
            ),
        )
    )
    valid = resolver.resolve(
        EntityMention(text="isin1", identifier_type=EntityIdentifierType.ISIN),
        product_types=(ProductType.OVERSEAS_ETF,),
    )
    wrong_kind = resolver.resolve(
        EntityMention(text="tick1", identifier_type=EntityIdentifierType.ISIN),
        product_types=(ProductType.OVERSEAS_ETF,),
    )
    unresolved = resolver.resolve(
        EntityMention(text="isinl", identifier_type=EntityIdentifierType.ISIN),
        product_types=(ProductType.OVERSEAS_ETF,),
    )

    assert valid.selected is not None
    assert valid.selected.product_id == "O1"
    assert wrong_kind.selected is None
    assert wrong_kind.candidates == ()
    assert unresolved.selected is None
    assert unresolved.candidates == ()


def test_exact_link_repository_exposes_only_gold_exact_identifier_links() -> None:
    from finproof.data.artifacts.serialization import ExactCrossSourceLinkRecord
    from finproof.entity import ExactCrossSourceLinkRepository

    calls: list[tuple[str, tuple[object, ...]]] = []

    class Connection:
        def execute(self, statement: str, parameters: list[object]) -> Self:
            calls.append((" ".join(statement.split()), tuple(parameters)))
            return self

        def fetchall(self) -> list[tuple[object, ...]]:
            return [
                (
                    "a" * 64,
                    "silver_domestic_listed_product",
                    "D1",
                    "pd_itm_no",
                    "silver_fund_item",
                    "F1",
                    "ksd_itm_no",
                    "RAW1",
                    "exact_identifier",
                    Decimal("1.0"),
                    "cross_source.domestic_etf_public_fund.exact_raw_identifier",
                    "1.0.0",
                )
            ]

        def close(self) -> None: ...

    repository = ExactCrossSourceLinkRepository(_runtime_session(Connection()))
    links = repository.links_for_product("D1")

    assert len(links) == 1
    assert type(links[0]) is ExactCrossSourceLinkRecord
    assert links[0].left_product_id == "D1"
    assert calls == [
        (
            "SELECT link_id, left_table, left_product_id, left_identifier_field, "
            "right_table, right_product_id, right_identifier_field, "
            "matched_raw_identifier, link_type, confidence, rule_id, rule_version "
            "FROM gold_exact_cross_source_link WHERE left_product_id = ? OR "
            "right_product_id = ? ORDER BY left_product_id, right_product_id, rule_version",
            ("D1", "D1"),
        )
    ]


def test_entity_and_link_surfaces_accept_runtime_session_not_connection_path_or_sql() -> None:
    import pytest

    from finproof.entity import EntityIndex, EntityResolver, ExactCrossSourceLinkRepository

    assert inspect.signature(EntityIndex.from_session).parameters["session"].annotation in {
        RuntimeArtifactSession,
        "RuntimeArtifactSession",
    }
    public = {
        EntityIndex: {"from_session"},
        EntityResolver: {"resolve"},
        ExactCrossSourceLinkRepository: {"all_links", "links_for_product"},
    }
    for owner, expected in public.items():
        names = {name for name in vars(owner) if not name.startswith("_")}
        assert names == expected
        assert not names & {"connection", "cursor", "execute", "path", "sql"}

    with pytest.raises(TypeError):
        EntityIndex.from_session(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ExactCrossSourceLinkRepository(object())  # type: ignore[arg-type]
