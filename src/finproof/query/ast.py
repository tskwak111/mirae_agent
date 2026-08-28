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
        if segment.product_type is ProductType.DOMESTIC_BOND:
            field_ids.setdefault("issue_date", None)
            field_ids.setdefault("maturity_date", None)
        if "aum" in field_ids:
            field_ids.setdefault("currency", None)
        projections = [fields.projection(field_id, segment.product_type) for field_id in field_ids]
        if segment.product_type in {
            ProductType.DOMESTIC_ETF,
            ProductType.DOMESTIC_ETN,
        }:
            saleable = fields.projection("saleable", segment.product_type)
            if "saleable" not in field_ids:
                projections.append(saleable)
            projections.append(
                FieldProjection(
                    field_id="suspension_flag",
                    product_type=segment.product_type,
                    table_name=saleable.table_name,
                    column_name="suspension_flag",
                    quality_column_name="suspension_flag__quality_status",
                    value_type="boolean",
                    metric_id=None,
                )
            )
            projections.extend(
                FieldProjection(
                    field_id=field_id,
                    product_type=segment.product_type,
                    table_name=saleable.table_name,
                    column_name=field_id,
                    quality_column_name=f"{field_id}__quality_status",
                    value_type="date",
                    metric_id=None,
                )
                for field_id in ("listing_date", "listing_end_date")
            )
        table_names = {projection.table_name for projection in projections}
        if len(table_names) != 1:
            raise ValueError("query AST projections require one native table")
        return cls(
            segment=segment,
            table_name=next(iter(table_names)),
            projections=tuple(projections),
        )


class CompiledQuery(_FrozenModel):
    product_type: ProductType
    native_result_grain: ResultGrain
    table_name: str
    projected_fields: tuple[str, ...]
    sql: str
    parameters: tuple[str | int | Decimal | bool, ...]
