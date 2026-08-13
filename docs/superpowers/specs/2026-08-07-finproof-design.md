# FinProof Design Specification

**Status:** Frozen for implementation on 2026-08-07.

## Goal

Build a reproducible financial-product agent that uses HyperCLOVA X only for constrained language planning, executes all data operations deterministically, and proves every material answer claim with official-source evidence.

## Required behavior

- four official masters with product-specific normalization
- immutable source lineage and quality states
- explicit identity/grain, time, state, metric/comparability, and evidence contracts
- public-fund item/attribute split and optional family candidate grouping
- ETF/ETN separation
- snapshot-aware bond maturity and product eligibility
- operation-specific missing/zero/tie policy
- currency/period/unit-safe comparison
- exact/alias entity resolution; fuzzy candidate only
- validated QueryPlan, explicit `top_k_scope`, native cross-product execution segments, and allowlisted parameterized SQL
- deterministic answer templates and claim verifier
- exact five-field evaluation API
- measured golden/differential/metamorphic/adversarial/load/soak quality

## Architecture

```text
source workbooks
  -> manifest/checksum/streaming ingest
  -> Bronze lineage + quality issues
  -> product-specific Silver + Gold views

question
  -> preprocess/exact IDs
  -> HyperCLOVA X constrained plan
  -> provider schema + strict local schema/semantic validation
  -> entity resolution
  -> native ExecutionBundle segmentation
  -> allowlisted AST/SQL per segment
  -> deterministic execution
  -> state/metric/comparability policy
  -> evidence
  -> deterministic answer
  -> claim verifier
  -> evaluation API
```

## Data design

DuckDB and Parquet are the default for a fixed, read-heavy dataset. The API opens a prebuilt database read-only. Source rows retain exact Excel lineage. Public-fund ranking operates on `itm_no`; attributes remain in a separate relation. Exact cross-source identifier matches are stored separately from candidate links.

## Planner design

The model-facing plan is intentionally small. Preferred HCX mode is structured JSON using the provider-safe schema in `schemas/hcx_query_plan.schema.json`; strict local validation uses `schemas/query_plan.schema.json`. A strict JSON prompt/parser and one bounded repair provide fallback. A rule parser handles high-frequency unambiguous patterns. No plan executes before semantic validation. Heterogeneous plans use `result_grain=product`, declare `top_k_scope`, and are decomposed into native execution segments before compilation.

## Error handling

- unsupported data: explicit limitation
- material ambiguity: safe split or concise clarification
- planner outage/malformed output: bounded fallback
- deterministic internal failure: safe five-field response, logged correlation ID
- source/checksum mismatch: readiness failure and implementation stop

## Testing

TDD is mandatory. Source contracts, domain policies, compiler boundaries, differential results, evidence coverage, planner contracts, API schema, metamorphic/adversarial cases, and operational tests form the release gate.

## Scope control

P0 excludes UI-first work, GraphDB, free Text-to-SQL, complex multi-agent designs, live external dependencies, fuzzy auto-merge, personalized advice, and portfolio optimization.

Detailed normative behavior is in `docs/02_FINAL_FROZEN_DESIGN.md` through `docs/08_SECURITY_OPERATIONS_AND_RELEASE.md`. Those documents and this spec must remain consistent; an official override is recorded in the decision log.
