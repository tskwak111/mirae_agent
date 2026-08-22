# Deterministic Query Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the HCX-independent deterministic core from strict QueryPlan validation through verified artifact retrieval, policy, evidence, claim verification, and stable Korean answers.

**Architecture:** One expected-verified `RuntimeArtifactSession` owns the immutable registry bundle, issued versions, and read-only DuckDB connection. Resolution and semantic validation create native execution segments; repositories return bounded pre-policy rows; one policy pipeline applies eligibility, metric policy, compatibility partitions, aggregate or rank/tie calculation, and final top-k. Evidence reuses Phase 1 lineage/value models and the deterministic renderer projects only verified structured claims.

**Tech Stack:** Python 3.12, Pydantic, DuckDB, PyYAML, RapidFuzz, Decimal, pytest/Hypothesis, Ruff, mypy.

**Spec:** `docs/05_QUERYPLAN_AND_API_CONTRACT.md`, governed by D-027 through D-030 in `docs/10_DECISION_LOG.md` and the frozen contracts in `docs/02_FINAL_FROZEN_DESIGN.md`, `docs/04_DATA_AND_DOMAIN_CONTRACTS.md`, and `docs/06_METRIC_REGISTRY_POLICY.md`.

## Global Constraints

- Phase 1 remains closed; do not change its 11-table artifact contract, expected logical bytes, source inputs, or publication behavior.
- Production runtime accepts only the expected-verified published artifact and packaged byte-identical registries.
- Reuse `SourceCellLocator`, normalized/derived value models, `RatingRegistry`, canonical wide `record_json`, `TABLE_SPECS`, and Phase 1 artifact verification. Do not create parallel DTOs or a second artifact format.
- No model/user string becomes SQL, an SQL identifier, or an automatic fuzzy merge.
- The fixed execution order is resolution/literal filtering → state and metric eligibility → compatibility partitioning → aggregate or rank/tie → final top-k.
- Validated eligibility is limited to domestic bonds and domestic listed ETF/ETN. Overseas-listed and public-fund validated-eligibility requests fail closed.
- The 13 AI handoff seeds are semantic examples only, never canonical QueryPlans.
- Every behavior follows one focused RED → smallest GREEN cycle. A parameterized family is one selector only when every case exercises the same production branch.
- If a later selector is already GREEN because an earlier minimum implementation entails it, record it as a derived first-GREEN acceptance. Do not manufacture a failure or weaken an earlier implementation.
- Run focused tests per behavior and one task aggregate/static gate per completed task. Do not run the full repository gate before the final unchanged candidate.
- Do not update `docs/implementation/STATUS.md` or plan checkboxes during implementation. Update closure docs once after final 0 Critical / 0 Important review.
- Commit Tasks 1–6 separately. Review the whole Phase 2 candidate once; allow one focused correction/re-review round. Further findings are root-classified as direct frozen violation, backlog, or rejected over-hardening.

## Serial TDD Procedure

For every selector below:

1. Add only that named selector.
2. Run `uv run pytest <file>::<selector> -q` and observe the intended missing-behavior RED.
3. Implement the smallest shared-root change.
4. Rerun that selector and the immediately affected predecessor selector(s).
5. Record RED/GREEN output in `/private/tmp/finproof-phase2-red-green.md` and append the honest summary to `.superpowers/sdd/2026-08-21-phase2-deterministic-query-engine/task-report.md` before the final implementation commit.

Task aggregates may reuse the session-scoped official artifact cache. They must not rebuild the official artifact once per selector.

---

### Task 1: Canonical contracts, packaged registries, versions, and runtime session

**Files:**

- Create: `src/finproof/domain/query_plan.py`
- Create: `src/finproof/domain/evidence.py`
- Create: `src/finproof/domain/execution.py`
- Create: `src/finproof/domain/answers.py`
- Create: `src/finproof/registry/models.py`
- Create: `src/finproof/registry/resources.py`
- Create: `src/finproof/registry/loader.py`
- Create: `src/finproof/registry/metric.py`
- Create: `src/finproof/registry/state.py`
- Create: `src/finproof/registry/quality.py`
- Create: `src/finproof/registry/answer.py`
- Create: `src/finproof/registry/planner.py`
- Create: `src/finproof/runtime/__init__.py`
- Create: `src/finproof/runtime/session.py`
- Create: `tests/helpers/query_runtime.py`
- Create: `tests/unit/domain/test_query_plan_models.py`
- Create: `tests/unit/domain/test_evidence_models.py`
- Create: `tests/unit/registry/test_registry_loader.py`
- Create: `tests/unit/runtime/test_runtime_session.py`
- Create: `tests/contract/test_phase2_schemas.py`
- Create: `tests/contract/test_runtime_registry_resources.py`
- Modify: `src/finproof/core/versions.py`
- Modify: `src/finproof/data/artifacts/config.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Modify: `src/finproof/resources/__init__.py`
- Modify: `config/artifact_build.yaml`
- Modify: `config/expected_phase1_artifacts.json`
- Modify: `config/field_registry.yaml`
- Modify: `config/state_rules.yaml`
- Modify: `schemas/artifact_manifest.schema.json`
- Modify: `schemas/query_plan.schema.json`
- Modify: `schemas/evidence_record.schema.json`
- Modify: `tests/contract/test_artifact_resources.py`
- Modify: `tests/helpers/artifacts.py`
- Modify: `tests/integration/artifacts/test_bronze_fixture_build.py`
- Modify: `tests/unit/core/test_versions.py`
- Modify: `tests/unit/data/artifacts/test_foundations.py`
- Modify: `tools/verify_handoff.py`
- Modify: `pyproject.toml`

**Interfaces:**

```python
class AggregationFunction(StrEnum):
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    AVG = "avg"

class AggregationSpec(BaseModel):
    function: AggregationFunction
    field: str | None
    group_by: tuple[str, ...]

class QueryPlan(BaseModel):
    # frozen canonical fields from docs/05 plus aggregation
    aggregation: AggregationSpec | None

class RegistryBundle(BaseModel):
    @classmethod
    def from_package(cls) -> Self: ...

class VersionBundle(BaseModel):
    @classmethod
    def from_runtime(
        cls,
        *,
        verified: VerifiedArtifactSet,
        registries: RegistryBundle,
        execution_mode: ExecutionMode,
    ) -> Self: ...

@contextmanager
def open_runtime_artifact_session(settings: Settings) -> Iterator[RuntimeArtifactSession]: ...
```

`pyproject.toml` force-includes the eight existing config sources directly into `finproof/resources/registries/`; do not create copied YAML files. `RegistryBundle.from_package()` parses those resources with bounded duplicate-key-safe strict loaders and reuses the exact `RatingRegistry` class for ratings.

`RegistryBundle` and `VersionBundle` are frozen, direct-construction-disabled values. The version factory accepts only the exact loader-issued registry bundle and expected-verification-issued `VerifiedArtifactSet`; copied, subclassed, object-new, foreign, or value-equal reconstructions fail closed. `VersionBundle` keeps the official snapshot date and adds distinct `dataset_registry_version` and `field_registry_version` fields so all eight registry resources are version-bound. Because Task 1 changes field reachability/aggregate authorization and narrows validated state support, `config/field_registry.yaml` and `config/state_rules.yaml` each advance from `1.0.0` to `1.1.0`; callers cannot supply or default those values.

**Selectors — 21 mandatory nodes:**

1. `test_phase2_domain_contract_skeleton_exposes_exact_public_types`
2. `test_query_plan_accepts_one_complete_nonaggregate_plan_and_rejects_unknown_fields`
3. `test_filter_operator_variants_require_or_forbid_exact_value_shapes`
4. `test_query_plan_aggregation_cross_field_contract_is_exact`
5. `test_clarify_unsupported_and_product_envelope_cross_field_contracts`
6. `test_query_plan_json_schema_and_pydantic_accept_and_reject_the_same_fixture_family`
7. `test_direct_evidence_reuses_complete_source_cell_locator_and_normalized_value`
8. `test_derived_evidence_binds_inputs_rule_version_and_derived_as_of`
9. `test_evidence_summary_bounds_counts_policy_versions_and_artifact_hash`
10. `test_registry_bundle_skeleton_has_exact_eight_member_inventory`
11. `test_registry_resources_reject_duplicate_oversized_mutable_and_wrong_shape_documents`
12. `test_field_metric_and_planner_alias_reachability_is_complete`
13. `test_field_registry_aggregate_allowlists_match_targetless_count_contract`
14. `test_state_registry_contains_only_phase2_supported_validated_eligibility_rules`
15. `test_registry_bundle_reuses_exact_rating_registry_type`
16. `test_repository_and_package_registry_bytes_are_identical`
17. `test_evidence_record_schema_matches_exact_domain_model_family`
18. `test_version_bundle_has_no_defaults_and_is_issued_from_verified_runtime_facts`
19. `test_runtime_session_expected_verifies_before_declared_database_open_and_closes_once`
20. `test_runtime_session_rejects_foreign_registry_result_and_exposes_no_path_connection_or_sql`
21. `test_wheel_and_editable_install_load_identical_runtime_registry_resources`

Selector 12 closes the seven current unreachable metrics (`domestic_etf.return_ytd`, `overseas_etf.return_1d`, and public-fund 1w/18m/2y/3y/5y) and the canonical `risk_grade` field through `config/field_registry.yaml`. Selector 13 removes legacy field-target `count` authorization: D-027 count has no target and counts the native result grain, while group fields are validated separately against their product-type field registrations. Selector 14 removes the unsupported overseas/public-fund validated rules from `config/state_rules.yaml` and advances its version from `1.0.0` to `1.1.0`; their raw display fields remain registered. No registry lookup bypass is permitted.

**Task gate:**

```bash
uv run pytest -q tests/unit/domain/test_query_plan_models.py tests/unit/domain/test_evidence_models.py tests/unit/registry/test_registry_loader.py tests/unit/runtime/test_runtime_session.py tests/contract/test_phase2_schemas.py tests/contract/test_runtime_registry_resources.py
uv run ruff format --check src/finproof/domain src/finproof/registry src/finproof/runtime src/finproof/core/versions.py tests/unit/domain tests/unit/registry tests/unit/runtime tests/contract/test_phase2_schemas.py tests/contract/test_runtime_registry_resources.py
uv run ruff check src/finproof/domain src/finproof/registry src/finproof/runtime src/finproof/core/versions.py tests/unit/domain tests/unit/registry tests/unit/runtime tests/contract/test_phase2_schemas.py tests/contract/test_runtime_registry_resources.py
uv run mypy src/finproof/domain src/finproof/registry src/finproof/runtime src/finproof/core/versions.py tests/unit/domain tests/unit/registry tests/unit/runtime tests/contract/test_phase2_schemas.py tests/contract/test_runtime_registry_resources.py
```

**Commit:** stage exactly the Task 1 file map and commit `feat: freeze Phase 2 runtime contracts`.

---

### Task 2: Deterministic entity resolution and exact-link access

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

**Interfaces:**

```python
def normalize_product_text(value: str) -> str: ...

class EntityIndex:
    @classmethod
    def from_session(cls, session: RuntimeArtifactSession) -> Self: ...

class EntityResolver:
    def resolve(
        self,
        mention: EntityMention,
        *,
        product_types: tuple[ProductType, ...],
    ) -> ResolutionResult: ...

class ExactCrossSourceLinkRepository:
    def __init__(self, session: RuntimeArtifactSession) -> None: ...
```

The exact index sources are closed: bond ID/name/short name; domestic-listed ID/market ID/name/short name; overseas-listed ID/market ID/ISIN/ticker/name; fund item ID/KSD ID/standard ID/name/short name. Exact identifiers outrank exact aliases/names. Fuzzy output is a deterministic top-five candidate list ordered by descending score, product-type order, then product ID; it never selects or links automatically.

**Selectors — 12 mandatory nodes:**

1. `test_entity_module_skeleton_exposes_exact_types`
2. `test_product_text_normalization_is_conservative_and_stable`
3. `test_entity_index_uses_only_closed_silver_projection_sources`
4. `test_exact_product_identifier_beats_every_other_match`
5. `test_exact_market_isin_ticker_and_alias_priority_is_deterministic`
6. `test_unique_normalized_name_selects_only_within_requested_product_types`
7. `test_fuzzy_candidates_are_top_five_deterministic_and_never_selected`
8. `test_ambiguous_exact_name_returns_no_selected_product`
9. `test_unresolved_identifier_is_not_found_without_fuzzy_promotion`
10. `test_exact_link_repository_exposes_only_gold_exact_identifier_links`
11. `test_entity_and_link_surfaces_accept_runtime_session_not_connection_path_or_sql`
12. `test_official_resolution_and_exact_link_profile_is_47`

**Task gate:**

```bash
uv run pytest -q tests/unit/entity tests/integration/entity
uv run ruff format --check src/finproof/entity tests/unit/entity tests/integration/entity
uv run ruff check src/finproof/entity tests/unit/entity tests/integration/entity
uv run mypy src/finproof/entity tests/unit/entity tests/integration/entity
```

**Commit:** stage exactly the Task 2 file map and commit `feat: add controlled product resolution`.

---

### Task 3: Semantic validation, native segmentation, and closed SQL compilation

**Files:**

- Modify: `src/finproof/domain/execution.py`
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
- Create: `tests/integration/query/test_official_semantic_validation.py`

**Interfaces:**

```python
class FieldRegistry:
    @classmethod
    def from_bundle(cls, registries: RegistryBundle) -> Self: ...

class SemanticValidator:
    def validate(
        self,
        plan: QueryPlan,
        *,
        resolutions: ResolutionBundle,
        context: ValidationContext,
    ) -> ValidatedQueryPlan: ...

class ExecutionBundleBuilder:
    def build(
        self,
        plan: ValidatedQueryPlan,
        *,
        context: ValidationContext,
    ) -> ExecutionBundle: ...

class SqlCompiler:
    def compile(self, ast: QueryAst) -> CompiledQuery: ...
```

The compiler returns bounded pre-policy projections only. Aggregate functions, final ranking, ties, compatibility partitioning, and final top-k are not compiled here; Task 5 owns them after policy eligibility. Aggregate plans compile the raw target/group/policy/evidence fields required by the later pipeline.

**Selectors — 12 mandatory RED→GREEN nodes plus 6 derived first-GREEN acceptances:**

1. `test_query_module_skeleton_exposes_exact_interfaces`
2. `test_field_registry_maps_every_canonical_field_to_closed_table_spec_projection`
3. `test_semantic_validator_rejects_unknown_field_operator_and_value_type_family`
4. `test_resolutions_are_retained_by_identity_and_candidate_or_ambiguous_status_fails_closed`
5. `test_product_type_and_native_grain_contract_is_exact`
6. `test_overseas_and_public_fund_validated_eligibility_requests_fail_closed`
7. `test_heterogeneous_product_envelope_builds_ordered_native_segments`
8. `test_clause_distribution_targets_only_registered_product_types_and_zero_targets_fail`
9. `test_global_scope_requires_one_compatible_partition_for_rank_and_aggregate`
10. `test_per_product_type_scope_records_each_required_compatibility_split`
11. `test_aggregation_target_group_and_operation_are_registry_authorized`
12. `test_query_ast_accepts_one_native_segment_and_rejects_product_envelope`
13. `test_sql_compiler_parameterizes_every_value_and_uses_closed_identifiers`
14. `test_contains_and_starts_with_treat_wildcards_controls_and_unicode_as_literal_data`
15. `test_compiler_projects_aggregate_inputs_without_prepolicy_aggregation_or_top_k`
16. `test_compiler_uses_deterministic_null_and_product_id_ordering_only_as_display_stability`
17. `test_query_injection_family_never_reaches_identifier_expression_or_statement_surface`
18. `test_official_registry_validates_supported_plan_and_fail_closed_eligibility_plan`

Selectors 8, 10, 14, 15, 17, and 18 are derived first-GREEN acceptances when the preceding generic guard already entails them. Do not weaken that guard or manufacture a failure. The other twelve selectors require focused RED→GREEN evidence.

**Task gate:**

```bash
uv run pytest -q tests/unit/query tests/security/test_query_injection.py tests/integration/query/test_official_semantic_validation.py
uv run ruff format --check src/finproof/domain/execution.py src/finproof/query tests/unit/query tests/security/test_query_injection.py tests/integration/query/test_official_semantic_validation.py
uv run ruff check src/finproof/domain/execution.py src/finproof/query tests/unit/query tests/security/test_query_injection.py tests/integration/query/test_official_semantic_validation.py
uv run mypy src/finproof/domain/execution.py src/finproof/query tests/unit/query tests/security/test_query_injection.py tests/integration/query/test_official_semantic_validation.py
```

**Commit:** stage exactly the Task 3 file map and commit `feat: validate and compile native query segments`.

---

### Task 4: Raw repositories, executor instrumentation, and differential reference

**Files:**

- Modify: `src/finproof/query/__init__.py`
- Create: `src/finproof/storage/__init__.py`
- Create: `src/finproof/storage/repositories/__init__.py`
- Create: `src/finproof/storage/repositories/products.py`
- Create: `src/finproof/query/executor.py`
- Create: `src/finproof/query/reference.py`
- Create: `tests/integration/query/test_executor.py`
- Create: `tests/integration/runtime/test_official_runtime_session.py`
- Create: `tests/differential/test_query_differential.py`
- Create: `tests/property/test_query_metamorphic.py`

**Interfaces:**

```python
class ProductRepository:
    def __init__(self, session: RuntimeArtifactSession) -> None: ...
    def execute(self, query: CompiledQuery) -> RawSegmentResult: ...

class QueryExecutor:
    def execute(self, bundle: ExecutionBundle) -> RawExecutionResult: ...

class ReferenceExecutor:
    def execute(
        self,
        rows: tuple[FixtureRow, ...],
        bundle: ExecutionBundle,
    ) -> RawExecutionResult: ...
```

Raw results retain product type, native grain, product identity, requested/policy values and quality states, compatibility dimensions, evidence lookup keys, and candidate counts. They do not claim final rank, aggregate, tie, partition, or top-k.

**Selectors — 5 mandatory RED→GREEN nodes plus 7 derived first-GREEN acceptances:**

1. `test_repository_and_executor_skeleton_exposes_exact_interfaces`
2. `test_repository_accepts_live_runtime_session_only`
3. `test_lookup_and_screen_return_typed_decimal_date_and_quality_values`
4. `test_raw_executor_does_not_apply_final_top_k_rank_tie_or_aggregate`
5. `test_candidate_counts_are_explicit_and_not_inferred_from_sql_text`
6. `test_no_result_returns_empty_typed_segment_without_error`
7. `test_native_segments_execute_once_in_frozen_product_type_order`
8. `test_same_grain_multi_type_rows_preserve_product_type_and_native_identity`
9. `test_reference_executor_is_independent_of_production_sql_and_compiler_helpers`
10. `test_duckdb_and_reference_raw_projections_are_equal`
11. `test_more_restrictive_literal_filter_cannot_increase_raw_candidate_count`
12. `test_official_runtime_session_executes_one_read_only_supported_query`

Selectors 4–6, 8, and 10–12 are derived first-GREEN acceptances when the preceding generic raw-result, ordered-executor, or independent-reference behavior already entails them. Do not manufacture a failure. The other five selectors require focused RED→GREEN evidence.

**Task gate:**

```bash
uv run pytest -q tests/integration/query/test_executor.py tests/integration/runtime/test_official_runtime_session.py tests/differential tests/property/test_query_metamorphic.py
uv run ruff format --check src/finproof/storage src/finproof/query/__init__.py src/finproof/query/executor.py src/finproof/query/reference.py tests/integration/query/test_executor.py tests/integration/runtime/test_official_runtime_session.py tests/differential tests/property/test_query_metamorphic.py
uv run ruff check src/finproof/storage src/finproof/query/__init__.py src/finproof/query/executor.py src/finproof/query/reference.py tests/integration/query/test_executor.py tests/integration/runtime/test_official_runtime_session.py tests/differential tests/property/test_query_metamorphic.py
uv run mypy src/finproof/storage src/finproof/query/__init__.py src/finproof/query/executor.py src/finproof/query/reference.py tests/integration/query/test_executor.py tests/integration/runtime/test_official_runtime_session.py tests/differential tests/property/test_query_metamorphic.py
```

**Commit:** stage exactly the Task 4 file map and commit `feat: execute bounded raw query segments`.

---

### Task 5: State, metric, partition, aggregate, rank, tie, and dual-lens policy

**Files:**

- Modify: `src/finproof/query/ast.py`
- Modify: `src/finproof/query/compiler.py`
- Modify: `src/finproof/query/segmenter.py`
- Create: `src/finproof/quality/__init__.py`
- Create: `src/finproof/quality/state.py`
- Create: `src/finproof/quality/metric_policy.py`
- Create: `src/finproof/quality/comparability.py`
- Create: `src/finproof/quality/ties.py`
- Create: `src/finproof/quality/dual_lens.py`
- Create: `src/finproof/quality/pipeline.py`
- Create: `tests/unit/quality/test_state_policy.py`
- Create: `tests/unit/quality/test_metric_operation_policy.py`
- Create: `tests/unit/quality/test_comparability.py`
- Create: `tests/unit/quality/test_ties.py`
- Create: `tests/unit/quality/test_pipeline_order.py`
- Create: `tests/integration/quality/test_official_quality_cases.py`
- Modify: `tests/unit/query/test_execution_bundle.py`
- Modify: `tests/unit/query/test_sql_compiler.py`

**Interfaces:**

```python
class StatePolicy:
    def evaluate(self, product: PolicyProduct, *, as_of: date) -> StateEvaluation: ...

class MetricPolicy:
    def apply(
        self,
        operation: Operation,
        values: Sequence[MetricValue],
    ) -> MetricPolicyResult: ...

class PolicyEngine:
    def apply(
        self,
        raw: RawExecutionResult,
        *,
        bundle: ExecutionBundle,
    ) -> PolicyExecutionResult: ...
```

`PolicyExecutionResult` owns the final partitions, aggregate groups or ranked rows, primary tie metadata, included/excluded counts, policy IDs, evidence requirements, warnings, and final top-k. `Decimal` is used for decimal aggregate arithmetic; average records numerator count and excluded count.

**Selectors — 18 mandatory nodes:**

1. `test_quality_policy_skeleton_exposes_exact_interfaces`
2. `test_domestic_listed_zero_suspension_flag_is_not_suspended`
3. `test_matured_positive_quantity_bond_is_source_buyable_not_validated_buyable`
4. `test_unsupported_overseas_and_public_fund_validated_eligibility_fails_closed`
5. `test_overseas_fee_zero_has_recorded_and_comparison_valid_views`
6. `test_constant_tracking_error_preserves_joint_primary_rank`
7. `test_krw_and_usd_aum_form_separate_compatibility_partitions`
8. `test_bond_yield_and_historical_return_cannot_share_one_rank`
9. `test_missing_return_period_requires_clarification`
10. `test_same_period_etf_and_fund_return_is_caveated_compatible`
11. `test_pipeline_applies_filter_then_state_and_metric_eligibility`
12. `test_pipeline_partitions_before_aggregate_or_rank_tie`
13. `test_pipeline_applies_top_k_only_after_each_final_partition`
14. `test_global_scope_rejects_more_than_one_final_partition`
15. `test_aggregate_functions_return_typed_value_counts_policy_and_evidence_requirements`
16. `test_rank_output_retains_tie_counts_policy_and_evidence_requirements`
17. `test_dual_lens_labels_appear_only_when_policy_difference_is_material`
18. `test_official_quality_profiles_match_325_254_zero_tie_and_currency_facts`

Sixteen additional focused correction selectors are recorded separately from these
18 planned nodes. They close only direct frozen-contract prerequisites discovered on
the real query path: policy-input projection, physical ETF/ETN discrimination,
targetless-count partitioning, state date boundaries, metric eligibility and dual
lens retention, per-product partition limits, typed aggregate groups and aggregate
top-k, and nonnumeric canonical-field sorting. They do not change the Phase 1
artifact contract or registry bytes.

**Task gate:**

```bash
uv run pytest -q tests/unit/quality tests/integration/quality/test_official_quality_cases.py tests/unit/query/test_execution_bundle.py tests/unit/query/test_sql_compiler.py
uv run ruff format --check src/finproof/quality src/finproof/query/ast.py src/finproof/query/compiler.py src/finproof/query/segmenter.py tests/unit/quality tests/integration/quality/test_official_quality_cases.py tests/unit/query/test_execution_bundle.py tests/unit/query/test_sql_compiler.py
uv run ruff check src/finproof/quality src/finproof/query/ast.py src/finproof/query/compiler.py src/finproof/query/segmenter.py tests/unit/quality tests/integration/quality/test_official_quality_cases.py tests/unit/query/test_execution_bundle.py tests/unit/query/test_sql_compiler.py
uv run mypy src/finproof/quality src/finproof/query/ast.py src/finproof/query/compiler.py src/finproof/query/segmenter.py tests/unit/quality tests/integration/quality/test_official_quality_cases.py tests/unit/query/test_execution_bundle.py tests/unit/query/test_sql_compiler.py
```

**Commit:** stage exactly the Task 5 file map and commit `feat: enforce deterministic financial policy`.

---

### Task 6: Evidence, claim verification, deterministic Korean rendering, and service

**Files:**

- Create: `src/finproof/storage/repositories/evidence.py`
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
- Modify: `src/finproof/domain/answers.py`
- Modify: `src/finproof/domain/evidence.py`
- Modify: `src/finproof/domain/execution.py`
- Create: `tests/unit/evidence/test_builder.py`
- Create: `tests/unit/evidence/test_claim_verifier.py`
- Create: `tests/unit/answer/test_renderer.py`
- Create: `tests/integration/service/test_answer_service.py`
- Create: `tests/golden/test_seed_answer_semantics.py`
- Modify: `tests/contract/test_phase2_schemas.py`
- Modify: `schemas/execution_trace.schema.json`

**Interfaces:**

```python
class EvidenceRepository:
    def __init__(self, session: RuntimeArtifactSession) -> None: ...
    def fetch_final_record_evidence(
        self,
        requests: tuple[EvidenceLookup, ...],
    ) -> tuple[RecordEvidence, ...]: ...

class EvidenceBuilder:
    def build(
        self,
        *,
        plan: ValidatedQueryPlan,
        policy_result: PolicyExecutionResult,
        repository: EvidenceRepository,
    ) -> EvidenceBundle: ...

class ClaimVerifier:
    def verify(self, draft: AnswerDraft, evidence: EvidenceBundle) -> VerifiedAnswer: ...

class AnswerService:
    def answer_plan(self, request: AnswerRequest, plan: QueryPlan) -> AnswerResult: ...
```

Evidence lookup is bounded by final returned products/aggregate groups and registered evidence requirements. It parses canonical wide `record_json` to recover exact Phase 1 value lineage; count/exclusion summaries bind explicit query/policy counts and verified table logical identity without serializing all Bronze cells.

**Selectors — 17 mandatory nodes:**

1. `test_evidence_and_answer_skeleton_exposes_exact_interfaces`
2. `test_final_product_claims_use_complete_source_cell_lineage`
3. `test_derived_claims_bind_formula_inputs_rule_and_as_of`
4. `test_count_exclusion_rank_tie_partition_and_aggregate_summaries_are_bounded`
5. `test_context_serialization_is_stable_json_safe_size_bounded_and_contains_no_local_runtime_path`
6. `test_claim_verifier_rejects_numeric_claim_without_evidence`
7. `test_claim_verifier_rejects_wrong_product_changed_decimal_and_false_sign_family`
8. `test_claim_verifier_rejects_unsupported_recommendation_claim`
9. `test_claim_verifier_requires_every_material_policy_limitation`
10. `test_current_answer_names_2026_07_11_snapshot_not_realtime`
11. `test_recommendation_request_renders_conditions_matching_candidates`
12. `test_renderer_handles_joint_tie_dual_lens_currency_split_and_no_result`
13. `test_clarify_and_unsupported_answers_execute_no_repository_query`
14. `test_answer_service_composes_exact_runtime_resolution_validation_execution_policy_evidence_render_verify_order`
15. `test_ai_handoff_seeds_assert_semantics_without_parsing_partial_expected_plans_as_queryplan`
16. `test_execution_trace_schema_matches_exact_domain_model`
17. `test_official_runtime_returns_one_verified_evidence_backed_answer_and_trace`

**Task gate:**

```bash
uv run pytest -q tests/unit/evidence tests/unit/answer tests/integration/service tests/golden/test_seed_answer_semantics.py tests/contract/test_phase2_schemas.py
uv run ruff format --check src/finproof/storage/repositories/evidence.py src/finproof/evidence src/finproof/answer src/finproof/service tests/unit/evidence tests/unit/answer tests/integration/service tests/golden/test_seed_answer_semantics.py tests/contract/test_phase2_schemas.py
uv run ruff check src/finproof/storage/repositories/evidence.py src/finproof/evidence src/finproof/answer src/finproof/service tests/unit/evidence tests/unit/answer tests/integration/service tests/golden/test_seed_answer_semantics.py tests/contract/test_phase2_schemas.py
uv run mypy src/finproof/storage/repositories/evidence.py src/finproof/evidence src/finproof/answer src/finproof/service tests/unit/evidence tests/unit/answer tests/integration/service tests/golden/test_seed_answer_semantics.py tests/contract/test_phase2_schemas.py
```

**Commit:** stage exactly the Task 6 file map and commit `feat: render verified evidence backed answers`.

---

## Final Phase 2 gate

Run once on the unchanged Task 6 candidate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

Also record:

- wheel and editable registry-resource tests;
- Phase 2 focused aggregate counts per task;
- official runtime/entity/quality/service selector results using the shared artifact session;
- source/resource and runtime artifact absence/read-only checks;
- exact Phase 2 implementation diff and clean status.

Do not rerun source/performance subsets already included by `pytest -q`. If the final gate exposes an explained stale fixture or mechanical type/import issue, correct it, rerun the affected focused selector, then run the final full gate exactly once more on the changed candidate.

## Independent review and bounded correction

1. Commit the unchanged final implementation candidate.
2. Request one independent review against D-027–D-030 and the exact Phase 2 diff. Only Critical and Important findings block.
3. If findings exist, reproduce each direct contract violation with focused RED, apply the smallest shared-root GREEN, run affected task aggregates/static checks, then one final full gate and one correction commit.
4. Request one scoped re-review of those findings.
5. Any later new finding is root-classified: fix only a direct frozen/official violation; record adjacent hardening as backlog; reject unsupported over-defense.

## Documentation closure

After 0 Critical / 0 Important:

- Modify only `docs/implementation/STATUS.md`, this plan's checkboxes/evidence section, and the repository's Phase 2 legacy phase pointer if one exists.
- Record exact implementation/review commit lineage, mandatory/derived selector counts, full gate outputs, unresolved official questions, and the exact next Phase 3 task.
- Commit once as `docs: close Phase 2 deterministic engine`.
- Verify `git diff --check`, expected tracked-file inventory, and empty porcelain status.
