"""Typed application settings."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EVALUATION_SNAPSHOT_DATE = date(2026, 7, 11)


class ExecutionMode(StrEnum):
    """Supported FinProof runtime modes."""

    EVALUATION = "evaluation"
    EXTENDED_DEMO = "extended_demo"


class Settings(BaseSettings):
    """Validated FinProof runtime configuration."""

    model_config = SettingsConfigDict(env_prefix="FINPROOF_", env_file=".env", extra="ignore")

    execution_mode: ExecutionMode = ExecutionMode.EVALUATION
    dataset_snapshot_date: date = EVALUATION_SNAPSHOT_DATE
    data_dir: Path = Path("source_material/data")
    artifact_dir: Path = Path("artifacts")
    database_path: Path = Path("artifacts/finproof.duckdb")
    default_top_k: int = Field(default=5, ge=1)
    max_top_k: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        """Reject a default result count that exceeds the hard maximum."""
        if (
            self.execution_mode is ExecutionMode.EVALUATION
            and self.dataset_snapshot_date != EVALUATION_SNAPSHOT_DATE
        ):
            raise ValueError("evaluation dataset_snapshot_date must be 2026-07-11")
        if self.default_top_k > self.max_top_k:
            raise ValueError("default_top_k must not exceed max_top_k")
        return self
