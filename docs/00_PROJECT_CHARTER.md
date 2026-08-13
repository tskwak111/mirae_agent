# FinProof Project Charter

## 1. Product statement

FinProof is an evidence-first financial-product analysis agent that answers Korean natural-language questions over the official 2026 Mirae Asset Securities AI Festival datasets.

It is not a generic investment chatbot. It is a controlled query-and-explanation system that understands product identity, result grain, dates, state/eligibility, metric comparability, and evidence provenance before producing an answer.

## 2. Problem

The four datasets do not share one safe universal schema:

- domestic bonds use maturity, yields, ratings, duration, evaluation price, and partial buyability fields
- domestic ETF data also contains ETNs and has incomplete or constant-valued metrics
- overseas ETF data also contains ETNs and includes rich descriptive fields but weak return coverage
- public funds repeat item-level values across attribute rows and mix currencies, statuses, and sentinel strings

A system that treats this as document retrieval, lets an LLM calculate values, or lets a model freely generate SQL is likely to return duplicated products, stale “current” claims, invalid cross-currency rankings, unsupported recommendations, or numbers without reproducible evidence.

## 3. Objective

Deliver a public evaluation API and reproducible repository that:

1. interprets natural-language intent and conditions with HyperCLOVA X
2. validates the plan against product, grain, time, state, metric, and safety contracts
3. executes retrieval and numeric operations deterministically
4. preserves official raw values and records quality/normalization separately
5. constructs evidence for every material claim
6. renders stable Korean answers and blocks unsupported claims
7. demonstrates measurable accuracy, stability, latency, and operational readiness

## 4. Primary users

- competition evaluator sending hidden API questions
- financial-product staff searching and comparing products
- reviewers auditing why a result was included, excluded, ranked, or limited
- developers reproducing the system from the submitted repository

## 5. In scope

- official domestic-bond, domestic ETF/ETN, overseas ETF/ETN, and public-fund workbooks
- offline source profiling, Bronze/Silver/Gold processing, DuckDB/Parquet artifacts
- exact and alias product resolution; fuzzy candidate suggestions without automatic merge
- lookup, screening, ranking, comparison, aggregation, explanation, and clarification
- product-specific state/eligibility rules
- metric availability and comparability checks
- conditional “provided-record” versus “comparison-valid” presentation
- HyperCLOVA X QueryPlan generation and bounded fallback
- deterministic answer rendering, evidence, claim verification, and execution trace
- FastAPI evaluation endpoint, Docker, CI, tests, load/soak, and release freeze

## 6. Out of scope before P0 completion

- personal investment suitability and individualized advice
- portfolio optimization or future-return prediction
- live market-data dependence in evaluation mode
- free-form Text-to-SQL
- automatic fuzzy entity consolidation
- GraphDB added only for novelty
- multi-agent choreography without measured benefit
- large UI work before API accuracy and stability gates pass

## 7. Product principles

1. **Source fidelity:** preserve official values; never silently “correct” them.
2. **Explicit semantics:** grain, date, state, unit, currency, period, and zero policy are first-class.
3. **Determinism:** all selection and numeric behavior is code/config driven.
4. **Evidence before prose:** claims are permitted only after evidence construction and verification.
5. **Useful restraint:** state limitations or separate incompatible results rather than inventing a single answer.
6. **Measured quality:** benchmarks and failure analysis, not feature count, determine readiness.

## 8. Success measures

### Deterministic core

- source contract and checksum agreement: 100%
- filter, sort, aggregation, and calculation exact match on verified fixtures: 100%
- evidence coverage for material numeric/comparative claims: 100%
- unsupported metric number generation: 0
- quarantined malformed row in normal results: 0
- API schema conformance: 100%

### Planner targets

- product-type accuracy: at least 98%
- filter-slot F1: at least 97%
- date interpretation: at least 98%
- exact/alias entity resolution: at least 98%
- unnecessary clarification on clear questions: below 2%

### Operations

- repeated deterministic execution returns the same ordered result
- bounded fallback on HyperCLOVA X timeout/rate limit
- 24–48 hour soak test with zero critical failures before release
- p95 latency comfortably below the organizer’s official timeout once disclosed
- clean, reproducible Docker build from the frozen repository

## 9. Delivery strategy

Phase-gated execution:

1. data foundation
2. deterministic query/evidence engine
3. HyperCLOVA X planner and API
4. evaluation, hardening, and release

Each phase has test-first tasks, a reviewable commit trail, and an explicit gate. New scope is rejected unless it raises evaluation quality more than it raises implementation and operational risk.
