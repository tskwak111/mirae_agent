# Official Requirements Traceability

## 1. Source

Authoritative source: `source_material/competition_task_financial_product_agent.pdf`.

This matrix records where each official requirement is designed, implemented, tested, and evidenced. Page references are to the supplied eight-page task document.

## 2. Traceability matrix

| Official requirement | Official location | Design response | Planned implementation | Verification evidence |
|---|---|---|---|---|
| Use domestic bonds, domestic ETF, overseas ETF, and public funds | p.4–5 | four product-specific Silver models plus common contracts | Phase 1 normalization/build pipeline | source audit, row/count/PK tests |
| Structure four schemas optimally | p.4 | Source Fidelity + five contracts; Bronze/Silver/Gold | Phase 1 | schema catalog, Parquet/DuckDB contract tests |
| Agent explores, filters, calculates, and answers from structured data | p.4 | constrained QueryPlan, deterministic compiler/executor | Phase 2–3 | SQL/compiler tests, differential tests |
| Understand asset, region, risk, fee, return, and combined conditions | p.4 | field/metric registry and semantic validator | Phase 2–3 | planner golden set, slot F1 |
| Search and detailed product lookup | p.4 | entity resolver plus typed repositories | Phase 2 | entity and lookup tests |
| Compare fee, return, and scale | p.4 | comparability engine and operation-specific metric policy | Phase 2 | comparison and policy tests |
| Sort, rank, aggregate, and calculate | p.4 | allowlisted AST/SQL and exact decimal handling | Phase 2 | differential/metamorphic tests |
| Cross product groups | p.4 | compatibility matrix; separated results when metrics are not comparable | Phase 2 | cross-product golden cases |
| Explain using data and show references | p.4–5 | evidence record, retrieved context, deterministic source footer | Phase 2–3 | evidence coverage and API tests |
| Do not guess absent data | p.4–5 | metric-availability gate and unsupported/clarify outcomes | Phase 2–3 | adversarial/unsupported cases |
| Ask for needed condition when information is insufficient | p.4–5 | ambiguity policy and safe defaults | Phase 2–3 | clarification precision tests |
| Avoid categorical recommendation and unsupported return forecast | p.5 | safety policy converts “recommend” to condition-matching candidates; forecast refusal | Phase 2–3 | safety regression suite |
| HyperCLOVA X only | p.4 | one HCX planner/verbalizer client; dependency and network audit | Phase 3–4 | prohibited-provider scan, integration config review |
| Official data is evaluation reference and wins conflicts | p.5 | official immutable evaluation mode; external demo namespace only | Phase 1, 4 | provenance and mode tests |
| Snapshot date 2026-07-11 | p.5 | explicit as-of default and answer note | all phases | date-policy tests |
| Quantitative evaluation via GET endpoint | p.6–7 | stable FastAPI adapter with bounded latency | Phase 3–4 | API/load/soak tests |
| Qualitative review of problem, technology, performance, creativity, accuracy, stability, utilization, risk | p.6 | FinProof contracts, ablation, quality dashboard, risk register | Phase 4 and proposal | benchmark report and review pack |
| Submit code, reproducible environment, README | p.7 | typed repository, lock file, Docker, commands | Phase 3–4 | clean-room reproduction |
| Submit proposal with architecture, flow, scenarios, impact, extensibility | p.7 | proposal evidence assets generated from measured system | Phase 4 | proposal checklist |
| Submit endpoint URL and request/response JSON schema | p.7 | exact `/answer` contract | Phase 3 | OpenAPI/API contract tests |
| Do not change code/results after deadline | p.7 | immutable release manifest and image digest | Phase 4 | release checklist and checksums |

## 3. Requirements not fully specified in the PDF

The supplied PDF does not settle the following. Do not invent organizer intent:

- exact hidden-answer matching policy
- official semantics for suspicious numeric zeroes
- expected public-fund answer grain
- exact `think_trace` content and length
- API timeout, concurrency, retry, and maximum payload sizes
- permitted failover/restart actions after submission freeze
- exact HyperCLOVA X models enabled for competition accounts

These remain in `docs/10_DECISION_LOG.md` as official questions. Current design choices are safe defaults, not claims about hidden scoring.
