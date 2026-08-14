# Phase 1 Task 5 Artifact Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, verify, and safely publish the reproducible Phase 1 Bronze/Silver/Gold Parquet and self-contained DuckDB artifact set, then freeze its independently reviewed timestamp-free logical contract.

**Architecture:** An offline builder verifies the exact nine logical inputs, streams verified workbooks through bounded external staging, writes eleven frozen Parquet tables and two semantic reports, materializes the same typed content into DuckDB, and verifies every logical and physical boundary before guarded publication. Operational timestamps and physical hashes prove one generation's provenance and integrity; canonical table/report/manifest hashes plus the separately packaged expected contract prove logical reproducibility across builds.

**Tech Stack:** Python 3.12, Pydantic 2, PyArrow/Parquet, DuckDB 1.5, Polars where already used, JSON Schema Draft 2020-12 with `FormatChecker`, PyYAML, pytest, Ruff, mypy, uv/Hatch.

## Global Constraints

- Governing authority is `docs/superpowers/specs/2026-08-14-phase1-task5-artifact-build-design.md`, D-014, D-017, D-021, D-022, and D-023. Stop and log any conflict instead of reconciling it in code.
- Official source files, `source_material/input_manifest.json`, `source_material/schema_catalog.json`, and `tests/contracts/expected_source_audit.json` are immutable. Snapshot date is exactly `2026-07-11`.
- Task 5 creates exactly three Bronze, six Silver, and two Gold logical tables. It creates no metric, family, eligibility/state, alias/fuzzy, search, runtime-evidence, QueryPlan, API, HCX, or release behavior.
- Public funds are persisted at `fund_item` and `fund_attribute` grains. Artifact construction orders staged canonical `SourceRow` payloads and collapses one complete item group at a time; it never calls `normalize_public_funds` on all 95,619 rows.
- The only automatic cross-source rule compares the exact untrimmed domestic ETF `pd_itm_no` raw value with the representative public-fund `ksd_itm_no` raw value. Trimming is acceptance evidence only.
- One caller-injected timezone-aware UTC timestamp is used for manifest persistence, every Bronze `loaded_at`, and every persisted D-021 `first_detected_at`. The builder never reads the clock.
- Runtime files under `artifacts/` and all recognized sibling lock/stage/backup/cleanup transients remain ignored and untracked.
- `config/expected_phase1_artifacts.json` must not exist during Checkpoints 1-7. It is created only in Checkpoint 8 after two independently verified official candidate builds and a fresh candidate-contract review.
- The candidate interface stays in repository tooling, is absent from `finproof.__init__`, package exports, project scripts, and the runtime wheel, never publishes, never writes the expected contract, and permanently refuses once either expected-contract source or packaged resource exists.
- Every behavior change follows focused RED -> observed expected failure -> smallest GREEN -> focused/regression gates -> commit -> fresh independent review. A review correction begins with its own focused RED and receives a separate correction commit and re-review.
- A parameterized trust-boundary family proves RED only when the same run reaches every parameter ID and every case fails for the intended missing behavior; one early exception or one first failing parameter does not prove the remaining cases. Split unrelated assertions into named selectors so operation IDs, printable basenames, immutable internal context, each ordered expected-contract family, and each path-safety case cannot mask one another.
- Every newly created `tests/source_contract/test_*.py` declares module-level `pytestmark = pytest.mark.source_contract`; every newly created `tests/performance/test_*.py` declares `pytestmark = pytest.mark.performance`. Directory naming, command-line selection, or conftest inference does not substitute for the explicit file mark.
- After any checkpoint changes a root file or destination mapping covered by Hatch `force-include`, the active standard-editable distribution data is presumed stale. Every pre-refresh legacy/stale RED selector must run through `uv run --no-sync` so uv cannot auto-sync/rebuild the editable copy before the failure is observed. Then, before any resource equality GREEN gate or commit, run exactly `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups --reinstall-package finproof` and rerun the active-editable outside-CWD byte/SHA selector with ordinary `uv run`. A plain `uv sync`, a fresh isolated editable alone, a wheel-only test, or a pre-refresh `uv run` without `--no-sync` does not satisfy this refresh rule.
- Use an isolated Task 5 worktree created with `superpowers:using-git-worktrees`. Run `python3 tools/verify_handoff.py` and `python3 tools/audit_source_data.py --check` before the first production edit.
- Use `UV_CACHE_DIR=/private/tmp/finproof-uv-cache` for uv commands and `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache` for pre-commit. No command may write under `source_material/`.

## File responsibility map

Create these focused production modules under `src/finproof/data/artifacts/`:

- `errors.py`: closed `ArtifactErrorCode` and bounded `ArtifactContractError`.
- `safe_files.py`: one descriptor-relative, no-follow regular-file reader used by the config, expected-contract, and filesystem-backed resource trust boundaries. It records `(st_dev, st_ino, file type)` for every opened ancestor and leaf, holds the entire descriptor chain through the read, re-stats every child name relative to its held parent after the read, compares every recorded identity/type, and closes descriptors in reverse order on every path. If descriptor-relative open, directory/no-follow flags, or identity revalidation are unavailable, it fails closed rather than using a lexical/precheck fallback.
- `config.py`: strict immutable `ArtifactBuildConfig` and exact production baseline loader.
- `resources.py`: checkout-independent closed runtime-resource loader: installed-wheel `importlib.resources` primary plus the one standard-editable `importlib.metadata.distribution("finproof").locate_file(...)` fallback required by the frozen destinations.
- `expected_contract.py`: strict timestamp-free expected-contract model, loader, and exhaustive comparator.
- `hashing.py`: canonical scalar/JSON/row/schema/table/report/manifest hash primitives.
- `manifest.py`: strict manifest models, JSON-schema load, recursive inventory verification, and `VerifiedArtifactSet`.
- `table_specs.py`: the sole frozen eleven-table schema/name/type/key/path registry.
- `serialization.py`: exact strict-model `record_json`, wide projections, Bronze/quality/Gold row projections.
- `parquet_io.py`: fixed-schema incremental writer and reopened Parquet verifier.
- `staging.py`: one-thread/1-GiB bounded DuckDB staging, spill ownership, ordering, and cleanup.
- `bronze.py`: source-catalog/row/cell emission and source-audit observations.
- `silver.py`: non-fund normalization staging and one-item-at-a-time public-fund collapse.
- `quality_persistence.py`: D-021 timestamp injection, schema validation, and Bronze joins.
- `reports.py`: strict source-audit and quality-summary contracts and semantic hashes.
- `links.py`: exact link/evidence models, raw join, conflicts, pair hash, and bidirectional evidence checks.
- `database.py`: self-contained DuckDB construction, read-only open, and bounded typed `EXCEPT ALL` verification.
- `publication.py`: lock/marker ownership, guarded rename/rollback, tombstone cleanup, and remnant recovery.
- `builder.py`: build-session orchestration and the public `build_artifacts` boundary; no domain rule is reimplemented here.

Create `src/finproof/resources/__init__.py` only as the stable resource anchor. Hatch force-includes root schema bytes beneath `finproof/resources/schemas/`; Checkpoint 8 additionally force-includes the reviewed expected contract beneath `finproof/resources/contracts/`. The loader accepts no caller path: it selects one exact frozen destination, tries the installed-wheel `importlib.resources` route first, and only when a regular `src/finproof` package shadows standard-editable distribution data uses `importlib.metadata.distribution("finproof").locate_file(exact_destination)`. No dev-mode-exact install workaround is allowed.

Repository-only `tools/build_candidate_artifacts.py` owns the unpublished candidate wrapper. Shared deterministic artifact fixtures live in `tests/helpers/artifacts.py`; test-only fault-injection filesystem wrappers live in `tests/helpers/artifact_filesystem.py`, never in production.

## Checkpoint execution rule

For every checkpoint below:

1. Select exactly one named behavior, or one coherent parameter family exercising the same behavior, and add only its focused test. Run one explicit node selector such as `test_file.py::test_name` and record the expected behavioral RED. Do not author multiple independent tests in a batch.
2. If that selector first stops at a missing import/symbol, add only the minimum non-behavioral skeleton, rerun the same selector, and record the narrower assertion/error proving the behavior is still absent before substantive implementation.
3. Implement the smallest GREEN for that one selector, rerun it, then run its immediately related focused regression. Only after both are green may the next named behavior/parameter family be authored. A combined missing-import RED never authorizes bulk implementation of the rest of a checkpoint.
4. Treat every multi-file/multi-test command printed later in this plan as an aggregate GREEN/regression gate only, never as RED evidence. This serial selector loop applies to CP1-CP8 and every CP7A/7B/7C behavior, even where a step heading summarizes several REDs.
5. Keep checkpoint edits uncommitted through all of its serial selector loops, then run the checkpoint aggregate focused gate and unchanged Task 1-4 regression command.
6. Run `git diff --check` and inspect `git diff --stat` for out-of-scope files.
7. Commit only the listed files with the listed commit subject.
8. Dispatch a fresh independent reviewer against the checkpoint commit and the approved design. The review report must state Critical/Important/Minor counts.
9. If Critical or Important is nonzero, add one focused regression selector that fails for the finding, record its expected failure, make the smallest correction, rerun that selector and checkpoint gate, commit `fix: close Task 5 checkpoint N review gaps`, and obtain a new 0 Critical / 0 Important review before starting the next checkpoint.

For status/review evidence, record every selector, its observed expected failure reason, the corresponding smallest-GREEN selector result, and the later aggregate commands separately. Never cite an aggregate collection failure as proof that each independent behavior was test-driven.

For Checkpoint 1 specifically, the following skeletons are mandatory so a missing import can never be followed directly by completed behavior: the options model initially lacks the UTC validator; the config loader initially parses the valid fixture but performs no frozen-value/type enforcement; the comparator initially returns without comparing; the logical-input resolver initially returns an empty tuple; the registry validator initially returns without checking; and the candidate guard initially returns for every probe state. Each same selector must then produce its narrower behavioral RED before its validator/comparison/inventory/refusal logic is added. Settings path validation must not disable ambient dotenv loading; the conflicting-dotenv selector first proves that CWD input still changes Settings, then `env_file=None` is the only GREEN change. Existing explicit-initializer and process-environment precedence selectors are labeled regression/acceptance and may be first-GREEN because they preserve pre-Task-5 behavior; they are not cited as new-behavior TDD evidence.

The unchanged Task 1-4 regression command is:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/core tests/unit/domain tests/unit/registry \
  tests/unit/data/normalization tests/contract/test_quality_issue_schema.py -q
```

---

### Checkpoint 1: Safe build foundations and unpublished baseline bootstrap boundary

**Files:**

- Modify: `src/finproof/core/settings.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.env.example`
- Modify: `.gitignore`
- Create: `config/artifact_build.yaml`
- Create: `src/finproof/data/artifacts/__init__.py`
- Create: `src/finproof/data/artifacts/errors.py`
- Create: `src/finproof/data/artifacts/safe_files.py`
- Create: `src/finproof/data/artifacts/config.py`
- Create: `src/finproof/data/artifacts/resources.py`
- Create: `src/finproof/data/artifacts/expected_contract.py`
- Create: `src/finproof/resources/__init__.py`
- Create: `tools/build_candidate_artifacts.py`
- Create: `tests/helpers/artifacts.py`
- Create: `tests/unit/core/test_artifact_settings.py`
- Create: `tests/unit/data/artifacts/__init__.py`
- Create: `tests/unit/data/artifacts/test_foundations.py`
- Create: `tests/contract/test_artifact_resources.py`

**Interfaces:**

- Produces: `Settings.repository_root`, `source_root`, `artifact_build_config_path`, and `expected_artifact_contract_path`, all resolved once against one explicit repository anchor.
- Freezes `Settings` with implicit dotenv loading disabled (`env_file=None`): configuration comes only from explicit initialization and `FINPROOF_*` process environment variables. `.env.example` is names/documentation for a user to source explicitly, never an ambient CWD-dependent input.
- Produces: `ArtifactBuildOptions(clean: bool = False, persistence_timestamp: datetime)` as a strict frozen model.
- Produces: `ArtifactBuildConfig.load(path: Path, *, repository_root: Path, versions: VersionBundle) -> ArtifactBuildConfig`. The config and every nested public Pydantic model use `ConfigDict(strict=True, frozen=True, extra="forbid")`; YAML scalar coercion is never part of the baseline contract.
- Produces: `resolve_logical_inputs(settings: Settings) -> tuple[ResolvedArtifactInput, ...]` with the exact closed nine-entry namespace/path/kind order; it canonicalizes paths without hashing them, while the builder reopens/re-hashes every entry immediately before ingestion.
- Produces: `validate_build_registry_versions(settings: Settings, versions: VersionBundle) -> None`, requiring datasets snapshot `2026-07-11` and exact dataset/quality/rating/state versions before source ingestion.
- Produces: `ArtifactContractError(code: ArtifactErrorCode, *, operation_id: str, target_basename: str | None = None, published: bool = False, internal_context: Mapping[str, str] | None = None)` with bounded `safe_message`. `operation_id` must be an exact `str` of 1-128 ASCII code points matching `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`; non-strings, non-ASCII, leading punctuation, whitespace/control/path characters, and 129+ code points are refused. Runtime validation requires exact-string context keys/values and copies them into an immutable mapping. The public basename must be an exact `str` of 1-128 Unicode code points, must pass `str.isprintable()`, must be neither `.` nor `..`, and contains no slash/backslash; C0/C1, CR/LF, U+2028/U+2029, bidi/format controls, separators, ANSI escapes, and 129+ code points are refused.
- Produces the exact read-only `ArtifactLogicalContractView(Protocol)` owned by `expected_contract.py`, with properties for artifact contract/set/dataset identities, the ordered exact-nine logical-input contract entries, ordered exact-eleven table schema/count/sort/unique/logical-hash entries, ordered two semantic report-ID/hash entries, overall manifest logical hash, link pair hash, and evidence count. Its property types are the strict expected-contract entry models defined in the same CP1 module; it contains no path, timestamp, physical hash, database bytes, or forward reference to later manifest types.
- Produces: `ExpectedPhase1ArtifactContract.load(path: Path) -> ExpectedPhase1ArtifactContract` and `compare_expected_artifact_contract(actual: ArtifactLogicalContractView, expected: ExpectedPhase1ArtifactContract) -> None`; the expected dataset version is exactly `2026-07-11`, the loader rejects every symlink path component and reads through a held no-follow descriptor chain with identity checks, and the comparator first reconstructs the complete actual structural payload through the same strict JSON model before comparing. Thus `bool`/`int`, wrong nested scalar/container types, missing properties, and reordered inventories fail as `invalid_actual_contract`. Checkpoint 7's `VerifiedArtifactSet` structurally conforms to this CP1-owned protocol.
- Produces closed `RuntimeArtifactResource(StrEnum)` values for exactly `finproof/resources/schemas/artifact_manifest.schema.json`, `finproof/resources/schemas/quality_issue.schema.json`, and, only after Checkpoint 8, `finproof/resources/contracts/expected_phase1_artifacts.json`; no public or internal loader accepts a caller-supplied path.
- Produces: `artifact_manifest_schema_bytes() -> bytes`, `quality_issue_schema_bytes() -> bytes`, and, only after Checkpoint 8, `expected_phase1_contract_bytes() -> bytes`. Each calls one internal closed loader that uses `importlib.resources` as the installed-wheel primary. Its sole fallback calls `importlib.metadata.distribution("finproof").locate_file(exact_frozen_destination)` for standard Hatch editable shadowing, then requires that the distribution-relative destination is unchanged, every existing component from the distribution root through the destination is nonsymlink, and the leaf is an existing regular file opened through a held no-follow descriptor with before/opened/after identity checks. Neither route uses CWD, repository/source parent discovery, caller paths, or a path search.
- Produces internal `CandidateBaselineProbe(Protocol)` with `source_exists() -> bool`, `resource_exists() -> bool`, and `second_check() -> None`, plus a production probe that checks the real repository expected source and packaged expected resource without exposing their paths. CP1's repository-only `assert_candidate_bootstrap_allowed(probe: CandidateBaselineProbe) -> None` performs only the initial absent/source-present/resource-present guard; Checkpoint 7's actual wrapper owns the post-transform `second_check` race boundary.

- [ ] **Step 1: Establish clean preconditions and prove the official baseline is absent**

Run:

```bash
python3 tools/verify_handoff.py
python3 tools/audit_source_data.py --check
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
git status --short
```

Expected: handoff reports 61 required files, 9 official inputs, and 41,384,928 bytes; source audit reports 145,393 rows at `2026-07-11`; both expected-contract paths are absent; only the approved Task 5 plan commit is present before implementation starts.

- [ ] **Step 2: Write focused REDs for repository anchoring, path safety, options, and safe errors**

Introduce the named tests below one selector/one behavior at a time under the global execution rule; the command at the end of the step is only their aggregate gate.

In `tests/unit/core/test_artifact_settings.py`, add named cases that assert:

```python
def test_build_paths_are_resolved_once_against_repository_root(tmp_path: Path) -> None:
    settings = Settings(repository_root=tmp_path)
    assert settings.source_root == tmp_path / "source_material"
    assert settings.data_dir == tmp_path / "source_material/data"
    assert settings.artifact_dir == tmp_path / "artifacts"
    assert settings.database_path == tmp_path / "artifacts/finproof.duckdb"


def test_build_settings_require_the_exact_database_location(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="finproof.duckdb"):
        Settings(repository_root=tmp_path, database_path=tmp_path / "other.duckdb")
```

Use one authoritative Settings family that first exercises valid default path resolution and the shown database invariant, then reaches separate case IDs for artifact root equal to repository/filesystem/home, inside source root, a symlink component at every build-path field (including `data_dir` itself), database outside artifact root or with the wrong basename inside it, `data_dir` other than `source_root/data`, source/config paths outside their declared namespace, and every equality among source root, artifact root, and database path. After a fields-only skeleton, the same family must report every invalid case ID as accepted rather than stopping at the first construction; then one path validator makes the family GREEN. The two shown named snippets are acceptance assertions inside/after this authoritative family, not separate new-behavior RED claims. In the same resolution family, instantiate equivalent relative and absolute Settings paths from two CWDs without dotenv files and assert the resolved Settings path fields are identical. Do not assert logical namespace serialization here; the Step 4 exact-nine resolver family owns that later behavior.

The same Settings family must include a nonexistent `repository_root`, a regular-file `repository_root`, a regular-file `source_root`, and a regular-file `repository_root/config` ancestor. Require the repository anchor and every existing source/config ancestor to be a directory before any `resolve(strict=False)` canonicalization can erase its original shape. Every new case ID must be observed RED in the same reached-all-IDs run before the validator is hardened. Do not set `env_file=None` during this family; the later conflicting-dotenv selector owns that behavior's RED and one-line GREEN.

Create two unrelated CWDs, each with a conflicting `.env` that tries to change repository/source/artifact/config/expected paths. Instantiate identical explicit `Settings` from each CWD and assert every resolved Settings path value remains identical and neither `.env` value appears. In separate selectors, preserve the existing explicit-initializer precedence and `FINPROOF_*` process-environment override behavior. The `.env.example` selector is also regression/acceptance evidence rather than a new behavior: assert it is never opened automatically and a value becomes active only when the caller explicitly exports/sources it into the process environment. None of these preserved-behavior selectors is cited as RED evidence.

In `tests/unit/data/artifacts/test_foundations.py`, add the options selector below. Use the shown safe-message selector as the first coherent error behavior: give it very long internal path/raw-payload values, require exact string `artifact error unsafe_target for artifacts (op-0123456789abcdef)`, require `str(error) == error.safe_message`, exclude every context key/value substring, and require length at most 512. After a missing-symbol skeleton, rerun it to the narrower missing/unsafe `safe_message` behavioral RED before implementing rendering. The length bound is an acceptance consequence of the exact format plus already bounded public fields. Then add three separate validation selectors so no earlier assertion masks another: one parameterized selector for non-string, empty, leading hyphen/underscore, whitespace, slash/backslash, NUL/C0/C1, non-ASCII, and 129-code-point operation IDs while proving 1- and 128-character regex-matching boundary values succeed; one parameterized selector for non-string/empty/dot/dot-dot, path separators, C0/C1/CR/LF/U+2028/U+2029/ANSI/bidi/format/non-printable, and 129-code-point basenames while proving printable 1- and 128-code-point boundary values succeed; and one for exact-string-only copied immutable `internal_context` that rejects non-string keys/values and nested mutable values. Every invalid parameter ID must be reached in the same RED run.

```python
def test_options_require_one_aware_utc_timestamp() -> None:
    kst = timezone(timedelta(hours=9))
    with pytest.raises(ValidationError):
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 14, 1, 2, 3))
    with pytest.raises(ValidationError):
        ArtifactBuildOptions(
            persistence_timestamp=datetime(2026, 8, 14, 10, 2, 3, tzinfo=kst)
        )
    options = ArtifactBuildOptions(
        persistence_timestamp=datetime(2026, 8, 14, 1, 2, 3, 456789, tzinfo=timezone.utc)
    )
    assert options.persistence_timestamp.isoformat().endswith("+00:00")


def test_artifact_error_safe_message_never_exposes_parent_paths(tmp_path: Path) -> None:
    error = ArtifactContractError(
        ArtifactErrorCode.UNSAFE_TARGET,
        operation_id="op-0123456789abcdef",
        target_basename="artifacts",
        internal_context={
            "stage": str(tmp_path / "private/stage") * 256,
            "raw": "untrusted-payload" * 256,
        },
    )
    assert error.safe_message == (
        "artifact error unsafe_target for artifacts (op-0123456789abcdef)"
    )
    assert str(error) == error.safe_message
    assert "private" not in error.safe_message
    assert "stage" not in error.safe_message
    assert "raw" not in error.safe_message
    assert "untrusted-payload" not in error.safe_message
    assert len(error.safe_message) <= 512
```

For each selector above, run its exact node ID and observe RED before its smallest GREEN. Only after all Step 2 loops are green, run this aggregate regression gate:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/core/test_artifact_settings.py \
  tests/unit/data/artifacts/test_foundations.py -q
```

Expected aggregate GREEN. The execution report records the earlier per-selector RED reasons (`Settings` rejects the new keyword fields and the artifact options/error symbols are missing or behaviorally permissive) separately; this multi-file command is never RED evidence.

- [ ] **Step 3: Confirm the accumulated serial settings/options/error boundary**

The implementations described here are the accumulated results of Step 2's completed selector-by-selector RED/GREEN loops, not a later bulk production step. Add the four Settings fields with the exact defaults from the approved design and a single model validator that resolves `repository_root` once, validates existing source/config ancestors without following symlinks, validates lexical containment, and assigns the resolved absolute paths. Set the Pydantic settings source configuration to `env_file=None`; accept only explicit initialization plus the existing `FINPROOF_*` process-environment source, independent of CWD. Preserve existing Settings defaults, environment precedence, and query consumers, but do not preserve an invalid path fixture or invent a query-only exception inside this shared model: every construction must satisfy `data_dir == source_root / "data"`. Update the existing frozen-default test fixture to pass a matching explicit `source_root`/`data_dir` pair while leaving its assertions unchanged.

Define the closed codes used by all later checkpoints:

```python
class ArtifactErrorCode(StrEnum):
    INVALID_SETTINGS = "invalid_settings"
    UNSAFE_TARGET = "unsafe_target"
    EXISTING_TARGET = "existing_target"
    UNRECOGNIZED_TARGET = "unrecognized_target"
    UNRECOGNIZED_ORPHAN_STAGE = "unrecognized_orphan_stage"
    MANIFEST_INVALID = "manifest_invalid"
    SCHEMA_INVALID = "schema_invalid"
    CONFIG_INVALID = "config_invalid"
    SERIALIZATION_FAILED = "serialization_failed"
    ROW_COUNT_MISMATCH = "row_count_mismatch"
    TABLE_SCHEMA_MISMATCH = "table_schema_mismatch"
    SORT_KEY_MISMATCH = "sort_key_mismatch"
    UNIQUE_KEY_MISMATCH = "unique_key_mismatch"
    EXACT_LINK_CONFLICT = "exact_link_conflict"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    DATABASE_VALIDATION_FAILED = "database_validation_failed"
    REPRODUCIBILITY_MISMATCH = "reproducibility_mismatch"
    LOGICAL_HASH_MISMATCH = "logical_hash_mismatch"
    REPORT_MISMATCH = "report_mismatch"
    TIMESTAMP_MISMATCH = "timestamp_mismatch"
    EXACT_TREE_MISMATCH = "exact_tree_mismatch"
    LOCK_HELD = "lock_held"
    STAGING_CLEANUP_FAILED = "staging_cleanup_failed"
    PUBLICATION_ROLLBACK_FAILED = "publication_rollback_failed"
    BACKUP_CLEANUP_FAILED_AFTER_PUBLISH = "backup_cleanup_failed_after_publish"
    BASELINE_MISSING = "baseline_missing"
    BASELINE_ALREADY_EXISTS = "baseline_already_exists"
```

`ArtifactContractError.__str__` returns `safe_message`; after exact runtime key/value validation, `internal_context` is copied into an immutable string-to-string mapping for access-controlled logs and never rendered. `target_basename` must pass `str.isprintable()`, contain no path separator, and remain one line. Normalize the UTC options timestamp only for JSON output; do not call `datetime.now` in this model or module.

Cap `safe_message` at 512 Unicode code points. Validate the operation ID as an opaque bounded token and never derive it from a source path or raw data value.

- [ ] **Step 4: Write REDs for the exact artifact config, expected model, packaged schemas, and candidate refusal**

Add tests that require `config/artifact_build.yaml` to declare version `1.0.0`, the exact four source table row/column/cell counts, the five Silver counts, two quarantine rows, 47 links, 371 evidence rows, the exact pair hash, Parquet options, writer batch maximum 65,536, and staging `threads=1`/`memory_limit=1GiB`. `ArtifactBuildConfig.load` accepts only the exact `repository_root/config/artifact_build.yaml`; its independently supplied anchor is an existing nonsymlink directory and the config is read through the shared held no-follow descriptor chain. First parameterize a nonexistent repository root, regular-file root, symlink root, outside-root byte-identical file, leaf symlink alias, and intermediate-parent swap performed after validation but before leaf open; all must RED against the permissive loader before the anchored reader is implemented. Mutation fixtures must create a complete synthetic `repository_root/config/artifact_build.yaml` and edit that exact file rather than passing an unrelated temp path. Then mutate every version/count/hash and add unknown/duplicate YAML keys; each load must fail closed.

After the exact-value family is GREEN but before strict model implementation, add one coherent YAML scalar-type family that quotes an integer count, quotes `threads`, encodes `statistics` as integer `1`, and quotes the dataset date. Require every case ID to RED because the permissive loader coerces it into the expected Python value, then set `strict=True` on `ArtifactBuildConfig` and every nested model and rerun every ID GREEN. Do not cite a wrong value as proof of a wrong type.

Assert `resolve_logical_inputs` returns exactly the nine source-root/repository entries from Section 2.1 in namespace-rank/POSIX-path order. Reject a tenth/missing/duplicate entry, repeated namespace directory, absolute/empty/dot/dot-dot/backslash/NUL/percent alias, out-of-namespace path, symlink component, kind mismatch, and CWD-dependent spelling.

Mutate the top-level `version` of datasets/quality/rating/state, the datasets snapshot, `VersionBundle.dataset_version`, and each corresponding VersionBundle rule field. `validate_build_registry_versions` must reject each before any workbook descriptor is opened. Use duplicate-key-rejecting YAML parsing for these trust-boundary fields; do not invent Task 5 policy models for their deferred rule bodies.

Construct a synthetic `ExpectedPhase1ArtifactContract` fixture with dataset version exactly `2026-07-11`. Use separate focused selectors, each observed RED before its implementation, for strict extra-field rejection; wrong dataset date; each of input/table/report ordering; top-level and nested deep immutability; all deterministic difference paths; a missing structural property; and strict actual-payload validation. Reorder fixtures must remain exact tuples—use `tuple(reversed(...))`—so the model reaches the ordering validator rather than failing early with `tuple_type`. The strict-actual selector parameterizes `bool` in every integer position plus wrong nested scalar/container types and requires every case to raise `ArtifactErrorCode.REPRODUCIBILITY_MISMATCH` with the fixed internal reason `invalid_actual_contract`; this reason is not a new error-code member, and Python equality is never the validation boundary. The synthetic contract contains no timestamp, output path, size, or physical hash. Add loader selectors whose file itself is regular but whose parent directory is a symlink, and whose validated intermediate parent is atomically replaced by a symlink before the leaf open; both must RED against this loader's initial unsafe implementation before the loader delegates to the already RED-driven shared held-dirfd reader. A leaf-only `O_NOFOLLOW` plus pre-open component `lstat` is insufficient.

Separately, before enabling strict expected models, exercise direct Python construction/model validation with `bool` or string values in every integer family, a dataset string in place of `date`, and wrong nested scalar/container types. Every parameter ID must first RED by being coerced or accepted. Then apply `ConfigDict(strict=True, frozen=True, extra="forbid")` to `ExpectedLogicalInput`, `ExpectedLogicalTable`, `ExpectedSemanticReport`, and `ExpectedPhase1ArtifactContract`. The JSON loader still uses `model_validate_json(..., strict=True)` so the canonical JSON date string remains the one allowed JSON representation; direct Python coercion remains forbidden.

In `tests/contract/test_artifact_resources.py`, freeze this exact resource TDD order; do not collapse it into one loader/dependency change:

1. Before any Hatch force-include exists, add `test_built_wheel_archive_contains_exact_schema_sources` that inspects the wheel ZIP directly and requires the two frozen schema destinations, exact root bytes/SHA, and absence of expected contract/candidate tooling. Observe the missing-resource RED, add only the two schema force-includes, rebuild, and make this selector GREEN.
2. With force-includes already GREEN, add a primary-loader unit selector that supplies an installed-wheel-shaped `importlib.resources` Traversable and makes the metadata fallback raise if touched. Observe the missing public-loader RED, then implement only `is_file() == True` reading plus the both-predicates-false missing case and make this selector GREEN. Do not use the active editable environment for this primary-only unit because its regular `src/finproof` package shadows force-included distribution data. Next add a separate generic-Traversable directory selector: `is_file() == False` and `is_dir() == True` must behaviorally RED by being treated as missing, then add only the typed fail-closed directory branch and make it GREEN without touching editable fallback.
3. Add four forged-resource operations (primary read, primary exists, editable read, editable exists) as one parameterized family and require all four IDs to RED before the enum guard is implemented. Then add one private valid-editable primitive selector with a synthetic distribution root, exact frozen destination, nonsymlink directory chain, and regular schema leaf; observe the internal primitive is missing, implement only an initially simple `_editable_candidate` plus `_editable_read`/`_editable_exists`, and make that selector GREEN without wiring it into the public primary-only dispatcher. Add a filesystem-Path primary unsafe family containing only cases the permissive adapter still mishandles—leaf symlink, static intermediate symlink, and special-file-as-missing—and require those IDs RED; generic Traversable directory and ordinary missing are already-driven regressions, not new RED evidence. Make the unsafe IDs GREEN with only a component-`lstat`/leaf-`O_NOFOLLOW` helper and rerun the earlier directory/missing regressions. Add the editable unsafe family with wrong destination, leaf/static-intermediate symlink, directory, and FIFO/special shape; FIFO/special probes use exists/stat or a controlled nonblocking fake and never call blocking `read_bytes()` on a live FIFO. Add a separate missing-leaf selector that must RED as a raw/untyped failure because the minimal valid primitive is forbidden from implementing missing handling early. Make the reached unsafe IDs and missing selector GREEN through that same still-racy helper. Only now add one two-case parent-swap race family covering filesystem-backed primary and editable adapters; both IDs must RED by reading external bytes. Replace the helper by delegating both adapters to `safe_files.py`, rerun both race IDs GREEN, then rerun every static family as regression before authoring the runtime-dependency selector. The shared reader opens and retains each ancestor directory descriptor, resolves the next component with `dir_fd` plus no-follow flags, records every component identity/type, re-stats every child through its held parent after the read, and closes in reverse order; comparing `abspath` strings, prechecking components, and holding only the leaf descriptor is insufficient.
4. Add `test_artifact_runtime_dependencies_are_declared` before moving dependencies. Observe its own metadata RED, then move `jsonschema`, `rfc3339-validator`, and `pyarrow` and update the lock.
5. Add `test_runtime_schema_resources_equal_repository_bytes` in the active editable environment while the public dispatcher is still primary-only. Observe the missing-primary/public-dispatch behavioral RED, wire only the already RED-driven and hardened private editable primitive into the public missing-primary branch, reinstall the active editable distribution, and make it GREEN. The fresh standard-editable selector then proves the same fallback from an unrelated CWD. Do not add or weaken filesystem behavior in this step; that behavior was independently driven by Step 3.
6. Only after the lower-level behaviors above are RED-driven may the real installed-wheel primary-only selector be first-GREEN as an integration/acceptance proof; its report may not cite a dependency failure as a wheel-resource RED.

The public loader selector asserts:

```python
def test_runtime_schema_resources_equal_repository_bytes() -> None:
    assert artifact_manifest_schema_bytes() == (ROOT / "schemas/artifact_manifest.schema.json").read_bytes()
    assert quality_issue_schema_bytes() == (ROOT / "schemas/quality_issue.schema.json").read_bytes()


def test_candidate_builder_is_not_packaged_or_registered() -> None:
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert set(scripts) == {"finproof"}
    assert not hasattr(finproof, "build_candidate_artifacts")
```

Add the named selector `test_standard_editable_schema_loader_uses_distribution_fallback_when_src_shadows`. It must create a fresh isolated venv under `mktemp -d`, perform a normal PEP 660 editable install with runtime dependencies (`uv pip install --python <venv-python> -e .`, never Hatch `dev-mode-exact`), change the subprocess to an unrelated CWD containing conflicting `finproof/resources/...` lookalikes, and prove the regular `src/finproof` package shadows the copied distribution data. In that real shadowed state, assert the public loaders return bytes and SHA-256 values equal to both root schemas through `importlib.metadata.distribution("finproof").locate_file` at the exact two frozen distribution-relative destinations. Assert each located file is existing/nonsymlink/regular, the candidate tool/export and expected-contract resource are absent, and changing CWD cannot change the result.

Add `test_active_standard_editable_schema_loader_matches_current_repository_sources_outside_cwd`. It runs in the active uv environment from an unrelated CWD, proves `finproof` resolves to the regular `src/` editable package while both primary resource paths are shadowed, and asserts the metadata-fallback bytes and SHA-256 equal the current two repository schema sources. This is the reusable stale-copy sentinel required immediately after every later force-included schema edit.

Add the named acceptance selector `test_built_wheel_schema_loader_uses_importlib_resources_primary`. Build/install the already inventory-proven wheel into another isolated venv, run outside the checkout, and assert exact wheel inventory contains the two frozen schema destinations but neither candidate tooling nor expected contract. Make any call to the metadata fallback raise, then prove both public loaders still read via `importlib.resources` and match repository source bytes/SHA-256. Parameterize the internal fallback boundary separately for a wrong destination, missing file, symlink, directory, FIFO/special file, and a distribution object that returns a different relative path; every case fails closed without CWD, parent, glob, or caller-path fallback.

Add permanently hermetic candidate-guard unit tests using a synthetic `CandidateBaselineProbe`: both absent is allowed; source present, resource present, and both present are refused. Assert the production probe/tool remains unpackaged and unexported, but do not create an output/transformation API or claim the second pre-output race check at CP1.

Add a synthetic class that structurally implements every `ArtifactLogicalContractView` property and prove the comparator exhaustively accepts it against an equal strict expected model. Remove one property or change each ordered entry family in focused parameter cases and require mypy/runtime comparison to fail at the CP1 boundary. Assert neither the protocol annotations nor comparator import `manifest.py`, `VerifiedArtifactSet`, or any alternate later-checkpoint result protocol.

For config, first add only the valid exact-baseline selector, observe its missing/skeleton RED, and implement a permissive typed loader sufficient for that valid file. Next run the six-case repository-anchor/path/race family (nonexistent, regular-file, and symlink roots; outside-root file; leaf symlink; parent swap) RED and wire only the exact anchored held-dirfd read GREEN. Then add the complete 43-case mutation family, require all 43 IDs to fail because the permissive loader accepts each mutation, add the exact frozen-value validator and make all 43 GREEN, and finally run the separate YAML scalar-type coercion family RED before strict model GREEN. Follow the same serial pattern for every remaining expected/resource/candidate selector. After all Step 4 loops are GREEN, run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_foundations.py \
  tests/contract/test_artifact_resources.py -q
```

Expected aggregate GREEN. The earlier exact selectors separately record the missing config/model/protocol/guard, wheel inventory, primary loader, editable fallback, and runtime-dependency REDs; this multi-file command is never RED evidence.

- [ ] **Step 5: Finish the serial foundations and synchronize their assembled dependency/resource state**

The implementations named here are the accumulated results of the Step 2/Step 4 serial selector loops, not authorization for one bulk change. Use a duplicate-key-rejecting YAML loader and strict frozen Pydantic models. Encode the exact production config values from the approved design, including source rows `42_394/1_734/5_646/95_619`, source columns `40/73/49/45`, source cells `1_695_760/126_582/276_654/4_302_855`, Silver counts `42_394/1_733/5_646/11_138/95_618`, quarantine rows `2`, links `47`, evidence `371`, and pair SHA-256 `8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962`. The coherent exhaustive config selector must show every one of its 43 parameter IDs failing before the exact validator is added; a first failing mutation does not satisfy the RED.

Move `jsonschema>=4.26,<5` and `rfc3339-validator>=0.1.4,<0.2` into `[project].dependencies`, keep type stubs in dev, and add `pyarrow>=21,<24` as the explicit incremental Parquet runtime only after their dedicated metadata RED. The two root-schema force-includes, installed-wheel primary, and editable fallback must already have been added separately in the exact Step 4 order; do not reimplement or batch them here. The expected contract force-include remains absent until Checkpoint 8. A primary missing resource may enter the fallback; a primary symlink/special/invalid resource fails closed rather than searching elsewhere. Do not inspect `Path.cwd()`, `__file__` parents, repository settings, arbitrary distribution files, or caller paths, and do not configure Hatch `dev-mode-exact`. Update the lock with:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv lock
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups \
  --reinstall-package finproof
```

Change `.gitignore` to ignore all `/artifacts/` content plus root sibling names `/.artifacts.finproof-build.lock`, `/.artifacts.finproof-stage-*`, `/.artifacts.finproof-backup-*`, and `/.artifacts.finproof-cleanup-*`. Do not ignore `config/expected_phase1_artifacts.json`.

Add names-only safe `.env.example` defaults for `FINPROOF_REPOSITORY_ROOT=.`, `FINPROOF_SOURCE_ROOT=source_material`, `FINPROOF_ARTIFACT_BUILD_CONFIG_PATH=config/artifact_build.yaml`, and `FINPROOF_EXPECTED_ARTIFACT_CONTRACT_PATH=config/expected_phase1_artifacts.json`. Document that the file is not auto-loaded and must be explicitly sourced/exported by the user when desired.

Implement only the probe plus initial candidate absence guard in `tools/build_candidate_artifacts.py`; it must not call `second_check` yet, expose a transformation/output API, write a file, or publish. The production probe knows how to recheck real source/resource state later, but CP7C is the first code allowed to invoke that post-transform method.

- [ ] **Step 6: Run GREEN and checkpoint gates**

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/core/test_artifact_settings.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/contract/test_artifact_resources.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv build --wheel --out-dir /private/tmp/finproof-task5-cp1-wheel
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py::test_active_standard_editable_schema_loader_matches_current_repository_sources_outside_cwd \
  tests/contract/test_artifact_resources.py::test_standard_editable_schema_loader_uses_distribution_fallback_when_src_shadows \
  tests/contract/test_artifact_resources.py::test_built_wheel_schema_loader_uses_importlib_resources_primary -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/core src/finproof/data/artifacts src/finproof/resources \
  tools/build_candidate_artifacts.py tests/unit/core/test_artifact_settings.py \
  tests/unit/data/artifacts tests/contract/test_artifact_resources.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/core src/finproof/data/artifacts src/finproof/resources \
  tools/build_candidate_artifacts.py tests/unit/core/test_artifact_settings.py \
  tests/unit/data/artifacts tests/contract/test_artifact_resources.py
test ! -e config/expected_phase1_artifacts.json
git check-ignore artifacts/manifest.json .artifacts.finproof-stage-op123
```

Expected GREEN: focused tests pass; an actual isolated standard editable outside the checkout proves the exact distribution-metadata fallback while `src/finproof` shadows data; the isolated wheel proves `importlib.resources` primary, exact inventory, source-byte/SHA equality, and no fallback call; neither package contains expected contract or candidate tool; no dev-mode-exact workaround exists; type/lint checks pass; runtime artifacts/transients are ignored; official baseline remains absent.

- [ ] **Step 7: Run regressions, commit, and obtain a fresh review**

Run the unchanged Task 1-4 regression command, `git diff --check`, and verify `find source_material -type f -perm -u=w -print` returns no path. Commit:

```bash
git add pyproject.toml uv.lock .env.example .gitignore config/artifact_build.yaml \
  src/finproof/core/settings.py src/finproof/data/artifacts src/finproof/resources \
  tools/build_candidate_artifacts.py tests/helpers/artifacts.py \
  tests/unit/core/test_artifact_settings.py tests/unit/data/artifacts \
  tests/contract/test_artifact_resources.py
git commit -m "feat: add artifact build foundations"
```

Fresh review must specifically check protected-path aliases/symlinks, error-path leakage, duplicate YAML keys, runtime dependency/resource loading outside the checkout CWD, deep immutability, baseline absence, and candidate non-publication/non-packaging. Do not start Checkpoint 2 until review is 0 Critical / 0 Important.

---

### Checkpoint 2: Strict manifest, recursive inventory, and canonical logical hashing

**Files:**

- Modify: `schemas/artifact_manifest.schema.json`
- Create: `src/finproof/data/artifacts/hashing.py`
- Create: `src/finproof/data/artifacts/manifest.py`
- Create: `src/finproof/data/artifacts/reports.py`
- Create: `tests/unit/data/artifacts/test_hashing.py`
- Create: `tests/unit/data/artifacts/test_manifest.py`
- Create: `tests/unit/data/artifacts/test_reports.py`
- Create: `tests/contract/test_artifact_manifest_schema.py`
- Modify: `tests/contract/test_artifact_resources.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Produces: `canonical_json_bytes(value: object, *, terminal_newline: bool = True) -> bytes` and `canonical_scalar(value: object) -> object`.
- Produces internal `TableSpecIdentity` protocol with exact `table_name`, `grain`, ordered column identity, `unique_key`, and `sort_key` attributes, plus `schema_sha256(spec: TableSpecIdentity) -> str`, `table_logical_hash(spec, *, row_count: int, rows: Iterable[Mapping[str, object]]) -> str`, `report_logical_hash(report) -> str`, and `manifest_logical_hash(manifest) -> str`. Checkpoint 3's frozen `TableSpec` implements this protocol.
- Produces strict frozen `ArtifactInput`, `ArtifactVersions`, `ArtifactFile`, `ArtifactTable`, `ArtifactManifest`, and `VerifiedPhysicalInventory`. It imports CP1's `ArtifactLogicalContractView` only where orchestration/comparator typing requires it and does not define a competing verification-result protocol or a forward reference to CP7's trusted result.
- Produces: `ArtifactManifest.load(path: Path) -> ArtifactManifest`.
- Produces internal `verify_declared_inventory(manifest: ArtifactManifest, root: Path) -> VerifiedPhysicalInventory` plus `ArtifactVerificationKernel` orchestration protocols exercised with synthetic stub specs. The public `ArtifactManifest.verify(root) -> VerifiedArtifactSet` is intentionally not introduced here: Checkpoint 3 supplies frozen table-aware Parquet verification and Checkpoint 7 closes DuckDB equality before the trusted public result exists.
- Produces strict frozen `SourceAuditReport` with `report_id="source_audit"` and `QualitySummaryReport` with `report_id="quality_summary"`.

- [ ] **Step 1: Write canonical hashing REDs from an independent encoder**

Introduce each scalar family, header-order/count behavior, and invariance family serially with its own named selector and expected behavioral RED; do not implement all dispatch/hash cases after the first missing import.

In `test_hashing.py`, implement a small test-only encoder that does not import production hashing. Assert exact bytes for null/bool/int/text, `Decimal("0.000") -> "0"`, `Decimal("12.3400") -> "12.34"`, dates, naive source datetimes, UTC operational datetimes with six microseconds and terminal `Z`, `PurePosixPath`, enums, sorted Unicode keys, preserved array order, UTF-8, and one newline. Assert NaN/Infinity, non-UTC aware datetimes, unsupported objects, Decimal precision overflow, and `repr`-dependent objects fail.

Require the table stream header to be exactly:

```python
expected_header = {
    "schema_sha256": schema_hash,
    "logical_projection": ["id", "value"],
    "row_count": 2,
}
```

Prove path/layer/compression changes do not affect schema/table hashes, while table name, grain, ordered name/type/nullability, unique key, sort key, logical row, or the explicitly supplied final count changes do. Assert the encoder emits the known header before the first logical row, consumes the reopened-row iterator exactly once, and rejects a negative count or a stream whose observed count differs from `row_count`. Use only synthetic stub identities/projections here; Bronze/quality operational projections begin in Checkpoint 3 after their frozen specs/serializers exist.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py -q
```

Expected RED: `finproof.data.artifacts.hashing` and every canonical hash callable are missing.

- [ ] **Step 2: Implement canonical encoding and hashing without filesystem/database bytes**

Implement explicit type dispatch; reject `float` entirely so NaN/Infinity cannot enter by accident. `schema_sha256` hashes only table name, grain, ordered column identity, unique key, and sort key. `table_logical_hash` receives the already-known final `row_count`, hashes the exact three-key header first, then consumes a logical-row iterator once in frozen order while checking the observed count; it never materializes all rows. This primitive is not a while-writing Parquet hash API. `report_logical_hash` uses only the report model's semantic projection. `manifest_logical_hash` includes exact inputs, versions, table metadata, and closed report pairs while excluding persistence/output/physical metadata.

- [ ] **Step 3: Write REDs for the exact manifest/schema/inventory trust boundary**

Create a complete synthetic artifact tree helper with root `manifest.json`, 11 Parquet-named regular files, two reports, `finproof.duckdb`, and only `parquet/` and `reports/` directories. Add tests for exact 9-input order/kinds, exact 14-file order/kinds, exact 11-table order, lowercase SHA-256, UTC terminal-`Z`, deep immutable mappings, database file identity, report conditional fields, extra fields, wrong versions, duplicate canonical paths, unsafe POSIX paths, and schema format errors with explicit `FormatChecker`.

Parameterize recursive inventory rejection for extra file, extra directory, symlink file/directory, FIFO/socket, hardlink with `st_nlink != 1`, missing file, `.wal`, case/canonical duplicate, size mismatch, and physical checksum mismatch. Capture every target byte before `verify_declared_inventory`; failure must not mutate any byte. Add report tests that prove semantic ID, not report path, drives the report hash/order.

In `test_artifact_resources.py`, add the single selector `test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd`. It requires the new Section 10.1 structural signature in the repository schema and then requires the active standard-editable metadata-fallback bytes/SHA to equal that source from an unrelated CWD. Before schema implementation or reinstall, run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run --no-sync pytest \
  tests/contract/test_artifact_resources.py::test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd -q
```

Expected first RED: the repository schema still has the legacy shape. Do not reinstall yet.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/contract/test_artifact_manifest_schema.py -q
```

Expected RED: the legacy artifact schema rejects the approved shape; manifest/report models, load/inventory verification, and semantic report contracts are absent.

- [ ] **Step 4: Implement the exact schema, strict models, load, and all-or-nothing inventory**

Replace the legacy schema with the exact Section 10.1 shape. Call `Draft202012Validator.check_schema`, construct it with `FormatChecker`, collect every error, and reject before opening declared files. `load` parses JSON/domain/schema only. `verify_declared_inventory` uses descriptor-relative `os.scandir(..., follow_symlinks=False)`/`lstat`, opens regular files with `O_NOFOLLOW` where available, compares `fstat` device/inode/link count to the inventoried entry, hashes/reads that held descriptor, and rescans before return. Never follow links or validate one path and reopen it by name without identity comparison.

Define the verification orchestration as internal typed protocols for a closed table-spec registry, table verifier, report verifier, database verifier, and expected-contract comparator. CP2 tests use synthetic stub specs only to prove call order and all-or-nothing propagation. No caller-supplied verifier enters a public API, and CP2 must not claim table-aware, Parquet-aware, DuckDB-aware, or operational timestamp verification before the required CP3/CP7 dependencies exist.

Immediately rerun:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run --no-sync pytest \
  tests/contract/test_artifact_resources.py::test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd -q
```

Expected narrower RED: the root schema now has the approved shape, but CP1's installed editable fallback copy returns the previous bytes/SHA.

- [ ] **Step 5: Rebuild active editable force-included data and close the stale-resource RED**

Run the syntax supported by the repository's current uv (`uv sync --help` exposes `--reinstall-package <PACKAGE>`):

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups \
  --reinstall-package finproof
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py::test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd \
  tests/contract/test_artifact_resources.py::test_active_standard_editable_schema_loader_matches_current_repository_sources_outside_cwd -q
```

Expected GREEN: from an unrelated CWD, the source package still shadows copied data, the metadata fallback resolves only the frozen manifest-schema destination, and its bytes/SHA now equal the newly implemented root schema; the unchanged quality schema also remains equal. Do not proceed to mutation tests while either selector is stale.

- [ ] **Step 6: Add mutation-boundary REDs and exhaustive expected-contract comparison**

Mutate one physical byte, one report value, one overall input hash, and one expected-contract field in separate tests. Assert distinct codes for checksum, report, overall, and expected-baseline mismatch. The expected comparator must return no partial success and must report all sorted field paths without updating its input file. Parquet logical-row and operational timestamp mutations are deliberate CP3 REDs; same-count/different-value DuckDB mutation is a deliberate CP7 RED.

Expected RED: at least the report/overall/expected mutations cross the initial structural implementation.

- [ ] **Step 7: Complete logical/operational verification and run GREEN**

Implement manifest-shape/input/report/overall invariants, the complete expected-contract comparator over the protocol shape, and the CP2 verification orchestration. Do not yet add quality/Bronze operational timestamp checks because their exact table projections are frozen in CP3. Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/contract/test_artifact_manifest_schema.py \
  tests/contract/test_artifact_resources.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts tests/unit/data/artifacts \
  tests/contract/test_artifact_manifest_schema.py \
  tests/contract/test_artifact_resources.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts tests/unit/data/artifacts \
  tests/contract/test_artifact_manifest_schema.py \
  tests/contract/test_artifact_resources.py
```

Expected GREEN: canonical independent bytes/hashes agree; all structural/path/mutation cases fail at their intended boundary; a valid synthetic manifest loads and its declared physical inventory verifies immutably; the orchestration refuses a missing later verifier and never returns a prematurely trusted artifact set.

- [ ] **Step 8: Commit and obtain a fresh review**

Run regressions and diff checks, then commit:

```bash
git add schemas/artifact_manifest.schema.json src/finproof/data/artifacts \
  tests/helpers/artifacts.py tests/unit/data/artifacts \
  tests/contract/test_artifact_manifest_schema.py \
  tests/contract/test_artifact_resources.py
git commit -m "feat: add strict artifact manifest and logical hashing"
```

Fresh review must independently reproduce canonical bytes, inspect every manifest/schema conditional, attack recursive inventory without following links, verify no physical/report/path/timestamp field leaks into logical identity, and confirm no incomplete verifier can return a trusted set. Require 0 Critical / 0 Important.

---

### Checkpoint 3: Frozen table specs, strict projections, and bounded Parquet I/O

**Files:**

- Create: `src/finproof/data/artifacts/table_specs.py`
- Create: `src/finproof/data/artifacts/serialization.py`
- Create: `src/finproof/data/artifacts/parquet_io.py`
- Modify: `src/finproof/data/artifacts/hashing.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Create: `tests/unit/data/artifacts/test_table_specs.py`
- Create: `tests/unit/data/artifacts/test_serialization.py`
- Create: `tests/unit/data/artifacts/test_parquet_io.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/artifacts/__init__.py`
- Create: `tests/integration/artifacts/test_parquet_verification.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Produces strict frozen `ColumnSpec(name, logical_type, arrow_type, duckdb_type, nullable)`, `TableSpec(table_name, layer, grain, columns, unique_key, sort_key, logical_projection, parquet_path)`, and deeply immutable `TABLE_SPECS` in exact artifact order.
- Produces: `derive_wide_columns(model_type: type[BaseModel], *, skip_fields: frozenset[str] = frozenset()) -> tuple[ColumnSpec, ...]`.
- Produces: `canonical_record_json(model: BaseModel) -> str` and `serialize_table_row(spec: TableSpec, value: object, *, persistence_timestamp: datetime | None = None) -> Mapping[str, object]`.
- Produces: `ParquetBatchWriter(spec: TableSpec, path: Path)` with `write_batch(rows: Sequence[Mapping[str, object]])`, `close()`, `abort()`, and metrics `max_batch_rows`/`rows_written`.
- Produces private `verify_parquet_table(path: Path, spec: TableSpec, declared: ArtifactTable) -> VerifiedParquetTable`, consumed later by the full verifier.

- [ ] **Step 1: Write REDs for all eleven exact immutable table specs**

Assert the table order is exactly:

```python
EXPECTED_TABLES = (
    "bronze_source_column",
    "bronze_source_row",
    "bronze_source_cell",
    "silver_bond_instrument",
    "silver_domestic_listed_product",
    "silver_overseas_listed_product",
    "silver_fund_item",
    "silver_fund_item_attribute",
    "silver_quality_issue",
    "gold_exact_cross_source_link",
    "gold_exact_cross_source_link_evidence",
)
```

For every explicit Bronze/fund-attribute/quality/Gold table, assert the exact column order, nullability, Arrow/DuckDB types, key, grain, and Parquet path from Sections 5.1-5.3 and 5.8-5.11. For each wide table, independently derive its expected sequence from the frozen domain model declaration and assert it equals the hard-coded reviewed `TableSpec`; never generate the production spec at runtime from the same helper used by the test.

Add synthetic Pydantic models with one inserted, removed, and reordered field and prove `assert_model_matches_frozen_spec(...)` rejects each. Prove changing only `layer` or `parquet_path` leaves `schema_sha256` unchanged, while name/grain/column/type/nullability/unique/sort changes it.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_table_specs.py -q
```

Expected RED: `table_specs` and its exact registry do not exist.

- [ ] **Step 2: Implement the closed type/spec registry and model-drift guard**

Map only the frozen physical types: UTF-8/VARCHAR, int64/BIGINT, decimal128(38,18)/DECIMAL(38,18), date32/DATE, timestamp[us]/TIMESTAMP, timestamp[us, UTC]/TIMESTAMPTZ, and bool/BOOLEAN. Reject caller names and any unregistered logical type.

The wide derivation algorithm is exact:

1. emit `grain`;
2. traverse Pydantic fields in declaration order;
3. skip only `FundItem.contributing_rows`;
4. `NormalizedValue[T]` emits `<field>` then `<field>__quality_status`;
5. `DerivedValue[T]` emits `<field>`, `<field>__quality_status`, then `<field>__as_of_date`;
6. **`FundItemValue[T]` emits `<field> = representative.normalized_value` then `<field>__quality_status = representative.quality_status`; `equivalent_sources` remains only in `record_json`;**
7. emit `record_json` last.

Hard-code the reviewed resulting columns in `TABLE_SPECS`; use derivation only as a drift assertion. Validate exactly 17 normalized plus four derived bond fields, 30 normalized plus one derived domestic fields, 49 overseas fields, and 44 fund representative fields.

- [ ] **Step 3: Write REDs for exact strict-model serialization and projection equality**

Using current complete SourceRow helpers, normalize one bond, domestic-listed, overseas, and two-row fund item. For every model field, assert:

```python
payload = canonical_record_json(record)
round_tripped = type(record).model_validate_json(payload)
row = serialize_table_row(TABLE_SPECS[table_name], record)
assert round_tripped == record
assert row["record_json"] == payload
```

Then assert each wide scalar and quality/as-of field equals its exact wrapper. Add explicit fund assertions that the projected scalar is `item.ksd_id.representative.normalized_value`, the quality is `item.ksd_id.representative.quality_status.value`, and every `equivalent_sources` plus `contributing_rows` survives only in parsed `record_json`. Add raw/padded attribute-code, source-local datetime-without-timezone, Decimal scale-preservation in `record_json`, null scalar, enum string, and UTC terminal-`Z` cases. Reject NaN/Infinity, Decimal overflow/scale loss, mismatched spec/model, and noncanonical model JSON.

For `bronze_source_row`, prove the typed physical `loaded_at` is the injected UTC value while its logical projection is null. For `silver_quality_issue`, prove typed/strict JSON timestamps agree physically and both become null only through strict model reconstruction for logical hashing; changing any other field changes the logical hash.

Expected RED: serializer/projection functions are absent.

- [ ] **Step 4: Implement canonical strict-model JSON and typed row serializers**

Use `model.model_dump(mode="json")` followed only by sorted keys, compact separators, UTF-8, and JSON escaping. Do not pass payload leaves through `canonical_scalar`. Parse the resulting JSON back through the exact model in tests. Convert wide wrapper values according to `ColumnSpec`; reject any conversion that changes Decimal value/scale beyond `DECIMAL(38,18)` or adds a timezone to a source-local timestamp.

For quality rows, the serializer accepts only an already-persisted strict issue with a non-null UTC `first_detected_at`, emits its physical typed/JSON values, and computes a separate null-timestamp logical `record_json` by strict model reconstruction. It does not inject persistence time; that pure-to-persisted adapter begins with a CP5 RED. Do not replace timestamp text in a string. For Bronze rows, logical projection replaces only `loaded_at` with null.

- [ ] **Step 5: Write REDs for one-file bounded Parquet writing and reopened verification**

Use a batch limit of two in tests, write two batches to one file, close, reopen with PyArrow, and assert exact physical schema, row order, metadata, compression `ZSTD`, statistics present, row-group maximum, and values. Include all-null Decimal/date/local-time/UTC/bool columns to prove their declared types survive. Assert rows over the batch maximum, out-of-order keys, duplicate unique keys, wrong/missing/extra columns, incompatible Decimal, write/flush/close failure, and reuse-after-close fail typed. Instrument the writer to prove it only writes/counts bounded batches and does not attempt a final logical hash before close. On reopened verification, prove the known final row count is placed in the logical header before the first row is streamed. Mutate one logical cell, recompute the outer physical hash, and require `verify_parquet_table` to fail its logical hash; a mutation limited to Parquet physical encoding with identical typed logical rows must leave the logical hash unchanged.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
```

Expected RED: the bounded writer and table-aware verifier are missing.

- [ ] **Step 6: Implement the incremental PyArrow writer and table-aware verifier**

Construct `pyarrow.parquet.ParquetWriter` with only the exact explicit Arrow schema and supported constructor options `compression="zstd"`, `compression_level=3`, `write_statistics=True`, and `data_page_size=1_048_576`. Reject any input batch above 65,536 before constructing its Arrow table, then call `writer.write_table(arrow_batch, row_group_size=65_536)` for each bounded batch; `row_group_size` is deliberately a `write_table` argument, not a `ParquetWriter` constructor keyword. The writer only writes bounded typed batches and tracks the prospective count/key bounds needed for early failures; it does not compute the table logical hash while writing and never collects the full table in Polars/Python. Reopened metadata tests require every row group to contain at most 65,536 rows.

On close, flush and close once, then reopen the file. Obtain and validate the final Parquet row count and exact schema first. Initialize the logical hash with the now-known exact header `{schema_sha256, logical_projection, row_count}`, then bounded-stream reopened typed logical rows while validating count/sort/unique keys and updating the hash. Never use serialized Arrow buffers, Parquet row bytes, row-group encoding, compression bytes, or the outer file SHA as logical identity. Return `VerifiedParquetTable` only after the reopened stream and count agree. Integrate this private verifier into the CP2 orchestration, but still do not expose the full public artifact verifier before DuckDB comparison exists.

- [ ] **Step 7: Run GREEN, focused gates, and model coverage probes**

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts tests/unit/data/artifacts tests/integration/artifacts
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts tests/unit/data/artifacts tests/integration/artifacts
```

Expected GREEN: exact eleven specs are immutable; all four wide models have complete projection/round-trip coverage including the `FundItemValue.representative` rule; one-file bounded Parquet and reopened logical verification pass.

- [ ] **Step 8: Commit and obtain a fresh review**

Run regressions/diff checks, then commit:

```bash
git add src/finproof/data/artifacts tests/helpers/artifacts.py \
  tests/unit/data/artifacts tests/integration/artifacts
git commit -m "feat: freeze artifact table and Parquet contracts"
```

Fresh review must enumerate all table columns from source models independently, test model insertion/removal/reorder, verify the fund representative projection rule and record-only equivalent lineage, inspect exact Decimal/timestamp behavior, confirm incremental one-file writing, and ensure no table-sized collection. Require 0 Critical / 0 Important.

---

### Checkpoint 4: Complete Bronze streaming, external staging, and source-audit observations

**Files:**

- Create: `src/finproof/data/artifacts/staging.py`
- Create: `src/finproof/data/artifacts/bronze.py`
- Create: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Create: `tests/unit/data/artifacts/test_staging.py`
- Create: `tests/unit/data/artifacts/test_bronze.py`
- Create: `tests/integration/artifacts/test_bronze_fixture_build.py`
- Create: `tests/performance/test_artifact_external_staging.py`
- Modify: `tests/helpers/artifacts.py`
- Modify: `tests/helpers/xlsx.py`

**Interfaces:**

- Produces: `ExternalOrderStore(stage_root: Path, *, operation_id: str, memory_limit: str = "1GiB", threads: int = 1)` with fixed relations, `insert_batch`, `iter_ordered_batches`, failure `cleanup`, and success-only `close_and_remove_working_state()`. The latter preserves emitted Parquet/output stage content but closes the connection and removes only the store-owned staging database, WAL, spill/temp directory, and store markers after exact `lstat`/inode/marker checks; it never removes the build-stage ownership marker or uses a broad delete.
- Produces: `iter_bronze_columns(catalog: SourceSchemaCatalog) -> Iterator[Mapping[str, object]]`.
- Produces internal `SourceRowConsumer` protocol with exactly `consume(row: SourceRow) -> None`; it owns no workbook iterator and may not request/rescan source rows.
- Produces internal `BronzeFanoutSink(..., consumer: SourceRowConsumer | None)` with `consume_source_row(row: SourceRow) -> None`; the method enqueues that row's complete Bronze row and cells first, then invokes the registered consumer exactly once. `None` is valid for the CP4 Bronze-only fixture.
- Produces internal `ArtifactBuildSession.initialize(settings, versions, options) -> ArtifactBuildSession` and `ingest_bronze(*, consumer: SourceRowConsumer | None = None) -> BronzeBuildResult`; it writes only to a recognized sibling stage and never publishes.
- Produces strict frozen, phase-tagged `SourceAuditObservations.from_bronze(config, inputs, bronze_counts) -> SourceAuditObservations`. At CP4 it contains and validates only resolved input identity plus expected/observed catalog/Bronze row/cell/column observations; Silver, quarantine, link, and evidence fields are forbidden rather than fabricated.

- [ ] **Step 1: Write REDs for fixed staging settings, ownership, spill, and cleanup**

Create a private stage fixture and assert the staging connection reports exactly one thread, `1GiB`, `preserve_insertion_order=false`, and `temp_directory=<private-stage>/duckdb-temp`. Insert unsorted keys in batches, externally order into batches of at most the configured limit, and prove no table-sized `list`, DataFrame, or tuple is created by using an iterator that raises on `len`, second iteration, or retained weak references.

Fault-inject disk-full/write, close, spill-directory removal, marker removal, and connection-close failures. Each must raise its typed pre-publication error, leave a pre-existing published target byte-identical, close before cleanup, and never delete an unmarked or mismatched directory. Concurrent lock ownership and ambiguous orphan-stage markers must fail without mutation. On the success path, first deliberately omit `close_and_remove_working_state()` and prove exact-tree readiness fails because store-owned database/WAL/spill/temp/marker state remains; then call it and assert emitted Parquet/stage ownership bytes remain while only verified store-owned working state disappears. Parameterize partial cleanup, inode substitution, symlink, wrong marker, and ambiguous path; each must fail closed without broadening deletion.

Expected RED: `ExternalOrderStore` and recognized stage ownership do not exist.

- [ ] **Step 2: Implement bounded staging and marker-owned cleanup only**

Create the sibling lock/stage names exactly from the managed target basename and opaque operation ID. Create sidecar marker mode 0600 with operation ID, artifact-set ID, contract version, and target basename. Use static allowlisted DDL and parameters; no caller SQL/table name/path. On failure remove only a nonsymlink, exact-basename, exact-marker-owned private stage after the connection closes. If cleanup fails, preserve the recognized stage and raise `STAGING_CLEANUP_FAILED`.

For successful completion, close the DuckDB connection first, enumerate the closed finite set of store-owned working paths, revalidate each nonsymlink inode and exact operation marker, remove children in the fixed safe order, and unlink the store marker last. `close_and_remove_working_state()` is idempotent only after a recorded successful cleanup; missing/partial/ambiguous state raises instead of guessing. It preserves all Parquet files, reports/models in memory, and the separate build-stage marker needed by publication.

- [ ] **Step 3: Write REDs for full canonical Bronze fixture streaming**

Extend the XLSX fixture to write all four complete canonical header sets. Include at least one valid row per table, one domestic malformed ID, one fund malformed ID, two interleaved valid rows for one fund item, one domestic ETF/fund exact pair, one ETN non-link, and unsorted product IDs.

Assert catalog rows follow manifest table order and contiguous column order. Assert every SourceRow is written before normalization, each `raw_payload_json` is the compact JSON array of exact strings, each payload SHA is NUL-join SHA-256, `loaded_at` is identical, every cell reconstructs the payload, and the exact complete locator joins its catalog/row once. With a test batch limit of two, assert max live row/cell batch is two and weakrefs from prior batches are released.

Register a spy `SourceRowConsumer` and assert, for every row, that the complete Bronze row/cell set has already been enqueued when `consume(row)` is called, the identical `SourceRow` object is passed, and the call occurs exactly once. Add a source iterable/workbook-open sentinel that raises on a second iteration or second open; require the combined Bronze-plus-spy flow to succeed with one pass. Run the same fixture with `consumer=None` and require the Bronze-only result to remain valid. Freeze the one-method protocol: the fan-out may not hand consumers the workbook iterator, a callback for fetching the next row, or a partially emitted row.

Add expected/observed `SourceAuditObservations` mismatch cases for every input/catalog/Bronze row/cell/column count; construction/validation must fail and no `SourceAuditReport` may exist or be written at CP4. Add serialization/checksum/count/consumer failure after one batch and prove the published target is unchanged and partial stage is guarded/cleaned; the consumer failure must not cause retry or a second `consume` call.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/integration/artifacts/test_bronze_fixture_build.py -q
```

Expected RED: Bronze iterators/build session/source-audit observations are absent.

- [ ] **Step 4: Implement one-pass Bronze ingestion and streaming hashes**

Resolve, reopen, size-check, and SHA-256 the exact nine direct logical inputs first; validate dataset/rule versions and snapshot; then call `SourceFileManifest.load(...).verify(source_root)`. Recheck direct-input identities immediately before the first workbook open so a changed config/schema/source manifest cannot race into a declared build identity. Stream each verified data workbook exactly once in manifest order. Write catalog once. For each `SourceRow`, `BronzeFanoutSink.consume_source_row` enqueues one complete Bronze row and all of its cells into bounded sinks, updates Bronze observations, and only then invokes the registered `SourceRowConsumer.consume(row)` once. Because the sort key begins with frozen source table order, write final Bronze Parquet in bounded batches without a Python sort. The consumer never owns or iterates the workbook; a consumer exception fails the build without retry. This seam is the only CP5 normalization feed, so no official workbook is rescanned.

Track input/catalog/Bronze observed counts in immutable accumulators and construct only the CP4 `SourceAuditObservations` stage after exact config equality. Do not construct, serialize, hash, or stage a `SourceAuditReport`: the Silver/quarantine/link/evidence observations required by that final report do not exist yet.

- [ ] **Step 5: Add external-sort scale RED/GREEN and run checkpoint gates**

In `test_artifact_external_staging.py`, set `pytestmark = pytest.mark.performance`, generate at least 131,073 unsorted synthetic keys (more than two final row groups), force spill with a test memory limit, and assert output order, uniqueness, maximum emitted batch 65,536, one thread, private spill location, no retained input rows, and complete cleanup. Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/integration/artifacts/test_bronze_fixture_build.py \
  tests/performance/test_artifact_external_staging.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts tests/unit/data/artifacts \
  tests/integration/artifacts tests/performance/test_artifact_external_staging.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts tests/unit/data/artifacts \
  tests/integration/artifacts tests/performance/test_artifact_external_staging.py
```

Expected GREEN: fixture Bronze is complete/reconstructable, the optional consumer receives each already-enqueued row exactly once with no rescan, staging is externally sorted/bounded, all failures isolate the published target, and a Bronze/input observation mismatch cannot be advanced or rendered as a successful source-audit report.

- [ ] **Step 6: Commit and obtain a fresh review**

Run regressions/source audit/diff checks, then commit:

```bash
git add src/finproof/data/artifacts tests/helpers tests/unit/data/artifacts \
  tests/integration/artifacts tests/performance/test_artifact_external_staging.py
git commit -m "feat: stream complete Bronze artifacts"
```

Fresh review must trace one raw source value through catalog/row/cell/hash, verify workbook single-pass behavior, force external spill and every close/cleanup fault, inspect marker/lock/path TOCTOU handling, and prove no pre-publication failure mutates a target. Require 0 Critical / 0 Important.

---

### Checkpoint 5: Wide Silver, one-group public-fund collapse, persisted D-021 quality, and deterministic reports

**Files:**

- Modify: `src/finproof/data/normalization/public_funds.py`
- Create: `src/finproof/data/artifacts/silver.py`
- Create: `src/finproof/data/artifacts/quality_persistence.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/staging.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Create: `tests/unit/data/normalization/test_public_fund_group_adapter.py`
- Create: `tests/unit/data/artifacts/test_silver.py`
- Create: `tests/unit/data/artifacts/test_quality_persistence.py`
- Create: `tests/unit/data/artifacts/test_quality_report.py`
- Create: `tests/integration/artifacts/test_silver_fixture_build.py`
- Create: `tests/performance/test_artifact_fund_streaming.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Owns internal `BoundedRelationVerifier(Protocol)` in `quality_persistence.py`. It exposes only closed operations for quality-to-Bronze joins, exact-evidence-to-Bronze joins, and exact-ID-filtered linked domestic/fund `record_json` scans over already registered `VerifiedParquetTable` handles; it exposes no generic execute method, caller SQL, caller table name, or caller path.
- Produces CP5's stage-backed `StagedBoundedRelationVerifier` implementation using the marker-owned `ExternalOrderStore` connection with observed `threads=1`, `memory_limit="1GiB"`, static allowlisted SQL, and bounded result batches. CP5 quality verification and CP6 link/evidence verification reuse this concrete implementation while the candidate stage is being built.
- Produces strict frozen `FundRowKeyClassification(item_key: str | None, issue: DataQualityIssue | None)`.
- Produces public `classify_public_fund_row(row: SourceRow) -> FundRowKeyClassification`; it invokes only the authoritative key validator and never `normalize_fund_attribute`.
- Produces public `normalize_public_fund_item_group(rows: Sequence[SourceRow]) -> FundCollapseResult`; it accepts one unique, source-row-ordered item group, invokes `normalize_fund_attribute` exactly once per valid row, and delegates the existing authoritative collapse behavior.
- Produces: `persist_quality_issue(issue: DataQualityIssue, *, persistence_timestamp: datetime) -> PersistedQualityIssueRow` and private `verify_quality_bronze_relation(quality: VerifiedParquetTable, bronze_rows: VerifiedParquetTable, bronze_cells: VerifiedParquetTable, *, relation_verifier: BoundedRelationVerifier) -> QualityJoinObservations`; it never constructs a Python Bronze lookup collection.
- Produces internal `SilverArtifactEmitter.consume(row: SourceRow) -> None`, `finish_fund_groups() -> None`, and `finalize() -> SilverBuildResult`, all bounded and stage-backed. `SilverArtifactEmitter` structurally implements CP4's frozen one-method `SourceRowConsumer`; it receives rows only from `ArtifactBuildSession.ingest_bronze(consumer=emitter)`.
- Extends a Bronze-valid `SourceAuditObservations` through `observations.with_silver(silver_counts, quarantine_counts) -> SourceAuditObservations`; the returned phase permits only verified Silver/quarantine observations and still cannot construct the final source-audit report before CP6 links/evidence.
- Produces: `QualitySummaryReport.from_verified_quality(...) -> QualitySummaryReport` with closed lexical group ordering and timestamp-free semantic content.

- [ ] **Step 1: Write the public fund classifier/group-adapter equivalence REDs first**

For `classify_public_fund_row`, use every existing valid and malformed raw-key fixture from `test_public_fund_collapse.py`; assert the exact authoritative item key or classifier-only key issue and prove `normalize_fund_attribute` is never called. A malformed row is consumed only by this classifier path and is never passed to the group adapter.

Separately, for `normalize_public_fund_item_group`, use only valid, source-row-ordered, unique-single-item groups covering duplicate raw values, normalized collision, non-attribute disagreement, and canonical/reverse/even-odd/odd-even ordering. Assert:

```python
classification = classify_public_fund_row(source_row)
assert classification.item_key == expected_key
assert classification.issue == expected_key_issue

group_result = normalize_public_fund_item_group(sorted_group)
full_result = normalize_public_funds(sorted_group)
assert group_result == full_result
```

Instrument `normalize_fund_attribute` and assert the accepted group adapter calls it exactly once per valid row. In separate rejection selectors, require empty groups, multiple item keys, unsorted/duplicate source locations, and any group containing a malformed key to fail without comparing to global `normalize_public_funds`; malformed classifier issues remain the classifier's exact output. The adapter must expose no private normalizer helper to the artifact module.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/normalization/test_public_fund_group_adapter.py -q
```

Expected RED: the public classification/group interfaces are missing; existing global `normalize_public_funds` is not a bounded item-group API.

- [ ] **Step 2: Implement the smallest authoritative public adapter and keep global behavior green**

Promote one key-classification function around the existing exact key policy and one one-group adapter around existing row normalization/collapse. Do not move business rules into the artifact package or SQL. Make `normalize_public_funds` reuse these public functions so equivalence cannot drift. Rerun the new file plus all existing public-fund tests; expected GREEN with unchanged Task 4 outputs.

- [ ] **Step 3: Write Silver projection/staging REDs for all product types**

Pass `SilverArtifactEmitter` as the consumer of the CP4 Bronze fixture session, using unsorted synthetic rows for bonds/domestic/overseas and interleaved public funds. Compare every emitted `record_json`/wide row with direct current normalizer results and strict model parseback. Assert malformed domestic/fund rows emit no normal Silver record, remain present in Bronze, and contribute canonical quarantined issues. Reuse the CP4 second-open/second-iteration sentinel and assert every row reaches `SilverArtifactEmitter.consume` exactly once only after its Bronze row/cells were enqueued.

Install sentinels that fail on full `list`/tuple/DataFrame materialization or second source iteration. Assert bond/domestic/overseas and the global quality relation use `ExternalOrderStore`, while grouped fund items/attributes write already ordered batches. Assert only canonical SourceRow JSON plus validated item key is staged for funds, SQL performs no normalization, maximum live fund source rows equals the current group, and objects/JSON from the prior group are released.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_silver.py \
  tests/integration/artifacts/test_silver_fixture_build.py -q
```

Expected RED: Silver emitter/stage relations/fund ordering do not exist.

- [ ] **Step 4: Implement one-pass non-fund normalization and bounded fund staging/collapse**

During the one and only Bronze source pass, `ArtifactBuildSession.ingest_bronze(consumer=silver_emitter)` calls `SilverArtifactEmitter.consume(row)` exactly once after Bronze enqueue. That consumer performs:

- PRBD01N001 calls `normalize_bond(row, versions.dataset_version, rating_registry)` once and stages a wide row by product ID;
- PREF01N001 calls `normalize_domestic_listed(row, versions.dataset_version)` once and stages a wide row by product ID;
- PREF02N001 calls `normalize_overseas_listed(row)` once and stages a wide row by product ID;
- PRFD01N001 calls `classify_public_fund_row(row)`; malformed issues go directly to quality staging, valid canonical SourceRow JSON plus item key/source row enter the fund staging relation.

After source ingestion, externally order fund staging by item key/source row, reconstruct exact `SourceRow` objects, call `normalize_public_fund_item_group` once per group, immediately serialize its one item/attributes/issues, flush bounded batches, and release the group. No CP5 component reopens a workbook or iterates the source stream. Expose instrumentation `max_live_fund_group_rows`, `max_writer_batch_rows`, source-consume counts, and staged relation row counts in the internal build result.

- [ ] **Step 5: Write D-021 persistence/joins/report REDs**

Assert pure normalizer issues still have `first_detected_at is None`. `persist_quality_issue` must reject pre-timestamped, naive, and non-UTC inputs; inject the one build timestamp; serialize terminal `Z`; pass the packaged/root quality schema with explicit `FormatChecker`; and preserve issue ID/rule/severity/reason/quarantine/raw hash/source exactly.

Build mutation cases for missing Bronze row, wrong cell, wrong raw-payload SHA, typed timestamp versus JSON mismatch, two distinct timestamps, duplicate issue ID, and global sort disorder. Each must block stage verification. Assert exactly two distinct quarantined source rows in the fixture, while total issue count is observed/reportable rather than frozen to 6,032. Install sentinels that raise on `len`, second iteration, `list`/DataFrame construction, or retention of a prior verifier batch; the quality-to-Bronze check must run as an allowlisted typed SQL relation and bounded stream rather than materializing Bronze rows/cells or all quality joins.

For `QualitySummaryReport`, assert lexical arrays/mapping keys, counts by table/rule-version/severity/status/quarantine, distinct affected rows, excluded native grains, and quality logical SHA; moving/pretty-printing the report keeps semantic hash, changing content changes it, and no timestamp/path enters. Assert `with_silver` rejects an observation object not validated at the Bronze phase, expected/observed Silver or quarantine mismatch, repeated extension, and any premature link/evidence or final-report field.

Expected RED: persistence adapter, the closed bounded-relation protocol/stage implementation, streaming Bronze joins, and quality report aggregation are absent.

- [ ] **Step 6: Implement D-021 persistence, global external sort, joins, and reports**

Reconstruct `DataQualityIssue` with `model_validate(issue.model_dump() | {"first_detected_at": timestamp})`; never mutate frozen issues. Validate canonical JSON with the runtime resource schema. Stage all issues under the exact global key and externally order them. During reopened table verification, register only internally supplied verified Parquet handles with `StagedBoundedRelationVerifier`, join the quality relation to Bronze row/cell relations through its closed operation, stream bounded mismatch/count results, compare raw payload hashes, and enforce one timestamp across manifest/Bronze/quality typed/quality JSON. Never load 145,393 Bronze rows, 6,401,851 Bronze cells, or the full join into Python. Build `QualitySummaryReport` only from the verified quality stream and extend the CP4 observations with verified Silver/quarantine counts. Do not construct `SourceAuditReport` yet, and never add dataset-level constant-metric issues.

- [ ] **Step 7: Prove fund and writer bounds under scale**

In `test_artifact_fund_streaming.py`, set `pytestmark = pytest.mark.performance`, generate thousands of interleaved rows with maximum group 16, reverse and interleave them, force external spill, and assert byte-identical logical item/attribute output, `max_live_fund_group_rows <= 16`, writer batch `<= 65_536`, no retained prior-group weakrefs, and no call to global full-dataset `normalize_public_funds`. Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/normalization/test_public_fund_group_adapter.py \
  tests/unit/data/artifacts/test_silver.py \
  tests/unit/data/artifacts/test_quality_persistence.py \
  tests/unit/data/artifacts/test_quality_report.py \
  tests/integration/artifacts/test_silver_fixture_build.py \
  tests/performance/test_artifact_fund_streaming.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/normalization/public_funds.py src/finproof/data/artifacts \
  tests/unit/data tests/integration/artifacts tests/performance/test_artifact_fund_streaming.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/normalization/public_funds.py src/finproof/data/artifacts \
  tests/unit/data tests/integration/artifacts tests/performance/test_artifact_fund_streaming.py
```

Expected GREEN: direct/current normalizers and serialized Silver agree from one Bronze-fed source pass; fund behavior is item-bounded/order-invariant; D-021 timestamps/joins are exact; the quality report contains no operational identity; Silver/quarantine observations are valid but the final source-audit report remains impossible before CP6.

- [ ] **Step 8: Commit and obtain a fresh review**

Run regressions/source audit/diff checks, then commit:

```bash
git add src/finproof/data/normalization/public_funds.py \
  src/finproof/data/artifacts tests/helpers/artifacts.py tests/unit/data \
  tests/integration/artifacts tests/performance/test_artifact_fund_streaming.py
git commit -m "feat: stream Silver and persisted quality artifacts"
```

Fresh review must compare the public group adapter with every Task 4 edge case, prove no full official collapse/double normalization, inspect all wide fields and quarantine joins, force issue timestamp/schema/hash mismatches, verify external sorting, and confirm the 6,032 observation is not a frozen acceptance constant. Require 0 Critical / 0 Important.

---

### Checkpoint 6: Exact raw identifier links and complete bidirectional locator evidence

**Files:**

- Create: `src/finproof/data/artifacts/links.py`
- Modify: `src/finproof/data/artifacts/silver.py`
- Modify: `src/finproof/data/artifacts/staging.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Create: `tests/unit/data/artifacts/test_exact_links.py`
- Create: `tests/unit/data/artifacts/test_source_audit_report.py`
- Create: `tests/integration/artifacts/test_link_evidence_fixture.py`
- Create: `tests/source_contract/test_official_exact_link_profile.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Produces strict frozen `ExactCrossSourceLink` and `ExactCrossSourceLinkEvidence` matching Sections 5.10-5.11 exactly.
- Produces: `build_exact_links(stage: ExternalOrderStore) -> ExactLinkBuildResult` over closed internally populated left/right candidate relations.
- Produces: `verify_exact_link_evidence(*, links: VerifiedParquetTable, evidence: VerifiedParquetTable, bronze_cells: VerifiedParquetTable, domestic_records: VerifiedParquetTable, fund_items: VerifiedParquetTable, relation_verifier: BoundedRelationVerifier) -> ExactEvidenceVerificationObservations` with complete bidirectional validation. Inputs are reopened verified Parquet handles/allowlisted relations, not table-sized Python iterables; CP6 passes CP5's `StagedBoundedRelationVerifier` and does not introduce a new or CP7-forward concrete type.
- Produces: `canonical_link_pair_tsv(rows: Iterable[ExactCrossSourceLink]) -> bytes` and `exact_link_pair_sha256(...) -> str`.
- Completes the phased observations through `observations.with_links(link_count, evidence_count, pair_sha256) -> SourceAuditObservations`, then produces `SourceAuditReport.from_complete_observations(config, observations) -> SourceAuditReport`. Both operations refuse missing/prior-phase, unequal expected/observed, or reordered/recomputed pair data; this is the first checkpoint where the final strict source-audit report can exist.

- [ ] **Step 1: Write rule-boundary REDs that reject every non-exact link path**

Construct direct domain records with exact raw locators. Assert one equal raw domestic ETF/fund ID links. Parameterize non-links for whitespace/padding mismatch, equal only after trim, case-fold/name/family/standard-ID equality, domestic ETN, overseas product, missing representative raw value, and normalized-value-only equality. Assert confidence serializes as shared `DECIMAL(38,18)` exact `1.0` and constants equal the approved rule/table/field/version values.

Add one-to-many left, many-to-one right, duplicate pair, and disagreeing `FundItemValue.equivalent_sources` raw-value cases; each must raise `EXACT_LINK_CONFLICT` before output. Reverse candidate input and assert byte-identical order/link IDs.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_exact_links.py -q
```

Expected RED: exact-link contracts/rule/candidate relations are absent.

- [ ] **Step 2: Implement the closed raw rule and deterministic conflict validation**

While domestic records are live in Checkpoint 5, stage only ETF candidate product ID/raw ID/full `pd_itm_no` locator. While one fund item is live, stage its item ID, representative KSD raw value, representative locator, and every ordered equivalent KSD locator/raw value. Do not rescan all wide `record_json` into Python.

Use static staging SQL only to order/join exact raw strings and detect cardinality conflicts. Build `link_id` from the NUL-separated rule ID/version/left table/ID/right table/ID/matched raw identifier. Keep trimming in a separate acceptance measurement and never feed a trimmed value into the link result.

- [ ] **Step 3: Write full evidence relation REDs**

For one link with multiple fund source rows, assert one left evidence at role order 0/ordinal 0 and every right `ksd_itm_no` locator at role order 1/contiguous ordinal in exact `equivalent_sources` order. Parameterize missing, duplicate, reordered, swapped-role, noncontiguous ordinal, wrong field, wrong raw value, wrong parent link, wrong Bronze locator, omitted authoritative locator, and extra proximity-derived locator. Each must fail verification.

Assert every evidence row joins exactly one complete Bronze cell, `evidence.raw_identifier == bronze.raw_value == parent.matched_raw_identifier`, and the evidence relation is bidirectionally equal to the two authoritative wrapper sources. Permit buffering only the bounded 47 link keys and 371 evidence keys. Require the verifier to select and strict-parse only the linked 47 domestic and 47 fund `record_json` values by exact IDs, and validate all Bronze locator/raw joins through internal allowlisted typed SQL plus bounded mismatch streams. Sentinels must fail on `len`, second iteration, whole-table list/tuple/DataFrame creation, parsing any unrelated wide record, or retaining a previous stream batch.

In `test_source_audit_report.py`, begin from a CP5 Silver/quarantine-complete observation fixture. Assert the exact-link/evidence counts and canonical pair hash extend it to the complete phase, and only that complete phase can construct the final strict `SourceAuditReport`. Parameterize missing/extra/repeated phases, wrong expected or observed count, wrong source-manifest/catalog hash, changed pair hash, link/evidence relation mismatch, and attempts to copy the tests baseline; each must fail before report serialization. Assert the report is timestamp/path-free and semantically stable across pretty rendering.

Expected RED: evidence construction/verification is absent or incomplete.

- [ ] **Step 4: Implement exact evidence emission and bidirectional validation**

Emit evidence from the staged authoritative candidates, never from inferred adjacent Bronze cells. Validate relation cardinality and order before Parquet writing and again after reopen. Use external stage ordering for links/evidence; no table-sized list or Python sort. The reopened validation registers only trusted verified Parquet handles with the one-thread/1-GiB relation verifier, buffers the closed small link/evidence key sets, filters wide records by those exact IDs before strict JSON parsing, and streams Bronze join mismatches/counts; it never scans wide `record_json` into Python or materializes the Bronze cell table. After the reopened relations establish exact counts and `exact_link_pair_sha256`, advance the CP5 observations once and construct the final `SourceAuditReport` from `config/artifact_build.yaml` expected values plus the fully observed source/catalog/Bronze/Silver/quarantine/link/evidence data. Keep the strict model in the private build session only; CP7 owns writing, reparsing, hashing, manifest declaration, and full verification.

- [ ] **Step 5: Add the official profile acceptance and observe it only after unit behavior is green**

`tests/source_contract/test_official_exact_link_profile.py` declares `pytestmark = pytest.mark.source_contract`, loads verified official source descriptors, and reuses the bounded internal candidate path without building a full runtime artifact. Assert exactly 47 one-to-one raw pairs, zero ETN links, raw and trimmed pair sets equal, canonical TSV length 1,222 and SHA-256 `8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962`, and exactly 371 evidence locators (47 left + 324 right).

This acceptance may pass on its first run because unit RED/GREEN already introduced the behavior; do not manufacture a production failure. Record that fact explicitly in status later.

- [ ] **Step 6: Run GREEN and checkpoint gates**

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_exact_links.py \
  tests/unit/data/artifacts/test_source_audit_report.py \
  tests/integration/artifacts/test_link_evidence_fixture.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/source_contract/test_official_exact_link_profile.py -q -m source_contract
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts/links.py src/finproof/data/artifacts/silver.py \
  src/finproof/data/artifacts/reports.py \
  tests/unit/data/artifacts/test_exact_links.py \
  tests/unit/data/artifacts/test_source_audit_report.py \
  tests/integration/artifacts/test_link_evidence_fixture.py \
  tests/source_contract/test_official_exact_link_profile.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts/links.py src/finproof/data/artifacts/silver.py \
  src/finproof/data/artifacts/reports.py \
  tests/unit/data/artifacts/test_exact_links.py \
  tests/unit/data/artifacts/test_source_audit_report.py \
  tests/integration/artifacts/test_link_evidence_fixture.py \
  tests/source_contract/test_official_exact_link_profile.py
```

Expected GREEN: only exact raw ETF/item links exist; conflicts block; every evidence locator is complete, ordered, bidirectional, and Bronze-backed; the final source-audit report is constructed only from complete equal observations; official profile is 47/371 with the frozen pair hash.

- [ ] **Step 7: Commit and obtain a fresh review**

Run regressions/source audit/diff checks, then commit:

```bash
git add src/finproof/data/artifacts tests/helpers/artifacts.py \
  tests/unit/data/artifacts/test_exact_links.py \
  tests/unit/data/artifacts/test_source_audit_report.py \
  tests/integration/artifacts/test_link_evidence_fixture.py \
  tests/source_contract/test_official_exact_link_profile.py
git commit -m "feat: add exact cross-source link artifacts"
```

Fresh review must independently recompute the 47-pair TSV/hash and 371 locator profile, inject every conflict/evidence mutation, confirm no trim/name/family/ETN route, inspect link ID/confidence/types, and verify candidates are bounded/staged while records are live. Require 0 Critical / 0 Important.

---

### Checkpoint 7: Self-contained DuckDB, full verification, guarded publication, and safe CLI

Keep one checkpoint number but make three independently reviewable commits, 7A/7B/7C. Obtain one fresh checkpoint review over all three commits; any review correction gets a fourth dedicated fix commit.

The global single-selector RED/smallest-GREEN loop applies independently to every named mutation, security boundary, fault-injection state, candidate guard, and CLI behavior in 7A/7B/7C. The grouped commands below are aggregate gates and cannot substitute for the recorded per-selector REDs.

#### Checkpoint 7A: Database construction and the first complete artifact verifier

**Files:**

- Create: `src/finproof/data/artifacts/database.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Create: `tests/integration/artifacts/test_artifact_duckdb.py`
- Create: `tests/integration/artifacts/test_artifact_equality.py`
- Create: `tests/integration/artifacts/test_artifact_tampering.py`
- Create: `tests/unit/data/artifacts/test_runtime_temp.py`
- Create: `tests/performance/test_artifact_verifier_bounds.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Produces private `build_self_contained_database(parquet_root: Path, database_path: Path) -> str`, returning the closed-file SHA-256.
- Produces public `open_read_only_database(path: Path) -> duckdb.DuckDBPyConnection` for application/runtime reads only.
- Produces private `verify_database_against_parquet(database_path, verified_tables, *, runtime_tmp_root: Path | None = None) -> None` using its own trusted internally allowlisted verification connection and marker-owned OS temp.
- Completes public `ArtifactManifest.verify(root: Path) -> VerifiedArtifactSet`; only this CP7 implementation can return the trusted type.
- Produces internal `build_verified_candidate_stage(settings, versions, options) -> CandidateArtifactSet`, which fully verifies but does not compare expected, publish, or expose its stage path publicly.

- [ ] **Step 1: Write 7A REDs for exact self-contained DuckDB construction**

Build the complete small fixture Parquet set. Assert DuckDB contains exactly the eleven table names, exact information-schema column order/types/nullability, exact counts, and no view/external path. Assert materialization uses explicit frozen column lists and final `ORDER BY`; database close/checkpoint leaves no `.wal`. Reopen it and compare Decimal/date/local timestamp/UTC timestamp/null values without text coercion.

Mutate one DuckDB cell while preserving table schema/count and recompute the physical database hash/manifest entry. The full verifier must reject it through bidirectional typed `EXCEPT ALL`; a count-only verifier is an observed RED. Add deleted/duplicated row variants too.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/integration/artifacts/test_artifact_duckdb.py \
  tests/integration/artifacts/test_artifact_equality.py -q
```

Expected RED: database builder/public reader/private equality verifier and full manifest verifier are missing.

- [ ] **Step 2: Implement separate public-reader and private-verifier connections**

The writer uses `threads=1`, `preserve_insertion_order=true`, `TimeZone=UTC`, static allowlisted DDL, and trusted stage paths only. Insert verified Parquet rows with explicit frozen columns/order; checkpoint/close; reject any WAL; hash the closed file.

`open_read_only_database` first `lstat`s an existing nonsymlink regular file, then opens `read_only=True` and permanently sets `enable_external_access=false`, `allow_unsigned_extensions=false`, `autoinstall_known_extensions=false`, `autoload_known_extensions=false`, and `lock_configuration=true`. Do not use this hardened connection to call `read_parquet`.

The private verifier creates one unique mode-0700 marker-owned directory below trusted OS temp or a containment-validated `FINPROOF_RUNTIME_TMP_ROOT`, places private spill there, uses `threads=1`/`memory_limit=1GiB`, and runs internally generated typed `EXCEPT ALL` in both directions using only `TABLE_SPECS`. Its `RuntimeBoundedRelationVerifier` is the second concrete implementation of CP5's closed `BoundedRelationVerifier`, separate from the stage-backed implementation: quality/Bronze and evidence/Bronze checks are allowlisted SQL relations over internally registered verified handles whose mismatch/count output is bounded; link/evidence validation buffers only the closed 47/371 keys and strict-parses only exact-ID-filtered 47 domestic plus 47 fund records. It never accepts caller SQL/table/path, materializes full Bronze/wide relations in Python, or writes in artifact root or its parent.

- [ ] **Step 3: Write 7A REDs for read-only security and runtime-temp failures**

Through the public reader, require persistent `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, external `ATTACH`, and `COPY TO` to fail. Assert TEMP objects are explicitly not promised but no public FinProof API exposes raw SQL. Test missing/symlink/directory database paths.

Make artifact root and its parent read-only and verify successfully using the private OS temp. Assert mode 0700, one thread, 1-GiB limit, spill actually occurs under forced low synthetic limits, and no artifact-parent entry appears. Fault-inject temp creation/marker/close/spill/removal failure; close before cleanup, delete only exact marker-owned temp, retain ambiguous temp, and raise a bounded typed verification error.

Expected RED: public hardening or private temp ownership/settings/cleanup is incomplete.

- [ ] **Step 4: Assemble the complete public verifier and mutation matrix**

`ArtifactManifest.verify(root)` now executes, all-or-nothing:

1. strict load/schema and exact recursive inventory;
2. every physical size/SHA;
3. every Parquet exact schema/count/sort/unique/logical hash;
4. both strict report IDs/logical hashes;
5. overall manifest logical hash;
6. manifest/Bronze/quality typed/quality-JSON timestamp consistency;
7. exact link/evidence/bidirectional Bronze relation;
8. exact DuckDB information schema/count and typed bidirectional `EXCEPT ALL` equality.

Only after all eight return `VerifiedArtifactSet`. In boundary 6/7, pass reopened verified Parquet handles to the private relation verifier; never expose raw table iterators to a materializing helper. Add adversarial fixtures that mutate one boundary and recompute every attacker-controlled outer field; each deeper boundary must still reject. Recheck the tree immediately before each file open/hash and immediately before returning to close inventory/hash TOCTOU windows; a swapped inode, newly added file, or symlink replacement blocks. Add finalizer selectors for one omitted `ExternalOrderStore.close_and_remove_working_state`, each partially removed working-state member, an ambiguous marker/path, and inode replacement between cleanup validation/removal; all must block before report/manifest creation and preserve declared output Parquets.

In `test_artifact_verifier_bounds.py`, set `pytestmark = pytest.mark.performance`, build scale relations with 145,393 Bronze rows and 6,401,851 generated Bronze cells (or reuse the fully verified official-size fixture when available), but only 47 links/371 evidence locators. Install `len`/second-iteration/materialization and prior-batch-retention sentinels. Assert `max_verifier_batch_rows <= 65_536`, exactly 47 domestic plus 47 fund strict `record_json` parses, at most 47 link and 371 evidence keys live, one verifier thread/1-GiB spill, and no Python collection proportional to Bronze cells, quality joins, or any full wide table.

The candidate-stage finalizer closes/reopens every Parquet and verifies every logical table first. It then calls `close_and_remove_working_state()` on every registered `ExternalOrderStore` and proves no staging database/WAL/spill/temp/store marker remains before writing either report or beginning the exact-tree inventory. An omitted call, partial cleanup, substituted inode, or ambiguous working path fails pre-manifest and preserves the build stage for guarded diagnostics; it cannot be hidden as an undeclared extra tree entry. Only then does the finalizer write/reparse both reports, materialize/checkpoint/close DuckDB, record all 14 physical sizes/SHA values, write canonical pretty `manifest.json` with one terminal newline, and invoke this public verifier. A file that merely closed without complete flush/hash/verify/working-state cleanup can never become a candidate.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/integration/artifacts/test_artifact_duckdb.py \
  tests/integration/artifacts/test_artifact_equality.py \
  tests/integration/artifacts/test_artifact_tampering.py \
  tests/unit/data/artifacts/test_runtime_temp.py \
  tests/performance/test_artifact_verifier_bounds.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts tests/integration/artifacts \
  tests/unit/data/artifacts/test_runtime_temp.py \
  tests/performance/test_artifact_verifier_bounds.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts tests/integration/artifacts \
  tests/unit/data/artifacts/test_runtime_temp.py \
  tests/performance/test_artifact_verifier_bounds.py
```

Expected GREEN: the fixture database is self-contained/read-only; same-count substitution fails; complete verification returns only after every physical/logical/report/timestamp/link/database boundary; runtime temp is private/bounded/clean.

- [ ] **Step 5: Commit 7A**

```bash
git add src/finproof/data/artifacts tests/helpers/artifacts.py \
  tests/integration/artifacts tests/unit/data/artifacts/test_runtime_temp.py \
  tests/performance/test_artifact_verifier_bounds.py
git commit -m "feat: verify self-contained artifact databases"
```

#### Checkpoint 7B: Guarded publication, rollback, tombstone cleanup, and recovery

**Files:**

- Create: `src/finproof/data/artifacts/publication.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Create: `tests/helpers/artifact_filesystem.py`
- Create: `tests/unit/data/artifacts/test_publication.py`
- Create: `tests/integration/artifacts/test_publication_faults.py`
- Create: `tests/integration/artifacts/test_publication_recovery.py`

**Interfaces:**

- Produces `PublicationState` as the closed enum `STAGE_VERIFIED`, `BACKUP_VERIFIED`, `TARGET_RENAMED_UNCOMMITTED`, `PUBLISHED`, `BACKUP_WITH_MARKER`, `BACKUP_WITH_PREPARED_TOMBSTONE_MARKER`, `TOMBSTONE_WITH_BOTH_MARKERS`, `BOTH_MARKERS_ONLY`, `BACKUP_MARKER_ONLY`, and `NO_REMNANT`.
- Produces: `publish_verified_stage(stage: CandidateArtifactSet, *, settings: Settings, clean: bool, filesystem: ArtifactFilesystem) -> ArtifactManifest`.
- Produces: `recover_owned_remnants(settings: Settings, *, filesystem: ArtifactFilesystem) -> None` under the same exclusive lock.
- `ArtifactFilesystem` exposes only exact-path `lstat`, exclusive marker create/read, same-filesystem rename, exact unlink, and marker-owned tombstone deletion; no glob/broad resolved delete method exists.

- [ ] **Step 6: Write 7B REDs for no-clean/clean recognition and both rename rollback boundaries**

Assert absent target publishes by stage rename only after full verification. Existing target without clean raises `EXISTING_TARGET` byte-identically. With clean, symlink/non-directory/empty/unrecognized/extra-entry/special/hardlink/WAL/invalid-manifest targets refuse before rename/chmod/unlink; snapshot every inode/byte/mode.

Freeze the target-absent first-publication rollback branch with three selectors separate from every existing-target/backup case:

- `test_first_publish_verification_failure_rolls_target_back_to_marked_stage`: inject reopened target verification failure after `stage -> target`; require the candidate bytes/inodes to return to the exact original marked stage, target absent, no backup/tombstone directory or marker, and every unrelated sibling byte/inode/mode unchanged.
- `test_first_publish_stage_marker_unlink_failure_rolls_target_back_to_marked_stage`: let post-rename verification pass, fail the orphaned stage-marker unlink before the commit point, then require the same target-absent/byte-identical marked-stage/no-backup-or-tombstone/unrelated-sibling state.
- `test_first_publish_target_to_stage_rollback_failure_is_typed_and_preserved`: after either pre-commit fault, fail the exact `target -> stage` rollback rename. Require only `PUBLICATION_ROLLBACK_FAILED`, `published=False`, closed state `TARGET_RENAMED_UNCOMMITTED`, the complete candidate still at target with its exact stage sidecar marker retained for operator recovery, original stage path absent, no backup/tombstone state, unrelated siblings unchanged, exact recovery paths only in internal diagnostics, and no path in safe output.

For a recognized old target, fault-inject old-target-to-backup rename, stage-to-target rename, post-rename target verification, and stage-marker unlink. Before commit point, the old target must remain or be restored byte-identically; failed restoration raises only `PUBLICATION_ROLLBACK_FAILED` and preserves both exact recovery paths in internal diagnostics, never safe output.

Expected RED: no publication state machine exists.

- [ ] **Step 7: Implement pre-commit recognition, rename, verification, and rollback**

Hold `.<target>.finproof-build.lock` exclusively for build/clean/recovery. Recognize target only by the complete public verifier and exact recursive inventory. Use exact same-filesystem sibling stage/backup markers and `lstat` immediately before every rename. The commit point is successful reopened target verification plus stage-marker removal. Never recursively delete before it.

Implement target-absent rollback without inventing a backup: after `stage -> target`, either target verification or stage-marker removal failure moves only that recognized target back to the exact marker-owned stage name and revalidates it, leaving target absent. If that move fails, preserve `TARGET_RENAMED_UNCOMMITTED` and raise the one typed rollback error without deleting target/marker or claiming a backup. Keep this branch distinct from existing-target rollback, which additionally restores its verified backup.

- [ ] **Step 8: Write 7B REDs for every post-commit tombstone/remnant state**

Exercise exactly:

```text
verified backup dir + backup marker
-> verified backup dir + backup marker + prepared tombstone marker
-> tombstone dir + tombstone marker + obsolete backup marker
-> tombstone marker + obsolete backup marker
-> obsolete backup marker
-> no remnant
```

Fault-inject backup-to-tombstone rename, recursive tombstone deletion, tombstone-marker unlink, and obsolete-backup-marker unlink separately. After commit, no failure may roll back/delete/mutate the new verified target. Rename failure retains a complete verified backup; failure after tombstone rename must not claim a verified backup. Error code is `BACKUP_CLEANUP_FAILED_AFTER_PUBLISH`, `published=True`, and safe message names only target basename/operation ID.

For next-run recovery, start from every closed state and reach none when the new target verifies. If target is absent, restore the verified backup and never consume a partial tombstone. Reject tombstone-marker-only, mismatched operation/basename, unexpected corresponding directory, duplicate marker, marker without verified target, ambiguous/unverified backup, and unrelated sibling. Fault-inject directory substitution between validation and deletion; `lstat`/marker/inode mismatch blocks without broadening delete.

Expected RED: partial cleanup/recovery or marker unlink behavior is absent.

- [ ] **Step 9: Implement atomic tombstoning and exact remnant recovery, then run GREEN**

Rename the complete verified backup to its cleanup tombstone before recursive deletion. Deletion traverses only exact marker-owned children by descriptor/`lstat`, never `resolve()` plus glob/rmtree. Persist marker states in the required unlink order so recovery is idempotent. Close all DuckDB connections before rename/delete.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_publication.py \
  tests/integration/artifacts/test_publication_faults.py \
  tests/integration/artifacts/test_publication_recovery.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts/publication.py tests/helpers/artifact_filesystem.py \
  tests/unit/data/artifacts/test_publication.py tests/integration/artifacts/test_publication_faults.py \
  tests/integration/artifacts/test_publication_recovery.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts/publication.py tests/helpers/artifact_filesystem.py \
  tests/unit/data/artifacts/test_publication.py tests/integration/artifacts/test_publication_faults.py \
  tests/integration/artifacts/test_publication_recovery.py
```

Expected GREEN: target-absent pre-commit faults recover a byte-identical marked stage with no invented backup/tombstone or preserve the exact typed uncommitted-target failure state; existing-target pre-commit faults restore old bytes; clean refuses unsafe content without mutation; committed targets survive all cleanup faults; each exact remnant state recovers without touching unrelated paths.

- [ ] **Step 10: Commit 7B**

```bash
git add src/finproof/data/artifacts/publication.py src/finproof/data/artifacts/builder.py \
  tests/helpers/artifact_filesystem.py tests/unit/data/artifacts/test_publication.py \
  tests/integration/artifacts/test_publication_faults.py \
  tests/integration/artifacts/test_publication_recovery.py
git commit -m "feat: guard artifact publication and recovery"
```

#### Checkpoint 7C: Production builder boundary, unpublished candidate wrapper, and safe CLI

**Files:**

- Modify: `src/finproof/data/artifacts/__init__.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `tools/build_candidate_artifacts.py`
- Modify: `src/finproof/cli/main.py`
- Create: `tests/unit/cli/__init__.py`
- Create: `tests/unit/cli/test_build_data.py`
- Create: `tests/integration/artifacts/test_candidate_builder.py`
- Create: `tests/integration/artifacts/test_build_fixture.py`
- Modify: `tests/contract/test_artifact_resources.py`

**Interfaces:**

- Produces internal strict frozen `ArtifactPhysicalFileHash(path, kind, size_bytes, sha256)`, `ArtifactManifestIdentity(manifest_version, artifact_contract_version, artifact_set_id, dataset_version, logical_hash)`, and path-free `ArtifactWorkspaceTelemetry(mode, marker_owned, containment_verified, cleanup_completed, threads, memory_limit)`.
- Produces internal strict frozen `ArtifactBuildTelemetry(persistence_timestamp, max_live_fund_group_rows, max_writer_batch_rows, max_verifier_batch_rows, max_bronze_reconstruction_cells, linked_domestic_record_json_parses, linked_fund_record_json_parses, max_live_link_keys, max_live_evidence_keys, staging_workspace, verifier_workspace, physical_files, manifest_identity)`. `persistence_timestamp` is emitted only after manifest/Bronze/quality typed/quality-JSON consistency verification. Each workspace record requires mode `0o700`, marker/containment/cleanup booleans true, observed `threads=1`, and `memory_limit="1GiB"`; it contains no absolute/relative temp path. `physical_files` is the exact ordered 14-entry manifest physical inventory with lowercase verified SHA-256. All values are observed verified facts, not caller/config claims.
- Produces internal strict frozen `ArtifactBuildOutcome(manifest: ArtifactManifest, logical_contract: ExpectedPhase1ArtifactContract, telemetry: ArtifactBuildTelemetry)`. Closed `_build_evaluation_artifacts_with_outcome(...)` and candidate-transform functions return this outcome so the public wrapper/official child and repository candidate tool consume the same verified counters/identities without changing evaluation behavior.
- Completes public `build_artifacts(settings: Settings, versions: VersionBundle, *, options: ArtifactBuildOptions) -> ArtifactManifest`.
- Completes repository-only `build_candidate_artifacts(settings: Settings, versions: VersionBundle, *, options: ArtifactBuildOptions) -> ExpectedPhase1ArtifactContract`.
- CLI adds only `finproof build-data [--clean]`.

- [ ] **Step 11: Write 7C REDs for candidate non-publication and production expected comparison**

In `test_real_candidate_default_builds_before_baseline`, build the complete small fixture once through the real-default candidate wrapper while the repository source/resource are absent and assert it performs the production transform/full verify, returns canonical expected-contract data, removes its private candidate artifacts, does not publish, and does not write the expected file. This real-default success integration is explicitly a pre-baseline CP7/CP8-Step-2 test and will be converted in CP8 after the reviewed resource is installed.

In a separate permanent hermetic test, inject a synthetic `CandidateBaselineProbe` that reports both absent at the initial guard, allows one instrumented private transform, then flips source or resource present in `second_check()`. Assert `BASELINE_ALREADY_EXISTS`, zero stdout/contract return, complete marker-owned candidate-stage cleanup, and no publication/write. This is the authoritative post-transform race test before and after baseline creation; do not attempt to reach the second boundary through the real default once the packaged resource exists.

Separately test the private production transform directly and require a complete `ArtifactBuildOutcome`: exact manifest/logical-contract identity agreement, the verified injected persistence timestamp, observed fund/writer/verifier/reconstruction/key/parse maxima, staging/verifier workspace mode `0o700`, true marker/containment/cleanup facts, actual `threads=1` and `memory_limit="1GiB"`, and exact ordered 14 path/kind/size/SHA physical entries. Missing/duplicate/reordered physical entries, unverified hash/timestamp, false workspace fact, unexpected mode/settings, config-only counter values, path-bearing telemetry, or logical manifest identity mismatch fail strict construction. These internal transform tests remain permanently valid after baseline creation.

Reuse CP1's injected read-only `CandidateBaselineProbe`; its synthetic source/resource states cover absent, source present, packaged present, both present, and the post-transform flip described above. The production default probe is not injectable through CLI/public APIs. Assert candidate callable is absent from installed package modules, `finproof` exports, project scripts, and wheel. Once a synthetic expected source or resource exists at the initial guard, every candidate invocation refuses with zero transform calls. In evaluation mode, `build_artifacts` must fully verify the stage, load packaged expected contract, compare it, then publish; missing/mismatch blocks before publication. Extended-demo may receive only an explicitly different expected object through a separate typed internal tooling API and cannot alter evaluation behavior.

Expected RED: exact candidate wrapper/production expected-before-publish boundary is incomplete.

- [ ] **Step 12: Implement the two non-bypassable build modes**

Factor one private production transform that always creates and fully verifies a private stage and returns `ArtifactBuildOutcome`. The repository candidate sequence is exact: initial probe guard; private transform; retain only strict outcome/contract data in memory; marker-owned candidate-root cleanup and verification; `probe.second_check()`; then and only then emit one canonical compact contract JSON line to stdout and one canonical compact bounded/path-free telemetry JSON line to stderr/return the expected contract. Any transform, cleanup, or second-check failure emits no contract/telemetry and leaves no guessed cleanup. `_build_evaluation_artifacts_with_outcome` loads only packaged expected bytes, compares the fully verified stage, calls the guarded publisher, and returns the strict outcome; public `build_artifacts` is a no-option wrapper over that exact function and returns only `outcome.manifest`. The official subprocess helper is the sole test-side consumer of the internal evaluation outcome for telemetry. Neither mode accepts a public/private skip/update/accept/write-back flag, and no test seam can disable comparison in the public builder.

Export only `ArtifactManifest`, `ArtifactBuildOptions`, `build_artifacts`, and `open_read_only_database` from `finproof.data.artifacts`; do not export the private transform, publication filesystem, candidate wrapper, or recovery paths.

- [ ] **Step 13: Write 7C CLI REDs for arguments, time capture, output, and safe errors**

Assert parser accepts only `build-data` and optional `--clean`; reject timestamp, source, output, SQL, table, version, and expected-path arguments with argparse exit 2. Inject a clock seam and assert it is called once, UTC, then the exact timestamp reaches `ArtifactBuildOptions`.

Success stdout must be one compact sorted JSON line with only target basename, `manifest.json`, database-relative path, and logical hash. Typed failure returns 2 and exactly one `error: ...` stderr line with no stdout, stack trace, raw payload, absolute/source/stage/backup/recovery path. Post-commit cleanup failure returns 2 and explicitly says the new target was published and verified while marked old-generation cleanup remains incomplete, without claiming a complete backup.

Expected RED: CLI has no `build-data`, and current checkout-discovery bootstrap path is unsafe for this command.

- [ ] **Step 14: Implement explicit-settings CLI dispatch and run the complete 7C fixture gate**

`build-data` loads `Settings` directly, never calls `_load_repository_tool`, constructs `VersionBundle`, captures `datetime.now(timezone.utc)` once, and calls the builder. Use a narrow internal callable injection only for CLI unit tests; the production default is the real builder.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/cli/test_build_data.py \
  tests/integration/artifacts/test_candidate_builder.py \
  tests/integration/artifacts/test_build_fixture.py \
  tests/contract/test_artifact_resources.py \
  tests/contract/test_handoff_commands.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/cli src/finproof/data/artifacts tools/build_candidate_artifacts.py \
  tests/unit/cli tests/integration/artifacts/test_candidate_builder.py \
  tests/integration/artifacts/test_build_fixture.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/cli src/finproof/data/artifacts tools/build_candidate_artifacts.py \
  tests/unit/cli tests/integration/artifacts/test_candidate_builder.py \
  tests/integration/artifacts/test_build_fixture.py
test ! -e config/expected_phase1_artifacts.json
```

Expected GREEN: candidate is full-transform/full-verify but unpublished/unpackaged/no-write; evaluation build cannot skip expected comparison; CLI arguments/output/errors are closed and safe; the existing installed `verify-handoff`/`audit-source` CLI contracts remain unchanged; official baseline is still absent.

- [ ] **Step 15: Commit 7C, run aggregate Checkpoint 7 gates, and obtain a fresh review**

Commit:

```bash
git add src/finproof/cli src/finproof/data/artifacts tools/build_candidate_artifacts.py \
  tests/unit/cli tests/integration/artifacts tests/contract/test_artifact_resources.py
git commit -m "feat: add verified artifact build command"
```

Then run all Checkpoint 7 focused commands, including `tests/contract/test_handoff_commands.py`, unchanged regressions, source audit, handoff, schema catalog, and diff checks. Fresh review spans 7A/7B/7C and must independently attack same-count database substitution, public reader writes/external access, runtime-temp containment, exact-tree TOCTOU, every rename/marker/tombstone state, candidate/publication bypass, installed handoff/audit CLI regression, and CLI leakage. Require 0 Critical / 0 Important before any official baseline candidate is run.

---

### Checkpoint 8: Two official candidate reproductions, reviewed expected contract, and Phase 1 gate

**Files:**

- Create after candidate review only: `config/expected_phase1_artifacts.json`
- Modify after candidate review only: `pyproject.toml`
- Modify: `src/finproof/data/artifacts/resources.py`
- Modify: `tests/contract/test_artifact_resources.py`
- Modify after baseline creation: `tests/integration/artifacts/test_candidate_builder.py`
- Create: `tests/source_contract/test_official_artifact_build.py`
- Create: `tests/performance/test_official_artifact_memory.py`
- Create: `tests/helpers/official_artifact_subprocess.py`
- Create: `tests/conftest.py`
- Modify: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`
- Modify: `docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Produces the sole reviewed official `ExpectedPhase1ArtifactContract` source and byte-identical packaged resource.
- Produces a session-scoped official artifact fixture that launches one fresh child through the same closed `_build_evaluation_artifacts_with_outcome` called by public `build_artifacts`, first calls `ArtifactManifest.load(...).verify(root)`, then `compare_expected_artifact_contract`, and shares that verified generation plus child telemetry across all assertions in the process.
- Consumes the frozen internal `ArtifactBuildOutcome`/`ArtifactBuildTelemetry` from the fresh child and adds only externally measured wall duration, platform-normalized peak RSS bytes, and `sys.platform`; it does not infer counters from logs or expose a public telemetry/skip flag.

- [ ] **Step 1: Write the final resource/acceptance RED without creating or guessing baseline bytes**

Add a contract test that requires source `config/expected_phase1_artifacts.json`, packaged `finproof/resources/contracts/expected_phase1_artifacts.json`, runtime loader availability outside checkout CWD, byte/SHA equality, strict parse, and exact wheel inclusion. Add `test_active_standard_editable_expected_contract_loader_matches_source_outside_cwd`, which runs in the active uv editable from an unrelated CWD and compares the frozen metadata-fallback destination bytes/SHA to the repository expected-contract source. Add `test_standard_editable_expected_contract_loader_uses_distribution_fallback_when_src_shadows`, using a fresh real isolated normal editable install: the regular source package must shadow copied contract data while the exact metadata-located frozen destination supplies source-identical bytes/SHA, with no dev-mode-exact behavior. Add `test_built_wheel_expected_contract_loader_uses_importlib_resources_primary`: install the built wheel alone with dependencies, make metadata fallback fail if called, change to an unrelated CWD, assert exact three-resource inventory/no candidate module, copy in a synthetic artifact root, and successfully call the public manifest verifier/expected loader without a repository root. In new `tests/source_contract/test_official_artifact_build.py`, declare `pytestmark = pytest.mark.source_contract`; its missing-contract fixture refuses to run without the expected contract and its first assertion loads/verifies the artifact before comparing expected.

Run only the missing-resource tests:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py \
  tests/source_contract/test_official_artifact_build.py -q \
  -k "expected_contract_resource or expected_contract_required"
```

Expected RED: the official expected source/resource is absent. Do not satisfy this RED yet, do not add placeholder JSON, and do not add a Hatch force-include for a nonexistent path.

- [ ] **Step 2: Run two fresh-process official candidates at different UTC timestamps**

Before each process, re-run handoff/source audit and both candidate-absence checks. Use repository-only tooling, never `finproof build-data`, and capture stdout contract JSON separately from stderr review telemetry:

```bash
test ! -e config/expected_phase1_artifacts.json
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python -m tools.build_candidate_artifacts \
  --persistence-timestamp 2026-08-14T00:00:00.000001Z \
  > /private/tmp/finproof-task5-candidate-a.json \
  2> /private/tmp/finproof-task5-candidate-a-telemetry.json

test ! -e config/expected_phase1_artifacts.json
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python -m tools.build_candidate_artifacts \
  --persistence-timestamp 2026-08-14T00:00:01.999999Z \
  > /private/tmp/finproof-task5-candidate-b.json \
  2> /private/tmp/finproof-task5-candidate-b-telemetry.json
```

The module `main` is repository review tooling, not a `[project.scripts]` entry and not included in the wheel. Each subprocess must independently verify source, all 11 Parquets, two reports, complete manifest, timestamp consistency, exact links/evidence, self-contained DuckDB typed equality, and its own 14 physical file hashes; then remove its marker-owned temporary artifact root. Exit nonzero if cleanup is incomplete.

Require exactly one compact JSON line on each candidate stderr and parse it through strict `ArtifactBuildTelemetry`. Assert candidate A reports exactly `2026-08-14T00:00:00.000001Z`, candidate B exactly `2026-08-14T00:00:01.999999Z`, and the two timestamps differ while the stdout logical contracts remain equal. For both staging and verifier records, require mode `0o700`, marker-owned/containment-verified/cleanup-completed true, one thread, and `1GiB`; reject any telemetry key or value exposing a temp/stage/spill absolute or relative path. Thus stderr itself provides bounded ownership/cleanup evidence without leaking workspace locations.

`tests/helpers/official_artifact_subprocess.py` measures the child externally. Convert `resource.getrusage(...).ru_maxrss` to bytes as `value` on macOS and `value * 1024` on Linux; record `sys.platform`. Do not assert a machine-specific absolute RSS cap. Assert the architectural counters `max_live_fund_group_rows <= 16`, `max_writer_batch_rows <= 65_536`, and the strict workspace facts independently of RSS.

- [ ] **Step 3: Compare both candidate contracts and obtain independent candidate approval**

Run a separate independent comparison that parses both stdout files through `ExpectedPhase1ArtifactContract` and asserts byte-identical canonical JSON and equality of:

- artifact set/contract/dataset identities;
- exact nine input namespace/path/kind/size/SHA entries;
- all eleven names/grains/schema/count/sort/unique/logical hashes;
- `source_audit` and `quality_summary` semantic hashes;
- overall manifest logical hash;
- exact pair hash and evidence count.

Independently inspect telemetry proving each generation's physical hashes verified while timestamps differed. Recompute the official counts: Bronze 207/145,393/6,401,851; Silver 42,394/1,733/5,646/11,138/95,618 plus observed quality; two quarantined source rows; 47 links; 371 evidence; frozen pair hash. The review report must be 0 Critical / 0 Important before any repository expected-contract file is created.

If contracts differ logically, stop under `REPRODUCIBILITY_MISMATCH`; do not select one, average values, regenerate tests, or create a baseline.

- [ ] **Step 4: Create only the reviewed expected contract and make the RED resource test GREEN**

After Step 3 approval, use `apply_patch` to add the exact canonical candidate JSON plus one terminal newline as `config/expected_phase1_artifacts.json`. Add its exact Hatch force-include destination `finproof/resources/contracts/expected_phase1_artifacts.json` in the same change and complete `expected_phase1_contract_bytes()` through the already frozen dual loader. Do not add a repository path branch, caller path, parent discovery, or dev-mode-exact packaging exception.

Before refreshing the active distribution, run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run --no-sync pytest \
  tests/contract/test_artifact_resources.py::test_active_standard_editable_expected_contract_loader_matches_source_outside_cwd -q
```

Expected narrower RED: the reviewed repository source and force-include mapping now exist, but the active standard-editable distribution still lacks the expected-contract copied resource. Rebuild it before any candidate-transition or aggregate GREEN:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups \
  --reinstall-package finproof
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py::test_active_standard_editable_expected_contract_loader_matches_source_outside_cwd -q
```

Expected GREEN: outside the checkout CWD, the active metadata fallback now returns bytes/SHA equal to the reviewed source.

The new real packaged resource intentionally invalidates CP7's pre-baseline real-default candidate-success selector. After the reinstall, run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/integration/artifacts/test_candidate_builder.py::test_real_candidate_default_builds_before_baseline -q
```

Expected RED: `BASELINE_ALREADY_EXISTS` occurs at the initial real probe with zero transform calls. Then replace only that integration case with `test_real_candidate_default_permanently_refuses_after_baseline`, asserting the initial production guard refuses with zero transform calls, no stdout/stage/publication, and no attempt to reach the now-unreachable second boundary. Do not weaken or remove the permanent synthetic `CandidateBaselineProbe` post-transform flip/race tests or the private full-transform `ArtifactBuildOutcome` tests; run both families and prove they still cover the second check, cleanup, all guard branches, complete transformation, telemetry, and logical-contract extraction without a public bypass.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py \
  tests/integration/artifacts/test_candidate_builder.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv build --wheel \
  --out-dir /private/tmp/finproof-task5-wheel
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py::test_active_standard_editable_expected_contract_loader_matches_source_outside_cwd \
  tests/contract/test_artifact_resources.py::test_standard_editable_expected_contract_loader_uses_distribution_fallback_when_src_shadows \
  tests/contract/test_artifact_resources.py::test_built_wheel_expected_contract_loader_uses_importlib_resources_primary -q
```

Expected GREEN: expected source/resource bytes and SHA match through the real standard-editable metadata fallback and installed-wheel resources primary outside the checkout CWD; exact wheel inventory contains three frozen resources and no candidate tooling; installed verification needs only caller artifact root plus package resources; the real candidate tool now permanently refuses at the initial guard with zero transform calls; the synthetic flip still proves the post-transform second check and cleanup; private transform/outcome coverage remains green; the normal builder has no skip/update/accept path.

- [ ] **Step 5: Complete one published official build and reuse its verified session artifact**

Use a managed test artifact root under `/private/tmp`, not the repository `artifacts/`, for the official acceptance fixture. `tests/conftest.py` exposes one session fixture backed by `tests/helpers/official_artifact_subprocess.py`: it launches a fresh child with third explicit timestamp `2026-08-14T00:00:02.123456Z` through `_build_evaluation_artifacts_with_outcome`, the exact implementation wrapped by public `build_artifacts`, captures platform-correct wall/RSS/counter telemetry, and asserts `outcome.telemetry.persistence_timestamp` equals that exact value after timestamp consistency verification. The child compares the packaged expected contract before publication, then loads/verifies the published manifest and expected contract again in the parent. Both official source-contract and performance tests consume that same generation/telemetry. Cache only this exact fully verified generation by expected overall logical hash; later pytest processes may reuse it only after complete current-code verification, never trust path existence alone.

`test_official_artifact_build.py` asserts:

- exact nine inputs and 14 physical files/exact recursive tree;
- every table schema/count/sort/unique/logical hash and strict `record_json` projection round-trip;
- Bronze 207 columns, 145,393 rows, and 6,401,851 cells; reconstruct rows by a sorted bounded merge that consumes cell batches once, releases each completed source row immediately, and never holds more than the maximum source-table width of 73 cells;
- Silver counts 42,394 / 1,733 / 5,646 / 11,138 / 95,618;
- both malformed rows in Bronze plus canonical quarantined issues, excluded from normal Silver;
- one common manifest/Bronze/quality UTC timestamp and timestamp-free logical equality with candidates;
- 47/371, exact raw=trimmed pair-set acceptance, 1,222-byte TSV and frozen SHA;
- deterministic report semantics and observed nonfrozen issue count;
- DuckDB exact eleven tables, typed Parquet equality, no external paths/WAL, and public write/ATTACH/COPY rejection;
- expected-contract exhaustive equality and per-generation physical SHA verification.

`test_official_artifact_memory.py` declares `pytestmark = pytest.mark.performance` and consumes the session child telemetry rather than launching a fourth build or reading pytest's polluted process high-water mark. It checks the platform conversion and architectural counters independently of RSS.

Add a reconstruction sentinel to the official acceptance that raises on `len`, second cell iteration, list/DataFrame conversion, or retention of a completed row. Require `max_bronze_reconstruction_cells <= 73`, `max_verifier_batch_rows <= 65_536`, exactly 47 linked domestic and 47 linked fund JSON parses, and live link/evidence keys `<=47/371`; no acceptance assertion may materialize the 6,401,851-cell relation merely to compare counts.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/source_contract/test_official_artifact_build.py \
  tests/performance/test_official_artifact_memory.py -q \
  -m "source_contract or performance"
```

Record exact durations, platform-normalized RSS, live-group/batch maxima, table/report/overall hashes, and all physical hashes. An unexplained count/hash/memory/regression difference is a hard stop, not a baseline update.

- [ ] **Step 6: Run complete Phase 1 gates on the exact implementation tree**

Run once after all implementation/test/resource changes are frozen:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy src tests tools
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/source_contract -q -m source_contract
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/performance/test_artifact_external_staging.py \
  tests/performance/test_artifact_fund_streaming.py \
  tests/performance/test_artifact_verifier_bounds.py \
  tests/performance/test_official_artifact_memory.py -q -m performance
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/audit_source_data.py --check
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/verify_handoff.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/extract_schema_catalog.py --check
PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache \
  UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pre-commit run --all-files
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv build --wheel \
  --out-dir /private/tmp/finproof-task5-final-wheel
git diff --check
git diff --cached --check
git check-ignore -v artifacts/manifest.json artifacts/reports/source_audit.json \
  artifacts/parquet/bronze_source_row.parquet artifacts/finproof.duckdb \
  .artifacts.finproof-stage-op .artifacts.finproof-backup-op \
  .artifacts.finproof-cleanup-op .artifacts.finproof-build.lock
find source_material -type f -perm -u=w -print
```

Expected: every command passes; source audit remains 145,393/`2026-07-11`; handoff remains 61/9/41,384,928; catalog remains 207; ignore probes match; source writable search prints nothing. Record exact observed test counts/times rather than predicting them.

- [ ] **Step 7: Commit the reviewed baseline and acceptance evidence checkpoint**

Only after Steps 1-6:

```bash
git add config/expected_phase1_artifacts.json pyproject.toml \
  src/finproof/data/artifacts/resources.py tests/contract/test_artifact_resources.py \
  tests/integration/artifacts/test_candidate_builder.py \
  tests/source_contract/test_official_artifact_build.py \
  tests/performance/test_official_artifact_memory.py \
  tests/helpers/official_artifact_subprocess.py tests/conftest.py
git commit -m "test: freeze reviewed Phase 1 artifact contract"
```

The commit contains no runtime `artifacts/` file and no candidate telemetry/output under `/private/tmp`.

- [ ] **Step 8: Obtain whole-branch review before marking Task 5 or Phase 1 complete**

Dispatch a fresh reviewer over the approved plan base through the Step 7 commit. It must inspect every Task 5 source/test/config/schema/resource change, all eight checkpoint review results, exact two-candidate contracts/telemetry, official published acceptance, dependency/package boundaries, and Git scope. It must independently rerun the focused artifact suite, official acceptance or verified session reuse, Ruff, mypy, source audit, handoff, catalog, wheel resource check, exact-tree/ignored/source-read-only checks.

Any Critical/Important finding gets a focused RED, smallest correction, separate `fix: close Task 5 final review gaps` commit, complete relevant/mandatory gate rerun, and fresh re-review. Do not update the official baseline unless the reviewed correction intentionally changes logical data under a higher-priority approved decision; an unexplained mismatch is a stop condition.

- [ ] **Step 9: Record completion evidence and exact next task**

After whole-branch review is 0 Critical / 0 Important, update:

- this plan's completed checkboxes with observed RED/GREEN/review references;
- all eight legacy Task 5 checkpoint boxes;
- `docs/implementation/STATUS.md` with scope, every focused RED reason, checkpoint/review commits, table/report/overall logical hashes, physical reviewed-generation hashes, durations/RSS/bounds, exact commands/results, residual risks, and source-read-only/clean-tree evidence;
- Phase 1 Task 5 and Phase 1 gate checkboxes to complete;
- exact next task: **Phase 2 Task 1: implement deterministic domain contracts and registry loaders from the approved Phase 2 plan**.

Commit documentation separately:

```bash
git add docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md \
  docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md \
  docs/implementation/STATUS.md
git commit -m "docs: record Phase 1 artifact verification"
```

- [ ] **Step 10: Run the final reviewed-tree gate and leave a clean feature worktree**

Run the complete Step 6 gate again on the exact documentation/review-evidence tree, including the full suite, wheel, source checks, pre-commit, diff checks, ignored paths, and zero writable official files. Also run:

```bash
git status --short --branch
test -z "$(git status --porcelain=v1)"
git ls-files artifacts .artifacts.finproof-build.lock \
  '.artifacts.finproof-stage-*' '.artifacts.finproof-backup-*' \
  '.artifacts.finproof-cleanup-*'
```

Expected: all gates pass; porcelain is empty; tracked runtime-artifact query prints nothing; only the timestamp-free expected contract is tracked; Phase 2 Task 1 is the first incomplete task. Use `superpowers:finishing-a-development-branch` for the already authorized local integration flow, then rerun the mandatory gate on the exact integrated main commit before reporting completion.

## Plan self-review checklist

- [x] Every approved-spec section 1-17 maps to at least one checkpoint and executable assertion.
- [x] Checkpoint 1 cannot create/package official expected bytes; Checkpoint 8 requires two full candidates plus independent approval first.
- [x] Installed wheels use `importlib.resources` primary; real isolated standard editable installs prove only the exact distribution-metadata fallback under source-package shadowing; schema and expected-contract bytes/SHA/inventory are CWD-independent with no dev-mode-exact workaround.
- [x] Every force-included source/mapping change observes its deterministic pre-refresh RED with `uv run --no-sync`, explicitly reinstalls `finproof` in the active editable environment, and reruns outside-CWD byte/SHA equality with ordinary `uv run`; CP2 covers the stale manifest-schema copy and CP8 the new expected contract.
- [x] The candidate path is repository-only, unpublished, no-write, no-publish, and permanently closed after baseline creation.
- [x] CP2 has no premature table-aware/full verifier; CP3 freezes specs/Parquet; CP7 alone completes trusted DuckDB-aware verification.
- [x] `FundItemValue` projects only its representative normalized value/quality, with all equivalent/contributing lineage retained in strict `record_json`.
- [x] Public fund key classification and one-group adapter avoid private imports, SQL policy, and full/double normalization.
- [x] Incremental PyArrow produces one Parquet file from bounded batches, passes row-group size only to `write_table`, and computes header-first logical identity only from reopened typed rows after final count is known.
- [x] CP4 records only input/Bronze observations, CP5 extends Silver/quarantine, CP6 alone constructs the complete source-audit report, and CP7 persists/verifies it.
- [x] Bronze fan-out invokes one optional frozen `SourceRowConsumer` exactly once only after Bronze enqueue, and Silver consumes that seam without workbook rescan.
- [x] Public read-only DuckDB and private trusted equality verification are separate connections with separate security purposes.
- [x] CP5 owns the bounded relation-verifier protocol/stage implementation; CP7 supplies a private OS-temp implementation; neither materializes full Bronze cells or wide tables.
- [x] Exact recursive inventory, hardlink/special/WAL rejection, descriptor identity checks, and marker-owned runtime temp/publication deletion cover TOCTOU and broad-delete risks.
- [x] Successful staging cleanup removes only store-owned DB/WAL/spill/temp/markers before reports/manifest while preserving verified outputs and publication ownership.
- [x] First publication into an absent target separately covers verification failure, stage-marker unlink failure, and failed target-to-stage rollback without inventing backup/tombstone state or touching unrelated siblings.
- [x] CP7 has separate 7A database/verifier, 7B publisher/recovery, and 7C builder/candidate/CLI RED-GREEN commits before review.
- [x] Every independent behavior uses a recorded named-selector RED/smallest-GREEN loop; grouped commands are aggregate gates only.
- [x] CP1 owns the logical-contract and candidate-probe protocols; the real candidate succeeds only pre-baseline, synthetic flip covers its second guard permanently, and post-baseline real default refuses before transform.
- [x] Strict path-free outcome telemetry proves verified timestamp, bounded counters, workspace ownership/settings/cleanup, exact 14 physical hashes, and manifest identity while the public builder still returns only a manifest.
- [x] Official tests reuse one fully reverified session generation; candidate and memory measurements run in fresh processes with platform-correct RSS conversion.
- [x] Every newly created source-contract/performance test module carries its explicit module-level `pytestmark`.
- [x] Task 1-4 behavior, official inputs, Phase 2+, runtime artifact tracking, and release behavior remain unchanged.
