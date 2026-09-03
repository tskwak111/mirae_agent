"""Fail closed on the static organizer runtime boundary."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

_FIELDS = {"question_id", "question", "retrieved_context", "think_trace", "answer"}
_PROHIBITED = (
    "anthropic",
    "bedrock-runtime",
    "cohere",
    "generativeai",
    "openai",
    "openrouter",
)


def check_repository(root: Path) -> list[str]:
    errors: list[str] = []
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(project["project"]["dependencies"]).lower()
    runtime = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((root / "src").rglob("*.py"))
    ).lower()
    for provider in _PROHIBITED:
        if provider in dependencies or provider in runtime:
            errors.append(f"prohibited generative provider is reachable: {provider}")

    route = (root / "src/finproof/api/routes/answer.py").read_text(encoding="utf-8")
    route_decorators = [
        line.strip()
        for path in sorted((root / "src/finproof/api/routes").glob("*.py"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("@router.")
    ]
    if route_decorators != ['@router.get("/answer")'] or "async def answer(" not in route:
        errors.append("public API must contain only GET /answer")

    schema = json.loads((root / "schemas/api_response.schema.json").read_bytes())
    if (
        schema.get("additionalProperties") is not False
        or set(schema.get("required", ())) != _FIELDS
        or set(schema.get("properties", {})) != _FIELDS
        or any(value != {"type": "string"} for value in schema["properties"].values())
    ):
        errors.append("API response must be the exact five-string envelope")

    settings = (root / "src/finproof/core/settings.py").read_text(encoding="utf-8")
    dependencies_source = (root / "src/finproof/api/dependencies.py").read_text(encoding="utf-8")
    limits = (root / "src/finproof/service/limits.py").read_text(encoding="utf-8")
    if (
        'EVALUATION = "evaluation"' not in settings
        or 'EXTENDED_DEMO = "extended_demo"' not in settings
    ):
        errors.append("evaluation and separately labeled demo modes are required")
    if "execution_mode: ExecutionMode = ExecutionMode.EVALUATION" not in settings:
        errors.append("evaluation must be the default runtime mode")
    if 'hcx_model_name: str = "HCX-007"' not in settings:
        errors.append("the configured evaluation model must default to HCX-007")
    for required in (
        "evaluation requires exact HCX-007 Structured Outputs",
        "evaluation requires HCX",
        "StructuredOutputPlanner",
        "HcxVerbalizer",
    ):
        if required not in dependencies_source:
            errors.append(f"mandatory HCX runtime boundary is missing: {required}")
    if "REQUEST_DEADLINE_SECONDS = 295.0" not in limits:
        errors.append("outer request deadline must reserve completion below 300 seconds")

    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8").splitlines()
    if (
        "USER finproof" not in dockerfile
        or "COPY artifacts" in dockerfile
        or "COPY source_material" in dockerfile
    ):
        errors.append("container must be non-root and exclude runtime data")
    if not {".env", ".env.*", "artifacts", "source_material"} <= set(dockerignore):
        errors.append("Docker context must exclude secrets and official data")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    errors = check_repository(args.root.resolve())
    sys.stdout.write(
        json.dumps({"errors": errors, "status": "passed" if not errors else "failed"}) + "\n"
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
