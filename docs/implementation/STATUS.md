# Implementation Status

**Last updated:** 2026-08-07 — Preflight Task 1 Candidate 1 implemented; independent verification pending.

## Frozen baseline

- [x] Official task PDF included
- [x] Eight official workbooks included with ASCII filenames
- [x] Input checksums and audit baseline defined
- [x] Final architecture and domain contracts frozen
- [x] Machine-readable seed policies and JSON schemas included
- [x] TDD phase plans and Codex prompts included

## Preflight safety remediation

Plan: `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`

- [ ] Task 1: exact Git-root/index guard and repository-owned quality loop — Candidate 1; final
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

**Preflight Task 1, Candidate 1 verification.** Do not begin Preflight Task 2 until both independent
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
- Candidate 1 final spec and fresh-execution reviews: pending.
- Candidate 1 commit: pending.
