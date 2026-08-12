# Phase Gates

## Gate 0 — Handoff integrity

Required:

```bash
python tools/verify_handoff.py
python tools/audit_source_data.py --check
```

Pass means all required files, JSON/YAML/schema syntax, checksums, row counts, and frozen audit values match. A mismatch blocks implementation.

## Phase 1 gate — Reproducible data foundation

All must pass:

- source manifest/checksum/header contract tests
- workbook streaming reader tests with exact Excel row lineage
- bond/listed/fund normalization tests
- public-fund item/attribute and quarantine regressions
- state/derived-date field tests
- exact link count test
- clean artifact build from source files
- two independent builds produce identical logical tables and artifact manifest hashes, excluding declared build timestamps
- DuckDB opens read-only and contains expected tables/counts
- full format/lint/type/test/audit/verify commands

Required deliverables:

```text
artifacts/manifest.json
artifacts/reports/source_audit.json
artifacts/reports/quality_summary.json
artifacts/parquet/*.parquet
artifacts/finproof.duckdb
```

## Phase 2 gate — Deterministic correctness and evidence

All must pass:

- QueryPlan schema and semantic validation
- product/native-grain/heterogeneous-envelope/field/operator/value/top-k/top-k-scope safety
- cross-product ExecutionBundle segmentation and compatibility partitioning
- exact/alias resolution and no fuzzy auto-merge
- parameterized allowlisted SQL tests including injection attempts
- lookup/screen/rank/compare/aggregate paths
- pure-Python vs DuckDB differential equality
- critical state/zero/tie/currency/period/rating regressions
- evidence coverage 100% for seeded material claims
- claim verifier fail-closed
- stable deterministic Korean answers
- unsupported/clarify/recommendation-safety cases
- full quality commands

## Phase 3 gate — Planner and API reliability

All must pass:

- only HyperCLOVA X generative provider in runtime dependency/config/code scan
- provider-safe HCX schema, strict local QueryPlan schema, and structured/strict JSON planner fixtures
- malformed output, one repair, timeout, 429, and fallback tests
- planner output always enters semantic validation
- exact five-field string response contract
- request echo and Korean URL encoding
- no NaN/Infinity/internal leakage
- bounded concurrency, retries, timeouts, and complete cache version key
- structured redacted logs and correlation IDs
- Docker build/start/health/ready/version/answer from a clean environment
- evaluation mode with network access denied except HCX endpoint
- full quality commands

## Phase 4 gate — Submission readiness

All must pass:

- frozen decision `D-017`: Phase-2/Phase-3 checkpoint candidate bytes and provenance were pinned
  without exposing locked results, and Phase 4 replayed those exact candidates in policy order with
  proof that no Phase-2 result guided or gated Phase 3
- after both locked reports, immutable `phase4_evaluation_complete_candidate` commit `G0` and both
  final repository-order witnesses exist; submission readiness consumes `G0`/those witnesses, and the
  successful gate evidence is recorded only afterward in descendant `G1`
- 250–300 reviewed canonical golden cases or an explicitly approved lower number with full category coverage
- actual planner/product/order/numeric/evidence/stability metrics reported
- all critical regressions pass
- reproducible ablation report
- measured mean/p95 latency and error rate under representative concurrency
- HCX fault injection and process restart pass
- 24-hour minimum soak, 48-hour preferred, with zero critical failure
- independent BLOCKER/HIGH findings resolved or officially accepted
- clean-room clone, sync, artifact build/load, Docker run, and API verification
- proposal values generated from measured artifacts
- release tag, commit hash, image digest, and code/data/config/prompt checksums recorded
- external endpoint reachable and schema checked
- no change after freeze
