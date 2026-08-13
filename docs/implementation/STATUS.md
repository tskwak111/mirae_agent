# Implementation Status

**Last updated:** 2026-08-13 — Phase 1 Task 1 implemented and verified; Phase 1 Task 2 is next.

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
- [ ] Task 2: implement source manifest and streaming workbook reader with row lineage
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

**Phase 1, Task 2.** Resolve decision-log item A-002 for the complete lineage shape, then implement the source manifest and streaming workbook reader under strict TDD.

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

- Added environment-backed typed `Settings` with evaluation defaults, frozen `2026-07-11` snapshot, typed paths, and bounded top-k validation.
- Added transport-independent `FinProofError`/`SourceContractError` and immutable `VersionBundle` defaults matching checked-in version `1.0.0` policies.
- Added `finproof` commands `show-versions`, `verify-handoff`, and `audit-source`. Source commands call the existing Python tools in-process from a verified FinProof checkout.
- Added `.env.example` with safe non-secret values, Ruff pre-commit hooks pinned to `v0.15.22`, and a read-only-permission GitHub Actions workflow on Python 3.12 with uv `0.12.3` frozen installation.
- Installed the local pre-commit hook and amended the original Phase 1 Task 1 file/check scope to cover the previously missing automation files.

RED evidence observed before implementation:

- Settings test collection failed with `ModuleNotFoundError: No module named 'finproof.core'`.
- Version test collection failed with `ModuleNotFoundError: No module named 'finproof.core.versions'`.
- CLI test collection failed with `ModuleNotFoundError: No module named 'finproof.cli'`.
- The installed `finproof` entry point then failed all three commands because pytest exposed top-level `tools` while the real console did not. A parameterized console regression reproduced that boundary before repository-tool loading was corrected.
- Automation contract tests failed three times with missing `.env.example`, `.pre-commit-config.yaml`, and `.github/workflows/ci.yml`.

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
- `uv run pytest -q` — PASS: 22 tests.
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

Remaining risks:

- The GitHub Actions YAML and every command it contains were validated locally, but no remote GitHub Actions run exists until this branch is pushed to a GitHub repository.
- `verify-handoff` and `audit-source` are repository bootstrap commands; when invoked outside a checkout they fail closed with a concise `FinProofError`.
- Phase 1 Task 2 must resolve A-002 before freezing `SourceRow`/evidence lineage fields. Other A-series decisions retain the task boundaries recorded in `docs/10_DECISION_LOG.md`.

Exact next task:

**Phase 1, Task 2.** First resolve A-002 so source checksum, dataset snapshot, and applicable-date lineage are present in the planned contracts. Then begin with the failing official-manifest checksum test; do not start normalization or artifact building in the same uncontrolled change.
