# Deterministic Query Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete deterministic core from validated QueryPlan through product results, policy decisions, evidence, verified claims, and stable Korean answers without requiring HyperCLOVA X.

**Architecture:** Typed registries define legal fields, metrics, states, ratings, and answer policies. An entity resolver and semantic validator create a validated plan; an allowlisted AST compiler executes against read-only DuckDB. Quality/comparability policy shapes results, evidence proves claims, and a verifier gates the deterministic renderer.

**Tech Stack:** Python 3.12, Pydantic, PyYAML, DuckDB, RapidFuzz, Decimal, pytest/Hypothesis, Ruff, mypy.

## Global Constraints

- Phase 1 gate must pass and artifacts must be read-only.
- No LLM, FastAPI, or transport type is required in this phase.
- No user/model string becomes an SQL identifier.
- Fuzzy matches are candidates only.
- Every numeric/comparative answer claim must have evidence.
- All policy that changes results comes from versioned registries and tested code.
- Strict TDD and independently reviewable commits are mandatory.

---

### Task 1: Define query/evidence domain models and validated registry loading

**Files:**
- Create: `src/finproof/domain/query_plan.py`
- Create: `src/finproof/domain/evidence.py`
- Create: `src/finproof/domain/execution.py`
- Create: `src/finproof/domain/answers.py`
- Create: `src/finproof/registry/models.py`
- Create: `src/finproof/registry/loader.py`
- Create: `src/finproof/registry/metric.py`
- Create: `src/finproof/registry/state.py`
- Create: `src/finproof/registry/quality.py`
- Create: `src/finproof/registry/answer.py`
- Create: `tests/unit/domain/test_query_plan_models.py`
- Create: `tests/unit/domain/test_evidence_models.py`
- Create: `tests/unit/registry/test_registry_loader.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `QueryPlan.model_validate_json(payload: str) -> QueryPlan`
- Produces: `ValidatedQueryPlan` immutable internal model
- Produces: `ExecutionSegment`, `ExecutionBundle`, `ComparisonPartition`, and `TopKScope`
- Produces: `EvidenceRecord`, `ExecutionTrace`, `ExecutionResult`, `AnswerDraft`, `VerifiedAnswer`
- Produces: `RegistryBundle.load(config_dir: Path) -> RegistryBundle`
- Registry bundle exposes `datasets`, `metrics`, `states`, `quality`, `ratings`, `answers`, and immutable `VersionBundle`

- [ ] **Step 1: Write failing QueryPlan schema tests**

```python
import pytest
from pydantic import ValidationError

from finproof.domain.query_plan import Intent, ProductType, QueryPlan, ResultGrain, TopKScope


def test_query_plan_parses_minimal_screen_rank() -> None:
    plan = QueryPlan.model_validate(
        {
            "intent": "screen_rank",
            "product_types": ["domestic_bond"],
            "entities": [],
            "as_of_date": "2026-07-11",
            "result_grain": "instrument",
            "filters": [{"field": "credit_rating", "operator": "gte", "value": "AA-"}],
            "metrics": ["buy_yield"],
            "sort": [{"field": "buy_yield", "direction": "desc"}],
            "top_k": 5,
            "top_k_scope": "global",
            "needs_clarification": False,
            "clarification_reason": "",
        }
    )
    assert plan.intent is Intent.SCREEN_RANK
    assert plan.product_types == (ProductType.DOMESTIC_BOND,)
    assert plan.result_grain is ResultGrain.INSTRUMENT
    assert plan.top_k_scope is TopKScope.GLOBAL
```

Add tests that reject unknown top-level fields, unknown intent/product/grain/operator/direction/top-k scope, duplicate product types, top-k below one, filters with missing values, and clarification marked true with an empty reason. Add a model test proving `result_grain=product` is representable but is not executable until semantic segmentation.

- [ ] **Step 2: Run and observe RED**

```bash
uv run pytest tests/unit/domain/test_query_plan_models.py -q
```

- [ ] **Step 3: Implement frozen Pydantic models**

Use `ConfigDict(extra="forbid", frozen=True)`. Model `FilterValue` as a constrained JSON scalar/list/range shape; do not use arbitrary Python objects. Preserve user/model field names as strings for later registry validation rather than turning them into SQL. `ExecutionSegment` records one product type, its native grain, typed clauses, top-k, comparison partition, and evidence requirements. `ExecutionBundle` stores the validated plan, ordered segments, response-envelope grain, partitions, assumptions, and versions.

- [ ] **Step 4: Run QueryPlan tests to green**

```bash
uv run pytest tests/unit/domain/test_query_plan_models.py -q
```

- [ ] **Step 5: Write failing evidence and registry tests**

```python
from decimal import Decimal

from finproof.domain.evidence import EvidenceRecord, SourceLocator


def test_evidence_keeps_raw_normalized_and_rule() -> None:
    record = EvidenceRecord(
        evidence_id="E1",
        claim_id="C1",
        product_id="P1",
        metric_id="total_fee",
        source=SourceLocator(
            table_id="PREF02N001",
            file_name="file.xlsx",
            sheet_name="datarows",
            excel_row_number=10,
            column_name="cu_charge_rt",
        ),
        raw_value="0.250000",
        normalized_value=Decimal("0.25"),
        unit="percent",
        quality_status="valid",
        transformation_rule="decimal.v1",
    )
    assert record.raw_value == "0.250000"
    assert record.normalized_value == Decimal("0.25")
```

```python
from pathlib import Path

from finproof.registry.loader import RegistryBundle


def test_seed_registries_load_and_versions_match() -> None:
    bundle = RegistryBundle.load(Path("config"))
    assert bundle.metrics["overseas_etf.total_fee"].source_column == "cu_charge_rt"
    assert bundle.states["domestic_listed.active_at_as_of"].version == "1.0.0"
    assert bundle.versions.dataset_version.isoformat() == "2026-07-11"
```

- [ ] **Step 6: Run RED, implement typed registries, and rerun**

```bash
uv run pytest tests/unit/domain/test_evidence_models.py tests/unit/registry/test_registry_loader.py -q
```

Load YAML with safe loading. Validate unique IDs, required operation policies, source table/column references, legal quality states, complete rating order, cross references, and version format. Reject a metric missing rank/tie policy rather than supplying hidden defaults.

```bash
uv run pytest tests/unit/domain/test_evidence_models.py tests/unit/registry/test_registry_loader.py -q
```

- [ ] **Step 7: Run task quality and commit**

```bash
uv run ruff check src/finproof/domain src/finproof/registry tests/unit/domain tests/unit/registry
uv run mypy src/finproof/domain src/finproof/registry tests/unit/domain tests/unit/registry
uv run pytest tests/unit/domain tests/unit/registry -q
```

```bash
git add src/finproof/domain src/finproof/registry tests/unit/domain tests/unit/registry docs/implementation/STATUS.md
git commit -m "feat: define FinProof plans evidence and registries"
```

---

### Task 2: Implement deterministic entity resolution and exact links

**Files:**
- Create: `src/finproof/entity/__init__.py`
- Create: `src/finproof/entity/normalization.py`
- Create: `src/finproof/entity/models.py`
- Create: `src/finproof/entity/index.py`
- Create: `src/finproof/entity/resolver.py`
- Create: `src/finproof/entity/cross_source.py`
- Create: `tests/unit/entity/test_normalization.py`
- Create: `tests/unit/entity/test_resolver.py`
- Create: `tests/integration/entity/test_official_resolution.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `normalize_product_text(value: str) -> str`
- Produces: `EntityIndex.build(connection, registry_bundle) -> EntityIndex`
- Produces: `EntityResolver.resolve(mention: EntityMention, product_types: tuple[ProductType, ...]) -> ResolutionResult`
- Resolution statuses: `exact_id`, `exact_alias`, `unique_normalized_name`, `candidate_list`, `not_found`, `ambiguous`
- Produces: `ExactCrossSourceLinkRepository`

- [ ] **Step 1: Write failing normalization tests**

```python
from finproof.entity.normalization import normalize_product_text


def test_product_normalization_is_conservative_and_stable() -> None:
    assert normalize_product_text("  KODEX  200  ") == "kodex 200"
    assert normalize_product_text("KODEX-200") == "kodex 200"
    assert normalize_product_text("A069500") == "a069500"
```

Do not strip digits, share-class letters, leverage/inverse terms, currency markers, or maturity information.

- [ ] **Step 2: Run RED, implement normalization, rerun**

```bash
uv run pytest tests/unit/entity/test_normalization.py -q
```

Use Unicode normalization, case fold, whitespace collapse, and a narrow punctuation mapping. Keep a test table for Korean brackets and common ticker separators.

- [ ] **Step 3: Write failing resolver priority and no-auto-merge tests**

```python
from finproof.entity.models import EntityMention, ResolutionStatus


def test_exact_identifier_beats_fuzzy_name(entity_resolver) -> None:
    result = entity_resolver.resolve(
        EntityMention(text="A069500", identifier_type="market_identifier"),
        product_types=(ProductType.DOMESTIC_ETF,),
    )
    assert result.status is ResolutionStatus.EXACT_ID
    assert result.selected.product_id == "KR7069500007"
```

```python
def test_fuzzy_candidates_are_never_selected_automatically(entity_resolver) -> None:
    result = entity_resolver.resolve(
        EntityMention(text="kodex 비슷한 이름"),
        product_types=(ProductType.DOMESTIC_ETF,),
    )
    assert result.status in {ResolutionStatus.CANDIDATE_LIST, ResolutionStatus.AMBIGUOUS}
    assert result.selected is None
```

- [ ] **Step 4: Run RED and implement the resolver pipeline**

```bash
uv run pytest tests/unit/entity/test_resolver.py -q
```

Resolution order is exact product ID, ISIN/ticker/market ID, exact normalized alias, unique normalized name, candidate list. Candidate scores and reasons are returned, but selection remains null unless deterministic rules resolve exactly.

- [ ] **Step 5: Add official integration tests**

```python
@pytest.mark.integration
def test_official_exact_link_repository_contains_47_links(read_only_db) -> None:
    repo = ExactCrossSourceLinkRepository(read_only_db)
    assert repo.count() == 47
    assert all(link.link_type == "exact_identifier" for link in repo.list_all())
```

Add one known official exact identifier/name lookup and an ambiguous normalized-name fixture.

- [ ] **Step 6: Run task suite and commit**

```bash
uv run pytest tests/unit/entity tests/integration/entity -q
uv run ruff check src/finproof/entity tests/unit/entity tests/integration/entity
uv run mypy src/finproof/entity tests/unit/entity tests/integration/entity
```

```bash
git add src/finproof/entity tests/unit/entity tests/integration/entity docs/implementation/STATUS.md
git commit -m "feat: add controlled financial product resolution"
```

---

### Task 3: Implement semantic validation, allowlisted AST, and parameterized SQL compiler

**Files:**
- Create: `src/finproof/query/__init__.py`
- Create: `src/finproof/query/fields.py`
- Create: `src/finproof/query/semantic_validator.py`
- Create: `src/finproof/query/segmenter.py`
- Create: `src/finproof/query/ast.py`
- Create: `src/finproof/query/compiler.py`
- Create: `tests/unit/query/test_field_registry.py`
- Create: `tests/unit/query/test_semantic_validator.py`
- Create: `tests/unit/query/test_execution_bundle.py`
- Create: `tests/unit/query/test_sql_compiler.py`
- Create: `tests/security/test_query_injection.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `FieldRegistry.from_bundle(registries: RegistryBundle) -> FieldRegistry`
- Produces: `SemanticValidator.validate(plan: QueryPlan, context: ValidationContext) -> ValidatedQueryPlan`
- Produces: `ExecutionBundleBuilder.build(plan: ValidatedQueryPlan, context: ValidationContext) -> ExecutionBundle`
- Produces: `QueryAst.from_segment(segment: ExecutionSegment) -> QueryAst`
- Produces: `CompiledQuery(sql: str, parameters: tuple[object, ...], evidence_fields: tuple[str, ...])`
- Produces: `SqlCompiler.compile(ast: QueryAst) -> CompiledQuery`

- [ ] **Step 1: Write failing semantic validation tests**

```python
import pytest

from finproof.query.semantic_validator import SemanticValidationError


def test_etf_grain_and_field_are_valid(validator, domestic_etf_plan) -> None:
    validated = validator.validate(domestic_etf_plan, validation_context())
    assert validated.result_grain is ResultGrain.LISTED_PRODUCT


def test_public_fund_source_attribute_grain_is_rejected_for_rank(validator, public_fund_rank_plan) -> None:
    invalid = public_fund_rank_plan.model_copy(update={"result_grain": "fund_attribute"})
    with pytest.raises(SemanticValidationError, match="fund_item"):
        validator.validate(invalid, validation_context())
```

Add tests for unknown field, illegal operator, wrong value type, missing return period, cross-currency integrated AUM request, top-k cap, unsupported metric, clarification plan bypass, and invalid product/native-grain combinations. Add the following segmentation tests:

```python
def test_heterogeneous_product_envelope_builds_native_segments(validator, bundle_builder, mixed_plan) -> None:
    validated = validator.validate(mixed_plan, validation_context())
    bundle = bundle_builder.build(validated, validation_context())
    assert validated.result_grain is ResultGrain.PRODUCT
    assert bundle.top_k_scope is TopKScope.PER_PRODUCT_TYPE
    assert [(segment.product_type, segment.native_result_grain) for segment in bundle.segments] == [
        (ProductType.DOMESTIC_BOND, ResultGrain.INSTRUMENT),
        (ProductType.DOMESTIC_ETF, ResultGrain.LISTED_PRODUCT),
        (ProductType.PUBLIC_FUND, ResultGrain.FUND_ITEM),
    ]
    assert all(segment.top_k == 3 for segment in bundle.segments)
```

```python
def test_incompatible_global_rank_requires_split_or_clarification(validator, bundle_builder, cross_currency_aum_plan) -> None:
    validated = validator.validate(cross_currency_aum_plan, validation_context())
    with pytest.raises(SemanticValidationError, match="top_k_scope"):
        bundle_builder.build(validated, validation_context())
```

Also test that a clause is distributed only to product types where its registry mapping is valid, a clause with no valid target fails closed, and heterogeneous result rows preserve native grain and evidence.

- [ ] **Step 2: Run RED and implement field registry/validator**

```bash
uv run pytest tests/unit/query/test_field_registry.py tests/unit/query/test_semantic_validator.py tests/unit/query/test_execution_bundle.py -q
```

The validator returns typed filters and policy IDs. It may inject safe defaults and assumptions but cannot silently change a literal user condition. The bundle builder creates one segment per product type, maps clauses through the registry, preserves deterministic product-type order, records every split, and permits a global rank only for one registered compatibility partition.

- [ ] **Step 3: Write failing compiler and injection tests**

```python
def test_compiler_uses_parameters_for_values(compiler, validated_bond_plan) -> None:
    segment = bundle_builder.build(validated_bond_plan, validation_context()).segments[0]
    compiled = compiler.compile(QueryAst.from_segment(segment))
    assert "AA-" not in compiled.sql
    assert "?" in compiled.sql
    assert "AA-" in compiled.parameters
```

```python
@pytest.mark.parametrize(
    "field",
    ["name; drop table silver_fund_item", "pd_nm --", "1=1"],
)
def test_unregistered_field_never_reaches_sql(field, validator, plan_factory) -> None:
    with pytest.raises(SemanticValidationError):
        validator.validate(plan_factory(field=field), validation_context())
```

- [ ] **Step 4: Run RED and implement closed AST/compiler**

```bash
uv run pytest tests/unit/query/test_sql_compiler.py tests/security/test_query_injection.py -q
```

AST nodes are typed enums/dataclasses. SQL column/expression functions are authored in `fields.py`; identifiers never come from plan text. A compiler accepts exactly one native segment and cannot compile `result_grain=product` directly. Use deterministic null ordering and append product ID as final stable sort only for display/order stability after semantic tie policy.

- [ ] **Step 5: Run task quality and commit**

```bash
uv run pytest tests/unit/query tests/security/test_query_injection.py -q
uv run ruff check src/finproof/query tests/unit/query tests/security
uv run mypy src/finproof/query tests/unit/query tests/security
```

```bash
git add src/finproof/query tests/unit/query tests/security docs/implementation/STATUS.md
git commit -m "feat: validate plans and compile allowlisted SQL"
```

---

### Task 4: Implement repositories, executor, instrumentation, and differential reference

**Files:**
- Create: `src/finproof/storage/repositories/__init__.py`
- Create: `src/finproof/storage/repositories/products.py`
- Create: `src/finproof/query/executor.py`
- Create: `src/finproof/query/reference.py`
- Create: `tests/integration/query/test_executor.py`
- Create: `tests/differential/test_query_differential.py`
- Create: `tests/property/test_query_metamorphic.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `ProductRepository.execute(compiled: CompiledQuery) -> tuple[ResultRow, ...]`
- Produces: `QueryExecutor.execute(bundle: ExecutionBundle) -> RawExecutionResult`
- Produces: `ReferenceExecutor.execute(fixture_rows, bundle: ExecutionBundle) -> RawExecutionResult`
- `RawExecutionResult` includes ordered segment results, compatibility partitions, stage candidate counts, aggregate values, query timing, policy hooks, evidence locators, and the assembled response envelope

- [ ] **Step 1: Write failing lookup/screen/rank/aggregate executor tests**

```python
def test_rank_executor_returns_stable_top_k(executor, execution_bundle) -> None:
    result = executor.execute(execution_bundle)
    segment = result.segment_results[0]
    assert len(segment.rows) == execution_bundle.segments[0].top_k
    assert [row.product_id for row in segment.rows] == ["P3", "P2", "P1"]
    assert segment.candidate_counts["after_filters"] == 3
```

Add fixtures for lookup, two filters, ascending/descending, count, average with Decimal, no-result, heterogeneous per-product top-k, same-grain multi-type results, and currency-separated partitions.

- [ ] **Step 2: Run RED and implement repository/executor**

```bash
uv run pytest tests/integration/query/test_executor.py -q
```

Use one read-only connection/request boundary and an explicit transaction where supported. Execute each segment independently in deterministic order, convert database decimal/date values into domain types, and assemble the envelope only after policy partitioning. Record candidate counts per segment through explicit count queries or CTE instrumentation, not by parsing SQL text.

- [ ] **Step 3: Write failing differential tests**

```python
@pytest.mark.parametrize("case", load_deterministic_query_cases())
def test_duckdb_matches_reference(case, executor, reference_executor) -> None:
    production = executor.execute(case.execution_bundle)
    reference = reference_executor.execute(case.fixture_rows, case.execution_bundle)
    assert production.comparable_projection() == reference.comparable_projection()
```

- [ ] **Step 4: Implement the simple reference executor**

The reference implementation uses typed Python comparisons over fixture records, not production SQL/compiler helpers. It supports the frozen operator/metric subset used by differential cases and fails explicitly for unsupported constructs.

- [ ] **Step 5: Add metamorphic property tests**

```python
@given(thresholds=st.lists(st.decimals(min_value=0, max_value=100), min_size=2, max_size=8, unique=True))
def test_more_restrictive_minimum_cannot_increase_count(thresholds, plan_factory, reference_executor) -> None:
    ordered = sorted(thresholds)
    counts = [reference_executor.execute(FIXTURE_ROWS, plan_factory(minimum=x)).total for x in ordered]
    assert counts == sorted(counts, reverse=True)
```

Also test stable ID/ticker aliases and order reversal for unique values.

- [ ] **Step 6: Run task checks and commit**

```bash
uv run pytest tests/integration/query tests/differential tests/property/test_query_metamorphic.py -q
uv run ruff check src/finproof/query src/finproof/storage/repositories tests/integration/query tests/differential tests/property
uv run mypy src/finproof/query src/finproof/storage/repositories tests/integration/query tests/differential tests/property
```

```bash
git add src/finproof/query src/finproof/storage/repositories tests/integration/query tests/differential tests/property docs/implementation/STATUS.md
git commit -m "feat: execute deterministic financial queries"
```

---

### Task 5: Implement state, metric, comparability, tie, and conditional dual-lens policy

**Files:**
- Create: `src/finproof/quality/__init__.py`
- Create: `src/finproof/quality/state.py`
- Create: `src/finproof/quality/metric_policy.py`
- Create: `src/finproof/quality/comparability.py`
- Create: `src/finproof/quality/ties.py`
- Create: `src/finproof/quality/dual_lens.py`
- Create: `tests/unit/quality/test_state_policy.py`
- Create: `tests/unit/quality/test_metric_operation_policy.py`
- Create: `tests/unit/quality/test_comparability.py`
- Create: `tests/unit/quality/test_ties.py`
- Create: `tests/integration/quality/test_official_quality_cases.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `StatePolicy.evaluate(product, as_of: date) -> StateEvaluation`
- Produces: `MetricPolicy.apply(operation: Operation, values: Sequence[MetricValue]) -> MetricPolicyResult`
- Produces: `ComparabilityEngine.check(request: ComparisonRequest) -> ComparabilityDecision`
- Produces: `TieAnalyzer.analyze(rows, primary_metric) -> TieResult`
- Produces: `DualLensEngine.apply(raw_result, policies) -> PolicyExecutionResult`

- [ ] **Step 1: Write failing critical state tests**

```python
def test_domestic_listed_zero_suspension_flag_is_not_suspended(state_policy, domestic_etf) -> None:
    product = domestic_etf(sale_flag="1", suspension_flag="0", listing_end="99991231")
    state = state_policy.evaluate(product, date(2026, 7, 11))
    assert state.eligible is True
    assert state.trade_suspended is False
```

```python
def test_positive_bond_quantity_matured_before_as_of_is_not_validated_buyable(state_policy, bond) -> None:
    product = bond(quantity="100", maturity=date(2026, 7, 10))
    state = state_policy.evaluate(product, date(2026, 7, 11))
    assert state.source_buyable is True
    assert state.validated_buyable is False
```

- [ ] **Step 2: Run RED and implement product-specific state policies**

```bash
uv run pytest tests/unit/quality/test_state_policy.py -q
```

No universal boolean parser may infer the meaning of product-specific flags.

- [ ] **Step 3: Write failing operation-specific zero/tie tests**

```python
def test_overseas_fee_zero_is_displayed_but_separated_for_comparison_rank(metric_policy, fee_values) -> None:
    display = metric_policy.apply(Operation.DISPLAY, fee_values)
    rank = metric_policy.apply(Operation.RANK, fee_values)
    assert display.values_by_product["ZERO"] == Decimal("0")
    assert "ZERO" in rank.recorded_value_group
    assert "ZERO" not in rank.comparison_valid_group
    assert rank.warning_code == "recorded_zero_unverified"
```

```python
def test_constant_tracking_error_is_joint_rank(tie_analyzer, tracking_rows) -> None:
    result = tie_analyzer.analyze(tracking_rows, "tracking_error")
    assert result.all_primary_values_tied is True
    assert set(result.primary_rank_by_product.values()) == {1}
```

- [ ] **Step 4: Implement metric/tie/dual-lens policies and rerun**

```bash
uv run pytest tests/unit/quality/test_metric_operation_policy.py tests/unit/quality/test_ties.py -q
```

Policies must report included/excluded counts and rule IDs. Secondary display order never changes primary tie rank.

- [ ] **Step 5: Write failing comparability tests**

```python
def test_krw_and_usd_aum_require_separation(comparability_engine) -> None:
    decision = comparability_engine.check(aum_request(currencies={"KRW", "USD"}))
    assert decision.is_directly_comparable is False
    assert decision.action is ComparisonAction.SEPARATE_BY_CURRENCY
```

Add bond-yield vs historical-return rejection, missing return-period clarification, and same-period ETF/fund return with caveat.

- [ ] **Step 6: Implement comparability and run official quality integration cases**

```bash
uv run pytest tests/unit/quality tests/integration/quality/test_official_quality_cases.py -q
```

Official integration cases must assert the frozen counts/tie groups for 325/254 bonds, domestic tracking zeroes, overseas fee zeroes, overseas one-day return zeroes, and public-fund currency groups.

- [ ] **Step 7: Commit**

```bash
git add src/finproof/quality tests/unit/quality tests/integration/quality docs/implementation/STATUS.md
git commit -m "feat: enforce financial state and comparability policies"
```

---

### Task 6: Build evidence, claim verification, deterministic Korean rendering, and core service

**Files:**
- Create: `src/finproof/evidence/__init__.py`
- Create: `src/finproof/evidence/builder.py`
- Create: `src/finproof/evidence/serializer.py`
- Create: `src/finproof/evidence/verifier.py`
- Create: `src/finproof/answer/__init__.py`
- Create: `src/finproof/answer/templates.py`
- Create: `src/finproof/answer/renderer.py`
- Create: `src/finproof/answer/safety.py`
- Create: `src/finproof/service/__init__.py`
- Create: `src/finproof/service/answer_service.py`
- Create: `tests/unit/evidence/test_builder.py`
- Create: `tests/unit/evidence/test_claim_verifier.py`
- Create: `tests/unit/answer/test_renderer.py`
- Create: `tests/integration/service/test_answer_service.py`
- Create: `tests/golden/test_seed_answer_semantics.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `EvidenceBuilder.build(plan, policy_result) -> EvidenceBundle`
- Produces: `EvidenceSerializer.to_context_string(bundle, byte_limit: int) -> str`
- Produces: `ClaimVerifier.verify(draft: AnswerDraft, evidence: EvidenceBundle) -> VerifiedAnswer`
- Produces: `DeterministicRenderer.render(context: RenderContext) -> AnswerDraft`
- Produces: `AnswerService.answer_plan(request: AnswerRequest, plan: QueryPlan) -> AnswerResult`

- [ ] **Step 1: Write failing evidence coverage tests**

```python
def test_rank_claim_has_product_values_count_and_rule_evidence(evidence_builder, ranked_policy_result) -> None:
    bundle = evidence_builder.build(ranked_policy_result.plan, ranked_policy_result)
    assert bundle.coverage.required_claims == bundle.coverage.supported_claims
    assert bundle.find_claim("rank:1").evidence_ids
    assert bundle.find_claim("candidate_count:after_filters").evidence_ids
```

- [ ] **Step 2: Run RED and implement evidence builder/serializer**

```bash
uv run pytest tests/unit/evidence/test_builder.py -q
```

Evidence for derived values includes formula/rule inputs and as-of date. Context serialization is stable, compact, JSON-safe, size-bounded, and contains no local path.

- [ ] **Step 3: Write failing verifier fail-closed tests**

```python
import pytest

from finproof.evidence.verifier import UnsupportedClaimError


def test_verifier_rejects_numeric_claim_without_evidence(verifier, draft_without_evidence, evidence_bundle) -> None:
    with pytest.raises(UnsupportedClaimError):
        verifier.verify(draft_without_evidence, evidence_bundle)
```

Add tests for wrong product ID, changed decimal, false comparison sign, unsupported “best investment,” and omitted material limitation.

- [ ] **Step 4: Implement structured claims and verifier**

Do not parse arbitrary prose to recover every number. The renderer creates structured `AnswerClaim` objects first; text is a projection. The verifier checks claim payloads against evidence and policy decisions before producing `VerifiedAnswer`.

```bash
uv run pytest tests/unit/evidence/test_claim_verifier.py -q
```

- [ ] **Step 5: Write failing Korean renderer behavior tests**

```python
def test_current_answer_names_snapshot(renderer, normal_context) -> None:
    draft = renderer.render(normal_context.with_assumption("current_as_snapshot"))
    assert "2026-07-11" in draft.text
    assert "실시간" not in draft.text
```

```python
def test_recommendation_request_is_rendered_as_condition_matching_candidates(renderer, recommendation_context) -> None:
    draft = renderer.render(recommendation_context)
    assert "조건에 부합하는 후보" in draft.text
    assert "무조건" not in draft.text
```

Add normal table, joint tie, dual-lens, separate currency, no result, unsupported metric, clarification, and source footer cases.

- [ ] **Step 6: Implement deterministic templates and safety**

Render from structured rows/claims. Format Decimal/date/unit deterministically. Keep table row count capped. Use Korean labels `제공 데이터 기록값` and `비교 가능 기준` only when policy result requests them.

```bash
uv run pytest tests/unit/answer/test_renderer.py -q
```

- [ ] **Step 7: Integrate the HCX-independent AnswerService**

The service accepts a `QueryPlan`, validates/resolves/compiles/executes/applies policy/builds evidence/renders/verifies, and returns `AnswerResult` with context string, trace, and text.

```python
def test_service_returns_verified_answer_and_reproducible_trace(answer_service, valid_plan) -> None:
    result = answer_service.answer_plan(AnswerRequest(question_id="Q1", question="질문"), valid_plan)
    assert result.verified is True
    assert "validation=passed" in result.execution_trace.to_compact_string()
    assert result.retrieved_context.startswith("{")
```

- [ ] **Step 8: Run Phase 2 gate**

```bash
uv run pytest -q tests/unit/domain tests/unit/registry tests/unit/entity tests/unit/query tests/unit/quality tests/unit/evidence tests/unit/answer tests/integration/query tests/integration/quality tests/integration/service tests/differential tests/property tests/security tests/golden/test_seed_answer_semantics.py
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

- [ ] **Step 9: Update status and commit**

```bash
git add src/finproof/evidence src/finproof/answer src/finproof/service tests docs/implementation/STATUS.md
git commit -m "feat: render and verify evidence-backed answers"
```
