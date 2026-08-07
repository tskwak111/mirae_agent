# Codex Prompt 03 — HyperCLOVA X and API Router

Use this prompt only when `docs/implementation/STATUS.md` selects a Phase 3 task and the Phase 2
gate is recorded green. Otherwise stop and follow the selected task's plan.

Read `AGENTS.md`, `docs/implementation/QUALITY_LOOP.md`, `STATUS.md`, the complete selected task,
and the QueryPlan/API/security contracts. Run repository verification, freeze one task brief, and
follow the repository-owned TDD, fan-out, review, retry, Git, status, and reporting gates.

HyperCLOVA X is the only runtime/evaluation generative model. Enforce provider-safe output plus
strict local/semantic validation, bounded repair/fallback, exact `GET /answer` five-string schema,
deterministic default rendering, verified-fact-only wording, safe `think_trace`, and bounded
operational controls. End after the selected task.
