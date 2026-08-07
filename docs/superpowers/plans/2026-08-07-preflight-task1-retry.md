# Preflight Task 1 Closed Git Workflow Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make repository Markdown Git workflows fail closed on every unapproved Git command and
every executable context change after the exact-root guard.

**Architecture:** One typed classifier owns all supported Git command shapes. One absorbing
per-fence state analyzer consumes that classifier and produces context and unguarded violations;
routing documents are normalized so a guard-containing executable fence is guard-only or a
dedicated Git workflow.

**Tech Stack:** Python 3.12 standard library, pytest, Ruff, mypy, CommonMark-aware line scanning,
PowerShell-oriented repository instructions, Git.

## Global Constraints

- Canonical brief:
  `docs/superpowers/specs/2026-08-07-preflight-task1-retry-design.md`, SHA-256
  `8e018109d130af5428d657ebbc1f8fa06ff09ea6a97ffb710eec89bcf97ac3f5` for the Candidate 3
  amendment (predecessor Candidate 1–2 hash:
  `0d271aa90df317ee470848aa603d8c61391d123c7bd7d3dac4d00f19f08a34d6`).
- Base commit: `94f0bfbbfd6034113c7f6dcb5927331f67f37675`; design commit:
  `00b9c86b6bcded627c7043b2c53c0f2f94d65a07`.
- Exact worktree:
  `C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`, branch
  `codex/preflight-safety`.
- This plan is one `STATUS.md` task. The numbered tasks below are internal reviewable checkpoints,
  not authorization to begin Preflight Task 2.
- `docs/implementation/QUALITY_LOOP.md` overrides execution-aid skills: coordinator `/root` is the
  only production/document/status writer and the only Git actor; `/root/retry_cycle_oracle` owns
  only `tests/contract/test_handoff_package.py`.
- Retry Candidate 1–3 and one infrastructure retry are the complete budget.
- Candidate 3 is additionally bound by the frozen amendment in canonical brief section 10: base
  `2dd7da5a23227918124abd4748baf921c93d8860`, no new supported Git command, non-expanding
  literal ASCII commit messages, and every non-empty post-guard line invalidating context.
- No dependency, product behavior, data, schema, prompt, API, HCX, remote, push, tag, or release
  action is allowed.
- TDD is strict: observe behavior RED before production edits, then make one minimal production
  change and observe focused GREEN before the next behavior.
- Every Git inspection or mutation follows the exact-root guard. Staging uses only the literal
  paths declared by the current checkpoint and an empty index.

---

### Task 1: Closed classifier, absorbing context state, and compatible routing surfaces

**Files:**

- Modify: `tests/contract/test_handoff_package.py`
- Modify: `tools/verify_handoff.py`
- Modify: `START_HERE.md`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`
- Modify: `docs/implementation/QUALITY_LOOP.md`
- Modify: `docs/implementation/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`
- Modify: `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`

**Interfaces:**

- Consumes: `_shell_tokens`, `_literal_stage_path`, `_shell_blocks`, `_is_root_guard`, and the
  existing stage/commit/Markdown verifier interfaces in `tools.verify_handoff`.
- Produces: `GitCommandKind`, `classify_git_command(line: str) -> GitCommandKind`, and
  `unsafe_git_context_lines(text: str) -> tuple[tuple[int, str], ...]`.
- Preserves: `unsafe_git_stage_lines`, `unguarded_git_block_lines`, `unsafe_git_commit_lines`,
  `git_workflow_violations`, and `verify_git_workflow_markdown` call signatures.

- [ ] **Step 1: Oracle writes the closed-command behavior tests**

Add these imports and behavior tests to `tests/contract/test_handoff_package.py`. Expectations are
literal and exercise the real classifier and public violation function.

````python
from tools.verify_handoff import (
    GitCommandKind,
    classify_git_command,
    unsafe_git_context_lines,
)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git status --short", GitCommandKind.READ_ONLY),
        ("git branch --show-current", GitCommandKind.READ_ONLY),
        ("git log -3 --oneline", GitCommandKind.READ_ONLY),
        ("git diff --check", GitCommandKind.READ_ONLY),
        ("git diff --cached --name-status --", GitCommandKind.READ_ONLY),
        ("git add -- README.md", GitCommandKind.INDEX_MUTATION),
        ("git commit -m safe", GitCommandKind.HISTORY_MUTATION),
    ],
)
def test_closed_git_classifier_accepts_only_registered_shapes(
    command: str, expected: GitCommandKind
) -> None:
    assert classify_git_command(command) is expected


@pytest.mark.parametrize(
    "command",
    [
        "git publish",
        "git publish origin main",
        "git fetch origin",
        "git status",
        "git log --oneline -3",
        "git diff --cached --name-status",
        "git tag -a finproof-submission -m release",
    ],
)
def test_closed_git_classifier_rejects_unknown_commands_and_near_misses(
    command: str,
) -> None:
    assert classify_git_command(command) is GitCommandKind.UNSUPPORTED


@pytest.mark.parametrize("command", ["git publish", "git fetch origin"])
def test_guarded_blocks_reject_unallowlisted_git_commands(command: str) -> None:
    text = f"""```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
{command}
```
"""
    assert unguarded_git_block_lines(text) == ((3, command),)
````

- [ ] **Step 2: Oracle writes absorbing-context behavior tests**

Add tests that name the context transition that must break. Do not derive expectations through
production helpers.

````python
@pytest.mark.parametrize(
    "invalidation",
    [
        "$env:GIT_DIR='../other/.git'",
        "& Set-Location ..",
        "Set-Alias git Invoke-Evil",
    ],
)
def test_post_guard_execution_invalidates_context(invalidation: str) -> None:
    text = f"""```powershell
python tools/check_repo_root.py --expected-root .
{invalidation}
git status --short
```
"""
    assert unsafe_git_context_lines(text)
    assert unsafe_git_context_lines(text)[0][0] == 3
    assert unguarded_git_block_lines(text)[-1] == (4, "git status --short")


def test_invalid_context_cannot_be_rearmed_by_relative_guard() -> None:
    text = """```powershell
python tools/check_repo_root.py --expected-root .
& Set-Location ..
python tools/check_repo_root.py --expected-root .
git status --short
```
"""
    assert unsafe_git_context_lines(text)[0][0] == 3
    assert unguarded_git_block_lines(text)[-1] == (5, "git status --short")


def test_cmd_caret_obfuscated_git_is_rejected_after_guard() -> None:
    text = """```cmd
python tools/check_repo_root.py --expected-root .
g^it status --short
```
"""
    assert unsafe_git_context_lines(text) == ((3, "g^it status --short"),)
````

- [ ] **Step 3: Run the focused oracle selection and record RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/contract/test_handoff_package.py -q -k "closed_git_classifier or unallowlisted_git_commands or post_guard_execution or cannot_be_rearmed or caret_obfuscated"
```

Expected: collection fails because `GitCommandKind`, `classify_git_command`, and
`unsafe_git_context_lines` do not exist. After adding interface stubs solely to permit collection,
the behavior cases must fail because current code accepts the recorded bypasses; an infrastructure
error is not RED.

- [ ] **Step 4: Implement the exact typed classifier**

In `tools/verify_handoff.py`, import `Enum` and define one authoritative classifier. Existing
category-specific reporting may inspect the result but may not define a second supported-command
registry.

```python
class GitCommandKind(Enum):
    NOT_GIT = "not_git"
    UNSUPPORTED = "unsupported"
    READ_ONLY = "read_only"
    INDEX_MUTATION = "index_mutation"
    HISTORY_MUTATION = "history_mutation"


READ_ONLY_GIT_ARGUMENTS: Final = {
    ("status", "--short"),
    ("branch", "--show-current"),
    ("log", "-3", "--oneline"),
    ("diff", "--check"),
    ("diff", "--cached", "--name-status", "--"),
}


def classify_git_command(line: str) -> GitCommandKind:
    stripped = line.strip()
    if not _contains_git_command(stripped):
        return GitCommandKind.NOT_GIT
    if not re.match(r"^git[ \t]+", stripped):
        return GitCommandKind.UNSUPPORTED
    if any(marker in stripped for marker in (";", "|", "&", "`", "$(", "<", ">", "\\", "(", ")")):
        return GitCommandKind.UNSUPPORTED
    tokens = _shell_tokens(stripped)
    if not tokens or tokens[0] != "git":
        return GitCommandKind.UNSUPPORTED
    arguments = tokens[1:]
    if arguments in READ_ONLY_GIT_ARGUMENTS:
        return GitCommandKind.READ_ONLY
    if len(tokens) >= 4 and tokens[:3] == ("git", "add", "--"):
        return (
            GitCommandKind.INDEX_MUTATION
            if all(_literal_stage_path(path) for path in tokens[3:])
            else GitCommandKind.UNSUPPORTED
        )
    if (
        len(tokens) == 4
        and tokens[:3] == ("git", "commit", "-m")
        and _literal_commit_message_expression(stripped)
    ):
        return GitCommandKind.HISTORY_MUTATION
    return GitCommandKind.UNSUPPORTED
```

Update `_is_canonical_stage`, `_is_canonical_commit`, `_is_unsafe_git_invocation`, and
`_is_mutating_git_line` to consume `classify_git_command`. Unknown commands must be unsafe even
under a clean guard.

- [ ] **Step 5: Run classifier tests and observe focused GREEN**

Run the classifier and unallowlisted-command selection from Step 3. Expected: every selected
classifier/unknown-command case passes while the context tests remain RED.

- [ ] **Step 6: Implement the absorbing guarded-workflow analyzer**

Add `cmd`, `bat`, and `batch` to `EXECUTABLE_FENCE_LABELS`. Make `_should_scan_fence` scan a
non-inert block containing an exact root guard even when Git token detection fails.

Implement one internal analyzer used by both public functions. Its shape is:

```python
class _GitWorkflowState(Enum):
    START = "start"
    GUARDED_READ = "guarded_read"
    GUARDED_CLEAN = "guarded_clean"
    INVALID = "invalid"


def _analyze_git_block(
    block: tuple[tuple[int, str], ...],
) -> tuple[tuple[tuple[int, str], ...], tuple[tuple[int, str], ...]]:
    context: list[tuple[int, str]] = []
    unguarded: list[tuple[int, str]] = []
    state = _GitWorkflowState.START
    continued_lines = {line_number for line_number, _ in _continued_git_lines(block)}

    for line_number, line in block:
        stripped = line.strip()
        if not stripped:
            continue
        if state is _GitWorkflowState.START:
            if _is_root_guard(stripped, require_clean_index=True):
                state = _GitWorkflowState.GUARDED_CLEAN
            elif _is_root_guard(stripped):
                state = _GitWorkflowState.GUARDED_READ
            elif _contains_git_command(stripped):
                unguarded.append((line_number, stripped))
            continue
        if state is _GitWorkflowState.INVALID:
            if _contains_git_command(stripped):
                unguarded.append((line_number, stripped))
            continue

        kind = classify_git_command(stripped)
        if kind is GitCommandKind.READ_ONLY:
            continue
        if kind in {GitCommandKind.INDEX_MUTATION, GitCommandKind.HISTORY_MUTATION}:
            if state is not _GitWorkflowState.GUARDED_CLEAN:
                unguarded.append((line_number, stripped))
            continue
        if kind is GitCommandKind.UNSUPPORTED or line_number in continued_lines:
            unguarded.append((line_number, stripped))
        else:
            context.append((line_number, stripped))
        state = _GitWorkflowState.INVALID

    return tuple(context), tuple(unguarded)
```

The final implementation must also report direct Git after invalidation, preserve existing
continuation/non-bare Git regressions, and ensure a later root guard cannot leave `INVALID`.
It treats every non-empty line as context-bearing, including apparent comment syntax, because the
same spelling is not a comment in every supported fence dialect. Only blank lines are exempt.
`unsafe_git_context_lines` aggregates the first return value;
`unguarded_git_block_lines` aggregates the second. Add unsafe-context results to
`git_workflow_violations`.

- [ ] **Step 7: Run context and legacy adversarial selections**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/contract/test_handoff_package.py -q -k "post_guard_execution or cannot_be_rearmed or caret_obfuscated or continuation or nonbare_platform_git_spellings or directory_stack_changes or commonmark"
```

Expected: selected context and legacy adversarial tests pass.

- [ ] **Step 8: Normalize repository routing surfaces to the strict grammar**

Make only these documentation changes:

1. Split the guard from non-Git validation commands in `START_HERE.md`.
2. Split the three guard-plus-validation blocks in
   `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`.
3. Remove the Phase 4 `git tag` command and state that tagging remains deferred until a tested
   clean-worktree release gate exists.
4. Record the exact supported Git grammar, absorbing invalid state, and tag deferral in
   `docs/implementation/QUALITY_LOOP.md`.
5. Add this retry spec and plan to `REQUIRED_FILES` and `HANDOFF_PACKAGE_MANIFEST.md`.
6. Record RED/GREEN commands, results, writers, and Retry Candidate 1 state in `STATUS.md`.

Do not change any financial, prompt, API, deployment, or later-task behavior.

- [ ] **Step 9: Run Task 1 regression and handoff invariants**

Run the exact-root guard alone:

```powershell
.venv\Scripts\python.exe tools/check_repo_root.py --expected-root .
```

Then run:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/contract/test_repo_root_guard.py tests/contract/test_handoff_package.py -q
.venv\Scripts\python.exe -B tools/verify_handoff.py
.venv\Scripts\python.exe -B tools/audit_source_data.py --check
.venv\Scripts\python.exe -B tools/extract_schema_catalog.py --check
.venv\Scripts\python.exe -m ruff format --check tools/verify_handoff.py tests/contract/test_handoff_package.py
.venv\Scripts\python.exe -m ruff check tools/verify_handoff.py tests/contract/test_handoff_package.py
.venv\Scripts\python.exe -m mypy tools/verify_handoff.py --follow-imports=skip --ignore-missing-imports
.venv\Scripts\python.exe -m compileall -q tools/verify_handoff.py tests/contract/test_handoff_package.py
```

Expected: all commands exit zero; frozen invariants remain 145,393 rows, snapshot `2026-07-11`,
207 columns, nine official inputs, and 41,384,928 source bytes.

- [ ] **Step 10: Stage the exact Candidate 1 paths and commit**

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tests/contract/test_handoff_package.py tools/verify_handoff.py START_HERE.md HANDOFF_PACKAGE_MANIFEST.md docs/implementation/QUALITY_LOOP.md docs/implementation/STATUS.md docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md
git diff --cached --name-status --
git commit -m "security: close guarded Git workflow grammar"
```

---

### Task 2: Independent Retry Candidate review and durable Task 1 disposition

**Files:**

- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Consumes: committed Retry Candidate 1, canonical brief, this plan, Task 1 pass commands, and the
  Candidate 1–3 budget.
- Produces: independent spec verdict, independent fresh-checkout execution verdict, and either a
  verified Task 1 handoff to Preflight Task 2 or a recorded next retry/BLOCKED disposition.

- [ ] **Step 1: Dispatch two independent read-only verifiers**

Verifier A receives the canonical brief, this plan, and an anonymized diff. Verifier B receives the
candidate commit, acceptance commands, and expected invariants and creates a fresh detached
worktree. Neither verifier receives authority to edit, stage, commit, or change candidate state.

- [ ] **Step 2: Reproduce every BLOCKER/HIGH finding before accepting it**

For each finding, run the smallest safe in-memory or isolated-repository reproducer. A valid
behavior finding receives one focused RED test before a correction. Incorrect findings are rejected
with command output and code evidence.

- [ ] **Step 3: Apply the bounded candidate lifecycle**

If Retry Candidate 1 has a valid BLOCKER/HIGH, create Retry Candidate 2. One final targeted
correction may create Retry Candidate 3. If any BLOCKER/HIGH remains after Retry Candidate 3,
record Task 1 as `BLOCKED`; do not begin Preflight Task 2.

- [ ] **Step 4: Run fresh final verification for an approved candidate**

Run the exact-root guard alone:

```powershell
.venv\Scripts\python.exe tools/check_repo_root.py --expected-root .
```

Then rerun every command from Task 1 Step 9 and observe its full output. Check final Git state:

```powershell
python tools/check_repo_root.py --expected-root .
git status --short
```

- [ ] **Step 5: Record the disposition and commit only `STATUS.md`**

Record candidate hashes, verifier identities, exact outputs, accepted/rejected findings, waivers,
unresolved risks, and the exact next task.

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "docs: record Task 1 retry disposition"
```
