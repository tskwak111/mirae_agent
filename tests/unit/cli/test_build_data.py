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
