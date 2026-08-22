"""Static container and CI security inventory contract."""

import json
from pathlib import Path

import yaml


def test_container_contract_is_non_root_frozen_and_has_no_secret_or_artifact_copy() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.13-slim-bookworm\n")
    assert "uv==0.12.3" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    assert "USER finproof" in dockerfile
    assert "COPY artifacts" not in dockerfile
    assert "COPY source_material" not in dockerfile
    assert "CLOVA" not in dockerfile
    assert "--factory" in dockerfile
    command = next(
        line.removeprefix("CMD ") for line in dockerfile.splitlines() if line.startswith("CMD ")
    )
    assert json.loads(command) == [
        "uvicorn",
        "finproof.api.app:create_app",
        "--factory",
        "--host",
        "0.0.0.0",  # noqa: S104 -- required container bind contract
        "--port",
        "8000",
    ]


def test_docker_context_excludes_runtime_data_secrets_and_unbounded_noise() -> None:
    entries = tuple(
        line
        for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert {".git", ".venv", "artifacts", "source_material", ".env", "*.pdf"} <= set(entries)
    assert len(entries) <= 20
    assert not tuple(Path.cwd().glob("docker-compose*.yml"))
    assert not tuple(Path.cwd().glob("docker-compose*.yaml"))
    assert not Path("entrypoint.sh").exists()
    assert not Path("tests/helpers/mock_provider.py").exists()


def test_ci_has_scoped_container_load_and_short_soak_jobs() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert {"container-contract", "container", "api-load", "short-soak"} <= set(jobs)
    assert jobs["container"]["timeout-minutes"] >= 180
    commands = "\n".join(
        str(step.get("run", ""))
        for job_name in ("container-contract", "container", "api-load", "short-soak")
        for step in jobs[job_name]["steps"]
    )
    assert commands.count("docker build -t finproof:phase3 .") == 1
    assert "FINPROOF_RUN_DOCKER_SMOKE=1" in commands
    assert "FINPROOF_RUN_API_LOAD=1" in commands
    assert "FINPROOF_SOAK_SECONDS=30" in commands
