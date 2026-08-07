# Preflight Safety Remediation Implementation Plan

> **For agentic workers:** REQUIRED REPOSITORY CONTRACT: follow
> `docs/implementation/QUALITY_LOOP.md` for the one task selected by `STATUS.md`. Skills are
> optional aids. Fan-out is read-only or uses isolated, disjoint files with named writers; it may
> not expand scope, writable paths, ownership, or review gates. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** Remove the five demonstrated pre-implementation blockers and leave an exact-root,
reproducible Python 3.12 repository ready to begin Phase 1 Task 1.

**Architecture:** A small executable Git-root guard protects every Git workflow. Repository-owned
contracts then define agent orchestration, trust planes, independent evaluation, aggregate
evidence, release provenance, and presentation claims. The final task freezes the Python 3.12
toolchain and makes every gate executable in CI.

**Tech Stack:** Python 3.12, standard library, pytest, jsonschema, PyYAML, Ruff, mypy, uv, Git,
GitHub Actions, Markdown, JSON Schema 2020-12, YAML.

## Global Constraints

- Work only in the exact `codex/preflight-safety` linked worktree.
- Run `python tools/check_repo_root.py --expected-root .` before every Git status, stage, commit,
  tag, push, or release command after Task 1 creates the guard.
- Run the guard with `--require-clean-index` immediately before canonical staging; no other
  process or agent may write the index through commit.
- Never run `git add .`, `git add tests`, or another unresolved/broad staging command.
- Execute exactly one incomplete Preflight task per implementation session.
- The coordinator is the only writer for shared prompts, plans, and `STATUS.md`.
- Parallel agents are read-only unless they own disjoint files in isolated worktrees.
- No non-HyperCLOVA-X model may create production/evaluation answers or evaluation truth.
- Do not infer unresolved financial semantics during this preflight.
- Record RED output, GREEN output, verification commands, reviewer findings, and commit hash in
  `docs/implementation/STATUS.md`.
- A task stops after Candidate 3 if any BLOCKER or HIGH finding remains.

---

### Task 1: Exact Git-root guard and repository-owned quality loop

**Files:**

- Create: `.gitattributes`
- Create: `tools/check_repo_root.py`
- Create: `tests/contract/test_repo_root_guard.py`
- Create: `docs/implementation/QUALITY_LOOP.md`
- Modify: `tools/verify_handoff.py`
- Modify: `tests/contract/test_handoff_package.py`
- Modify: `AGENTS.md`
- Modify: `START_HERE.md`
- Modify: `README.md`
- Modify: `CODEX_MASTER_PROMPT.md`
- Modify: `CODEX_RESUME_PROMPT.md`
- Modify: `CODEX_REVIEW_PROMPT.md`
- Modify: `prompts/00_INITIAL_KICKOFF.md`
- Modify: `prompts/01_DATA_FOUNDATION.md`
- Modify: `prompts/02_QUERY_ENGINE.md`
- Modify: `prompts/03_HCX_AND_API.md`
- Modify: `prompts/04_EVALUATION_AND_RELEASE.md`
- Modify: `prompts/99_CODE_REVIEW.md`
- Modify: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`
- Modify: `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md`
- Modify: `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md`
- Modify: `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`
- Modify: `docs/superpowers/plans/2026-08-07-00-roadmap.md`
- Modify: `docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`
- Modify: `.gitignore`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Produces: `RepoRootError(RuntimeError)`
- Produces: `git_top_level(cwd: Path) -> Path`
- Produces: `ensure_exact_repo_root(expected_root: Path, cwd: Path | None = None) -> Path`
- Produces: `ensure_clean_index(root: Path) -> None`
- CLI: `python tools/check_repo_root.py --expected-root PATH [--require-clean-index]`
- Produces: `unsafe_git_stage_lines(text: str) -> tuple[tuple[int, str], ...]`
- Produces: CommonMark-aware Git-block, commit, and routing-surface verification
- Consumes: the approved preflight design and current Git checkout

- [ ] **Step 1: Write focused failing exact-root and index tests**

In addition to the nominal examples below, cover the real CLI, current-CWD binding, Unicode and
spaces, linked worktrees nested under `.worktrees`, cross-mismatches, repository/config-selection
environment variables, typed launch/timeout errors, unborn repositories, staged add/modify/delete/
rename/conflict states, and linked-worktree index isolation. All Git subprocess decoding is UTF-8
and fixtures neutralize ambient Git discovery/configuration.

Create `tests/contract/test_repo_root_guard.py` with real temporary Git repositories:

````python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.check_repo_root import RepoRootError, ensure_exact_repo_root


def run_git(path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, "init", "--initial-branch=main")


def test_exact_repository_root_is_accepted(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)

    assert ensure_exact_repo_root(repo, cwd=repo) == repo.resolve()


def test_ancestor_repository_is_rejected(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "project"
    init_repo(parent)
    child.mkdir()

    with pytest.raises(RepoRootError, match="does not match expected root"):
        ensure_exact_repo_root(child, cwd=child)


def test_missing_repository_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(RepoRootError, match="not inside a Git repository"):
        ensure_exact_repo_root(project, cwd=project)
````

- [ ] **Step 2: Run RED and verify the missing module is the only failure cause**

```powershell
python -m pytest -p no:cacheprovider tests/contract/test_repo_root_guard.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'tools.check_repo_root'`.

- [ ] **Step 3: Implement the minimal exact-root and clean-index guard**

The implementation must bind the default call to `Path.cwd()`, require invoking-directory and Git
top-level identity with resolved/same-file semantics, reject repository/index/config injection
variables before Git runs, use bounded subprocess timeouts, wrap launch/decoding/path failures in
`RepoRootError`, and preserve Unicode paths. `--require-clean-index` uses cached diff exit codes,
fails closed on every staged state, and prints escaped NUL-delimited diagnostic paths. The original
snippet below is the starting skeleton; these requirements and the contract tests are normative.

Create `tools/check_repo_root.py`:

```python
"""Fail closed unless Git is rooted at the explicitly expected workspace."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Final, Sequence


class RepoRootError(RuntimeError):
    """Raised when a Git command would operate outside the expected workspace."""


GIT_NOT_FOUND: Final = "not inside a Git repository"


def git_top_level(cwd: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RepoRootError(f"{GIT_NOT_FOUND}: {cwd.resolve()}")
    return Path(result.stdout.strip()).resolve()


def ensure_exact_repo_root(expected_root: Path, cwd: Path | None = None) -> Path:
    expected = expected_root.resolve(strict=True)
    actual = git_top_level((cwd or expected).resolve(strict=True))
    if actual != expected:
        raise RepoRootError(
            f"Git top level {actual} does not match expected root {expected}"
        )
    return actual


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = ensure_exact_repo_root(args.expected_root)
    except (OSError, RepoRootError) as exc:
        parser.exit(2, f"repository safety check failed: {exc}\n")
    print(f"Repository root PASS: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run GREEN and add a real linked-worktree case**

First rerun the three tests. Then add a linked-worktree test that configures a local test identity,
creates one commit, adds a worktree, and proves the worktree path—not the common Git directory—is
accepted:

```python
def test_linked_worktree_root_is_accepted(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    linked = tmp_path / "linked"
    init_repo(repo)
    run_git(repo, "config", "user.name", "FinProof Test")
    run_git(repo, "config", "user.email", "finproof-test@example.invalid")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    run_git(repo, "add", "--", "README.md")
    run_git(repo, "commit", "-m", "baseline")
    run_git(repo, "worktree", "add", str(linked), "-b", "codex/test-linked")

    assert ensure_exact_repo_root(linked, cwd=linked) == linked.resolve()
```

Run:

```powershell
python -m pytest -p no:cacheprovider tests/contract/test_repo_root_guard.py -q
```

Expected: four tests pass.

- [ ] **Step 5: Write RED tests for fenced Git workflow policy**

Add tests to `tests/contract/test_handoff_package.py`:

````python
from tools.verify_handoff import unsafe_git_stage_lines


def test_unsafe_git_stage_lines_rejects_broad_targets() -> None:
    text = """```powershell
git add .
git add tests
git add src/finproof/query tests/unit/query
```
"""
    assert unsafe_git_stage_lines(text) == ((2, "git add ."), (3, "git add tests"))


def test_unsafe_git_stage_lines_accepts_exact_owned_paths() -> None:
    text = """```powershell
git add -- tools/check_repo_root.py tests/contract/test_repo_root_guard.py
```
"""
    assert unsafe_git_stage_lines(text) == ()
````

Run:

```powershell
python -m pytest -p no:cacheprovider tests/contract/test_handoff_package.py::test_unsafe_git_stage_lines_rejects_broad_targets tests/contract/test_handoff_package.py::test_unsafe_git_stage_lines_accepts_exact_owned_paths -q
```

Expected: import fails because `unsafe_git_stage_lines` does not exist.

- [ ] **Step 6: Implement Git-workflow validation and wire it into handoff checks**

Parse CommonMark backtick/tilde fences of length three or greater, including attributes, longer
closing fences, unclosed fences, and inert nested examples. Scan known shell labels and fail closed
on Git inside unknown/unlabeled fences; Python/text fixtures remain inert. Accept only literal
direct `git add -- <ASCII repo-relative forward-slash path>...`; reject every other staging form,
context override, pathspec, variable, quote, wildcard, control operator, continuation, absolute/
parent path, and case-folded bare broad directory. Every Git block starts with the exact guard;
mutating blocks require clean-index mode, commits require an observed staged name/status diff, and
auto-staging commit options are forbidden. Invoke the checks for every routing surface and plan.

Add `tools/check_repo_root.py`, `docs/implementation/QUALITY_LOOP.md`, the preflight design, and
this plan to `REQUIRED_FILES` and `HANDOFF_PACKAGE_MANIFEST.md`.

Run the focused tests again and confirm both pass.

- [ ] **Step 7: Write the repository-owned quality loop and simplify prompt routing**

Create `docs/implementation/QUALITY_LOOP.md` from Sections 5.1–5.4 of the approved design. It must
define:

- one `STATUS.md` task per session;
- task brief hash and exact allowed paths;
- read-only or isolated non-overlapping fan-out;
- oracle author, implementer, spec verifier, and execution verifier separation;
- anonymized spec review and fresh-checkout execution review;
- Candidate 1–3 retry limit and one infrastructure retry;
- zero BLOCKER/HIGH pass gate and named expiring MEDIUM waivers;
- prohibition on non-HCX-generated runtime answers and evaluation truth;
- coordinator-only `STATUS.md` ownership.

Replace duplicated orchestration prose in the three top-level Codex prompts and six files under
`prompts/` with a concise link to `QUALITY_LOOP.md`, the current task, approval boundaries, and
the exact-root command. Keep product/domain invariants in `AGENTS.md`; do not duplicate them.

Replace every broad staging command in the roadmap, all phase plans, and this Preflight plan with
literal files only. Each mutating Git block begins with clean-index mode,
uses canonical staging, and reviews the staged name/status list before commit.

```powershell
python tools/check_repo_root.py --expected-root .
```

Replace the unsafe `START_HERE.md` initialization block with explicit verification and an
allowlisted initial import. It must state that a parent Git repository is a stop condition.

- [ ] **Step 8: Add Preflight to STATUS and run Task 1 verification**

Insert a Preflight section before Phase 1 in `docs/implementation/STATUS.md` with five tasks from
the approved design. Mark Task 1 complete only after the commands below pass and record RED/GREEN
results and reviewer evidence.

Run:

```powershell
python tools/check_repo_root.py --expected-root .
python -m pytest -p no:cacheprovider tests/contract/test_repo_root_guard.py tests/contract/test_handoff_package.py -q
python -B tools/verify_handoff.py
python -B tools/audit_source_data.py --check
python -B tools/extract_schema_catalog.py --check
```

Expected source invariants: 145,393 rows, snapshot `2026-07-11`, and 207 columns.

- [ ] **Step 9: Request two independent reviews and commit exact Task 1 paths**

Verifier A receives the approved spec, Task 1 plan text, and an anonymized diff. Verifier B
receives only the expected commands, acceptance criteria, and commit range and reruns the tests
itself. Apply technically valid findings one at a time and rerun the focused suite after each.

Stage only the paths listed in Task 1:

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- .gitattributes .gitignore tools/check_repo_root.py tools/verify_handoff.py tests/contract/test_repo_root_guard.py tests/contract/test_handoff_package.py docs/implementation/QUALITY_LOOP.md docs/implementation/STATUS.md AGENTS.md START_HERE.md README.md CODEX_MASTER_PROMPT.md CODEX_RESUME_PROMPT.md CODEX_REVIEW_PROMPT.md prompts/00_INITIAL_KICKOFF.md prompts/01_DATA_FOUNDATION.md prompts/02_QUERY_ENGINE.md prompts/03_HCX_AND_API.md prompts/04_EVALUATION_AND_RELEASE.md prompts/99_CODE_REVIEW.md docs/superpowers/plans/2026-08-07-00-roadmap.md docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md HANDOFF_PACKAGE_MANIFEST.md
git diff --cached --name-status --
git commit -m "chore: enforce exact-root quality workflow"
```

---

### Task 2: Separate instruction authority from official data

**Files:**

- Create: `schemas/input_manifest.schema.json`
- Create: `tests/contract/test_instruction_authority.py`
- Modify: `source_material/input_manifest.json`
- Modify: `source_material/README.md`
- Modify: `AGENTS.md`
- Modify: `CODEX_MASTER_PROMPT.md`
- Modify: `docs/08_SECURITY_OPERATIONS_AND_RELEASE.md`
- Modify: `docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md`
- Modify: `docs/10_DECISION_LOG.md`
- Modify: `tools/verify_handoff.py`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Produces: input-manifest `trust_plane` enum of `official_instruction` or `official_data`
- Produces: one allowlisted instruction document and eight data-only workbook entries
- Consumes: unchanged official file hashes and snapshot baseline

- [ ] **Step 1: Write RED manifest trust-plane tests**

Test the real manifest with `Draft202012Validator` and assert:

```python
assert by_path["competition_task_financial_product_agent.pdf"]["trust_plane"] == "official_instruction"
assert {
    entry["trust_plane"] for entry in manifest["files"] if entry["path"].endswith(".xlsx")
} == {"official_data"}
```

Also mutate a copy so an XLSX claims `official_instruction` and assert the repository validator
returns a specific error.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest -p no:cacheprovider tests/contract/test_instruction_authority.py -q
```

Expected: failure because `trust_plane` and its schema do not exist.

- [ ] **Step 3: Implement the versioned trust-plane schema and manifest values**

Define `schemas/input_manifest.schema.json` with `additionalProperties: false`, the frozen
snapshot, SHA-256 pattern, positive size, kind-specific table/sheet metadata, and `trust_plane`.
Assign only the competition task PDF to `official_instruction`; assign all workbooks to
`official_data`. Do not change any file hash or size.

Update `verify_handoff.py` to validate the manifest schema and reject instruction authority on
workbook entries.

- [ ] **Step 4: Revise authority prose and record the official state**

Make `AGENTS.md` the single canonical precedence list. Other prompts link to it. State explicitly
that official data is authoritative for facts and lineage but never executable instruction.
Record in `docs/10_DECISION_LOG.md` that the owner supplied no additional organizer notice as of
2026-08-07. Add the organizer private-repository requirement and currently published evaluation
dates to traceability with source/page attribution.

- [ ] **Step 5: Run verification, review, and commit**

```powershell
python tools/check_repo_root.py --expected-root .
python -m pytest -p no:cacheprovider tests/contract/test_instruction_authority.py tests/contract/test_handoff_package.py -q
python -B tools/verify_handoff.py
python -B tools/audit_source_data.py --check
```

Stage exactly the Task 2 files and commit with:

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- schemas/input_manifest.schema.json tests/contract/test_instruction_authority.py source_material/input_manifest.json source_material/README.md AGENTS.md CODEX_MASTER_PROMPT.md docs/08_SECURITY_OPERATIONS_AND_RELEASE.md docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md docs/10_DECISION_LOG.md tools/verify_handoff.py HANDOFF_PACKAGE_MANIFEST.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "security: separate instruction and data trust planes"
```

---

### Task 3: Enforce independent evaluation, typed goldens, and aggregate evidence

**Files:**

- Create: `schemas/aggregate_evidence.schema.json`
- Create: `schemas/golden_expected_result.schema.json`
- Create: `schemas/golden_expected_answer.schema.json`
- Create: `config/question_coverage.yaml`
- Create: `tools/build_coverage_report.py`
- Create: `tests/contract/test_evaluation_contracts.py`
- Create: `tests/contract/test_question_coverage.py`
- Create: `tests/evaluation/README.md`
- Modify: `schemas/golden_case.schema.json`
- Modify: `tests/golden/README.md`
- Modify: `tests/contract/test_handoff_package.py`
- Modify: `docs/07_TESTING_AND_EVALUATION.md`
- Modify: `docs/09_RISK_REGISTER.md`
- Modify: `docs/10_DECISION_LOG.md`
- Modify: `tools/verify_handoff.py`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Produces: typed golden cases resolving canonical QueryPlan references
- Produces: `AggregateEvidence` for counts, ranks, exclusions, and calculations
- Produces: `build_coverage_report(catalog: dict, coverage: dict) -> dict`
- Produces: explicit open, locked, and sealed evaluation lanes

- [ ] **Step 1: Write RED typed-contract tests**

Build a JSON Schema registry containing the canonical QueryPlan, expected-result,
expected-answer, and golden-case schemas. Assert the current seeds validate. Then mutate one case
to remove `filters`, use a numeric value where an exact decimal string is required, and omit an
evidence requirement; assert each mutation fails validation.

Write a valid aggregate-evidence fixture containing dataset hash, plan hash, segment/partition,
policy IDs, candidate counts, ordered-result hash, calculation inputs, and exclusion counts.
Mutate it to remove the plan hash and assert validation fails.

- [ ] **Step 2: Run RED and implement minimal schemas**

```powershell
python -m pytest -p no:cacheprovider tests/contract/test_evaluation_contracts.py -q
```

Expected RED: referenced schemas and required typed fields are missing. Implement only the fields
specified by the approved design, update the seed cases to the typed shape without changing their
intended semantics, then rerun to GREEN.

- [ ] **Step 3: Write RED 207-column coverage tests**

Assert that `build_coverage_report` returns exactly the 207 `(table_id, column_name)` pairs in
`source_material/schema_catalog.json`, each with one status from:

```text
supported
intentionally_unsupported
blocked_official_semantics
source_unavailable
```

Assert every planner alias maps to a coverage concept and specifically that `risk_grade` cannot
be reported as supported unless its source mapping, ordering, null semantics, and evidence rule
are all present.

- [ ] **Step 4: Run RED, implement coverage generation, and classify every column**

```powershell
python -m pytest -p no:cacheprovider tests/contract/test_question_coverage.py -q
```

Expected RED: coverage config and generator do not exist. Implement a deterministic generator and
classify all 207 columns. Leave unresolved concepts blocked; do not invent mappings. Record
manager, base index, strategy, replication, coupon, duration, evaluation price, and risk grade as
named question concepts with explicit status and reason.

- [ ] **Step 5: Freeze evaluation-lane governance**

Document open regression, locked validation, and sealed human-curated holdout access. Define
consumption, invalidation, prompt/model/config/code hash freeze, denominator reporting, and the
rule that no LLM creates sealed truth. Add evaluation leakage, oracle coupling, and reviewer bias
to the risk register.

- [ ] **Step 6: Verify, review, and commit**

Run focused contracts, all contract tests, handoff, source audit, and schema-catalog checks. Stage
only Task 3 paths and commit:

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- schemas/aggregate_evidence.schema.json schemas/golden_expected_result.schema.json schemas/golden_expected_answer.schema.json config/question_coverage.yaml tools/build_coverage_report.py tests/contract/test_evaluation_contracts.py tests/contract/test_question_coverage.py tests/evaluation/README.md schemas/golden_case.schema.json tests/golden/README.md tests/contract/test_handoff_package.py docs/07_TESTING_AND_EVALUATION.md docs/09_RISK_REGISTER.md docs/10_DECISION_LOG.md tools/verify_handoff.py HANDOFF_PACKAGE_MANIFEST.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "test: enforce independent evidence-backed evaluation"
```

---

### Task 4: Correct release provenance and create presentation claim evidence

**Files:**

- Create: `schemas/release_attestation.schema.json`
- Create: `schemas/decision_evidence.schema.json`
- Create: `tools/verify_release_attestation.py`
- Create: `docs/release/RELEASE_PROVENANCE.md`
- Create: `docs/presentation/DECISION_EVIDENCE_LEDGER.yaml`
- Create: `tests/contract/test_release_provenance_contract.py`
- Create: `tests/contract/test_decision_evidence_contract.py`
- Modify: `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`
- Modify: `docs/08_SECURITY_OPERATIONS_AND_RELEASE.md`
- Modify: `docs/09_RISK_REGISTER.md`
- Modify: `docs/10_DECISION_LOG.md`
- Modify: `docs/11_DEFINITION_OF_DONE.md`
- Modify: `HANDOFF_PACKAGE_MANIFEST.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Produces: immutable `code_commit` plus optional distinct `release_record_commit`
- Produces: release-attestation hashes for image, evaluation reports, source, config, prompts,
  and schemas
- Produces: `verify_release_attestation(record: dict[str, object]) -> tuple[str, ...]`
- Produces: presentation claim ledger with reproducible evidence links

- [ ] **Step 1: Write RED release-attestation tests**

Validate a fixture with distinct `code_commit`, tag, image digest, source/config/prompt/schema
hashes, evaluation report hashes, dirty flag `false`, and optional `release_record_commit`. Mutate
it so `code_commit == release_record_commit` while the record claims to contain itself and assert
validation or semantic verification rejects it.

- [ ] **Step 2: Run RED and implement the release contract**

```powershell
python -m pytest -p no:cacheprovider tests/contract/test_release_provenance_contract.py -q
```

Implement the schema, a semantic verifier that rejects an attestation claiming its own containing
commit as `code_commit`, and the normative release order: freeze code → tag code → reproduce
tagged checkout → build image → evaluate/soak → create external attestation → independently
verify.

- [ ] **Step 3: Write RED presentation-evidence tests**

Validate ledger entries containing decision ID, official requirement, observed failure/data
profile, alternatives, selected rule, benchmark/ablation evidence, limitation, and source/config/
report hashes. Assert an unsupported quantitative claim without a report hash is rejected.

- [ ] **Step 4: Run RED and create the initial evidence ledger**

Populate entries for public-fund grain, operation-specific zero handling, deterministic execution,
cross-currency partitioning, exact identifier linking, and claim verification using already
recorded repository evidence. Do not add a performance or ROI claim without a measured report.

- [ ] **Step 5: Remove the Phase 4 self-reference and verify order**

Rewrite Phase 4 Task 5 so clean-room reproduction checks the exact tagged `code_commit` and the
attestation is created afterward. If stored in Git, label its containing commit only as
`release_record_commit`. Add manifest self-reference and wrong-root release to the risk register.

- [ ] **Step 6: Verify, review, and commit**

Run both focused contract suites and handoff verification, stage exact Task 4 paths, and commit:

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- schemas/release_attestation.schema.json schemas/decision_evidence.schema.json tools/verify_release_attestation.py docs/release/RELEASE_PROVENANCE.md docs/presentation/DECISION_EVIDENCE_LEDGER.yaml tests/contract/test_release_provenance_contract.py tests/contract/test_decision_evidence_contract.py docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md docs/08_SECURITY_OPERATIONS_AND_RELEASE.md docs/09_RISK_REGISTER.md docs/10_DECISION_LOG.md docs/11_DEFINITION_OF_DONE.md HANDOFF_PACKAGE_MANIFEST.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "release: separate code freeze from attestation"
```

---

### Task 5: Freeze Python 3.12, repair quality gates, and audit the preflight

**Files:**

- Create: `uv.lock`
- Create: `tools/check_runtime_policy.py`
- Create: `tools/probe_hcx_capability.py`
- Create: `tests/contract/test_runtime_policy.py`
- Create: `tests/contract/test_hcx_capability_probe.py`
- Create: `docs/review/HCX_CAPABILITY_REPORT.md`
- Create: `docs/review/PREFLIGHT_FINAL_AUDIT.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.pre-commit-config.yaml`
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `CODEX_MASTER_PROMPT.md`
- Modify: `tools/audit_source_data.py`
- Modify: `tools/create_input_manifest.py`
- Modify: `tools/extract_schema_catalog.py`
- Modify: `tools/verify_handoff.py`
- Modify: `tools/xlsx_stream.py`
- Modify: `tests/contract/test_handoff_package.py`
- Modify: `docs/implementation/PHASE_GATES.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Produces: frozen Python 3.12 dependency graph
- Produces: runtime/provider/egress compliance checker
- Produces: a redacted HCX capability observation with model, interface, schema mode, quota
  headers, timeout result, and latency
- Produces: separate CI jobs for quality, contracts, compliance, and reproducibility
- Produces: independent final Preflight audit and exact Phase 1 Task 1 handoff

- [ ] **Step 1: Establish the supported Python 3.12 environment**

Load the configured workspace dependency runtime and verify `Python 3.12.x`. Install or invoke
`uv` through the approved runtime. Generate `uv.lock`, then run:

```powershell
uv sync --frozen --all-groups
uv run python --version
```

Stop if the interpreter is outside Python 3.12 or dependency resolution changes approved version
constraints without a reviewed reason.

- [ ] **Step 2: Write RED runtime-policy tests**

Test a fixture dependency graph and source tree. Reject a forbidden generative provider,
non-approved outbound model host, missing lock, unlocked CI sync, or extra evaluation API field.
Accept the approved HCX host allowlist and exact five-field API schema.

- [ ] **Step 3: Run RED and implement compliance checks**

```powershell
uv run pytest -p no:cacheprovider tests/contract/test_runtime_policy.py -q
```

Implement `tools/check_runtime_policy.py` using parsed TOML/JSON/YAML and lock data rather than
substring-only dependency detection. Report file and policy category without printing secrets.

- [ ] **Step 4: Write RED HCX capability-probe tests and implement the bounded probe**

Use recorded HTTP fixtures to assert that the probe:

- targets only the approved CLOVA Studio host;
- requests the configured HCX model without silently substituting another model;
- records Structured Outputs success or incompatibility;
- records quota headers, timeout category, and latency;
- redacts authorization and API-key values from output and exceptions;
- refuses `--live` when the required environment variable is absent.

Run RED:

```powershell
uv run pytest -p no:cacheprovider tests/contract/test_hcx_capability_probe.py -q
```

Implement `tools/probe_hcx_capability.py` with recorded mode as the default and an explicit
`--live` flag. The live request is bounded to one representative structured-output request and
one malformed-schema rejection check. Write only redacted observations to
`docs/review/HCX_CAPABILITY_REPORT.md`. If account access is unavailable, record
`BLOCKED_EXTERNAL` and do not mark Preflight complete.

- [ ] **Step 5: Repair existing format, lint, and strict typing debt**

Run Ruff format on the six reported files, then address each Ruff finding without changing source
audit behavior. Replace unsafe workbook XML parsing with a hardened parser or an explicit,
documented checksum-plus-resource-limit boundary that satisfies the selected security rule.
Resolve strict mypy errors; do not add blanket ignores.

- [ ] **Step 6: Split and freeze CI gates**

Use `uv sync --frozen --all-groups`. Add required jobs for:

- formatting/lint/type/coverage;
- source and schema contracts;
- provider/egress/SBOM compliance;
- clean artifact reproduction.

Activate `pytest --cov=finproof --cov-branch --cov-report=term-missing` so the configured 90%
threshold is actually enforced. Pin release-critical actions to reviewed commit SHAs before the
submission freeze.

- [ ] **Step 7: Run the complete Preflight gate**

```powershell
python tools/check_repo_root.py --expected-root .
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -p no:cacheprovider -q
uv run python tools/audit_source_data.py --check
uv run python tools/extract_schema_catalog.py --check
uv run python tools/verify_handoff.py
uv run python tools/check_runtime_policy.py
uv run python tools/probe_hcx_capability.py
```

Record exact outputs. A failure is a blocker, not a reason to weaken a gate.

- [ ] **Step 8: Run two fresh-context final audits**

Verifier A reviews the complete Preflight commit range against the approved design. Verifier B
starts from a fresh checkout, installs from `uv.lock`, reruns every command above, and compares
source hashes, row counts, column counts, and Git-root evidence. Both reports go in
`docs/review/PREFLIGHT_FINAL_AUDIT.md`; unresolved HIGH findings block acceptance.

- [ ] **Step 9: Update STATUS and commit the verified checkpoint**

Mark all five Preflight tasks complete only when the full gate and both reviews satisfy the
approved pass criteria. Name Phase 1 Task 1 as the exact next task. Stage only Task 5 paths and
the final review report, then commit:

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- uv.lock tools/check_runtime_policy.py tools/probe_hcx_capability.py tests/contract/test_runtime_policy.py tests/contract/test_hcx_capability_probe.py docs/review/HCX_CAPABILITY_REPORT.md docs/review/PREFLIGHT_FINAL_AUDIT.md .github/workflows/ci.yml .pre-commit-config.yaml pyproject.toml Makefile CODEX_MASTER_PROMPT.md tools/audit_source_data.py tools/create_input_manifest.py tools/extract_schema_catalog.py tools/verify_handoff.py tools/xlsx_stream.py tests/contract/test_handoff_package.py docs/implementation/PHASE_GATES.md docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "chore: freeze verified preflight baseline"
```
