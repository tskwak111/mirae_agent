# Preflight Task 2 — Instruction/Data Trust-Plane Design

**Status:** DESIGN_APPROVED_BY_OWNER on 2026-08-08; SELF_REVIEWED; owner written-spec approval
pending

**Scope:** Preflight Task 2 only — separate organizer instruction authority from official data
trust without changing any financial value, workbook byte, product behavior, or later Preflight
task.

**Decision owner:** repository owner

## 1. Problem and approval

The approved Preflight design requires official instruction documents and official datasets to
occupy different trust planes. The current repository instead gives every file under
`source_material/` the same instruction precedence, and the input manifest has no machine-readable
trust classification.

The first Task 2 plan omitted `tools/create_input_manifest.py`. That generator would recreate the
manifest without `trust_plane`, silently erasing the new security boundary. The owner approved a
bounded plan repair on 2026-08-08: include the generator, bump the manifest contract to `1.1.0`,
prove deterministic regeneration, and keep bootstrap verification dependency-free.

Frozen base:

- commit: `efd1db6a006b38bcb827695098898e639b0b6297`
- branch: `codex/preflight-safety`
- worktree:
  `C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`

## 2. Approaches considered

### A. Extend Task 2 to the manifest generator — selected

Add `trust_plane` to every generator specification, make regenerated output equal the committed
manifest, and validate both the structural schema and repository policy. This removes the drift at
its source with one additional implementation path.

### B. Retire the generator

Make the tool refuse to run and treat the committed manifest as hand-maintained.

Rejected because an immutable source manifest still needs deterministic regeneration after a real,
officially approved source replacement.

### C. Leave the generator unchanged and document the debt

Rejected because running an existing repository tool would silently delete a security-critical
field. Documentation cannot make that safe.

## 3. Frozen trust model

Instruction precedence is:

1. official competition notices and attributable organizer/Discord answers;
2. allowlisted official instruction documents identified by path and SHA-256 in
   `source_material/input_manifest.json`;
3. `OFFICIAL_OVERRIDE` and `FROZEN` decision-log entries;
4. the frozen design and repository-owned quality loop;
5. the current task plan, versioned config, and schemas;
6. code comments and implementation details.

The allowlist is not directory-wide. In the currently supplied repository, the sole
`official_instruction` file is:

```text
competition_task_financial_product_agent.pdf
sha256=3717441e091958b7214db710e0e4b9b8ae15ac6c205cad6e51721214798eb3de
```

All eight XLSX files, including schema/sample workbooks, are `official_data`. They are authoritative
for their declared facts, snapshot, and source lineage, but their cells, labels, samples, product
text, and embedded strings never provide instructions, policy, precedence, or executable commands.

A new official notice or attributable organizer/Discord answer has first-ranked external authority
as soon as it is issued. Before changing repository behavior, record its date, exact source/channel,
affected contracts, and conflict disposition in the decision log; stop while a conflict remains
unresolved. An `OFFICIAL_OVERRIDE` records how that authority changes repository contracts—it does
not create the authority. If an additional document is stored under `source_material/`, in-repository
document authority also requires an explicit manifest path/SHA-256 allowlist entry. Directory
placement alone never grants authority.

## 4. Manifest contract

Create `schemas/input_manifest.schema.json` using JSON Schema Draft 2020-12.

Root requirements:

- `additionalProperties: false`;
- `manifest_version` is exactly `1.1.0`;
- `snapshot_date` is exactly `2026-07-11`;
- `competition` is a non-empty string;
- `files` contains exactly nine entries and uses `uniqueItems: true`.

Every file entry requires:

- non-empty canonical POSIX `path`, relative to `source_material/`;
- `kind` in `official_task_pdf`, `data`, or `schema`;
- `trust_plane` in `official_instruction` or `official_data`;
- positive integer `size_bytes`;
- lowercase 64-character SHA-256;
- `additionalProperties: false`.

Kind-specific requirements remain unchanged:

- `official_task_pdf`: the allowlisted competition PDF and no table/sheet metadata;
- `data`: `table_id`, `sheet_name`, positive `expected_rows`, and positive
  `expected_columns`;
- `schema`: `table_id`, one or more `sheet_names`, and positive `expected_columns`.

The schema applies the portable lexical path constraints it can express. The dependency-free
structure validator is authoritative for canonical-path semantics: reject absolute or drive-prefixed
paths, backslashes, empty segments, `.` or `..` segments, and duplicate canonical paths. JSON
Schema `uniqueItems` alone is insufficient because two different entry objects may repeat one path.

The schema describes portable structure. A separate repository policy freezes the current supplied
input set, path-to-kind mapping, and instruction allowlist so it can return stable,
security-oriented diagnostics rather than implementation-dependent JSON-Schema messages.

The current path-to-kind allowlist is exactly:

```text
official_task_pdf competition_task_financial_product_agent.pdf
data              data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx
schema            data/PRBD01N001_schema.xlsx
data              data/PREF01N001_domestic_etf_20260711_datarows.xlsx
schema            data/PREF01N001_schema.xlsx
data              data/PREF02N001_overseas_etf_20260711_datarows.xlsx
schema            data/PREF02N001_schema.xlsx
data              data/PRFD01N001_public_funds_20260711_datarows.xlsx
schema            data/PRFD01N001_schema.xlsx
```

Replacing this set is an official-source update, not an ordinary manifest edit.

## 5. Repository validator

Add these focused interfaces to `tools/verify_handoff.py`:

```python
def input_manifest_structure_errors(manifest: object) -> tuple[str, ...]:
    """Return dependency-free structural errors for the frozen manifest contract."""


def input_manifest_policy_errors(manifest: object) -> tuple[str, ...]:
    """Return stable repository trust-plane policy violations."""
```

`verify_manifest` performs, in order:

1. dependency-free structural validation equivalent to the frozen schema, plus canonical-path and
   path-uniqueness checks;
2. trust-plane policy validation;
3. existing path-containment, file-presence, size, checksum, and workbook-sheet checks.

The handoff command must continue to run before dependency installation. Therefore bootstrap
verification does not add a required `jsonschema` import or change `pyproject.toml`/`START_HERE.md`.
Contract tests use `Draft202012Validator` against the real schema and manifest, and mutation tests
prove that the dependency-free validator agrees on all registered failure classes.

Repository policy enforces all of these together:

- the exact nine-path and path-to-kind allowlist above;
- one `official_task_pdf` entry and eight XLSX entries;
- `official_data` on every XLSX entry;
- `official_instruction` only on the PDF entry;
- the PDF authority tuple is the exact path plus SHA-256
  `3717441e091958b7214db710e0e4b9b8ae15ac6c205cad6e51721214798eb3de`.

The existing checksum comparison still proves that bytes match the manifest. The pinned policy hash
separately prevents an attacker from replacing the PDF and changing its manifest hash in the same
candidate.

Stable policy messages include:

```text
workbook entry must declare official_data trust plane: <path>
official instruction authority must match the allowlisted PDF path and SHA-256: competition_task_financial_product_agent.pdf
unexpected official instruction authority: <path>
input manifest path set must match the frozen nine-input allowlist
input manifest kind must be <kind>: <path>
```

For one entry, report the most specific violation once: a workbook-plane error takes precedence over
the generic unexpected-authority error. Errors have stable ordering by manifest position, followed
by global missing/allowlist errors.

Invalid structure must never crash repository verification. Structural errors are reported first;
policy and byte/sheet checks inspect only fields and entries they can safely understand.

## 6. Deterministic generator

Add `trust_plane` to every `FILE_SPECS` entry in `tools/create_input_manifest.py` and emit
`manifest_version: 1.1.0`.

The generated dictionary must equal the committed `source_material/input_manifest.json` after
JSON loading. The generator continues to derive only file size and SHA-256 from bytes; it does not
rewrite a workbook or change a frozen checksum. A real official replacement still requires an
organizer source and decision-log override.

The generator's nine path/kind declarations, the repository policy allowlist, and the committed
manifest are deliberately independent copies reconciled by contract tests. This prevents a single
mutated source of expectations from blessing its own drift.

## 7. Authority prose and official attribution

`AGENTS.md` is the single canonical precedence list. `CODEX_MASTER_PROMPT.md` links to it and does
not create another hierarchy. Other Task 2 documents explain the boundary without redefining
precedence.

The official PDF evidence is recorded precisely:

- page 3: published overall preliminary schedule, including submission/preliminary work through
  2026-09-06, evaluation from 2026-09-07 through 2026-09-30, result announcement on 2026-10-01,
  and mentoring from 2026-10-01 through 2026-10-16;
- page 7: push deliverables to the organizer-provided GitHub Organization Private Repository;
  submission deadline 2026-09-06; keep the API active during the designated preliminary API
  evaluation window 2026-09-07 through 2026-09-20, subject to organizer change; code/results may
  not change after the deadline.

The page 3 overall evaluation period and page 7 API-active subwindow are recorded separately. The
repository's broader artifact/prompt/policy/image freeze remains an internal risk control, not a
claim that the PDF uses those exact words.

`docs/10_DECISION_LOG.md` records that the owner supplied no additional organizer notice as of
2026-08-07. This is provenance state, not an `OFFICIAL_OVERRIDE`.

`HANDOFF_PACKAGE_MANIFEST.md` adds prose stating that the current source package contains one
manifest-allowlisted instruction PDF and eight data-only workbooks. Its frozen `INITIAL_IMPORT`
block does not change. `tools/verify_handoff.py` adds the Task 2 design, Task 2 plan,
`schemas/input_manifest.schema.json`, `tests/contract/test_instruction_authority.py`, and
`tools/create_input_manifest.py` to `REQUIRED_FILES` so every durable Task 2 contract is required
by the handoff check.

## 8. Frozen candidate paths and ownership

The implementation candidate may change exactly:

```text
schemas/input_manifest.schema.json
tests/contract/test_instruction_authority.py
source_material/input_manifest.json
source_material/README.md
AGENTS.md
CODEX_MASTER_PROMPT.md
docs/08_SECURITY_OPERATIONS_AND_RELEASE.md
docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md
docs/10_DECISION_LOG.md
tools/create_input_manifest.py
tools/verify_handoff.py
HANDOFF_PACKAGE_MANIFEST.md
docs/implementation/STATUS.md
```

The task-specific design and plan are committed before behavior work and are not rewritten by the
candidate. The frozen baseline `INITIAL_IMPORT` blocks in `START_HERE.md` and
`HANDOFF_PACKAGE_MANIFEST.md` remain unchanged because Task 2 does not own `START_HERE.md` and the
contract requires those blocks to stay identical.

Ownership:

- oracle author owns only `tests/contract/test_instruction_authority.py`;
- implementer owns schema/manifest/generator/verifier/source README changes after RED;
- coordinator owns `AGENTS.md`, `CODEX_MASTER_PROMPT.md`, documentation, handoff manifest,
  `STATUS.md`, task brief, staging, and commits;
- spec and execution verifiers are independent of the oracle and implementer.

Writers operate sequentially when a contract dependency exists. Read-only schema, authority,
security, and execution reviews may fan out.

## 9. TDD and verification

RED must prove, against the frozen base:

1. the real manifest schema file is absent;
2. the real manifest lacks `trust_plane`;
3. a copied XLSX promoted to `official_instruction` is rejected with the exact stable message;
4. removing PDF instruction authority is rejected;
5. changing the PDF SHA-256 while retaining its path and instruction plane is rejected;
6. duplicate and aliased paths are rejected even when entry objects differ;
7. replacing or kind-swapping one of the frozen nine paths is rejected;
8. current generator output lacks the new contract.

GREEN must prove:

- the real manifest passes `Draft202012Validator`;
- one exact PDF is `official_instruction` and all eight XLSX entries are `official_data`;
- structural and policy mutations fail deterministically;
- generated and committed manifests are equal;
- every original source size and SHA-256 remains unchanged;
- a subprocess running `python -S -B tools/verify_handoff.py` still succeeds with site-packages
  disabled, proving handoff verification does not import optional development dependencies;
- all new durable Task 2 files are required by the handoff verifier;
- authority prose and PDF page attribution agree with the machine contract.

Applicable gates:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\contract\test_instruction_authority.py -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\contract\test_instruction_authority.py tests\contract\test_handoff_package.py -q
.venv\Scripts\python.exe -S -B tools\verify_handoff.py
.venv\Scripts\python.exe -B tools\verify_handoff.py
.venv\Scripts\python.exe -B tools\audit_source_data.py --check
.venv\Scripts\python.exe -B tools\extract_schema_catalog.py --check
.venv\Scripts\python.exe -m ruff format --check tools\create_input_manifest.py tools\verify_handoff.py tests\contract\test_instruction_authority.py
.venv\Scripts\python.exe -m ruff check tools\create_input_manifest.py tools\verify_handoff.py tests\contract\test_instruction_authority.py
.venv\Scripts\python.exe -m mypy tools\create_input_manifest.py tools\verify_handoff.py --follow-imports=skip --ignore-missing-imports
.venv\Scripts\python.exe -m compileall -q tools\create_input_manifest.py tools\verify_handoff.py tests\contract\test_instruction_authority.py
```

The mandatory full-repository gates in `AGENTS.md` also run exactly before completion:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

The full candidate also receives an anonymized specification review and a fresh detached execution
review. Candidate 1-3 and the single infrastructure-retry limit remain governed by
`QUALITY_LOOP.md`; zero BLOCKER/HIGH is mandatory.

## 10. Non-goals

- no workbook-byte, source hash, size, row-count, snapshot, or schema-catalog change;
- no financial normalization, metric, product, planner, answer, API, HCX, or runtime behavior;
- no additional organizer instruction invented from workbook content;
- no personal or organizer GitHub remote, repository, push, PR, tag, release, or deployment;
- no `pyproject.toml`, dependency-order, or `START_HERE.md` change;
- no Preflight Task 3 work.

## 11. Acceptance

Task 2 passes only when:

1. all thirteen candidate paths are exact and no unowned path changed;
2. the committed manifest and deterministic generator agree at version `1.1.0`;
3. the sole allowlisted instruction document is the exact pinned PDF path/SHA tuple;
4. the exact eight allowlisted workbooks are data-only, have their expected kinds, and cannot gain
   instruction authority;
5. official PDF dates and submission rules have page attribution without overclaiming;
6. RED/GREEN, source, schema, style, type, compile, handoff, Git-root, and clean-worktree evidence is
   recorded;
7. both independent final verifiers report zero BLOCKER/HIGH;
8. `STATUS.md` selects Preflight Task 3 without beginning it.
