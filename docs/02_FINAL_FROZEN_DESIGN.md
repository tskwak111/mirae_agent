# Final Frozen Design — FinProof

## 1. Design thesis

The system is not “RAG over 145k rows.” It is a controlled financial-data execution system with an LLM at the interpretation boundary.

```text
Korean question
  -> preprocessing and exact identifiers
  -> HyperCLOVA X QueryPlan
  -> strict schema + semantic validation
  -> entity resolution
  -> native ExecutionBundle segmentation
  -> allowlisted AST and parameterized SQL per segment
  -> deterministic execution
  -> state/quality/comparability policy
  -> evidence construction
  -> deterministic answer
  -> claim verification
  -> exact evaluation API adapter
```

The model cannot generate executable SQL, calculate financial values, change metric policy, invent IDs, or bypass evidence.

## 2. Architectural boundaries

### `core`

Settings, immutable version bundle, constants, correlation IDs, typed errors, and structured logging.

### `domain`

Pydantic/domain contracts for QueryPlan, validated plan, ExecutionBundle/ExecutionSegment, products, metrics, evidence, execution results, quality issues, and answers. No FastAPI imports.

### `data`

Official-source manifest, streaming workbook ingestion, raw lineage, product-specific normalization, quarantine, data-quality report, Parquet output, and DuckDB build.

### `registry`

Load and validate dataset, field, metric, state, quality, rating, and answer policies. Registry versions become part of each execution trace.

### `entity`

Normalize identifiers/names, exact-match identifiers, alias lookup, controlled fuzzy candidate generation, and exact cross-source linking.

### `query`

Semantic validation, allowlisted field/operator registry, typed AST, SQL compiler, executor, and candidate-count instrumentation.

### `quality`

Metric availability, operation-specific zero/missing/tie policy, state and eligibility, period/unit/currency compatibility, and conditional dual-lens behavior.

### `evidence`

Build source-cell lineage, serialize compact retrieved context, calculate claim coverage, and block unsupported claims.

### `planner`

HyperCLOVA X client and adapters. Preferred mode is structured JSON output; fallback is strict JSON prompting with local parsing, at most one bounded repair, then rule parser/clarification.

### `answer`

Stable Korean templates, table rendering, limitation language, optional verified HCX wording, and recommendation/forecast safety.

### `service`

Orchestrate one request without importing transport-specific objects.

### `api`

FastAPI request validation, exact evaluation response, health/readiness/version endpoints, error mapping, timeout, concurrency, and cache adapter.

## 3. Data architecture

### Bronze

Read-only source files plus per-row raw payload and lineage:

```text
source_file
source_sheet
source_row_number
source_table
source_checksum
raw_payload
loaded_at
```

### Silver

Product-specific normalized tables:

```text
silver_bond_instrument
silver_bond_metric
silver_domestic_listed_product
silver_domestic_listed_metric
silver_overseas_listed_product
silver_overseas_listed_metric
silver_overseas_strategy_text
silver_fund_item
silver_fund_item_attribute
silver_fund_family_candidate
silver_quality_issue
```

### Gold

Query-optimized views and registries:

```text
gold_product_identity
gold_product_alias
gold_exact_cross_source_link
gold_product_metric
gold_search_view_*
gold_state_view_*
gold_evidence_locator
```

Artifacts are built offline and loaded read-only by the API.

## 4. Global invariant and contracts

### Source Fidelity invariant

Raw official values never disappear. A normalization may create a new typed value and quality status, but cannot overwrite or silently reinterpret the source.

### Identity & Grain

- heterogeneous cross-product response: `product`, preserving each result’s native grain
- bond: `instrument`
- domestic/overseas ETF or ETN: `listed_product`
- public fund: `fund_item` by default
- public-fund source attribute: `(itm_no, prfd_attr_cd)`
- optional family: candidate grouping only when explicitly requested

### Time

The default is the official `2026-07-11` snapshot. Derived maturity and state predicates are computed at the explicit query date. Field dates remain separate from the dataset date.

### State & Eligibility

State is product-specific and versioned. For domestic listed products, `pd_tr_yn = 0` means not suspended under the supplied schema interpretation. For bonds, “source buyable” and “validated buyable at as-of” are distinct.

Phase 2 validated eligibility is limited to domestic bonds and domestic listed ETF/ETN. Overseas-listed and public-fund raw sale/state values remain displayable with their source labels, but they do not become validated eligibility until a later frozen rule exists.

### Metric & Comparability

Metrics are operation aware. A raw recorded zero can be displayed literally while being flagged or separated in ranking/aggregation. Periods, units, currencies, and definitions must align before cross-product comparison.

### Evidence

Every material claim maps to source rows/columns and transformation rules. Phase 2 reuses the exact Phase 1 `SourceCellLocator` and normalized/derived value models rather than introducing a parallel locator DTO. Counts, exclusions, ranks, ties, partitions, and aggregates require bounded evidence summaries bound to the validated plan, policy IDs, version bundle, and expected artifact logical hash, not only product values.

## 5. Query planning

The model-facing schema stays small:

```text
intent
product_types
entities
as_of_date
result_grain
filters
metrics
metric_targets
sort
top_k
top_k_scope
needs_clarification
clarification_reason
```

The application injects versions and source policy. Semantic validation prevents invalid product/grain/field/operator/period/currency/state combinations before compilation. `top_k_scope` is either `global` or `per_product_type`. An aggregate plan contains exactly one closed `AggregationSpec`: `count` of the native result grain, or `min`/`max`/`sum`/`avg` of one registry-approved field, optionally grouped by at most two canonical fields.

A validated multi-product plan becomes an immutable `ExecutionBundle`. One `ExecutionSegment` is created per selected product type with its native grain and only the clauses registered for that type. A flat plan distributes metrics to every registered applicable type. When the language decision explicitly assigns metrics by product type, D-038's validated `metric_targets` is the sole routing authority and the same-field sorts follow it; no applicability or positional inference may invent that assignment. The fixed order is entity resolution and literal filtering, product-specific state and metric eligibility, compatibility partitioning, aggregate or rank/tie calculation, then `top_k`. A compiler consumes one segment at a time; `global` requires exactly one final compatibility partition, while `per_product_type` applies `top_k` independently to every final partition within each product type and traces every split. Heterogeneous results are assembled under the `product` envelope without erasing native identity or evidence.

## 6. Entity resolution

Resolution order:

1. exact official product identifier
2. exact ISIN/ticker/market identifier
3. normalized exact name/alias
4. controlled lexical/fuzzy candidate list
5. clarification when candidates materially conflict

Fuzzy similarity never creates an automatic cross-source merge. The known 47 domestic ETF–public fund links are exact identifier links only.

## 7. SQL boundary

- no raw SQL from a model or user
- no string interpolation for identifiers
- each native `ExecutionSegment` is compiled independently
- fields and expressions are functions registered in code
- values are parameters
- operators are a closed enum
- complexity, result count, and top-k are capped
- generated SQL and parameters are available in internal logs but not user output

## 8. Answer behavior

Normal data produces one concise answer. Quality issues that materially alter interpretation trigger two labeled views:

- `제공 데이터 기록값`
- `비교 가능 기준`

Examples:

- positive bond quantity: 325 source candidates; 254 remain after snapshot maturity validation
- overseas ETF fee zeroes: recorded values remain visible; a comparison-valid view may separate unverified zeroes
- domestic tracking error: all available values tie at zero, so no unique primary rank exists; a declared secondary sort may order display rows

A “recommend” request becomes “conditions-matching candidates,” not a suitability recommendation.

## 9. Runtime modes

### Evaluation mode

- official data only
- fixed artifact/version bundle
- one application-owned `RuntimeArtifactSession` that expected-verifies the published manifest before opening its declared read-only DuckDB
- packaged runtime registries that are byte-identical to their repository sources
- no live external data
- deterministic renderer by default
- strict five-field response

### Extended demo mode

- optional external static snapshots under separate provenance
- official value still wins conflicts
- no behavior leakage into evaluation mode

## 10. Availability and fallback

1. preferred HCX structured JSON planning
2. strict JSON prompt + local parser + one bounded repair
3. rule parser for common high-confidence patterns
4. concise clarification/unsupported answer

A planner failure must not allow an unvalidated query to execute.

## 11. Caching

Cache key includes:

```text
dataset_version
normalized_question
planner_version
metric_policy_version
state_policy_version
answer_policy_version
```

Never cache by `question_id` alone. Cached evidence and trace must belong to the exact version bundle.

## 12. Non-goals frozen for P0

No GraphDB, free Text-to-SQL, complex multi-agent graph, real-time external dependency, fuzzy auto-merge, personalized portfolio advice, or UI-first development.
