"""Immutable artifact build configuration contracts."""

import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, BinaryIO, Self

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.safe_files import (
    ExpectedDirectoryIdentity,
    SafeFileReadError,
    read_held_regular_file,
)


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that refuses duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("duplicate YAML key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class ArtifactBuildOptions(BaseModel):
    """Caller-controlled options for one artifact generation."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    clean: bool = False
    persistence_timestamp: datetime

    @model_validator(mode="after")
    def require_aware_utc_timestamp(self) -> Self:
        if (
            self.persistence_timestamp.tzinfo is None
            or self.persistence_timestamp.utcoffset() != timedelta(0)
        ):
            raise ValueError("persistence_timestamp must be timezone-aware UTC")
        return self


class ArtifactSourceExpectation(BaseModel):
    """Expected physical source dimensions."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    table: str
    rows: int
    columns: int
    cells: int


class ArtifactRegistryVersions(BaseModel):
    """Registry versions bound to one build."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    dataset: str
    quality: str
    rating: str
    state: str


class ArtifactSilverCounts(BaseModel):
    """Expected emitted Silver row counts."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bond_instrument: int
    domestic_listed_product: int
    overseas_listed_product: int
    fund_item: int
    fund_item_attribute: int


class ArtifactExactLinkExpectations(BaseModel):
    """Expected exact-link outputs."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    links: int
    evidence: int
    pair_sha256: str


class ArtifactParquetOptions(BaseModel):
    """Deterministic Parquet writer options."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    compression: str
    compression_level: int
    statistics: bool
    row_group_size: int
    data_page_size: int
    writer_batch_rows: int


class ArtifactStagingOptions(BaseModel):
    """Bounded staging engine options."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    threads: int
    memory_limit: str


class ArtifactBuildConfig(BaseModel):
    """Typed view of the artifact build baseline."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    version: str
    artifact_contract_version: str
    artifact_set_id: str
    dataset_snapshot_date: date
    registry_versions: ArtifactRegistryVersions
    sources: tuple[ArtifactSourceExpectation, ...]
    silver_counts: ArtifactSilverCounts
    quarantine_source_rows: int
    exact_links: ArtifactExactLinkExpectations
    parquet: ArtifactParquetOptions
    staging: ArtifactStagingOptions

    @classmethod
    def from_held_stream(
        cls,
        stream: BinaryIO,
        *,
        versions: VersionBundle,
    ) -> Self:
        """Parse the frozen build config from one caller-held verified stream."""
        try:
            return cls._parse_frozen_payload(_read_held_stream(stream), versions=versions)
        except (OSError, UnicodeError, TypeError, ValueError, yaml.YAMLError) as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.CONFIG_INVALID,
                operation_id="load-artifact-config",
                internal_context={"reason": "invalid_yaml_or_shape"},
            ) from exc

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        repository_root: Path,
        versions: VersionBundle,
    ) -> Self:
        """Parse one artifact baseline; later validators close its trust boundary."""
        try:
            repository_stat = repository_root.lstat()
            if not repository_root.is_absolute() or not repository_root.is_dir():
                raise SafeFileReadError("repository root is not an absolute directory")
            if stat.S_IFMT(repository_stat.st_mode) != stat.S_IFDIR:
                raise SafeFileReadError("repository root is not a nonsymlink directory")
            repository_identity = ExpectedDirectoryIdentity.from_stat(
                repository_root, repository_stat
            )
            if path != repository_root / "config/artifact_build.yaml":
                raise SafeFileReadError("config path is not the frozen repository path")
            payload = read_held_regular_file(path, expected_directory=repository_identity)
            return cls._parse_frozen_payload(payload, versions=versions)
        except (
            OSError,
            SafeFileReadError,
            UnicodeError,
            TypeError,
            ValueError,
            yaml.YAMLError,
        ) as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.CONFIG_INVALID,
                operation_id="load-artifact-config",
                internal_context={"reason": "invalid_yaml_or_shape"},
            ) from exc

    @classmethod
    def _parse_frozen_payload(cls, raw: bytes, *, versions: VersionBundle) -> Self:
        _require_config_versions(versions)
        payload = yaml.load(raw.decode("utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506
        model_payload = payload
        if isinstance(payload, dict) and isinstance(payload.get("sources"), list):
            model_payload = {**payload, "sources": tuple(payload["sources"])}
        config = cls.model_validate(model_payload)
        expected = cls.model_validate(_EXPECTED_ARTIFACT_CONFIG)
        if config != expected or not _same_container_shape(payload, _EXPECTED_ARTIFACT_CONFIG):
            raise ValueError("artifact config does not match the frozen baseline")
        return config


def _same_container_shape(actual: object, expected: object) -> bool:
    if isinstance(expected, Mapping):
        return (
            isinstance(actual, Mapping)
            and actual.keys() == expected.keys()
            and all(
                _same_container_shape(actual[key], expected_value)
                for key, expected_value in expected.items()
            )
        )
    if isinstance(expected, tuple):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _same_container_shape(actual_item, expected_item)
                for actual_item, expected_item in zip(actual, expected, strict=True)
            )
        )
    return True


_EXPECTED_ARTIFACT_CONFIG: dict[str, Any] = {
    "version": "1.0.0",
    "artifact_contract_version": "1.0.0",
    "artifact_set_id": "finproof-data-artifacts/v1",
    "dataset_snapshot_date": date(2026, 7, 11),
    "registry_versions": {
        "dataset": "1.0.0",
        "quality": "1.0.0",
        "rating": "1.0.0",
        "state": "1.0.0",
    },
    "sources": (
        {
            "table": "PRBD01N001",
            "rows": 42_394,
            "columns": 40,
            "cells": 1_695_760,
        },
        {
            "table": "PREF01N001",
            "rows": 1_734,
            "columns": 73,
            "cells": 126_582,
        },
        {
            "table": "PREF02N001",
            "rows": 5_646,
            "columns": 49,
            "cells": 276_654,
        },
        {
            "table": "PRFD01N001",
            "rows": 95_619,
            "columns": 45,
            "cells": 4_302_855,
        },
    ),
    "silver_counts": {
        "bond_instrument": 42_394,
        "domestic_listed_product": 1_733,
        "overseas_listed_product": 5_646,
        "fund_item": 11_138,
        "fund_item_attribute": 95_618,
    },
    "quarantine_source_rows": 2,
    "exact_links": {
        "links": 47,
        "evidence": 371,
        "pair_sha256": ("8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962"),
    },
    "parquet": {
        "compression": "zstd",
        "compression_level": 3,
        "statistics": True,
        "row_group_size": 65_536,
        "data_page_size": 1_048_576,
        "writer_batch_rows": 65_536,
    },
    "staging": {"threads": 1, "memory_limit": "1GiB"},
}


class ArtifactInputNamespace(StrEnum):
    """Closed logical roots for direct build inputs."""

    SOURCE_ROOT = "source_root"
    REPOSITORY = "repository"


class ArtifactInputKind(StrEnum):
    """Closed direct build-input roles."""

    SOURCE_MANIFEST = "source_manifest"
    SOURCE_SCHEMA_CATALOG = "source_schema_catalog"
    ARTIFACT_BUILD_CONFIG = "artifact_build_config"
    DATASET_REGISTRY = "dataset_registry"
    QUALITY_RULE_REGISTRY = "quality_rule_registry"
    RATING_SCALE_REGISTRY = "rating_scale_registry"
    STATE_RULE_REGISTRY = "state_rule_registry"
    ARTIFACT_MANIFEST_SCHEMA = "artifact_manifest_schema"
    QUALITY_ISSUE_SCHEMA = "quality_issue_schema"


_RESOLVER_TOKEN = object()


@dataclass(frozen=True, init=False)
class ResolvedArtifactInput:
    """Canonical descriptor for one direct build input."""

    namespace: ArtifactInputNamespace
    path: str
    kind: ArtifactInputKind
    absolute_path: Path

    def __init__(
        self,
        namespace: ArtifactInputNamespace,
        path: str,
        kind: ArtifactInputKind,
        absolute_path: Path,
        *,
        _resolver_token: object,
    ) -> None:
        if _resolver_token is not _RESOLVER_TOKEN:
            raise ValueError("ResolvedArtifactInput is resolver-owned")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "absolute_path", absolute_path)


def resolve_logical_inputs(settings: Settings) -> tuple[ResolvedArtifactInput, ...]:
    """Resolve the closed direct-input inventory."""
    try:
        if _LOGICAL_INPUT_DECLARATIONS != _EXPECTED_LOGICAL_INPUT_DECLARATIONS:
            raise ValueError("logical input declarations differ from the closed inventory")
        resolved: list[ResolvedArtifactInput] = []
        for namespace, relative_path, kind in _LOGICAL_INPUT_DECLARATIONS:
            root = (
                settings.source_root
                if namespace is ArtifactInputNamespace.SOURCE_ROOT
                else settings.repository_root
            )
            _validate_logical_input_path(root, relative_path)
            resolved.append(
                ResolvedArtifactInput(
                    namespace=namespace,
                    path=relative_path,
                    kind=kind,
                    absolute_path=root / relative_path,
                    _resolver_token=_RESOLVER_TOKEN,
                )
            )
        return tuple(resolved)
    except (OSError, TypeError, ValueError) as exc:
        raise ArtifactContractError(
            ArtifactErrorCode.CONFIG_INVALID,
            operation_id="resolve-logical-inputs",
            internal_context={"reason": "invalid_logical_input_declaration"},
        ) from exc


def _validate_logical_input_path(root: Path, relative_path: str) -> None:
    if type(relative_path) is not str:
        raise TypeError("logical input path must be an exact string")
    components = relative_path.split("/")
    if (
        not relative_path
        or relative_path.startswith("/")
        or "\\" in relative_path
        or "\x00" in relative_path
        or "%" in relative_path
        or any(component in {"", ".", ".."} for component in components)
        or components[0] == root.name
    ):
        raise ValueError("logical input path is not canonical POSIX")
    current = root
    for index, component in enumerate(components):
        current /= component
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("logical input path contains a symlink")
        is_leaf = index == len(components) - 1
        expected_type = stat.S_IFREG if is_leaf else stat.S_IFDIR
        if stat.S_IFMT(metadata.st_mode) != expected_type:
            raise ValueError("logical input component has the wrong type")


_EXPECTED_LOGICAL_INPUT_DECLARATIONS = (
    (
        ArtifactInputNamespace.SOURCE_ROOT,
        "input_manifest.json",
        ArtifactInputKind.SOURCE_MANIFEST,
    ),
    (
        ArtifactInputNamespace.SOURCE_ROOT,
        "schema_catalog.json",
        ArtifactInputKind.SOURCE_SCHEMA_CATALOG,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/artifact_build.yaml",
        ArtifactInputKind.ARTIFACT_BUILD_CONFIG,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/datasets.yaml",
        ArtifactInputKind.DATASET_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/quality_rules.yaml",
        ArtifactInputKind.QUALITY_RULE_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/rating_scale.yaml",
        ArtifactInputKind.RATING_SCALE_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/state_rules.yaml",
        ArtifactInputKind.STATE_RULE_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "schemas/artifact_manifest.schema.json",
        ArtifactInputKind.ARTIFACT_MANIFEST_SCHEMA,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "schemas/quality_issue.schema.json",
        ArtifactInputKind.QUALITY_ISSUE_SCHEMA,
    ),
)

_LOGICAL_INPUT_DECLARATIONS = _EXPECTED_LOGICAL_INPUT_DECLARATIONS


def validate_build_registry_versions(
    settings: Settings,
    versions: VersionBundle,
) -> None:
    """Validate build-time registry headers against the version bundle."""
    try:
        config_root = settings.repository_root / "config"
        datasets = _load_registry(config_root / "datasets.yaml")
        quality = _load_registry(config_root / "quality_rules.yaml")
        rating = _load_registry(config_root / "rating_scale.yaml")
        state = _load_registry(config_root / "state_rules.yaml")
        if (
            datasets.get("version") != "1.0.0"
            or datasets.get("snapshot_date") != "2026-07-11"
            or quality.get("version") != versions.quality_rule_version
            or rating.get("version") != versions.rating_rule_version
            or state.get("version") != versions.state_rule_version
            or versions.dataset_version != date(2026, 7, 11)
            or versions.quality_rule_version != "1.0.0"
            or versions.rating_rule_version != "1.0.0"
            or versions.state_rule_version != "1.0.0"
        ):
            raise ValueError("build registry version mismatch")
    except (OSError, SafeFileReadError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise ArtifactContractError(
            ArtifactErrorCode.CONFIG_INVALID,
            operation_id="validate-build-registry-versions",
            internal_context={"reason": "registry_version_mismatch"},
        ) from exc


def validate_build_registry_versions_from_held_streams(
    *,
    datasets: BinaryIO,
    quality: BinaryIO,
    rating: BinaryIO,
    state: BinaryIO,
    versions: VersionBundle,
) -> None:
    """Validate exact registry headers from four caller-held verified streams."""
    try:
        _validate_registry_payloads(
            datasets=_load_registry_bytes(_read_held_stream(datasets)),
            quality=_load_registry_bytes(_read_held_stream(quality)),
            rating=_load_registry_bytes(_read_held_stream(rating)),
            state=_load_registry_bytes(_read_held_stream(state)),
            versions=versions,
        )
    except (OSError, UnicodeError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise ArtifactContractError(
            ArtifactErrorCode.CONFIG_INVALID,
            operation_id="validate-build-registry-versions",
            internal_context={"reason": "registry_version_mismatch"},
        ) from exc


def _load_registry(path: Path) -> Mapping[str, object]:
    return _load_registry_bytes(read_held_regular_file(path))


def _load_registry_bytes(raw: bytes) -> Mapping[str, object]:
    payload = yaml.load(raw.decode("utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506
    if not isinstance(payload, Mapping):
        raise TypeError("registry must be a mapping")
    return payload


def _validate_registry_payloads(
    *,
    datasets: Mapping[str, object],
    quality: Mapping[str, object],
    rating: Mapping[str, object],
    state: Mapping[str, object],
    versions: VersionBundle,
) -> None:
    if (
        datasets.get("version") != "1.0.0"
        or datasets.get("snapshot_date") != "2026-07-11"
        or quality.get("version") != versions.quality_rule_version
        or rating.get("version") != versions.rating_rule_version
        or state.get("version") != versions.state_rule_version
        or versions.dataset_version != date(2026, 7, 11)
        or versions.quality_rule_version != "1.0.0"
        or versions.rating_rule_version != "1.0.0"
        or versions.state_rule_version != "1.0.0"
    ):
        raise ValueError("build registry version mismatch")


def _require_config_versions(versions: VersionBundle) -> None:
    if (
        type(versions) is not VersionBundle
        or versions.dataset_version != date(2026, 7, 11)
        or versions.quality_rule_version != "1.0.0"
        or versions.rating_rule_version != "1.0.0"
        or versions.state_rule_version != "1.0.0"
    ):
        raise ValueError("artifact config version bundle mismatch")


def _read_held_stream(stream: BinaryIO, *, maximum_bytes: int = 1_048_576) -> bytes:
    if not hasattr(stream, "seek") or not hasattr(stream, "read"):
        raise TypeError("held input stream must be seekable binary IO")
    stream.seek(0)
    payload = stream.read(maximum_bytes + 1)
    if type(payload) is not bytes or len(payload) > maximum_bytes:
        raise ValueError("held input stream is invalid or exceeds its bound")
    return payload
