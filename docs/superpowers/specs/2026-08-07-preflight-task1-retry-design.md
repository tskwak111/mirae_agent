# Preflight Task 1 Retry — Closed Git Workflow Design

**Status:** Owner-approved on 2026-08-07

**Parent task:** Preflight Task 1 — exact Git-root/index guard and repository-owned quality loop

**Retry budget:** Retry Candidate 1–3, with one separately recorded infrastructure retry

**Canonical brief:** The UTF-8 bytes of this file; its SHA-256 is recorded in
`docs/implementation/STATUS.md` before behavior changes begin.

## 1. Objective

Replace the handoff verifier's open-ended Git denylist and Boolean guard tracking with:

1. a closed, typed grammar for the exact Git commands used by repository instructions; and
2. an absorbing workflow state machine that invalidates a root guard after any unapproved
   executable line.

The retry closes the confirmed `git publish`, `git fetch origin`, `$env:GIT_DIR=...`,
`& Set-Location ..`, and CMD `g^it` bypasses without interpreting or executing arbitrary shell.

## 2. Scope and ownership

Base commit: `94f0bfbbfd6034113c7f6dcb5927331f67f37675`

Branch: `codex/preflight-safety`

Externally selected worktree:
`C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`

Exact writable paths and writers:

- Coordinator `/root`:
  - `docs/superpowers/specs/2026-08-07-preflight-task1-retry-design.md`
  - `docs/superpowers/plans/2026-08-07-preflight-task1-retry.md`
  - `tools/verify_handoff.py`
  - `START_HERE.md`
  - `HANDOFF_PACKAGE_MANIFEST.md`
  - `docs/implementation/QUALITY_LOOP.md`
  - `docs/implementation/STATUS.md`
  - `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`
  - `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`
- Oracle writer `/root/retry_cycle_oracle`:
  - `tests/contract/test_handoff_package.py`

All other agents are read-only. Only the coordinator may stage, commit, change `STATUS.md`, or
change candidate state.

## 3. Non-goals

- No production financial behavior, source data, schema, prompt, API, HCX, deployment, remote,
  GitHub, tag, push, or release change.
- No general PowerShell, Bash, CMD, or CommonMark interpreter.
- No new dependency.
- No support for a Git command merely because upstream Git documents it as read-only.
- No re-opening of Preflight Task 2 or later work.

## 4. Frozen inputs

The retry does not interpret financial data, but source invariants remain a completion gate.

| Input | SHA-256 at base |
|---|---|
| `docs/implementation/QUALITY_LOOP.md` | `580e063b6dc835d72a596916da5eb0a30dd865d8f1a8ba9969850997f2d86788` |
| `docs/superpowers/specs/2026-08-07-preflight-safety-remediation-design.md` | `e090f2e8f5cbb30ea81ae329c8eb240a56bd61d65d89e603d14d4944c21b6907` |
| `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md` | `34ed5e3813e51a7a9d1fd85f8b749dfadc67ab36956c6dbd35813a45e69d82bb` |
| `tools/verify_handoff.py` | `ce13c9604988c46586f0b983748c48f1090a61b910328e6463e2898fb3339eff` |
| `tests/contract/test_handoff_package.py` | `cf4ddd076df6f6a801fa2c0fb939fe071bccde6a0b1096146c26a4b4c68e5100` |
| `source_material/input_manifest.json` | `8eb4ee0e0e7335081e208be0787eff65d52540debac434bb47b360b459d62fc4` |

Frozen source expectations: 145,393 rows, snapshot `2026-07-11`, 207 catalog columns, nine
official inputs, and 41,384,928 source bytes.

## 5. Closed Git command grammar

`GitCommandKind` has five values: `NOT_GIT`, `UNSUPPORTED`, `READ_ONLY`, `INDEX_MUTATION`, and
`HISTORY_MUTATION`. `classify_git_command(line)` returns one value for every logical line. Only a
lowercase, direct, bare `git` invocation may be supported.

Exact read-only token tuples:

- `git status --short`
- `git branch --show-current`
- `git log -3 --oneline`
- `git diff --check`
- `git diff --cached --name-status --`

Exact mutation grammars:

- `git add -- PATH+`, where every operand passes the existing literal ASCII repository-relative
  path validator;
- `git commit -m MESSAGE`, with exactly one non-empty parsed message token and the existing clean
  guard → canonical add → staged name/status review contract.

Every other subcommand, argument order, missing terminator, global option, alias, external
`git-foo` extension, path-qualified executable, wrapper, quote-obfuscated executable, chain, or
continuation is `UNSUPPORTED`. This includes `fetch`, `publish`, `show`, `rev-parse`, `status`
without `--short`, and reordered `log` arguments.

The existing Phase 4 `git tag` instruction is removed. Tagging remains unsupported until a later
release task introduces and tests a clean-worktree precondition; clean index alone is insufficient.

## 6. Guarded workflow state machine

States:

- `START`
- `GUARDED_READ`
- `GUARDED_CLEAN`
- `INVALID`

Transitions:

1. The first executable logical line must be the exact root guard. It enters `GUARDED_READ`, or
   `GUARDED_CLEAN` when `--require-clean-index` is present.
2. Blank lines and whole-line `#` comments do not change state.
3. An approved read-only Git command remains in the guarded state.
4. An approved mutation is valid only in `GUARDED_CLEAN`.
5. Any other executable logical line enters `INVALID` and is reported as an unsafe execution
   context. `INVALID` is absorbing.
6. A later relative root guard never re-arms an invalid fence because the current directory may
   already differ from the externally selected worktree.
7. Direct Git following `INVALID` is also reported as unguarded.

Executable labels add `cmd`, `bat`, and `batch`. Any non-inert fence containing the exact root guard
is scanned even when existing Git detection finds no Git token. This makes variable wrappers,
aliases, call operators, environment mutation, directory mutation, child shells, and CMD caret
obfuscation fail closed after a guard.

Existing root-guard-plus-validation fences in `START_HERE.md` and the parent preflight plan are
split so a guarded shell fence is either guard-only or a dedicated approved Git workflow.

## 7. Interfaces

`tools.verify_handoff` produces:

- `GitCommandKind`;
- `classify_git_command(line: str) -> GitCommandKind`;
- `unsafe_git_context_lines(text: str) -> tuple[tuple[int, str], ...]`;
- existing `unguarded_git_block_lines`, `unsafe_git_stage_lines`, and
  `unsafe_git_commit_lines`, all consuming the closed classifier rather than independent
  subcommand denylists.

`git_workflow_violations` reports unsafe context lines alongside stage, guard, and commit findings.

## 8. TDD and acceptance

The oracle writes focused behavior tests before production edits. Required RED cases:

- unknown alias/extension commands: `git publish`, `git publish origin main`;
- unallowlisted repository mutation: `git fetch origin`;
- near-miss arguments for each approved read-only grammar;
- post-guard `$env:GIT_DIR=...`, `& Set-Location ..`, and `Set-Alias git ...`;
- invalid state followed by a second root guard and direct Git;
- CMD `g^it` after an exact guard;
- existing repository routing surfaces remain valid after the documented fence splits.

Pass criteria:

- zero BLOCKER/HIGH findings from independent spec and execution verifiers;
- all retry RED cases observed failing for the intended missing behavior, then GREEN;
- complete Task 1 contract regression green;
- handoff, source count/snapshot, and schema catalog exact;
- Ruff, focused mypy, compileall, diff, LF, exact-root/index, allowlisted staging, and clean-worktree
  checks green;
- no MEDIUM waiver unless it has a human owner, evidence, rationale, expiry, and removal condition.

## 9. Required commands

Run from the exact worktree with Python 3.12:

```text
.venv\Scripts\python.exe tools/check_repo_root.py --expected-root .
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/contract/test_repo_root_guard.py tests/contract/test_handoff_package.py -q
.venv\Scripts\python.exe -B tools/verify_handoff.py
.venv\Scripts\python.exe -B tools/audit_source_data.py --check
.venv\Scripts\python.exe -B tools/extract_schema_catalog.py --check
.venv\Scripts\python.exe -m ruff format --check tools/verify_handoff.py tests/contract/test_handoff_package.py
.venv\Scripts\python.exe -m ruff check tools/verify_handoff.py tests/contract/test_handoff_package.py
.venv\Scripts\python.exe -m mypy tools/verify_handoff.py --follow-imports=skip --ignore-missing-imports
.venv\Scripts\python.exe -m compileall -q tools/verify_handoff.py tests/contract/test_handoff_package.py
```

## 10. Retry lifecycle

Retry Candidate 1 receives one independent spec review and one fresh-checkout execution review.
Technically valid findings may produce Retry Candidate 2 and one final Retry Candidate 3. If a
BLOCKER or HIGH remains after Retry Candidate 3, Task 1 returns to `BLOCKED`. No unbounded loop and
no automatic scope expansion are permitted.
