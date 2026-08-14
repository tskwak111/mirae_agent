# Implementation Status

**Last updated:** 2026-08-15 — Phase 1 Task 5 Checkpoint 1 is implemented and
independently approved at Critical 0 / Important 0 / Minor 0. Task 5 and the Phase 1
gate remain incomplete; Checkpoint 2 is the exact next task.

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
- [x] Task 3: normalize domestic bonds and domestic listed products
- [x] Task 4: normalize overseas listed products and public funds with quarantine
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

**Phase 1 Task 5 Checkpoint 2: implement the strict manifest, recursive inventory,
and canonical logical hashing under focused RED-GREEN TDD.** The approved detailed
plan is `docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md`. Keep Task 5
and the Phase 1 gate unchecked until all eight checkpoints, two-candidate
reproduction, official artifact acceptance, and independent whole-branch review
exist.

## Phase 1 Task 5 design and plan record

The artifact-build contract is approved for implementation in
`docs/superpowers/specs/2026-08-14-phase1-task5-artifact-build-design.md`. D-022 and
D-023 freeze logical-versus-physical identity, exact artifact inventory, bounded
external ordering, guarded publication, wide Silver scope, and the raw exact-link rule.
The authoritative detailed plan is
`docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md`; the legacy Task 5
body points to it and records Checkpoint 1 complete while Checkpoints 2–8 remain
unchecked.

Observed design-gate evidence on 2026-08-14:

- independent final review: Critical 0 / Important 0 / Minor 0;
- `python3 tools/verify_handoff.py`: 61 required files, 9 official inputs,
  41,384,928 bytes;
- `python3 tools/audit_source_data.py --check`: 145,393 rows, snapshot 2026-07-11;
- `uv run pytest tests/contract -q`: 39 passed in 45.28 seconds;
- `uv run pre-commit run --all-files`: Ruff check and Ruff format passed;
- `git diff --check`: passed.

The detailed plan contains eight checkpoints and passed independent final review with
Critical 0 / Important 0 / Minor 0 after its executable resource-loading, stale
editable-copy, first-publication rollback, bounded-memory, packaging, and strict TDD
boundaries were corrected. The narrow resource design correction was independently
approved with Critical 0 / Important 0 / Minor 0 and committed as `0dec136`.

Checkpoint 1 implementation and review evidence on 2026-08-15:

- reviewed commit series: `2546833` (`feat: add artifact build foundations`),
  `fa7b98e` (`fix: close Task 5 checkpoint 1 review gaps`), and `756a791`
  (`fix: verify missing-resource ancestor identity`);
- final independent review at `756a791`: Critical 0 / Important 0 / Minor 0;
- exact CP1 focused suite: 277 passed; unchanged Task 1–4 regression: 533 passed;
  reviewer-selected focused regression: 12 passed;
- full implementation suite: 920 passed in 574.36 seconds;
- Ruff format/check and mypy passed over 91 source files;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required
  files, 9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- final worktree was clean, official source files were read-only, and the official
  expected-contract source remained absent.

The exact next step is Checkpoint 2 in the dedicated plan. Do not create the official
expected logical baseline before Checkpoint 8's two independently verified candidate
builds and review.

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

Observed pre-review Task 6 gate before the first documentation checkpoint:

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

Independent review and fix round:

- Review found four Important gaps and no Critical finding: metadata versions were
  unconstrained; unresolved entities could silently become empty inline/shared-string
  values; rows outside the worksheet's single direct `sheetData` were accepted; and an
  intermediate manifest-path symlink was accepted.
- RED: unsupported manifest/catalog versions plus an intermediate symlink produced
  `3 failed, 30 deselected`; each missing guard accepted the invalid fixture.
- RED: inline entity plus missing/duplicate `sheetData` initially produced `3 failed,
  34 deselected`. The sheetData fixture was corrected and verified against the guardless
  implementation as `2 failed, 35 deselected`; nested `sheetData` separately failed once.
- RED: entity-bearing shared strings separately failed once because the reader returned
  an empty value rather than raising.
- GREEN: exact version literals, component-wise symlink rejection, inline/shared entity
  rejection, and direct/single `sheetData` validation produced `7 passed, 64 deselected`;
  the expanded entity/sheetData set produced `5 passed, 34 deselected`; and the related
  manifest/XLSX suite produced `72 passed` after formatting.
- Independent re-review approved the fix diff with no remaining Critical or Important
  finding. No Phase 1 Task 3 behavior was introduced.
- `27caba1` — close source-ingestion independent-review gaps.

Observed post-review implementation gate before this final documentation update:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 1 ms.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 112 tests in 103.09 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  72 deselected in 77.42 s with full 145,393-row production traversal.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` — PASS.

Observed complete gate after the final documentation update:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 1 ms.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 112 tests in 103.24 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  72 deselected in 77.46 s with full 145,393-row production traversal.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` — PASS.

Subsequent final-review correction wave:

- A later complete-branch review found four additional Important trusted-boundary gaps:
  mutable validated catalog mappings; DTD/entity use in XML attributes plus permissive
  metadata roots/descendants; raw `UnicodeDecodeError`/lexical path `ValueError`
  escapes; and post-percent-decoding OPC target bypasses.
- D-020 freezes the correction without changing D-018/D-019: catalog mappings are
  deeply immutable and predictably serializable; every parsed XML part rejects
  declarations before values/attributes and requires exact root/direct structure; raw
  and decoded targets must pass control/backslash/NUL/traversal/URI and canonical
  round-trip checks before ZIP access.
- RED for catalog immutability: `3 failed, 33 deselected`; table replacement, nested
  sample-map mutation, and serialized/reloaded catalog mutation all succeeded before
  the correction. GREEN: the complete manifest suite was `36 passed` at that
  checkpoint, with focused Ruff/mypy clean.
- RED for malformed metadata/path typing: `3 failed, 36 deselected`; invalid UTF-8
  escaped twice as `UnicodeDecodeError`, and a NUL-bearing manifest path escaped as
  `ValueError` with a local path. GREEN: manifest suite `39 passed`, with focused
  Ruff/mypy clean.
- RED for XML declarations/metadata structure: `15 failed, 2 passed, 39 deselected`;
  all four XML parts accepted unused DTDs, entity-backed metadata attributes and
  malformed roots/containers were consumed, and nested relationships were accepted.
  GREEN: `17 passed, 55 deselected`.
- RED for OPC post-decoding canonicalization: `15 failed, 1 passed, 56 deselected`;
  encoded backslash/NUL/controls, raw controls, non-round-trip encodings, XML attribute
  normalization, and attacker-named ZIP members bypassed validation. GREEN: `18 passed,
  54 deselected`, including canonical relative and `/xl/...` targets.
- Self-review added two more RED-first defenses: wrapper-root worksheet data could be
  yielded before exhaustion and a UTF-16 DTD bypassed the ASCII marker scan (`2 failed,
  72 deselected`). GREEN was `2 passed, 72 deselected`; complete XLSX suite `74 passed`
  with Ruff/mypy clean.
- Correction checkpoints: `5ecab8b` (immutable catalog), `c6899aa` (safe metadata/path
  errors), `efb0191` (XML/OPC hardening), `6610059` (design/plan/D-020), and `026860f`
  (pre-yield root plus multiencoding declaration scan).
- Official inputs, `tests/contracts/expected_source_audit.json`, normalization,
  quarantine, artifacts, and all Phase 1 Task 3 behavior remain untouched.
- Independent final review found no remaining Critical or Important implementation
  issue. Its corroborating runs observed the 113-test focused source-manifest/XLSX suite
  and the three official lineage/parity contracts green.

Observed complete correction-tree gate:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 6 ms.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 153 tests in 99.24 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  113 deselected in 76.09 s with full official traversal.
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

### 2026-08-14 — Phase 1 Task 3: domestic bond and domestic ETF/ETN normalization

Scope implemented:

- Added frozen strict source-cell locator, normalized/derived value, quality-issue,
  and normalization-result contracts. Locators come only from complete `SourceRow`
  cells and preserve raw values, verified checksum, snapshot, sheet, Excel row/column,
  and unchanged cell applicable dates.
- Added pure text, exact identifier, strict date/source-datetime, finite `Decimal`,
  and integral parsers. No parser performs filesystem, database, network, clock, or
  environment I/O.
- Added the strict immutable `1.0.0` rating registry. Missing/unrated and unmapped
  ratings are not comparable; official `C0` and `CC0` remain out of domain, and agency
  values never backfill the primary grade.
- Added pure domestic bond normalization with raw-versus-derived remaining days,
  strict-before-as-of maturity, quantity/maturity tri-state buyability, exact currency,
  rating disagreement, and deterministic nonquarantine warnings.
- Added pure domestic ETF/ETN normalization with distinct product types, exact D-007
  flags, false-before-unknown eligibility, primary/secondary AUM separation, explicit
  domestic currency mapping, independent update fields, and field-specific zero states.
- Added official full-source acceptance only after Tasks 1–5. No official input,
  expected source-audit value, artifact, overseas/public-fund, query, or API behavior
  changed.

Focused RED/GREEN and independent checkpoint review evidence:

| Checkpoint | Observed RED before behavior | Observed GREEN / review result |
|---|---|---|
| shared contracts (`a178438`, `2cad9ca`) | missing `finproof.domain.locators`, then missing normalization error/wrapper contracts; review regressions were `7 failed, 14 passed` because unsafe direct locators were accepted | initial contracts `14 passed`; final locator/source suite `30 passed`; review approved after the direct-lineage fix |
| pure parsers (`5eab49f`, `bb78c80`) | each text/temporal/numeric module was absent; review regressions were `2 failed, 17 passed` for raw string zero status and oversized integral expansion | parser suite `48 passed`; review approved after numeric-bound hardening |
| rating registry (`1a2afa5`, `a5f0481`, `a5dfa17`) | typed errors/registry were absent; first review regressions were `16 failed, 29 passed`; second were `6 failed, 45 passed` for duplicate YAML keys and categories | final registry suite `51 passed`; review approved after serialization/direct-construction and duplicate-key hardening |
| bonds (`e905edf`) | module absent; later behavior REDs were `1 failed, 19 passed`, `4 failed, 37 passed`, and `6 failed, 46 passed` for maturity warning, currency/quantity warnings, and ratings | bond file `52 passed`; combined gate `172 passed`; independent review approved with no Critical or Important finding |
| domestic listed (`7ab7a88`, `388fdd9`) | module absent; state RED was `16 failed, 18 passed`; currency/optional-warning RED was `4 failed, 53 passed` | domestic-listed file `57 passed`; combined gate `229 passed`; review approved, and its Minor combined-quarantine test passed immediately then committed test-only |

Task 6 acceptance evidence:

- The full acceptance contract was permitted to pass immediately because it introduced
  no new production behavior. Its first executable run was `1 passed in 14.16s`; no
  synthetic RED or production correction was introduced. After a type-only test local
  rename and Ruff formatting, the same acceptance was `1 passed in 14.10s`; the Step 4
  run was `1 passed in 14.04s`.
- The accepted assertions exhausted exactly 44,128 source rows without an unexpected
  exception: 42,394 bond rows produced 42,394 records and zero quarantines; 1,734
  domestic-listed rows produced 1,733 records and one quarantine.
- Source groups were exactly 1,202 ETF and 532 ETN before quarantine; produced groups
  were 1,201 ETF and 532 ETN. The only quarantined row was Excel row 1,155 with raw
  `pd_itm_no="KR"` and a blocker located at that exact cell.
- The acceptance assertions proved 42,394 unique bond IDs and 1,733 unique
  domestic-listed IDs. Every declared wrapped field matched its source row's exact raw
  value and full locator, and every derived value named the exact expected input-cell
  locators at as-of `2026-07-11`.

Observed pre-final-review repository gate on acceptance commit `f9d218d`:

- `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups` — PASS:
  67 packages checked in 1 ms.
- focused Task 3 unit command — PASS: 230 tests in 0.24 s.
- official domestic acceptance command — PASS: 1 test in 14.04 s.
- all source-contract tests with the marker — PASS: 4 tests, 113 deselected in
  93.13 s.
- `uv run ruff format --check .` — PASS: 64 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 64 source files.
- `uv run pytest -q` — PASS: 384 tests in 114.63 s.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official
  inputs, 41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` and `git diff --cached --check` — PASS: no output.

Task 3 commits through the acceptance checkpoint:

- `e855d8a0375037febf3374a7c01424cc00cedc38` — approved domestic-normalization
  design.
- `f2a49136509b1fea9ad1191b992fc4cbd7394c96` and
  `c5d2434ca810e7724d1c4384e566bb56a355b926` — detailed implementation plan and
  plan-review hardening.
- `a1784384da6c90a21cebc341802c189a8adc0717` and
  `2cad9ca8c1f25895d3f0ff08975d340690ed293d` — shared contracts and direct-locator
  review fix.
- `5eab49fa6668d7ba9b800dc9d76cbb228d878d83` and
  `bb78c8075690e0a2eee11cf281b40d49035f5a68` — pure parsers and numeric-bound
  review fix.
- `1a2afa5f05679dad328cb5b078af9558206d6e17`,
  `a5f048174a3bf93aa7d0737c8cbe6fcd2f44a5c3`, and
  `a5dfa170300541f0bdc7f797ceb91a34aba8cd1a` — rating registry and its two review
  fixes.
- `e905edfe5ad3b8f973b2be9fc25c3302b1efaba4` — domestic bond normalization.
- `7ab7a88bdd877175d4b4879199cf3b9042ffa7f3` and
  `388fdd98d7bdaf545fedbae465006c733c597086` — domestic listed normalization and
  review-requested test-only composition coverage.
- `f9d218d4820cb4cf64dae73163a7af53841bfdcf` — official 44,128-row acceptance.
- The Task 3 verification-document commit is recorded in the subsequent
  final-review evidence update and the ignored Task 6 report, because a Git commit
  cannot embed its own final object hash.

Decision-log inspection and residual boundaries:

- No higher-priority conflict or new frozen product decision was discovered, so
  `docs/10_DECISION_LOG.md` was not changed.
- A-011 remains open for the later persisted quality/evidence artifact schema; Task 3
  keeps normalization issues deterministic and clock-free with
  `first_detected_at=None`.
- Q-003 remains open. Bond source quantity and deterministic snapshot-maturity
  validation remain separate rather than guessing the organizer's intended meaning
  of “buyable.”
- Independent whole-branch review of
  `f2a49136509b1fea9ad1191b992fc4cbd7394c96..1a9dc52be0c4d981ec89b008fe2c246e98784ce4`
  was approved with Critical 0, Important 0, and Minor 0. The reviewer independently
  observed 230 focused tests, the official 44,128-row acceptance, 384 full-suite tests,
  Ruff, mypy over 64 files, source audit 145,393, handoff 61/9/41,384,928, schema 207,
  strict serialization/no-I/O probes, clean scope diff, and a clean worktree.
- Final reviewed-tree gate on review-evidence commit `fbbcec4` — PASS: frozen sync
  checked 67 packages; 230 focused tests; official acceptance 1 test in 14.03 s;
  source-contract 4 tests/113 deselected in 91.85 s; Ruff format/check; mypy over 64
  files; 384 full-suite tests in 116.06 s; source audit 145,393; handoff
  61/9/41,384,928; schema 207; pre-commit; diff checks; and clean feature worktree.
- Phase 1 Tasks 4–5 and the Phase 1 gate remain unchecked.

Exact next development task:

**Phase 1 Task 4: normalize overseas listed products and public funds with
quarantine.** Resolve A-011 before its first persisted quality/evidence consumer and
start with the overseas zero/tie preservation RED. Do not start artifact building in
the same uncontrolled change.

### 2026-08-14 — Phase 1 Task 4: overseas listed and public-fund normalization

Scope implemented:

- Aligned the canonical quality-issue JSON schema to the frozen
  `DataQualityIssue.model_dump(mode="json")` contract, including all issue/locator
  fields, explicit Draft 2020-12 `FormatChecker` use, and UTC terminal-`Z` validation.
- Added complete 49-column overseas and 45-column public-fund synthetic rows, a shared
  exact ETF/ETN enum, exact unpadded overseas identity parsing, opt-in literal-`NULL`
  parsing, and strict `FundItemValue` repeated-locator invariants.
- Added a strict all-field `OverseasListedProduct` and pure normalizer. Product type
  comes only from `pd_grp_no`; trading currency comes only from `pd_trd_ccy`; source
  zero/date/timestamp/flag states remain field-specific; no eligibility, staleness, or
  dataset-level constant state is inferred.
- Added a strict all-field `FundAttributeRow` and pure normalizer. The exact input
  `SourceRow` instance is retained; Python accepts only exact `SourceRow` objects;
  canonical JSON is structurally prechecked before validation; every wrapper is
  cross-checked against its exact raw cell and locator.
- Added global public-fund collapse to `itm_no` grain with one sibling attribute per
  contributing source row, complete 44-field representative/equivalent-locator
  evidence, exact raw agreement, stable output, and fail-closed duplicate,
  normalized-collision, and disagreement rules.
- Added the verified official acceptance for 5,646 overseas rows and 95,619 public-
  fund rows. No official input, expected audit, persisted artifact, exact link,
  family, query, API, HCX, or eligibility behavior changed.

Focused RED/GREEN evidence:

| Checkpoint | Observed RED before behavior | Observed GREEN / review result |
|---|---|---|
| quality schema (`d8a6500`, `6f5c93f`) | legacy schema: `2 failed, 17 passed`; review regression: malformed terminal-`Z` values were accepted, `2 failed, 19 passed` | schema `21 passed`; combined contract gate `42 passed`; initial review 0 Critical/1 Important/0 Minor, then approved 0/0/0 after the dev-only RFC3339 checker correction |
| foundations (`8c60cad`) | exact helper import and `FundItemValue` module were absent; a guard-disabled later-source-order mutation failed to raise | fixture/parser cycle `88 passed`; value cycle `16 passed`; regression suite `130 passed`; independent review approved 0/0/0 |
| overseas (`23f02a5`) | missing module; then missing mapping/valid path; policy `6 failed, 14 passed`; model invariants `7 failed, 23 passed` | model scaffold `2 passed`; valid mapping `8 passed`; policy `20 passed`; final model file `30 passed`; regression `105 passed`; independent review approved 0/0/0 |
| fund row (`687a8a5`) | missing model/module; policy `7 failed, 13 passed`; Python/JSON/invariants `44 failed, 38 passed`; padded-currency self-review exposed two failures | scaffold `17 passed`; mapping `23 passed`; policy `20 passed`; invariant suite `82 passed`; final fund/overseas regression `137 passed`; independent review approved 0/0/0 |
| fund collapse (`b554b48`, `cc55153`) | missing models/callables; invariants `20 failed, 75 passed`; duplicate/collision `3 failed, 25 passed`; disagreement `44 failed, 28 passed`; mixed ordering one failure; malformed-key and short-row regressions failed at unsafe lookup; independent review added four duplicate-location failures | scaffold `3 passed`; valid/scale `7 passed`; invariant `95 passed`; producer suites `28` then `72 passed`; final corrected focused suite `190 passed`; initial review 0 Critical/1 Important/0 Minor, then approved 0/0/0 after duplicate source-location rejection |
| official acceptance (`ba2122d`) | no synthetic RED was manufactured because Tasks 1-5 already introduced the production behavior | first run `2 passed in 383.99s`; checkpoint review approved 0/0/0; no production correction was required |

Official acceptance evidence:

- Overseas: 5,646 source rows produced 5,646 unique records and zero quarantines;
  5,587 ETF and 59 ETN; all trading currencies were the source `pd_trd_ccy=USD`;
  363 fee zeroes and 5,283 positive fees; 5,388 recorded-zero and 258 blank one-day
  returns; 5,451 positive, 8 zero, and 187 blank AUM values; 5,638 nonblank values for
  each core text field; 2,360 replication methods; 8 listing-date zero sentinels; and
  10 blank sale plus 10 blank trade flags. Every one of the 49 wrappers retained the
  exact raw cell and complete locator.
- Public funds: 95,619 rows contained 11,139 raw IDs and produced 11,138 item records,
  95,618 attributes, and one malformed-item blocker at Excel row 84,563 for raw
  `itm_no='"'`. The source had 95,619 unique raw pairs, zero raw duplicates, 228 raw
  and 228 trimmed attribute codes, 1,670 padded rows, zero normalized collisions, and
  zero non-attribute disagreement groups.
- Item facts were 11,067 KRW and 71 USD items; 18,416 literal-`NULL` risk-code rows
  across 2,573 items; 5,436 type-`06` rows across 686 items; and exactly 20 below-minus-
  100 cells on five source rows for item `KR515303001M`. Maximum attribute cardinality
  was 16. Every item retained all contributing rows, the lowest-row representative,
  and every agreeing field locator; no family or name-based ETF conversion occurred.
- The selected 32 official multi-attribute rows produced byte-identical two-item,
  32-attribute results in canonical, reverse, even-then-odd, and odd-then-even orders.

Checkpoint reviews and commits:

- `c47e011463c55124f47cba17e048ff3a21857394` — approved Task 4 design.
- `500926afd02f8448916014f88c48e3d772d347ed` — approved detailed plan and frozen
  D-021/refined A-011 decision boundary.
- `d8a6500c96b87001a0b5f709a4560815288a62ee` and
  `6f5c93f601a3bbbea0a7a3077e61bd40c80f5fd6` — quality schema and review correction.
- `8c60cade794f0131e3a5ee68cde28096dd365fa5` — Task 4 foundations.
- `23f02a5ae7d595cd44f8b429655807777c758999` — overseas normalization.
- `687a8a502dafd2386963aa5e9cdc2e867d817bcb` — public-fund row normalization.
- `b554b48c71c1381c249c465ae9a47a89d5c7d0ee` and
  `cc55153c20bffa0fbed40eb50c589ba6d0d9324d` — fund collapse and review correction.
- `ba2122d73f51cc12db014aad8a1e0b538c74ec4d` — official acceptance.
- `70e017c95525969aadd90c9022eadbf5c93d78a7` — Task 4 verification evidence and
  plan/status checkpoint.
- `baf0c21dc83210057003bb545cc127c33882c495` — independent whole-branch review
  evidence; this is the exact reviewed HEAD used by the final gate below.

Observed pre-whole-branch repository gate on implementation HEAD `ba2122d`:

- `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups` — PASS:
  68 packages checked in 2 ms.
- focused quality/domain/normalization command — PASS: 442 tests in 1.97 s.
- bounded collapse scale command — PASS: 2 tests in 10.29 s; JUnit measured 98,240
  transient bytes at 256 rows, 223,424 at 512 rows, and peak live normalized rows 1.
- official Task 4 acceptance — PASS: 2 tests in 364.89 s; the fund normalization body
  measured 261.755902 s and peak RSS 4,963,942,400 before versus 7,303,561,216 bytes
  after (increase 2,339,618,816 bytes).
- all source-contract tests with the marker — PASS: 6 tests, 113 deselected in
  532.19 s.
- `uv run ruff format --check .` — PASS: 77 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 77 source files.
- `uv run pytest -q` — PASS: 642 tests in 575.03 s.
- source audit — PASS: 145,393 rows, snapshot `2026-07-11`.
- handoff — PASS: 61 required files, 9 official inputs, 41,384,928 source bytes.
- schema catalog — PASS: 207 columns.
- pre-commit — PASS: Ruff check and Ruff format hooks.
- both diff checks — PASS with no output; official writable-file count remained zero;
  the implementation HEAD worktree was clean before this documentation update.

Independent whole-branch review evidence:

- A fresh reviewer inspected commit `70e017c95525969aadd90c9022eadbf5c93d78a7`
  with exact tree `c29b6d4bb9c114b92b0236c15a8f7c3644f7f4e9` against the repository
  contract, frozen decisions, approved design/plan, Task 2/3 boundaries, RED/GREEN
  history, and every Task 4 official acceptance invariant.
- Review result: approved with Critical 0, Important 0, and Minor 0. No correction
  commit or new production behavior was required.
- Reviewer fresh evidence: frozen sync checked 68 packages; focused quality/domain/
  normalization tests were 442 passed in 2.18 s; bounded scale was 2 passed in
  10.41 s with 98,240/223,424 transient bytes and peak live normalized rows 1;
  official acceptance was 2 passed in 364.12 s, with fund normalization
  259.344823 s and peak RSS 5,014,470,656 before versus 7,627,603,968 bytes after
  (increase 2,613,133,312 bytes).
- Reviewer Ruff format/check and mypy over 77 source files were clean. Source audit
  remained 145,393 rows at `2026-07-11`; handoff remained 61 required files, 9
  official inputs, and 41,384,928 bytes; schema catalog remained 207 columns; and
  the reviewed tree/worktree was clean.
- This review-evidence commit is recorded in the subsequent final-gate update because
  a Git commit cannot embed its own final object hash.

Final reviewed-tree gate evidence on exact clean HEAD
`baf0c21dc83210057003bb545cc127c33882c495`:

- `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups` — PASS:
  68 packages checked in 2 ms.
- focused quality/domain/normalization command — PASS: 442 tests in 2.03 s.
- bounded collapse scale command — PASS: 2 tests in 10.26 s; JUnit suite time
  10.194 s, 98,240 transient bytes at 256 rows, 223,424 at 512 rows, and peak live
  normalized rows 1.
- official Task 4 acceptance — PASS: 2 tests in 375.23 s; JUnit suite time
  375.122 s and fund-test time 367.262 s. The fund normalization body measured
  270.740757 s; peak RSS was 5,015,289,856 before versus 7,035,207,680 bytes after,
  an increase of 2,019,917,824 bytes.
- all source-contract tests with the marker — PASS: 6 tests, 113 deselected in
  533.72 s.
- `uv run ruff format --check .` — PASS: 77 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 77 source files.
- `uv run pytest -q` — PASS: 642 tests in 591.54 s.
- source audit — PASS: 145,393 rows, snapshot `2026-07-11`.
- handoff — PASS: 61 required files, 9 official inputs, 41,384,928 source bytes.
- schema catalog — PASS: 207 columns.
- pre-commit — PASS: Ruff check and Ruff format hooks.
- both diff checks — PASS with no output; `git status --short --branch` showed only
  the feature-branch header, the porcelain emptiness assertion passed, and the
  official writable-file search returned zero paths before this documentation update.

Decision boundaries and remaining procedures:

- D-021 is implemented: pure issues keep `first_detected_at=None`; Task 5 injects a
  timezone-aware UTC persistence time whose JSON form ends in `Z`, outside logical
  reproducibility hashes.
- A-003 remains open; Task 4 derives no overseas/public-fund eligibility.
- A-011 remains open only for later evidence, golden-case, and metric contracts.
- Independent whole-branch review, the final reviewed-tree gate, and the authorized
  local fast-forward are complete. Task 5 Checkpoint 1 is now implemented and
  independently approved; Checkpoints 2–8 remain.
- Phase 1 Task 5 and the Phase 1 gate remain unchecked.

Exact next development task:

**Phase 1 Task 5 Checkpoint 2: implement the strict manifest, recursive inventory,
and canonical logical hashing from the approved dedicated plan.** Do not mark Task 5
or the Phase 1 gate complete before official reproduction and review evidence exists.
