"""Controlled deterministic entity resolution."""

from finproof.entity.cross_source import ExactCrossSourceLinkRepository
from finproof.entity.index import EntityIndex
from finproof.entity.models import ResolutionCandidate, ResolutionMatchKind, ResolutionResult
from finproof.entity.normalization import normalize_product_text
from finproof.entity.resolver import EntityResolver

__all__ = [
    "EntityIndex",
    "EntityResolver",
    "ExactCrossSourceLinkRepository",
    "ResolutionCandidate",
    "ResolutionMatchKind",
    "ResolutionResult",
    "normalize_product_text",
]
