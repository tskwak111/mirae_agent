"""Compatibility partition policy."""

from pydantic import BaseModel, ConfigDict

from finproof.quality.metric_policy import MetricValue
from finproof.registry.loader import RegistryBundle


class CompatibilityPartition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    compatibility_key: str
    currency: str | None
    period: str | None
    values: tuple[MetricValue, ...]
    selected_values: tuple[MetricValue, ...] = ()
    caveats: tuple[str, ...]


class CompatibilityPartitioner:
    def __init__(self) -> None:
        self._metrics = RegistryBundle.from_package().metrics.entries

    def partition(
        self,
        values: tuple[MetricValue, ...],
        *,
        requested_period: str | None = None,
    ) -> tuple[CompatibilityPartition, ...]:
        if type(values) is not tuple or any(type(value) is not MetricValue for value in values):
            raise TypeError("compatibility inputs differ")
        definitions = tuple(self._metrics[value.metric_id] for value in values)
        if (
            definitions
            and all(
                definition.comparability_group == "historical_total_return"
                for definition in definitions
            )
            and requested_period is None
        ):
            raise ValueError("return period requires clarification")
        groups: dict[tuple[str, str | None, str | None, str], list[MetricValue]] = {}
        for value in values:
            metric = self._metrics[value.metric_id]
            key = (
                metric.comparability_group,
                value.currency or metric.currency,
                value.period or metric.period,
                metric.cross_product_policy,
            )
            groups.setdefault(key, []).append(value)
        return tuple(
            CompatibilityPartition(
                compatibility_key=":".join(str(item) for item in key),
                currency=key[1],
                period=key[2],
                values=tuple(group),
                caveats=("cross-product source semantics differ",)
                if key[3] == "same_period_and_compatible_source_semantics"
                and len({value.product_type for value in group}) > 1
                else (),
            )
            for key, group in groups.items()
        )
