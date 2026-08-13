"""Immutable typed wrappers for normalized and derived source values."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import QualityStatus

NonEmptyText = Annotated[str, StringConstraints(min_length=1)]


class NormalizedValue[ValueT](BaseModel):
    """One typed source value together with its exact raw lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    raw_value: str
    normalized_value: ValueT | None
    quality_status: QualityStatus
    rule_id: NonEmptyText
    rule_version: NonEmptyText
    source: SourceCellLocator


class DerivedValue[ValueT](BaseModel):
    """One deterministic derived value and the locators used to derive it."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    value: ValueT | None
    quality_status: QualityStatus
    rule_id: NonEmptyText
    rule_version: NonEmptyText
    as_of_date: date
    inputs: tuple[SourceCellLocator, ...]
