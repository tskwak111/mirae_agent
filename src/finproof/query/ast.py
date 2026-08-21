"""Closed native query AST and compiled-query contracts."""

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict

from finproof.domain.execution import ExecutionSegment
from finproof.domain.query_plan import ProductType, ResultGrain
from finproof.query.fields import FieldProjection, FieldRegistry


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class QueryAst(_FrozenModel):
    segment: ExecutionSegment
    table_name: str
    projections: tuple[FieldProjection, ...]

    @classmethod
    def from_segment(cls, segment: ExecutionSegment, *, fields: FieldRegistry) -> Self:
        if cls is not QueryAst or type(segment) is not ExecutionSegment:
            raise TypeError("query AST requires one exact execution segment")
        if type(fields) is not FieldRegistry:
            raise TypeError("query AST requires exact query fields")
        if segment.native_result_grain is ResultGrain.PRODUCT:
            raise ValueError("query AST requires one native result grain")
        field_ids = dict.fromkeys(
            (
                "product_id",
                *(clause.field for clause in segment.filters),
                *segment.metrics,
                *(sort.field for sort in segment.sort),
                *(segment.aggregation.group_by if segment.aggregation else ()),
                *(
                    (segment.aggregation.field,)
                    if segment.aggregation is not None and segment.aggregation.field is not None
                    else ()
                ),
            )
        )
        projections = tuple(
            fields.projection(field_id, segment.product_type) for field_id in field_ids
        )
        table_names = {projection.table_name for projection in projections}
        if len(table_names) != 1:
            raise ValueError("query AST projections require one native table")
        return cls(
            segment=segment,
            table_name=next(iter(table_names)),
            projections=projections,
        )


class CompiledQuery(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    table_name: str
    projected_fields: tuple[str, ...]
    sql: str
    parameters: tuple[str | int | Decimal | bool, ...]
