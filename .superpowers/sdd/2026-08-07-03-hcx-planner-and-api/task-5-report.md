# Phase 3 Task 5 TDD Report

## Scope

Task 5 only: production dependency composition, Docker/CI contracts, in-process E2E,
dynamic container smoke, bounded load, and short soak. Task 6 closure and frozen/status
documentation were not touched.

## Prerequisites

- `python3 tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes (PyYAML bootstrap note only).
- `python3 tools/audit_source_data.py --check` — PASS: 145,393 rows, snapshot
  `2026-07-11`.

## RED → GREEN ledger

### Production application graph

- RED: `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest
  tests/e2e/test_evaluation_api.py -q`
- Expected/observed RED: `ApiDependencies.__init__()` rejected `http_client_factory`; the
  production orchestrator graph was not wired (`1 failed`).
- GREEN: the same command — `1 passed in 2.48s`.
- Regression: `tests/integration/api/test_answer_endpoint.py` plus E2E — `25 passed`,
  one pre-existing Starlette deprecation warning.

### Container inventory and CI

- RED: `FINPROOF_RUN_DOCKER_SMOKE=1 ... uv run pytest
  tests/contract/test_container_contract.py tests/e2e/test_container_smoke.py -q`
- Expected/observed RED: missing `Dockerfile` and `.dockerignore`, and missing CI jobs —
  `3 failed, 2 skipped`.
- GREEN: `uv run pytest tests/contract/test_container_contract.py -q` — `3 passed`.

### Load-discovered production defect

- Acceptance RED: `FINPROOF_RUN_API_LOAD=1 ... uv run pytest
  tests/performance/test_api_load.py -q -m performance` — a subset of eight concurrent
  requests returned `safe_failure`.
- Diagnostic RED with request logs: all eight HCX calls returned 200; orchestration logs
  identified `database_failure` on concurrent requests.
- Root cause: one application-owned `AnswerService` allowed multiple worker threads to
  interleave result state on one DuckDB connection. Single-request E2E stayed green;
  concurrency alone reproduced the failure.
- Minimal production correction: one per-service lock around the deterministic
  DB/evidence pipeline. No pool or new dependency was added.
- GREEN: the same load command — `1 passed in 4.67s`.
- Regression: AnswerService plus E2E — `5 passed in 1.53s`.

### Short soak

- Acceptance first run: the 30-second traffic loop retained exact contracts, but the
  final concurrency probe was slowed past the 15-second request deadline because
  `tracemalloc` remained enabled during that probe.
- Harness correction: finalize current-allocation growth and stop `tracemalloc`
  immediately after the duration loop; run the permit probe under normal runtime
  overhead.
- Diagnostic GREEN: `FINPROOF_SOAK_SECONDS=1 ...` — `1 passed in 15.17s`.
- Required GREEN: `FINPROOF_SOAK_SECONDS=30 ...` — `1 passed in 34.97s`.
- Covered lookup, ranking, same-grain cross-product, recorded timeout, 429, malformed
  output, rule fallback, final eight-request permit probe, exact response schema, and
  bounded current Python allocation growth.

### Docker dynamic smoke

- Initial build: `docker build -t finproof:phase3 .` — exit 0. A load-discovered
  production correction made that image stale, so the same tag was rebuilt from the
  current candidate.
- Focused permission RED: container exited 3 before bind because the host cache was
  `0700/0600`, so non-root `finproof` could not descriptor-open mounted
  `/app/artifacts/manifest.json`.
- Minimal harness correction: after host current-code expected verification, grant
  read/execute mode only for the read-only bind duration and restore original modes in
  `finally`; content and verification are unchanged.
- Fail-closed GREEN: missing-artifact selector — `1 passed, 1 deselected in 1.89s`.
- Focused Linux RED: after the permission correction, real container startup exited 3
  with `workspace_configure_failed`; `_descriptor_path()` used Darwin-only
  `fcntl.F_GETPATH` while configuring the held DuckDB spill descriptor.
- Minimal production correction: on platforms without `F_GETPATH`, resolve the exact
  held descriptor through `/proc/self/fd/<fd>`. Existing inode/type/mode revalidation
  remains unchanged. Focused GREEN — `1 passed`; related resolution, symlink, and
  changed-identity security cases — `7 passed, 399 deselected`.
- Readiness RED: full host verification and Linux container verification reached the
  listening socket, but `/answer` received `RemoteDisconnected` (`1 failed in
  27:32`). A bound Uvicorn socket precedes completion of the long lifespan check.
- Minimal harness correction: retain the required port wait, then wait for an actual
  `/version` 404 response before the one `/answer` call; no public route was added.
- Focused container diagnostics then proved startup was killed externally: Docker
  state `OOMKilled=true`, exit 137, with a 7.30 GiB peak under the 7.75 GiB VM limit.
  Cgroup evidence (`anon` about 7.48 GiB while `file` was about 11 MiB) rejected an
  initial page-cache hypothesis; that experimental change and its tests were removed.
- Temporary phase markers narrowed the real boundary to `silver_fund_item` batch 0,
  before its completion. The official Parquet metadata is 11,138 rows in one row group
  with 2,597,960,016 uncompressed bytes; whole-batch `to_pylist()` expanded it to the
  OOM peak.
- Focused bounded-row RED: `_iter_bounded_python_rows` was absent (`1 failed`). Minimal
  production correction: retain the frozen Arrow batch and all fidelity/uniqueness
  checks, but materialize Python dictionaries in 256-row slices. Focused GREEN —
  `1 passed`; complete related regression — `407 passed in 6.43s`.
- Final image build exited 0 with manifest-list digest
  `sha256:0ee6563f9a621d1b6a8a61f21af3ae8df5136ec11f9af2b17869577f329cef3e`.
  Rebuilds beyond the planned single build were necessary because load, Linux
  portability, readiness, and real cgroup acceptance exposed production defects; all
  diagnostic-only code was removed before this final image.
- Final container-only startup reached readiness in about 24 minutes with
  `OOMKilled=false`; observed fund peak was 3.35 GiB and the later DB peak 1.96 GiB.
- Official read-only success GREEN: current-code host expected verification, read-only
  mount, bounded readiness, `/answer` schema, and `/version` 404 — `1 passed in
  3432.35s (57:12)`.
- Final fail-closed GREEN, reusing the final image: missing and tampered manifests —
  `2 passed, 1 deselected in 3.23s`.
- Cleanup evidence: no `finproof-task5-*` containers remained, and the host cache was
  restored to directory `0700` / file `0600` modes.
- Fresh-runner CI timeout RED: observed build 94.5 minutes + host verification 57.2
  minutes + container verification about 24 minutes exceeds the original 120-minute
  job timeout; focused contract failed `120 >= 180`.
- Minimal CI correction: only the container job timeout changed to 240 minutes. Focused
  GREEN — `3 passed in 0.07s`; its scoped format/Ruff/mypy checks also passed.

### Independent-review portability correction

- Review finding: the shared official-artifact helper fixed all three cache paths under
  `/private/tmp`, but a fresh Ubuntu runner normally exposes `/tmp` without creating
  `/private/tmp`; artifact initialization requires the selected parent to exist.
- RED: `uv --cache-dir /private/tmp/finproof-uv-cache run pytest -q
  tests/unit/test_official_artifact_subprocess.py` — expected/observed failure:
  `_official_cache_parent` was absent (`1 failed in 0.25s`).
- Minimal correction: one shared helper retains the existing `/private/tmp` parent when
  it is a directory and otherwise uses stdlib `tempfile.gettempdir()`; artifact,
  outcome, and measurement paths all derive from that selected parent. No new config or
  dependency was added.
- GREEN: the same focused command — `1 passed in 0.07s`. Affected helper, container
  contract, and non-dynamic smoke selection — `4 passed, 3 expected skips in 0.08s`.
- Docker smoke was not repeated: the correction changes only the host-side test helper,
  not the image or runtime code, and the deterministic test does not build official
  artifacts.
- Scoped checks after formatting the new test: `ruff format --check` — `2 files already
  formatted`; Ruff — `All checks passed!`; mypy — `Success: no issues found in 2 source
  files`.

## Aggregate and scoped verification

- Task 5 aggregate: `uv run pytest tests/contract/test_container_contract.py
  tests/e2e/test_evaluation_api.py tests/e2e/test_container_smoke.py -q` — `4 passed,
  3 expected dynamic-Docker skips in 1.10s`.
- Scoped format: the first check identified two test files; formatting only those files,
  then repeating `ruff format --check` — `11 files already formatted`.
- Scoped Ruff — `All checks passed!`.
- Scoped mypy — `Success: no issues found in 11 source files`.
- Source audit — `Official source audit PASS: 145,393 rows; snapshot 2026-07-11`.
- Handoff — `FinProof handoff PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes`.
- `git diff --check` — PASS with no output.

## Files

- Production: `src/finproof/api/app.py`, `src/finproof/api/dependencies.py`,
  `src/finproof/data/artifacts/parquet_io.py`, `src/finproof/service/answer_service.py`.
- Container/CI: `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`.
- Tests: `tests/contract/test_container_contract.py`, `tests/e2e/__init__.py`,
  `tests/e2e/test_evaluation_api.py`, `tests/e2e/test_container_smoke.py`,
  `tests/integration/artifacts/test_parquet_verification.py`,
  `tests/performance/test_api_load.py`, `tests/resilience/__init__.py`,
  `tests/resilience/test_api_soak.py`, `tests/unit/test_official_artifact_subprocess.py`.
- Shared test helper: `tests/helpers/official_artifact_subprocess.py`.
- Evidence: this report only. `docs/implementation/STATUS.md`, frozen docs, README,
  API spec, source material, artifacts, and the two untracked PDFs were not changed.

## Self-review

- Production runtime reaches only the fixed-origin `HcxClient`; the shared
  `httpx.AsyncClient` is lifespan-owned and closed. Disabled HCX uses the validated
  rule fallback.
- No cache, Structured Outputs runtime, alternate provider URL, Compose, entrypoint,
  secret/data COPY, or public health/version route was introduced.
- Docker runs as non-root and mounts expected-verified runtime artifacts read-only.
- Linux descriptor fallback retains the caller's exact inode/type/mode revalidation;
  bounded row conversion changes only peak Python materialization, not Arrow limits,
  validation, hashes, uniqueness, or expected comparison.
- Temporary diagnostics and the disproved page-cache experiment are absent from the
  final diff. No Task 5 containers remain and official-cache modes are restored.
- The deliberate session-wide DB serialization ceiling is marked with a `ponytail:`
  comment; per-worker cursors are deferred until measured DB throughput requires them.
- Review backlog only: the load check exercises exactly eight permits, and `tracemalloc`
  excludes native allocations. Neither item was implemented in this correction wave.

## Commit

- Implementation checkpoint: `f5140c6` (`feat: complete phase 3 runtime delivery gate`).
- Evidence/report follow-up: this report-only commit; its final hash is included in the handoff.
- Independent-review portability correction: this correction/report commit; its final
  hash is included in the handoff.
