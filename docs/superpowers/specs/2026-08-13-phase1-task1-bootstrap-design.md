# Phase 1 Task 1 — Typed Core, CLI, and CI Bootstrap Design

**Date:** 2026-08-13

**Status:** Approved for implementation planning

## 1. Goal

Implement only Phase 1 Task 1: establish the typed FinProof application core, a deterministic local CLI, and the missing repository automation needed to run the existing handoff/source gates on Python 3.12.

This task does not ingest, normalize, query, rank, or answer over product data. Those behaviors remain in later Phase 1 and Phase 2 tasks.

## 2. Scope

Create:

- `finproof.core.settings` with environment-backed typed settings
- `finproof.core.versions` with an immutable version bundle
- `finproof.core.errors` with transport-independent application errors
- `finproof.cli.main` with `verify-handoff`, `audit-source`, and `show-versions`
- focused unit and contract tests
- `.env.example` containing variable names and safe non-secret defaults only
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`

Update the Phase 1 plan and implementation status so their file scope, TDD evidence, commands, results, and exact next task match the repository.

## 3. Component design

### Settings

`ExecutionMode` is a closed string enum with `evaluation` and `extended_demo`. `Settings` is a Pydantic `BaseSettings` model using the `FINPROOF_` prefix and optional local `.env` file.

Defaults are evaluation-safe:

- snapshot date: `2026-07-11`
- official source directory: `source_material/data`
- artifact directory: `artifacts`
- database path: `artifacts/finproof.duckdb`
- default top-k: `5`
- maximum top-k: `50`, bounded to at most `100`

Validation rejects a default top-k greater than the maximum. Paths remain typed `Path` values and are not created as a side effect of loading settings.

### Version bundle

`VersionBundle` is a frozen Pydantic model. It carries dataset, metric, state, quality, rating, answer, and planner versions. Its safe defaults match the checked-in versioned configuration. Mutation raises a Pydantic validation error.

The bundle is serializable for CLI output and later execution traces, but this task does not yet load or validate full registries.

### Errors

`FinProofError` is the base application exception. `SourceContractError` represents official-source contract violations. These errors have no FastAPI dependency and expose no stack trace or internal path to a user-facing transport.

### CLI

`main(argv)` uses `argparse`, returns an integer exit code, and has no mutable module-level request state.

- `verify-handoff` calls the importable handoff verifier directly.
- `audit-source` calls the importable frozen source audit directly.
- `show-versions` emits deterministic JSON from `VersionBundle`.

The first two commands do not spawn subprocesses. Expected `FinProofError` failures produce a concise stderr message and a nonzero exit code; unexpected exceptions are not silently swallowed.

## 4. Repository automation

### Environment template

`.env.example` lists only supported `FINPROOF_` names and safe defaults. It contains no credential values. Runtime secrets are out of scope for Task 1 because HCX integration begins in Phase 3.

### Pre-commit

The configuration pins published hook revisions and runs repository formatting/linting checks without modifying official binary inputs. Type checks and the complete test/source gates remain explicit CI commands rather than expensive commit-time hooks.

### CI

GitHub Actions runs on a case-sensitive Linux filesystem with Python 3.12 and a frozen uv installation. It performs:

1. `uv sync --frozen --all-groups`
2. Ruff format check
3. Ruff lint
4. mypy over `src`, `tests`, and `tools`
5. pytest
6. source audit
7. handoff verification
8. schema catalog verification

CI receives no external model credential and invokes no generative model. Official source files are treated as immutable inputs and verified before their values are trusted.

## 5. Data flow and failure behavior

```text
environment/defaults -> Settings validation -> typed settings or validation error
checked-in versions  -> frozen VersionBundle -> deterministic JSON
CLI arguments        -> argparse dispatch -> existing in-process verifier/auditor -> exit code
Git checkout         -> frozen uv sync -> quality/source gates -> CI result
```

A checksum or frozen-count mismatch remains a stop condition. No command rewrites the manifest, expected audit values, or official workbook/PDF files.

## 6. Test strategy

Every production behavior follows strict red-green-refactor:

1. Settings defaults and invalid top-k relationship
2. Environment-variable parsing
3. Version immutability and deterministic serialization
4. CLI version output and exit codes
5. In-process delegation of both source commands against the real repository tools
6. CI/environment/pre-commit contract where behavior can be executed rather than checked as prose

Each focused test must be observed failing for the expected missing behavior before the smallest implementation is added. Final verification uses every command required by `AGENTS.md` plus the schema catalog check.

## 7. Alternatives rejected

- Core/CLI without CI and environment templates leaves the audited bootstrap gap unresolved.
- Expanding into source ingestion violates the first-incomplete-task boundary.
- Subprocess-based CLI delegation introduces avoidable interpreter/path differences and weakens typed error handling.
- Dynamic registry loading in Task 1 duplicates Phase 2 Task 1 and is unnecessary for a bootstrap version bundle.

## 8. Acceptance criteria

- All declared imports and the `finproof` console entry point work on Python 3.12.
- Settings defaults are evaluation-safe and invalid limits fail validation.
- Version data is immutable and serializes deterministically.
- Three CLI subcommands return meaningful exit codes without subprocess delegation.
- Frozen installation, pre-commit configuration, CI, and `.env.example` are present and consistent.
- Ruff, mypy, pytest, source audit, handoff verification, and schema catalog checks succeed.
- Official inputs and frozen audit values remain byte-identical.
- `STATUS.md` marks only Phase 1 Task 1 complete and names Phase 1 Task 2 as the exact next task.
