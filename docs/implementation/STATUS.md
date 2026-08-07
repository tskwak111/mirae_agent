# Implementation Status

**Last updated:** 2026-08-08 — Preflight Task 1 single-quote one-candidate implementation plan
frozen; oracle RED is the exact next step.

## Frozen baseline

- [x] Official task PDF included
- [x] Eight official workbooks included with ASCII filenames
- [x] Input checksums and audit baseline defined
- [x] Final architecture and domain contracts frozen
- [x] Machine-readable seed policies and JSON schemas included
- [x] TDD phase plans and Codex prompts included

## Preflight safety remediation

Plan: `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`

- [ ] Task 1: exact Git-root/index guard and repository-owned quality loop — single-quote
  one-candidate retry plan frozen; oracle RED pending
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

**Execute Task 1 of the frozen single-quote retry plan:** oracle
`/root/candidate3_oracle` changes only `tests/contract/test_handoff_package.py`, adds the exact
single-quote/CMD-family/blank-line/double-quote cases, and records the expected mixed RED. Do not
edit production behavior before that RED and do not begin Preflight Task 2.

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
- Candidate 3 commit: `891f2af07dcf252bb706c1931d7abf319ae68e76`.
- Fresh-execution review: PASS, 0 BLOCKER / 0 HIGH / 0 MEDIUM. Detached commit `891f2af` on
  Python 3.12.8 observed 121 passing Task 1 contracts in 20.72s after its one recorded temporary-
  directory infrastructure retry; handoff/source/schema, Ruff, focused mypy, compileall, LF,
  `git diff --check`, exact-root/clean-index, and clean-worktree checks passed.
- Independent final spec review: FAIL, 0 BLOCKER / 1 HIGH / 0 MEDIUM. The denylist-based Git
  classifier accepted both `git publish` (an unsupported configured alias that may perform arbitrary
  mutations) and `git fetch origin` (an unclassified repository mutation) under the weak guard.
  This violates the bare-Git/alias prohibition and the clean-index requirement for every mutation.
- Coordinator adversarial confirmation found a second HIGH trust-boundary class. After a valid
  guard, `$env:GIT_DIR=...` and `& Set-Location ..` change repository or working-directory context,
  yet `unguarded_git_block_lines` returned no violation for the following direct Git command.
  PowerShell execution confirmed that `& Set-Location ..` changes the process location. The same
  classifier also misses CMD caret-obfuscated `g^it` in a `cmd` fence.
- Final disposition: Candidate 3 does not meet the zero-BLOCKER/HIGH gate. No waiver is accepted.
  Under the frozen Candidate 1–3 budget, Task 1 is BLOCKED and Task 2 remains unauthorized until
  the owner explicitly approves a new bounded brief/retry cycle.

### 2026-08-07 — Preflight Task 1 bounded retry design

- Authorization: the owner explicitly approved a Task 1 redesign and a new Candidate 1–3 retry
  budget limited to Git command allowlisting and post-guard execution-context invalidation, then
  approved the presented closed-grammar/state-machine design.
- Canonical brief: `docs/superpowers/specs/2026-08-07-preflight-task1-retry-design.md` at SHA-256
  `0d271aa90df317ee470848aa603d8c61391d123c7bd7d3dac4d00f19f08a34d6`.
- Base: commit `94f0bfbbfd6034113c7f6dcb5927331f67f37675`, branch
  `codex/preflight-safety`, exact linked worktree
  `C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`.
- Scope: exact closed Git grammar, absorbing post-guard context state, CMD fence recognition,
  strict guarded-workflow fence routing, removal of the premature release-tag instruction, and
  only the documentation/test surfaces enumerated by the canonical brief.
- Ownership: coordinator `/root` owns every listed file except
  `tests/contract/test_handoff_package.py`, which is reserved for oracle writer
  `/root/retry_cycle_oracle`. All other agents are read-only; only the coordinator may stage,
  commit, or edit this status file.
- Frozen baseline observed before design edits: 121 Task 1 contracts passed in 12.79s; handoff
  reported 67 required files, nine official inputs, and 41,384,928 source bytes; source audit
  reported 145,393 rows at snapshot 2026-07-11; schema catalog reported 207 columns.
- Retry lifecycle: Retry Candidate 1–3 with one separately recorded infrastructure retry; zero
  BLOCKER/HIGH is mandatory and no automatic scope expansion is authorized.
- Written-spec approval: the owner directed `진행`; implementation plan commit `91ba9d3` followed
  approved design commit `00b9c86`. Behavior work then began with the independent oracle.

### 2026-08-07 — Preflight Task 1 Retry Candidate 1 implementation

- Scope and writers: coordinator `/root` alone changed production, routing, manifest, policy, and
  this status record. Oracle `/root/retry_cycle_oracle` changed only
  `tests/contract/test_handoff_package.py`. All other agents were read-only; only the coordinator
  may stage or commit.
- Interface RED: the focused oracle selection stopped at collection with
  `ImportError: cannot import name 'GitCommandKind'`. Minimal public enum/function stubs then
  exposed the intended behavior RED: 30 failed, 11 passed, 78 deselected. Failures covered every
  registered/unknown command classification, wrappers, raw stage operands, post-guard context,
  absorbing invalid state, and CMD caret obfuscation.
- Accepted adversarial corrections: raw quoted stage operands stay unsupported while a quoted
  commit message remains supported; a Bash `#` suffix cannot be erased by tokenization; direct
  `git-foo`/`git.*` executables fail closed. These are within the approved closed-grammar scope and
  intentionally tighten the implementation-plan sketch.
- Focused GREEN: classifier cases reached 19 passed; the complete new allowlist/context selection
  reached 41 passed; the legacy Git/CommonMark/commit selection reached 100 passed and then 101
  passed after the final classifier refactor. The two final-routing contracts passed 2/2.
- Category-surface RED/GREEN: `git-stage -- README.md` and `git.cmd commit -m unsafe` were centrally
  classified unsupported but initially escaped their stage/commit-specific reports (`2 failed,
  121 deselected`). Shared Git-like executable recognition closed both; the focused rerun passed
  2/2 without adding another supported command.
- Infrastructure record: default and sandbox-local pytest temporary directories hit the known
  Windows ACL failure. Those attempts are infrastructure diagnostics, not RED/GREEN evidence. The
  single authorized infrastructure retry used an approved checkout-local basetemp outside the
  sandbox and is now consumed.
- Full Candidate 1 local contract: Python 3.12.8 ran both Task 1 contract files with the approved
  checkout-local basetemp — 155 passed in 15.80s.
- Routing/policy: guard-plus-validation fences were split; the release-tag command was removed and
  deferred to a future tested clean-worktree gate; the retry design/plan were added to the required
  handoff and frozen literal import.
- Local gates: exact root PASS; handoff PASS with 69 required files, nine official inputs, and
  41,384,928 source bytes; source audit PASS with 145,393 rows at snapshot 2026-07-11; schema
  catalog PASS with 207 columns; Ruff format/check PASS; focused mypy PASS; compileall PASS.
- Verification orchestration note: one parallel wrapper returned no component results when source
  audit contention reached its 60.7-second command limit. No PASS is claimed from that wrapper.
  Fresh split commands all exited zero; the isolated source audit completed in 45.5 seconds. This
  did not create another behavior candidate.
- Candidate commit: `a90db20173724215c1d514ef5764bbe5f8cbf18b`.
- Fresh-execution review: APPROVE, 0 BLOCKER / 0 HIGH / 0 MEDIUM / 0 LOW. The detached commit
  reproduced 155 passing contracts, every frozen handoff/source/schema invariant, Ruff, focused
  mypy, compileall, 94-file LF/binary state, exact root, and clean candidate/detached worktrees.
- Independent spec/security review: FAIL, 0 BLOCKER / 3 HIGH / 1 MEDIUM. Valid list-to-blockquote
  CommonMark fences bypassed scanning; CMD `# & cd ..` armed a false exact guard; Bash brace
  expansion injected `--all` through an accepted commit message. A read-only guard mutation also
  failed to make `INVALID` absorbing. All four were reproduced; no waiver was accepted.
- Disposition: Candidate 1 failed the zero-HIGH gate. Candidate 2 is authorized only for these four
  corrections; Task 2 remains unauthorized.

### 2026-08-07 — Preflight Task 1 Retry Candidate 2 implementation

- Oracle RED: two valid list-to-blockquote CommonMark variants, the CMD hash/control-operator
  guard, the brace-expanded commit, and the post-mutation absorbing-state case produced 5 failed,
  123 deselected. The oracle modified only `tests/contract/test_handoff_package.py`.
- Coordinator reproduction: all three HIGH inputs returned empty public diagnostics against
  Candidate 1. `cmd.exe` executed both sides of `# &`; Git Bash expanded `{safe,--all}` to
  `safe --all`. These were behavior findings, not review-style preferences.
- Corrections: root guards now match one of two exact raw lines; commit messages must be
  non-expanding literal/quoted ASCII expressions; CommonMark opener/container removal is stable
  across list/blockquote order; a mutation under the read-only guard now enters absorbing
  `INVALID`. No Git command was added to the supported grammar.
- Focused GREEN: each correction passed alone; the combined Candidate 2 selection passed 5/5.
  Existing Git/CommonMark regressions passed 106 tests with 22 deselections.
- Full local contract: Python 3.12.8 ran both Task 1 contract files with the approved
  checkout-local basetemp — final rerun 160 passed in 13.06s.
- Candidate 2 commit: `2dd7da5a23227918124abd4748baf921c93d8860`.
- Fresh-execution review: APPROVE, 0 BLOCKER / 0 HIGH / 0 MEDIUM / 0 LOW. The detached checkout
  reproduced 160 passing Task 1 contracts, all frozen handoff/source/schema invariants, Ruff,
  focused mypy, compileall, LF/diff checks, exact roots, and clean candidate/verifier worktrees.
- Independent specification review: REJECT, 0 BLOCKER / 2 HIGH / 0 MEDIUM / 0 LOW. A standalone
  `# & cd ..` after the guard in a CMD fence changed the real process directory while both public
  diagnostics returned empty. Separately, Candidate 2's non-expanding literal ASCII commit-message
  grammar safely narrowed the approved one-token sketch without first recording the changed
  acceptance contract.
- Disposition: Candidate 2 fails the zero-HIGH gate. No waiver is accepted. The final Candidate 3
  is limited to the standalone non-empty-line context correction and recording the already-tested
  literal message grammar; Task 2 remains unauthorized.

### 2026-08-07 — Preflight Task 1 Retry Candidate 3 frozen amendment

- Base: `2dd7da5a23227918124abd4748baf921c93d8860`; same branch, externally selected worktree,
  writers, writable paths, non-goals, gates, and single remaining candidate budget.
- Revised canonical brief:
  `docs/superpowers/specs/2026-08-07-preflight-task1-retry-design.md` at SHA-256
  `8e018109d130af5428d657ebbc1f8fa06ff09ea6a97ffb710eec89bcf97ac3f5`.
- Behavior contract: only a blank line is context-neutral after the exact root guard. Every
  non-empty line, including apparent comment syntax whose meaning differs by shell dialect,
  invalidates the guarded context unless it is an approved Git command.
- Clarified interface: commit messages use the Candidate 2 non-expanding literal ASCII grammar;
  no new Git command, wrapper, option, expansion form, or shell interpretation is authorized.
- Required RED: a CMD fenced block containing exact guard, standalone `# & cd ..`, and direct Git
  must initially escape both public diagnostics. The oracle alone owns the test edit; the
  coordinator alone owns production/docs/status and Git actions.
- Frozen-brief checkpoint: `1f28305e1c188c1b399a46d7accff6b209dc6c5f`.
- Oracle RED: the one new focused test failed as intended (`1 failed, 128 deselected in 0.44s`)
  because `unsafe_git_context_lines` returned empty instead of line 3; the later unguarded-Git
  assertion for line 4 was also frozen in the test. The oracle changed only
  `tests/contract/test_handoff_package.py`; its Ruff format/check and diff check passed.
- Minimal GREEN: `_is_executable_line` now exempts only blank lines. The focused rerun passed
  (`1 passed, 128 deselected in 0.17s`) and the complete Task 1 contract rerun passed
  (`161 passed in 12.90s`).
- Local gates: handoff PASS with 69 required files, nine official inputs, and 41,384,928 source
  bytes; source audit PASS with 145,393 rows at snapshot 2026-07-11; schema catalog PASS with 207
  columns; Ruff format/check, focused mypy, compileall, and exact brief-hash checks passed.
- Behavior checkpoint: `68b6d9ed979c5364132fc713dd34117c2b589971`.
- Pre-review normative audit: the coordinator found that `QUALITY_LOOP.md` still said
  `blank/comment lines` while the revised canonical brief, plan, implementation, and oracle test
  required blank lines only. Both reviews of the stale checkpoint were interrupted; no verdict is
  claimed from them. The policy wording is aligned without another behavior change.
- Final Candidate 3 composite checkpoint:
  `61ea58ea698896000de75918e2db40102237cdc8`.
- Fresh-execution review: FAIL, 0 BLOCKER / 1 HIGH / 0 MEDIUM / 0 LOW. In a harmless CMD argv
  inspection, `'security: review pass'` became three arguments while the verifier classified the
  corresponding `git commit -m` line as `HISTORY_MUTATION` and all three public diagnostics were
  empty. The extra positional arguments can become commit pathspecs. The same detached review
  reproduced 161 passing contracts, handoff 69/9/41,384,928, source audit 145,393 rows at
  2026-07-11, schema 207 columns, Ruff, focused mypy, compileall, diff/EOL, exact roots, and clean
  candidate/verifier worktrees.
- Independent specification review: REJECT, 0 BLOCKER / 1 HIGH / 1 MEDIUM / 1 LOW. It independently
  reproduced the CMD/BAT single-quote split and the missing diagnostics. Its MEDIUM was this file's
  stale Candidate 2 routing, corrected by this disposition-only update. Its LOW was the absence of
  a committed positive regression for blank-line neutrality; the behavior passed an in-memory
  control but is not pinned by a test.
- Accepted final HIGH: the canonical brief permits single-quoted spaced ASCII messages, while
  supported CMD/BAT fences do not group single quotes. POSIX `shlex` therefore proves a different
  argv from the real shell, violating the closed cross-dialect one-message and task-owned staging
  contracts. No waiver is accepted.
- Final disposition: Candidate 3 does not meet the zero-BLOCKER/HIGH gate. The approved three
  candidates are exhausted, so Task 1 returns to `BLOCKED`; Task 2 remains unauthorized. No further
  implementation or oracle edit may occur until the owner explicitly approves a new bounded brief.

### 2026-08-08 — Preflight Task 1 single-quote retry written design

- Authorization: the owner explicitly approved one new bounded retry limited to globally banning
  single-quoted commit messages, adding CMD/BAT regressions and a blank-line positive regression,
  and requiring two independent final verifiers.
- Base: `525312c78ae19e13ea5482b635f66f535f2dd8cc`, branch `codex/preflight-safety`, exact linked
  worktree `C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`.
- Canonical brief:
  `docs/superpowers/specs/2026-08-08-preflight-task1-quote-retry-design.md` at SHA-256
  `26eab093d601a82837e5e38661430d37c59c8b183d7ce6ae470fb655ef0cfb1b`.
- Selected design: accept only unquoted or double-quoted literal ASCII commit messages. A
  dialect-specific parser was rejected as unnecessary new complexity; forbidding all quoted
  messages was rejected because it would remove safe multi-word checkpoints.
- Frozen ownership: oracle `/root/candidate3_oracle` alone owns
  `tests/contract/test_handoff_package.py`; coordinator `/root` owns the brief, forthcoming plan,
  verifier/policy/routing/status files, and every Git action. Both final verifiers are read-only.
- Baseline evidence before the written design: exact root and clean index PASS on the expected
  branch; handoff PASS with 69 required files, nine official inputs, and 41,384,928 source bytes;
  source audit PASS with 145,393 rows at snapshot 2026-07-11.
- No test or production behavior changed. The next gate is owner review of the committed written
  spec; implementation planning remains unauthorized until that review is approved.
- Written-spec review: the owner explicitly replied `written spec 승인` after design checkpoint
  `80b192a4d54720b3cb339b2f7b32ccf6a979a3f2`.
- Frozen implementation plan:
  `docs/superpowers/plans/2026-08-08-preflight-task1-quote-retry.md` at SHA-256
  `bea4670cfd5bbf46f88e839c07e0d395f0940b2754876a0cb5e5b0aaedfe53dd`.
- Plan self-review: every brief requirement maps to an explicit task; placeholder scan passed;
  function names and expected diagnostics match the current interfaces; handoff verification
  passed with 69 required files before durable registration of the new spec/plan.
- Execution method: the owner's existing fan-out requirement selects subagent-driven execution.
  Writers remain sequential; the two read-only final verifiers run in parallel only after the one
  candidate is committed.
- No test or production behavior changed while writing the plan. The next authorized action is the
  independent oracle RED in plan Task 1.
