"""Deterministic answer-policy registry contracts."""

from collections.abc import Mapping

from finproof.registry.models import FrozenRegistry


class AnswerRegistry(FrozenRegistry):
    version: str
    document: Mapping[str, object]
