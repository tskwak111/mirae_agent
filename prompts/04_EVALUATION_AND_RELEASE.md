# Codex Prompt 04 — Evaluation, Hardening, and Release

Implement the first incomplete task in `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md` only. Phases 1–3 must already have passed their gates.

Read `AGENTS.md`, the testing/evaluation strategy, operations/release policy, risk register, definition of done, current status, and the full Phase 4 plan. Run repository verification before editing.

Use strict TDD for every harness or release behavior. Golden expectations must come from deterministic reference calculations and source evidence, not unverified LLM output. Keep `AI-handoff-seed` cases out of the final approved score until a human reviewer replaces the review record. Measure rather than invent planner accuracy, exact match, evidence coverage, latency, failure rate, and ablation results. Exercise malformed model output, 429/timeouts, restart, no-external-network evaluation mode, and exact API schema.

Do not claim competition readiness until clean-room Docker reproduction, compliance scan, critical regression suite, performance/resilience checks, immutable artifact manifest, and independent review have passed with recorded evidence.

End after one independently reviewable task. Update status, commit, and report verified facts and the exact next task.
