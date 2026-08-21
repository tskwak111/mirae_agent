"""Exact Gold cross-source link access."""

from typing import Protocol, cast

from finproof.data.artifacts.serialization import ExactCrossSourceLinkRecord
from finproof.runtime.session import RuntimeArtifactSession

_COLUMNS = (
    "link_id",
    "left_table",
    "left_product_id",
    "left_identifier_field",
    "right_table",
    "right_product_id",
    "right_identifier_field",
    "matched_raw_identifier",
    "link_type",
    "confidence",
    "rule_id",
    "rule_version",
)
_SELECT = (
    f"SELECT {', '.join(_COLUMNS)} FROM gold_exact_cross_source_link "  # noqa: S608 -- closed columns/table
    "WHERE left_product_id = ? OR right_product_id = ? "
    "ORDER BY left_product_id, right_product_id, rule_version"
)
_SELECT_ALL = (
    f"SELECT {', '.join(_COLUMNS)} FROM gold_exact_cross_source_link "  # noqa: S608 -- closed columns/table
    "ORDER BY left_product_id, right_product_id, rule_version"
)


class _QueryResult(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class _QueryConnection(Protocol):
    def execute(
        self,
        statement: str,
        parameters: list[object] | None = None,
    ) -> _QueryResult: ...


class ExactCrossSourceLinkRepository:
    __slots__ = ("_session",)

    def __init__(self, session: RuntimeArtifactSession) -> None:
        if type(session) is not RuntimeArtifactSession:
            raise TypeError("exact links require the exact runtime session")
        session.assert_live()
        self._session = session

    def links_for_product(self, product_id: str) -> tuple[ExactCrossSourceLinkRecord, ...]:
        if type(product_id) is not str or not 1 <= len(product_id) <= 300:
            raise ValueError("product identifier differs")
        self._session.assert_live()
        connection = cast(_QueryConnection, self._session._connection)
        return _links(connection.execute(_SELECT, [product_id, product_id]).fetchall())

    def all_links(self) -> tuple[ExactCrossSourceLinkRecord, ...]:
        self._session.assert_live()
        connection = cast(_QueryConnection, self._session._connection)
        return _links(connection.execute(_SELECT_ALL).fetchall())


def _links(rows: list[tuple[object, ...]]) -> tuple[ExactCrossSourceLinkRecord, ...]:
    return tuple(
        ExactCrossSourceLinkRecord.model_validate(
            dict(zip(_COLUMNS, row, strict=True)),
            strict=True,
        )
        for row in rows
    )
