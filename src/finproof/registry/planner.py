"""Planner-alias registry contracts."""

from collections.abc import Mapping

from finproof.registry.models import FrozenRegistry


class PlannerRegistry(FrozenRegistry):
    version: str
    product_type_aliases: Mapping[str, tuple[str, ...]]
    field_aliases: Mapping[str, tuple[str, ...]]
    period_aliases: Mapping[str, tuple[str, ...]]
    ranking_aliases: Mapping[str, tuple[str, ...]]
