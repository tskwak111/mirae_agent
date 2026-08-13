# Codex Prompt 03 — HyperCLOVA X Planner and Evaluation API

Implement the first incomplete task in `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md` only. Phase 2 must already have passed its gate.

Read `AGENTS.md`, the QueryPlan/API contract, security/operations document, current status, and the full Phase 3 plan. Run repository verification before editing.

Use strict TDD and recorded fixtures for model-contract tests. HyperCLOVA X is the only generative model permitted in runtime/evaluation. Prefer HCX-007 Structured Outputs where the configured competition account supports it; send only `schemas/hcx_query_plan.schema.json`, never the stricter local schema, and do not combine Structured Outputs with Function Calling or thinking in the same request. Every response then passes the strict canonical QueryPlan and semantic validator. Keep a validated strict-JSON adapter and deterministic fallback behind the same Planner interface. Bound timeouts, retries, repair attempts, concurrency, and output size.

The public endpoint must be `GET /answer`, echo the request, and return exactly five string fields: `question_id`, `question`, `retrieved_context`, `think_trace`, and `answer`. `think_trace` is a reproducible execution summary, not hidden chain-of-thought. Default answer rendering is deterministic; optional HCX wording must consume verified facts and pass claim verification.

End after one independently reviewable task. Run focused, contract, and relevant integration checks, update status, commit, and report the exact next task.
