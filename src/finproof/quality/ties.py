"""Deterministic tie policy."""

from collections import Counter
from decimal import Decimal
from typing import cast

from pydantic import BaseModel, ConfigDict

from finproof.quality.metric_policy import MetricValue


class RankedMetricValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    value: MetricValue
    rank: int
    tie_count: int


class TiePolicy:
    def rank(
        self,
        values: tuple[MetricValue, ...],
        *,
        descending: bool,
    ) -> tuple[RankedMetricValue, ...]:
        if type(values) is not tuple or type(descending) is not bool:
            raise TypeError("tie policy inputs differ")
        if any(type(item) is not MetricValue or item.value is None for item in values):
            raise ValueError("tie ranking requires exact numeric values")
        ordered = sorted(values, key=lambda item: item.product_id)
        ordered.sort(key=lambda item: cast(Decimal, item.value), reverse=descending)
        counts = Counter(item.value for item in ordered)
        ranks: dict[object, int] = {}
        for index, item in enumerate(ordered, start=1):
            ranks.setdefault(item.value, index)
        return tuple(
            RankedMetricValue(
                value=item,
                rank=ranks[item.value],
                tie_count=counts[item.value],
            )
            for item in ordered
        )
