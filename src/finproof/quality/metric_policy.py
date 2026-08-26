"""Operation-specific metric policies."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from finproof.domain.query_plan import ProductType
from finproof.registry.loader import RegistryBundle


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class Operation(StrEnum):
    DISPLAY = "display"
    FILTER = "filter"
    RANK = "rank"
    AGGREGATE = "aggregate"


class MetricValue(_FrozenModel):
    metric_id: str
    product_type: ProductType
    product_id: str
    value: Decimal | str | None
    quality_status: str
    currency: str | None = None
    period: str | None = None
    sort_value: Decimal | int | str | None = None


class MetricPolicyResult(_FrozenModel):
    recorded_values: tuple[MetricValue, ...]
    comparison_valid_values: tuple[MetricValue, ...]
    excluded_count: int
    warnings: tuple[str, ...]


class MetricPolicy:
    def __init__(self) -> None:
        self._metrics = RegistryBundle.from_package().metrics.entries

    def apply(
        self,
        operation: Operation,
        values: tuple[MetricValue, ...],
    ) -> MetricPolicyResult:
        if type(operation) is not Operation or type(values) is not tuple:
            raise TypeError("metric policy inputs differ")
        recorded = tuple(value for value in values if value.value is not None)
        valid = (
            recorded
            if operation in {Operation.DISPLAY, Operation.FILTER}
            else tuple(
                value
                for value in recorded
                if type(value) is MetricValue
                and value.quality_status in {"valid", "recorded_zero", "constant_metric"}
                and not (
                    value.value == 0 and "unverified" in self._metrics[value.metric_id].zero_policy
                )
            )
        )
        return MetricPolicyResult(
            recorded_values=recorded,
            comparison_valid_values=valid,
            excluded_count=len(values) - len(valid),
            warnings=(
                (
                    "recorded zero excluded from comparison"
                    if any(
                        value.value == 0
                        and "unverified" in self._metrics[value.metric_id].zero_policy
                        for value in recorded
                    )
                    else "metric values excluded from comparison"
                ),
            )
            if len(values) != len(valid)
            else (),
        )
