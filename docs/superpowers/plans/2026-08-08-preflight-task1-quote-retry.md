# Preflight Task 1 Single-Quote Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject single-quoted Git commit messages across every supported Markdown shell dialect
while preserving unquoted, double-quoted, and blank-line behavior.

**Architecture:** Keep `classify_git_command` and `_literal_commit_message_expression` as the one
closed grammar. Narrow only the quoted-message branch to matching double quotes, pin the behavior
through public diagnostics for CMD/BAT/batch, and register the new retry documents in the durable
handoff surfaces.

**Tech Stack:** Python 3.12 standard library, pytest, Ruff, mypy, Markdown contract validation,
PowerShell, Git.

## Global Constraints

- Canonical brief:
  `docs/superpowers/specs/2026-08-08-preflight-task1-quote-retry-design.md`, SHA-256
  `26eab093d601a82837e5e38661430d37c59c8b183d7ce6ae470fb655ef0cfb1b`.
- Written-spec approval: owner approved on 2026-08-08 after design commit
  `80b192a4d54720b3cb339b2f7b32ccf6a979a3f2`.
- Behavior base: `525312c78ae19e13ea5482b635f66f535f2dd8cc`; branch
  `codex/preflight-safety`; exact worktree
  `C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`.
- This is one `STATUS.md` task and exactly one behavior candidate. A valid final BLOCKER/HIGH
  returns Task 1 to `BLOCKED`; no correction candidate is authorized.
- Coordinator `/root` is the only production/document/status writer and Git actor. Oracle
  `/root/candidate3_oracle` owns only `tests/contract/test_handoff_package.py`. Final spec verifier
  `/root/r3_spec_conformance` and execution verifier `/root/r1_execution_verifier` are read-only.
- The owner already selected fan-out/subagent-driven execution. File writers remain sequential;
  the two independent final reviews may run in parallel only after the candidate commit is frozen.
- No dependency, product, data, schema, prompt, API, HCX, deployment, GitHub, remote, tag, push,
  release, root-guard, state-machine, staging, or Preflight Task 2 behavior change is authorized.
- Only unquoted or matching double-quoted literal ASCII commit messages remain supported. Every
  single quote in the message expression is unsupported.
- TDD is strict for the single-quote behavior. The blank-line test is a baseline-positive
  characterization and does not authorize production behavior.
- The established checkout-local pytest basetemp may be used directly for the known Windows ACL
  condition. At most one separately recorded infrastructure rerun is allowed; it is not a behavior
  retry.
- Every Git inspection or mutation follows the exact-root guard. Candidate staging uses only the
  literal paths declared in Task 2 and an empty index.

---

### Task 1: Oracle contract and focused RED

**Files:**

- Test: `tests/contract/test_handoff_package.py`

**Interfaces:**

- Consumes: `GitCommandKind`, `classify_git_command`, `unsafe_git_context_lines`,
  `unguarded_git_block_lines`, and `unsafe_git_commit_lines` from `tools.verify_handoff`.
- Produces: eleven pytest cases covering two classifier negatives, three CMD-family public
  diagnostic negatives, three blank-line positives, and three double-quoted workflow positives.

- [ ] **Step 1: Add the exact oracle cases**

Append these tests without changing existing expectations:

````python
@pytest.mark.parametrize(
    "command",
    ["git commit -m 'safe'", "git commit -m 'safe message'"],
)
def test_closed_git_classifier_rejects_single_quoted_commit_messages(
    command: str,
) -> None:
    assert classify_git_command(command) is GitCommandKind.UNSUPPORTED


@pytest.mark.parametrize("label", ["cmd", "bat", "batch"])
def test_cmd_family_single_quoted_commit_is_reported_by_every_public_diagnostic(
    label: str,
) -> None:
    command = "git commit -m 'safe message'"
    text = f"""```{label}
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- README.md
git diff --cached --name-status --
{command}
```
"""

    assert unsafe_git_context_lines(text) == ((5, command),)
    assert unguarded_git_block_lines(text) == ((5, command),)
    assert unsafe_git_commit_lines(text) == ((5, command),)


@pytest.mark.parametrize("label", ["cmd", "bat", "batch"])
def test_cmd_family_blank_line_remains_neutral(label: str) -> None:
    text = f"""```{label}
python tools/check_repo_root.py --expected-root .

git status --short
```
"""

    assert unsafe_git_context_lines(text) == ()
    assert unguarded_git_block_lines(text) == ()


@pytest.mark.parametrize("label", ["cmd", "bat", "batch"])
def test_cmd_family_double_quoted_commit_workflow_remains_supported(label: str) -> None:
    command = 'git commit -m "safe message"'
    text = f"""```{label}
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- README.md
git diff --cached --name-status --
{command}
```
"""

    assert classify_git_command(command) is GitCommandKind.HISTORY_MUTATION
    assert unsafe_git_context_lines(text) == ()
    assert unguarded_git_block_lines(text) == ()
    assert unsafe_git_commit_lines(text) == ()
````

- [ ] **Step 2: Run only the new selection and observe mixed RED/baseline GREEN**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\contract\test_handoff_package.py -q -k "single_quoted_commit or blank_line_remains_neutral or double_quoted_commit_workflow"
```

Expected: 5 failures and 6 passes. The two classifier and three CMD-family single-quote cases fail
because the current classifier accepts single quotes; the blank-line and double-quote controls pass.

- [ ] **Step 3: Verify oracle formatting and scope**

```powershell
.venv\Scripts\python.exe -m ruff format --check tests\contract\test_handoff_package.py
.venv\Scripts\python.exe -m ruff check tests\contract\test_handoff_package.py
```

Expected: both commands exit zero. The oracle reports a diff limited to
`tests/contract/test_handoff_package.py`, with no staging or commit.

---

### Task 2: Minimal grammar correction and candidate checkpoint

**Files:**

- Modify: `tests/contract/test_handoff_package.py`
- Modify: `tools/verify_handoff.py`
- Modify: `docs/implementation/QUALITY_LOOP.md`
- Modify: `docs/implementation/STATUS.md`
- Modify: `START_HERE.md`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`

**Interfaces:**

- Consumes: the Task 1 RED/positive controls and the existing
  `_literal_commit_message_expression(line: str) -> bool` classifier helper.
- Produces: an unchanged public classifier API whose history-mutation grammar accepts only
  unquoted or double-quoted literal ASCII messages; durable handoff registration for this spec and
  plan; one committed candidate for final review.

- [ ] **Step 1: Reproduce the exact oracle selection as coordinator**

Run the Task 1 Step 2 command unchanged. Expected: the same 5 failures and 6 passes for the same
behavioral reasons. Stop if the failure shape differs.

- [ ] **Step 2: Apply the smallest production change**

Replace only the quoted branch in `_literal_commit_message_expression`:

```python
def _literal_commit_message_expression(line: str) -> bool:
    prefix = "git commit -m "
    if not line.startswith(prefix):
        return False
    expression = line.removeprefix(prefix)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", expression):
        return True
    if len(expression) < 2 or expression[0] != '"':
        return False
    if expression[-1] != '"':
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._:/-]*", expression[1:-1]))
```

Do not change `_shell_tokens`, `classify_git_command`, fence labels, workflow states, or public
signatures.

- [ ] **Step 3: Run the focused selection and observe GREEN**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\contract\test_handoff_package.py -q -k "single_quoted_commit or blank_line_remains_neutral or double_quoted_commit_workflow"
```

Expected: 11 passed. If any baseline-positive case changes, revert the implementation and stop.

- [ ] **Step 4: Align the normative policy and durable handoff**

Make these exact documentation/registration updates:

1. In `QUALITY_LOOP.md`, replace `literal or quoted ASCII message` with
   `unquoted or double-quoted literal ASCII message`, and explicitly state that every single quote
   in the message expression is unsupported.
2. Add the new spec and this plan to `REQUIRED_FILES` in `tools/verify_handoff.py`.
3. Add the same two literal paths to the identical documentation `git add -- docs/...` line in
   both `START_HERE.md` and `HANDOFF_PACKAGE_MANIFEST.md`.
4. Update `STATUS.md` with the plan hash, writers, observed RED/GREEN, baseline-positive results,
   exact commands, candidate files, and final-review state. Do not mark Task 1 complete.

- [ ] **Step 5: Run focused, regression, and frozen-invariant gates**

Run the exact-root guard alone:

```powershell
.venv\Scripts\python.exe tools/check_repo_root.py --expected-root .
```

Then run:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_tmp_quote_retry tests\contract\test_repo_root_guard.py tests\contract\test_handoff_package.py -q
.venv\Scripts\python.exe -B tools\verify_handoff.py
.venv\Scripts\python.exe -B tools\audit_source_data.py --check
.venv\Scripts\python.exe -B tools\extract_schema_catalog.py --check
.venv\Scripts\python.exe -m ruff format --check tools\verify_handoff.py tests\contract\test_handoff_package.py
.venv\Scripts\python.exe -m ruff check tools\verify_handoff.py tests\contract\test_handoff_package.py
.venv\Scripts\python.exe -m mypy tools\verify_handoff.py --follow-imports=skip --ignore-missing-imports
.venv\Scripts\python.exe -m compileall -q tools\verify_handoff.py tests\contract\test_handoff_package.py
```

Expected: 172 Task 1 contracts; handoff 71 required files, nine official inputs, and 41,384,928
source bytes; source audit 145,393 rows at snapshot `2026-07-11`; schema catalog 207 columns; Ruff,
focused mypy, and compileall exit zero.

- [ ] **Step 6: Remove only verifier-created caches and prove the candidate diff**

Resolve and verify every cleanup target under the exact worktree before removal. Remove only
`.pytest_tmp_quote_retry`, tool/test `__pycache__`, `.mypy_cache`, and `.ruff_cache` created by the
commands above. Confirm LF checkout and a diff limited to the six declared files.

- [ ] **Step 7: Stage the exact candidate and commit**

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tests/contract/test_handoff_package.py tools/verify_handoff.py docs/implementation/QUALITY_LOOP.md docs/implementation/STATUS.md START_HERE.md HANDOFF_PACKAGE_MANIFEST.md
git diff --cached --name-status --
git commit -m "security: reject single-quoted commit messages"
```

Expected staged paths: exactly the six `Modify` paths above. After commit, the worktree and index
are clean. Record the full candidate hash without changing the candidate before final review.

---

### Task 3: Two independent final reviews and durable disposition

**Files:**

- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Consumes: the frozen candidate commit, canonical brief and plan hashes, Task 2 command outputs,
  and the exact one-candidate budget.
- Produces: one independent specification verdict, one fresh-checkout execution verdict, and a
  durable Task 1 PASS or BLOCKED disposition.

- [ ] **Step 1: Dispatch the two final verifiers in parallel**

Give the spec verifier only the canonical brief, plan, candidate diff, and acceptance criteria.
Give the execution verifier the candidate hash, expected 172-test/invariant outputs, and a unique
fresh detached worktree path. Neither verifier may edit, stage, commit, tag, push, or switch the
candidate branch.

- [ ] **Step 2: Require exact review coverage**

Both reviewers must independently check:

- every single-quoted no-space and spaced message is unsupported;
- CMD, BAT, and batch public diagnostics all report the unsupported history mutation;
- unquoted and double-quoted messages remain supported;
- a blank line remains neutral;
- the spec, plan, `QUALITY_LOOP.md`, `STATUS.md`, implementation, tests, required-file list, and
  both frozen initial-import blocks agree;
- no unrelated Git grammar or repository workflow changed.

The execution verifier additionally performs harmless real CMD argv-boundary inspection, runs all
Task 2 Step 5 gates from a fresh detached checkout, checks LF/diff state, removes only its caches,
and proves both candidate and verifier worktrees clean.

- [ ] **Step 3: Apply the one-candidate disposition rule**

If either reviewer reports a valid BLOCKER/HIGH, reproduce it safely, record Task 1 `BLOCKED`, and
make no behavior/test correction. If both report zero BLOCKER/HIGH, resolve every MEDIUM without an
unowned waiver, mark Preflight Task 1 complete, and set the exact next task to Preflight Task 2
without beginning it.

- [ ] **Step 4: Record and commit only the durable disposition**

Update `STATUS.md` with the candidate hash, both verifier identities and severity counts, exact
observed commands/results, accepted/rejected findings, remaining risks, cleanup, and exact next
task.

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "docs: record Task 1 quote retry disposition"
```

- [ ] **Step 5: Run the final handoff and cleanliness checks**

```powershell
.venv\Scripts\python.exe -B tools\verify_handoff.py
```

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git status --short
git log -3 --oneline
```

Expected: handoff exits zero with 71 required files; exact root and empty index pass; status is
empty; log shows the disposition and candidate checkpoints. Task 2 remains untouched in this
session.
