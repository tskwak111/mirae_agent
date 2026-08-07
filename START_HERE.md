# Start Here — Codex Handoff

## 1. Do not start by coding

Read, in order:

1. `AGENTS.md`
2. `docs/implementation/QUALITY_LOOP.md`
3. `docs/00_PROJECT_CHARTER.md`
4. `docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md`
5. `docs/02_FINAL_FROZEN_DESIGN.md`
6. `docs/03_DATA_AUDIT_BASELINE.md`
7. `docs/04_DATA_AND_DOMAIN_CONTRACTS.md`
8. `docs/05_QUERYPLAN_AND_API_CONTRACT.md`
9. `docs/06_METRIC_REGISTRY_POLICY.md`
10. `docs/07_TESTING_AND_EVALUATION.md`
11. `docs/implementation/STATUS.md`
12. the complete plan section for the one task selected by `STATUS.md`

## 2. Verify the package

```bash
python tools/check_repo_root.py --expected-root .
python tools/verify_handoff.py
python tools/audit_source_data.py --check
```

Both must pass before source-derived implementation work begins. A checksum or audit mismatch is a stop condition, not an invitation to update expected numbers.

## 3. Verify the repository boundary

This package must already be an exact project repository before an agent works in it:

```powershell
python tools/check_repo_root.py --expected-root .
git status --short
git branch --show-current
git log -3 --oneline
```

If the guard reports a missing repository, an ancestor repository, another worktree, or a
repository-selection environment variable, stop. Do not run `git init` or stage from that state.
A human/coordinator must establish the private project repository at the exact directory, import
only the paths listed in `HANDOFF_PACKAGE_MANIFEST.md`, and then rerun the guard. Never perform a
broad initial import. Use an isolated `codex/` branch or linked worktree for each selected task.

## 4. Bootstrap dependencies

```bash
uv sync --all-groups
uv run pre-commit install
```

The handoff intentionally does not fabricate a lock file: its creation environment had no registry access. Generate and commit `uv.lock` in the first network-enabled bootstrap, change CI to `uv sync --frozen --all-groups`, and use frozen sync afterward.

## 5. Start Codex

Paste the full contents of `CODEX_MASTER_PROMPT.md` into the first Codex session. Do not replace it with “build this project.” The prompt intentionally forces source verification, phase boundaries, TDD, review gates, and status updates.

For later sessions, use `CODEX_RESUME_PROMPT.md`. For an independent final audit, use `CODEX_REVIEW_PROMPT.md` in a fresh context.

## 6. Phase order

1. Repository and data foundation
2. Deterministic query/evidence engine
3. HyperCLOVA X planner and evaluation API
4. Evaluation, hardening, and release freeze

Do not start UI, GraphDB, runtime/product multi-agent architecture, live external data, portfolio
optimization, or personalized recommendations before all P0 phase gates pass. Safe development
fan-out is governed separately by `QUALITY_LOOP.md`.

## 7. Human review gates

A human should inspect after every phase:

- source fidelity and data policy changes
- public-fund grain behavior
- state/eligibility semantics
- metric zero/tie/currency behavior
- generated SQL allowlists
- evidence coverage
- exact API schema
- competition compliance and LLM dependencies

## 8. Current task

The single task named under `Current next task` in `docs/implementation/STATUS.md` is authoritative.
Do not infer a phase-local task from a prompt, plan filename, or remaining context.
