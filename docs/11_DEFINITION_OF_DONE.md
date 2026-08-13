# Definition of Done

## 1. A task is done only when

- its behavior test was written and observed failing first
- minimal implementation passes the focused and relevant suites
- public interfaces are typed and documented
- no frozen design drift or hidden policy was introduced
- commands/results are recorded in status
- the change is independently reviewable and committed
- worktree is clean

## 2. Phase 1 — Data foundation done

- all source checksums, headers, and audit baselines pass
- Bronze lineage preserves source file/sheet/row/column/raw values
- product-specific Silver tables build deterministically
- public-fund item/attribute split is correct
- malformed row is quarantined
- snapshot state and key derived fields are tested
- registry/config schemas validate
- Parquet and DuckDB artifacts are reproducible with checksums
- clean build from raw workbooks succeeds

## 3. Phase 2 — Deterministic engine done

- strict canonical QueryPlan, HCX-provider schema contract, domain types, and semantic validator are complete
- heterogeneous `product` envelopes, `top_k_scope`, native ExecutionBundle segmentation, and compatibility partitions are complete
- entity resolver follows exact/alias/candidate rules
- allowlisted compiler cannot inject identifiers/statements
- all core lookup/screen/rank/compare/aggregate paths execute
- state, metric, tie, zero, currency, period, and grain policies pass
- conditional dual-lens behavior is deterministic
- evidence and claim verification cover every material claim
- deterministic Korean renderer handles supported/clarify/unsupported paths
- differential and critical regression suites pass

## 4. Phase 3 — Planner/API done

- HyperCLOVA X is the only generative client/provider in runtime
- structured/strict JSON planner and bounded fallback validate into one internal plan
- API returns exact five-field string response
- echo, encoding, timeout, retries, concurrency, cache versioning, and safe errors pass
- health/readiness/version endpoints work
- Docker build and local run reproduce the service
- no live external data is needed in evaluation mode

## 5. Phase 4 — Release done

- canonical golden set is human-reviewed
- planner and end-to-end metrics are measured, not assumed
- ablation results are reproducible
- adversarial, load, restart, and 24–48h soak tests pass
- no critical/high unmitigated competition risk remains
- clean-room clone/build/run succeeds
- proposal numbers match measured reports
- immutable release manifest, commit, image digest, data/config/prompt checksums exist
- external endpoint and API spec are verified
- submission checklist is signed before freeze

## 6. AAA claim gate

Do not call the implementation AAA unless all release criteria above pass and the report includes actual:

- deterministic correctness
- planner metrics
- evidence coverage
- repeat stability
- latency and error rate
- load/soak evidence
- known limitations

Strong architecture alone is not an AAA implementation.
