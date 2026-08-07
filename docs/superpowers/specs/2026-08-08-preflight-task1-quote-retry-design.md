# Preflight Task 1 Single-Quote Retry Design

**Status:** Concept approved by the owner on 2026-08-08; written-spec review pending

**Parent task:** Preflight Task 1 — exact Git-root/index guard and repository-owned quality loop

**Retry budget:** Exactly one behavior candidate; no automatic scope expansion

**Canonical brief:** The UTF-8 bytes of this file. Its SHA-256 is recorded in
`docs/implementation/STATUS.md` before test or production behavior changes begin.

## 1. Objective

Close the final cross-dialect history-mutation gap without adding a shell interpreter:

1. reject every single-quoted `git commit -m` message globally;
2. preserve the existing unquoted and double-quoted literal ASCII message forms;
3. pin CMD, BAT, and batch behavior with focused regressions;
4. pin blank-line neutrality with a positive regression; and
5. require one independent specification review and one fresh-checkout execution review.

The owner explicitly authorized this one-candidate retry after both final Candidate 3 verifiers
showed that POSIX `shlex` grouped `'safe message'` while real CMD split it into multiple arguments.
Those extra positional arguments may become Git commit pathspecs.

## 2. Selected design and alternatives

### Selected — globally reject single quotes

The one supported spaced-message form is matching double quotes. This is the smallest fail-closed
rule shared by Bash, PowerShell, CMD, BAT, and batch after the existing character allowlist rejects
variable expansion, substitution, escape syntax, operators, and globbing.

### Rejected — dialect-specific parsing

Passing the fence label into a second shell parser would enlarge interfaces, duplicate shell
semantics, and create new disagreement risks. The repository does not need dialect-specific
single-quote support.

### Rejected — forbid every quoted message

Allowing only unquoted messages would avoid parsing ambiguity but unnecessarily prohibit ordinary
multi-word checkpoint messages. Double quotes already provide one argument across the supported
fence dialects under the existing restricted character grammar.

## 3. Scope, base, and ownership

Base commit: `525312c78ae19e13ea5482b635f66f535f2dd8cc`

Branch: `codex/preflight-safety`

Externally selected worktree:
`C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`

Exact writable paths and writers:

- Coordinator `/root`:
  - `docs/superpowers/specs/2026-08-08-preflight-task1-quote-retry-design.md`
  - `docs/superpowers/plans/2026-08-08-preflight-task1-quote-retry.md`
  - `tools/verify_handoff.py`
  - `docs/implementation/QUALITY_LOOP.md`
  - `docs/implementation/STATUS.md`
  - `START_HERE.md`
  - `HANDOFF_PACKAGE_MANIFEST.md`
- Oracle writer `/root/candidate3_oracle`:
  - `tests/contract/test_handoff_package.py`

Spec verifier `/root/r3_spec_conformance` and execution verifier
`/root/r1_execution_verifier` are read-only and independent of the implementation. Only the
coordinator may stage, commit, change candidate state, or edit `STATUS.md`.

## 4. Frozen inputs and invariants

| Input | SHA-256 at base |
|---|---|
| `docs/implementation/QUALITY_LOOP.md` | `b0c97c5c26d4821eea699bf4a2315c10ceb0be067ecaffe119b14f6e82d37b93` |
| `docs/superpowers/specs/2026-08-07-preflight-task1-retry-design.md` | `8e018109d130af5428d657ebbc1f8fa06ff09ea6a97ffb710eec89bcf97ac3f5` |
| `docs/superpowers/plans/2026-08-07-preflight-task1-retry.md` | `309285bf6f2e51aa0cbc868041f8e9037abc4557578620a40798d0110548997d` |
| `tools/verify_handoff.py` | `b0d85454cc84e9d034e3fec4c4538bc4e003cfbf5017603cefd0e9f093d42938` |
| `tests/contract/test_handoff_package.py` | `f22991ccafde81e64a2f95979f2c299418fd0da9f95cde70ef3aeecc81c3a75e` |
| `source_material/input_manifest.json` | `8eb4ee0e0e7335081e208be0787eff65d52540debac434bb47b360b459d62fc4` |

Frozen completion expectations remain 145,393 source rows, snapshot `2026-07-11`, 207 schema
columns, nine official inputs, and 41,384,928 source bytes.

## 5. Exact interface contract

`classify_git_command(line)` remains the only supported-command classifier. No public signature,
enum member, read-only command, staging grammar, guard transition, or fence label changes.

The complete supported `git commit -m MESSAGE` message grammar becomes:

- unquoted: `[A-Za-z0-9][A-Za-z0-9._:-]*`; or
- double-quoted: `"[A-Za-z0-9][A-Za-z0-9 ._:/-]*"`.

Any single quote anywhere in the message expression is `UNSUPPORTED`. Empty messages, unmatched
or nested quotes, leading option-like punctuation, variables, percent/bang expansion, globbing,
brace/array/splat expansion, command substitution, escape syntax, and control operators remain
unsupported.

The existing clean-index guard → canonical add → staged name/status review → canonical commit
sequence remains mandatory. An unsupported single-quoted commit is reported by
`unsafe_git_context_lines`, `unguarded_git_block_lines`, and `unsafe_git_commit_lines` in CMD, BAT,
and batch executable fences.

## 6. Test contract

The oracle changes only `tests/contract/test_handoff_package.py` before production edits.

Required behavior RED:

- `classify_git_command("git commit -m 'safe message'")` is currently
  `GitCommandKind.HISTORY_MUTATION` but must become `UNSUPPORTED`;
- for each label `cmd`, `bat`, and `batch`, a fully guarded canonical staging/review workflow ending
  in `git commit -m 'safe message'` currently escapes all three public diagnostics but must be
  reported by all three.

Required baseline-positive and regression controls:

- an internal blank line after the exact read guard remains neutral and the following approved
  read-only Git command produces no context or unguarded violation;
- unquoted `git commit -m safe` remains `HISTORY_MUTATION`;
- double-quoted `git commit -m "safe message"` remains `HISTORY_MUTATION` and a fully guarded
  workflow remains clean in CMD, BAT, and batch fences;
- existing expansion-negative, post-guard invalidation, CommonMark, staging, and commit-workflow
  tests remain green.

The blank-line test is a positive characterization test, not RED evidence. Only the single-quote
cases authorize a production behavior change.

## 7. Minimal implementation

Change `_literal_commit_message_expression` so its quoted branch accepts only matching double
quotes. Do not introduce a fence-label parameter, shell-specific parser, new helper registry, or
new dependency. Update `QUALITY_LOOP.md` to say `unquoted or double-quoted literal ASCII`.

Register this brief and its implementation plan in `tools.verify_handoff.REQUIRED_FILES` and the
matching frozen initial-import blocks in `START_HERE.md` and `HANDOFF_PACKAGE_MANIFEST.md`. Those
are durable handoff updates, not new Git-command behavior.

## 8. Non-goals

- No additional Git command, option, alias, wrapper, executable spelling, quote form, or shell
  syntax becomes supported.
- No general Bash, PowerShell, CMD, BAT, batch, or CommonMark interpreter.
- No root-guard, state-machine, staging-path, commit-sequence, repository-selection, source-data,
  schema, prompt, API, HCX, deployment, GitHub, remote, tag, push, or release behavior change.
- No Preflight Task 2 work.
- No second behavior candidate within this retry.

## 9. Required verification

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

Also verify the exact brief hash, frozen input hashes, LF checkout, diff checks, exact root/index,
allowlisted staging, candidate cleanliness, and a fresh detached execution worktree.

## 10. Review and disposition

The single candidate receives exactly two independent final reviews:

1. a read-only specification review of every acceptance statement and documentation surface; and
2. a fresh-detached-checkout execution review that reruns all gates and harmless argv-boundary
   controls for single-quoted and double-quoted messages.

Pass requires both reviewers to report zero BLOCKER/HIGH and no unowned MEDIUM. A valid
BLOCKER/HIGH returns Task 1 to `BLOCKED`; no further correction is authorized. With both approvals,
the coordinator records Task 1 complete and selects Preflight Task 2 without beginning it in the
same session.
