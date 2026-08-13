# Start Here — Codex Handoff

## 1. Do not start by coding

Read, in order:

1. `AGENTS.md`
2. `docs/00_PROJECT_CHARTER.md`
3. `docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md`
4. `docs/02_FINAL_FROZEN_DESIGN.md`
5. `docs/03_DATA_AUDIT_BASELINE.md`
6. `docs/04_DATA_AND_DOMAIN_CONTRACTS.md`
7. `docs/05_QUERYPLAN_AND_API_CONTRACT.md`
8. `docs/06_METRIC_REGISTRY_POLICY.md`
9. `docs/07_TESTING_AND_EVALUATION.md`
10. `docs/implementation/STATUS.md`
11. the first incomplete phase plan under `docs/superpowers/plans/`

## 2. Verify the package

```bash
python3 tools/verify_handoff.py
python3 tools/audit_source_data.py --check
```

These standard-library entry points provide the pre-install integrity check. Both must pass before source-derived implementation work begins. A checksum or audit mismatch is a stop condition, not an invitation to update expected numbers.

## 3. Initialize Git safely

If this directory is not already the organizer’s private repository:

```bash
git init
git add .
git commit -m "chore: add FinProof implementation handoff"
```

When using Codex for implementation, create an isolated branch/worktree per phase when practical. Do not make submission-freeze changes on `main` without review.

## 4. Bootstrap dependencies

```bash
uv sync --frozen --all-groups
uv run python tools/verify_handoff.py
uv run python tools/audit_source_data.py --check
```

The macOS bootstrap generated and committed `uv.lock` with Python 3.12, so installation must remain frozen. `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, and `.env.example` were not present in the transferred handoff; Phase 1 Task 1 must add and test them before installing hooks or claiming CI bootstrap completion.

## 5. Start Codex

Paste the full contents of `CODEX_MASTER_PROMPT.md` into the first Codex session. Do not replace it with “build this project.” The prompt intentionally forces source verification, phase boundaries, TDD, review gates, and status updates.

For later sessions, use `CODEX_RESUME_PROMPT.md`. For an independent final audit, use `CODEX_REVIEW_PROMPT.md` in a fresh context.

## 6. Phase order

1. Repository and data foundation
2. Deterministic query/evidence engine
3. HyperCLOVA X planner and evaluation API
4. Evaluation, hardening, and release freeze

Do not start UI, GraphDB, multi-agent orchestration, live external data, portfolio optimization, or personalized recommendations before all P0 phase gates pass.

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

## 8. First task

The first incomplete item in `docs/implementation/STATUS.md` is authoritative. At package creation, it is Phase 1, Task 1: bootstrap the repository under TDD and make the handoff/source checks part of CI.
