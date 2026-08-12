# Preflight Task 3 Evaluation Control-Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the frozen Preflight Task 3 evaluation contracts, complete 207-column coverage accounting, strict seed migration, and deterministic model-only control-plane validators without creating production truth, storage, cryptographic custody, or release behavior.

**Architecture:** One closed JSON-Schema/Pydantic spine supplies immutable types to three artifact lanes (seed migration, coverage, and governance). Six focused deterministic validator modules own canonical I/O, reservations, history, runtime lifecycle, remediation, and reporting. A thin facade composes those modules and runs the generated adversarial matrix. Real stores, KMS, ACLs, clocks, signatures, runners, and network enforcement remain Phase 4 work.

**Tech Stack:** Python 3.12, Pydantic 2 strict/frozen models, JSON Schema Draft 2020-12, PyYAML, orjson/standard-library canonical JSON, hashlib/hmac synthetic vectors, pytest/Hypothesis, Ruff, mypy.

## Global Constraints

- Frozen design: `docs/superpowers/specs/2026-08-08-preflight-task3-evaluation-control-plane-design.md`.
- Frozen design SHA-256: `99ABA03D8D5D44705AF87159908963296BCC13BAEE4453BB8DC7B8DFB2FBB44C`.
- Candidate base commit: `2cdf70bbeb55ee7b7175ca48fe9637c027d7e61f`.
- Branch/worktree: `codex/preflight-safety` at `C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`.
- This plan supersedes only Task 3 of `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`.
- D-017 is immutable: Phase-2/Phase-3 checkpoints pin candidate bytes and provenance; Phase 4 replays both candidates in order; the Phase-2 result never guides or gates Phase 3; G0 precedes readiness and G1 records later gate evidence.
- Do not edit the frozen Task-3 design, `src/`, dependencies, lockfiles, production/deployment paths, source-material bytes, `START_HERE.md`, field/metric/planner/answer/quality/dataset runtime registries, or any path outside the frozen Section 11 allowlist.
- Task 3 validates models, projections, state transitions, and simulated transaction outcomes only. It does not claim real Ed25519 verification, physical ACL/KMS isolation, authoritative clock service, real multi-store CAS, direct-storage bypass prevention, or external submission.
- Preserve official competition rules, the submission freeze, source fidelity, one-use truth, cumulative truth, no hidden correction, and no unsupported public claim.
- Every behavior checkpoint is strict RED → minimal GREEN → relevant regression → independently reviewable commit.
- Tests must fail for the intended missing behavior after all prerequisites are committed. Import errors or absent prerequisite files are not acceptable RED evidence.
- `tools/evaluation_models.py`, `tools/evaluation_contracts.py`, `tools/evaluation_control.py`, `tests/contract/test_evaluation_governance.py`, and `docs/implementation/STATUS.md` have one coordinator writer. Parallel workers may read them only.
- No worker updates `STATUS.md`. The coordinator records observed commands and exact next task after integrating each commit.
- Implementation must not begin until the owner approves this plan and the planning checkpoint is reviewed and committed.
- The frozen design/reconciliation bytes are currently content-addressed but not yet a Git commit. This is an explicit stop condition. Before P0 staging, the owner must separately authorize a documentation-only freeze commit of the already-preserved design/reconciliation paths. The coordinator then records that exact 40-hex commit in both this plan's P0 execution record and `STATUS.md`, recomputes the plan SHA-256, and obtains implementation approval tied to those exact bytes. No RED or implementation edit may precede that sequence.

## Frozen Writable-Path Allowlist

Create only:

- `docs/superpowers/plans/2026-08-08-preflight-task3-evaluation-control-plane.md`
- `schemas/evaluation_common.schema.json`
- `schemas/aggregate_evidence.schema.json`
- `schemas/evidence_package.schema.json`
- `schemas/golden_expected_result.schema.json`
- `schemas/golden_expected_answer.schema.json`
- `schemas/evaluation_suite_manifest.schema.json`
- `schemas/evaluation_suite_history_attestation.schema.json`
- `schemas/evaluation_disposition_policy.schema.json`
- `schemas/evaluation_freeze_fingerprint.schema.json`
- `schemas/evaluation_runtime_attestation.schema.json`
- `schemas/evaluation_lifecycle_event.schema.json`
- `schemas/evaluation_private_control_bundle.schema.json`
- `schemas/evaluation_report.schema.json`
- `config/question_coverage.yaml`
- `config/question_coverage.lock.json`
- `config/evaluation_governance.yaml`
- `config/evaluation_governance.lock.json`
- `tools/build_coverage_report.py`
- `tools/build_seed_migration_manifest.py`
- `tools/evaluation_models.py`
- `tools/evaluation_contracts.py`
- `tools/evaluation_control.py`
- `tools/evaluation_control_core/__init__.py`
- `tools/evaluation_control_core/canonical_io.py`
- `tools/evaluation_control_core/storage_reservations.py`
- `tools/evaluation_control_core/history_registry.py`
- `tools/evaluation_control_core/runtime_lifecycle.py`
- `tools/evaluation_control_core/remediation.py`
- `tools/evaluation_control_core/reporting.py`
- `tests/contract/test_evaluation_contracts.py`
- `tests/contract/test_evaluation_models.py`
- `tests/contract/test_question_coverage.py`
- `tests/contract/test_evaluation_governance.py`
- `tests/contract/test_evaluation_control_canonical.py`
- `tests/contract/test_evaluation_control_reservations.py`
- `tests/contract/test_evaluation_control_history.py`
- `tests/contract/test_evaluation_control_lifecycle.py`
- `tests/contract/test_evaluation_control_remediation.py`
- `tests/contract/test_evaluation_control_reporting.py`
- `tests/golden/legacy_seed_migration_manifest.json`
- `tests/evaluation/README.md`

Modify only:

- `schemas/golden_case.schema.json`
- `schemas/evidence_record.schema.json`
- `tests/golden/seed_cases.jsonl`
- `tests/golden/README.md`
- `tests/contract/test_handoff_package.py`
- `docs/07_TESTING_AND_EVALUATION.md`
- `docs/09_RISK_REGISTER.md`
- `docs/10_DECISION_LOG.md`
- `docs/superpowers/specs/2026-08-07-preflight-safety-remediation-design.md`
- `docs/implementation/PHASE_GATES.md`
- `docs/implementation/QUALITY_LOOP.md`
- `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md`
- `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md`
- `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`
- `tools/verify_handoff.py`
- `HANDOFF_PACKAGE_MANIFEST.md`
- `docs/implementation/STATUS.md`

## Dependency and Commit Graph

~~~text
P0 planning checkpoint
  -> P1 handoff registration
  -> S schema/model spine
  -> M0 immutable legacy migration ledger -> M1 reviewed seed migration
  -> C 207-column coverage lock
  -> G governance policy/lock
       -> K0 canonical I/O
       -> K1 reservations
       -> K2 history/currentness/human scope
       -> K3 runtime lifecycle
       -> K4 conditional remediation
       -> K5 reporting/disclosure/readiness
  -> X facade and generated adversarial matrix (requires M1 + C + K5)
  -> H documentation, handoff, final review, and status
~~~

The graph is serial at shared-file boundaries. M0/M1 and C may be delegated after S, but only if they do not edit coordinator-owned shared files. K3 and K4 may be prepared in parallel after K2 because their production/test files are disjoint; the coordinator integrates them serially and runs the combined regression before K5.

---

### Task P0: Freeze the executable Task-3 plan checkpoint

**Files:**

- Create: `docs/superpowers/plans/2026-08-08-preflight-task3-evaluation-control-plane.md`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Verify the immutable planning inputs**

Run:

~~~powershell
Get-FileHash -Algorithm SHA256 -LiteralPath docs/superpowers/specs/2026-08-08-preflight-task3-evaluation-control-plane-design.md
~~~

~~~powershell
python tools/check_repo_root.py --expected-root .
git log -3 --oneline
~~~

~~~powershell
python tools/check_repo_root.py --expected-root .
git branch --show-current
~~~

Expected: the design hash is exactly `99ABA03D8D5D44705AF87159908963296BCC13BAEE4453BB8DC7B8DFB2FBB44C`; the one-line HEAD prefix matches the exact 40-hex documentation-only freeze commit already recorded by that checkpoint in `STATUS.md`; the reviewed commit scope contains the frozen design/reconciliation paths; the branch is `codex/preflight-safety`; and the preserved design records candidate base `2cdf70bbeb55ee7b7175ca48fe9637c027d7e61f`. Copy the exact STATUS commit into a `P0 Execution Record` appended to this plan; an empty result or mismatch stops the task.

- [ ] **Step 2: Record the plan checkpoint in STATUS**

Record only:

- the frozen design path/hash;
- that three exact-hash reviewers returned BLOCKER=0 and HIGH=0;
- this plan path and its SHA-256;
- current worktree/branch;
- “implementation not started; awaiting owner approval” while authoring, followed before P0 staging by the exact approval date/source, approved plan SHA-256, frozen design commit, and “P1 is next”;
- exact next task P1.

Do not claim any production check or implementation result.

- [ ] **Step 3: Close the approval evidence, then review and commit the two planning files**

After the documentation-only frozen-design commit exists, replace the authoring stop state in `STATUS.md` with the exact owner implementation approval, approved plan SHA-256, frozen-design commit, and P1 next-task statement. Recompute the plan hash and confirm the approval applies to it. Then run:

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- docs/superpowers/plans/2026-08-08-preflight-task3-evaluation-control-plane.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "docs: freeze Task 3 execution plan"
~~~

Expected staged paths: exactly the two listed files. Stop if the pre-existing index is not clean; do not reset, unstage, or overwrite preserved user changes without separate authorization.

---

### Task P1: Register the frozen design and dated plan in the handoff contract

**Files:**

- Modify: `tests/contract/test_handoff_package.py`
- Modify: `tools/verify_handoff.py`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write the focused handoff RED**

Add a test that independently names the exact files:

~~~python
from tools.verify_handoff import REQUIRED_FILES

TASK3_DESIGN = (
    "docs/superpowers/specs/"
    "2026-08-08-preflight-task3-evaluation-control-plane-design.md"
)
TASK3_PLAN = (
    "docs/superpowers/plans/"
    "2026-08-08-preflight-task3-evaluation-control-plane.md"
)

def test_task3_frozen_design_and_dated_plan_are_registered() -> None:
    assert TASK3_DESIGN in REQUIRED_FILES
    assert TASK3_PLAN in REQUIRED_FILES
    assert (ROOT / TASK3_DESIGN).is_file()
    assert (ROOT / TASK3_PLAN).is_file()
~~~

- [ ] **Step 2: Run RED and verify the failure reason**

~~~powershell
uv run pytest tests/contract/test_handoff_package.py::test_task3_frozen_design_and_dated_plan_are_registered -q
~~~

Expected RED: the design and plan are absent from `REQUIRED_FILES`. A syntax/import/file-not-found failure is not the intended RED.

- [ ] **Step 3: Implement the minimal registration**

Add both exact paths to `REQUIRED_FILES`, add both to the manifest’s explicit dated-design/plan list, and keep the dependency-free verifier importable under `python -S -B`.

- [ ] **Step 4: Run GREEN and handoff checks**

~~~powershell
uv run pytest tests/contract/test_handoff_package.py -q
uv run python tools/verify_handoff.py
uv run python -S -B tools/verify_handoff.py
~~~

- [ ] **Step 5: Commit the registration checkpoint**

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tests/contract/test_handoff_package.py tools/verify_handoff.py HANDOFF_PACKAGE_MANIFEST.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "chore: register frozen Task 3 control plane"
~~~

---

### Task S: Build the complete closed schema and Pydantic model spine

**Files:**

- Create: all 13 new schema files in the frozen allowlist
- Modify: `schemas/golden_case.schema.json`, `schemas/evidence_record.schema.json`
- Create: `tools/evaluation_models.py`, `tools/evaluation_contracts.py`
- Create importable no-behavior shells: `tools/build_coverage_report.py`, `tools/build_seed_migration_manifest.py`, `tools/evaluation_control.py`, `tools/evaluation_control_core/__init__.py`, `tools/evaluation_control_core/canonical_io.py`, `tools/evaluation_control_core/storage_reservations.py`, `tools/evaluation_control_core/history_registry.py`, `tools/evaluation_control_core/runtime_lifecycle.py`, `tools/evaluation_control_core/remediation.py`, `tools/evaluation_control_core/reporting.py`
- Create: `tests/contract/test_evaluation_models.py`, `tests/contract/test_evaluation_contracts.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write schema/model parity RED tests**

Use a literal schema inventory and require one strict model for every frozen `$def`:

~~~python
EXPECTED_SCHEMA_FILES = {
    "evaluation_common.schema.json",
    "aggregate_evidence.schema.json",
    "evidence_package.schema.json",
    "golden_expected_result.schema.json",
    "golden_expected_answer.schema.json",
    "evaluation_suite_manifest.schema.json",
    "evaluation_suite_history_attestation.schema.json",
    "evaluation_disposition_policy.schema.json",
    "evaluation_freeze_fingerprint.schema.json",
    "evaluation_runtime_attestation.schema.json",
    "evaluation_lifecycle_event.schema.json",
    "evaluation_private_control_bundle.schema.json",
    "evaluation_report.schema.json",
}

def test_schema_model_parity_census_is_exact() -> None:
    assert set(EVALUATION_SCHEMA_MODELS) == expected_def_inventory()
    assert set(path.name for path in SCHEMA_PATHS) == EXPECTED_SCHEMA_FILES
~~~

Also add focused tests for:

- `extra="forbid"`, strict scalar validation, frozen models, and deep immutability;
- exact lower-hex/base64/ID/tick/descriptor caps;
- deterministic sorted diagnostics `EVC001`–`EVC007`;
- aggregate evidence never replacing source evidence;
- rejection of floats, non-finite numbers, lone surrogates, duplicate keys, coercion, and post-parse mutation.

Add an interface-only RED that uses `importlib.util.find_spec` and literal `inspect.signature` expectations for every future builder/facade/core module. It must fail by assertion while modules are absent, never during test collection.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_models.py tests/contract/test_evaluation_contracts.py -q
~~~

Expected RED: the schema/model/interface inventory assertions report the exact absent artifacts. Collection and all existing handoff tests remain green.

- [ ] **Step 3: Implement all frozen shapes once**

Implement:

- every Section 4 `$def` and root schema with `additionalProperties: false`;
- Pydantic strict/frozen counterparts, `FrozenMap`, bounded readers, and Protocols;
- schema/model inventories as independent literals compared bidirectionally;
- exact pure `golden_case_policy_errors`, `aggregate_evidence_policy_errors`, and `evidence_package_policy_errors` functions with stable `EVC001`–`EVC007` diagnostics;
- external complete-object digests and canonical projections exactly as frozen.
- importable exact-signature shells for every later builder/facade/core module. Each unimplemented behavioral entry point raises `NotImplementedError("TASK3_BEHAVIOR_NOT_IMPLEMENTED")`; the interface tests pass, and K0-K5 behavioral REDs must fail only at that sentinel or at an expected returned diagnostic.

Downstream tasks may not invent or extend types. A missing type returns to this checkpoint for review.

- [ ] **Step 4: Run GREEN and static checks**

~~~powershell
uv run pytest tests/contract/test_evaluation_models.py tests/contract/test_evaluation_contracts.py -q
uv run ruff check tools/evaluation_models.py tools/evaluation_contracts.py tests/contract/test_evaluation_models.py tests/contract/test_evaluation_contracts.py
uv run mypy tools/evaluation_models.py tools/evaluation_contracts.py tests/contract/test_evaluation_models.py tests/contract/test_evaluation_contracts.py
~~~

- [ ] **Step 5: Commit the schema/model spine**

Stage every created schema plus the two modified schemas and four Python files explicitly; verify the cached path list before committing:

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- schemas/evaluation_common.schema.json schemas/aggregate_evidence.schema.json schemas/evidence_package.schema.json schemas/golden_expected_result.schema.json schemas/golden_expected_answer.schema.json schemas/evaluation_suite_manifest.schema.json schemas/evaluation_suite_history_attestation.schema.json schemas/evaluation_disposition_policy.schema.json schemas/evaluation_freeze_fingerprint.schema.json schemas/evaluation_runtime_attestation.schema.json schemas/evaluation_lifecycle_event.schema.json schemas/evaluation_private_control_bundle.schema.json schemas/evaluation_report.schema.json schemas/golden_case.schema.json schemas/evidence_record.schema.json tools/evaluation_models.py tools/evaluation_contracts.py tools/build_coverage_report.py tools/build_seed_migration_manifest.py tools/evaluation_control.py tools/evaluation_control_core/__init__.py tools/evaluation_control_core/canonical_io.py tools/evaluation_control_core/storage_reservations.py tools/evaluation_control_core/history_registry.py tools/evaluation_control_core/runtime_lifecycle.py tools/evaluation_control_core/remediation.py tools/evaluation_control_core/reporting.py tests/contract/test_evaluation_models.py tests/contract/test_evaluation_contracts.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: add strict evaluation schemas and models"
~~~

---

### Task M0: Freeze the immutable legacy-seed migration ledger

**Files:**

- Modify the S shell: `tools/build_seed_migration_manifest.py`
- Create: `tests/golden/legacy_seed_migration_manifest.json`
- Modify: `tests/contract/test_evaluation_contracts.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write REDs against the exact Git blob, not ambient bytes**

The test invokes the builder against commit `2cdf70bbeb55ee7b7175ca48fe9637c027d7e61f` and asserts:

~~~python
EXPECTED_BASE_BYTES = 12_221
EXPECTED_BASE_LF = 13
EXPECTED_BASE_CR = 0
EXPECTED_BASE_SHA256 = (
    "afbc2f3148a3a9508a4eff4e3f87d159"
    "4a06b6e539f79ef1d4caa6dc863c61c3"
)
EXPECTED_LEAF_COUNT = 302
EXPECTED_INVENTORY_SHA256 = (
    "ab4902c3aa6824450a3ecd4206326a0c"
    "dad9800c8eee067da97cefcbd9e51e21"
)
~~~

Require all 302 primitive leaves exactly once, a closed transform/default registry, and no invented result/product/review fact. Each source tuple occurs in exactly one mapping, while `target_pointers` and `target_ids` obey the frozen transform-specific cardinality rules; do not impose a false universal one-target rule. M0 computes the complete final mappings, target hashes, migrated semantic inventory, and reviewed projection in memory before changing the working seed file.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_contracts.py -q -k "legacy_seed or migration"
~~~

Expected RED: the importable S shell raises `TASK3_BEHAVIOR_NOT_IMPLEMENTED` when the pure bytes-to-final-manifest function is called with the exact base blob. Test collection and imports pass.

- [ ] **Step 3: Implement the dependency-free ledger builder**

Read the exact Git blob through a fixed subprocess argument list. Do not normalize line endings or read the working copy as the source inventory. Apply the closed transforms to an in-memory target, derive the complete final mapping/semantic inventory/review projection, and commit that complete ledger now. Implement `--check` to compare both the immutable base inventory and, once M1 writes the target JSONL, the target hashes/semantic inventory against this unchanged committed manifest.

- [ ] **Step 4: Run GREEN**

~~~powershell
uv run pytest tests/contract/test_evaluation_contracts.py -q -k "legacy_seed or migration"
uv run python tools/build_seed_migration_manifest.py --check
~~~

- [ ] **Step 5: Commit the immutable ledger before any seed edit**

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/build_seed_migration_manifest.py tests/golden/legacy_seed_migration_manifest.json tests/contract/test_evaluation_contracts.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "test: freeze legacy seed migration ledger"
~~~

---

### Task M1: Apply and review the faithful seed migration

**Files:**

- Modify: `tests/golden/seed_cases.jsonl`
- Modify: `tests/golden/README.md`
- Modify: `tests/contract/test_evaluation_contracts.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Add the migrated-target RED assertions**

Require:

- exactly 13 JSONL records and unique `case_id` values;
- every case validates against the strict schema;
- every transformed target resolves and every semantic node has exactly one producer;
- `migration_semantics_review.disposition == "faithful_migration_only"`;
- no new product IDs, expected results, approvals, reviewer identity, or human-review claims;
- regenerated manifest/review projection equals the committed bytes.

- [ ] **Step 2: Run RED before editing the seed file**

~~~powershell
uv run pytest tests/contract/test_evaluation_contracts.py -q -k "migrated_seed or semantic_inventory"
~~~

Expected RED: legacy seeds do not satisfy the frozen typed targets.

- [ ] **Step 3: Apply only the reviewed 302 transformations**

Migrate the 13 records according to the committed M0 ledger until their hashes and semantic inventory match it byte-for-byte. Do not rewrite or regenerate the manifest. Stop for the required independent-human acceptance of the ledger's exact reviewed-projection digest; metadata alone is not proof of review.

- [ ] **Step 4: Run GREEN**

~~~powershell
uv run pytest tests/contract/test_evaluation_contracts.py tests/contract/test_evaluation_models.py -q
uv run python tools/build_seed_migration_manifest.py --check
~~~

- [ ] **Step 5: Commit the reviewed seed migration**

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tests/golden/seed_cases.jsonl tests/golden/README.md tests/contract/test_evaluation_contracts.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: migrate golden seed contracts"
~~~

---

### Task C: Lock exact 207-column question coverage

**Files:**

- Create: `config/question_coverage.yaml`
- Create: `config/question_coverage.lock.json`
- Modify the S shell: `tools/build_coverage_report.py`
- Create: `tests/contract/test_question_coverage.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write the complete coverage RED**

Test exact catalog cardinalities `40/73/49/45 = 207`, exact case-sensitive pair equality, duplicate/missing/extra/case-fold rejection, stable `COV001`–`COV012` diagnostics, alias reachability, and the required explicit concepts.

~~~python
def test_coverage_lock_contains_exact_207_catalog_pairs() -> None:
    report = build_report_from_repository()
    assert report.table_counts == {
        "PRBD01N001": 40,
        "PREF01N001": 73,
        "PREF02N001": 49,
        "PRFD01N001": 45,
    }
    assert len(report.column_classifications) == 207
    assert report.structurally_valid is True
    assert report.all_supported is False
~~~

Require `risk_grade`, duration/evaluation-price ambiguities, and unverified `SRFC_IRT` semantics to remain `blocked_official_semantics`.

- [ ] **Step 2: Verify official data before using counts, then run RED**

~~~powershell
uv run python tools/audit_source_data.py --check
uv run pytest tests/contract/test_question_coverage.py -q
~~~

Expected RED: the importable builder shell raises `TASK3_BEHAVIOR_NOT_IMPLEMENTED` when the pure function is called with explicit in-memory catalog/coverage fixtures. The repository config/lock files are created only during GREEN.

- [ ] **Step 3: Implement the pure builder and checked lock**

Implement `build_coverage_report(catalog, coverage)` with no implicit I/O, clock, locale, environment, or network. The CLI strictly loads the four typed bundle members and implements byte-exact `--check`.

- [ ] **Step 4: Run GREEN**

~~~powershell
uv run pytest tests/contract/test_question_coverage.py -q
uv run python tools/build_coverage_report.py --check
~~~

- [ ] **Step 5: Commit coverage**

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- config/question_coverage.yaml config/question_coverage.lock.json tools/build_coverage_report.py tests/contract/test_question_coverage.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: lock 207-column question coverage"
~~~

---

### Task G: Freeze governance policy and generated lock

**Files:**

- Create: `config/evaluation_governance.yaml`
- Create: `config/evaluation_governance.lock.json`
- Modify the S shell: `tools/evaluation_control.py`
- Create: `tests/contract/test_evaluation_governance.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write governance-lock and registry REDs**

Require byte-exact regeneration, stable policy/hash/version metadata, and bidirectional inventories for:

- 27 HMAC domains and 27 matching formulas;
- two AEAD purposes;
- 13 signed-current store attestations, including the two claim-created dynamic-g0 rows;
- eight non-store signature purposes and only the identity-authority key-reuse pair;
- schedule offset profiles, caps, state/action enums, and transition/source maps;
- D-017 checkpoint/G0/G1 policy.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_governance.py -q
~~~

Expected RED: the importable facade shell raises `TASK3_BEHAVIOR_NOT_IMPLEMENTED` for the explicit in-memory governance-lock fixture. The repository config/lock files are created only during GREEN.

- [ ] **Step 3: Implement policy loading and lock generation**

Keep `tools/evaluation_control.py` thin: parse arguments, load typed inputs, call pure functions, sort diagnostics, and return a process status. Do not put domain state logic in the facade.

- [ ] **Step 4: Run GREEN**

~~~powershell
uv run pytest tests/contract/test_evaluation_governance.py -q
uv run python tools/evaluation_control.py --check
~~~

- [ ] **Step 5: Commit governance source and lock**

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- config/evaluation_governance.yaml config/evaluation_governance.lock.json tools/evaluation_control.py tests/contract/test_evaluation_governance.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: lock evaluation governance policy"
~~~

---

## Core Behavioral RED Protocol

S commits importable exact-signature shells for every K0-K5 module. In each K unit, the focused test is written against that committed interface, imports successfully, and reaches `TASK3_BEHAVIOR_NOT_IMPLEMENTED` or an exact expected missing-behavior diagnostic. Collection errors, missing modules, missing config files, and missing prerequisite schemas are invalid RED evidence. The unit then replaces only its owning shell behavior and reruns the focused and predecessor suites before commit.

---

### Task K0: Implement canonical I/O and projection primitives

**Files:**

- Modify the S shells: `tools/evaluation_control_core/__init__.py`, `tools/evaluation_control_core/canonical_io.py`
- Create: `tests/contract/test_evaluation_control_canonical.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write canonical REDs**

Cover duplicate keys at every depth, trailing data, floats/non-finite numbers, invalid UTF-8/surrogates, coercion, caps before parse, deep mutation, canonical overlay, complete/projection digest order, HMAC formula/tag/key-slot substitution, and signature-removed projections.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_canonical.py -q
~~~

- [ ] **Step 3: Implement the smallest canonical foundation**

Implement bounded byte readers, unique-key JSON load, canonical JSON v1 serialization, deep freeze, tagged SHA/HMAC projection helpers, exact byte/cap checks, and synthetic signature message construction. Do not implement real asymmetric verification.

- [ ] **Step 4: Run GREEN and commit**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_canonical.py tests/contract/test_evaluation_governance.py -q
uv run ruff check tools/evaluation_control_core/canonical_io.py tests/contract/test_evaluation_control_canonical.py
uv run mypy tools/evaluation_control_core/canonical_io.py tests/contract/test_evaluation_control_canonical.py
~~~

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/evaluation_control_core/__init__.py tools/evaluation_control_core/canonical_io.py tests/contract/test_evaluation_control_canonical.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: add canonical evaluation I/O"
~~~

---

### Task K1: Validate preclaim reservations and atomic scope preparation

**Files:**

- Modify the S shell: `tools/evaluation_control_core/storage_reservations.py`
- Create: `tests/contract/test_evaluation_control_reservations.py`
- Modify: `tools/evaluation_control_core/__init__.py`
- Modify: `tools/evaluation_control.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write reservation REDs**

Cover:

- exact simultaneous-maximum formulas and every cap-plus-one;
- head-independent preclaim subjects and schedule-before-scope construction;
- private-control/private-history reservation plans, receipts, allowances, and current pointers;
- refresh/rebase using the same allocation;
- four-entry scope plus 1–4 slot preparation all-or-none modeled CAS;
- crash/fault at each participant, second contender, fifth entry, duplicate/permuted ordinals;
- loser artifacts remaining provisional only and nonmembership before modeled reap;
- no public reservation plan/receipt/usage/schedule bytes.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_reservations.py -q
~~~

- [ ] **Step 3: Implement pure reservation validators**

Return typed sorted diagnostics and modeled all-or-none successor sets. No filesystem/store mutation occurs in these functions.

- [ ] **Step 4: Run GREEN and commit**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_reservations.py tests/contract/test_evaluation_control_canonical.py -q
~~~

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/evaluation_control_core/storage_reservations.py tests/contract/test_evaluation_control_reservations.py tools/evaluation_control_core/__init__.py tools/evaluation_control.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: validate evaluation storage reservations"
~~~

---

### Task K2: Validate history, signed currentness, human review, and scope deadlines

**Files:**

- Modify the S shell: `tools/evaluation_control_core/history_registry.py`
- Create: `tests/contract/test_evaluation_control_history.py`
- Modify: `tools/evaluation_control_core/__init__.py`
- Modify: `tools/evaluation_control.py`
- Modify: `tests/contract/test_evaluation_governance.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write history/currentness REDs**

Cover:

- immutable genesis, no reset/fork, stale head/prefix, bad Sparse-Merkle path;
- complete signed-current tuples and dynamic-g0 claim creation/binding;
- five-registry coherent read set plus independent clock/authority/current readers;
- exact `reference_truth_derivation_errors`, `reference_executor_disjointness_errors`, and `reference_truth_suite_errors` positives and source/artifact/executor/substitution mutations;
- checkpoint provenance subject, owner pin receipt, repository key tuple/signature message, exact Git object ID/tree/ancestry, and pre-execution order witness validation through `suite_history_policy_errors` and `evaluation_control_errors`; final G0 witnesses remain K5-owned;
- every member/branch/cap/current-reader/validation-versus-write race of `non_open_irreversible_action_authority_guard_errors`, producing the one complete binding reused by later branch validators;
- disjointness-handle absent→occupied uniqueness;
- private fingerprint/history source not copied to public metadata;
- review-session active→terminal durability, stable identity/non-alias and clock-domain equality;
- `[P2,P3,RC0,RC1]` scope order, schedule profile/ref, final commit-tick recheck;
- deadline−1/equality/+1, no-claim close, child parent-deadline resolution, zero-channel audit, and no premature scope completion;
- streamed archive gaps/permutation/substitution/cap+1.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_history.py tests/contract/test_evaluation_governance.py -q
~~~

- [ ] **Step 3: Implement the history-owned validators**

Keep reference-truth, checkpoint-pin/pre-execution, irreversible-authority, registry/currentness, review/scope, and deadline validation in `history_registry.py`. Return modeled successor descriptors and diagnostics; do not create a Git repository adapter, signer, store, or clock service.

- [ ] **Step 4: Run GREEN and commit**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_history.py tests/contract/test_evaluation_control_reservations.py tests/contract/test_evaluation_governance.py -q
~~~

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/evaluation_control_core/history_registry.py tests/contract/test_evaluation_control_history.py tools/evaluation_control_core/__init__.py tools/evaluation_control.py tests/contract/test_evaluation_governance.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: validate evaluation history and scope"
~~~

---

### Task K3: Validate runtime, truth, scoring, and post-freeze lifecycle

**Files:**

- Modify the S shell: `tools/evaluation_control_core/runtime_lifecycle.py`
- Create: `tests/contract/test_evaluation_control_lifecycle.py`
- Modify: `tools/evaluation_control_core/__init__.py`
- Modify: `tools/evaluation_control.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write lifecycle REDs**

Cover:

- claim/dispatch/ingress lineage and exactly one pre-egress fenced retry;
- byte-identical reuse and fresh revalidation of the K2 irreversible-action authority binding for claim, dispatch, truth-session redeem, scoring start, and outcome finalize; mutate every action kind/member/current generation and interpose an authority successor before the modeled write;
- 301/302/303/307/308/reconnect/late-output ambiguity;
- truth-release commit before decryption and one-use terminalization;
- AEAD key/nonce/recovery/session/pointer all-or-none transitions and nonce uniqueness;
- capability available/redeemed/revoked branches, authority conflict, deadline, and crash recovery;
- runtime/scoring leases, prefix sealing, complete/objective-error/authority-start/authority-finalize branches;
- post-outcome before report, no durable-outcome rewrite, factual reporting while allowed;
- dynamic early submission-freeze bound and private postfreeze incomplete-scope fence;
- no fabricated public outcome/report after freeze.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_lifecycle.py -q
~~~

- [ ] **Step 3: Implement the runtime state validator**

Implement strict branch-discriminated pure functions and typed transaction plans. Every caller-supplied witness is checked against the required independently current-reader result model. Do not create live capability, token, lease, clock, KMS, or worker services.

- [ ] **Step 4: Run GREEN and commit**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_lifecycle.py tests/contract/test_evaluation_control_history.py -q
~~~

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/evaluation_control_core/runtime_lifecycle.py tests/contract/test_evaluation_control_lifecycle.py tools/evaluation_control_core/__init__.py tools/evaluation_control.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: validate evaluation runtime lifecycle"
~~~

---

### Task K4: Validate the one conditional remediation child

**Files:**

- Modify the S shell: `tools/evaluation_control_core/remediation.py`
- Create: `tests/contract/test_evaluation_control_remediation.py`
- Modify: `tools/evaluation_control_core/__init__.py`
- Modify: `tools/evaluation_control.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write remediation REDs**

Cover:

- precommitted RC1 identity and distinct parent/child release cycles;
- blinded private join, 32-byte private salt, transient fixed padding, recovery reuse only;
- signer-current consume and approval result/ack ordering;
- owner decline/expiry/withdrawal/activate races;
- byte-identical reuse and fresh revalidation of the K2 irreversible-action authority binding for `child_activate`, including changed-instruction/freeze races;
- parent revision/current authority changes before child activation;
- exact comparability and build-extension evidence;
- no third/reset/replacement cycle and no postfreeze activation;
- no private approval/base/scope/schedule hash in public fingerprint.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_remediation.py -q
~~~

- [ ] **Step 3: Implement remediation validators**

Own only private join, owner action, candidate-cycle resolution, child activation/closure, and related fingerprint-extension validation. Reuse canonical/history/runtime types; do not duplicate their logic.

- [ ] **Step 4: Run GREEN and commit**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_remediation.py tests/contract/test_evaluation_control_history.py tests/contract/test_evaluation_control_lifecycle.py -q
~~~

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/evaluation_control_core/remediation.py tests/contract/test_evaluation_control_remediation.py tools/evaluation_control_core/__init__.py tools/evaluation_control.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: validate conditional remediation"
~~~

---

### Task K5: Validate reports, privacy projections, correction, and release readiness

**Files:**

- Modify the S shell: `tools/evaluation_control_core/reporting.py`
- Create: `tests/contract/test_evaluation_control_reporting.py`
- Modify: `tools/evaluation_control_core/history_registry.py`
- Modify: `tools/evaluation_control_core/__init__.py`
- Modify: `tools/evaluation_control.py`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write reporting/readiness REDs**

Cover:

- deterministic disposition and private/public report reconciliation;
- evidence package/aggregate evidence with source support;
- K=10 overall and K=5 cell/complement disclosure floors;
- original report immutability and exactly one zero-budget correction lineage;
- cause-independent revoked public shape, preallocated IDs, epoch timestamp/fixed role;
- common private publication-not-before and no early lifecycle/history/report replication;
- 100,002-entry maximum dossier, 196 shards, 512 entries/shard; reject entry 100,003, shard 197, and shard entry 513;
- verified-publication receipt tag/key/projection and staged outbox bytes;
- three states: invalid report, valid-but-embargoed, current enable/readiness with exact bytes;
- release-action current g0/reset/fork/replay/policy drift;
- both pre-execution witnesses plus both final repository-order witnesses through the immutable G0 evaluation-complete candidate, ordered D-017 replay, rejection of reconstructed/later candidate bytes, and categorical rejection of G1 as a readiness input;
- branch-specific reuse of the K2 irreversible-action authority binding for report publication, enable, readiness, release-action, and every controlled read;
- every read’s coherent current authority/history/human/identity/release/sink/slot/nonce fence.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_reporting.py -q
~~~

- [ ] **Step 3: Implement reporting validators and access facade**

Build private/public projections, dossier streaming validation, `published_report_errors`, `release_readiness_errors`, publication/enable action validation, and `DisclosureOutboxReadTransaction` as model-only pure orchestration over injected typed readers. K5 owns final-witness/G0/D-017 readiness and G1-exclusion logic; it reuses rather than reimplements K2 checkpoint/pre-execution and authority validation. Do not provide a direct blob-reader bypass.

- [ ] **Step 4: Run GREEN and commit**

~~~powershell
uv run pytest tests/contract/test_evaluation_control_reporting.py tests/contract/test_evaluation_control_lifecycle.py tests/contract/test_evaluation_control_remediation.py -q
~~~

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/evaluation_control_core/reporting.py tests/contract/test_evaluation_control_reporting.py tools/evaluation_control_core/history_registry.py tools/evaluation_control_core/__init__.py tools/evaluation_control.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: validate evaluation reporting and readiness"
~~~

---

### Task X: Integrate the thin facade and generated adversarial matrix

**Files:**

- Modify: `tools/evaluation_control.py`
- Modify: `tools/evaluation_control_core/__init__.py`
- Modify: `tests/contract/test_evaluation_governance.py`
- Modify: `docs/implementation/STATUS.md`

**Dependencies:** M1, C, G, K0–K5.

- [ ] **Step 1: Write the integration RED**

Add one generated matrix test whose inventory is independently literal and whose rows cover:

- all 27 HMAC domains and formulas;
- both AEAD purposes;
- all 13 signed-current stores and eight non-store signature purposes;
- schema/model/config/lock bidirectional parity;
- max-shape/cap+1 boundaries;
- four-slot atomic preparation;
- all three reference-truth validator families, disjointness, and source/artifact/executor substitution;
- checkpoint owner-pin trust tuple, Git object/tree/OID mutations, pre-execution witness, G0 final-witness/readiness/G1 chronology, and D-017 no-feedback;
- every `irreversible_action_authority_binding` member/branch/cap/current-reader/write-race mutation across K2-K5 actions;
- revoked-cause byte and availability noninterference;
- disjointness-handle uniqueness/private boundary;
- release-action/outbox/access-gate races;
- schedule/deadline/freeze-fence boundaries;
- blinded join recovery/substitution;
- stale current readers, CAS losers, crash/replay, missing/extra/tag/key/projection mutations.

~~~python
def test_late_control_plane_acceptance_matrix_is_complete() -> None:
    assert matrix_inventory() == frozen_expected_matrix_inventory()
    assert run_positive_matrix() == ()
    assert all(case.expected_code in run_mutation(case) for case in mutation_matrix())
~~~

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_evaluation_governance.py::test_late_control_plane_acceptance_matrix_is_complete -q
~~~

Expected RED: the facade/matrix does not yet enumerate all frozen contracts.

- [ ] **Step 3: Complete only facade routing and matrix generation**

The facade parses strict inputs, obtains injected reader models, dispatches to the six owning modules, sorts diagnostics, and exposes `--check`. It must not reproduce domain logic.

- [ ] **Step 4: Run the full Task-3 GREEN slice**

~~~powershell
uv run pytest tests/contract/test_evaluation_models.py tests/contract/test_evaluation_contracts.py tests/contract/test_question_coverage.py tests/contract/test_evaluation_governance.py tests/contract/test_evaluation_control_canonical.py tests/contract/test_evaluation_control_reservations.py tests/contract/test_evaluation_control_history.py tests/contract/test_evaluation_control_lifecycle.py tests/contract/test_evaluation_control_remediation.py tests/contract/test_evaluation_control_reporting.py -q
uv run python tools/build_seed_migration_manifest.py --check
uv run python tools/build_coverage_report.py --check
uv run python tools/evaluation_control.py --check
~~~

- [ ] **Step 5: Commit the integration gate**

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/evaluation_control.py tools/evaluation_control_core/__init__.py tests/contract/test_evaluation_governance.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "test: enforce Task 3 adversarial matrix"
~~~

---

### Task H: Reconcile documentation, handoff evidence, and final review

**Files:**

- Create: `tests/evaluation/README.md`
- Modify: `docs/07_TESTING_AND_EVALUATION.md`
- Modify: `docs/09_RISK_REGISTER.md`
- Modify: `docs/10_DECISION_LOG.md`
- Modify: `docs/superpowers/specs/2026-08-07-preflight-safety-remediation-design.md`
- Modify: `docs/implementation/PHASE_GATES.md`
- Modify: `docs/implementation/QUALITY_LOOP.md`
- Modify: `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md`
- Modify: `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md`
- Modify: `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`
- Modify: `tests/contract/test_handoff_package.py`
- Modify: `tools/verify_handoff.py`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`
- Modify: `docs/implementation/STATUS.md`

- [ ] **Step 1: Write documentation/handoff REDs before prose edits**

Assert exact D-017 wording, G0/G1 order, registry counts `27/2/13/8`, frozen Task-3 paths, model-only/Phase4 boundary, and no unsupported “real enforcement” claim.

- [ ] **Step 2: Run RED**

~~~powershell
uv run pytest tests/contract/test_handoff_package.py tests/contract/test_evaluation_governance.py -q
~~~

- [ ] **Step 3: Reconcile only the authorized documents**

Describe implemented contracts and preserve the Section 15 backlog as Phase4/residual-risk work. Do not weaken official precedence, submission freeze, source fidelity, one-use truth, disclosure, or no-postfreeze-result rules.

- [ ] **Step 4: Create the reviewable reconciliation candidate**

Run the focused documentation/handoff slice, update `STATUS.md` only with observed focused results and candidate scope, then commit the authorized reconciliation paths:

~~~powershell
uv run pytest tests/contract/test_handoff_package.py tests/contract/test_evaluation_governance.py -q
uv run python tools/verify_handoff.py
uv run python -S -B tools/verify_handoff.py
~~~

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tests/evaluation/README.md docs/07_TESTING_AND_EVALUATION.md docs/09_RISK_REGISTER.md docs/10_DECISION_LOG.md docs/superpowers/specs/2026-08-07-preflight-safety-remediation-design.md docs/implementation/PHASE_GATES.md docs/implementation/QUALITY_LOOP.md docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md tests/contract/test_handoff_package.py tools/verify_handoff.py HANDOFF_PACKAGE_MANIFEST.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "docs: reconcile Task 3 control plane"
~~~

- [ ] **Step 5: Obtain exact-commit independent implementation review**

Give all reviewers the same candidate commit hash:

- one schema/model/coverage/migration reviewer;
- one crypto/privacy/state-machine reviewer;
- one governance/scope/adversarial reviewer.

Fix each BLOCKER/HIGH through a new focused RED→GREEN commit, then repeat exact-hash review. Record MEDIUM/Phase4 findings in the existing backlog without expanding Task 3. Do not proceed until BLOCKER=0 and HIGH=0 on one common commit.

- [ ] **Step 6: Run the full mandatory gate on the post-review bytes**

~~~powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python -S -B tools/verify_handoff.py
uv run python tools/build_seed_migration_manifest.py --check
uv run python tools/build_coverage_report.py --check
uv run python tools/evaluation_control.py --check
~~~

~~~powershell
python tools/check_repo_root.py --expected-root .
git diff --check
~~~

Also run the integration/load/soak commands required by `docs/07_TESTING_AND_EVALUATION.md` only when the implemented change crosses that document’s API/performance/release threshold. Task-3 model-only work must not fabricate those results.

- [ ] **Step 7: Record results and repeat the full gate after the STATUS edit**

Update `STATUS.md` with only the outputs observed in Step 6, the common reviewed commit, B/H counts, residual backlog, and exact next task. Then rerun every Step-6 command on those final working bytes. Any failure reopens the owning RED→GREEN checkpoint and requires a new common-hash review plus another full Step-6/Step-7 loop.

- [ ] **Step 8: Commit only the final STATUS disposition**

~~~powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "docs: record Task 3 review disposition"
~~~

- [ ] **Step 9: Prove final scope and leave a clean worktree**

~~~powershell
python tools/check_repo_root.py --expected-root .
git status --short
git diff --check
~~~

Expected: no path outside the frozen allowlist changed, all recorded commands have observed output, `STATUS.md` names the exact next task, and the worktree is clean.

## Implementation Backlog Boundary

The following are intentionally not Task-3 expansion points:

- real Ed25519 vectors, deployment keys/fingerprints, physical ACL/KMS/clock/CAS/network enforcement;
- operational measurement of the 100,002-entry dossier;
- real publication-not-before scheduling/replication enforcement;
- same-row signing-key operational reuse wording;
- the external submission adapter/manual handoff;
- any item that requires changing official rules, submission freeze, source fidelity, cryptographic domains, truth semantics, one-use state, disclosure policy, or submission state.

If implementation reveals that one of these changes a core invariant or needs a new path/dependency/subsystem, stop and request a new frozen brief. Do not patch around it.
