from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tools.check_repo_root import (
    RepoRootError,
    ensure_clean_index,
    ensure_exact_repo_root,
    git_top_level,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "check_repo_root.py"
REPOSITORY_SELECTION_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_KEY_0",
    "GIT_CONFIG_VALUE_0",
    "GIT_CONFIG_PARAMETERS",
)
GIT_EXECUTABLE = shutil.which("git") or "git"


def clean_git_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in REPOSITORY_SELECTION_ENV:
        env.pop(name, None)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env


@pytest.fixture(autouse=True)
def _clear_repository_selection_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in REPOSITORY_SELECTION_ENV:
        monkeypatch.delenv(name, raising=False)


def run_git(path: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 - test arguments are fixed by each test case
        [GIT_EXECUTABLE, *args],
        cwd=path,
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=clean_git_env(),
    )


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, "init", "--initial-branch=main")


def configure_test_identity(repo: Path) -> None:
    run_git(repo, "config", "user.name", "FinProof Test")
    run_git(repo, "config", "user.email", "finproof-test@example.invalid")
    run_git(repo, "config", "commit.gpgSign", "false")


def create_linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "main repo"
    linked = repo / ".worktrees" / "연결 작업공간"
    init_repo(repo)
    configure_test_identity(repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    run_git(repo, "add", "--", "README.md")
    run_git(repo, "commit", "-m", "baseline")
    linked.parent.mkdir()
    run_git(repo, "worktree", "add", "-b", "codex/test-linked", "--", str(linked))
    return repo, linked


def run_cli(
    cwd: Path, expected_root: str = ".", *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - invokes this repository's fixed CLI
        [sys.executable, str(SCRIPT), "--expected-root", expected_root],
        cwd=cwd,
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=env or clean_git_env(),
    )


def test_exact_repository_root_is_accepted(tmp_path: Path) -> None:
    repo = tmp_path / "한글 경로 with spaces"
    init_repo(repo)

    assert ensure_exact_repo_root(repo, cwd=repo) == repo.resolve()

    result = run_cli(repo)
    assert result.returncode == 0
    assert "Repository root PASS:" in result.stdout
    assert result.stderr == ""


def test_ancestor_repository_is_rejected(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "project"
    init_repo(parent)
    child.mkdir()

    with pytest.raises(RepoRootError, match="does not match expected root"):
        ensure_exact_repo_root(child, cwd=child)


def test_missing_repository_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    with pytest.raises(RepoRootError, match="not inside a Git repository"):
        ensure_exact_repo_root(project, cwd=project)


def test_default_cwd_cannot_be_replaced_by_expected_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = tmp_path / "expected"
    elsewhere = tmp_path / "elsewhere"
    init_repo(expected)
    init_repo(elsewhere)
    monkeypatch.chdir(elsewhere)

    with pytest.raises(RepoRootError, match="invoking working directory"):
        ensure_exact_repo_root(expected)


@pytest.mark.parametrize("variable", REPOSITORY_SELECTION_ENV)
def test_repository_selection_environment_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    monkeypatch.setenv(variable, str(tmp_path / "external"))

    with pytest.raises(RepoRootError, match=variable):
        ensure_exact_repo_root(repo, cwd=repo)


def test_linked_worktree_root_and_cross_mismatches(tmp_path: Path) -> None:
    repo, linked = create_linked_worktree(tmp_path)

    assert git_top_level(linked) == linked.resolve()
    assert ensure_exact_repo_root(linked, cwd=linked) == linked.resolve()
    with pytest.raises(RepoRootError, match="does not match expected root"):
        ensure_exact_repo_root(repo, cwd=linked)
    with pytest.raises(RepoRootError, match="does not match expected root"):
        ensure_exact_repo_root(linked, cwd=repo)

    common = subprocess.run(  # noqa: S603 - fixed Git inspection
        [GIT_EXECUTABLE, "rev-parse", "--git-common-dir"],
        cwd=linked,
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=clean_git_env(),
    ).stdout.strip()
    assert Path(common).resolve() != linked.resolve()

    result = run_cli(linked)
    assert result.returncode == 0
    assert "Repository root PASS:" in result.stdout


def test_cli_rejects_ancestor_repository_without_traceback(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "project"
    init_repo(parent)
    child.mkdir()

    result = run_cli(child)

    assert result.returncode == 2
    assert "does not match expected root" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_rejects_missing_repository_without_traceback(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    env = clean_git_env()
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path)

    result = run_cli(project, env=env)

    assert result.returncode == 2
    assert "not inside a Git repository" in result.stderr
    assert "Traceback" not in result.stderr


def test_library_wraps_invalid_paths_as_repo_root_errors(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(RepoRootError, match="expected root is not an accessible directory"):
        ensure_exact_repo_root(missing, cwd=missing)


@pytest.mark.parametrize(
    "launch_error",
    [
        FileNotFoundError("git missing"),
        subprocess.TimeoutExpired(["git", "rev-parse"], 10),
    ],
)
def test_git_launch_errors_are_wrapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    launch_error: OSError | subprocess.TimeoutExpired,
) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)

    def fail_to_launch(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise launch_error

    monkeypatch.setattr("tools.check_repo_root.subprocess.run", fail_to_launch)

    with pytest.raises(RepoRootError, match="Git root discovery could not run"):
        ensure_exact_repo_root(repo, cwd=repo)


def test_clean_index_gate_rejects_preexisting_staged_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / "unexpected.txt").write_text("staged\n", encoding="utf-8")
    run_git(repo, "add", "--", "unexpected.txt")

    with pytest.raises(RepoRootError, match=r"index is not clean.*unexpected\.txt"):
        ensure_clean_index(repo)

    result = subprocess.run(  # noqa: S603 - invokes this repository's fixed CLI
        [
            sys.executable,
            str(SCRIPT),
            "--expected-root",
            ".",
            "--require-clean-index",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=clean_git_env(),
    )
    assert result.returncode == 2
    assert "unexpected.txt" in result.stderr
    assert "Traceback" not in result.stderr


def test_clean_index_gate_accepts_unstaged_worktree_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / "unstaged.txt").write_text("not staged\n", encoding="utf-8")

    ensure_clean_index(repo)

    result = subprocess.run(  # noqa: S603 - invokes this repository's fixed CLI
        [
            sys.executable,
            str(SCRIPT),
            "--expected-root",
            ".",
            "--require-clean-index",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=clean_git_env(),
    )
    assert result.returncode == 0


@pytest.mark.parametrize("staged_change", ["modify", "delete", "rename"])
def test_clean_index_gate_rejects_every_staged_change_type(
    tmp_path: Path, staged_change: str
) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    configure_test_identity(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("baseline\n", encoding="utf-8")
    run_git(repo, "add", "--", "tracked.txt")
    run_git(repo, "commit", "-m", "baseline")

    if staged_change == "modify":
        tracked.write_text("changed\n", encoding="utf-8")
        run_git(repo, "add", "--", "tracked.txt")
    elif staged_change == "delete":
        run_git(repo, "rm", "--", "tracked.txt")
    else:
        run_git(repo, "mv", "--", "tracked.txt", "renamed.txt")

    with pytest.raises(RepoRootError, match="index is not clean"):
        ensure_clean_index(repo)


def test_clean_index_gate_rejects_merge_conflict(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    configure_test_identity(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("baseline\n", encoding="utf-8")
    run_git(repo, "add", "--", "tracked.txt")
    run_git(repo, "commit", "-m", "baseline")
    run_git(repo, "switch", "-c", "feature")
    tracked.write_text("feature\n", encoding="utf-8")
    run_git(repo, "add", "--", "tracked.txt")
    run_git(repo, "commit", "-m", "feature")
    run_git(repo, "switch", "main")
    tracked.write_text("main\n", encoding="utf-8")
    run_git(repo, "add", "--", "tracked.txt")
    run_git(repo, "commit", "-m", "main")

    merge = subprocess.run(  # noqa: S603 - fixed adversarial Git fixture
        [GIT_EXECUTABLE, "merge", "feature"],
        cwd=repo,
        check=False,
        capture_output=True,
        encoding="utf-8",
        env=clean_git_env(),
    )
    assert merge.returncode != 0
    with pytest.raises(RepoRootError, match="index is not clean"):
        ensure_clean_index(repo)


def test_linked_worktree_has_an_independent_index(tmp_path: Path) -> None:
    repo, linked = create_linked_worktree(tmp_path)
    (repo / "main-only.txt").write_text("main\n", encoding="utf-8")
    run_git(repo, "add", "--", "main-only.txt")

    with pytest.raises(RepoRootError, match=r"main-only\.txt"):
        ensure_clean_index(repo)
    ensure_clean_index(linked)

    (linked / "linked-only.txt").write_text("linked\n", encoding="utf-8")
    run_git(linked, "add", "--", "linked-only.txt")

    with pytest.raises(RepoRootError, match=r"linked-only\.txt"):
        ensure_clean_index(linked)
