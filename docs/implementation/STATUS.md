# Implementation Status

**Last updated:** 2026-08-07 — Preflight Task 1 Candidate 3 implemented; independent final verification pending.

## Frozen baseline

- [x] Official task PDF included
- [x] Eight official workbooks included with ASCII filenames
- [x] Input checksums and audit baseline defined
- [x] Final architecture and domain contracts frozen
- [x] Machine-readable seed policies and JSON schemas included
- [x] TDD phase plans and Codex prompts included

## Preflight safety remediation

Plan: `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`

- [ ] Task 1: exact Git-root/index guard and repository-owned quality loop — Candidate 3; final
  spec/execution reviews pending
- [ ] Task 2: separate official instruction authority from official data trust
- [ ] Task 3: independent typed evaluation, sealed holdout, coverage, and aggregate evidence
- [ ] Task 4: non-self-referential release provenance and presentation claim evidence
- [ ] Task 5: Python 3.12 lock, CI/quality gates, HCX capability probe, and final Preflight audit
- [ ] Preflight gate passed

## Phase 1 — Repository and data foundation

Plan: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`

- [ ] Task 1: bootstrap settings, version bundle, CLI, and handoff/source checks in tests/CI
- [ ] Task 2: implement source manifest and streaming workbook reader with row lineage
- [ ] Task 3: normalize domestic bonds and domestic listed products
- [ ] Task 4: normalize overseas listed products and public funds with quarantine
- [ ] Task 5: build Parquet/DuckDB artifacts, exact links, quality report, and reproducibility check
- [ ] Phase 1 gate passed

## Phase 2 — Deterministic query, policy, evidence, and answer engine

Plan: `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md`

- [ ] Task 1: domain contracts and registry loaders
- [ ] Task 2: entity resolution and exact cross-source links
- [ ] Task 3: QueryPlan semantic validator and allowlisted SQL compiler
- [ ] Task 4: repositories/executor and differential reference
- [ ] Task 5: state, metric, comparability, and conditional dual-lens policy
- [ ] Task 6: evidence, claim verifier, deterministic Korean renderer, and core service
- [ ] Phase 2 gate passed

## Phase 3 — HyperCLOVA X planner and evaluation API

Plan: `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md`

- [ ] Task 1: HCX client and recorded contract fixtures
- [ ] Task 2: structured/strict JSON planner, repair, and rule fallback
- [ ] Task 3: API application, exact `/answer`, health/readiness/version, and safe errors
- [ ] Task 4: bounded timeout/retry/concurrency/cache and structured observability
- [ ] Task 5: Docker/reproduction and end-to-end API tests
- [ ] Phase 3 gate passed

## Phase 4 — Evaluation, hardening, proposal evidence, and release

Plan: `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`

- [ ] Task 1: canonical golden set and scoring harness
- [ ] Task 2: paraphrase, metamorphic, differential, quality, and adversarial suites
- [ ] Task 3: ablation and latency/load/resilience/soak measurement
- [ ] Task 4: competition compliance and independent review closure
- [ ] Task 5: clean-room reproduction, immutable release manifest, and submission freeze
- [ ] Phase 4 gate passed

## Current next task

**Preflight Task 1, Candidate 3 verification.** Do not begin Preflight Task 2 until both independent
verifiers approve the current candidate with zero BLOCKER/HIGH findings and the Task 1 gate is
recorded.

## Handoff validation record — not production implementation

Observed on 2026-08-07:

- `python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs.
- `python tools/audit_source_data.py --check` — PASS: 145,393 source rows, snapshot 2026-07-11.
- `python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `pytest -q` — PASS: 7 handoff contract tests.
- `python -m compileall -q src tools tests` — PASS.
- `python -m tools.verify_handoff` — PASS; handoff tools are importable as modules as well as executable scripts.
- JSON/YAML parse check — PASS: 8 schemas and 8 policy/config files.
- `uv.lock` is not included. A real `uv lock` attempt failed because the artifact environment could not resolve the package registry/Python download host. The first network-enabled bootstrap must resolve dependencies, generate and commit the lock file, then change CI installation to `uv sync --frozen --all-groups`; never hand-author a lock file.
- Dependency metadata was cross-checked before handoff; notably the Polars lower bound was corrected to the published `1.43.0` release. Ruff and mypy were not available in the artifact environment and remain Phase 1 bootstrap checks.

See `docs/13_HANDOFF_VALIDATION_REPORT.md`. These checks validate the handoff package, not the production system.

## Work log

### 2026-08-07 — Preflight Task 1 Candidate 1

- Authorization: owner approved the Preflight design and directed implementation. No additional
  organizer notice was supplied; the trust-plane record remains Preflight Task 2.
- Frozen basis: design commit `b6f6dfc`, implementation-plan commit `1565c34`, base commit
  `1565c34`, branch `codex/preflight-safety`, linked worktree `.worktrees/preflight-safety`.
  Because `QUALITY_LOOP.md` is created by this bootstrap task, those reviewed commits serve as the
  legacy frozen brief; future tasks require the canonical SHA-256 task brief before edits.
- Writers: coordinator only for all modified files. Parallel specialists were read-only.
- RED 1: `python -m pytest -p no:cacheprovider tests/contract/test_repo_root_guard.py -q` failed
  during collection only with `ModuleNotFoundError: tools.check_repo_root`.
- Infrastructure note: the unsupported Python 3.14 runner could not create pytest temp locks under
  sandbox ACLs. A project-local Python 3.12.8 environment with pytest 9.1.1 was created; this was
  infrastructure evidence, not behavioral RED.
- GREEN 1: Python 3.12 root/ancestor/missing/CLI/Unicode/linked-worktree/environment tests reached
  12 passed before adversarial expansion.
- RED 2: clean-index and Markdown workflow contracts failed at collection because
  `ensure_clean_index`, `unguarded_git_block_lines`, `unsafe_git_commit_lines`, and
  `unsafe_git_stage_lines` did not exist.
- Adversarial RED: 19 focused failures demonstrated staging variants, CommonMark fence evasion,
  weak mutation guards, combined auto-staging commit flags, and missing staged-diff review.
- GREEN 2: supported Python 3.12 Candidate 1 contract command — 73 passed in 14.37s, including 25
  root/index/linked-worktree cases and the complete handoff/Markdown workflow suite.
- Static repository gate: `python -B tools/verify_handoff.py` — PASS after routing/plan repair:
  66 required files, 9 official inputs, 41,384,928 source bytes.
- Source invariants: `tools/audit_source_data.py --check` — PASS, 145,393 rows and snapshot
  2026-07-11; `tools/extract_schema_catalog.py --check` — PASS, 207 columns.
- Focused style: Ruff initially reported four files requiring format and 25 lint findings. After
  targeted corrections, Ruff check and format check passed for all four modified Python files.
- Strict typing: focused mypy passed for both modified tool modules with skipped dependency
  traversal. The four-file/global probe remains blocked by previously recorded bootstrap debt in
  imported audit/schema modules and untyped pytest decorators. Full strict typing remains assigned
  to Preflight Task 5; Task 1 does not claim the global gate.
- Accepted oracle/security findings: bind default CWD, use same-file semantics, reject Git
  repository/index/config injection variables, test Unicode and real linked worktrees, wrap launch
  and timeout errors, use a cached-diff clean-index gate, parse CommonMark fences fail-closed, accept
  only canonical literal staging, require root/clean-index first, forbid auto-staging commits, and
  require observed staged name/status review.
- Accepted prompt-contract findings: make `QUALITY_LOOP.md` the sole orchestration authority; route
  `AGENTS.md`, README/startup/Codex/phase/review prompts and every plan through one `STATUS.md` task;
  root-guard all Git blocks; add canonical staging to all 21 phase commit blocks; repair this
  Preflight plan's own commit blocks.
- Candidate 1 commit: `6dc86056bcc28429800bbc68af254b3a6067ec73`.
- Candidate 1 final spec review: FAIL, 0 BLOCKER / 4 HIGH / 1 MEDIUM. Findings covered
  explicit-CWD equality, config/discovery overrides, noncanonical index mutations, commit-time
  staging, CommonMark/container and executable-path bypasses, non-task-owned phase staging, and
  unresolved initial import.
- Candidate 1 fresh-execution review: FAIL, 0 BLOCKER / 5 HIGH. A detached checkout reproduced
  73 passing contracts, source/schema/handoff invariants, Ruff lint, and focused mypy, but failed
  Ruff format on all four Python files and reproduced explicit-CWD, intent-to-add, commit-path,
  interactive/patch, `git -C..`, and PowerShell-escape bypasses.

### 2026-08-07 — Preflight Task 1 Candidate 2

- Oracle writer changed only the two contract-test files; coordinator changed implementation,
  repository policy, routing docs, and plans. Mapping/reviewer agents remained read-only.
- RED: the fresh Candidate 2 contract run produced 24 behavioral failures and 71 passes. The
  failures covered exact explicit CWD, seven config/discovery variables, missing-repository
  isolation, intent-to-add, raw/path-qualified/escaped Git commands, directory-stack changes,
  blockquoted fences, strict commit grammar, post-review index mutation, and LF checkout policy.
- RED: the new plan/evidence/import contract first failed at import because
  `plan_task_staging_violations` did not exist, then exposed 21 phase checkpoint mismatches, the
  ignored JSON evidence path, and absent frozen initial-import blocks.
- GREEN: `tests/contract/test_repo_root_guard.py` — 32 passed; root and clean-index behavior now
  rejects every selected override and intent-to-add state.
- GREEN: `tests/contract/test_handoff_package.py` reached 63 passed after Git/CommonMark/commit/LF
  repair. Subsequent semantic-plan and parser-hardening tests expanded the combined Task 1 suite.
- GREEN: combined supported-Python command — 102 passed in 12.20s with a unique checkout-local
  `--basetemp` under the approved Windows ACL retry.
- Plan repair: all 21 Phase 1-4 checkpoints now stage exactly the task's declared literal files;
  generated JSON evidence has frozen names and narrow `.gitignore` exceptions. Phase 1 now names
  both source-audit and quality-summary reports; Phase 4 names canonical, robustness, ablation,
  load, soak, final-canonical, and release-manifest evidence.
- Import repair: `START_HERE.md` and `HANDOFF_PACKAGE_MANIFEST.md` carry identical literal baseline
  import commands. Missing/ancestor repositories remain stop conditions; no agent receives
  authority to improvise the import.
- Candidate 2 commit: `76f5ec42471e49c0b3f7c81a6e3bad91acf31b20`.
- Candidate 2 fresh-execution review: PASS within the Task 1 execution scope, 0 BLOCKER / 0 HIGH.
  From a detached checkout it observed 102 passing contracts, LF checkout state, handoff/source/
  schema invariants, focused Ruff and mypy, compileall, a clean diff, and a clean worktree after the
  single recorded Windows ACL retry.
- Candidate 2 independent security/spec review rejected the candidate with two confirmed HIGH
  trust-boundary classes: non-bare or continuation-split Git commands and chained mutations were
  not fail-closed, and valid CommonMark list-contained shell fences were not scanned. No waiver was
  accepted.

### 2026-08-07 — Preflight Task 1 Candidate 3

- Oracle ownership: the independent oracle changed only `tests/contract/test_handoff_package.py`;
  the coordinator alone changed `tools/verify_handoff.py` and this status record.
- RED 1: the focused oracle command produced 12 failures, 5 passes, and 70 deselections. Failures
  covered Bash `g\\it`, adjacent quoted `git`, uppercase PowerShell `GIT`, a pipe before a second
  Git mutation, Bash/PowerShell continuation splits, bullet/ordered/blockquote-list fences, a list
  fence close boundary, and non-bare commit spellings.
- GREEN 1: after fail-closed executable, chaining, continuation, and CommonMark-container handling,
  all 17 oracle cases passed with 70 deselections.
- RED 2: a coordinator-authored adversarial extension split `git` over three physical lines; both
  Bash and PowerShell cases failed as expected (`2 failed, 87 deselected`).
- GREEN 2: continuation folding was generalized across the entire chain. The expanded targeted run
  passed all 19 cases with 70 deselections.
- Regression: the combined root/handoff Task 1 command passed 121 tests in 12.38s on Python 3.12.8
  after the one recorded Windows sandbox ACL retry. The first run's `WinError 5` occurred only in
  pytest temporary-directory setup/cleanup and is not claimed as behavioral evidence.
- Focused quality: Ruff reformatted only `tools/verify_handoff.py`; format check and lint then
  passed for both changed Python files. Focused mypy passed for `tools/verify_handoff.py` with the
  same explicit dependency traversal settings recorded for Candidate 2.
- Candidate 3 commit: pending final local verification.
- Final independent spec and fresh-execution reviews: pending. No BLOCKER/HIGH waiver is permitted.
