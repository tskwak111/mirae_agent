# FinProof Codex Handoff Package Manifest

## Give these to Codex

The preferred delivery is the whole repository. The minimum required set is:

1. `AGENTS.md` — non-negotiable engineering and competition contract.
2. `START_HERE.md` — exact startup order.
3. `docs/implementation/QUALITY_LOOP.md` — normative task, fan-out, TDD, review, and Git contract.
4. `CODEX_MASTER_PROMPT.md` — first-session router.
5. `CODEX_RESUME_PROMPT.md` — later-session continuation router.
6. `CODEX_REVIEW_PROMPT.md` — fresh-context independent audit router.
7. `docs/` — frozen design, official traceability, policies, risks, validation report, definition of done, phase gates, and implementation plans.
8. `config/` — machine-readable data, state, quality, metric, planner, and answer policies.
9. `schemas/` — strict local QueryPlan, HCX-provider-safe QueryPlan, evidence, trace, API, quality-issue, artifact, and golden-case contracts.
10. `source_material/` — official task PDF, eight immutable workbooks, SHA-256 manifest, and extracted schema catalog.
11. `tools/` and `tests/contracts/` — repository guard, source audit, and verification baselines.
12. `pyproject.toml`, `Makefile`, CI, and environment templates — reproducible engineering environment. Generate and commit `uv.lock` during the first network-enabled bootstrap.
13. `prompts/` — task-routing and independent-review prompts.
14. `tools/check_repo_root.py`, `tests/contract/test_repo_root_guard.py`, and the dated Preflight
    design/plan — executable repository-boundary protection and its remediation record.

Do not give Codex only a prose summary or only the source workbooks. The contracts, registries, tests, and phase plans are what prevent design drift.

## First command sequence

```bash
cat START_HERE.md
cat AGENTS.md
cat docs/implementation/QUALITY_LOOP.md
python tools/check_repo_root.py --expected-root .
python tools/verify_handoff.py
python tools/audit_source_data.py --check
uv sync --all-groups
uv run pytest -q
```

Then paste `CODEX_MASTER_PROMPT.md` and let Codex execute only the task selected in
`docs/implementation/STATUS.md`.

## Session discipline

- `docs/implementation/QUALITY_LOOP.md` governs task scope, fan-out, role separation, retries,
  staging, verification, and durable handoff.
- Exactly one selected `STATUS.md` task per session; phase prompts cannot select work themselves.
- Use `CODEX_RESUME_PROMPT.md` for continuation and a fresh verifier context for every candidate.
- `STATUS.md` and allowlisted Git commits are the durable record; phase gates remain mandatory.
