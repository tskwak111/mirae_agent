"""Closed product identity index."""

from dataclasses import dataclass
from typing import Protocol, Self, cast

from finproof.domain.query_plan import EntityIdentifierType, ProductType
from finproof.entity.normalization import normalize_product_text
from finproof.runtime.session import RuntimeArtifactSession


class _QueryResult(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class _QueryConnection(Protocol):
    def execute(self, statement: str) -> _QueryResult: ...


@dataclass(frozen=True, slots=True)
class _IndexedProduct:
    product_id: str
    product_type: ProductType
    name: str
    identifiers: tuple[tuple[EntityIdentifierType, str], ...]
    names: tuple[str, ...]


class EntityIndex:
    __slots__ = ("_entries",)

    _entries: tuple[_IndexedProduct, ...]

    def __new__(cls) -> "EntityIndex":
        raise TypeError("EntityIndex is runtime-session-owned")

    @classmethod
    def from_session(cls, session: RuntimeArtifactSession) -> Self:
        if cls is not EntityIndex or type(session) is not RuntimeArtifactSession:
            raise TypeError("entity index requires the exact runtime session")
        session.assert_live()
        connection = cast(_QueryConnection, session._connection)
        entries = [
            *(
                _entry(
                    row,
                    ProductType.DOMESTIC_BOND,
                    ((0, EntityIdentifierType.PRODUCT_ID),),
                    (1, 2),
                )
                for row in connection.execute(
                    "SELECT product_id, name, short_name "
                    "FROM silver_bond_instrument ORDER BY product_id"
                ).fetchall()
            ),
            *(
                _listed_entry(row, domestic=True)
                for row in connection.execute(
                    "SELECT product_id, market_identifier, product_type, name, short_name "
                    "FROM silver_domestic_listed_product ORDER BY product_id"
                ).fetchall()
            ),
            *(
                _listed_entry(row, domestic=False)
                for row in connection.execute(
                    "SELECT product_id, market_identifier, isin, ticker, product_type, name "
                    "FROM silver_overseas_listed_product ORDER BY product_id"
                ).fetchall()
            ),
            *(
                _entry(
                    row,
                    ProductType.PUBLIC_FUND,
                    (
                        (0, EntityIdentifierType.PRODUCT_ID),
                        (1, EntityIdentifierType.MARKET_IDENTIFIER),
                        (2, EntityIdentifierType.ISIN),
                    ),
                    (3, 4),
                )
                for row in connection.execute(
                    "SELECT fund_item_id, ksd_id, standard_item_id, name, short_name "
                    "FROM silver_fund_item ORDER BY fund_item_id"
                ).fetchall()
            ),
        ]
        value = object.__new__(cls)
        value._entries = tuple(entries)
        return value

    @classmethod
    def _from_entries(cls, entries: tuple[_IndexedProduct, ...]) -> Self:
        value = object.__new__(cls)
        value._entries = entries
        return value


def _listed_entry(row: tuple[object, ...], *, domestic: bool) -> _IndexedProduct:
    type_index = 2 if domestic else 4
    listed_type = _text(row[type_index])
    product_type = (
        ProductType.DOMESTIC_ETF
        if domestic and listed_type == "ETF"
        else ProductType.DOMESTIC_ETN
        if domestic and listed_type == "ETN"
        else ProductType.OVERSEAS_ETF
        if not domestic and listed_type == "ETF"
        else ProductType.OVERSEAS_ETN
        if not domestic and listed_type == "ETN"
        else None
    )
    if product_type is None:
        raise ValueError("listed product type differs")
    return _entry(
        row,
        product_type,
        (
            (0, EntityIdentifierType.PRODUCT_ID),
            (1, EntityIdentifierType.MARKET_IDENTIFIER),
        )
        if domestic
        else (
            (0, EntityIdentifierType.PRODUCT_ID),
            (1, EntityIdentifierType.MARKET_IDENTIFIER),
            (2, EntityIdentifierType.ISIN),
            (3, EntityIdentifierType.TICKER),
        ),
        (3, 4) if domestic else (5,),
    )


def _entry(
    row: tuple[object, ...],
    product_type: ProductType,
    identifier_columns: tuple[tuple[int, EntityIdentifierType], ...],
    name_indexes: tuple[int, ...],
) -> _IndexedProduct:
    identifiers = tuple(
        (kind, text)
        for index, kind in identifier_columns
        if (text := _optional_text(row[index])) is not None
    )
    names = tuple(
        text for index in name_indexes if (text := _optional_text(row[index])) is not None
    )
    if (
        not identifiers
        or identifiers[0][0] is not EntityIdentifierType.PRODUCT_ID
        or not identifiers[0][1]
        or not names
        or not names[0]
    ):
        raise ValueError("entity index row is incomplete")
    return _IndexedProduct(
        product_id=identifiers[0][1],
        product_type=product_type,
        name=names[0],
        identifiers=tuple(
            (kind, normalize_product_text(value)) for kind, value in identifiers if value
        ),
        names=tuple(normalize_product_text(value) for value in names if value),
    )


def _text(value: object) -> str:
    if type(value) is not str:
        raise TypeError("entity index scalar differs")
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)
