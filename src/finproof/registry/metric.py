"""Metric and canonical-field registry contracts."""

from collections.abc import Mapping

from finproof.domain.query_plan import AggregationFunction, FilterOperator, ProductType
from finproof.registry.models import FrozenRegistry


class MetricDefinition(FrozenRegistry):
    label_ko: str
    product_types: tuple[ProductType, ...]
    source_table: str
    source_column: str
    secondary_source_column: str | None
    derived_rule: str | None
    value_type: str
    unit: str | None
    period: str | None
    currency: str | None
    currency_source: str | None
    missing_policy: str
    zero_policy: str
    display_policy: str
    literal_filter_policy: str
    ranking_policy: str
    aggregation_policy: str
    tie_policy: str
    comparability_group: str
    cross_product_policy: str
    evidence_rule: str
    queryable: bool = True


class MetricRegistry(FrozenRegistry):
    version: str
    entries: Mapping[str, MetricDefinition]


class FieldDefinition(FrozenRegistry):
    product_types: tuple[ProductType, ...]
    value_type: str | None
    metric_ids: tuple[str, ...]
    operators: tuple[FilterOperator, ...]
    sortable: bool
    aggregations: tuple[AggregationFunction, ...]


class FieldRegistry(FrozenRegistry):
    version: str
    targetless_aggregations: tuple[AggregationFunction, ...]
    entries: Mapping[str, FieldDefinition]
