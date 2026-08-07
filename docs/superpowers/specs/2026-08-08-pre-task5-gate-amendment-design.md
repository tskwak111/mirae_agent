# Pre-Task-5 Quality-Gate Amendment Design

**Status:** DESIGN_APPROVED_BY_OWNER on 2026-08-08; SELF_REVIEWED; owner written-spec approval
pending

**Scope:** Gate applicability for Preflight Tasks 2–4 before Preflight Task 5 establishes `uv`,
`uv.lock`, and a globally clean quality baseline. No product, data, manifest-authority, runtime, or
Task 2 candidate-path behavior changes.

**Decision owner:** repository owner

## 1. Trigger and observed evidence

The approved Task 2 trust-plane design required every repository-wide `uv run` quality command to
pass before Task 2 completion. Plan self-review proved that condition cannot currently be executed:

- `uv` is absent from PATH, absent from `.venv\Scripts`, and not installed in the project venv;
- `uv.lock` does not exist, and `docs/implementation/STATUS.md` already assigns its creation to the
  first network-enabled bootstrap;
- `.venv\Scripts\python.exe -m ruff format --check .` reports eight pre-existing files that would
  be reformatted;
- `.venv\Scripts\python.exe -m ruff check .` reports 31 pre-existing findings;
- `.venv\Scripts\python.exe -m mypy src tests tools --no-incremental` reports 10 pre-existing
  errors;
- Preflight Task 5, not Task 2, owns lock creation, global quality-debt repair, frozen sync, CI
  enforcement, and the complete Preflight gate.

The eight observed formatting paths are:

```text
src/finproof/__init__.py
tests/__init__.py
tests/contract/__init__.py
tools/__init__.py
tools/audit_source_data.py
tools/create_input_manifest.py
tools/extract_schema_catalog.py
tools/xlsx_stream.py
```

Most are outside Task 2's approved thirteen-path allowlist. Keeping the original condition would
deadlock the ordered Preflight: Task 2 could not pass, while Task 5—the owner of the missing
environment and global debt—could never be reached.

These diagnostics are observed baseline evidence, not waivers and not PASS results.

## 2. Approaches considered

### A. Split provisional task gates from the Task 5 global gate — selected

Preflight Tasks 2–4 must pass full behavior/regression tests plus strict checks on every changed
Python file, while repository-wide Ruff/mypy debt remains explicitly pending. Preflight Task 5
installs/invokes `uv`, generates `uv.lock`, repairs the complete baseline, and runs the exact global
commands as hard gates.

This preserves scope ownership, makes Tasks 2–4 independently verifiable, and keeps the final
quality bar unchanged.

### B. Expand Task 2 to install `uv`, create the lock, and repair all global debt

Rejected because it would absorb Preflight Task 5, expand beyond the thirteen approved candidate
paths, mix instruction-authority work with environment/security refactoring, and invalidate the
review boundary.

### C. Reorder Preflight Task 5 before Task 2

Rejected because Task 5 is the final Preflight integration/audit task and consumes contracts from
Tasks 2–4. Running it first would produce a lock and audit against incomplete trust, evaluation, and
release contracts.

## 3. Normative override and unchanged contracts

This amendment supersedes only the Task 2 trust-plane design sentence that required the exact
repository-wide `uv run` commands before Task 2 completion. It also defines the same provisional
gate rule for Preflight Tasks 3 and 4 when their task-specific plans are frozen.

All other approved Task 2 requirements remain unchanged, including:

- manifest `1.1.0`;
- the exact PDF instruction path/SHA tuple;
- eight XLSX `official_data` entries;
- canonical path, frozen path/kind, generator-equality, and dependency-free verifier contracts;
- the exact thirteen candidate paths;
- strict RED/GREEN TDD, independent final reviews, Candidate 1–3, and one infrastructure retry;
- no `pyproject.toml`, `START_HERE.md`, workbook, `INITIAL_IMPORT`, remote, tag, push, or deployment
  change.

The complete Preflight and later production phases still require the exact global gates. This
amendment changes when they become applicable, not their final thresholds.

## 4. Gate taxonomy

### 4.1 Task-local hard gates for Preflight Tasks 2–4

A task passes only when all of these applicable checks are observed:

1. every task-owned Python file passes Ruff format and lint;
2. every task-owned typed Python interface passes the task's strict focused mypy command;
3. focused RED is recorded and focused GREEN passes;
4. the complete repository pytest suite passes under the existing Python 3.12 venv;
5. task-specific adversarial and regression suites pass;
6. handoff, source audit, schema catalog, Git-root, staging, diff, and clean-worktree checks pass;
7. both independent final verifiers report zero BLOCKER/HIGH.

A deterministic failure in any task-local hard gate blocks the candidate. A Windows temporary-path
or permission failure is infrastructure evidence and may use the one separately recorded retry
with a unique, coordinator-verified checkout-local pytest base directory.

### 4.2 Global diagnostics before Task 5

Before accepting Tasks 2–4, rerun repository-wide Ruff format, Ruff lint, and mypy as diagnostics.
Their nonzero exit is not called PASS and is not silently ignored. Compare normalized findings by
`(path, rule-or-error-code, message)` so harmless line-number movement does not masquerade as a new
finding. The candidate must satisfy both:

- no normalized finding is added relative to the recorded baseline;
- the set of failing paths does not expand relative to the recorded baseline.

Record command, exit code, normalized finding set, count, failing paths, and disposition in
`STATUS.md`. A pre-existing global-only finding remains explicit Task 5 debt even when its file is
modified by an earlier task; it is not a waiver. A new or worsened finding is a hard failure. A new
failing path is a blocker pending reproduction and ownership resolution.

### 4.3 Global hard gate at Preflight Task 5

Preflight Task 5 must:

1. load the approved Python 3.12 runtime;
2. install or invoke `uv` through that runtime;
3. generate and commit a reviewed `uv.lock`;
4. reconcile its allowed paths with a fresh global diagnostic inventory before edits;
5. repair all remaining formatting, lint, strict typing, and security-rule debt without changing
   frozen source behavior;
6. run the exact `uv run` commands from `AGENTS.md` and the additional runtime/compliance gates in
   the controlling Task 5 plan;
7. obtain two fresh-context final audits from a clean checkout.

The current Task 5 plan's “six reported files” language is stale against the observed eight
formatting paths. Task 5 must receive its own reviewed brief/path amendment before implementation;
this Task 2 amendment does not pre-authorize those future edits.

Any global gate failure at Task 5 blocks the complete Preflight. Earlier task-local approval cannot
waive it.

## 5. Exact Task 2 evidence

Task 2 Candidate 1 must run and record:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\contract\test_instruction_authority.py tests\contract\test_handoff_package.py -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
.venv\Scripts\python.exe -S -B tools\verify_handoff.py
.venv\Scripts\python.exe -B tools\verify_handoff.py
.venv\Scripts\python.exe -B tools\audit_source_data.py --check
.venv\Scripts\python.exe -B tools\extract_schema_catalog.py --check
.venv\Scripts\python.exe -m ruff format --check tools\create_input_manifest.py tools\verify_handoff.py tests\contract\test_instruction_authority.py
.venv\Scripts\python.exe -m ruff check tools\create_input_manifest.py tools\verify_handoff.py tests\contract\test_instruction_authority.py
.venv\Scripts\python.exe -m mypy tools\create_input_manifest.py tools\verify_handoff.py --follow-imports=skip --ignore-missing-imports
.venv\Scripts\python.exe -m compileall -q tools\create_input_manifest.py tools\verify_handoff.py tests\contract\test_instruction_authority.py
```

It also reruns these diagnostic probes and records their nonzero/zero result honestly:

```powershell
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests tools --no-incremental
```

Task 2 does not run `uv run`, create `uv.lock`, install dependencies, or modify a path merely to
silence an out-of-scope baseline diagnostic.

## 6. Durable routing and evidence

During Task 2 implementation:

- `AGENTS.md` distinguishes pre-Task-5 task-local gates from the unchanged post-bootstrap `uv`
  global hard gate;
- `STATUS.md` records this amendment, the exact baseline diagnostics, task-local results, and
  `GLOBAL QUALITY GATE PENDING — PREFLIGHT TASK 5`;
- `tools/verify_handoff.py` adds this amendment spec to `REQUIRED_FILES`;
- `tests/contract/test_instruction_authority.py` asserts the amendment spec is durably registered;
- the Task 2 plan expects one additional required file, so successful handoff reports
  `77 required files, 9 official inputs, 41,384,928 source bytes`.

No second precedence hierarchy is introduced. `AGENTS.md` remains the canonical repository
contract; the task-specific written specs define which checks are applicable before Task 5.

## 7. Claims and stop conditions

Before Task 5 passes, completion reports may say only that a named Preflight task passed its
approved task-local gates. They may not say:

- repository-wide Ruff/mypy passed;
- `uv` or lock reproducibility passed;
- the complete Preflight passed;
- the system is production-ready, competition-ready, AAA, or globally clean.

Stop and report instead of proceeding when:

- a new normalized global diagnostic is introduced;
- an out-of-scope failing path is newly introduced;
- full pytest, handoff, source audit, or schema catalog fails deterministically;
- the manifest/source facts drift;
- an independent verifier reports BLOCKER/HIGH;
- a later task attempts to treat this amendment as a waiver of the Task 5 global gate.

## 8. Acceptance

This amendment is correctly implemented when:

1. Task 2's detailed plan removes the impossible pre-Task-5 `uv run` completion requirement;
2. Task 2 retains strict changed-file quality, full pytest, source, schema, handoff, adversarial,
   and two-verifier hard gates;
3. global diagnostics are rerun and recorded without a false PASS claim;
4. the exact Task 2 candidate path allowlist remains unchanged;
5. the amendment is registered as a required handoff file and the expected count becomes 77;
6. `STATUS.md` explicitly leaves the global gate pending for Task 5;
7. Task 5 remains the non-waivable owner of `uv.lock`, global debt repair, and exact global gates;
8. Preflight Task 3 is selected only after Task 2's task-local acceptance and no Task 3 work begins
   in the Task 2 session.
