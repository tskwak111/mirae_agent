"""Immutable domain contract for one normalized domestic bond instrument."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from finproof.domain.values import DerivedValue, NormalizedValue


class BondInstrument(BaseModel):
    """One domestic bond at its native instrument grain."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["instrument"] = "instrument"
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
    buyable_quantity: NormalizedValue[Decimal]
    source_remaining_days: NormalizedValue[int]
    credit_rating: NormalizedValue[str]
    credit_rating_agencies_raw: NormalizedValue[str]
    credit_rating_date: NormalizedValue[date]
    duration: NormalizedValue[Decimal]
    evaluation_price: NormalizedValue[Decimal]
    remaining_days_at_as_of: DerivedValue[int]
    is_matured_at_as_of: DerivedValue[bool]
    has_positive_buyable_quantity: DerivedValue[bool]
    is_buyable_validated_at_as_of: DerivedValue[bool]
