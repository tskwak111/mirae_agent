"""Fail closed unless Git is rooted at the explicitly expected workspace."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Final


class RepoRootError(RuntimeError):
    """Raised when a Git command would operate outside the expected workspace."""


GIT_NOT_FOUND: Final = "not inside a Git repository"
REPOSITORY_SELECTION_ENV: Final = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_SHALLOW_FILE",
    "GIT_REPLACE_REF_BASE",
    "GIT_EXEC_PATH",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
)
GIT_TIMEOUT_SECONDS: Final = 10
GIT_EXECUTABLE: Final = shutil.which("git") or "git"


def _existing_directory(path: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RepoRootError(f"{label} is not an accessible directory: {path}") from exc
    if not resolved.is_dir():
        raise RepoRootError(f"{label} is not an accessible directory: {resolved}")
    return resolved


def _reject_repository_selection_env() -> None:
    selected = sorted(
        name
        for name in os.environ
        if name in REPOSITORY_SELECTION_ENV or re.fullmatch(r"GIT_CONFIG_(?:KEY|VALUE)_\d+", name)
    )
    if selected:
        joined = ", ".join(selected)
        raise RepoRootError(f"repository-selection environment variable is set: {joined}")


def git_top_level(cwd: Path) -> Path:
    """Return Git's resolved top-level directory or fail with a domain error."""
    _reject_repository_selection_env()
    working_directory = _existing_directory(cwd, label="working directory")
    local_marker = working_directory / ".git"
    immediate_parent_marker = working_directory.parent / ".git"
    if not local_marker.exists() and not immediate_parent_marker.exists():
        raise RepoRootError(f"{GIT_NOT_FOUND}: {working_directory}")
    try:
        result = subprocess.run(
            [GIT_EXECUTABLE, "rev-parse", "--show-toplevel"],
            cwd=working_directory,
            check=False,
            capture_output=True,
            encoding="utf-8",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise RepoRootError(f"Git root discovery could not run: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.rstrip("\r\n")
        if "not a git repository" in detail.lower():
            raise RepoRootError(f"{GIT_NOT_FOUND}: {working_directory}")
        raise RepoRootError(f"Git root discovery failed for {working_directory}: {detail}")
    output = result.stdout.rstrip("\r\n")
    if not output:
        raise RepoRootError(f"Git root discovery returned no path for {working_directory}")
    return Path(output).resolve()


def ensure_exact_repo_root(expected_root: Path, cwd: Path | None = None) -> Path:
    """Require Git's top-level path to equal the explicitly expected root."""
    expected = _existing_directory(expected_root, label="expected root")
    invoking = _existing_directory(cwd or Path.cwd(), label="invoking working directory")
    if not invoking.samefile(expected):
        raise RepoRootError(
            f"invoking working directory {invoking} does not match expected root {expected}"
        )
    actual = git_top_level(invoking)
    if not actual.samefile(expected):
        raise RepoRootError(f"Git top level {actual} does not match expected root {expected}")
    return actual


def ensure_clean_index(root: Path) -> None:
    """Fail unless the exact repository has no paths staged for commit."""
    exact_root = ensure_exact_repo_root(root, cwd=root)
    try:
        result = subprocess.run(
            [
                GIT_EXECUTABLE,
                "diff",
                "--cached",
                "--quiet",
                "--no-ext-diff",
                "--ita-visible-in-index",
                "--",
            ],
            cwd=exact_root,
            check=False,
            capture_output=True,
            encoding="utf-8",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise RepoRootError(f"Git index inspection could not run: {exc}") from exc
    if result.returncode == 0:
        return
    if result.returncode != 1:
        raise RepoRootError(f"Git index inspection failed: {result.stderr.rstrip('\r\n')}")
    try:
        diagnostic = subprocess.run(
            [
                GIT_EXECUTABLE,
                "diff",
                "--cached",
                "--name-only",
                "-z",
                "--ita-visible-in-index",
                "--",
            ],
            cwd=exact_root,
            check=False,
            capture_output=True,
            encoding="utf-8",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise RepoRootError(f"Git staged-path inspection could not run: {exc}") from exc
    if diagnostic.returncode != 0:
        raise RepoRootError(
            f"Git staged-path inspection failed: {diagnostic.stderr.rstrip('\r\n')}"
        )
    staged = tuple(path for path in diagnostic.stdout.split("\0") if path)
    detail = ", ".join(ascii(path) for path in staged) or "<unresolved staged state>"
    raise RepoRootError(f"Git index is not clean; staged paths: {detail}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the exact-root check as a command-line gate."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-root", required=True, type=Path)
    parser.add_argument("--require-clean-index", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = ensure_exact_repo_root(args.expected_root)
        if args.require_clean_index:
            ensure_clean_index(root)
    except RepoRootError as exc:
        parser.exit(2, f"repository safety check failed: {exc}\n")
    print(f"Repository root PASS: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
