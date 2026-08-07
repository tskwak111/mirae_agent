# FinProof Codex Handoff Package Manifest

## Give these to Codex

The preferred delivery is the whole repository. The minimum required set is:

1. `AGENTS.md` — non-negotiable engineering and competition contract.
2. `START_HERE.md` — exact startup order.
3. `CODEX_MASTER_PROMPT.md` — first-session metaprompt.
4. `CODEX_RESUME_PROMPT.md` — later-session continuation prompt.
5. `CODEX_REVIEW_PROMPT.md` — fresh-context independent audit prompt.
6. `docs/` — frozen design, official traceability, policies, risks, validation report, definition of done, phase gates, and implementation plans.
7. `config/` — machine-readable data, state, quality, metric, planner, and answer policies.
8. `schemas/` — strict local QueryPlan, HCX-provider-safe QueryPlan, evidence, trace, API, quality-issue, artifact, and golden-case contracts.
9. `source_material/` — official task PDF, eight immutable workbooks, SHA-256 manifest, and extracted schema catalog.
10. `tools/` and `tests/contracts/` — source audit and package verification baselines.
11. `pyproject.toml`, `Makefile`, CI, and environment templates — reproducible engineering environment. Generate and commit `uv.lock` during the first network-enabled bootstrap.
12. `prompts/` — phase-specific and review prompts.

Do not give Codex only a prose summary or only the source workbooks. The contracts, registries, tests, and phase plans are what prevent design drift.

## First command sequence

```bash
cat START_HERE.md
cat AGENTS.md
python tools/verify_handoff.py
python tools/audit_source_data.py --check
uv sync --all-groups
uv run pytest -q
```

Then paste `CODEX_MASTER_PROMPT.md` and let Codex execute only the first incomplete task in `docs/implementation/STATUS.md`.

## Session discipline

- One independently reviewable task per implementation session.
- A fresh review context after every phase.
- `CODEX_RESUME_PROMPT.md` for continuation; never rely on chat memory.
- Status file and Git commits are the durable record.
- No phase advancement until its gate passes.
