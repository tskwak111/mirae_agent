"""Typed application settings."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

OFFICIAL_DISTRIBUTION_DATE = date(2026, 8, 24)
OFFICIAL_COVERAGE_DATES = MappingProxyType(
    {
        "domestic_bond": date(2026, 8, 22),
        "domestic_etf": date(2026, 8, 22),
        "domestic_etn": date(2026, 8, 22),
        "overseas_etf": date(2026, 8, 23),
        "overseas_etn": date(2026, 8, 23),
        "public_fund": date(2026, 8, 22),
    }
)
EVALUATION_SNAPSHOT_DATE = OFFICIAL_DISTRIBUTION_DATE


class ExecutionMode(StrEnum):
    """Supported FinProof runtime modes."""

    EVALUATION = "evaluation"
    EXTENDED_DEMO = "extended_demo"


class Settings(BaseSettings):
    """Validated FinProof runtime configuration."""

    model_config = SettingsConfigDict(
        env_prefix="FINPROOF_", env_file=None, extra="ignore", frozen=True
    )

    execution_mode: ExecutionMode = ExecutionMode.EVALUATION
    dataset_snapshot_date: date = EVALUATION_SNAPSHOT_DATE
    repository_root: Path = Path(".")
    source_root: Path = Path("source_material")
    data_dir: Path = Path("source_material/data")
    artifact_dir: Path = Path("artifacts")
    database_path: Path = Path("artifacts/finproof.duckdb")
    artifact_build_config_path: Path = Path("config/artifact_build.yaml")
    expected_artifact_contract_path: Path = Path("config/expected_phase1_artifacts.json")
    default_top_k: int = Field(default=5, ge=1)
    max_top_k: int = Field(default=50, ge=1, le=100)
    hcx_enabled: bool = False
    hcx_api_key: SecretStr | None = None
    hcx_model_name: str = "HCX-007"

    @model_validator(mode="before")
    @classmethod
    def resolve_build_paths(cls, values: Any) -> Any:
        """Resolve build paths once from the explicit repository anchor."""
        if not isinstance(values, dict):
            return values
        resolved = dict(values)
        repository_input = Path(resolved.get("repository_root", ".")).expanduser()
        repository_absolute = (
            repository_input if repository_input.is_absolute() else Path.cwd() / repository_input
        )
        _require_existing_directory(repository_absolute, "repository_root")
        repository = repository_absolute.resolve(strict=True)
        resolved["repository_root"] = repository

        defaults = {
            "source_root": Path("source_material"),
            "data_dir": Path("source_material/data"),
            "artifact_dir": Path("artifacts"),
            "database_path": Path("artifacts/finproof.duckdb"),
            "artifact_build_config_path": Path("config/artifact_build.yaml"),
            "expected_artifact_contract_path": Path("config/expected_phase1_artifacts.json"),
        }
        directory_fields = {"source_root", "data_dir", "artifact_dir"}
        for field, default in defaults.items():
            path_input = Path(resolved.get(field, default)).expanduser()
            absolute = path_input if path_input.is_absolute() else repository / path_input
            _reject_symlink_components(absolute)
            _require_existing_components_are_directories(
                absolute,
                leaf_is_directory=field in directory_fields,
                field=field,
            )
            resolved[field] = absolute.resolve(strict=False)
        return resolved

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        """Reject a default result count that exceeds the hard maximum."""
        if (
            self.execution_mode is ExecutionMode.EVALUATION
            and self.dataset_snapshot_date != EVALUATION_SNAPSHOT_DATE
        ):
            raise ValueError("evaluation dataset_snapshot_date must be 2026-08-24")
        if self.default_top_k > self.max_top_k:
            raise ValueError("default_top_k must not exceed max_top_k")
        if not self.hcx_model_name.startswith("HCX-"):
            raise ValueError("hcx_model_name must start with HCX-")
        if self.hcx_enabled and (
            self.hcx_api_key is None or not self.hcx_api_key.get_secret_value().strip()
        ):
            raise ValueError("HCX API key is required when HCX is enabled")
        if not self.source_root.is_relative_to(self.repository_root):
            raise ValueError("source_root must be inside repository_root")
        if self.data_dir != self.source_root / "data":
            raise ValueError("data_dir must equal source_root/data")
        config_root = self.repository_root / "config"
        if not self.artifact_build_config_path.is_relative_to(config_root):
            raise ValueError("artifact_build_config_path must be inside repository config")
        if not self.expected_artifact_contract_path.is_relative_to(config_root):
            raise ValueError("expected_artifact_contract_path must be inside repository config")
        home = Path.home().resolve(strict=False)
        if self.artifact_dir in {
            self.repository_root,
            Path(self.artifact_dir.anchor),
            home,
        }:
            raise ValueError("artifact_dir is an unsafe target")
        if self.artifact_dir.is_relative_to(self.source_root):
            raise ValueError("artifact_dir must not be inside source_root")
        if self.database_path != self.artifact_dir / "finproof.duckdb":
            raise ValueError("database_path must equal artifact_dir/finproof.duckdb")
        if len({self.source_root, self.artifact_dir, self.database_path}) != 3:
            raise ValueError("source_root, artifact_dir, and database_path must be distinct")
        return self


def _require_existing_directory(path: Path, field: str) -> None:
    _reject_symlink_components(path)
    if not path.exists() or not path.is_dir():
        raise ValueError(f"{field} must be an existing directory")


def _require_existing_components_are_directories(
    path: Path, *, leaf_is_directory: bool, field: str
) -> None:
    """Require every existing ancestor and directory leaf to remain a directory."""
    current = Path(path.anchor)
    parts = path.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        is_leaf = index == len(parts) - 1
        if current.exists() and (not is_leaf or leaf_is_directory) and not current.is_dir():
            raise ValueError(f"{field} has a non-directory path component")


def _reject_symlink_components(path: Path) -> None:
    """Reject every existing symbolic-link component without following it."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"build path contains a symbolic link: {current.name}")
