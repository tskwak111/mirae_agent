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
per_product_type   # top_k is applied independently to each selected product type
```

`global` is valid only when the requested metric, unit, period, currency, state semantics, and ranking policy form one compatible partition. If they do not, the validator either creates declared side-by-side partitions, changes no user literal, or returns clarification.

`per_product_type` always creates one native execution segment per selected product type. The comparability engine may further partition a segment by currency or another registered compatibility key; it may not silently combine incompatible values.

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
  "top_k": 5,
  "top_k_scope": "global",
  "needs_clarification": false,
  "clarification_reason": ""
}
```

Canonical local schema: `schemas/query_plan.schema.json`.

Provider-facing HCX Structured Outputs schema: `schemas/hcx_query_plan.schema.json`.

The provider schema deliberately uses only the supported HCX JSON-Schema subset. It does not contain local-only strictness keywords such as `additionalProperties`, `uniqueItems`, `pattern`, `minLength`, or `maxLength`. Every provider response must still pass the strict canonical Pydantic/schema model and semantic validator before execution.

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
metric_registry_version
state_rule_version
quality_rule_version
rating_rule_version
answer_policy_version
planner_version
execution_mode
```

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
2. strict local JSON/Pydantic canonical validation
3. product type and result-grain compatibility
4. `top_k_scope` compatibility
5. entity-resolution status
6. field/operator/value validation
7. metric availability
8. cross-product segment distribution
9. date/period/unit/currency compatibility and partitioning
10. state-rule applicability
11. operation-specific zero/missing/tie policy
12. top-k and complexity limits per segment and request
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
- aggregate candidate-count plan
- response-envelope grain
```

A compiler consumes one `ExecutionSegment`, not an unsplit heterogeneous plan. The executor runs the bundle and returns segment results plus an assembled response projection. Native identity and evidence are never erased by the common `product` envelope.

## 13. Evaluation API

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

## 14. Error behavior

For syntactically valid evaluation requests, prefer a valid five-field response with a safe answer rather than leaking an internal error.

- unsupported data -> explicitly unavailable
- clarification required -> concise required condition
- planner failure -> bounded retry, validated rule fallback, or clarification
- cross-product incompatibility -> safe side-by-side split or clarification
- deterministic failure -> internal correlation ID in logs and generic safe answer
- request contract violation -> standard validation response, subject to organizer confirmation

## 15. Operational endpoints

```text
GET /health/live
GET /health/ready
GET /version
```

They are separate from the evaluation response contract.
