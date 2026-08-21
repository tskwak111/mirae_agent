"""Immutable Phase 2 runtime registry bundle."""

from collections.abc import Mapping
from datetime import date
from io import BytesIO
from types import MappingProxyType
from typing import Self

from pydantic import PrivateAttr

from finproof.domain.query_plan import AggregationFunction, FilterOperator, ProductType
from finproof.registry.answer import AnswerRegistry
from finproof.registry.metric import (
    FieldDefinition,
    FieldRegistry,
    MetricDefinition,
    MetricRegistry,
)
from finproof.registry.models import DatasetRegistry, FrozenRegistry
from finproof.registry.planner import PlannerRegistry
from finproof.registry.quality import QualityRegistry
from finproof.registry.rating import RatingRegistry
from finproof.registry.resources import (
    REGISTRY_RESOURCE_NAMES,
    load_registry_document,
    registry_resource_bytes,
)
from finproof.registry.state import StateRegistry


class RegistryBundle(FrozenRegistry):
    _issuance: object = PrivateAttr(default=None)

    datasets: DatasetRegistry
    metrics: MetricRegistry
    fields: FieldRegistry
    states: StateRegistry
    quality: QualityRegistry
    ratings: RatingRegistry
    answers: AnswerRegistry
    planner: PlannerRegistry

    @classmethod
    def from_package(cls) -> Self:
        return cls._from_resource_bytes(
            {name: registry_resource_bytes(name) for name in REGISTRY_RESOURCE_NAMES}
        )

    @classmethod
    def _from_resource_bytes(cls, payloads: Mapping[str, bytes]) -> Self:
        if cls is not RegistryBundle:
            raise TypeError("registry bundle type differs")
        if set(payloads) != set(REGISTRY_RESOURCE_NAMES):
            raise ValueError("registry resource inventory differs")
        documents = {
            name: load_registry_document(payloads[name])
            for name in REGISTRY_RESOURCE_NAMES
            if name != "rating_scale.yaml"
        }
        datasets = documents["datasets.yaml"]
        metrics = documents["metric_registry.yaml"]
        fields = documents["field_registry.yaml"]
        states = documents["state_rules.yaml"]
        quality = documents["quality_rules.yaml"]
        answers = documents["answer_policy.yaml"]
        planner = documents["planner_catalog.yaml"]

        metric_entries = MappingProxyType(
            {
                metric_id: _metric_definition(value)
                for metric_id, value in _entries(metrics, "metrics").items()
            }
        )
        field_entries = MappingProxyType(
            {
                field_id: _field_definition(value)
                for field_id, value in _entries(fields, "fields").items()
            }
        )
        referenced_metrics = {
            metric_id for field in field_entries.values() for metric_id in field.metric_ids
        }
        unresolved_metrics = {
            metric_id
            for metric_id, metric in metric_entries.items()
            if metric.queryable and metric_id not in referenced_metrics
        }
        planner_aliases = _alias_mapping(planner, "field_aliases")
        if unresolved_metrics or set(planner_aliases) - set(field_entries):
            raise ValueError("registry reachability differs")
        rating_registry = RatingRegistry.from_held_stream(BytesIO(payloads["rating_scale.yaml"]))
        if type(rating_registry) is not cls.model_fields["ratings"].annotation:
            raise TypeError("rating registry type differs")

        value = cls(
            datasets=DatasetRegistry(
                version=_version(datasets),
                snapshot_date=date.fromisoformat(_exact_str(datasets, "snapshot_date")),
                entries=_entries(datasets, "datasets"),
            ),
            metrics=MetricRegistry(version=_version(metrics), entries=metric_entries),
            fields=FieldRegistry(
                version=_version(fields),
                targetless_aggregations=tuple(
                    AggregationFunction(value)
                    for value in _string_tuple(fields, "targetless_aggregations")
                ),
                entries=field_entries,
            ),
            states=StateRegistry(
                version=_version(states),
                entries=_entries(states, "rules"),
            ),
            quality=QualityRegistry(
                version=_version(quality),
                statuses=_string_tuple(quality, "quality_statuses"),
                entries=_entries(quality, "rules"),
            ),
            ratings=rating_registry,
            answers=AnswerRegistry(version=_version(answers), document=answers),
            planner=PlannerRegistry(
                version=_version(planner),
                product_type_aliases=_alias_mapping(planner, "product_type_aliases"),
                field_aliases=planner_aliases,
                period_aliases=_alias_mapping(planner, "period_aliases"),
                ranking_aliases=_alias_mapping(planner, "ranking_aliases"),
            ),
        )
        value._issuance = _RegistryBundleIssuance(value)
        return value

    def require_issued(self) -> None:
        if (
            type(self) is not RegistryBundle
            or type(self._issuance) is not _RegistryBundleIssuance
            or self._issuance.value is not self
        ):
            raise TypeError("registry bundle is not loader-issued")


class _RegistryBundleIssuance:
    __slots__ = ("value",)

    def __init__(self, value: RegistryBundle) -> None:
        self.value = value


def _metric_definition(value: object) -> MetricDefinition:
    item = _exact_mapping(value)
    return MetricDefinition(
        label_ko=_exact_str(item, "label_ko"),
        product_types=tuple(ProductType(value) for value in _string_tuple(item, "product_types")),
        source_table=_exact_str(item, "source_table"),
        source_column=_exact_str(item, "source_column"),
        secondary_source_column=_optional_str(item, "secondary_source_column"),
        derived_rule=_optional_str(item, "derived_rule"),
        value_type=_exact_str(item, "value_type"),
        unit=_optional_str(item, "unit"),
        period=_optional_str(item, "period"),
        currency=_optional_str(item, "currency"),
        currency_source=_optional_str(item, "currency_source"),
        missing_policy=_exact_str(item, "missing_policy"),
        zero_policy=_exact_str(item, "zero_policy"),
        display_policy=_exact_str(item, "display_policy"),
        literal_filter_policy=_exact_str(item, "literal_filter_policy"),
        ranking_policy=_exact_str(item, "ranking_policy"),
        aggregation_policy=_exact_str(item, "aggregation_policy"),
        tie_policy=_exact_str(item, "tie_policy"),
        comparability_group=_exact_str(item, "comparability_group"),
        cross_product_policy=_exact_str(item, "cross_product_policy"),
        evidence_rule=_exact_str(item, "evidence_rule"),
        queryable=_optional_bool(item, "queryable", default=True),
    )


def _field_definition(value: object) -> FieldDefinition:
    item = _exact_mapping(value)
    metric_id = _optional_str(item, "metric_id")
    metric_ids = _string_tuple(item, "metric_ids") if "metric_ids" in item else ()
    if metric_id is not None:
        if metric_ids:
            raise ValueError("field metric references differ")
        metric_ids = (metric_id,)
    return FieldDefinition(
        product_types=(
            tuple(ProductType(value) for value in _string_tuple(item, "product_types"))
            if "product_types" in item
            else ()
        ),
        value_type=_optional_str(item, "value_type"),
        metric_ids=metric_ids,
        operators=tuple(FilterOperator(value) for value in _string_tuple(item, "operators")),
        sortable=_exact_bool(item, "sortable"),
        aggregations=tuple(
            AggregationFunction(value) for value in _string_tuple(item, "aggregations")
        ),
    )


def _version(document: Mapping[str, object]) -> str:
    return _exact_str(document, "version")


def _entries(document: Mapping[str, object], key: str) -> Mapping[str, Mapping[str, object]]:
    entries = _exact_mapping(document.get(key))
    return MappingProxyType({name: _exact_mapping(value) for name, value in entries.items()})


def _alias_mapping(document: Mapping[str, object], key: str) -> Mapping[str, tuple[str, ...]]:
    aliases = _exact_mapping(document.get(key))
    return MappingProxyType({name: _string_tuple(aliases, name) for name in aliases})


def _exact_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise ValueError("registry mapping differs")
    return value


def _exact_str(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if type(value) is not str or value == "":
        raise ValueError("registry string differs")
    return value


def _optional_str(document: Mapping[str, object], key: str) -> str | None:
    value = document.get(key)
    if value is None:
        return None
    if type(value) is not str or value == "":
        raise ValueError("registry optional string differs")
    return value


def _exact_bool(document: Mapping[str, object], key: str) -> bool:
    value = document.get(key)
    if type(value) is not bool:
        raise ValueError("registry boolean differs")
    return value


def _optional_bool(document: Mapping[str, object], key: str, *, default: bool) -> bool:
    if key not in document:
        return default
    return _exact_bool(document, key)


def _string_tuple(document: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = document.get(key)
    if type(value) is not tuple or any(type(item) is not str or item == "" for item in value):
        raise ValueError("registry string tuple differs")
    return value
