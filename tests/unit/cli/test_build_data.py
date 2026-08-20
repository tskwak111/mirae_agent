"""CP7C safe build-data command contract."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from finproof.core.settings import Settings
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.manifest import ArtifactManifest


def test_parser_accepts_only_build_data_and_optional_clean() -> None:
    from finproof.cli.main import _parser

    assert vars(_parser().parse_args(["build-data"])) == {
        "command": "build-data",
        "clean": False,
    }
    assert vars(_parser().parse_args(["build-data", "--clean"])) == {
        "command": "build-data",
        "clean": True,
    }


@pytest.mark.parametrize(
    "argument",
    [
        "--timestamp",
        "--source",
        "--output",
        "--sql",
        "--table",
        "--version",
        "--expected-path",
    ],
)
def test_build_data_rejects_every_unapproved_argument(argument: str) -> None:
    from finproof.cli.main import _parser

    with pytest.raises(SystemExit) as raised:
        _parser().parse_args(["build-data", argument, "untrusted"])
    assert raised.value.code == 2


def test_build_data_captures_one_utc_timestamp_and_passes_exact_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.cli.main import _run_main
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from tests.helpers.artifacts import artifact_staging_settings

    configured = artifact_staging_settings(tmp_path / "repository")
    monkeypatch.setenv("FINPROOF_REPOSITORY_ROOT", str(configured.repository_root))
    captured: list[tuple[Settings, VersionBundle, ArtifactBuildOptions]] = []
    clock_calls = 0
    instant = datetime(2026, 8, 15, 4, 5, 6, 789, tzinfo=UTC)

    def clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return instant

    def refusing_builder(
        settings: Settings,
        versions: VersionBundle,
        *,
        options: ArtifactBuildOptions,
    ) -> ArtifactManifest:
        captured.append((settings, versions, options))
        raise ArtifactContractError(
            ArtifactErrorCode.BASELINE_MISSING,
            operation_id="build-artifacts",
            target_basename="artifacts",
        )

    assert _run_main(["build-data", "--clean"], builder=refusing_builder, clock=clock) == 2
    assert clock_calls == 1
    assert len(captured) == 1
    settings, _, options = captured[0]
    assert settings == configured
    assert options == ArtifactBuildOptions(clean=True, persistence_timestamp=instant)


def test_build_data_missing_baseline_is_one_bounded_error_line_without_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from finproof.cli.main import _load_repository_tool, _run_main
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from tests.helpers.artifacts import artifact_staging_settings

    configured = artifact_staging_settings(tmp_path / "repository")
    monkeypatch.setenv("FINPROOF_REPOSITORY_ROOT", str(configured.repository_root))
    calls = 0

    def refusing_builder(
        settings: Settings,
        versions: VersionBundle,
        *,
        options: ArtifactBuildOptions,
    ) -> ArtifactManifest:
        nonlocal calls
        del settings, versions, options
        calls += 1
        raise ArtifactContractError(
            ArtifactErrorCode.BASELINE_MISSING,
            operation_id="build-artifacts",
            target_basename="artifacts",
            internal_context={
                "source_path": "/secret/source.xlsx",
                "stage_path": "/secret/.artifacts.finproof-stage-private",
            },
        )

    def forbidden_checkout_discovery(_name: str) -> object:
        raise AssertionError("build-data used repository tool discovery")

    monkeypatch.setattr("finproof.cli.main._load_repository_tool", forbidden_checkout_discovery)
    assert (
        _run_main(
            ["build-data"],
            builder=refusing_builder,
            clock=lambda: datetime(2026, 8, 15, tzinfo=UTC),
        )
        == 2
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "error: artifact error baseline_missing for artifacts (build-artifacts)\n"
    assert calls == 1
    assert "/secret" not in output.err
    assert "Traceback" not in output.err
    assert _load_repository_tool is not forbidden_checkout_discovery


def test_build_data_success_emits_only_compact_verified_manifest_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from finproof.cli.main import _run_main
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.manifest import ArtifactManifest
    from tests.helpers.artifacts import (
        artifact_staging_settings,
        manifest_payload,
    )

    configured = artifact_staging_settings(tmp_path / "repository")
    monkeypatch.setenv("FINPROOF_REPOSITORY_ROOT", str(configured.repository_root))
    manifest = ArtifactManifest.model_validate(manifest_payload(), strict=True)

    def successful_builder(
        settings: Settings,
        versions: VersionBundle,
        *,
        options: ArtifactBuildOptions,
    ) -> ArtifactManifest:
        assert settings == configured
        assert type(versions) is VersionBundle
        assert options.persistence_timestamp == datetime(2026, 8, 15, tzinfo=UTC)
        return manifest

    assert (
        _run_main(
            ["build-data"],
            builder=successful_builder,
            clock=lambda: datetime(2026, 8, 15, tzinfo=UTC),
        )
        == 0
    )
    output = capsys.readouterr()
    assert output.out == (
        '{"database_path":"finproof.duckdb","logical_hash":"'
        f'{manifest.logical_hash}","manifest_path":"manifest.json",'
        '"target_basename":"artifacts"}\n'
    )
    assert output.err == ""


def test_build_data_postcommit_cleanup_error_states_published_verified_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from finproof.cli.main import _run_main
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from tests.helpers.artifacts import artifact_staging_settings

    configured = artifact_staging_settings(tmp_path / "repository")
    monkeypatch.setenv("FINPROOF_REPOSITORY_ROOT", str(configured.repository_root))

    def cleanup_failed_builder(
        settings: Settings,
        versions: VersionBundle,
        *,
        options: ArtifactBuildOptions,
    ) -> ArtifactManifest:
        del settings, versions, options
        raise ArtifactContractError(
            ArtifactErrorCode.BACKUP_CLEANUP_FAILED_AFTER_PUBLISH,
            operation_id="publish-artifacts",
            target_basename="artifacts",
            published=True,
            internal_context={"backup_path": "/secret/backup"},
        )

    assert (
        _run_main(
            ["build-data", "--clean"],
            builder=cleanup_failed_builder,
            clock=lambda: datetime(2026, 8, 15, tzinfo=UTC),
        )
        == 2
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == (
        "error: artifact error backup_cleanup_failed_after_publish for artifacts "
        "(publish-artifacts); published verified target retained\n"
    )
    assert "/secret" not in output.err
