"""Validated product-state registry contracts."""

from collections.abc import Mapping

from finproof.registry.models import FrozenRegistry


class StateRegistry(FrozenRegistry):
    version: str
    entries: Mapping[str, Mapping[str, object]]
