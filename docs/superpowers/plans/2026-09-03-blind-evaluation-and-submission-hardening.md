# Blind Evaluation and Submission Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a 144-case latest-data development evaluation plus a separately custodied 48-case holdout, make at most one observed-failure correction, then close the organizer ablation, ontology, proposal, deployment, and submission requirements.

**Architecture:** Reuse the existing 24-case HCX authoring, deterministic reference, `EvaluationRunner`, `LoadRunner`, A-E ablation, artifact, and release flows. Add only the suite-selection and blinded-summary seams those flows lack. Keep holdout plaintext in a separate NCP curator workspace until the final candidate is frozen; the root worktree receives only checksums and aggregate results.

**Tech Stack:** Python 3.12, Pydantic, httpx, DuckDB-backed FinProof runtime, NCP HyperCLOVA X HCX-007, pytest, Ruff, mypy, Docker, Turtle/RDF, Git.

**Spec:** `docs/superpowers/specs/2026-09-03-blind-evaluation-and-submission-hardening-design.md`

## Global Constraints

- Official distribution: `2026-08-24`; domestic/public coverage through `2026-08-22`, overseas coverage through Korea-time `2026-08-23`.
- Corpus: batches `012`-`017` are 144 visible development cases; batches `018`-`019` are 48 holdout cases; every batch contains exactly 24 cases.
- Holdout plaintext, expected plans/results/answers, and case-level failures stay outside the root worktree until final freeze.
- HCX-007 is the only generative model in authoring, evaluation, and runtime paths. Obtain a hard call-cap approval before each new external-transfer stage.
- Runtime performs no live external-data retrieval. Supplemental data must already satisfy the sealed admission and exact-link contract; official values always win.
- One observed-development-failure correction is allowed. Holdout results never authorize tuning.
- Each behavior change uses focused RED -> minimum GREEN. Run aggregate checks only when a task bundle closes and the full repository gate only for the final candidate.
- If runtime/data/prompt/policy/image changes, old Task 10 load/soak reports do not attest the new candidate.
- Preserve all unrelated user-owned ablation edits, review drafts, PDFs, credentials, and NCP state.

---

### Task 1: Add latest-data blind authoring batches 012-017

**Files:**
- Modify: `tools/generate_canonical_questions.py`
- Modify: `tests/unit/evaluation/test_generate_canonical_questions.py`

**Interfaces:**
- Consumes: existing `_batch_contract(batch_id)` and `generate_review_packet(...)` authoring flow.
- Produces: six new immutable batch contracts for IDs `012`-`017`, prompt versions `canonical-question-candidates-v15` through `v20`, and seeds `149, 161, 173, 185, 197, 209`.
- Preserves: packet root/candidate shapes, 24-case count, HCX-007-only provider, strict JSON, and existing batches `001`-`011` byte-for-byte.

- [ ] **Step 1: Write failing contract tests for new batch identity and old-batch preservation**

Add a parameterized test that calls `_batch_contract` for all six IDs and asserts exact seed, prompt version, and request ID:

```python
@pytest.mark.parametrize(
    ("batch_id", "seed", "version"),
    (
        ("012", 149, "canonical-question-candidates-v15"),
        ("013", 161, "canonical-question-candidates-v16"),
        ("014", 173, "canonical-question-candidates-v17"),
        ("015", 185, "canonical-question-candidates-v18"),
        ("016", 197, "canonical-question-candidates-v19"),
        ("017", 209, "canonical-question-candidates-v20"),
    ),
)
def test_blind_development_batch_identity(batch_id: str, seed: int, version: str) -> None:
    actual_seed, actual_version, prompt, request_id = generator._batch_contract(batch_id)
    assert (actual_seed, actual_version) == (seed, version)
    assert request_id == f"finproof-canonical-question-candidates-{batch_id}"
    assert "공식 2026-08-24 배포본" in prompt
```

Retain the existing exact assertions for batches `001`-`011`; do not rewrite their prompts or versions.

- [ ] **Step 2: Run the focused RED**

Run:

```bash
uv run pytest tests/unit/evaluation/test_generate_canonical_questions.py -k 'blind_development_batch_identity or batch_011' -q
```

Expected: the new IDs fail with the current `batch_id must be one of ... 006-011` error while the existing batch assertion passes.

- [ ] **Step 3: Add the six exact slot contracts and the August prompt**

Add `_BLIND_DEVELOPMENT_METADATA`, `_BLIND_DEVELOPMENT_SLOTS`,
`_BLIND_DEVELOPMENT_FAMILIES`, and a separate `_blind_development_prompt`; do not
change `_new_batch_prompt` used by old batches. Keep both slot maps as tuples of
strings so they fit the existing prompt builder without a new wrapper type. Their
indexes are paired one-to-one. The semantic-family counts per batch are fixed:

```python
_BLIND_FAMILY_COUNTS = {
    "012": {"cross_metric": 20, "missing_zero": 2, "unsupported": 2},
    "013": {"cross_metric": 4, "holding_sector": 18, "unsupported": 2},
    "014": {"cross_metric": 4, "holding_sector": 2, "missing_zero": 16, "unsupported": 2},
    "015": {"cross_metric": 2, "missing_zero": 2, "unsupported": 18, "entity_variant": 2},
    "016": {"cross_metric": 4, "holding_sector": 2, "missing_zero": 2, "entity_variant": 16},
    "017": {"cross_metric": 8, "holding_sector": 14, "missing_zero": 2},
}
```

Each slot keeps one existing `EvaluationCategory` and one explicit behavior instruction. Across all slots the totals must be exactly `42/36/24/24/18`. The prompt must state the August coverage dates, invalid `BUYABLE_QUANTITY`, unavailable code meanings, missing/zero exclusion policy, no overseas one-year-return fabrication, native cross-product segmentation, ETF-not-ETN default, exact-only entity links, and sealed-holdings coverage limitation.

- [ ] **Step 4: Add strict family/count and prompt-boundary tests**

```python
def test_blind_development_slots_have_approved_family_distribution() -> None:
    totals = Counter(
        family
        for batch_id in ("012", "013", "014", "015", "016", "017")
        for family in generator._BLIND_DEVELOPMENT_FAMILIES[batch_id]
    )
    assert totals == {
        "cross_metric": 42,
        "holding_sector": 36,
        "missing_zero": 24,
        "unsupported": 24,
        "entity_variant": 18,
    }
    assert all(
        len(generator._BLIND_DEVELOPMENT_SLOTS[batch_id]) == 24
        for batch_id in generator._BLIND_DEVELOPMENT_SLOTS
    )
    assert all(
        len(generator._BLIND_DEVELOPMENT_SLOTS[batch_id])
        == len(generator._BLIND_DEVELOPMENT_FAMILIES[batch_id])
        for batch_id in generator._BLIND_DEVELOPMENT_SLOTS
    )
```

Also assert every slot has a registered category, a unique normalized instruction, and no unsupported internal-code meaning or fabricated external fact.

- [ ] **Step 5: Run focused GREEN and the authoring aggregate**

```bash
uv run pytest tests/unit/evaluation/test_generate_canonical_questions.py -q
uv run ruff check tools/generate_canonical_questions.py tests/unit/evaluation/test_generate_canonical_questions.py
```

Expected: all authoring tests pass; no HCX call has occurred.

- [ ] **Step 6: Commit Task 1**

```bash
git add tools/generate_canonical_questions.py tests/unit/evaluation/test_generate_canonical_questions.py
git commit -m "test: add latest-data blind question contracts"
```

---

### Task 2: Admit development and holdout suites without weakening canonical review

**Files:**
- Modify: `tools/build_canonical_reference_packet.py`
- Modify: `tools/promote_canonical_reference_packet.py`
- Modify: `src/finproof/evaluation/loader.py`
- Modify: `tests/unit/evaluation/test_build_canonical_reference_packet.py`
- Modify: `tests/unit/evaluation/test_promote_canonical_reference_packet.py`
- Create: `tests/unit/evaluation/test_blind_case_suite.py`

**Interfaces:**
- Produces: `load_blind_suite(name: str, *, repository_root: Path | None = None) -> tuple[GoldenCase, ...]`.
- Supports: `blind_development` with batches `012`-`017` and exactly 144 cases; `blind_holdout` with batches `018`-`019` and exactly 48 cases.
- Adds: explicit `independent_blind_curator` review authority only for destinations named `blind_development` or `blind_holdout`, exposed by the promotion CLI as `--review-authority`.
- Preserves: human-review-only admission for `evaluation/canonical` and `evaluation/organizer_20260824`.

- [ ] **Step 1: Write RED tests for suite shape, cross-suite deduplication, and review authority**

Use temporary GoldenCase JSONL fixtures. Assert:

```python
def test_blind_suite_rejects_wrong_count_or_batch_range(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="blind development suite"):
        load_blind_suite("blind_development", repository_root=tmp_path)

def test_independent_curator_cannot_promote_into_canonical(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="human review"):
        promotion.promote_reference_packet(
            reference,
            independent_approval,
            tmp_path / "evaluation/canonical",
            repository_root=tmp_path,
            review_authority="independent_blind_curator",
        )
```

Add one test proving normalized duplicate questions and duplicate semantic signatures across canonical, organizer, and blind suites are rejected.

- [ ] **Step 2: Run focused RED**

```bash
uv run pytest tests/unit/evaluation/test_blind_case_suite.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evaluation/test_promote_canonical_reference_packet.py -q
```

Expected: failures identify the absent loader and review-authority parameter.

- [ ] **Step 3: Implement the minimum blind loader and authority check**

Keep `load_golden_cases` unchanged. Add fixed suite metadata and reuse it:

```python
_BLIND_SUITES = {
    "blind_development": (frozenset(f"{number:03d}" for number in range(12, 18)), 144),
    "blind_holdout": (frozenset({"018", "019"}), 48),
}

def load_blind_suite(name: str, *, repository_root: Path | None = None) -> tuple[GoldenCase, ...]:
    allowed_batches, expected_count = _BLIND_SUITES[name]
    root = repository_root or Path(__file__).resolve().parents[3]
    cases = load_golden_cases(tuple(sorted((root / "evaluation" / name).glob("*.jsonl"))))
    case_id_pattern = re.compile(r"^CQ-(\d{3})-\d{3}$")
    observed_batches = {
        match.group(1)
        for case in cases
        if (match := case_id_pattern.fullmatch(case.case_id)) is not None
    }
    if len(cases) != expected_count or observed_batches != allowed_batches:
        raise ValueError(f"{name.replace('_', ' ')} suite shape differs")
    return cases
```

Reject any case whose ID does not match the pattern before comparing the batch set.

Implement normalized-question and plan-signature collision checking with stdlib `json` and `hashlib`; do not add a fuzzy-matching dependency. Add the function and CLI review-authority argument with default `human`, restrict the CLI choices to `human` and `independent_blind_curator`, reject independent authority for canonical/organizer destinations, and keep every old approval value valid without migration.

- [ ] **Step 4: Run focused GREEN and adjacent loader/promotion tests**

```bash
uv run pytest tests/unit/evaluation/test_blind_case_suite.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evaluation/test_promote_canonical_reference_packet.py tests/unit/evaluation/test_organizer_case_suite.py -q
```

- [ ] **Step 5: Commit Task 2**

```bash
git add tools/build_canonical_reference_packet.py tools/promote_canonical_reference_packet.py src/finproof/evaluation/loader.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evaluation/test_promote_canonical_reference_packet.py tests/unit/evaluation/test_blind_case_suite.py
git commit -m "test: isolate reviewed blind evaluation suites"
```

---

### Task 3: Reuse evaluation, load, and ablation runners for selected suites

**Files:**
- Modify: `src/finproof/cli/evaluate.py`
- Modify: `src/finproof/evaluation/load.py`
- Modify: `src/finproof/evaluation/ablation.py`
- Modify: `src/finproof/evaluation/ablation_experiment.py`
- Modify: `tests/unit/cli/test_evaluate.py`
- Modify: `tests/unit/evaluation/test_load_runner.py`
- Modify: `tests/unit/evaluation/test_ablation.py`

**Interfaces:**
- `run_evaluation` accepts `blind_development` and `blind_holdout` and delegates to `load_blind_suite`.
- `reviewed_suite_mix(repository_root: Path, suite: str) -> tuple[LoadCase, ...]` maps every selected case once with weight `1`.
- `run_load.sh --suite blind_development` and `--suite blind_holdout` measure actual HTTP latency without full response logging.
- `run_ablation.sh --suite organizer_20260824 --repeats 2` binds the A-E report to the official 35-case checksum.

- [ ] **Step 1: Write RED CLI/dispatch tests**

```python
def test_parser_accepts_blind_development_evaluation() -> None:
    args = _parser().parse_args(
        ["evaluate", "--suite", "blind_development", "--output", "report.json"]
    )
    assert args.suite == "blind_development"

def test_reviewed_suite_mix_uses_every_case_once(tmp_path: Path) -> None:
    cases = write_blind_suite_fixture(tmp_path, partition="blind_development", count=144)
    mix = reviewed_suite_mix(tmp_path, "blind_development")
    assert [case.case_id for case in mix] == [case.case_id for case in cases]
    assert {case.weight for case in mix} == {1}
```

Add an ablation test that injects the organizer loader and asserts case count `35`, organizer checksum, and five identical variant identities.

- [ ] **Step 2: Run focused RED**

```bash
uv run pytest tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_load_runner.py tests/unit/evaluation/test_ablation.py -k 'blind or suite or organizer' -q
```

- [ ] **Step 3: Implement suite selection by reusing existing runners**

In `run_evaluation`, route the two blind names through `load_blind_suite`; do not add a remote correctness scorer. In `load.py`, add `--suite` and choose `reviewed_benchmark_mix` only when it is omitted. In ablation, pass the selected suite into raw production and validation instead of hard-coding `evaluation/canonical`.

```python
if suite in {"blind_development", "blind_holdout"}:
    cases = load_blind_suite(suite, repository_root=root)
elif suite == "organizer_20260824":
    cases = load_suite(suite, repository_root=root)
```

Keep the original load default and original ablation default for compatibility.

- [ ] **Step 4: Run focused GREEN and evaluation aggregate**

```bash
uv run pytest tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_load_runner.py tests/unit/evaluation/test_ablation.py tests/integration/evaluation/test_runner.py -q
uv run ruff check src/finproof/cli/evaluate.py src/finproof/evaluation/load.py src/finproof/evaluation/ablation.py src/finproof/evaluation/ablation_experiment.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_load_runner.py tests/unit/evaluation/test_ablation.py
```

- [ ] **Step 5: Commit Task 3**

```bash
git add src/finproof/cli/evaluate.py src/finproof/evaluation/load.py src/finproof/evaluation/ablation.py src/finproof/evaluation/ablation_experiment.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_load_runner.py tests/unit/evaluation/test_ablation.py
git commit -m "test: run blind and organizer evaluation suites"
```

---

### Task 4: Produce a non-leaking holdout manifest and summary

**Files:**
- Create: `src/finproof/evaluation/holdout.py`
- Create: `tools/summarize_blind_holdout.py`
- Create: `tests/unit/evaluation/test_holdout_summary.py`

**Interfaces:**
- `HoldoutManifest`: protocol version, suite checksum, count `48`, exact family counts `14/12/8/8/6`, curator identity, authoring/reference versions, artifact hash, and creation timestamp.
- `HoldoutCandidateIdentity`: suite checksum, covered commit, image digest, artifact/configuration/prompt identities, HCX-007 model, response-version hash, and freeze timestamp.
- `summarize_holdout(manifest: HoldoutManifest, candidate: HoldoutCandidateIdentity, evaluation: EvaluationReport, load: LoadReport, *, evaluation_sha256: str, load_sha256: str) -> HoldoutSummary`.
- `HoldoutSummary`: candidate/replay identity, aggregate scores, request failures, latency, and hashes only; it contains no question, expected value, case ID, answer, evidence body, or per-case failure.

- [ ] **Step 1: Write RED tests for information minimization and identity mismatch**

```python
def test_holdout_summary_has_no_case_level_or_question_material() -> None:
    summary = summarize_holdout(manifest, candidate, evaluation, load, **report_hashes)
    serialized = summary.model_dump_json()
    assert "question" not in serialized
    assert "case_scores" not in serialized
    assert "HOLDOUT-" not in serialized

def test_holdout_summary_rejects_artifact_or_count_mismatch() -> None:
    with pytest.raises(ValueError, match="holdout identity differs"):
        summarize_holdout(
            manifest, candidate, wrong_artifact_evaluation, load, **report_hashes
        )
```

Also reject a suite checksum mismatch, count other than 48, wrong family totals, load request count other than 48, nonzero invalid-schema response, inconsistent response-version hashes, non-UTC time, malformed report hash, and unknown aggregate key.

- [ ] **Step 2: Run focused RED**

```bash
uv run pytest tests/unit/evaluation/test_holdout_summary.py -q
```

- [ ] **Step 3: Implement frozen Pydantic contracts and atomic CLI output**

Use existing `RatioScore`, `LatencySummary`, `EvaluationReport`, `LoadReport`, and the project JSON-writing pattern. The CLI reads the manifest, candidate identity, and two reports; computes both raw report hashes itself; validates all identities; and atomically writes one summary.

```python
class HoldoutSummary(_FrozenModel):
    protocol_version: Literal["blind-holdout-summary.v1"]
    suite_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    load_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    artifact_version: str
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: Literal[48]
    family_counts: dict[str, int]
    aggregates: dict[str, RatioScore]
    request_failure_count: int = Field(ge=0)
    latency: LatencySummary
```

Derive `response_version_sha256` only when all 48 load samples carry the same non-null
version hash; otherwise fail closed. Require that value and every replay identity match
the already-written `HoldoutCandidateIdentity`; the summary cannot define its own
candidate after execution.

- [ ] **Step 4: Run focused GREEN**

```bash
uv run pytest tests/unit/evaluation/test_holdout_summary.py -q
uv run ruff check src/finproof/evaluation/holdout.py tools/summarize_blind_holdout.py tests/unit/evaluation/test_holdout_summary.py
uv run mypy src/finproof/evaluation/holdout.py tools/summarize_blind_holdout.py tests/unit/evaluation/test_holdout_summary.py
```

- [ ] **Step 5: Commit Task 4**

```bash
git add src/finproof/evaluation/holdout.py tools/summarize_blind_holdout.py tests/unit/evaluation/test_holdout_summary.py
git commit -m "test: seal aggregate-only holdout evidence"
```

---

### Task 5: Author, review, and admit the 144 development cases and 48 private holdout cases

**Files:**
- Create: `evaluation/review_batches/batch-012-candidates.json` through `batch-017-candidates.json`
- Create: `evaluation/review_batches/batch-012-approved-questions-and-draft-plans.json` through `batch-017-approved-questions-and-draft-plans.json`
- Create: `evaluation/review_batches/batch-012-reference-review.json` through `batch-017-reference-review.json`
- Create: `evaluation/review_batches/batch-012-reference-approval.json` through `batch-017-reference-approval.json`
- Create: `evaluation/blind_development/*.jsonl`
- Create: `artifacts/evaluation/blind-holdout-manifest.json`
- Private NCP only: batches `018`-`019`, their references, and `evaluation/blind_holdout/*.jsonl`

**Interfaces:**
- Produces: reviewed 144-case development suite and a checksum-only 48-case holdout manifest.
- Depends on: Tasks 1-4 and the exact approved HCX external-transfer ceiling.

- [x] **Step 1: Calculate and approve external transfer bounds before calling HCX**

Record separately:

- six development question-generation calls;
- two private holdout question-generation calls;
- any planner calls used during independent draft-plan diagnosis, with the existing two-call maximum;
- the exact question/schema/registry content sent in each stage.

Do not infer approval from earlier Task 10 or ablation authorizations. Stop until the user approves the stated combined ceiling.

- [x] **Step 2: Generate development question packets one 24-case batch at a time**

Run for each ID `012` through `017`:

```bash
uv run python tools/generate_canonical_questions.py --batch-id 012 --output evaluation/review_batches/batch-012-candidates.json
```

Use the matching ID in each subsequent command. Validate all six packet hashes and exact 24-case counts before review.

- [x] **Step 3: Build and independently review development plans**

Construct each QueryPlan from the approved slot contract, not from expected result values. Run the existing local semantic validator. An independent reviewer checks question/plan fidelity, latest-data policy, registered fields, exact identifiers, top-k scope, and answerability. After 0 Critical / 0 Important, request one consolidated human approval over the six packet hashes rather than 144 individual confirmations.

- [x] **Step 4: Build deterministic references and review evidence**

For each approved batch:

```bash
uv run python tools/build_canonical_reference_packet.py --input evaluation/review_batches/batch-012-approved-questions-and-draft-plans.json --output evaluation/review_batches/batch-012-reference-review.json --artifact-dir artifacts
```

The independent reviewer verifies source locators, product identity/grain, rank/ties, numeric values, exclusions, evidence IDs, limitation language, and exact August artifact identity. Record one approval JSON per batch, then promote into `evaluation/blind_development` with the existing exact-checksum promotion command.

- [x] **Step 5: Have the separate curator create and seal holdout batches 018-019**

The curator uses a separate NCP worktree and a private prompt/slot patch that is never merged. Its exact family counts are:

```text
batch 018: cross_metric 8, holding_sector 8, missing_zero 3, unsupported 3, entity_variant 2
batch 019: cross_metric 6, holding_sector 4, missing_zero 5, unsupported 5, entity_variant 4
```

The curator runs the same schema, semantic, deterministic-reference, source-evidence, and independent-review checks, then places plaintext under a mode-`0700` NCP directory and writes only `artifacts/evaluation/blind-holdout-manifest.json` to the root worktree. The manifest must contain the suite checksum and metadata but no case IDs or text.

- [x] **Step 6: Run corpus aggregate checks**

```bash
uv run pytest tests/unit/evaluation/test_generate_canonical_questions.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evaluation/test_promote_canonical_reference_packet.py tests/unit/evaluation/test_blind_case_suite.py -q
uv run finproof evaluate --suite blind_development --mode deterministic-core --output artifacts/evaluation/blind-development-deterministic.json
uv run python tools/check_claim_evidence_report.py artifacts/evaluation/blind-development-deterministic.json
```

Expected: 144 cases load, no duplicate text/semantic identity, all deterministic supported claims and evidence satisfy the reviewed references. This is not a live-HCX score.

- [x] **Step 7: Commit only development references and the non-secret holdout manifest**

Stage only batches `012`-`017`, `evaluation/blind_development`, the deterministic report, and the manifest. Do not stage private holdout plaintext or unrelated older review drafts.

```bash
git add \
  evaluation/review_batches/batch-012-candidates.json \
  evaluation/review_batches/batch-012-approved-questions-and-draft-plans.json \
  evaluation/review_batches/batch-012-reference-review.json \
  evaluation/review_batches/batch-012-reference-approval.json \
  evaluation/review_batches/batch-013-candidates.json \
  evaluation/review_batches/batch-013-approved-questions-and-draft-plans.json \
  evaluation/review_batches/batch-013-reference-review.json \
  evaluation/review_batches/batch-013-reference-approval.json \
  evaluation/review_batches/batch-014-candidates.json \
  evaluation/review_batches/batch-014-approved-questions-and-draft-plans.json \
  evaluation/review_batches/batch-014-reference-review.json \
  evaluation/review_batches/batch-014-reference-approval.json \
  evaluation/review_batches/batch-015-candidates.json \
  evaluation/review_batches/batch-015-approved-questions-and-draft-plans.json \
  evaluation/review_batches/batch-015-reference-review.json \
  evaluation/review_batches/batch-015-reference-approval.json \
  evaluation/review_batches/batch-016-candidates.json \
  evaluation/review_batches/batch-016-approved-questions-and-draft-plans.json \
  evaluation/review_batches/batch-016-reference-review.json \
  evaluation/review_batches/batch-016-reference-approval.json \
  evaluation/review_batches/batch-017-candidates.json \
  evaluation/review_batches/batch-017-approved-questions-and-draft-plans.json \
  evaluation/review_batches/batch-017-reference-review.json \
  evaluation/review_batches/batch-017-reference-approval.json \
  evaluation/blind_development \
  artifacts/evaluation/blind-development-deterministic.json \
  artifacts/evaluation/blind-holdout-manifest.json
git commit -m "test: add latest-data blind development corpus"
```

---

### Task 6: Run live development evaluation and perform the single correction gate

**Files:**
- Generate: `artifacts/evaluation/blind-development-live.json`
- Generate: `artifacts/evaluation/blind-development-load.json`
- Create: `docs/review/BLIND_DEVELOPMENT_FAILURES.md`

No production file is preselected: doing so would invent a fix before an observed
failure. If the ledger accepts a Critical/Important finding, it must name the exact
single owner file and focused test file before either is edited.

**Interfaces:**
- Produces: exact-candidate live correctness and HTTP latency reports for 144 cases.
- Decision: zero Critical/Important failures means no behavior change; accepted failures permit one bounded correction checkpoint.

- [x] **Step 1: Deploy or select one exact pre-correction candidate on NCP**

Require the existing task-specific local variable without committing host information:

```bash
: "${FINPROOF_NCP_SSH_TARGET:?FINPROOF_NCP_SSH_TARGET is required}"
```

Verify the remote commit, image digest, artifact hash, HCX-007 configuration, container health, and read-only artifact mount before sending cases. The variable is supplied by the existing approved local operator configuration and is never written to the repository.

- [x] **Step 2: Obtain the exact live-evaluation HCX call-cap approval**

The ceiling accounts for 144 requests and the already frozen maximum of two planner plus two wording calls per request. State normal expected calls separately from the hard ceiling. Do not start on a broader or inherited approval.

- [x] **Step 3: Run live correctness once on NCP**

```bash
uv run finproof evaluate --suite blind_development --mode end-to-end --output artifacts/evaluation/blind-development-live.json
```

Copy the immutable report back by encrypted SSH and verify its SHA-256 before inspection.

- [x] **Step 4: Run every development question once through HTTP for latency — stopped before transmission after Step 3 found 111 terminal planner failures**

Require the configured endpoint without writing it to the repository:

```bash
: "${FINPROOF_EVALUATION_BASE_URL:?FINPROOF_EVALUATION_BASE_URL is required}"
```

```bash
bash scripts/run_load.sh --base-url "$FINPROOF_EVALUATION_BASE_URL" --suite blind_development --concurrency 1 --rate-per-second 0 --max-requests 144 --duration-seconds 43200 --output artifacts/evaluation/blind-development-load.json
```

Expected: 144 schema-valid HTTP 200 responses, failure count `0`, and each selected case sent once. Record mean, p95, maximum, and stage latency.

- [x] **Step 5: Classify observed failures without speculative fixes**

Write `BLIND_DEVELOPMENT_FAILURES.md` with the exact report hashes, metric failures, public error categories, owner module, severity, and disposition. Ignore Minor findings for the correction. If there are zero Critical/Important findings, record that fact and skip Steps 6-8.

- [x] **Step 6: For each accepted failure, write one focused RED in the owning existing suite**

Use the recorded provider output or smallest synthetic equivalent and assert the reviewed contract. Select the exact test file by owner:

```text
planner transport/repair -> tests/integration/planner/test_planner_service.py
semantic validation      -> tests/unit/query/test_semantic_validator.py
entity resolution        -> tests/unit/entity/test_resolver.py
holding resolution       -> tests/unit/entity/test_holding_resolution.py
cross-product holding    -> tests/integration/query/test_cross_product_holding_query.py
execution segmentation   -> tests/unit/query/test_execution_bundle.py
query execution           -> tests/integration/query/test_executor.py
state policy              -> tests/unit/quality/test_state_policy.py
metric/comparability      -> tests/unit/quality/test_metric_operation_policy.py
evidence/claim coverage   -> tests/unit/evidence/test_claim_verifier.py
answer construction       -> tests/integration/service/test_answer_service.py
API/publication           -> tests/integration/api/test_answer_endpoint.py
```

Run the single node ID and observe the expected contract failure before editing production code.

- [x] **Step 7: Implement the smallest owner-level correction and run focused GREEN**

Patch the shared owner reached by every affected caller. Do not add a new fallback, widen an allowlist, alter official data, weaken evidence, or change a frozen contract. Run the exact RED node IDs, then the nearest aggregate suite once.

- [x] **Step 8: Re-run only affected live cases and conduct one independent review**

Use an explicit case subset; never repeat all 144 solely after correction. The independent reviewer examines the approved failure contract and correction diff. Fix only actual Critical/Important direct violations inside the same bounded correction checkpoint, then re-review once. A frozen-contract change stops for a plan amendment.

- [x] **Step 9: Commit the live reports, failure ledger, tests, and correction together**

Use exact `git add` paths after inspecting the diff. Commit message:

```bash
git commit -m "fix: correct observed blind evaluation failures"
```

If no code changed, use:

```bash
git commit -m "test: record blind development acceptance"
```

---

### Task 7: Freeze the candidate, run holdout once, and close organizer ablation

**Files:**
- Create: `artifacts/evaluation/blind-holdout-summary.json`
- Create: `artifacts/evaluation/blind-holdout-candidate.json`
- Private NCP only: full holdout correctness/load reports
- Create: `artifacts/evaluation/ablation_organizer_20260824_raw/*.json`
- Create: `artifacts/evaluation/ablation-organizer-20260824.json`
- Modify: `docs/submission/PROPOSAL_EVIDENCE_INDEX.md`
- Modify: `tools/create_release_manifest.py`
- Modify: `tests/contract/test_release_manifest.py`

**Interfaces:**
- Produces: one no-peek 48-case holdout score and one current 35-case A-E ablation.
- Preserves: old interrupted `artifacts/evaluation/ablation*.json` files as diagnostics/user-owned changes.

- [x] **Step 1: Freeze and attest the candidate before revealing holdout**

Record commit, image digest, artifact logical hash, configuration hash, prompt versions,
HCX model, one smoke-response version hash, and holdout suite checksum in
`artifacts/evaluation/blind-holdout-candidate.json`. The curator receives this file
before execution and rejects any mismatch.

- [x] **Step 2: Obtain the holdout live-call approval and run exactly once**

The hard ceiling is 48 requests times the frozen two-planner/two-wording-call maximum. The curator runs correctness and one-request-per-case HTTP load in its private NCP workspace. The root receives no live commentary containing questions or failures.

- [x] **Step 3: Produce and verify the aggregate-only summary**

```bash
uv run python tools/summarize_blind_holdout.py --manifest artifacts/evaluation/blind-holdout-manifest.json --candidate artifacts/evaluation/blind-holdout-candidate.json --evaluation-report "$FINPROOF_PRIVATE_HOLDOUT_EVALUATION_REPORT" --load-report "$FINPROOF_PRIVATE_HOLDOUT_LOAD_REPORT" --output artifacts/evaluation/blind-holdout-summary.json
```

The curator executes this command and transfers only the summary. Verify its hashes, zero-leak schema, failure count, aggregate metrics, and p95. Do not change runtime behavior after reading it.

- [x] **Step 4: Obtain the exact ablation approval and run the current organizer suite**

For 35 cases, two repeats, one direct call plus one structured-planner call per case/repeat, the normal count is 140 HCX calls and the rate-limit-retry ceiling is 280.

```bash
bash scripts/run_ablation.sh --produce --suite organizer_20260824 --artifact-dir artifacts --measurement-dir artifacts/evaluation/ablation_organizer_20260824_raw --output artifacts/evaluation/ablation-organizer-20260824.json --repeats 2
```

Expected: 35 cases, five variants, shared checksum/environment/configuration, current commit/artifact/prompt identity, and error count `0`. Stop on provider interruption rather than promoting partial output.

Observed 2026-09-05: the fresh run produced all five 35-case/two-repeat measurements
with shared identity but returned nonzero A/B/C/D/E error counts `25/10/14/16/15`.
The complete report is retained as diagnostic evidence and is not described as a
zero-error acceptance; no additional live rerun or runtime correction followed.

- [x] **Step 5: Validate reports and update proposal evidence once**

Run focused report-contract tests and `tools/check_claim_evidence_report.py` for supported report types. Add actual holdout and ablation metrics with their limitations to `PROPOSAL_EVIDENCE_INDEX.md`; never claim monotonic improvement that the measurements do not show.

Add the development-live report, frozen holdout-candidate identity, aggregate-only
holdout summary, and current ablation report to the release-manifest required paths.
Do not add private holdout plaintext or case-level reports. Prove the manifest rejects
a missing or changed required file.

- [x] **Step 6: Commit Task 7**

```bash
git add artifacts/evaluation/blind-holdout-candidate.json artifacts/evaluation/blind-holdout-summary.json artifacts/evaluation/ablation_organizer_20260824_raw artifacts/evaluation/ablation-organizer-20260824.json docs/submission/PROPOSAL_EVIDENCE_INDEX.md tools/create_release_manifest.py tests/contract/test_release_manifest.py
git commit -m "perf: record blind holdout and current ablation"
```

---

### Task 8: Add the five mandatory submission ontologies

**Files:**
- Create: `ontology/common.ttl`
- Create: `ontology/bond_kr.ttl`
- Create: `ontology/etf_kr.ttl`
- Create: `ontology/etf_gl.ttl`
- Create: `ontology/fund_pub.ttl`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/contract/test_submission_ontology.py`
- Modify: `README.md`

**Interfaces:**
- Produces: parseable Turtle graphs rooted at `http://mafest.ai/product#` that describe the implemented identities, native grains, registered metrics/state, evidence, and provenance relationships.
- Does not produce: a second runtime rules engine or unsupported holdings facts.

- [x] **Step 1: Write the failing ontology contract test**

Use `rdflib` as a dev/test dependency only because no Turtle parser is currently installed.

```python
@pytest.mark.parametrize(
    "name",
    ("common.ttl", "bond_kr.ttl", "etf_kr.ttl", "etf_gl.ttl", "fund_pub.ttl"),
)
def test_submission_ontology_is_valid_turtle(name: str) -> None:
    graph = Graph().parse(ROOT / "ontology" / name, format="turtle")
    assert len(graph) > 0

def test_domain_classes_share_product_and_evidence_contract() -> None:
    graph = load_all_graphs()
    assert (FP.DomesticBond, RDFS.subClassOf, FP.Product) in graph
    assert (FP.DomesticETF, RDFS.subClassOf, FP.ListedProduct) in graph
    assert (FP.OverseasETF, RDFS.subClassOf, FP.ListedProduct) in graph
    assert (FP.PublicFund, RDFS.subClassOf, FP.Product) in graph
    assert (FP.hasEvidence, RDF.type, OWL.ObjectProperty) in graph
```

Also assert the exact five filenames, Korean labels, `instrument/listed_product/fund_item` grain individuals, source locator, raw/normalized value, quality status, applicable date, and no reference to live external APIs.

- [x] **Step 2: Run RED**

```bash
uv run pytest tests/contract/test_submission_ontology.py -q
```

Expected: missing dependency/files. Add the smallest compatible `rdflib` dev dependency
and resolve the lock, then rerun to observe missing ontology files:

```bash
uv add --dev 'rdflib>=7,<8'
uv lock
```

- [x] **Step 3: Write the minimum truthful Turtle graphs**

Start `common.ttl` with exact shared declarations:

```turtle
@prefix fp: <http://mafest.ai/product#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

fp:Product a owl:Class ; rdfs:label "금융상품"@ko .
fp:Evidence a owl:Class ; rdfs:label "근거"@ko .
fp:hasEvidence a owl:ObjectProperty ; rdfs:domain fp:Product ; rdfs:range fp:Evidence .
fp:rawValue a owl:DatatypeProperty ; rdfs:domain fp:Evidence ; rdfs:range xsd:string .
fp:normalizedValue a owl:DatatypeProperty ; rdfs:domain fp:Evidence .
fp:applicableDate a owl:DatatypeProperty ; rdfs:domain fp:Evidence ; rdfs:range xsd:date .
```

Each domain file adds only classes/properties represented by its official schema and registry. Plain ETF and ETN remain distinct, public fund identifies `itm_no` as `fund_item`, overseas one-year return is absent, and `BUYABLE_QUANTITY` is not an eligibility property.

- [x] **Step 4: Run GREEN and ontology aggregate**

```bash
uv run pytest tests/contract/test_submission_ontology.py tests/contract/test_competition_compliance.py -q
uv run ruff check tests/contract/test_submission_ontology.py
uv run mypy tests/contract/test_submission_ontology.py
```

- [x] **Step 5: Document and commit Task 8**

Add the ontology inventory and validation command to README.

```bash
git add ontology pyproject.toml uv.lock tests/contract/test_submission_ontology.py README.md
git commit -m "docs: add mandatory FinProof ontologies"
```

---

### Task 9: Build and visually verify the technical proposal

**Files:**
- Create: `docs/submission/FinProof_Technical_Proposal.pptx`
- Create: `docs/submission/FinProof_Technical_Proposal.pdf`
- Modify: `docs/submission/PROPOSAL_EVIDENCE_INDEX.md`
- Modify: `docs/submission/SUBMISSION_CHECKLIST.md`

**Interfaces:**
- Consumes: only verified report paths and hashes from Tasks 5-8.
- Produces: an editable deck and submission PDF covering the organizer's required proposal outline.

- [x] **Step 1: Load the presentation and PDF skills before authoring**

Follow their template, rendering, and artifact-operation requirements. Do not manually assemble a PDF without visual QA.

- [x] **Step 2: Create the exact 15-page narrative**

```text
1 cover and one-sentence value proposition
2 problem definition and 20/40/40 evaluation strategy
3 official/latest data boundary and Source Fidelity
4 end-to-end architecture and trust boundaries
5 ingestion, normalization, quarantine, and immutable artifact
6 ontology model and five submitted Turtle files
7 HCX intent planning and validated QueryPlan
8 native-grain cross-product execution and comparability partitions
9 deterministic evidence, claim verification, and safe failure
10 representative user scenario and five-field API flow
11 144+48 blind evaluation protocol and leakage controls
12 actual correctness, holdout, and A-E ablation results
13 actual latency, load, soak, and residual-risk results
14 expected effects, operational use, and product-family expansion
15 reproduction, endpoint/API contract, limitations, and evidence appendix
```

Every number must resolve to `PROPOSAL_EVIDENCE_INDEX.md`. State that the accepted soak is 517.063 seconds, not 24 hours; separate deterministic-core and live-HCX latency; do not claim unavailable holdings coverage.

- [x] **Step 3: Render every page and perform visual QA**

Verify Korean font rendering, margins, page numbers, graph/table labels, no clipping/overlap, readable diagrams, and consistent colors. Re-render after every material correction. Also extract PDF text and confirm all 15 headings and critical numeric claims.

- [x] **Step 4: Run an independent claim/design review**

Reviewer checks official required sections, source attribution, metric fidelity, architecture truth, limitations, and legibility. Only Critical/Important findings block; correct once and re-render.

- [x] **Step 5: Commit Task 9**

```bash
git add docs/submission/FinProof_Technical_Proposal.pptx docs/submission/FinProof_Technical_Proposal.pdf docs/submission/PROPOSAL_EVIDENCE_INDEX.md docs/submission/SUBMISSION_CHECKLIST.md
git commit -m "docs: add verified FinProof technical proposal"
```

---

### Task 10: Build the final candidate, deploy, and submit

**Files:**
- Modify if runtime changed: `artifacts/evaluation/final-load.json`
- Modify if runtime changed: `artifacts/evaluation/final-soak.json`
- Modify: `release/manifest.json`
- Modify: `docs/submission/RELEASE_RECORD.md`
- Modify: `docs/submission/SUBMISSION_CHECKLIST.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: one covered commit, metadata child, exact image digest, verified artifact/report hashes, NCP HTTPS endpoint, organizer-private-repository push, annotated tag, and freeze record.

- [ ] **Step 1: Decide whether Task 10 v22 performance evidence remains applicable**

If Tasks 1-9 changed only evaluation tools, tests, docs, ontology, or proposal assets, keep the sealed runtime candidate and its Task 10 reports. If any runtime/data/prompt/policy/image input changed, create a new covered candidate and obtain approval for one organizer-shaped 35-request load plus bounded 20-cycle soak; replace final reports only after zero failure/drift.

- [ ] **Step 2: Conduct the final independent review before the final gate**

Review only the approved spec, Tasks 1-10 diffs, final reports, ontology/proposal
deliverables, deployment plan, and submission checklist. Critical/Important findings
alone block. Apply at most one bounded correction, run its focused RED/GREEN checks,
and re-review once. Stop immediately at 0 Critical / 0 Important.

- [ ] **Step 3: Run the single mandatory full gate on the final candidate**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/check_competition_compliance.py --check
git diff --check
```

Record exact observed results. If code changes after this gate, run focused tests first and repeat this full gate exactly once on the new final candidate.

- [ ] **Step 4: Reproduce and verify the exact package**

```bash
: "${FINPROOF_COVERED_COMMIT:?FINPROOF_COVERED_COMMIT is required}"
bash scripts/clean_room_reproduce.sh . "$FINPROOF_COVERED_COMMIT"
uv run python tools/create_release_manifest.py --covered-commit "$FINPROOF_COVERED_COMMIT" --output release/manifest.json
uv run python tools/verify_release_manifest.py release/manifest.json
```

Verify the covered commit, image digest, artifact logical hash, blind/ablation report hashes, API schema hash, and clean-room result.

- [ ] **Step 5: Deploy the exact image to NCP and smoke-test HTTPS**

Use the existing encrypted SSH access and server secret file. Mount `/opt/finproof/artifacts` read-only, expose only HTTPS `GET /answer`, and verify health internally plus one non-destructive public schema request. Do not rebuild on the server or copy `.env.local` into the image.

- [ ] **Step 6: Obtain and verify the organizer private repository**

The user supplies or grants access to the organizer-provided repository once. Add it as a separate `organizer` remote; do not replace the personal `origin` mirror.

```bash
: "${FINPROOF_ORGANIZER_REPOSITORY:?FINPROOF_ORGANIZER_REPOSITORY is required}"
git remote get-url organizer
```

If `organizer` is absent, add it with
`git remote add organizer "$FINPROOF_ORGANIZER_REPOSITORY"`; if present, require its
reported URL to match exactly. Verify read access without changing `origin`. Do not push
until the metadata child and tag exist.

Confirm the private repository contains source, `pyproject.toml`/`uv.lock`, README, five ontology files, proposal PDF, API specification, and release metadata.

- [ ] **Step 7: Freeze, close documentation once, and record continuous operation**

Before `2026-09-06 23:59 KST`, record endpoint, tag, covered commit,
image/artifact/manifest hashes, submission time, operator checks, full-gate results, and
the 0 Critical / 0 Important verdict. Update STATUS and closure documents once, commit
the metadata child, then create the release tag on that child as required by
`RELEASE_RECORD.md`:

```bash
git add release/manifest.json docs/submission/RELEASE_RECORD.md docs/submission/SUBMISSION_CHECKLIST.md docs/implementation/STATUS.md
git commit -m "release: seal FinProof submission"
git tag -a finproof-submission -m "FinProof competition submission"
git push origin main
git push origin finproof-submission
git push organizer main
git push organizer finproof-submission
```

Before tagging, prove `FINPROOF_COVERED_COMMIT` is the metadata commit's parent and no
tag with that name exists. Leave only explicitly preserved user-owned files unstaged.
Keep the exact service active from `2026-09-07` through `2026-09-20`. After freeze,
permit monitoring and identical-image restart only; no code, data, prompt, policy,
image, or result change without organizer authorization.

---

## Execution order and user actions

Execute Tasks 1-4 first, then Task 5 authoring. The user is asked only for bounded HCX external-transfer approvals, one consolidated development-reference approval if required by the existing human-review gate, and the organizer private-repository invitation/URL. All other implementation, NCP execution, review, report generation, staging, commits, and pushes are handled by the agent workflow.
