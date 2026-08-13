import re
from pathlib import Path

import pytest
import yaml

from finproof.core.settings import ExecutionMode, Settings

ROOT = Path(__file__).resolve().parents[2]


def test_environment_example_loads_without_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    (tmp_path / ".env").write_text(example, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.execution_mode is ExecutionMode.EVALUATION
    assert settings.dataset_snapshot_date.isoformat() == "2026-07-11"
    assert "SECRET" not in example
    assert "API_KEY" not in example


def test_pre_commit_configuration_pins_ruff() -> None:
    configuration = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))

    ruff_repository = next(
        repository
        for repository in configuration["repos"]
        if repository["repo"] == "https://github.com/astral-sh/ruff-pre-commit"
    )
    assert ruff_repository["rev"] == "v0.15.22"


def test_ci_runs_the_required_frozen_checks() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    assert workflow["permissions"]["contents"] == "read"
    assert workflow["jobs"]["quality"]["runs-on"] == "ubuntu-latest"

    steps = workflow["jobs"]["quality"]["steps"]
    action_references = [step["uses"] for step in steps if "uses" in step]
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference) for reference in action_references)
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "uv sync --frozen --all-groups" in commands
    assert "uv run ruff format --check ." in commands
    assert "uv run ruff check ." in commands
    assert "uv run mypy src tests tools" in commands
    assert "uv run pytest -q" in commands
    assert "tools/audit_source_data.py --check" in commands
    assert "tools/verify_handoff.py" in commands
    assert "tools/extract_schema_catalog.py --check" in commands
