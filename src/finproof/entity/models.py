"""Closed entity-resolution result contracts."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from finproof.domain.query_plan import ProductType


class ResolutionMatchKind(StrEnum):
    EXACT_PRODUCT_ID = "exact_product_id"
    EXACT_IDENTIFIER = "exact_identifier"
    EXACT_NAME = "exact_name"
    FUZZY_CANDIDATE = "fuzzy_candidate"


class ResolutionCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    product_id: Annotated[str, Field(min_length=1, max_length=300)]
    product_type: ProductType
    name: Annotated[str, Field(min_length=1, max_length=500)]
    match_kind: ResolutionMatchKind
    score: Annotated[int, Field(ge=0, le=10_000)]


class ResolutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    selected: ResolutionCandidate | None
    candidates: Annotated[tuple[ResolutionCandidate, ...], Field(max_length=5)]


class HoldingResolutionCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    constituent_identifier: Annotated[str, Field(min_length=1, max_length=300)]
    constituent_identifier_type: Annotated[str, Field(min_length=1, max_length=100)]
    display_name: Annotated[str, Field(min_length=1, max_length=500)]


class HoldingResolutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    selected: HoldingResolutionCandidate | None
    candidates: Annotated[tuple[HoldingResolutionCandidate, ...], Field(max_length=5)]
