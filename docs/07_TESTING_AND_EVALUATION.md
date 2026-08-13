# Testing and Evaluation Strategy

## 1. Quality model

FinProof separates deterministic correctness from language interpretation quality.

### Deterministic core must reach

- filter/sort/aggregate/calculation exact match: 100% on verified tests
- evidence coverage: 100% for material claims
- source checksum and audit match: 100%
- quarantined malformed row in normal results: 0
- API response-schema failure: 0
- unsupported metric fabricated number: 0

### Planner targets

- product type: at least 98%
- filter-slot F1: at least 97%
- as-of interpretation: at least 98%
- entity identification: at least 98%
- unnecessary clarification on clear questions: under 2%

Targets are not results. Record actual measurements.

## 2. Test pyramid

### Source contract

- manifest SHA-256
- workbook sheet/header/row count
- primary/composite key counts
- frozen audit metrics

### Unit/domain

- parsing and normalization
- sentinel and literal-null states
- rating order
- state/eligibility predicates
- metric operation policies
- currency/period/unit comparability
- result-grain selection

### Query engine

- QueryPlan schema and semantic validation
- field/operator allowlist
- parameterized SQL compilation
- candidate count and deterministic ordering
- differential result equality against a pure-Python reference

### Evidence/answer

- source-cell locators
- derived calculation evidence
- count/exclusion evidence
- claim coverage
- stable Korean answer templates
- safety/refusal/clarification language

### Planner/API

- recorded HyperCLOVA X contract fixtures
- malformed JSON and one repair
- timeout/rate-limit fallback
- exact request echo and five string fields
- Korean URL encoding
- no NaN/Infinity or internal leakage

### System

- golden set
- paraphrase and metamorphic set
- adversarial prompts
- load, resilience, restart, and soak
- clean-room Docker reproduction

## 3. Golden set

Build 250–300 human-verified canonical questions:

| Category | Target count |
|---|---:|
| exact product lookup | 40 |
| condition screen | 60 |
| rank/sort | 45 |
| comparison | 35 |
| aggregate | 25 |
| cross-product | 25 |
| ambiguity/clarification | 25 |
| data quality/tie/state | 30 |

Each case stores:

```text
expected intent/product/grain/as_of
expected filters/metrics/sort/top_k/top_k_scope and execution-segment partitioning
expected product IDs and order
expected numeric values
expected quality warnings
expected evidence locators or coverage rules
expected answer semantics
```

`tests/golden/seed_cases.jsonl` starts critical cases; expand it only with reviewed expectations.

## 4. Differential tests

For deterministic queries, compare:

```text
reference implementation: simple typed Python over canonical fixtures/full extracts
production implementation: DuckDB compiled SQL
```

Product IDs, ordering, values, included/excluded counts, and policy IDs must agree.

## 5. Metamorphic tests

Required relations:

- adding a restrictive filter cannot increase result count
- swapping ascending/descending reverses unique primary order
- A vs B difference changes sign for B vs A
- ticker/ISIN/exact official name resolve to the same product
- KRW won vs 억원 display conversion does not change rank
- paraphrasing condition order preserves the validated plan
- primary all-tie values remain joint rank despite a secondary display sort
- public-fund attribute count never duplicates `fund_item` rank results

## 6. Critical regression cases

Do not remove these:

1. `pd_tr_yn = 0` means not suspended in domestic listed-product state rule.
2. ETF query excludes ETN.
3. public-fund results deduplicate to `itm_no` by default.
4. public-fund literal `NULL` risk is missing, not a risk code.
5. the malformed public-fund source row is quarantined.
6. KRW and USD AUM are not directly ranked together.
7. overseas fee zero produces operation-specific warning/views.
8. domestic tracking-error ranking reports a tie.
9. overseas one-day-return ranking reports a tie.
10. positive bond quantity with snapshot-expired maturity is excluded from validated buyability.
11. Not Rated/missing bond grade is not promoted to AAA.
12. differing agency ratings are preserved and warned.
13. model/user field strings cannot inject SQL identifiers or statements.
14. fuzzy product candidates cannot auto-merge.
15. every numeric/comparative answer claim has evidence.
16. evaluation response contains exactly five string fields.
17. no non-HyperCLOVA generative provider is reachable from runtime code.

## 7. Ablation study

Use the same HCX model and question set:

| Version | Components |
|---|---|
| A | HCX reads retrieved rows and answers directly |
| B | constrained QueryPlan |
| C | deterministic executor |
| D | grain/time/state/metric policy |
| E | evidence, verifier, and conditional dual-lens |

Measure product-set F1, order accuracy, numeric exact match, evidence coverage, proper limitation/clarification, repeat stability, mean/p95 latency, and failure rate. Do not invent results before running experiments.

## 8. Performance and resilience

Once the organizer publishes limits, test above expected load. Until then:

- benchmark simple lookup, multi-filter rank, cross-product split, and explanation
- report planner, DB, evidence, and rendering latency separately
- test HCX timeout, 429, malformed output, DNS failure, and retry budget
- test process restart and readiness
- run at least 24 hours, preferably 48, with representative traffic before release
- ensure cached and uncached answers use the same version bundle

## 9. Mandatory commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

Phase plans add focused commands. Record exact output summaries in `docs/implementation/STATUS.md`.
