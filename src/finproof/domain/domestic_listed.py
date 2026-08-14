"""Immutable domain contract for one normalized domestic listed product."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from finproof.domain.listed import ListedProductType as ListedProductType
from finproof.domain.values import DerivedValue, NormalizedValue


class ListedProduct(BaseModel):
    """One domestic ETF or ETN at its native listed-product grain."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["listed_product"] = "listed_product"
    product_id: NormalizedValue[str]
    market_identifier: NormalizedValue[str]
    product_type: NormalizedValue[ListedProductType]
    name: NormalizedValue[str]
    short_name: NormalizedValue[str]
    currency: NormalizedValue[str]
    listing_date: NormalizedValue[date]
    listing_end_date: NormalizedValue[date]
    sale_flag: NormalizedValue[bool]
    suspension_flag: NormalizedValue[bool]
    aum_primary: NormalizedValue[Decimal]
    aum_secondary: NormalizedValue[Decimal]
    total_fee: NormalizedValue[Decimal]
    tracking_error: NormalizedValue[Decimal]
    difference_rate: NormalizedValue[Decimal]
    return_1d: NormalizedValue[Decimal]
    return_1m: NormalizedValue[Decimal]
    return_3m: NormalizedValue[Decimal]
    return_6m: NormalizedValue[Decimal]
    return_1y: NormalizedValue[Decimal]
    return_ytd: NormalizedValue[Decimal]
    risk_code: NormalizedValue[str]
    risk_name: NormalizedValue[str]
    base_index: NormalizedValue[str]
    manager: NormalizedValue[str]
    asset_type: NormalizedValue[str]
    region: NormalizedValue[str]
    custom_update_date: NormalizedValue[date]
    daily_update_at: NormalizedValue[datetime]
    weekly_update_date: NormalizedValue[date]
    is_eligible_at_as_of: DerivedValue[bool]
