"""Deterministic tie policy."""

from collections import Counter
from decimal import Decimal

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
            raise ValueError("tie ranking requires exact comparable values")
        ordered = sorted(values, key=lambda item: item.product_id)
        ordered.sort(key=_sort_value, reverse=descending)
        counts = Counter(_sort_value(item) for item in ordered)
        ranks: dict[object, int] = {}
        for index, item in enumerate(ordered, start=1):
            ranks.setdefault(_sort_value(item), index)
        return tuple(
            RankedMetricValue(
                value=item,
                rank=ranks[_sort_value(item)],
                tie_count=counts[_sort_value(item)],
            )
            for item in ordered
        )


def _sort_value(value: MetricValue) -> Decimal | int | str:
    result = value.sort_value if value.sort_value is not None else value.value
    if type(result) is Decimal:
        return result
    if type(result) is int:
        return result
    if type(result) is str:
        return result
    raise ValueError("tie ranking requires exact comparable values")
