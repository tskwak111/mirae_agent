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
- Bronze contains exactly 145,393 source rows, 6,401,851 source cells, and 207
  source-catalog columns with complete D-017 lineage
- Silver contains exactly 42,394 bonds, 1,733 domestic listed products, 5,646 overseas
  listed products, 11,138 fund items, and 95,618 fund attributes; the two quarantined
  source rows remain in Bronze and canonical quality output
- exact raw-identifier links contain 47 item-grain pairs, canonical pair SHA-256
  `8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962`, and
  371 source locators
- two independent builds with different injected UTC persistence times produce
  identical table and manifest logical hashes; each build's declared physical hashes
  independently verify its own generation
- verification recomputes Parquet schema/count/sort/unique/logical hashes, both report
  logical hashes, and the overall manifest logical hash, then matches the verified set
  against packaged `config/expected_phase1_artifacts.json`
- initial expected-contract bootstrap uses only the unpublished, non-packaged candidate
  path with full verification and independent review; it refuses any existing baseline
- manifest/Bronze/quality typed/quality-JSON persistence timestamps agree exactly, and
  report logical identity uses semantic report IDs rather than output paths
- staged build/publication failures leave an existing verified artifact unchanged or
  restore it; no-clean refuses an existing target and clean refuses unrecognized or
  symlink targets
- manifest verification and clean recognition require the exact recursive tree
  (`manifest.json`, 14 declared regular files, required parent directories only); extra,
  link, special, hardlink-alias, canonical-duplicate, and WAL entries refuse byte-safely
- DuckDB is self-contained, opens read-only, rejects writes, and contains only the
  expected Task 5 tables; bidirectional typed equality proves every DuckDB table has
  exactly the verified Parquet content, not merely the same schema/count
- official public-fund artifact construction is bounded by one complete item group
  (at most 16 source rows) plus fixed-size writer batches
- every non-source-sorted Silver/quality/link output uses bounded external staging with
  one DuckDB thread, a 1-GiB memory limit, and a private spill directory
- verification equality also uses one DuckDB thread, a 1-GiB limit, and its own
  mode-0700 marker-owned OS temp without artifact-root/parent writes; post-commit old
  generations are atomically renamed to marked cleanup tombstones before recursive
  deletion
- full format/lint/type/test/audit/verify commands

Required deliverables:

```text
artifacts/manifest.json
artifacts/reports/source_audit.json
artifacts/reports/quality_summary.json
artifacts/parquet/*.parquet
artifacts/finproof.duckdb
```

These are generated runtime deliverables and remain untracked. The repository tracks a
timestamp-free expected Phase 1 logical-artifact contract and records the reviewed
generation's physical hashes in implementation status.

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
