"""Bounded product projection repository."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, cast

from pydantic import BaseModel, ConfigDict

from finproof.domain.query_plan import ProductType, ResultGrain
from finproof.runtime.session import RuntimeArtifactSession

if TYPE_CHECKING:
    from finproof.query.ast import CompiledQuery


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class RawFieldValue(_FrozenModel):
    field_id: str
    value: str | int | Decimal | bool | date | datetime | None
    quality_status: str


class RawProductRow(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    product_id: str
    values: tuple[RawFieldValue, ...]


class RawSegmentResult(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    rows: tuple[RawProductRow, ...]
    candidate_count: int
    max_batch_rows: int


class RawExecutionResult(_FrozenModel):
    segments: tuple[RawSegmentResult, ...]
    candidate_count: int


class ProductRepository:
    __slots__ = ("_session",)

    def __init__(self, session: RuntimeArtifactSession) -> None:
        if type(session) is not RuntimeArtifactSession:
            raise TypeError("product repository requires exact runtime session")
        session.assert_live()
        self._session = session

    def execute(self, query: "CompiledQuery") -> RawSegmentResult:
        from finproof.query.ast import CompiledQuery

        if type(query) is not CompiledQuery:
            raise TypeError("product repository requires exact compiled query")
        self._session.assert_live()
        connection = cast(_QueryConnection | None, self._session._connection)
        if connection is None:
            raise RuntimeError("runtime artifact session is closed")
        cursor = connection.execute(query.sql, query.parameters)
        rows: list[RawProductRow] = []
        max_batch_rows = 0
        while batch := cursor.fetchmany(_BATCH_LIMIT):
            if len(batch) > _BATCH_LIMIT or len(rows) + len(batch) > _CANDIDATE_LIMIT:
                raise ValueError("raw candidate limit exceeded")
            max_batch_rows = max(max_batch_rows, len(batch))
            for physical in batch:
                if len(physical) != len(query.projected_fields) * 2:
                    raise ValueError("raw projection width differs")
                values = tuple(
                    RawFieldValue(
                        field_id=field_id,
                        value=_raw_scalar(physical[index * 2]),
                        quality_status=_exact_str(physical[index * 2 + 1]),
                    )
                    for index, field_id in enumerate(query.projected_fields)
                )
                product_id = values[0].value
                if values[0].field_id != "product_id" or type(product_id) is not str:
                    raise ValueError("raw product identity differs")
                rows.append(
                    RawProductRow(
                        product_type=query.product_type,
                        native_result_grain=query.native_result_grain,
                        product_id=product_id,
                        values=values,
                    )
                )
        return RawSegmentResult(
            product_type=query.product_type,
            native_result_grain=query.native_result_grain,
            rows=tuple(rows),
            candidate_count=len(rows),
            max_batch_rows=max_batch_rows,
        )


class _QueryCursor(Protocol):
    def fetchmany(self, size: int) -> list[tuple[object, ...]]: ...


class _QueryConnection(Protocol):
    def execute(
        self,
        sql: str,
        parameters: tuple[str | int | Decimal | bool, ...],
    ) -> _QueryCursor: ...


_BATCH_LIMIT = 65_536
_CANDIDATE_LIMIT = 65_536


def _exact_str(value: object) -> str:
    if type(value) is not str:
        raise ValueError("raw string differs")
    return value


def _raw_scalar(value: object) -> str | int | Decimal | bool | date | datetime | None:
    if value is None or type(value) in {str, int, Decimal, bool, date, datetime}:
        return value  # type: ignore[return-value]
    raise ValueError("raw scalar type differs")
