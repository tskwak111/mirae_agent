# QueryPlan and Evaluation API Contract

## 1. QueryPlan role

HyperCLOVA X maps natural language to a constrained plan. It does not write SQL, calculate metrics, invent identifiers, set unregistered policy, or directly select answer rows.

The application validates, enriches, decomposes, compiles, and executes the plan.

## 2. Intents

```text
lookup
screen
screen_rank
compare
aggregate
explain
clarify
unsupported
```

## 3. Product types

```text
domestic_bond
domestic_etf
domestic_etn
overseas_etf
overseas_etn
public_fund
```

Plain ETF excludes ETN.

## 4. Result grains

```text
product                  # heterogeneous cross-product response envelope
instrument               # domestic bond
listed_product           # domestic/overseas ETF or ETN
fund_item                 # default public-fund query grain
fund_attribute            # public-fund attribute question only
fund_family_candidate     # explicit class-consolidation request only
```

Semantic validation enforces product/grain compatibility.

- A single product type uses its native grain.
- Multiple product types that share the same native grain may retain that grain when the operation is semantically compatible.
- A request spanning different native grains uses `product`; it is never compiled as one physical table scan.
- `product` is an output envelope. Every result retains its native product type, native grain, identity, currency, evidence, and policy partition.

## 5. Top-k scope

Every plan declares how `top_k` applies:

```text
global             # one compatible comparison partition
per_product_type   # top_k is applied independently to each final partition within each product type
```

`global` is valid only when the requested metric, unit, period, currency, state semantics, and ranking policy form one compatible partition. If they do not, the validator either creates declared side-by-side partitions, changes no user literal, or returns clarification.

`per_product_type` always creates one native execution segment per selected product type. The comparability engine may further partition a segment by currency or another registered compatibility key. Each resulting final partition receives its own `top_k`, carries a stable partition key, and is labeled in the trace and answer; incompatible partitions are never merged merely to enforce one product-type-wide limit.

## 6. Model-facing plan

```json
{
  "intent": "screen_rank",
  "product_types": ["domestic_bond"],
  "entities": [],
  "as_of_date": "2026-07-11",
  "result_grain": "instrument",
  "filters": [
    {"field": "buyable_quantity", "operator": "gt", "value": 0},
    {"field": "maturity_date", "operator": "gte", "value": "2026-07-11"},
    {"field": "credit_rating", "operator": "gte", "value": "AA-"}
  ],
  "metrics": ["buy_yield", "maturity_date", "credit_rating"],
  "sort": [{"field": "buy_yield", "direction": "desc"}],
  "aggregation": null,
  "top_k": 5,
  "top_k_scope": "global",
  "needs_clarification": false,
  "clarification_reason": ""
}
```

Canonical local schema: `schemas/query_plan.schema.json`.

Provider-facing HCX Structured Outputs schema: `schemas/hcx_query_plan.schema.json`.

The provider schema deliberately uses only the supported HCX JSON-Schema subset. It does not contain local-only strictness keywords such as `additionalProperties`, `uniqueItems`, `pattern`, `minLength`, or `maxLength`. Every provider response must still pass the strict canonical Pydantic/schema model and semantic validator before execution.

### Aggregate shape

`intent=aggregate` requires exactly one object:

```json
{
  "function": "avg",
  "field": "total_fee",
  "group_by": ["currency"]
}
```

The function is exactly `count`, `min`, `max`, `sum`, or `avg`. `count` requires `field=null` and counts the native result grain after filtering and policy eligibility. The other functions require one canonical field whose registry entry authorizes that operation. `group_by` is an ordered unique tuple of zero, one, or two canonical fields. Nested expressions, arbitrary formulas, multiple aggregations, caller SQL, and caller-selected output aliases are prohibited.

Aggregate output is an ordered tuple of immutable groups. Each group contains its typed group-key values, typed aggregate value, included and excluded counts, policy IDs, and bounded evidence-summary IDs. Count values are exact integers; decimal operations use `Decimal`; dates and strings are accepted only for registry-authorized `min`/`max`.

The canonical local schema always includes `aggregation`, using JSON `null` for non-aggregate plans. Executable intents require at least one product type, `needs_clarification=false`, an empty `clarification_reason`, and the clauses allowed by that intent. `clarify` requires `needs_clarification=true`, a nonempty reason, no filters/metrics/sort/aggregation, and may leave product types empty. `unsupported` requires `needs_clarification=false`, a nonempty reason, no filters/metrics/sort/aggregation, and may leave product types empty. Clarify/unsupported `top_k` values are validated for shape but never executed.

## 7. Cross-product decomposition

The model-facing plan remains small. The application converts one validated plan into an immutable execution bundle:

```text
ExecutionBundle
- original ValidatedQueryPlan
- top_k_scope
- one or more ExecutionSegment values
- comparison partitions
- assumptions and policy IDs
- immutable version bundle

ExecutionSegment
- product_type
- native_result_grain
- resolved entities for that type
- applicable typed filters
- applicable requested metrics
- applicable typed sort
- segment top_k
- compatibility partition key
- compiled-query/evidence requirements
```

Distribution rules:

1. create one segment per selected product type;
2. map each canonical field/metric through the registry for that product type;
3. apply a clause only to product types for which it is registered and semantically valid;
4. reject or clarify a clause that maps to no selected type;
5. clarify when a clause has materially different unresolved meanings across types;
6. never force bond yield, historical return, fee, AUM, risk, or state into a false common metric;
7. preserve the original user condition and record every split or safe assumption in the execution trace;
8. compile and execute each segment independently, then assemble a side-by-side `product` envelope;
9. perform an integrated global rank only when one registered compatibility group permits it.

This decomposition is how FinProof satisfies product-group cross queries without a union of incompatible physical schemas.

## 8. Application-injected versions

The model cannot choose:

```text
dataset_version
artifact_manifest_hash
dataset_registry_version
field_registry_version
metric_registry_version
state_rule_version
quality_rule_version
rating_rule_version
answer_policy_version
planner_version
execution_mode
```

The application issues this bundle only from one expected-verified artifact and one exact immutable runtime registry bundle. It has no behavior-bearing defaults. `artifact_manifest_hash` is the verified overall manifest logical hash; registry versions come from parsed package resources that are byte-identical to their repository sources.

## 9. Operator allowlist

```text
eq
ne
gt
gte
lt
lte
in
not_in
between
contains
starts_with
is_missing
is_not_missing
```

Each field registration states product types, operators, value type, SQL expression factory, sortable/aggregatable status, and evidence mapping. A model string never becomes an SQL identifier.

`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, and `starts_with` require one scalar value. `in` and `not_in` require a bounded nonempty scalar tuple. `between` requires exactly two ordered values. `is_missing` and `is_not_missing` prohibit a `value` member. The strict local schema and Pydantic model use the same operator-discriminated variants. `contains` and `starts_with` treat `%`, `_`, backslash, control characters, and Unicode as literal parameter data rather than SQL wildcard or identifier syntax.

## 10. Defaults and ambiguity

### Safe defaults

- missing date -> `2026-07-11`
- “current” -> `2026-07-11` and disclose it
- plain ETF -> exclude ETN
- public fund -> `fund_item`
- heterogeneous native grains -> `product`
- missing top-k on a ranking request -> configured default, capped at maximum
- single-product or compatible global rank -> `top_k_scope=global`
- explicit “각각 N개” -> `top_k_scope=per_product_type`

### No silent guess

- missing return period when ranking depends on it
- integrated AUM rank across currencies without FX basis
- multiple materially ambiguous product candidates
- unsupported metric or horizon
- suitability/personalized recommendation
- cross-product clause whose field or meaning cannot be assigned safely
- one global top-k over incompatible product/metric partitions

### Single-call evaluation strategy

Apply a safe default if it preserves the user’s intent and state it. Split results if incompatible groups can still be useful. Ask a concise clarification only when different interpretations materially change the answer and cannot be safely separated.

## 11. Validation pipeline

1. HCX-provider schema validation when Structured Outputs is used
2. strict local JSON/Pydantic canonical validation, including intent/aggregation and operator/value variants
3. product type and result-grain compatibility
4. exact entity resolution or fail-closed candidate/ambiguity result
5. field/operator/value and aggregate-function validation
6. metric availability and product-specific state-policy support
7. cross-product segment distribution
8. literal filtering and bounded candidate-count capture
9. state and operation-specific metric eligibility
10. date/period/unit/currency compatibility partitioning
11. aggregate calculation or rank/tie calculation within final partitions
12. `top_k_scope`, top-k, and complexity limits per final partition and request
13. supportability and recommendation safety

A failed plan never reaches the SQL compiler.

## 12. Internal plan and execution bundle

```text
ValidatedQueryPlan
- request identity
- original and normalized question
- intent and product types
- resolved entities
- as_of_date
- result_grain
- typed filters
- requested metrics
- typed sort
- optional typed aggregation
- top_k
- top_k_scope
- assumptions
- selected policy IDs
- clarification/unsupported state
- immutable version bundle

ExecutionBundle
- validated plan
- ordered native ExecutionSegment values
- comparison partitions
- optional closed aggregate specification
- bounded candidate/included/excluded count plan
- response-envelope grain
```

A compiler consumes one `ExecutionSegment`, not an unsplit heterogeneous plan. The executor returns bounded pre-policy segment rows and candidate counts. The policy pipeline then applies eligibility/metric rules, partitions, aggregate or rank/tie calculation, and final `top_k` before assembling the response projection. Native identity and evidence are never erased by the common `product` envelope.

## 13. Runtime artifact and registry session

The application composition root creates one `RuntimeArtifactSession` before constructing a resolver, repository, executor, evidence builder, or answer service. Session creation:

1. loads `artifacts/manifest.json` through `ArtifactManifest.load`;
2. expected-verifies the exact published artifact root;
3. loads the exact packaged runtime registry inventory whose build/contract tests prove source/resource byte identity;
4. issues the immutable `VersionBundle` from the verified artifact and registries;
5. opens only the manifest-declared `finproof.duckdb` through the locked read-only database API;
6. owns and closes the connection.

Repositories accept this live session, never a caller `Path`, DuckDB connection, cursor, SQL string, or arbitrary registry bundle. Tests may use a private small verified-session factory; production code has no bypass constructor.

## 14. Evaluation API

### Request

```http
GET /answer?question_id=Q-001&question=<URL-encoded Korean question>
```

### Response

Until an official override, return exactly:

```json
{
  "question_id": "Q-001",
  "question": "evaluation question",
  "retrieved_context": "serialized evidence context",
  "think_trace": "reproducible execution trace",
  "answer": "final answer"
}
```

All values are strings. Schema: `schemas/api_response.schema.json`.

### Echo

`question_id` and `question` exactly echo request values. Normalized text remains internal.

### `retrieved_context`

A compact serialized JSON string containing only facts/evidence needed for the answer:

```json
{
  "dataset_version": "2026-07-11",
  "segments": [],
  "products": [],
  "metrics": [],
  "evidence": [],
  "warnings": []
}
```

No secrets, SQL, stack traces, or local paths.

### `think_trace`

A stable execution summary:

```text
intent=screen_rank;product_types=domestic_bond;as_of=2026-07-11;
result_grain=instrument;top_k_scope=global;segments=1;
source_candidates=42394;positive_quantity=325;not_matured=254;
rating_filter_passed=31;returned=5;validation=passed
```

For a cross-product request, include segment and compatibility-partition counts. Do not expose unrestricted model reasoning.

### `answer`

Concise Korean output containing result, relevant basis/date, evidence source, and material limitation. It must remain correct if the optional verbalizer is disabled. Heterogeneous results are labeled by product type and compatibility partition.

## 15. Error behavior

For syntactically valid evaluation requests, prefer a valid five-field response with a safe answer rather than leaking an internal error.

- unsupported data -> explicitly unavailable
- clarification required -> concise required condition
- planner failure -> bounded retry, validated rule fallback, or clarification
- cross-product incompatibility -> safe side-by-side split or clarification
- deterministic failure -> internal correlation ID in logs and generic safe answer
- request contract violation -> standard validation response, subject to organizer confirmation

## 16. Operational endpoints

```text
GET /health/live
GET /health/ready
GET /version
```

They are separate from the evaluation response contract.
