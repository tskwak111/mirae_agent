"""Closed canonical-field to artifact-projection mapping."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Self

from pydantic import BaseModel, ConfigDict

from finproof.domain.query_plan import ProductType
from finproof.registry.loader import RegistryBundle


class FieldProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    field_id: str
    product_type: ProductType
    table_name: str
    column_name: str
    quality_column_name: str
    value_type: str
    metric_id: str | None


class FieldRegistry:
    __slots__ = ("_projections", "_registries")

    _projections: Mapping[tuple[str, ProductType], FieldProjection]
    _registries: RegistryBundle

    @classmethod
    def from_bundle(cls, registries: RegistryBundle) -> Self:
        if cls is not FieldRegistry or type(registries) is not RegistryBundle:
            raise TypeError("query fields require the exact registry bundle")
        registries.require_issued()
        projections: dict[tuple[str, ProductType], FieldProjection] = {}
        for field_id, field in registries.fields.entries.items():
            if field_id == "holding_constituent":
                continue
            product_types = field.product_types or tuple(
                product_type
                for metric_id in field.metric_ids
                for product_type in registries.metrics.entries[metric_id].product_types
            )
            for product_type in product_types:
                metric_id = next(
                    (
                        metric_id
                        for metric_id in field.metric_ids
                        if product_type in registries.metrics.entries[metric_id].product_types
                    ),
                    None,
                )
                value_type = (
                    registries.metrics.entries[metric_id].value_type
                    if metric_id is not None
                    else field.value_type
                )
                if value_type is None:
                    raise ValueError("field value type differs")
                column_name = _column_name(field_id, product_type)
                projections[(field_id, product_type)] = FieldProjection(
                    field_id=field_id,
                    product_type=product_type,
                    table_name=_TABLE_BY_PRODUCT_TYPE[product_type],
                    column_name=column_name,
                    quality_column_name=f"{column_name}__quality_status",
                    value_type=value_type,
                    metric_id=metric_id,
                )
        value = object.__new__(cls)
        value._registries = registries
        value._projections = MappingProxyType(projections)
        return value

    @property
    def projections(self) -> Mapping[tuple[str, ProductType], FieldProjection]:
        return self._projections

    def projection(self, field_id: str, product_type: ProductType) -> FieldProjection:
        try:
            return self._projections[(field_id, product_type)]
        except KeyError as exc:
            raise ValueError("field is not registered for product type") from exc


_TABLE_BY_PRODUCT_TYPE = {
    ProductType.DOMESTIC_BOND: "silver_bond_instrument",
    ProductType.DOMESTIC_ETF: "silver_domestic_listed_product",
    ProductType.DOMESTIC_ETN: "silver_domestic_listed_product",
    ProductType.OVERSEAS_ETF: "silver_overseas_listed_product",
    ProductType.OVERSEAS_ETN: "silver_overseas_listed_product",
    ProductType.PUBLIC_FUND: "silver_fund_item",
}


def _column_name(field_id: str, product_type: ProductType) -> str:
    if field_id == "product_name":
        return "name"
    if field_id == "product_id":
        return "fund_item_id" if product_type is ProductType.PUBLIC_FUND else "product_id"
    special = {
        ("aum", ProductType.DOMESTIC_ETF): "aum_primary",
        ("aum", ProductType.DOMESTIC_ETN): "aum_primary",
        ("aum", ProductType.PUBLIC_FUND): "net_assets",
        ("region", ProductType.PUBLIC_FUND): "region_description",
        ("currency", ProductType.OVERSEAS_ETF): "trading_currency",
        ("currency", ProductType.OVERSEAS_ETN): "trading_currency",
        ("risk_grade", ProductType.PUBLIC_FUND): "risk_name",
        ("saleable", ProductType.DOMESTIC_ETF): "sale_flag",
        ("saleable", ProductType.DOMESTIC_ETN): "sale_flag",
        ("saleable", ProductType.OVERSEAS_ETF): "sale_flag_raw",
        ("saleable", ProductType.OVERSEAS_ETN): "sale_flag_raw",
        ("saleable", ProductType.PUBLIC_FUND): "sale_status_raw",
        ("mirae_saleable", ProductType.PUBLIC_FUND): "mirae_sale_flag_raw",
    }
    return special.get((field_id, product_type), field_id)
