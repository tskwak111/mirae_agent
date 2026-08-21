"""Data-quality registry contracts."""

from collections.abc import Mapping

from finproof.registry.models import FrozenRegistry


class QualityRegistry(FrozenRegistry):
    version: str
    statuses: tuple[str, ...]
    entries: Mapping[str, Mapping[str, object]]
