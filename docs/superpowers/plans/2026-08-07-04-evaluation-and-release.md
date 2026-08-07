# Evaluation, Hardening, and Release Implementation Plan

> **For agentic workers:** REQUIRED REPOSITORY CONTRACT: follow
> `docs/implementation/QUALITY_LOOP.md` for the one task selected by `STATUS.md`. Skills are
> optional aids and may not expand scope, writable paths, ownership, or review gates. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove FinProof’s accuracy, stability, safety, latency, and reproducibility with reviewed evaluation assets, close material risks, and freeze an immutable submission release.

**Architecture:** A versioned evaluation harness runs canonical, paraphrase, differential, metamorphic, quality, adversarial, and operational suites. Reports are machine-readable and feed proposal figures. Release tooling produces checksums for code/data/config/prompt/image and verifies a clean-room deployment before freeze.

**Tech Stack:** Python 3.12, pytest/Hypothesis, Polars, DuckDB, httpx, JSON/Markdown reports, Docker, Git/GitHub Actions, optional load generator implemented in Python.

## Global Constraints

- Phase 3 gate must pass.
- Evaluation expectations are human-reviewed and versioned; do not generate “ground truth” from the same model under test.
- Metrics in the proposal come from committed/reproducible reports.
- No benchmark result is invented or manually edited.
- No post-freeze behavior change.
- Strict TDD applies to harness and release tooling.

---

### Task 1: Build canonical golden dataset schema, authoring checks, and scorer

**Files:**
- Create: `src/finproof/evaluation/__init__.py`
- Create: `src/finproof/evaluation/models.py`
- Create: `src/finproof/evaluation/loader.py`
- Create: `src/finproof/evaluation/scoring.py`
- Create: `src/finproof/evaluation/runner.py`
- Create: `src/finproof/cli/evaluate.py`
- Create: `tests/unit/evaluation/test_case_schema.py`
- Create: `tests/unit/evaluation/test_scoring.py`
- Create: `tests/integration/evaluation/test_runner.py`
- Create: `evaluation/canonical/.gitkeep`
- Create: `evaluation/README.md`
- Create: `artifacts/evaluation/canonical.json`
- Modify: `src/finproof/cli/main.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `GoldenCase`, `ExpectedPlan`, `ExpectedResult`, `ExpectedAnswerSemantics`
- Produces: `load_golden_cases(paths: Sequence[Path]) -> tuple[GoldenCase, ...]`
- Produces: `score_case(case: GoldenCase, observed: ObservedCase) -> CaseScore`
- Produces: `EvaluationRunner.run(cases, service) -> EvaluationReport`
- CLI: `finproof evaluate --suite canonical --output artifacts/evaluation/canonical.json`

- [ ] **Step 1: Write failing golden-case schema tests**

```python
from finproof.evaluation.models import GoldenCase


def test_golden_case_requires_review_metadata_and_expected_semantics() -> None:
    case = GoldenCase.model_validate(
        {
            "case_id": "BOND-RANK-001",
            "category": "rank",
            "question": "2026-07-11 기준 AA- 이상 매수 가능 채권 5개",
            "expected_plan": {
                "intent": "screen_rank",
                "product_types": ["domestic_bond"],
                "as_of_date": "2026-07-11",
                "result_grain": "instrument",
                "top_k_scope": "global",
            },
            "expected_result": {"product_ids": ["B1"], "order_matters": True},
            "expected_answer": {"required_concepts": ["2026-07-11"], "forbidden_concepts": ["실시간"]},
            "review": {"reviewer": "human", "reviewed_at": "2026-08-20", "source": "reference-engine"},
        }
    )
    assert case.review.reviewer == "human"
```

Reject duplicate case IDs, missing review metadata, impossible expected product ordering, empty question, unknown category, invalid `top_k_scope`, and heterogeneous expected plans that omit the `product` envelope or native segment expectations.

- [ ] **Step 2: Run RED and implement evaluation models/loader**

```bash
uv run pytest tests/unit/evaluation/test_case_schema.py -q
```

Use JSONL files split by category. Loader checks duplicate IDs across files and records suite checksum.

- [ ] **Step 3: Write failing scorer tests**

```python
def test_product_set_f1_and_order_accuracy_are_separate() -> None:
    score = score_products(expected=["A", "B", "C"], observed=["B", "A", "C"])
    assert score.set_f1 == 1.0
    assert score.order_accuracy < 1.0
```

Add exact Decimal/date match, filter-slot F1, evidence coverage, limitation/clarification, repeated stability, and latency aggregation tests.

- [ ] **Step 4: Implement scorer and report models**

Reports include numerator/denominator and per-case failures, not only aggregate percentages. Numeric tolerance is zero unless a case explicitly defines display-only tolerance. Score top-k scope, segment assignment, compatibility partitions, and assembled-envelope semantics separately from product-set and order accuracy.

```bash
uv run pytest tests/unit/evaluation/test_scoring.py -q
```

- [ ] **Step 5: Implement runner with deterministic replay metadata**

The runner records code commit, artifact/config/prompt/planner versions, environment, started/ended time, and case checksum. It can run plan-only, deterministic-core, or end-to-end mode.

```bash
uv run pytest tests/integration/evaluation/test_runner.py -q
```

- [ ] **Step 6: Author and review canonical cases**

Expand from `tests/golden/seed_cases.jsonl` to 250–300 cases across the target category distribution. Each expected product/value/order comes from a reference query and human review. Store generation/reference scripts; do not copy model output as truth.

Run:

```bash
uv run finproof evaluate --suite canonical --output artifacts/evaluation/canonical.json
```

- [ ] **Step 7: Commit harness and reviewed cases**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/evaluation/__init__.py src/finproof/evaluation/models.py src/finproof/evaluation/loader.py src/finproof/evaluation/scoring.py src/finproof/evaluation/runner.py src/finproof/cli/evaluate.py tests/unit/evaluation/test_case_schema.py tests/unit/evaluation/test_scoring.py tests/integration/evaluation/test_runner.py evaluation/canonical/.gitkeep evaluation/README.md artifacts/evaluation/canonical.json src/finproof/cli/main.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "test: add reviewed canonical FinProof evaluation"
```

---

### Task 2: Add paraphrase, metamorphic, differential, quality, and adversarial suites

**Files:**
- Create: `src/finproof/evaluation/paraphrases.py`
- Create: `src/finproof/evaluation/metamorphic.py`
- Create: `src/finproof/evaluation/adversarial.py`
- Create: `evaluation/paraphrase_rules.yaml`
- Create: `evaluation/adversarial_cases.jsonl`
- Create: `tests/evaluation/test_paraphrase_invariance.py`
- Create: `tests/evaluation/test_metamorphic_relations.py`
- Create: `tests/evaluation/test_quality_cases.py`
- Create: `tests/evaluation/test_adversarial_cases.py`
- Create: `artifacts/evaluation/robustness.json`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `generate_rule_paraphrases(case: GoldenCase, rules: ParaphraseRules) -> tuple[DerivedCase, ...]`
- Produces: `MetamorphicRelation.check(base, transformed) -> RelationResult`
- Produces: `AdversarialRunner.run(cases, service) -> AdversarialReport`

- [ ] **Step 1: Write failing deterministic paraphrase tests**

```python
def test_condition_order_paraphrase_preserves_canonical_plan(paraphraser, planner) -> None:
    base = "미국 ETF 중 총보수 0.2% 이하이고 AUM이 큰 5개"
    variant = "AUM이 큰 순서로, 총보수 0.2% 이하 미국 ETF 5개"
    assert canonicalize_plan(planner(base)) == canonicalize_plan(planner(variant))
```

Rule transformations include condition order, honorific/colloquial forms, top-k wording, ascending/descending synonyms, exact ticker/ISIN/name substitution, whitespace, and reviewed typo variants. They must not change semantic values.

- [ ] **Step 2: Run RED and implement rule-based paraphrase generation**

```bash
uv run pytest tests/evaluation/test_paraphrase_invariance.py -q
```

No non-HCX generative model may create evaluation cases. HCX-generated candidates require human review before becoming expected cases.

- [ ] **Step 3: Write failing metamorphic relation tests**

```python
def test_added_filter_cannot_increase_result_count(metamorphic_runner, base_case) -> None:
    relation = metamorphic_runner.run(add_minimum_aum_filter(base_case))
    assert relation.transformed.total <= relation.base.total
```

Cover filter monotonicity, sort reversal, comparison sign, unit-display invariance, identity alias invariance, tie preservation, and fund-item non-duplication.

- [ ] **Step 4: Implement metamorphic harness and rerun**

```bash
uv run pytest tests/evaluation/test_metamorphic_relations.py -q
```

- [ ] **Step 5: Write quality and adversarial tests**

Quality cases include all 17 critical regressions in `docs/07_TESTING_AND_EVALUATION.md`.

Adversarial cases include:

```text
SQL statement in question
system-prompt extraction request
instruction embedded in product strategy text
unknown field/metric
conflicting conditions
excessive top-k
future-return forecast
categorical buy recommendation
request to call another LLM
oversized/repeated Unicode input
ambiguous product alias
```

Expected outcomes are validated safe plans/answers, not keyword-only refusal.

- [ ] **Step 6: Run suites and generate report**

```bash
uv run pytest tests/evaluation -q
uv run finproof evaluate --suite robustness --output artifacts/evaluation/robustness.json
```

- [ ] **Step 7: Commit**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/evaluation/paraphrases.py src/finproof/evaluation/metamorphic.py src/finproof/evaluation/adversarial.py evaluation/paraphrase_rules.yaml evaluation/adversarial_cases.jsonl tests/evaluation/test_paraphrase_invariance.py tests/evaluation/test_metamorphic_relations.py tests/evaluation/test_quality_cases.py tests/evaluation/test_adversarial_cases.py artifacts/evaluation/robustness.json docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "test: harden FinProof language and policy behavior"
```

---

### Task 3: Implement ablation, latency, load, resilience, and soak measurement

**Files:**
- Create: `src/finproof/evaluation/ablation.py`
- Create: `src/finproof/evaluation/latency.py`
- Create: `src/finproof/evaluation/load.py`
- Create: `src/finproof/evaluation/soak.py`
- Create: `tests/unit/evaluation/test_latency_stats.py`
- Create: `tests/integration/evaluation/test_fault_injection.py`
- Create: `scripts/run_ablation.sh`
- Create: `scripts/run_load.sh`
- Create: `scripts/run_soak.sh`
- Create: `docs/benchmark/README.md`
- Create: `artifacts/evaluation/ablation.json`
- Create: `artifacts/evaluation/load.json`
- Create: `artifacts/evaluation/soak.json`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `AblationRunner.run(variants, cases) -> AblationReport`
- Produces: `LatencySummary.from_samples(samples: Sequence[LatencySample]) -> LatencySummary`
- Produces: `LoadRunner.run(config: LoadConfig) -> LoadReport`
- Produces: `SoakRunner.run(config: SoakConfig) -> SoakReport`

- [ ] **Step 1: Write failing percentile and stage-accounting tests**

```python
def test_latency_summary_computes_nearest_rank_p95() -> None:
    summary = LatencySummary.from_milliseconds(list(range(1, 101)))
    assert summary.p95_ms == 95
    assert summary.count == 100
```

Add test that total latency is not lower than any recorded stage and that failed requests are counted separately.

- [ ] **Step 2: Run RED and implement deterministic report statistics**

```bash
uv run pytest tests/unit/evaluation/test_latency_stats.py -q
```

- [ ] **Step 3: Implement ablation variants**

Variants:

```text
A direct HCX answer over retrieved rows
B constrained QueryPlan
C deterministic executor
D grain/time/state/metric policy
E evidence/verifier/conditional dual-lens
```

A is an experiment only and must never become production. All variants use the same official data, HCX model/config, question set, and recorded environment. Reports include actual token/latency/error data.

- [ ] **Step 4: Write failing fault-injection tests**

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["timeout", "429", "malformed_json", "connection_error"])
async def test_fault_path_is_bounded_and_returns_safe_contract(fault, fault_service) -> None:
    result = await fault_service.answer_with_fault(fault)
    assert result.elapsed_seconds < fault_service.deadline_seconds + 0.1
    assert result.response_schema_valid
    assert not result.leaked_internal_error
```

Add DuckDB open/read error, cache corruption detection, process restart, and readiness failure tests.

- [ ] **Step 5: Implement load and soak tools**

The load tool uses async httpx, configurable concurrency/rate/duration, a weighted reviewed question mix, and records response schema, status, latency, question type, and answer hash. It must not print secrets or full responses by default.

The soak tool periodically checks health/readiness/version, sends representative requests, detects answer drift for deterministic cases, and writes a resumable report.

- [ ] **Step 6: Run measured experiments**

```bash
bash scripts/run_ablation.sh --output artifacts/evaluation/ablation.json
bash scripts/run_load.sh --output artifacts/evaluation/load.json
bash scripts/run_soak.sh --hours 24 --output artifacts/evaluation/soak.json
```

Prefer a 48-hour final soak. If organizer timeout/concurrency is disclosed, set pass thresholds in committed config and rerun.

- [ ] **Step 7: Commit code and immutable measured summaries**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/evaluation/ablation.py src/finproof/evaluation/latency.py src/finproof/evaluation/load.py src/finproof/evaluation/soak.py tests/unit/evaluation/test_latency_stats.py tests/integration/evaluation/test_fault_injection.py scripts/run_ablation.sh scripts/run_load.sh scripts/run_soak.sh docs/benchmark/README.md artifacts/evaluation/ablation.json artifacts/evaluation/load.json artifacts/evaluation/soak.json docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "perf: measure FinProof quality latency and resilience"
```

Do not commit secrets or giant uncompressed request logs. Commit the three exact summary files above;
each summary records hashes and immutable storage references for excluded raw request logs.

---

### Task 4: Run competition-compliance scan and close independent review findings

**Files:**
- Create: `tools/check_competition_compliance.py`
- Create: `tools/check_claim_evidence_report.py`
- Create: `tests/contract/test_competition_compliance.py`
- Create: `docs/review/INDEPENDENT_REVIEW.md`
- Create: `docs/review/FINDING_CLOSURE.md`
- Modify: `docs/09_RISK_REGISTER.md`
- Modify: `docs/10_DECISION_LOG.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Tool: `python tools/check_competition_compliance.py --check`
- Tool: `python tools/check_claim_evidence_report.py artifacts/evaluation/canonical.json`
- Compliance report checks generative providers, external runtime URLs, exact response schema, source checksum, data priority, prompt/config versions, and freeze-sensitive files

- [ ] **Step 1: Write failing compliance scanner tests**

```python
def test_compliance_scanner_detects_forbidden_provider(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("from anthropic import Anthropic", encoding="utf-8")
    report = scan_repository(tmp_path)
    assert any(f.code == "forbidden_generative_provider" for f in report.findings)
```

Add tests for external live-data URL in evaluation path, extra API field, missing source manifest, and unversioned prompt.

- [ ] **Step 2: Implement scanner and add it to CI**

```bash
uv run pytest tests/contract/test_competition_compliance.py -q
uv run python tools/check_competition_compliance.py --check
```

The scanner uses AST/config inspection where possible and a narrow text scan for endpoints; avoid false positives from docs/source material.

- [ ] **Step 3: Run independent review in a fresh context**

Use `CODEX_REVIEW_PROMPT.md` with no implementation-history assumptions. Record exact commands and findings in `docs/review/INDEPENDENT_REVIEW.md`.

- [ ] **Step 4: Fix each BLOCKER/HIGH finding with TDD**

For each accepted finding:

1. add a failing regression test
2. reproduce
3. implement smallest fix
4. rerun affected and full gates
5. record fix commit/evidence in `FINDING_CLOSURE.md`

Do not dismiss technically valid feedback without evidence. Document rejected findings and why.

- [ ] **Step 5: Update risk and decision logs**

No BLOCKER/HIGH release risk remains unresolved unless the organizer explicitly accepts it. Official Discord answers become dated `OFFICIAL_OVERRIDE` entries and update config/tests.

- [ ] **Step 6: Commit review closure**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/check_competition_compliance.py tools/check_claim_evidence_report.py tests/contract/test_competition_compliance.py docs/review/INDEPENDENT_REVIEW.md docs/review/FINDING_CLOSURE.md docs/09_RISK_REGISTER.md docs/10_DECISION_LOG.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "chore: close FinProof competition review findings"
```

---

### Task 5: Clean-room reproduction, proposal evidence, immutable manifest, and freeze

**Files:**
- Create: `tools/create_release_manifest.py`
- Create: `tools/verify_release_manifest.py`
- Create: `scripts/clean_room_reproduce.sh`
- Create: `docs/submission/SUBMISSION_CHECKLIST.md`
- Create: `docs/submission/API_SCHEMA.md`
- Create: `docs/submission/PROPOSAL_EVIDENCE_INDEX.md`
- Create: `docs/submission/RELEASE_RECORD.md`
- Create: `release/.gitkeep`
- Create: `tests/contract/test_release_manifest.py`
- Create: `artifacts/evaluation/final-canonical.json`
- Create: `release/manifest.json`
- Modify: `README.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Tool: `python tools/create_release_manifest.py --output release/manifest.json`
- Tool: `python tools/verify_release_manifest.py release/manifest.json`
- Script: `scripts/clean_room_reproduce.sh <repository-url-or-path>`

- [ ] **Step 1: Write failing release-manifest test**

```python
def test_release_manifest_covers_behavior_sensitive_assets(release_manifest) -> None:
    required_prefixes = ("src/", "config/", "schemas/", "prompts/", "source_material/input_manifest.json")
    covered = set(release_manifest.files)
    for prefix in required_prefixes:
        assert any(path == prefix or path.startswith(prefix) for path in covered)
    assert release_manifest.git_commit
    assert release_manifest.image_digest.startswith("sha256:")
```

- [ ] **Step 2: Run RED and implement deterministic release manifest**

```bash
uv run pytest tests/contract/test_release_manifest.py -q
```

Manifest includes Git commit/tag, dirty flag, source artifact manifest hash, config/schema/prompt/code checksums, Python/dependency lock hash, Docker image digest, evaluation report hashes, endpoint/API schema hash, and creation metadata. Verification fails on any mismatch.

- [ ] **Step 3: Implement and run clean-room reproduction**

The script uses a fresh temporary directory and performs:

```text
git clone/checkout exact commit
uv sync --frozen --all-groups
handoff/source/compliance checks
artifact build or immutable artifact verification
full tests
docker build and start
health/ready/version/answer external calls
API JSON Schema validation
cleanup
```

```bash
bash scripts/clean_room_reproduce.sh .
```

- [ ] **Step 4: Build proposal evidence index**

Every proposed number/diagram links to an artifact/report/query:

- official source counts and quality findings
- architecture/version diagram source
- golden/planner/deterministic metrics
- ablation table
- latency/load/soak results
- sample trace/evidence/dual-lens answers
- exact limitations and unresolved official assumptions

No manually typed benchmark number without a reproducible source path.

- [ ] **Step 5: Run the final release gate**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/check_competition_compliance.py --check
uv run finproof evaluate --suite canonical --output artifacts/evaluation/final-canonical.json
python tools/create_release_manifest.py --output release/manifest.json
python tools/verify_release_manifest.py release/manifest.json
bash scripts/clean_room_reproduce.sh .
```

Run the final load and soak reports against the submitted endpoint candidate.

- [ ] **Step 6: Freeze and record**

Create the release commit/tag only with a clean worktree. Record:

```text
submission commit
tag
Docker image digest
artifact manifest hash
release manifest hash
public endpoint
API schema hash
start/end of required server availability
organizer-approved failover procedure
```

- [ ] **Step 7: Commit final submission assets**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/create_release_manifest.py tools/verify_release_manifest.py scripts/clean_room_reproduce.sh docs/submission/SUBMISSION_CHECKLIST.md docs/submission/API_SCHEMA.md docs/submission/PROPOSAL_EVIDENCE_INDEX.md docs/submission/RELEASE_RECORD.md release/.gitkeep tests/contract/test_release_manifest.py artifacts/evaluation/final-canonical.json release/manifest.json README.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "chore: freeze FinProof competition release"
git tag -a finproof-submission -m "FinProof competition submission"
```

After freeze, do not modify behavior. Monitor and use only organizer-approved identical-image operations.
