"""Bootstrap command-line entry point."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

from finproof.cli.evaluate import run_evaluation
from finproof.core.errors import FinProofError
from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.builder import build_artifacts
from finproof.data.artifacts.config import ArtifactBuildOptions
from finproof.data.artifacts.errors import ArtifactContractError
from finproof.data.artifacts.manifest import ArtifactManifest
from finproof.evaluation.runner import EvaluationMode


class _ArtifactBuilder(Protocol):
    def __call__(
        self,
        settings: Settings,
        versions: VersionBundle,
        *,
        options: ArtifactBuildOptions,
    ) -> ArtifactManifest: ...


class _Evaluator(Protocol):
    def __call__(self, suite: str, output: Path, mode: EvaluationMode, /) -> None: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finproof")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("verify-handoff", help="Verify the repository handoff contract")
    subcommands.add_parser("audit-source", help="Check official data against the frozen audit")
    subcommands.add_parser("show-versions", help="Print the current immutable version bundle")
    build_data = subcommands.add_parser("build-data", help="Build verified data artifacts")
    build_data.add_argument("--clean", action="store_true")
    evaluate = subcommands.add_parser("evaluate", help="Run a reviewed evaluation suite")
    evaluate.add_argument("--suite", choices=("canonical", "robustness"), required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument(
        "--mode",
        type=EvaluationMode,
        choices=tuple(EvaluationMode),
        default=EvaluationMode.END_TO_END,
    )
    return parser


def _show_versions() -> int:
    rendered = json.dumps(
        VersionBundle().model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    sys.stdout.write(f"{rendered}\n")
    return 0


def _load_repository_tool(module_name: str) -> ModuleType:
    root = Path(__file__).resolve().parents[3]
    required = (
        root / "AGENTS.md",
        root / "pyproject.toml",
        root / "source_material/input_manifest.json",
        root / "tools/__init__.py",
    )
    if Path.cwd().resolve() != root or not all(path.is_file() for path in required):
        raise FinProofError(
            "bootstrap source commands must run from the installed FinProof checkout"
        )

    sys.path.insert(0, str(root))
    try:
        return importlib.import_module(f"tools.{module_name}")
    finally:
        sys.path.pop(0)


def _verify_handoff() -> int:
    module = _load_repository_tool("verify_handoff")
    tool_main = cast(Callable[[], int], module.main)
    return tool_main()


def _audit_source() -> int:
    module = _load_repository_tool("audit_source_data")
    tool_main = cast(Callable[[list[str] | None], int], module.main)
    return tool_main(["--check"])


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _build_data(
    *,
    clean: bool,
    builder: _ArtifactBuilder,
    clock: Callable[[], datetime],
) -> int:
    settings = Settings()
    versions = VersionBundle()
    timestamp = clock()
    manifest = builder(
        settings,
        versions,
        options=ArtifactBuildOptions(
            clean=clean,
            persistence_timestamp=timestamp,
        ),
    )
    rendered = json.dumps(
        {
            "database_path": manifest.database_path,
            "logical_hash": manifest.logical_hash,
            "manifest_path": "manifest.json",
            "target_basename": settings.artifact_dir.name,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    sys.stdout.write(rendered + "\n")
    return 0


def _run_main(
    argv: Sequence[str] | None,
    *,
    builder: _ArtifactBuilder = build_artifacts,
    clock: Callable[[], datetime] = _utc_now,
    evaluator: _Evaluator = run_evaluation,
) -> int:
    args = _parser().parse_args(None if argv is None else list(argv))
    command = cast(str, args.command)

    try:
        if command == "verify-handoff":
            return _verify_handoff()
        if command == "audit-source":
            return _audit_source()
        if command == "build-data":
            return _build_data(
                clean=cast(bool, args.clean),
                builder=builder,
                clock=clock,
            )
        if command == "evaluate":
            evaluator(
                cast(str, args.suite),
                cast(Path, args.output),
                cast(EvaluationMode, args.mode),
            )
            return 0
        return _show_versions()
    except ArtifactContractError as error:
        published = "; published verified target retained" if error.published else ""
        sys.stderr.write(f"error: {error.safe_message}{published}\n")
        return 2
    except FinProofError as error:
        sys.stderr.write(f"error: {error}\n")
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch a FinProof command and return its exit code."""
    return _run_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
