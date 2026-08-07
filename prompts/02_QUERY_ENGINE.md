# Codex Prompt 02 — Deterministic Query and Evidence Router

Use this prompt only when `docs/implementation/STATUS.md` selects a Phase 2 task and the Phase 1
gate is recorded green. Otherwise stop and follow the selected task's plan.

Read `AGENTS.md`, `docs/implementation/QUALITY_LOOP.md`, `STATUS.md`, the complete selected task,
and its QueryPlan, metric, evidence, and testing contracts. Run repository verification, freeze one
task brief, and follow the repository-owned TDD, fan-out, review, retry, Git, status, and reporting
gates.

Keep query execution deterministic and independent of FastAPI/HCX. Preserve `top_k_scope`, native
cross-product segments, allowlisted parameterized SQL, identity boundaries, state/time/metric/
currency policy, evidence, claim verification, and deterministic rendering from `AGENTS.md`. End
after the selected task.
