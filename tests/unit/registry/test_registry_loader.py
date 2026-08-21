"""Focused immutable Phase 2 registry loading tests."""

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _registry_payloads() -> dict[str, bytes]:
    return {
        name: (ROOT / "config" / name).read_bytes()
        for name in (
            "datasets.yaml",
            "metric_registry.yaml",
            "field_registry.yaml",
            "state_rules.yaml",
            "quality_rules.yaml",
            "rating_scale.yaml",
            "answer_policy.yaml",
            "planner_catalog.yaml",
        )
    }


def test_registry_bundle_skeleton_has_exact_eight_member_inventory() -> None:
    """The runtime registry bundle contains exactly the frozen eight registries."""
    from finproof.registry.answer import AnswerRegistry
    from finproof.registry.loader import RegistryBundle
    from finproof.registry.metric import FieldRegistry, MetricRegistry
    from finproof.registry.models import DatasetRegistry
    from finproof.registry.planner import PlannerRegistry
    from finproof.registry.quality import QualityRegistry
    from finproof.registry.rating import RatingRegistry
    from finproof.registry.state import StateRegistry

    assert tuple(RegistryBundle.model_fields) == (
        "datasets",
        "metrics",
        "fields",
        "states",
        "quality",
        "ratings",
        "answers",
        "planner",
    )
    assert tuple(field.annotation for field in RegistryBundle.model_fields.values()) == (
        DatasetRegistry,
        MetricRegistry,
        FieldRegistry,
        StateRegistry,
        QualityRegistry,
        RatingRegistry,
        AnswerRegistry,
        PlannerRegistry,
    )


def test_registry_resources_reject_duplicate_oversized_mutable_and_wrong_shape_documents() -> None:
    """One bounded parser closes every YAML resource trust boundary."""
    from finproof.registry.resources import MAX_REGISTRY_BYTES, load_registry_document

    document = load_registry_document(b'version: "1.0.0"\nitems:\n  key: [one, two]\n')
    assert isinstance(document, Mapping)
    assert document["items"]["key"] == ("one", "two")  # type: ignore[index]
    with pytest.raises(TypeError):
        document["version"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        document["items"]["key"] = ()  # type: ignore[index]

    invalid = (
        b'version: "1.0.0"\nversion: "2.0.0"\n',
        b"x" * (MAX_REGISTRY_BYTES + 1),
        b"- one\n- two\n",
        b"value: !!python/object/apply:os.system ['echo unsafe']\n",
    )
    for payload in invalid:
        with pytest.raises(ValueError, match="invalid registry resource"):
            load_registry_document(payload)


def test_field_metric_and_planner_alias_reachability_is_complete() -> None:
    """Every queryable metric and planner field alias reaches one canonical field."""
    from finproof.registry.loader import RegistryBundle

    bundle = RegistryBundle._from_resource_bytes(_registry_payloads())
    referenced_metrics = {
        metric_id for field in bundle.fields.entries.values() for metric_id in field.metric_ids
    }
    assert set(bundle.metrics.entries) == referenced_metrics | {
        metric_id for metric_id, metric in bundle.metrics.entries.items() if not metric.queryable
    }
    assert set(bundle.planner.field_aliases) <= set(bundle.fields.entries)
    assert bundle.fields.version == "1.1.0"


def test_field_registry_aggregate_allowlists_match_targetless_count_contract() -> None:
    """Count belongs only to the native grain; field targets authorize value functions."""
    from finproof.domain.query_plan import AggregationFunction
    from finproof.registry.loader import RegistryBundle

    fields = RegistryBundle._from_resource_bytes(_registry_payloads()).fields
    assert fields.targetless_aggregations == (AggregationFunction.COUNT,)
    assert all(
        AggregationFunction.COUNT not in field.aggregations for field in fields.entries.values()
    )
    assert {function for field in fields.entries.values() for function in field.aggregations} <= {
        AggregationFunction.MIN,
        AggregationFunction.MAX,
        AggregationFunction.SUM,
        AggregationFunction.AVG,
    }


def test_state_registry_contains_only_phase2_supported_validated_eligibility_rules() -> None:
    """Only frozen domestic bond and domestic-listed eligibility rules load."""
    from finproof.registry.loader import RegistryBundle

    states = RegistryBundle._from_resource_bytes(_registry_payloads()).states
    assert states.version == "1.1.0"
    assert tuple(states.entries) == (
        "bond.source_buyable",
        "bond.validated_buyable_at_as_of",
        "domestic_listed.active_at_as_of",
    )
    assert {
        product_type
        for rule in states.entries.values()
        for product_type in cast(tuple[str, ...], rule["product_types"])
    } == {"domestic_bond", "domestic_etf", "domestic_etn"}


def test_registry_bundle_reuses_exact_rating_registry_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The eighth member is the existing exact registry, never a parallel/subclass DTO."""
    import finproof.registry.loader as loader
    from finproof.registry.loader import RegistryBundle
    from finproof.registry.rating import RatingRegistry

    bundle = RegistryBundle._from_resource_bytes(_registry_payloads())
    assert type(bundle.ratings) is RatingRegistry

    class ForeignRatingRegistry(RatingRegistry):
        pass

    monkeypatch.setattr(loader, "RatingRegistry", ForeignRatingRegistry)
    with pytest.raises(TypeError):
        RegistryBundle._from_resource_bytes(_registry_payloads())
