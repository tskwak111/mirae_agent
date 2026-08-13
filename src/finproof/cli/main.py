"""Bootstrap command-line entry point."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

from finproof.core.errors import FinProofError
from finproof.core.versions import VersionBundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finproof")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("verify-handoff", help="Verify the repository handoff contract")
    subcommands.add_parser("audit-source", help="Check official data against the frozen audit")
    subcommands.add_parser("show-versions", help="Print the current immutable version bundle")
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
    root = Path.cwd().resolve()
    required = (
        root / "AGENTS.md",
        root / "source_material/input_manifest.json",
        root / "tools/__init__.py",
    )
    if not all(path.is_file() for path in required):
        raise FinProofError("bootstrap source commands must run from a FinProof checkout")

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


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch a FinProof bootstrap command and return its exit code."""
    args = _parser().parse_args(None if argv is None else list(argv))
    command = cast(str, args.command)

    try:
        if command == "verify-handoff":
            return _verify_handoff()
        if command == "audit-source":
            return _audit_source()
        return _show_versions()
    except FinProofError as error:
        sys.stderr.write(f"error: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
