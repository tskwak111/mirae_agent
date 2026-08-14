"""Task 5 build-path settings contracts."""

import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from finproof.core.settings import Settings


def _valid_build_paths(root: Path) -> dict[str, Any]:
    source_root = root / "source_material"
    artifact_dir = root / "artifacts"
    return {
        "repository_root": root,
        "source_root": source_root,
        "data_dir": source_root / "data",
        "artifact_dir": artifact_dir,
        "database_path": artifact_dir / "finproof.duckdb",
        "artifact_build_config_path": root / "config/artifact_build.yaml",
        "expected_artifact_contract_path": root / "config/expected_phase1_artifacts.json",
    }


_PATH_CASES = [
    "valid-defaults-and-two-cwds",
    "nonexistent-repository-root",
    "repository-root-file",
    "source-root-file",
    "config-ancestor-file",
    "artifact-equals-repository",
    "artifact-equals-filesystem-root",
    "artifact-equals-home",
    "artifact-inside-source",
    "repository-root-symlink",
    "source-root-symlink",
    "data-dir-symlink",
    "artifact-dir-symlink",
    "database-path-symlink",
    "artifact-config-symlink",
    "expected-contract-symlink",
    "database-outside-artifact",
    "database-wrong-basename",
    "wrong-data-dir",
    "source-outside-repository",
    "artifact-config-outside-config",
    "expected-contract-outside-config",
    "source-equals-artifact",
    "source-equals-database",
    "artifact-equals-database",
]


@pytest.mark.parametrize("case", _PATH_CASES)
def test_build_settings_authoritative_path_family(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    paths = _valid_build_paths(root)

    if case == "valid-defaults-and-two-cwds":
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        monkeypatch.chdir(first)
        relative = Settings(repository_root=Path(os.path.relpath(root, first)))
        monkeypatch.chdir(second)
        absolute = Settings(repository_root=root)
        fields = (
            "repository_root",
            "source_root",
            "data_dir",
            "artifact_dir",
            "database_path",
            "artifact_build_config_path",
            "expected_artifact_contract_path",
        )
        observed = {field: getattr(relative, field) for field in fields}
        assert observed == {field: getattr(absolute, field) for field in fields}
        assert observed == {
            "repository_root": root,
            "source_root": root / "source_material",
            "data_dir": root / "source_material/data",
            "artifact_dir": root / "artifacts",
            "database_path": root / "artifacts/finproof.duckdb",
            "artifact_build_config_path": root / "config/artifact_build.yaml",
            "expected_artifact_contract_path": root / "config/expected_phase1_artifacts.json",
        }
        return
    if case == "nonexistent-repository-root":
        paths["repository_root"] = tmp_path / "missing-repository"
    elif case == "repository-root-file":
        repository_file = tmp_path / "repository-file"
        repository_file.touch()
        paths["repository_root"] = repository_file
    elif case == "source-root-file":
        source_file = root / "source-file"
        source_file.touch()
        paths["source_root"] = source_file
        paths["data_dir"] = source_file / "data"
    elif case == "config-ancestor-file":
        (root / "config").touch()
    elif case == "artifact-equals-repository":
        paths["artifact_dir"] = root
        paths["database_path"] = root / "finproof.duckdb"
    elif case == "artifact-equals-filesystem-root":
        filesystem_root = Path(root.anchor)
        paths["artifact_dir"] = filesystem_root
        paths["database_path"] = filesystem_root / "finproof.duckdb"
    elif case == "artifact-equals-home":
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        paths["artifact_dir"] = fake_home
        paths["database_path"] = fake_home / "finproof.duckdb"
    elif case == "artifact-inside-source":
        paths["artifact_dir"] = paths["source_root"] / "artifacts"
        paths["database_path"] = paths["artifact_dir"] / "finproof.duckdb"
    elif case.endswith("-symlink"):
        real = tmp_path / f"real-{case}"
        if case == "database-path-symlink":
            real.touch()
        else:
            real.mkdir()
        link = tmp_path / f"link-{case}"
        link.symlink_to(real, target_is_directory=case != "database-path-symlink")
        field = {
            "repository-root-symlink": "repository_root",
            "source-root-symlink": "source_root",
            "data-dir-symlink": "data_dir",
            "artifact-dir-symlink": "artifact_dir",
            "database-path-symlink": "database_path",
            "artifact-config-symlink": "artifact_build_config_path",
            "expected-contract-symlink": "expected_artifact_contract_path",
        }[case]
        paths[field] = link
        if field == "artifact_dir":
            paths["database_path"] = link / "finproof.duckdb"
    elif case == "database-outside-artifact":
        paths["database_path"] = root / "other/finproof.duckdb"
    elif case == "database-wrong-basename":
        paths["database_path"] = paths["artifact_dir"] / "other.duckdb"
    elif case == "wrong-data-dir":
        paths["data_dir"] = paths["source_root"] / "other"
    elif case == "source-outside-repository":
        paths["source_root"] = tmp_path / "outside-source"
        paths["data_dir"] = paths["source_root"] / "data"
    elif case == "artifact-config-outside-config":
        paths["artifact_build_config_path"] = root / "other/artifact_build.yaml"
    elif case == "expected-contract-outside-config":
        paths["expected_artifact_contract_path"] = root / "other/expected.json"
    elif case == "source-equals-artifact":
        paths["artifact_dir"] = paths["source_root"]
        paths["database_path"] = paths["artifact_dir"] / "finproof.duckdb"
    elif case == "source-equals-database":
        paths["database_path"] = paths["source_root"]
    elif case == "artifact-equals-database":
        paths["database_path"] = paths["artifact_dir"]
    else:
        raise AssertionError(case)

    with pytest.raises(ValidationError):
        Settings(**paths)


def test_conflicting_dotenv_files_never_change_any_build_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    fields = (
        "repository_root",
        "source_root",
        "data_dir",
        "artifact_dir",
        "database_path",
        "artifact_build_config_path",
        "expected_artifact_contract_path",
    )
    observed: list[dict[str, str]] = []
    for index, name in enumerate(("first", "second"), start=1):
        cwd = tmp_path / name
        cwd.mkdir()
        (cwd / ".env").write_text(
            "\n".join(
                [
                    f"FINPROOF_REPOSITORY_ROOT={tmp_path / f'ambient-repo-{index}'}",
                    f"FINPROOF_SOURCE_ROOT=source-{index}",
                    f"FINPROOF_DATA_DIR=source-{index}/data",
                    f"FINPROOF_ARTIFACT_DIR=artifacts-{index}",
                    f"FINPROOF_DATABASE_PATH=artifacts-{index}/finproof.duckdb",
                    f"FINPROOF_ARTIFACT_BUILD_CONFIG_PATH=config/build-{index}.yaml",
                    f"FINPROOF_EXPECTED_ARTIFACT_CONTRACT_PATH=config/expected-{index}.json",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(cwd)
        settings = Settings(repository_root=repository)
        observed.append({field: str(getattr(settings, field)) for field in fields})

    assert observed[0] == observed[1]
    assert all("ambient" not in value for item in observed for value in item.values())
    assert all("source-" not in value for item in observed for value in item.values())
    assert all("artifacts-" not in value for item in observed for value in item.values())


def test_explicit_initializer_precedes_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FINPROOF_ARTIFACT_DIR", "ambient-artifacts")
    explicit = tmp_path / "explicit-artifacts"
    settings = Settings(
        repository_root=tmp_path,
        artifact_dir=explicit,
        database_path=explicit / "finproof.duckdb",
    )
    assert settings.artifact_dir == explicit


def test_process_environment_overrides_build_path_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FINPROOF_REPOSITORY_ROOT", str(tmp_path))
    monkeypatch.setenv("FINPROOF_ARTIFACT_DIR", "environment-artifacts")
    monkeypatch.setenv("FINPROOF_DATABASE_PATH", "environment-artifacts/finproof.duckdb")
    settings = Settings()
    assert settings.artifact_dir == tmp_path / "environment-artifacts"


def test_env_example_only_applies_after_explicit_process_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env.example").write_text("FINPROOF_MAX_TOP_K=77\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert Settings(repository_root=tmp_path).max_top_k == 50

    monkeypatch.setenv("FINPROOF_MAX_TOP_K", "77")
    assert Settings(repository_root=tmp_path).max_top_k == 77


def test_build_settings_are_frozen(tmp_path: Path) -> None:
    settings = Settings(repository_root=tmp_path)
    with pytest.raises(ValidationError):
        settings.artifact_dir = tmp_path / "mutated"
