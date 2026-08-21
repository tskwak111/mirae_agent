"""Shared strict registry contracts."""

from collections.abc import Mapping
from datetime import date

from pydantic import BaseModel, ConfigDict


class FrozenRegistry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class DatasetRegistry(FrozenRegistry):
    version: str
    snapshot_date: date
    entries: Mapping[str, Mapping[str, object]]
