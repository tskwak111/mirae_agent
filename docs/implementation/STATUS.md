# Implementation Status

**Last updated:** 2026-08-14 — Phase 1 Task 2 implemented and verified; Phase 1 Task 3 is next.

## Frozen baseline

- [x] Official task PDF included
- [x] Eight official workbooks included with ASCII filenames
- [x] Input checksums and audit baseline defined
- [x] Final architecture and domain contracts frozen
- [x] Machine-readable seed policies and JSON schemas included
- [x] TDD phase plans and Codex prompts included

## Phase 1 — Repository and data foundation

Plan: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`

- [x] Task 1: bootstrap settings, version bundle, CLI, and handoff/source checks in tests/CI
- [x] Task 2: implement source manifest and streaming workbook reader with row lineage
- [ ] Task 3: normalize domestic bonds and domestic listed products
- [ ] Task 4: normalize overseas listed products and public funds with quarantine
- [ ] Task 5: build Parquet/DuckDB artifacts, exact links, quality report, and reproducibility check
- [ ] Phase 1 gate passed

## Phase 2 — Deterministic query, policy, evidence, and answer engine

Plan: `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md`

- [ ] Task 1: domain contracts and registry loaders
- [ ] Task 2: entity resolution and exact cross-source links
- [ ] Task 3: QueryPlan semantic validator and allowlisted SQL compiler
- [ ] Task 4: repositories/executor and differential reference
- [ ] Task 5: state, metric, comparability, and conditional dual-lens policy
- [ ] Task 6: evidence, claim verifier, deterministic Korean renderer, and core service
- [ ] Phase 2 gate passed

## Phase 3 — HyperCLOVA X planner and evaluation API

Plan: `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md`

- [ ] Task 1: HCX client and recorded contract fixtures
- [ ] Task 2: structured/strict JSON planner, repair, and rule fallback
- [ ] Task 3: API application, exact `/answer`, health/readiness/version, and safe errors
- [ ] Task 4: bounded timeout/retry/concurrency/cache and structured observability
- [ ] Task 5: Docker/reproduction and end-to-end API tests
- [ ] Phase 3 gate passed

## Phase 4 — Evaluation, hardening, proposal evidence, and release

Plan: `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`

- [ ] Task 1: canonical golden set and scoring harness
- [ ] Task 2: paraphrase, metamorphic, differential, quality, and adversarial suites
- [ ] Task 3: ablation and latency/load/resilience/soak measurement
- [ ] Task 4: competition compliance and independent review closure
- [ ] Task 5: clean-room reproduction, immutable release manifest, and submission freeze
- [ ] Phase 4 gate passed

## Current next task

**Phase 1 Task 3: normalize domestic bonds and domestic listed products.** Begin with the failing bond date/source-fidelity tests in the Phase 1 plan. Do not start overseas-listed/public-fund normalization or artifact building in the same uncontrolled change.

## Handoff validation record — not production implementation

Observed on 2026-08-07:

- `python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs.
- `python tools/audit_source_data.py --check` — PASS: 145,393 source rows, snapshot 2026-07-11.
- `python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `pytest -q` — PASS: 7 handoff contract tests.
- `python -m compileall -q src tools tests` — PASS.
- `python -m tools.verify_handoff` — PASS; handoff tools are importable as modules as well as executable scripts.
- JSON/YAML parse check — PASS: 8 schemas and 8 policy/config files.
- The original handoff did not include `uv.lock`. The first network-enabled macOS bootstrap generated it with uv on 2026-08-13; future installation must use `uv sync --frozen --all-groups`.
- Dependency metadata was cross-checked before handoff; notably the Polars lower bound was corrected to the published `1.43.0` release. Ruff and mypy were unavailable in the artifact environment; both were installed and their existing findings were cleared during the 2026-08-13 macOS bootstrap below.

See `docs/13_HANDOFF_VALIDATION_REPORT.md`. These checks validate the handoff package, not the production system.

## Work log

### 2026-08-13 — Windows-to-macOS handoff audit and workstation bootstrap

This was workstation and handoff work, not Phase 1 product implementation.

Changes:

- Installed native Apple Silicon `uv 0.12.3` and Python `3.12.13` with Homebrew.
- Generated `.python-version`, `.venv`, and resolver-produced `uv.lock` for all dependency groups.
- Added `.gitignore`, initialized `main`, and committed the verified handoff baseline.
- Removed four `.DS_Store` files, eleven CPython 3.14 bytecode files (including transferred Windows absolute paths), and empty pytest transfer directories. None were committed.
- Made the local `source_material/` tree read-only. Git does not preserve `0444`, so checksum gates and future read-only CI/container mounts remain required.
- Normalized the other transferred project files/directories from world-writable `0666`/`0777` to `0644`/`0755`; retained Apple quarantine/provenance extended attributes as non-blocking provenance metadata.
- Formatted and typed the existing handoff tools without changing official data, config, schemas, or product behavior; added `types-jsonschema` as a dev-only typing dependency.
- Corrected `START_HERE.md`, `HANDOFF_PACKAGE_MANIFEST.md`, and `Makefile` to use the checked-in lock with frozen sync, run source checks before dependency installation, and stop claiming that absent pre-commit/CI/environment templates exist.
- Added a regression contract for those bootstrap instructions and registered every audited contract conflict in `docs/10_DECISION_LOG.md` with its affected task boundary.
- Added the exhaustive audit report at `docs/implementation/2026-08-13_MACOS_HANDOFF_AUDIT.md`.

RED evidence observed before the quality-only repair:

- `uv run ruff format --check .` — FAIL: 6 files required formatting.
- `uv run ruff check .` — FAIL: 41 findings.
- `uv run mypy src tests tools` — FAIL: 14 findings.
- These findings were present in the transferred baseline when first checked in the resolved macOS environment; the original handoff report states Ruff and mypy were unavailable in its creation environment.

GREEN evidence observed after the repair:

- `uv run ruff format --check .` — PASS: 10 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 10 source files.
- `uv run pytest -q` — PASS: 7 tests.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot 2026-07-11.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs, 41,384,928 bytes; PyYAML parser active.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.

RED/GREEN evidence for the bootstrap-instruction regression:

- RED: the focused test first failed because `Makefile` used unfrozen sync; after that repair, its ordering assertion failed because the manifest synchronized dependencies before the pre-install source checks.
- An incidental first rerun was blocked before test collection when uv needed the isolated `hatchling` build dependency and the sandbox denied DNS. `uv sync --frozen --all-groups` was rerun with approved network access; the actual assertion RED failures above were then observed.
- GREEN: the focused test passed after all three active bootstrap entry points were corrected.

Final current-tree evidence after independent review:

- `uv sync --frozen --all-groups` — PASS: checked 67 packages.
- `uv run ruff format --check .` — PASS: 10 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 10 source files.
- `uv run pytest -q` — PASS: 8 tests.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot 2026-07-11.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs, 41,384,928 bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- permission gate — PASS: zero world-writable project paths outside local Git/venv state; source files locally read-only.
- `git diff --check` — PASS.

Intermediate commits created before this final audit record:

- `68bdd2e1686737eee652c91e8d3751a92e3555a8` — verified handoff and macOS bootstrap baseline.
- `97a79c3483086e0e25c073e1537181a4d8ea6f6d` — bootstrap Ruff/mypy repair.

Risks and unresolved decisions:

- The original handoff claimed CI/environment templates were included, but they were absent at migration time. Phase 1 Task 1 added `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, and `.env.example` as recorded below.
- The full audit found unresolved aggregate-plan, lineage, state, cache-key, partitioned top-k, and release-manifest contracts. They are registered in `docs/10_DECISION_LOG.md` and must be reconciled before each listed affected task, not before unrelated Phase 1 Task 1 work.
- All 13 golden seeds are AI-handoff seeds rather than human-reviewed evaluation cases.
- Docker is not installed; it is not needed for Phase 1 and becomes necessary for the Phase 3 container gate.
- The first Git commit was created after cleanup/bootstrap, so Git cannot independently reconstruct the pre-clean transfer inventory or prove chain of custody before that root commit. Current manifest/audit checks establish internal consistency only.

Exact next task:

**Phase 1, Task 1**, under strict TDD. First amend its planned file scope to include CI, `.pre-commit-config.yaml`, and `.env.example`; then add the failing settings/version/CLI/bootstrap tests specified by the plan. The other logged conflicts block only their listed affected tasks.

### 2026-08-13 — Phase 1 Task 1: typed core, CLI, and CI bootstrap

Scope implemented:

- Added environment-backed typed `Settings` with evaluation defaults, an evaluation-mode invariant that fixes the official snapshot at `2026-07-11`, typed paths, and bounded top-k validation.
- Added transport-independent `FinProofError`/`SourceContractError` and immutable `VersionBundle` defaults matching checked-in version `1.0.0` policies.
- Added `finproof` commands `show-versions`, `verify-handoff`, and `audit-source`. Source commands call the existing Python tools in-process only when the working directory is the checkout containing the installed editable FinProof package.
- Added `.env.example` with safe non-secret values, Ruff pre-commit hooks pinned to `v0.15.22`, and a read-only-permission GitHub Actions workflow on Python 3.12 with uv `0.12.3` frozen installation. Every third-party CI action is pinned to a full commit SHA.
- Installed the local pre-commit hook and amended the original Phase 1 Task 1 file/check scope to cover the previously missing automation files.

RED evidence observed before implementation:

- Settings test collection failed with `ModuleNotFoundError: No module named 'finproof.core'`.
- Version test collection failed with `ModuleNotFoundError: No module named 'finproof.core.versions'`.
- CLI test collection failed with `ModuleNotFoundError: No module named 'finproof.cli'`.
- The installed `finproof` entry point then failed all three commands because pytest exposed top-level `tools` while the real console did not. A parameterized console regression reproduced that boundary before repository-tool loading was corrected.
- Automation contract tests failed three times with missing `.env.example`, `.pre-commit-config.yaml`, and `.github/workflows/ci.yml`.
- Independent review then produced three focused RED checks against the first implementation: evaluation mode accepted `2026-07-10`; a lookalike working directory executed its own `tools.verify_handoff`; and the CI action-reference assertion rejected the mutable `actions/checkout@v6` and `actions/setup-python@v6` tags. The minimal hardening change made the three focused checks and the 14-test related suite pass.

Incidental verification findings and resolution:

- Pydantic's runtime-only `_env_file` argument is absent from its static synthesized signature. Tests now isolate `.env` through `tmp_path`/working directory and use the public constructor.
- Strict mypy identified one unnecessary suppression comment, which was removed.
- The first pre-commit invocation could not write the sandboxed home cache and could not fetch GitHub over sandbox DNS. A task-specific `/private/tmp` cache and approved one-time network fetch were used; the pinned hook subsequently ran offline.
- The first full format gate reported one automation test file; it was mechanically formatted and the complete gate was rerun.

Final observed verification before this status update:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked.
- `uv run ruff format --check .` — PASS: 22 files already formatted.
- `uv run ruff check .` — PASS.
- `uv run mypy src tests tools` — PASS: no issues in 22 source files.
- `uv run pytest -q` — PASS: 24 tests.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs, 41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- All three `uv run finproof ...` commands — PASS with deterministic versions and the same handoff/source results.
- `uv run pre-commit run --all-files` — PASS: Ruff check and format hooks.
- `git diff --check` — PASS.

Implementation checkpoints:

- `7d2888f` — typed settings and errors.
- `3c339f8` — immutable version bundle.
- `20ea7c9` — deterministic CLI and installed-console regression.
- `d443feb` — environment, pre-commit, CI, and automation contracts.
- `a3af00b` — mechanical formatting required by the final hook gate.
- `1e12985` — Task 1 verification evidence, status, and exact next task.
- `a23fab3` — independent-review hardening for snapshot, repository-command, and CI supply-chain boundaries.

Remaining risks:

- The GitHub Actions YAML and every command it contains were validated locally, but no remote GitHub Actions run exists until this branch is pushed to a GitHub repository.
- `verify-handoff` and `audit-source` are repository bootstrap commands; when invoked anywhere other than the checkout that supplies the installed editable package they fail closed with a concise `FinProofError`.
- Phase 1 Task 2 must resolve A-002 before freezing `SourceRow`/evidence lineage fields. Other A-series decisions retain the task boundaries recorded in `docs/10_DECISION_LOG.md`.

Exact next task:

**Phase 1, Task 2.** First resolve A-002 so source checksum, dataset snapshot, and applicable-date lineage are present in the planned contracts. Then begin with the failing official-manifest checksum test; do not start normalization or artifact building in the same uncontrolled change.

### 2026-08-14 — Phase 1 Task 2: verified source manifest and streaming XLSX lineage

This is the first Phase 1 product-data implementation checkpoint. The prior Task 1
checkpoint made the workstation/repository automation ready; it did not implement
source ingestion. The Phase 1 gate remains open because normalization, quarantine,
quality reports, and reproducible Parquet/DuckDB artifacts are later tasks.

Scope implemented:

- Added safe structured source errors and immutable `SourceCell`/`SourceRow` raw-lineage
  contracts with checksum, snapshot, manifest-relative file, table, sheet, exact Excel
  row/column, raw payload/value, and explicit optional cell applicable date.
- Added strict immutable manifest/schema-catalog metadata models. Unknown fields,
  coercible numeric metadata, table/catalog drift, and injected catalog content fail
  closed.
- Added all-or-nothing file verification for containment, type/symlink, size, and
  chunked SHA-256 checks. Only a fully verified set exposes `VerifiedSourceFile` values.
- Added a bounded-memory hardened XLSX reader whose only public input is
  `VerifiedSourceFile`. It validates ZIP/OPC/XML structure, exact sheet/header/cell
  coordinates, formulas, row widths/order/counts, and emits exact unnormalised strings.
- Added official-source acceptance coverage that fully traverses all 145,393 rows,
  checks every row/cell lineage coordinate and state, and compares selected rows with
  the independent bootstrap reader.
- No normalization, quarantine, artifact building, query/API behavior, official input,
  or expected source-audit value changed.

Authoritative decisions and remaining boundary:

- A-002 is implemented under D-017: production ingestion accepts only a verified
  descriptor and preserves the complete frozen raw-lineage shape.
- D-018 assigns JSON structure/metadata validation to `SourceFileManifest.load` and
  manifest-relative containment/`PATH_ESCAPE` validation to `verify(base_dir)`.
- D-019 permits the official OPC package-absolute `/xl/...` worksheet target only after
  strict canonicalization to an internal ZIP member; traversal, external/URI targets,
  external relationship mode, and host-filesystem interpretation remain prohibited.
- A-011 remains open only for later quality/evidence schemas and metric entries. It no
  longer blocks the implemented Task 2 raw-lineage boundary.

Focused RED/GREEN evidence:

| Checkpoint | Observed RED before behavior | Observed GREEN |
|---|---|---|
| source errors / lineage (`c711623`) | error imports failed because `SourceErrorCode` was absent; lineage collection failed because `finproof.domain` was absent; the public error boundary then failed because `Path` context was accepted | error tests `3 passed`; initial combined lineage/error tests `12 passed`; hardened combined suite `13 passed` |
| strict metadata (`946f562`, `0aa3907`) | collection failed because `finproof.data` was absent; review regressions then showed injected `schema_catalog` accepted, two unsafe path forms accepted, and a numeric string coerced | initial metadata suite `14 passed`; hardened suite `18 passed` |
| verified descriptors (`5541d55`, `3941f3e`) | `10 failed, 16 passed`: nine cases lacked `verify`, and the boundary test exposed load-time rather than verify-time path handling; three injected OS-access cases then escaped as raw `PermissionError` | verification suite `26 passed`; fail-closed OS-error suite brought the file to `30 passed` |
| streaming reader (`ecbc6e2`) | collection failed because `finproof.data.xlsx_stream` was absent; first implementation was `19 passed, 1 failed` because an invalid shared-string index escaped as `IndexError`; after the authoritative OPC decision, three tests exposed rejection of the required package-absolute target and acceptance of external variants | initial reader suite `20 passed`; OPC-safe reader suite `23 passed` |
| reader hardening (`6ac3c5b`) | Excel bounds/row ordering: `4 failed, 1 passed`; negative shared-string index: `1 failed`; relationship type/base resolution: `2 failed`; duplicate/encrypted/unsupported ZIP members: `3 failed` | corresponding focused suites `5 passed`, `2 passed`, `3 passed`, and `3 passed`; complete reader suite `34 passed` |
| official acceptance (`05949b4`, `f4d49cc`) | no synthetic production RED was permitted for already-implemented acceptance behavior; one authoring-only pytest mark tuple error was corrected before the first executable acceptance run | official lineage/parity acceptance `3 passed`; exhaustive cell-coordinate/state amendment also passed immediately with no production change |

Implementation checkpoints:

- `c711623` — immutable source lineage contracts.
- `946f562` and `0aa3907` — strict official metadata plus validation hardening.
- `5541d55` and `3941f3e` — all-or-nothing verified descriptors plus fail-closed
  source-access handling.
- `ecbc6e2` and `6ac3c5b` — verified XLSX streaming plus structural hardening.
- `05949b4` and `f4d49cc` — official full-lineage/parity acceptance plus exhaustive
  cell-coordinate/state assertions.

Observed Task 6 gate before this documentation checkpoint:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 7 ms. The first
  sandboxed attempt could not initialize `~/.cache/uv`; the exact command was rerun with
  approved access to the configured uv cache.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 104 tests in 100.07 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  64 deselected in 72.68 s; the official test fully traversed 145,393 production rows.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` — PASS.

Residual risks:

- Full official lineage acceptance is intentionally expensive because it normally
  exhausts every production iterator; sampling cannot replace this count/lineage gate.
- The GitHub Actions workflow remains locally validated but has no remote run until the
  branch is pushed.
- A-011 must be resolved before its later quality/evidence producer or consumer; Task 2
  does not authorize guessing those schemas.

Exact next task:

**Phase 1 Task 3: normalize domestic bonds and domestic listed products.** Begin with
the failing bond date/source-fidelity tests in the Phase 1 plan. Keep Phase 1 Tasks 4–5
and the Phase 1 gate unchecked until their own evidence exists.
