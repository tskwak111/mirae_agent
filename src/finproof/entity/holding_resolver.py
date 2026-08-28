"""Deterministic exact resolution over the sealed holding relation."""

from typing import Protocol, Self, cast

from finproof.entity.models import HoldingResolutionCandidate, HoldingResolutionResult
from finproof.entity.normalization import normalize_product_text
from finproof.runtime.session import RuntimeArtifactSession


class _QueryResult(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class _QueryConnection(Protocol):
    def execute(self, statement: str) -> _QueryResult: ...


class HoldingResolver:
    __slots__ = ("_candidates",)

    _candidates: tuple[HoldingResolutionCandidate, ...]

    def __new__(cls) -> "HoldingResolver":
        raise TypeError("HoldingResolver is runtime-session-owned")

    @classmethod
    def from_session(cls, session: RuntimeArtifactSession) -> Self:
        if cls is not HoldingResolver or type(session) is not RuntimeArtifactSession:
            raise TypeError("holding resolver requires the exact runtime session")
        session.assert_live()
        connection = cast(_QueryConnection, session._connection)
        return cls._from_rows(
            tuple(
                cast(tuple[str, str, str], row)
                for row in connection.execute(
                    "SELECT constituent_identifier, constituent_identifier_type, display_name "
                    "FROM silver_product_holding "
                    "ORDER BY constituent_identifier, constituent_identifier_type, display_name"
                ).fetchall()
            )
        )

    @classmethod
    def _from_rows(cls, rows: tuple[tuple[str, str, str], ...]) -> Self:
        if cls is not HoldingResolver or type(rows) is not tuple:
            raise TypeError("holding resolution rows differ")
        by_pair: dict[tuple[str, str], str] = {}
        for row in rows:
            if (
                type(row) is not tuple
                or len(row) != 3
                or any(type(value) is not str or not value for value in row)
            ):
                raise TypeError("holding resolution row differs")
            identifier, identifier_type, display_name = row
            key = (identifier, identifier_type)
            existing = by_pair.get(key)
            if existing is None or (normalize_product_text(display_name), display_name) < (
                normalize_product_text(existing),
                existing,
            ):
                by_pair[key] = display_name
        value = object.__new__(cls)
        value._candidates = tuple(
            HoldingResolutionCandidate(
                constituent_identifier=identifier,
                constituent_identifier_type=identifier_type,
                display_name=display_name,
            )
            for (identifier, identifier_type), display_name in sorted(by_pair.items())
        )
        return value

    def resolve(self, text: str) -> HoldingResolutionResult:
        if type(text) is not str or not text:
            raise TypeError("holding constituent must be a nonempty exact string")
        identifier_matches = tuple(
            candidate for candidate in self._candidates if candidate.constituent_identifier == text
        )
        matches = identifier_matches or tuple(
            candidate
            for candidate in self._candidates
            if normalize_product_text(candidate.display_name) == normalize_product_text(text)
        )
        bounded = matches[:5]
        return HoldingResolutionResult(
            selected=bounded[0] if len(matches) == 1 else None,
            candidates=bounded,
        )
