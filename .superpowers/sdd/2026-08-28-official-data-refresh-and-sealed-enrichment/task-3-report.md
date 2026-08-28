# Task 3 — Bond sale lots and organizer purchaseability

Date: 2026-08-28
Base: `5ee3590ec98f5288313b4a81036e44a4f51fbc43`

## Scope implemented

- Added strict immutable `BondSaleLotKey` and `BondSaleLot` contracts. Every recoverable
  refreshed PRBD row retains its exact key fields, quote fields, raw
  `buyable_quantity`, complete `SourceRow`, and cell locators.
- Added deterministic `project_bond_instrument`: exactly one parent per `pd_no`, maximum
  valid buy yield, all quote fields from the selected lot, and canonical source-key tie
  breaking that never observes quantity.
- Parent conflicts now fail the individual field closed while preserving every sorted,
  equivalent source locator. Missing/sentinel maturity emits the explicit unverifiable-end
  warning.
- Purchaseability excludes only issue-after-boundary and ended bonds. Raw quantity is
  ignored under the organizer override.
- Removed quantity from the parent model, state evaluation, field/metric/planner
  registries, implicit AST, rule fallback, and evidence source-lens/limitation logic. It
  remains only in source/lot lineage.

## Preflight evidence

- `python3 tools/verify_handoff.py` — PASS; 61 required files, 9 official inputs,
  19,074,953 official bytes.
- `python3 tools/audit_source_data.py --check` — PASS; 53,375 official rows with the
  frozen 2026-08-24 distribution.

## Focused RED → GREEN evidence

### Lot and projection behavior

RED:

```text
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest tests/unit/data/normalization/test_bonds.py -q -k 'lot or projection or purchase'
```

Collection failed because `normalize_bond_lot` and the new lot/projection interfaces did
not exist. After the minimum lot model, normalizer, and projection implementation, the
same selector was GREEN: `12 passed, 2 deselected`; the complete focused file was GREEN:
`14 passed`.

### State, registry, AST/compiler, and fallback behavior

RED:

```text
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest tests/unit/quality/test_state_policy.py tests/unit/query/test_field_registry.py tests/unit/query/test_query_ast.py tests/unit/query/test_sql_compiler.py tests/unit/planner/test_prompts.py tests/unit/planner -q -k 'buyable or purchase or saleable or quantity'
```

Observed `7 failed`: legacy quantity-based state evaluation, the queryable quantity
field/metric, forged quantity AST acceptance, and the rule fallback's quantity clause.
After removing those paths, the same command was GREEN: `7 passed, 59 deselected`.

### Evidence behavior

RED:

```text
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest tests/unit/evidence/test_builder.py -q -k 'buyable or purchase or saleable or quantity'
```

The zero-quantity case alone emitted the legacy exclusion limitation, so otherwise
identical evidence bundles differed. After removing quantity from the source-lens and
limitation paths, the selector was GREEN: `1 passed, 29 deselected`.

### Real-locator ordering regression

The first official acceptance run reached all frozen counts, then exposed that canonical
lot order can differ from source-row locator order. A focused synthetic reproduction was
added:

```text
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest tests/unit/data/normalization/test_bonds.py -q -k equivalent_locator
```

RED failed with `BondFieldSources`' unique-and-sorted validation. Sorting the wrapped
parent values by exact source row/column before selecting the representative made the
same command GREEN: `1 passed, 13 deselected`.

## Official acceptance

```text
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest tests/source_contract/test_official_domestic_normalization.py -q -k bond
```

GREEN: `1 passed in 31.70s`. The test proves:

- 21,882 recoverable source lots and 21,882 unique exact source keys;
- 20,497 queryable parent instruments;
- 1,078 duplicate `pd_no` groups;
- exact raw/cell lineage for every modeled lot field; and
- identical parent projections after changing every lot's raw quantity input.

## Aggregate and scoped checks

The first bundle aggregate exposed only Task-3 test-harness drift: the evidence fixture
still constructed uppercase pre-refresh PRBD rows, and its generic session paired the
new registry snapshot with the intentionally not-yet-rebuilt July artifact fixture. The
Task-3-listed evidence test now constructs refreshed rows and explicitly issues a
candidate registry session without altering any artifact. The final required bundle was:

```text
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest tests/unit/data/normalization/test_bonds.py tests/unit/quality/test_state_policy.py tests/unit/query/test_field_registry.py tests/unit/query/test_query_ast.py tests/unit/query/test_sql_compiler.py tests/unit/planner tests/unit/evidence/test_builder.py tests/source_contract/test_official_domestic_normalization.py -q
```

GREEN: `111 passed in 54.26s`.

Scoped static verification after mechanical formatting/import cleanup:

- `uv run ruff format --check <17 Task 3 Python files>` — `17 files already formatted`.
- `uv run ruff check <17 Task 3 Python files>` — `All checks passed!`.
- `uv run mypy <17 Task 3 Python files>` — `Success: no issues found in 17 source files`.
- `git diff --check` — PASS with no output.
- Post-static focused regression:
  `uv run pytest tests/unit/data/normalization/test_bonds.py tests/unit/planner/test_rule_fallback.py tests/unit/evidence/test_builder.py -q`
  — `63 passed in 2.32s`.

No full-repository pytest, Ruff, or mypy gate was run at this intermediate checkpoint.

## Preserved user state and remaining work

All user-owned `artifacts/evaluation/**`, PDFs, and `evaluation/review_batches/**` were
left byte-for-byte untouched and unstaged. No closure/status document was changed.

No unresolved Task 3 contract risk or official question remains. Legacy artifact table
specs and old golden/evaluation fixtures still mention quantity because their migration
is explicitly owned by Task 6 and later evaluation-refresh work; they were not broadened
into this checkpoint. The exact next implementation checkpoint is Task 4, refreshed
domestic/overseas listed-product normalization.
