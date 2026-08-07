# Preflight Safety Remediation Design

**Status:** APPROVED_BY_USER on 2026-08-07

**Scope:** repository safety and implementation contracts before Phase 1 production code

**Decision owner:** repository owner

## 1. Purpose

FinProof has a strong evidence-first product design, but the handoff cannot safely begin
implementation while repository isolation, agent orchestration, instruction authority,
evaluation independence, release provenance, and the Python 3.12 toolchain remain unresolved.

This preflight changes those contracts without implementing the financial query engine. Its
output is a safe, testable starting point for Phase 1 Task 1.

## 2. Approaches considered

### A. Git-only repair

Create a local repository and continue with the existing prompts.

Rejected because it leaves conflicting task scopes, an unsafe instruction/data authority
boundary, evaluation leakage, and a self-referential release sequence.

### B. Comprehensive bounded preflight — selected

Isolate Git first, then repair the repository-owned orchestration, authority, evaluation,
release, and toolchain contracts. Preserve the frozen FinProof product architecture and avoid
speculative financial semantics.

Selected because every change removes a demonstrated blocker and can be verified before
production behavior begins.

### C. Full redesign

Replace the existing architecture, plans, schemas, and prompts.

Rejected because the core design—HyperCLOVA X planning followed by deterministic execution,
evidence construction, and verification—is sound. A rewrite would add risk without addressing
the specific blockers more effectively.

## 3. Non-negotiable invariants

1. The Git top-level path must equal the resolved workspace path before any status, stage,
   commit, tag, push, or release operation.
2. `git add .`, broad home-relative paths, and unresolved staging targets are prohibited.
3. Official instruction documents and official datasets occupy different trust planes.
4. Workbook cells, product descriptions, and user questions are untrusted data and never
   executable instructions.
5. Only HyperCLOVA X may act as a generative model in production or evaluation runtime.
6. Non-HCX development agents may review code, but may not generate sealed evaluation truth,
   production answers, benchmark ground truth, or runtime artifacts.
7. Financial behavior is not invented during preflight. Unresolved metric/state semantics stay
   blocked or explicitly unsupported.
8. A quality claim requires recorded commands, observed outputs, artifact versions, and a clean
   exact-root worktree.

## 4. Repository and Git safety

### 4.1 Local isolation

The reviewed handoff is captured as the local `main` baseline. Preflight work occurs on
`codex/preflight-safety` in `.worktrees/preflight-safety`, which is ignored by Git.

No remote is created or changed during preflight. The organizer-provided GitHub Organization
private repository remains the official submission destination. A personal private repository
may later be configured only as an explicitly approved development mirror.

### 4.2 Executable hard gate

Create `tools/check_repo_root.py` with one responsibility: resolve the expected workspace and
the Git top level and exit non-zero unless they are identical. The command accepts an explicit
`--expected-root`; it never derives authority from a parent repository.

Every repository prompt and release plan invokes this check before its first Git command.
Tests cover an exact root, an ancestor repository, a missing repository, and a linked worktree.

### 4.3 Staging contract

Plans list exact paths for every checkpoint. Directory-level staging is allowed only when the
task owns the entire named directory and the coordinator verifies its diff. `git add .`,
`git add tests`, and equivalent broad staging patterns are forbidden.

## 5. Repository-owned quality loop

Create `docs/implementation/QUALITY_LOOP.md` as the only normative orchestration contract.
Other prompts state each rule once and link to this file.

### 5.1 Scope and ownership

- The coordinator selects exactly one incomplete `STATUS.md` task.
- It freezes a task brief containing scope, interfaces, acceptance tests, allowed paths,
  source hashes, and base commit.
- Only subitems with no shared writable files may run concurrently.
- One writer owns each file. `STATUS.md` is coordinator-owned.
- Shared contracts are frozen before implementation fan-out.

### 5.2 Roles

- **Oracle author:** writes focused failing tests and proves RED against the base commit.
- **Domain/data reviewer:** checks grain, metric, state, currency, period, and source fidelity.
- **Security reviewer:** checks trust boundaries, allowlists, secrets, egress, and resource caps.
- **Implementer:** makes the smallest change that satisfies the frozen task.
- **Spec verifier:** reviews an anonymized diff against the frozen brief without the implementer
  narrative or earlier reviewer conclusions.
- **Execution verifier:** uses a fresh checkout to rerun commands and adversarial/differential
  checks; it does not trust reported results.

Development agents may be combined when the task is small, except that an implementer cannot
serve as either final verifier for its own change.

### 5.3 Review and retry budget

1. Candidate 1 is reviewed by both verifiers.
2. A targeted fix may create Candidate 2.
3. One final targeted fix may create Candidate 3.
4. Infrastructure-only transient failures receive one separately recorded retry.
5. Remaining BLOCKER or HIGH findings after Candidate 3 set the task to `BLOCKED`; they do not
   trigger an unbounded loop.

High-risk changes—source normalization, state/eligibility, metric policy, SQL compilation,
claim verification, API contract, or release provenance—require both verifier approvals.

### 5.4 Pass gate

- BLOCKER and HIGH findings: zero
- deterministic contract, evidence, and API failures: zero
- source manifest and frozen audit: exact match
- focused RED/GREEN evidence: recorded
- relevant regression and adversarial suites: observed green
- sealed holdout: threshold met only after prompt/model/config freeze
- exact Git root and clean worktree: verified
- MEDIUM waiver: named human owner, evidence, reason, and expiry date

Subjective reactions such as “looks AAA” or “the reviewer is impressed” are never a pass gate.

## 6. Instruction and data trust planes

Revise the precedence contract as follows:

1. Official competition notices and attributable organizer/Discord answers.
2. Allowlisted official instruction documents identified by path and SHA-256 in the input
   manifest.
3. `OFFICIAL_OVERRIDE` and `FROZEN` decision-log entries.
4. Frozen design and repository-owned quality loop.
5. Current task plan, versioned config, and schemas.
6. Code comments and implementation details.

Official workbooks and their cells are authoritative facts for their declared fields, snapshot,
and source lineage, but never instruction authority. Product text is always treated as data.

The decision log records that no additional organizer notice was supplied as of 2026-08-07.

## 7. Evaluation independence and coverage

### 7.1 Dataset split

Evaluation assets are separated into:

- **open regression:** visible during implementation and rerun continuously;
- **locked validation:** visible results only at named checkpoints;
- **sealed holdout:** human-curated truth unavailable to implementers until the release candidate
  freezes prompt, model, config, schema, and code hashes.

Failure on a consumed sealed holdout invalidates it for further tuning. A corrected release
candidate requires a newly sealed set. The release report publishes denominators, failures, and
version hashes rather than only aggregate percentages.

### 7.2 Typed golden contract

`expected_plan` must validate against the canonical QueryPlan contract. Expected results use
typed product identifiers, order/tie groups, exact decimal strings, warning codes, exclusion
counts, and evidence requirements. Expected answers are structured claims; Korean style review
is separate from factual correctness.

### 7.3 Coverage matrix

Create a machine-readable field/metric coverage report across all 207 official columns. Each
officially relevant question concept is classified as:

- supported with registry and tested source mapping;
- intentionally unsupported with an answer limitation;
- blocked pending official semantic clarification;
- source-unavailable.

The `risk_grade` alias/registry mismatch is a required failing preflight check. Preflight may map
it only when the official column meaning, product type, null semantics, ordering, and evidence
rule are documented. Other gaps such as manager, base index, strategy, replication, coupon,
duration, and evaluation price follow the same rule.

### 7.4 Aggregate evidence

Add a versioned aggregate-proof contract for counts, ranks, exclusions, and calculations. It
contains dataset/artifact hash, execution-plan hash, segment/partition, predicate and policy IDs,
candidate counts by stage, ordered result IDs or a content hash, calculation inputs, and
exclusion-reason counts. It complements rather than replaces source-cell evidence.

## 8. HyperCLOVA X boundary

Phase 0 adds a non-production connectivity spike for the selected HCX interface. It records model
availability, Structured Outputs support, supported JSON Schema subset, service-app approval,
quota, timeout behavior, and representative latency without changing official answer behavior.

The evaluation renderer remains deterministic. Optional free-form HCX verbalization is disabled
in evaluation mode unless every emitted material claim can be projected from a verified,
closed structured-claim grammar.

## 9. Release provenance

The release sequence becomes:

1. Freeze and commit behavior-sensitive code, config, schemas, prompts, and source manifest.
2. Tag that immutable `code_commit`.
3. Reproduce from the exact tagged checkout.
4. Build the image and record its digest.
5. Run evaluation, load, resilience, restart, and soak checks against those artifacts.
6. Create a release attestation that references `code_commit`, tag, image digest, evaluation
   report hashes, source hash, and dirty flag.
7. Verify the attestation independently.

If the attestation is committed to Git, it uses a separate `release_record_commit`; it never
claims that its own containing commit is the behavior `code_commit`.

## 10. Python and CI baseline

- Python baseline: exactly the repository-supported 3.12 series.
- Generate and commit `uv.lock` from the approved dependency constraints.
- CI and local checks use `uv sync --frozen --all-groups` after lock creation.
- Ruff format, Ruff lint, mypy strict, pytest, source audit, and handoff verification are required.
- Coverage execution explicitly activates branch coverage and the configured 90% threshold.
- CI adds separate compliance checks for forbidden generative providers, lock/SBOM inspection,
  approved HCX host egress, exact API schema, and clean reproducibility.
- Windows and POSIX instructions use shell-appropriate or shell-neutral commands.

Existing lint failures are baseline debt, not accepted success. Preflight removes them without
changing frozen audit values or financial behavior.

## 11. Presentation decision evidence

Create a decision-evidence ledger with:

```text
decision_id
official requirement
observed data profile or failure
alternatives considered
selected rule and rationale
benchmark or ablation evidence
known limitation
source/config/report hashes
```

This ledger supplies the final presentation’s explanations for data grain, preprocessing,
operation-specific zero policy, deterministic execution, evidence verification, cross-currency
partitioning, and failure handling. Every quantitative slide claim links to a reproducible
report or source hash.

## 12. Implementation boundaries

Preflight is split into independently reviewable tasks:

1. Git-root checker, staging rules, and repository-owned quality loop.
2. Instruction/data authority split and official traceability update.
3. Typed evaluation/aggregate-evidence contracts and coverage-gap report.
4. Release provenance correction and presentation decision-evidence contract.
5. Python 3.12 lock, lint/type/test baseline, CI gates, and final independent audit.

Each task follows RED → GREEN → refactor, uses exact-path staging, receives fresh verification,
and records results in `docs/implementation/STATUS.md`. Phase 1 Task 1 begins only after all five
preflight tasks meet their gates.

## 13. Out of scope

- production ingestion and normalization
- SQL compiler or query executor implementation
- live evaluation API deployment
- personal or organizer GitHub remote creation
- speculative resolution of open official financial semantics
- UI implementation
- generation of sealed holdout answers by any LLM

## 14. Acceptance criteria

The preflight phase is accepted only when:

1. all five preflight tasks are independently committed and reviewed;
2. project-local Git and linked-worktree checks prove exact-root isolation;
3. no prompt or plan contains conflicting execution-scope rules;
4. raw data cannot become instruction authority;
5. open, locked, and sealed evaluation assets have enforceable separation;
6. release provenance has no self-reference;
7. the Python 3.12 frozen environment runs all required checks with observed results;
8. official source hashes, 145,393-row audit, and 207-column schema catalog remain unchanged;
9. the worktree is clean and `STATUS.md` names Phase 1 Task 1 as the exact next task.
