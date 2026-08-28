"""CP7C guarded candidate and evaluation builder boundaries."""

from __future__ import annotations

import io
import pickle
from copy import copy, deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from finproof.core.settings import Settings
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.builder import _LiveArtifactBuildCandidate
    from finproof.data.artifacts.config import ArtifactBuildOptions


class _FlipProbe:
    def __init__(self) -> None:
        self.second_checks = 0

    def source_exists(self) -> bool:
        return False

    def resource_exists(self) -> bool:
        return False

    def second_check(self) -> None:
        from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

        self.second_checks += 1
        raise ArtifactContractError(
            ArtifactErrorCode.BASELINE_ALREADY_EXISTS,
            operation_id="build-candidate-artifacts",
        )


class _AbsentProbe:
    def __init__(self) -> None:
        self.second_checks = 0

    def source_exists(self) -> bool:
        return False

    def resource_exists(self) -> bool:
        return False

    def second_check(self) -> None:
        self.second_checks += 1


class _PresentProbe(_AbsentProbe):
    def __init__(self, source: bool, resource: bool) -> None:
        super().__init__()
        self._source = source
        self._resource = resource

    def source_exists(self) -> bool:
        return self._source

    def resource_exists(self) -> bool:
        return self._resource


def _install_small_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Settings, VersionBundle]:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    loaded = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    payload = loaded.model_dump(mode="python")
    payload["sources"] = tuple(
        {**source, "rows": 1, "cells": source["columns"]} for source in payload["sources"]
    )
    payload["silver_counts"] = {
        "bond_sale_lot": 1,
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
    }
    payload["quarantine_source_rows"] = 0
    payload["exact_link_candidate_limit"] = 217
    config = ArtifactBuildConfig.model_validate(payload, strict=True)

    def small_config(
        _cls: object,
        _stream: object,
        *,
        versions: VersionBundle,
    ) -> ArtifactBuildConfig:
        assert versions is not None
        return config

    monkeypatch.setattr(
        ArtifactBuildConfig,
        "from_held_stream",
        classmethod(small_config),
    )
    return settings, versions


def test_private_transform_returns_one_provenance_bound_live_candidate_carrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts.builder import (
        _build_private_live_candidate,
        _LiveArtifactBuildCandidate,
    )
    from finproof.data.artifacts.config import ArtifactBuildOptions

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)
    with pytest.raises(TypeError, match="builder-issued"):
        _LiveArtifactBuildCandidate()
    carrier = _build_private_live_candidate(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, 1, 2, 3, tzinfo=UTC)),
    )
    issuance = object.__getattribute__(carrier, "_issuance")
    try:
        assert type(carrier) is _LiveArtifactBuildCandidate
        assert issuance.value is carrier
        issuance.candidate._require_issued()
        assert not any(
            hasattr(carrier, name)
            for name in ("candidate", "observations", "manifest", "custody", "path")
        )
        for operation in (copy, deepcopy, pickle.dumps):
            with pytest.raises(TypeError, match="cannot be copied"):
                operation(carrier)
    finally:
        issuance.candidate._custody.discard_if_exact()
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))


def test_candidate_tool_discards_live_carrier_before_core_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.build_candidate_artifacts import _build_candidate_artifacts_with_probe

    from finproof.data.artifacts.builder import (
        ArtifactBuildTelemetry,
        _build_private_live_candidate,
        _discard_live_candidate_to_core_outcome,
    )
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.manifest import ArtifactCoreVerificationResult

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)

    class LiveProbe(_AbsentProbe):
        def second_check(self) -> None:
            assert tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))
            super().second_check()

    carrier: _LiveArtifactBuildCandidate | None = None

    def transform(
        settings: Settings,
        versions: VersionBundle,
        options: ArtifactBuildOptions,
    ) -> _LiveArtifactBuildCandidate:
        nonlocal carrier
        carrier = _build_private_live_candidate(settings, versions, options)
        return carrier

    stdout = io.StringIO()
    stderr = io.StringIO()
    probe = LiveProbe()
    returned = _build_candidate_artifacts_with_probe(
        settings,
        versions,
        options=ArtifactBuildOptions(
            persistence_timestamp=datetime(2026, 8, 15, 9, 8, 7, tzinfo=UTC)
        ),
        probe=probe,
        transform=transform,
        stdout=stdout,
        stderr=stderr,
    )
    assert probe.second_checks == 1
    assert returned == ArtifactCoreVerificationResult.model_validate_json(
        stdout.getvalue(), strict=True
    )
    assert ArtifactBuildTelemetry.model_validate_json(stderr.getvalue(), strict=True)
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))
    assert carrier is not None
    with pytest.raises(ValueError, match="already consumed"):
        _discard_live_candidate_to_core_outcome(carrier)


def test_real_candidate_default_permanently_refuses_after_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import build_candidate_artifacts as candidate_tool

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from tests.helpers.artifacts import artifact_staging_settings

    settings = artifact_staging_settings(tmp_path / "repository")
    calls = 0

    def forbidden_transform(*args: object, **kwargs: object) -> None:
        nonlocal calls
        del args, kwargs
        calls += 1

    monkeypatch.setattr(candidate_tool, "_build_private_live_candidate", forbidden_transform)
    with pytest.raises(ArtifactContractError) as raised:
        candidate_tool.build_candidate_artifacts(
            settings,
            VersionBundle(),
            options=ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        )
    assert raised.value.code is ArtifactErrorCode.BASELINE_ALREADY_EXISTS
    assert calls == 0
    assert not settings.artifact_dir.exists()


def test_evaluation_build_with_expected_resource_reaches_private_transform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import builder
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from tests.helpers.artifacts import artifact_staging_settings

    settings = artifact_staging_settings(tmp_path / "repository")
    calls = 0

    def observed_transform(*args: object, **kwargs: object) -> None:
        nonlocal calls
        del args, kwargs
        calls += 1
        raise RuntimeError("observed expected-route transform")

    monkeypatch.setattr(builder, "_build_private_live_candidate", observed_transform)
    with pytest.raises(RuntimeError, match="observed expected-route transform"):
        builder.build_artifacts(
            settings,
            VersionBundle(),
            options=ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        )
    assert calls == 1
    assert not settings.artifact_dir.exists()


@pytest.mark.parametrize(
    ("source", "resource"),
    [(True, False), (False, True), (True, True)],
)
def test_candidate_existing_baseline_states_block_before_transform_or_output(
    tmp_path: Path,
    source: bool,
    resource: bool,
) -> None:
    from tools.build_candidate_artifacts import _build_candidate_artifacts_with_probe

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from tests.helpers.artifacts import artifact_staging_settings

    settings = artifact_staging_settings(tmp_path / "repository")
    stdout = io.StringIO()
    stderr = io.StringIO()
    calls = 0

    def forbidden_transform(
        settings: Settings,
        versions: VersionBundle,
        options: ArtifactBuildOptions,
    ) -> _LiveArtifactBuildCandidate:
        nonlocal calls
        del settings, versions, options
        calls += 1
        raise AssertionError("candidate transform ran after baseline existed")

    with pytest.raises(ArtifactContractError) as raised:
        _build_candidate_artifacts_with_probe(
            settings,
            VersionBundle(),
            options=ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            probe=_PresentProbe(source, resource),
            transform=forbidden_transform,
            stdout=stdout,
            stderr=stderr,
        )
    assert raised.value.code is ArtifactErrorCode.BASELINE_ALREADY_EXISTS
    assert calls == 0
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""


def test_candidate_second_check_race_emits_nothing_after_exact_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.build_candidate_artifacts import _build_candidate_artifacts_with_probe

    from finproof.data.artifacts import builder
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)
    transform_calls = 0
    production_transform = builder._build_private_live_candidate

    def instrumented_transform(
        settings: Settings,
        versions: VersionBundle,
        options: ArtifactBuildOptions,
    ) -> _LiveArtifactBuildCandidate:
        nonlocal transform_calls
        transform_calls += 1
        return production_transform(settings, versions, options)

    stdout = io.StringIO()
    stderr = io.StringIO()
    probe = _FlipProbe()
    with pytest.raises(ArtifactContractError) as raised:
        _build_candidate_artifacts_with_probe(
            settings,
            versions,
            options=ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            probe=probe,
            transform=instrumented_transform,
            stdout=stdout,
            stderr=stderr,
        )
    assert raised.value.code is ArtifactErrorCode.BASELINE_ALREADY_EXISTS
    assert transform_calls == 1
    assert probe.second_checks == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""
    assert not settings.artifact_dir.exists()
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))


def test_candidate_outputs_contract_then_path_free_telemetry_only_after_second_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.build_candidate_artifacts import _build_candidate_artifacts_with_probe

    from finproof.data.artifacts import builder
    from finproof.data.artifacts.builder import ArtifactBuildTelemetry
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.manifest import ArtifactCoreVerificationResult

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)
    stdout = io.StringIO()
    stderr = io.StringIO()
    probe = _AbsentProbe()
    returned = _build_candidate_artifacts_with_probe(
        settings,
        versions,
        options=ArtifactBuildOptions(
            persistence_timestamp=datetime(2026, 8, 15, 9, 8, 7, tzinfo=UTC)
        ),
        probe=probe,
        transform=builder._build_private_live_candidate,
        stdout=stdout,
        stderr=stderr,
    )
    assert probe.second_checks == 1
    assert returned == ArtifactCoreVerificationResult.model_validate_json(
        stdout.getvalue(), strict=True
    )
    telemetry = ArtifactBuildTelemetry.model_validate_json(stderr.getvalue(), strict=True)
    assert telemetry.persistence_timestamp == datetime(2026, 8, 15, 9, 8, 7, tzinfo=UTC)
    assert len(stdout.getvalue().splitlines()) == 1
    assert len(stderr.getvalue().splitlines()) == 1
    assert "tmp" not in stderr.getvalue()
    assert "stage" not in stderr.getvalue()
    assert "spill" not in stderr.getvalue()
    assert not settings.artifact_dir.exists()


def test_repository_candidate_parser_accepts_only_required_utc_timestamp() -> None:
    from tools.build_candidate_artifacts import _parser

    parsed = _parser().parse_args(["--persistence-timestamp", "2026-08-14T00:00:00.000001Z"])
    assert vars(parsed) == {"persistence_timestamp": "2026-08-14T00:00:00.000001Z"}
    for forbidden in ("--output", "--publish", "--accept", "--update", "--expected-path"):
        with pytest.raises(SystemExit) as raised:
            _parser().parse_args(
                [
                    "--persistence-timestamp",
                    "2026-08-14T00:00:00.000001Z",
                    forbidden,
                    "value",
                ]
            )
        assert raised.value.code == 2
