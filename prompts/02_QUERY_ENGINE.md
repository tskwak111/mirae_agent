# Codex Prompt 02 — Deterministic Query and Evidence Engine

Implement the first incomplete task in `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md` only. Phase 1 must already have passed its gate.

Read `AGENTS.md`, the frozen design, domain contracts, QueryPlan/API contract, metric registry policy, testing strategy, current status, and the full Phase 2 plan. Run repository verification before editing.

Use strict TDD. Keep all domain logic independent of FastAPI and HCX. Validate QueryPlans semantically; require `top_k_scope`; decompose heterogeneous `result_grain=product` plans into native `ExecutionBundle` segments; compile only allowlisted fields/operators to parameterized SQL per segment. Preserve ETF/ETN separation, fund grain, snapshot time, state rules, metric-specific zero/tie policies, currency/period comparability, exact identity links, evidence lineage, and deterministic rendering. Every numeric/comparative claim must be verifiable. Never add free-form Text-to-SQL or fuzzy automatic merge.

End after one independently reviewable task. Run focused and relevant suites, update status with observed results, commit, and report the exact next task.
