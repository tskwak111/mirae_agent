"""Immutable domestic-bond sale-lot and instrument contracts."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.domain.locators import SourceCellLocator
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue

BOND_LOT_FIELD_COLUMNS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "product_id": "pd_no",
        "exchange_market": "pd_exg_mkt",
        "info_base_date": "info_base_dt",
        "info_sequence": "info_seq",
        "name": "pd_nm",
        "short_name": "pd_abrv_nm",
        "currency": "curr_cd",
        "bond_kind_raw": "bd_knd",
        "issue_date": "isu_dt",
        "maturity_date": "mat_dt",
        "source_update_date": "pd_std_info_update",
        "coupon_rate": "srfc_irt",
        "buy_yield": "buy_yield",
        "buyable_quantity": "buyable_quantity",
        "source_remaining_days": "remaining_days",
        "credit_rating": "crd_grd",
        "credit_rating_date": "crd_grd_dt",
        "duration": "dur",
        "evaluation_price": "eval_price",
        "trade_price": "trade_price",
    }
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class BondSaleLotKey(_FrozenModel):
    """Exact stable identity of one source sale lot."""

    product_id: str = Field(min_length=1)
    exchange_market: str = Field(min_length=1)
    info_base_date: str = Field(min_length=1)
    info_seq: str = Field(min_length=1)
    source_row_number: int = Field(gt=0)


class BondSaleLot(_FrozenModel):
    """One recoverable PRBD source row at its sale-lot grain."""

    grain: Literal["bond_sale_lot"] = "bond_sale_lot"
    source_row: SourceRow
    source_key: BondSaleLotKey
    product_id: NormalizedValue[str]
    exchange_market: NormalizedValue[str]
    info_base_date: NormalizedValue[date]
    info_sequence: NormalizedValue[int]
    name: NormalizedValue[str]
    short_name: NormalizedValue[str]
    currency: NormalizedValue[str]
    bond_kind_raw: NormalizedValue[str]
    issue_date: NormalizedValue[date]
    maturity_date: NormalizedValue[date]
    source_update_date: NormalizedValue[date]
    coupon_rate: NormalizedValue[Decimal]
    buy_yield: NormalizedValue[Decimal]
    buyable_quantity: NormalizedValue[Decimal]
    source_remaining_days: NormalizedValue[int]
    credit_rating: NormalizedValue[str]
    credit_rating_date: NormalizedValue[date]
    duration: NormalizedValue[Decimal]
    evaluation_price: NormalizedValue[Decimal]
    trade_price: NormalizedValue[Decimal]

    @model_validator(mode="after")
    def validate_complete_source_lineage(self) -> Self:
        row = self.source_row
        if row.source_table != "PRBD01N001":
            raise ValueError("bond sale lot must name PRBD01N001")
        for field_name, column_name in BOND_LOT_FIELD_COLUMNS.items():
            wrapped = getattr(self, field_name)
            if wrapped.raw_value != row.cell(column_name).raw_value:
                raise ValueError("bond lot wrapper raw value differs from source row")
            if wrapped.source != SourceCellLocator.from_row(row, column_name):
                raise ValueError("bond lot wrapper locator differs from source row")
        if self.source_key != BondSaleLotKey(
            product_id=self.product_id.raw_value,
            exchange_market=self.exchange_market.raw_value,
            info_base_date=self.info_base_date.raw_value,
            info_seq=self.info_sequence.raw_value,
            source_row_number=row.source_row_number,
        ):
            raise ValueError("bond lot source key differs from source row")
        return self


class BondFieldSources(_FrozenModel):
    """All exact source cells collapsed into one parent field."""

    field_name: str = Field(min_length=1)
    sources: tuple[SourceCellLocator, ...]

    @model_validator(mode="after")
    def validate_sources(self) -> Self:
        if not self.sources:
            raise ValueError("bond parent field sources must not be empty")
        positions = tuple(
            (source.source_row_number, source.source_column_number) for source in self.sources
        )
        if positions != tuple(sorted(set(positions))):
            raise ValueError("bond parent field sources must be unique and sorted")
        column_names = {source.source_column_name for source in self.sources}
        if len(column_names) != 1:
            raise ValueError("bond parent field sources must name one source column")
        return self


class BondInstrument(_FrozenModel):
    """One domestic bond at its native instrument grain."""

    grain: Literal["instrument"] = "instrument"
    selected_lot_key: BondSaleLotKey
    field_sources: tuple[BondFieldSources, ...]
    product_id: NormalizedValue[str]
    name: NormalizedValue[str]
    short_name: NormalizedValue[str]
    currency: NormalizedValue[str]
    bond_kind_raw: NormalizedValue[str]
    issue_date: NormalizedValue[date]
    maturity_date: NormalizedValue[date]
    source_update_date: NormalizedValue[date]
    coupon_rate: NormalizedValue[Decimal]
    buy_yield: NormalizedValue[Decimal]
    source_remaining_days: NormalizedValue[int]
    credit_rating: NormalizedValue[str]
    credit_rating_date: NormalizedValue[date]
    duration: NormalizedValue[Decimal]
    evaluation_price: NormalizedValue[Decimal]
    trade_price: NormalizedValue[Decimal]
    remaining_days_at_as_of: DerivedValue[int]
    is_matured_at_as_of: DerivedValue[bool]
    is_purchasable_at_as_of: DerivedValue[bool]
    buy_yield_range: DerivedValue[tuple[Decimal, Decimal]]
