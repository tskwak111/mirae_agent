"""Artifact build foundation contracts."""

from __future__ import annotations

import builtins
import json
import os
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from pydantic import ValidationError

from tests.helpers.artifacts import expected_contract_payload

if TYPE_CHECKING:
    from finproof.data.artifacts.expected_contract import (
        ArtifactLogicalContractView,
        ExpectedLogicalInput,
        ExpectedLogicalTable,
        ExpectedPhase1ArtifactContract,
        ExpectedSemanticReport,
    )


class _SyntheticArtifactLogicalContract:
    def __init__(
        self,
        expected: ExpectedPhase1ArtifactContract,
        *,
        logical_inputs: tuple[ExpectedLogicalInput, ...] | None = None,
        tables: tuple[ExpectedLogicalTable, ...] | None = None,
        reports: tuple[ExpectedSemanticReport, ...] | None = None,
    ) -> None:
        self._expected = expected
        self._logical_inputs = logical_inputs or expected.logical_inputs
        self._tables = tables or expected.tables
        self._reports = reports or expected.reports

    @property
    def artifact_contract_version(self) -> str:
        return self._expected.artifact_contract_version

    @property
    def artifact_set_id(self) -> str:
        return self._expected.artifact_set_id

    @property
    def dataset_version(self) -> date:
        return self._expected.dataset_version

    @property
    def logical_inputs(self) -> tuple[ExpectedLogicalInput, ...]:
        return self._logical_inputs

    @property
    def tables(self) -> tuple[ExpectedLogicalTable, ...]:
        return self._tables

    @property
    def reports(self) -> tuple[ExpectedSemanticReport, ...]:
        return self._reports

    @property
    def overall_manifest_logical_hash(self) -> str:
        return self._expected.overall_manifest_logical_hash

    @property
    def exact_link_pair_sha256(self) -> str:
        return self._expected.exact_link_pair_sha256

    @property
    def exact_link_evidence_count(self) -> int:
        return self._expected.exact_link_evidence_count


class _StringSubclass(str):
    pass


_VALID_ARTIFACT_CONFIG = """\
version: 1.0.0
artifact_contract_version: 1.0.0
artifact_set_id: finproof-data-artifacts/v1
dataset_snapshot_date: 2026-07-11
registry_versions:
  dataset: 1.0.0
  quality: 1.0.0
  rating: 1.0.0
  state: 1.0.0
sources:
  - table: PRBD01N001
    rows: 42394
    columns: 40
    cells: 1695760
  - table: PREF01N001
    rows: 1734
    columns: 73
    cells: 126582
  - table: PREF02N001
    rows: 5646
    columns: 49
    cells: 276654
  - table: PRFD01N001
    rows: 95619
    columns: 45
    cells: 4302855
silver_counts:
  bond_instrument: 42394
  domestic_listed_product: 1733
  overseas_listed_product: 5646
  fund_item: 11138
  fund_item_attribute: 95618
quarantine_source_rows: 2
exact_links:
  links: 47
  evidence: 371
  pair_sha256: 8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962
parquet:
  compression: zstd
  compression_level: 3
  statistics: true
  row_group_size: 65536
  data_page_size: 1048576
  writer_batch_rows: 65536
staging:
  threads: 1
  memory_limit: 1GiB
"""


def _write_valid_artifact_config(repository_root: Path) -> Path:
    config_path = repository_root / "config/artifact_build.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(_VALID_ARTIFACT_CONFIG, encoding="utf-8")
    return config_path


def _mutate_frozen_artifact_config(config: Any, case: str) -> None:
    if case == "top-level":
        config.version = "forged"
    elif case == "source":
        config.sources[0].rows = 0
    elif case == "registry":
        config.registry_versions.dataset = "forged"
    elif case == "silver":
        config.silver_counts.bond_instrument = 0
    elif case == "links":
        config.exact_links.links = 0
    elif case == "parquet":
        config.parquet.compression = "forged"
    else:
        config.staging.threads = 2


def test_repository_artifact_build_config_matches_frozen_model() -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig

    repository_root = Path(__file__).parents[4]
    config_path = repository_root / "config/artifact_build.yaml"

    loaded = ArtifactBuildConfig.load(
        config_path,
        repository_root=repository_root,
        versions=VersionBundle(),
    )

    assert loaded.artifact_set_id == "finproof-data-artifacts/v1"


def _synthetic_build_settings(repository_root: Path) -> object:
    from finproof.core.settings import Settings

    source_root = repository_root / "source_material"
    data_dir = source_root / "data"
    data_dir.mkdir(parents=True)
    (source_root / "input_manifest.json").write_text("{}", encoding="utf-8")
    (source_root / "schema_catalog.json").write_text("{}", encoding="utf-8")
    config_dir = repository_root / "config"
    config_dir.mkdir()
    for name in (
        "artifact_build.yaml",
        "datasets.yaml",
        "quality_rules.yaml",
        "rating_scale.yaml",
        "state_rules.yaml",
    ):
        content = "version: 1.0.0\n"
        if name == "datasets.yaml":
            content += 'snapshot_date: "2026-07-11"\n'
        (config_dir / name).write_text(content, encoding="utf-8")
    schemas_dir = repository_root / "schemas"
    schemas_dir.mkdir()
    for name in ("artifact_manifest.schema.json", "quality_issue.schema.json"):
        (schemas_dir / name).write_text("{}", encoding="utf-8")
    return Settings(
        repository_root=repository_root,
        source_root=source_root,
        data_dir=data_dir,
        artifact_dir=repository_root / "artifacts",
        database_path=repository_root / "artifacts/finproof.duckdb",
        artifact_build_config_path=config_dir / "artifact_build.yaml",
        expected_artifact_contract_path=config_dir / "expected_phase1_artifacts.json",
    )


_CONFIG_MUTATION_IDS = [
    "version",
    "artifact-contract-version",
    "artifact-set-id",
    "snapshot-date",
    "registry-dataset",
    "registry-quality",
    "registry-rating",
    "registry-state",
    *[
        f"source-{aspect}-{table}"
        for table in ("PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001")
        for aspect in ("order", "rows", "columns", "cells")
    ],
    "silver-bond",
    "silver-domestic",
    "silver-overseas",
    "silver-fund-item",
    "silver-fund-attribute",
    "quarantine",
    "links",
    "evidence",
    "pair-sha256",
    "parquet-compression",
    "parquet-compression-level",
    "parquet-statistics",
    "parquet-row-group",
    "parquet-data-page",
    "parquet-writer-batch",
    "staging-threads",
    "staging-memory",
    "unknown-key",
    "duplicate-key",
]


def _mutate_artifact_config(case: str) -> str:
    if case == "duplicate-key":
        return _VALID_ARTIFACT_CONFIG + "version: 1.0.0\n"
    payload: dict[str, Any] = yaml.safe_load(_VALID_ARTIFACT_CONFIG)
    direct = {
        "version": ("version", "9.9.9"),
        "artifact-contract-version": ("artifact_contract_version", "9.9.9"),
        "artifact-set-id": ("artifact_set_id", "forged/v9"),
        "snapshot-date": ("dataset_snapshot_date", "2026-07-10"),
        "quarantine": ("quarantine_source_rows", 3),
    }
    if case in direct:
        key, value = direct[case]
        payload[key] = value
    elif case.startswith("registry-"):
        payload["registry_versions"][case.removeprefix("registry-")] = "9.9.9"
    elif case.startswith("source-"):
        _, aspect, table = case.split("-", 2)
        sources = payload["sources"]
        index = next(i for i, item in enumerate(sources) if item["table"] == table)
        if aspect == "order":
            item = sources.pop(index)
            sources.insert(0 if index else len(sources), item)
        else:
            sources[index][aspect] += 1
    elif case.startswith("silver-"):
        key = {
            "silver-bond": "bond_instrument",
            "silver-domestic": "domestic_listed_product",
            "silver-overseas": "overseas_listed_product",
            "silver-fund-item": "fund_item",
            "silver-fund-attribute": "fund_item_attribute",
        }[case]
        payload["silver_counts"][key] += 1
    elif case in {"links", "evidence"}:
        payload["exact_links"][case] += 1
    elif case == "pair-sha256":
        payload["exact_links"]["pair_sha256"] = "0" * 64
    elif case.startswith("parquet-"):
        key = {
            "parquet-compression": "compression",
            "parquet-compression-level": "compression_level",
            "parquet-statistics": "statistics",
            "parquet-row-group": "row_group_size",
            "parquet-data-page": "data_page_size",
            "parquet-writer-batch": "writer_batch_rows",
        }[case]
        current = payload["parquet"][key]
        payload["parquet"][key] = (
            not current
            if isinstance(current, bool)
            else ("snappy" if isinstance(current, str) else current + 1)
        )
    elif case == "staging-threads":
        payload["staging"]["threads"] = 2
    elif case == "staging-memory":
        payload["staging"]["memory_limit"] = "2GiB"
    elif case == "unknown-key":
        payload["unexpected"] = "accepted"
    else:
        raise AssertionError(case)
    return yaml.safe_dump(payload, sort_keys=False)


def test_options_require_one_aware_utc_timestamp() -> None:
    from finproof.data.artifacts.config import ArtifactBuildOptions

    kst = timezone(timedelta(hours=9))
    with pytest.raises(ValidationError):
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 14, 1, 2, 3))
    with pytest.raises(ValidationError):
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 14, 10, 2, 3, tzinfo=kst))
    options = ArtifactBuildOptions(
        persistence_timestamp=datetime(2026, 8, 14, 1, 2, 3, 456789, tzinfo=UTC)
    )
    assert options.persistence_timestamp.isoformat().endswith("+00:00")


def test_artifact_error_safe_message_never_exposes_parent_paths(tmp_path: Path) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    error = ArtifactContractError(
        ArtifactErrorCode.UNSAFE_TARGET,
        operation_id="op-0123456789abcdef",
        target_basename="artifacts",
        internal_context={
            "stage": str(tmp_path / "private/stage") * 256,
            "raw": "untrusted-payload" * 256,
        },
    )
    assert error.safe_message == (
        "artifact error unsafe_target for artifacts (op-0123456789abcdef)"
    )
    assert str(error) == error.safe_message
    assert "private" not in error.safe_message
    assert "stage" not in error.safe_message
    assert "raw" not in error.safe_message
    assert "untrusted-payload" not in error.safe_message
    assert len(error.safe_message) <= 512


@pytest.mark.parametrize(
    "operation_id",
    [
        None,
        1,
        True,
        "",
        "_leading",
        "-leading",
        " leading",
        "embedded space",
        "slash/value",
        "backslash\\value",
        "nul\x00value",
        "c0\x1fvalue",
        "c1\x80value",
        "비ascii",
        "a" * 129,
    ],
    ids=[
        "none",
        "integer",
        "boolean",
        "empty",
        "leading-underscore",
        "leading-hyphen",
        "leading-space",
        "embedded-space",
        "slash",
        "backslash",
        "nul",
        "c0-control",
        "c1-control",
        "non-ascii",
        "too-long",
    ],
)
def test_artifact_error_rejects_every_invalid_operation_id(operation_id: object) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    with pytest.raises((TypeError, ValueError)):
        ArtifactContractError(
            ArtifactErrorCode.UNSAFE_TARGET,
            operation_id=operation_id,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("operation_id", ["a", "a" * 128], ids=["one", "128"])
def test_artifact_error_accepts_operation_id_boundaries(operation_id: str) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    error = ArtifactContractError(
        ArtifactErrorCode.UNSAFE_TARGET,
        operation_id=operation_id,
    )
    assert error.operation_id == operation_id


@pytest.mark.parametrize(
    "target_basename",
    [
        1,
        True,
        "",
        ".",
        "..",
        "slash/value",
        "backslash\\value",
        "nul\x00value",
        "c0\x1fvalue",
        "c1\x80value",
        "carriage\rreturn",
        "line\nfeed",
        "line\u2028separator",
        "paragraph\u2029separator",
        "ansi\x1b[31m",
        "bidi\u202eoverride",
        "format\u200bcontrol",
        "nonbreaking\u00a0space",
        "a" * 129,
    ],
    ids=[
        "integer",
        "boolean",
        "empty",
        "dot",
        "dot-dot",
        "slash",
        "backslash",
        "nul",
        "c0-control",
        "c1-control",
        "cr",
        "lf",
        "unicode-line-separator",
        "unicode-paragraph-separator",
        "ansi-escape",
        "bidi-control",
        "format-control",
        "nonprintable-separator",
        "too-long",
    ],
)
def test_artifact_error_rejects_every_invalid_target_basename(
    target_basename: object,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    with pytest.raises((TypeError, ValueError)):
        ArtifactContractError(
            ArtifactErrorCode.UNSAFE_TARGET,
            operation_id="op-1",
            target_basename=target_basename,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("target_basename", [None, "한", "가" * 128], ids=["none", "one", "128"])
def test_artifact_error_accepts_target_basename_boundaries(
    target_basename: str | None,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    error = ArtifactContractError(
        ArtifactErrorCode.UNSAFE_TARGET,
        operation_id="op-1",
        target_basename=target_basename,
    )
    assert error.target_basename == target_basename


@pytest.mark.parametrize(
    "internal_context",
    [
        [],
        {1: "value"},
        {True: "value"},
        {_StringSubclass("key"): "value"},
        {"key": 1},
        {"key": True},
        {"key": _StringSubclass("value")},
        {"key": ["nested"]},
        {"key": {"nested": "value"}},
    ],
    ids=[
        "non-mapping",
        "integer-key",
        "boolean-key",
        "string-subclass-key",
        "integer-value",
        "boolean-value",
        "string-subclass-value",
        "nested-list-value",
        "nested-mapping-value",
    ],
)
def test_artifact_error_rejects_non_exact_string_internal_context(
    internal_context: object,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    with pytest.raises(TypeError):
        ArtifactContractError(
            ArtifactErrorCode.UNSAFE_TARGET,
            operation_id="op-1",
            internal_context=internal_context,  # type: ignore[arg-type]
        )


def test_artifact_error_copies_and_freezes_internal_context() -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    original = {"stage": "before"}
    error = ArtifactContractError(
        ArtifactErrorCode.UNSAFE_TARGET,
        operation_id="op-1",
        internal_context=original,
    )
    original["stage"] = "after"

    assert error.internal_context == {"stage": "before"}
    with pytest.raises(TypeError):
        error.internal_context["stage"] = "mutated"  # type: ignore[index]


def test_artifact_build_config_loads_valid_exact_baseline(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig

    repository_root = tmp_path / "repository"
    config_path = _write_valid_artifact_config(repository_root)

    config = ArtifactBuildConfig.load(
        config_path,
        repository_root=repository_root,
        versions=VersionBundle(),
    )

    assert config.version == "1.0.0"
    assert tuple(source.table for source in config.sources) == (
        "PRBD01N001",
        "PREF01N001",
        "PREF02N001",
        "PRFD01N001",
    )
    assert config.parquet.writer_batch_rows == 65_536
    assert config.staging.threads == 1


@pytest.mark.parametrize(
    "case",
    [
        "nonexistent-repository-root",
        "regular-file-repository-root",
        "symlink-repository-root",
        "outside-root-byte-identical-config",
        "leaf-symlink-config",
        "intermediate-parent-swap",
    ],
)
def test_artifact_build_config_rejects_unsafe_anchor_path_and_parent_race(
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    repository_root = tmp_path / "repository"
    config_path = _write_valid_artifact_config(repository_root)
    supplied_root = repository_root

    if case == "nonexistent-repository-root":
        supplied_root = tmp_path / "missing-repository"
    elif case == "regular-file-repository-root":
        supplied_root = tmp_path / "repository-file"
        supplied_root.write_text("not a directory", encoding="utf-8")
    elif case == "symlink-repository-root":
        supplied_root = tmp_path / "repository-link"
        supplied_root.symlink_to(repository_root, target_is_directory=True)
        config_path = supplied_root / "config/artifact_build.yaml"
    elif case == "outside-root-byte-identical-config":
        config_path = tmp_path / "outside-artifact-build.yaml"
        config_path.write_text(_VALID_ARTIFACT_CONFIG, encoding="utf-8")
    elif case == "leaf-symlink-config":
        outside = tmp_path / "outside-artifact-build.yaml"
        outside.write_text(_VALID_ARTIFACT_CONFIG, encoding="utf-8")
        config_path.unlink()
        config_path.symlink_to(outside)
    elif case == "intermediate-parent-swap":
        original_parent = config_path.parent
        moved_parent = repository_root / "config-original"
        external_parent = tmp_path / "external-config"
        _write_valid_artifact_config(external_parent.parent)
        generated_external_parent = external_parent.parent / "config"
        generated_external_parent.rename(external_parent)
        swapped = False
        real_builtin_open = builtins.open
        real_os_open = os.open

        def swap_parent_once() -> None:
            nonlocal swapped
            if swapped:
                return
            swapped = True
            original_parent.rename(moved_parent)
            original_parent.symlink_to(external_parent, target_is_directory=True)

        def racing_builtin_open(file: object, *args: object, **kwargs: object) -> object:
            if isinstance(file, (str, os.PathLike)) and Path(file).name == config_path.name:
                swap_parent_once()
            return real_builtin_open(file, *args, **kwargs)  # type: ignore[call-overload]

        def racing_os_open(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if Path(os.fsdecode(path)).name == config_path.name:
                swap_parent_once()
            return real_os_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(builtins, "open", racing_builtin_open)
        monkeypatch.setattr(os, "open", racing_os_open)

    with pytest.raises(ArtifactContractError) as caught:
        ArtifactBuildConfig.load(
            config_path,
            repository_root=supplied_root,
            versions=VersionBundle(),
        )
    assert caught.value.code is ArtifactErrorCode.CONFIG_INVALID


def test_artifact_build_config_rejects_repository_root_replacement_before_held_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import config as artifact_config
    from finproof.data.artifacts import safe_files
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    repository_root = tmp_path / "repository"
    config_path = _write_valid_artifact_config(repository_root)
    moved_root = tmp_path / "repository-held"
    real_read = safe_files.read_held_regular_file
    swapped = False

    def replace_root_before_read(
        path: Path,
        *,
        expected_directory: safe_files.ExpectedDirectoryIdentity | None = None,
    ) -> bytes:
        nonlocal swapped
        if not swapped:
            swapped = True
            repository_root.rename(moved_root)
            _write_valid_artifact_config(repository_root)
        return real_read(path, expected_directory=expected_directory)

    monkeypatch.setattr(
        "finproof.data.artifacts.config.read_held_regular_file",
        replace_root_before_read,
    )

    with pytest.raises(ArtifactContractError) as caught:
        artifact_config.ArtifactBuildConfig.load(
            config_path,
            repository_root=repository_root,
            versions=VersionBundle(),
        )
    assert caught.value.code is ArtifactErrorCode.CONFIG_INVALID


@pytest.mark.parametrize("case", _CONFIG_MUTATION_IDS)
def test_artifact_build_config_rejects_all_43_frozen_mutations(
    case: str,
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    repository_root = tmp_path / "repository"
    config_path = _write_valid_artifact_config(repository_root)
    config_path.write_text(_mutate_artifact_config(case), encoding="utf-8")

    with pytest.raises(ArtifactContractError) as caught:
        ArtifactBuildConfig.load(
            config_path,
            repository_root=repository_root,
            versions=VersionBundle(),
        )
    assert caught.value.code is ArtifactErrorCode.CONFIG_INVALID


@pytest.mark.parametrize(
    "case",
    ["quoted-source-rows", "quoted-threads", "integer-statistics", "quoted-date"],
)
def test_artifact_build_config_rejects_yaml_scalar_type_coercion(
    case: str,
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    replacement = {
        "quoted-source-rows": ("    rows: 42394", '    rows: "42394"'),
        "quoted-threads": ("  threads: 1", '  threads: "1"'),
        "integer-statistics": ("  statistics: true", "  statistics: 1"),
        "quoted-date": (
            "dataset_snapshot_date: 2026-07-11",
            'dataset_snapshot_date: "2026-07-11"',
        ),
    }[case]
    repository_root = tmp_path / "repository"
    config_path = _write_valid_artifact_config(repository_root)
    config_path.write_text(
        _VALID_ARTIFACT_CONFIG.replace(*replacement),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactContractError) as caught:
        ArtifactBuildConfig.load(
            config_path,
            repository_root=repository_root,
            versions=VersionBundle(),
        )
    assert caught.value.code is ArtifactErrorCode.CONFIG_INVALID


@pytest.mark.parametrize(
    "case",
    ["top-level", "source", "registry", "silver", "links", "parquet", "staging"],
)
def test_artifact_build_config_is_deeply_frozen(case: str, tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig

    repository_root = tmp_path / "repository"
    config_path = _write_valid_artifact_config(repository_root)
    config = ArtifactBuildConfig.load(
        config_path,
        repository_root=repository_root,
        versions=VersionBundle(),
    )

    with pytest.raises(ValidationError):
        _mutate_frozen_artifact_config(config, case)


def test_expected_contract_accepts_exact_synthetic_contract() -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    contract = ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())

    assert contract.dataset_version.isoformat() == "2026-07-11"
    assert len(contract.logical_inputs) == 9
    assert len(contract.tables) == 11
    assert tuple(report.report_id for report in contract.reports) == (
        "source_audit",
        "quality_summary",
    )


@pytest.mark.parametrize("case", ["top-level", "logical-input", "table", "report"])
def test_expected_contract_rejects_extra_fields(case: str) -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    payload = expected_contract_payload()
    if case == "top-level":
        payload["unexpected"] = "forged"
    elif case == "logical-input":
        payload["logical_inputs"][0]["unexpected"] = "forged"
    elif case == "table":
        payload["tables"][0]["unexpected"] = "forged"
    else:
        payload["reports"][0]["unexpected"] = "forged"

    with pytest.raises(ValidationError):
        ExpectedPhase1ArtifactContract.model_validate(payload)


def test_expected_contract_requires_official_dataset_date() -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    payload = expected_contract_payload()
    payload["dataset_version"] = date(2026, 7, 10)

    with pytest.raises(ValidationError, match="2026-07-11"):
        ExpectedPhase1ArtifactContract.model_validate(payload)


def test_expected_contract_rejects_reordered_logical_inputs() -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    payload = expected_contract_payload()
    payload["logical_inputs"] = tuple(reversed(payload["logical_inputs"]))

    with pytest.raises(ValidationError, match="logical_inputs"):
        ExpectedPhase1ArtifactContract.model_validate(payload)


def test_expected_contract_rejects_reordered_tables() -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    payload = expected_contract_payload()
    payload["tables"] = tuple(reversed(payload["tables"]))

    with pytest.raises(ValidationError, match="tables"):
        ExpectedPhase1ArtifactContract.model_validate(payload)


def test_expected_contract_rejects_reordered_reports() -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    payload = expected_contract_payload()
    payload["reports"] = tuple(reversed(payload["reports"]))

    with pytest.raises(ValidationError, match="reports"):
        ExpectedPhase1ArtifactContract.model_validate(payload)


@pytest.mark.parametrize("level", ["top-level", "logical-input", "table", "report"])
def test_expected_contract_is_deeply_immutable(level: str) -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    contract = ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())
    target, field = {
        "top-level": (contract, "artifact_set_id"),
        "logical-input": (contract.logical_inputs[0], "path"),
        "table": (contract.tables[0], "grain"),
        "report": (contract.reports[0], "report_id"),
    }[level]

    with pytest.raises(ValidationError):
        setattr(target, field, "forged")


@pytest.mark.parametrize(
    "case",
    [
        "input-size-bool",
        "input-size-string",
        "table-row-bool",
        "table-row-string",
        "evidence-bool",
        "evidence-string",
        "dataset-string",
        "logical-inputs-list",
        "tables-list",
        "reports-list",
        "sort-key-list",
        "unique-key-list",
    ],
)
def test_expected_models_reject_direct_python_coercion_and_wrong_containers(
    case: str,
) -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    payload = expected_contract_payload()
    if case == "input-size-bool":
        payload["logical_inputs"][0]["size_bytes"] = True
    elif case == "input-size-string":
        payload["logical_inputs"][0]["size_bytes"] = "1"
    elif case == "table-row-bool":
        payload["tables"][0]["row_count"] = True
    elif case == "table-row-string":
        payload["tables"][0]["row_count"] = "10"
    elif case == "evidence-bool":
        payload["exact_link_evidence_count"] = True
    elif case == "evidence-string":
        payload["exact_link_evidence_count"] = "371"
    elif case == "dataset-string":
        payload["dataset_version"] = "2026-07-11"
    elif case == "logical-inputs-list":
        payload["logical_inputs"] = list(payload["logical_inputs"])
    elif case == "tables-list":
        payload["tables"] = list(payload["tables"])
    elif case == "reports-list":
        payload["reports"] = list(payload["reports"])
    elif case == "sort-key-list":
        payload["tables"][0]["sort_key"] = ["id"]
    else:
        payload["tables"][0]["unique_key"] = ["id"]

    with pytest.raises(ValidationError):
        ExpectedPhase1ArtifactContract.model_validate(payload)


@pytest.mark.parametrize(
    "case",
    [
        "artifact-version",
        "artifact-set",
        "input-uppercase-hash",
        "input-malformed-hash",
        "input-negative-size",
        "input-bool-size",
        "table-uppercase-schema",
        "table-malformed-schema",
        "table-uppercase-logical",
        "table-malformed-logical",
        "table-negative-count",
        "table-bool-count",
        "table-wrong-grain",
        "table-wrong-known-count",
        "report-uppercase-hash",
        "report-malformed-hash",
        "overall-uppercase-hash",
        "overall-malformed-hash",
        "pair-uppercase-hash",
        "pair-malformed-hash",
        "pair-wrong-hash",
        "evidence-negative-count",
        "evidence-bool-count",
        "evidence-wrong-count",
    ],
)
def test_expected_contract_enforces_literals_hashes_counts_and_grains(case: str) -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    contract = ExpectedPhase1ArtifactContract.model_validate(
        expected_contract_payload(), strict=True
    )
    update: dict[str, object] = {}
    if case == "artifact-version":
        update["artifact_contract_version"] = "2.0.0"
    elif case == "artifact-set":
        update["artifact_set_id"] = "other/v1"
    elif case.startswith("input-"):
        field = "size_bytes" if case.endswith(("size", "count")) else "sha256"
        value: object
        if case == "input-uppercase-hash":
            value = "A" * 64
        elif case == "input-malformed-hash":
            value = "a" * 63
        elif case == "input-negative-size":
            value = -1
        else:
            value = True
        update["logical_inputs"] = (
            contract.logical_inputs[0].model_copy(update={field: value}),
            *contract.logical_inputs[1:],
        )
    elif case.startswith("table-"):
        if case == "table-uppercase-schema":
            field, value = "schema_hash", "A" * 64
        elif case == "table-malformed-schema":
            field, value = "schema_hash", "a" * 63
        elif case == "table-uppercase-logical":
            field, value = "logical_hash", "A" * 64
        elif case == "table-malformed-logical":
            field, value = "logical_hash", "a" * 63
        elif case == "table-negative-count":
            field, value = "row_count", -1
        elif case == "table-bool-count":
            field, value = "row_count", True
        elif case == "table-wrong-grain":
            field, value = "grain", "other"
        else:
            field, value = "row_count", contract.tables[0].row_count + 1
        update["tables"] = (
            contract.tables[0].model_copy(update={field: value}),
            *contract.tables[1:],
        )
    elif case.startswith("report-"):
        value = "A" * 64 if "uppercase" in case else "a" * 63
        update["reports"] = (
            contract.reports[0].model_copy(update={"semantic_hash": value}),
            contract.reports[1],
        )
    elif case.startswith("overall-"):
        update["overall_manifest_logical_hash"] = "A" * 64 if "uppercase" in case else "a" * 63
    elif case.startswith("pair-"):
        update["exact_link_pair_sha256"] = {
            "pair-uppercase-hash": "A" * 64,
            "pair-malformed-hash": "a" * 63,
            "pair-wrong-hash": "d" * 64,
        }[case]
    else:
        update["exact_link_evidence_count"] = {
            "evidence-negative-count": -1,
            "evidence-bool-count": True,
            "evidence-wrong-count": 370,
        }[case]
    forged = contract.model_copy(update=update)

    with pytest.raises(ValidationError):
        ExpectedPhase1ArtifactContract.model_validate(forged, strict=True)


def test_expected_comparator_accepts_equal_structural_contract() -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
        compare_expected_artifact_contract,
    )

    expected = ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())

    actual: ArtifactLogicalContractView = _SyntheticArtifactLogicalContract(expected)

    compare_expected_artifact_contract(actual, expected)


@pytest.mark.parametrize("inventory", ["logical-inputs", "tables", "reports"])
def test_expected_comparator_rejects_reordered_structural_inventory(
    inventory: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
        compare_expected_artifact_contract,
    )

    expected = ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())
    logical_inputs = expected.logical_inputs
    tables = expected.tables
    reports = expected.reports
    if inventory == "logical-inputs":
        logical_inputs = tuple(reversed(logical_inputs))
    elif inventory == "tables":
        tables = tuple(reversed(tables))
    else:
        reports = tuple(reversed(reports))
    actual = _SyntheticArtifactLogicalContract(
        expected,
        logical_inputs=logical_inputs,
        tables=tables,
        reports=reports,
    )

    with pytest.raises(ArtifactContractError):
        compare_expected_artifact_contract(actual, expected)


def test_expected_protocol_and_comparator_are_later_manifest_independent() -> None:
    from finproof.data.artifacts import expected_contract

    source = Path(expected_contract.__file__).read_text(encoding="utf-8")
    assert "manifest.py" not in source
    assert "VerifiedArtifactSet" not in source
    assert "ArtifactVerificationResult" not in source


@pytest.mark.parametrize(
    "difference",
    [
        "contract-version",
        "set-id",
        "input-size",
        "input-sha",
        "table-schema",
        "table-count",
        "table-logical",
        "report-semantic",
        "manifest-logical",
        "link-pair",
        "evidence-count",
    ],
)
def test_expected_comparator_rejects_every_deterministic_difference(
    difference: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.expected_contract import (
        ArtifactLogicalContractPayload,
        ExpectedPhase1ArtifactContract,
        compare_expected_artifact_contract,
    )

    expected = ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())
    payload = expected_contract_payload()
    if difference == "contract-version":
        payload["artifact_contract_version"] = "2.0.0"
    elif difference == "set-id":
        payload["artifact_set_id"] = "other/v1"
    elif difference == "input-size":
        payload["logical_inputs"][0]["size_bytes"] += 1
    elif difference == "input-sha":
        payload["logical_inputs"][0]["sha256"] = "e" * 64
    elif difference == "table-schema":
        payload["tables"][0]["schema_hash"] = "e" * 64
    elif difference == "table-count":
        payload["tables"][0]["row_count"] += 1
    elif difference == "table-logical":
        payload["tables"][0]["logical_hash"] = "e" * 64
    elif difference == "report-semantic":
        payload["reports"][0]["semantic_hash"] = "e" * 64
    elif difference == "manifest-logical":
        payload["overall_manifest_logical_hash"] = "e" * 64
    elif difference == "link-pair":
        payload["exact_link_pair_sha256"] = "e" * 64
    else:
        payload["exact_link_evidence_count"] += 1
    actual: ArtifactLogicalContractView
    if difference in {"contract-version", "set-id"}:
        actual = SimpleNamespace(
            artifact_contract_version=payload["artifact_contract_version"],
            artifact_set_id=payload["artifact_set_id"],
            dataset_version=expected.dataset_version,
            logical_inputs=expected.logical_inputs,
            tables=expected.tables,
            reports=expected.reports,
            overall_manifest_logical_hash=expected.overall_manifest_logical_hash,
            exact_link_pair_sha256=expected.exact_link_pair_sha256,
            exact_link_evidence_count=expected.exact_link_evidence_count,
        )
    else:
        actual = ArtifactLogicalContractPayload.model_validate(payload)

    with pytest.raises(ArtifactContractError) as caught:
        compare_expected_artifact_contract(actual, expected)
    assert caught.value.code is ArtifactErrorCode.REPRODUCIBILITY_MISMATCH


def test_expected_comparator_reports_every_nested_difference_without_writeback(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
        compare_expected_artifact_contract,
    )

    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(expected_contract_payload(json_compatible=True), separators=(",", ":")),
        encoding="utf-8",
    )
    expected = ExpectedPhase1ArtifactContract.load(expected_path)
    file_before = expected_path.read_bytes()
    logical_inputs = list(expected.logical_inputs)
    logical_inputs[0] = logical_inputs[0].model_copy(
        update={"size_bytes": logical_inputs[0].size_bytes + 1}
    )
    logical_inputs[1] = logical_inputs[1].model_copy(update={"sha256": "e" * 64})
    tables = list(expected.tables)
    tables[0] = tables[0].model_copy(update={"schema_hash": "e" * 64})
    tables[1] = tables[1].model_copy(update={"row_count": tables[1].row_count + 1})
    tables[2] = tables[2].model_copy(update={"logical_hash": "e" * 64})
    reports = list(expected.reports)
    reports[0] = reports[0].model_copy(update={"semantic_hash": "e" * 64})
    actual = SimpleNamespace(
        artifact_contract_version=expected.artifact_contract_version,
        artifact_set_id=expected.artifact_set_id,
        dataset_version=expected.dataset_version,
        logical_inputs=tuple(logical_inputs),
        tables=tuple(tables),
        reports=tuple(reports),
        overall_manifest_logical_hash="e" * 64,
        exact_link_pair_sha256="e" * 64,
        exact_link_evidence_count=370,
    )
    actual_before = deepcopy(actual.__dict__)
    expected_before = expected.model_dump(mode="python")

    with pytest.raises(ArtifactContractError) as caught:
        compare_expected_artifact_contract(actual, expected)

    assert caught.value.code is ArtifactErrorCode.REPRODUCIBILITY_MISMATCH
    paths = (
        "/exact_link_evidence_count",
        "/exact_link_pair_sha256",
        "/logical_inputs/0/size_bytes",
        "/logical_inputs/1/sha256",
        "/overall_manifest_logical_hash",
        "/reports/0/semantic_hash",
        "/tables/0/schema_hash",
        "/tables/1/row_count",
        "/tables/2/logical_hash",
    )
    assert caught.value.internal_context == {
        "reason": "contract_mismatch",
        "difference_paths": json.dumps(paths, ensure_ascii=False, separators=(",", ":")),
    }
    assert all(value not in str(caught.value.internal_context) for value in ("e" * 64, "370"))
    assert actual.__dict__ == actual_before
    assert expected.model_dump(mode="python") == expected_before
    assert expected_path.read_bytes() == file_before


def test_internal_difference_paths_escapes_tokens_and_root_pointer() -> None:
    from finproof.data.artifacts.expected_contract import _difference_paths

    actual = {"a/b": {"a~b": ("same", "actual")}}
    expected = {"a/b": {"a~b": ("same", "expected")}}
    actual_before = deepcopy(actual)
    expected_before = deepcopy(expected)

    assert _difference_paths(actual, expected) == ("/a~1b/a~0b/1",)
    assert _difference_paths("actual", "expected") == ("",)
    assert actual == actual_before
    assert expected == expected_before


def test_expected_comparator_rejects_missing_structural_property() -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
        compare_expected_artifact_contract,
    )

    expected = ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())
    actual = SimpleNamespace(
        **{key: value for key, value in expected.__dict__.items() if key != "tables"}
    )

    with pytest.raises(ArtifactContractError) as caught:
        compare_expected_artifact_contract(actual, expected)
    assert caught.value.code is ArtifactErrorCode.REPRODUCIBILITY_MISMATCH
    assert caught.value.internal_context["reason"] == "invalid_actual_contract"


@pytest.mark.parametrize(
    "case",
    [
        "input-size-bool",
        "table-row-bool",
        "evidence-bool",
        "dataset-string",
        "input-size-string",
        "table-row-string",
        "evidence-string",
        "logical-inputs-list",
        "tables-list",
        "reports-list",
        "input-entry-dict",
        "table-entry-dict",
        "report-entry-dict",
        "sort-key-list",
    ],
)
def test_expected_comparator_strictly_rejects_actual_types(case: str) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
        compare_expected_artifact_contract,
    )

    expected = ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())
    payload: dict[str, Any] = {
        "artifact_contract_version": expected.artifact_contract_version,
        "artifact_set_id": expected.artifact_set_id,
        "dataset_version": expected.dataset_version,
        "logical_inputs": expected.logical_inputs,
        "tables": expected.tables,
        "reports": expected.reports,
        "overall_manifest_logical_hash": expected.overall_manifest_logical_hash,
        "exact_link_pair_sha256": expected.exact_link_pair_sha256,
        "exact_link_evidence_count": expected.exact_link_evidence_count,
    }
    if case in {"input-size-bool", "input-size-string"}:
        input_entries = list(expected.logical_inputs)
        input_entries[0] = input_entries[0].model_copy(
            update={"size_bytes": True if case.endswith("bool") else "1"}
        )
        payload["logical_inputs"] = tuple(input_entries)
    elif case in {"table-row-bool", "table-row-string"}:
        table_entries = list(expected.tables)
        table_entries[0] = table_entries[0].model_copy(
            update={"row_count": True if case.endswith("bool") else "10"}
        )
        payload["tables"] = tuple(table_entries)
    elif case == "evidence-bool":
        payload["exact_link_evidence_count"] = True
    elif case == "dataset-string":
        payload["dataset_version"] = "2026-07-11"
    elif case == "evidence-string":
        payload["exact_link_evidence_count"] = "371"
    elif case == "logical-inputs-list":
        payload["logical_inputs"] = list(expected.logical_inputs)
    elif case == "tables-list":
        payload["tables"] = list(expected.tables)
    elif case == "reports-list":
        payload["reports"] = list(expected.reports)
    elif case == "input-entry-dict":
        payload["logical_inputs"] = (
            expected.logical_inputs[0].model_dump(),
            *expected.logical_inputs[1:],
        )
    elif case == "table-entry-dict":
        payload["tables"] = (expected.tables[0].model_dump(), *expected.tables[1:])
    elif case == "report-entry-dict":
        payload["reports"] = (expected.reports[0].model_dump(), *expected.reports[1:])
    elif case == "sort-key-list":
        sort_entries = list(expected.tables)
        sort_entries[0] = sort_entries[0].model_copy(update={"sort_key": ["id"]})
        payload["tables"] = tuple(sort_entries)
    else:
        raise AssertionError(case)

    with pytest.raises(ArtifactContractError) as caught:
        compare_expected_artifact_contract(
            SimpleNamespace(**payload),
            expected,
        )
    assert caught.value.code is ArtifactErrorCode.REPRODUCIBILITY_MISMATCH
    assert caught.value.internal_context["reason"] == "invalid_actual_contract"


def test_expected_contract_loader_accepts_canonical_json(tmp_path: Path) -> None:
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    contract_path = tmp_path / "expected.json"
    contract_path.write_text(
        json.dumps(expected_contract_payload(json_compatible=True)),
        encoding="utf-8",
    )

    loaded = ExpectedPhase1ArtifactContract.load(contract_path)

    assert loaded == ExpectedPhase1ArtifactContract.model_validate(expected_contract_payload())


@pytest.mark.parametrize("case", ["symlink-parent", "intermediate-parent-swap"])
def test_expected_contract_loader_rejects_parent_alias_and_race(
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.expected_contract import (
        ExpectedPhase1ArtifactContract,
    )

    canonical_json = json.dumps(expected_contract_payload(json_compatible=True))
    trusted_parent = tmp_path / "trusted"
    trusted_parent.mkdir()
    contract_path = trusted_parent / "expected.json"
    contract_path.write_text(canonical_json, encoding="utf-8")

    if case == "symlink-parent":
        linked_parent = tmp_path / "linked"
        linked_parent.symlink_to(trusted_parent, target_is_directory=True)
        contract_path = linked_parent / "expected.json"
    else:
        external_parent = tmp_path / "external"
        external_parent.mkdir()
        (external_parent / "expected.json").write_text(canonical_json, encoding="utf-8")
        moved_parent = tmp_path / "trusted-original"
        swapped = False
        real_builtin_open = builtins.open
        real_os_open = os.open

        def swap_parent_once() -> None:
            nonlocal swapped
            if swapped:
                return
            swapped = True
            trusted_parent.rename(moved_parent)
            trusted_parent.symlink_to(external_parent, target_is_directory=True)

        def racing_builtin_open(file: object, *args: object, **kwargs: object) -> object:
            if isinstance(file, (str, os.PathLike)) and Path(file).name == "expected.json":
                swap_parent_once()
            return real_builtin_open(file, *args, **kwargs)  # type: ignore[call-overload]

        def racing_os_open(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if Path(os.fsdecode(path)).name == "expected.json":
                swap_parent_once()
            return real_os_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(builtins, "open", racing_builtin_open)
        monkeypatch.setattr(os, "open", racing_os_open)

    with pytest.raises(ArtifactContractError) as caught:
        ExpectedPhase1ArtifactContract.load(contract_path)
    assert caught.value.code is ArtifactErrorCode.UNSAFE_TARGET


def test_resolve_logical_inputs_returns_exact_closed_nine(tmp_path: Path) -> None:
    from finproof.data.artifacts.config import resolve_logical_inputs

    settings = _synthetic_build_settings(tmp_path / "repository")
    resolved = resolve_logical_inputs(settings)  # type: ignore[arg-type]

    assert [(item.namespace, item.path, item.kind) for item in resolved] == [
        ("source_root", "input_manifest.json", "source_manifest"),
        ("source_root", "schema_catalog.json", "source_schema_catalog"),
        ("repository", "config/artifact_build.yaml", "artifact_build_config"),
        ("repository", "config/datasets.yaml", "dataset_registry"),
        ("repository", "config/quality_rules.yaml", "quality_rule_registry"),
        ("repository", "config/rating_scale.yaml", "rating_scale_registry"),
        ("repository", "config/state_rules.yaml", "state_rule_registry"),
        (
            "repository",
            "schemas/artifact_manifest.schema.json",
            "artifact_manifest_schema",
        ),
        ("repository", "schemas/quality_issue.schema.json", "quality_issue_schema"),
    ]
    assert all(item.absolute_path.is_absolute() for item in resolved)


@pytest.mark.parametrize(
    "case",
    [
        "tenth",
        "missing",
        "duplicate",
        "repeated-namespace-directory",
        "absolute",
        "empty",
        "empty-component",
        "dot",
        "dot-dot",
        "backslash",
        "nul",
        "percent-alias",
        "out-of-namespace",
        "symlink-component",
        "kind-mismatch",
        "cwd-dependent-spelling",
    ],
)
def test_resolve_logical_inputs_rejects_every_invalid_declaration(
    case: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import config as artifact_config
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    repository_root = tmp_path / "repository"
    settings = _synthetic_build_settings(repository_root)
    declarations = list(artifact_config._LOGICAL_INPUT_DECLARATIONS)
    namespace, relative_path, kind = declarations[2]
    if case == "tenth":
        declarations.append((namespace, "config/tenth.yaml", kind))
    elif case == "missing":
        declarations.pop()
    elif case == "duplicate":
        declarations.append(declarations[0])
    elif case == "repeated-namespace-directory":
        declarations[2] = (namespace, "repository/config/artifact_build.yaml", kind)
    elif case == "absolute":
        declarations[2] = (namespace, "/private/forged.yaml", kind)
    elif case == "empty":
        declarations[2] = (namespace, "", kind)
    elif case == "empty-component":
        declarations[2] = (namespace, "config//artifact_build.yaml", kind)
    elif case == "dot":
        declarations[2] = (namespace, "config/./artifact_build.yaml", kind)
    elif case == "dot-dot":
        declarations[2] = (namespace, "config/../artifact_build.yaml", kind)
    elif case == "backslash":
        declarations[2] = (namespace, "config\\artifact_build.yaml", kind)
    elif case == "nul":
        declarations[2] = (namespace, "config/artifact\x00build.yaml", kind)
    elif case == "percent-alias":
        declarations[2] = (namespace, "config/%61rtifact_build.yaml", kind)
    elif case == "out-of-namespace":
        declarations[2] = (namespace, "source_material/input_manifest.json", kind)
    elif case == "symlink-component":
        real = repository_root / "real-config"
        real.mkdir()
        (repository_root / "linked-config").symlink_to(real, target_is_directory=True)
        declarations[2] = (namespace, "linked-config/artifact_build.yaml", kind)
    elif case == "kind-mismatch":
        declarations[2] = (
            namespace,
            relative_path,
            artifact_config.ArtifactInputKind.DATASET_REGISTRY,
        )
    else:
        declarations[2] = (namespace, "./config/artifact_build.yaml", kind)
    monkeypatch.setattr(
        artifact_config,
        "_LOGICAL_INPUT_DECLARATIONS",
        tuple(declarations),
    )

    with pytest.raises(ArtifactContractError) as caught:
        artifact_config.resolve_logical_inputs(settings)  # type: ignore[arg-type]
    assert caught.value.code is ArtifactErrorCode.CONFIG_INVALID


def test_resolved_artifact_input_cannot_be_directly_forged() -> None:
    from finproof.data.artifacts.config import (
        ArtifactInputKind,
        ArtifactInputNamespace,
        ResolvedArtifactInput,
    )

    with pytest.raises((TypeError, ValueError)):
        ResolvedArtifactInput(  # type: ignore[call-arg]
            namespace=ArtifactInputNamespace.REPOSITORY,
            path="config/artifact_build.yaml",
            kind=ArtifactInputKind.ARTIFACT_BUILD_CONFIG,
            absolute_path=Path("/private/forged/artifact_build.yaml"),
        )


def test_build_registry_versions_accept_exact_headers(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import validate_build_registry_versions

    settings = _synthetic_build_settings(tmp_path / "repository")

    validate_build_registry_versions(settings, VersionBundle())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "case",
    [
        "datasets-version",
        "quality-version",
        "rating-version",
        "state-version",
        "snapshot",
        "bundle-dataset",
        "bundle-quality",
        "bundle-rating",
        "bundle-state",
        "duplicate-datasets-version",
    ],
)
def test_build_registry_versions_reject_every_mismatch(
    case: str,
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import validate_build_registry_versions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    repository_root = tmp_path / "repository"
    settings = _synthetic_build_settings(repository_root)
    config_dir = repository_root / "config"
    config_file = {
        "datasets-version": "datasets.yaml",
        "quality-version": "quality_rules.yaml",
        "rating-version": "rating_scale.yaml",
        "state-version": "state_rules.yaml",
    }.get(case)
    if config_file is not None:
        path = config_dir / config_file
        path.write_text(
            path.read_text(encoding="utf-8").replace("1.0.0", "9.9.9", 1),
            encoding="utf-8",
        )
    elif case == "snapshot":
        path = config_dir / "datasets.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace("2026-07-11", "2026-07-10"),
            encoding="utf-8",
        )
    elif case == "duplicate-datasets-version":
        path = config_dir / "datasets.yaml"
        path.write_text(
            path.read_text(encoding="utf-8") + "version: 1.0.0\n",
            encoding="utf-8",
        )

    version_overrides: dict[str, object] = {}
    if case == "bundle-dataset":
        version_overrides["dataset_version"] = date(2026, 7, 10)
    elif case.startswith("bundle-"):
        version_overrides[f"{case.removeprefix('bundle-')}_rule_version"] = "9.9.9"

    with pytest.raises(ArtifactContractError) as caught:
        validate_build_registry_versions(
            settings,  # type: ignore[arg-type]
            VersionBundle(**version_overrides),  # type: ignore[arg-type]
        )
    assert caught.value.code is ArtifactErrorCode.CONFIG_INVALID
