# Phase 1 Task 5 Artifact Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, verify, and safely publish the reproducible Phase 1 Bronze/Silver/Gold Parquet and self-contained DuckDB artifact set, then freeze its independently reviewed timestamp-free logical contract.

**Architecture:** An offline builder verifies the exact nine logical inputs, streams verified workbooks through bounded external staging, writes eleven frozen Parquet tables and two semantic reports, materializes the same typed content into DuckDB, and verifies every logical and physical boundary before guarded publication. Operational timestamps and physical hashes prove one generation's provenance and integrity; canonical table/report/manifest hashes plus the separately packaged expected contract prove logical reproducibility across builds.

**Tech Stack:** Python 3.12, Pydantic 2, PyArrow/Parquet, DuckDB 1.5, Polars where already used, JSON Schema Draft 2020-12 with `FormatChecker`, PyYAML, pytest, Ruff, mypy, uv/Hatch.

## Global Constraints

- Governing authority is `docs/superpowers/specs/2026-08-14-phase1-task5-artifact-build-design.md`, D-014, D-017, D-021, D-022, D-023, D-024, and D-025. Stop and log any conflict instead of reconciling it in code.
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
- `config.py`: strict immutable `ArtifactBuildConfig`, exact production baseline loader,
  and Task5 held-stream config/registry parsers; source-manifest held-stream parsing
  remains owned by `source_manifest.py`.
- `resources.py`: checkout-independent closed runtime-resource loader: installed-wheel `importlib.resources` primary plus the one standard-editable `importlib.metadata.distribution("finproof").locate_file(...)` fallback required by the frozen destinations.
- `expected_contract.py`: private strict baseline-neutral structural payload, stricter
  timestamp-free official expected-contract model, held-file loader, and exhaustive
  comparator with canonical RFC 6901 difference paths.
- `hashing.py`: canonical scalar/JSON/row/schema/table/report/manifest hash primitives.
- `manifest.py`: strict manifest models/schema load, the narrow input-identity view,
  CP2-owned opaque held-root adoption, recursive physical inventory and entry reopen
  capability, internal staged verification kernel, and—only after CP8 installs the
  reviewed expected resource—public `VerifiedArtifactSet`; it never imports concrete
  input identity, staging, or publication.
- `table_specs.py`: the sole frozen eleven-table schema/name/type/key/path registry.
- `serialization.py`: exact strict-model `record_json`, wide projections, Bronze/quality/Gold row projections.
- `parquet_io.py`: capability-bound fixed-schema writer, common bounded stream/unique
  checker, pre-manifest staged verification, and distinct final-inventory adapter.
- `input_identity.py`: no-follow held-nine input verification, its one-use issuance
  seal, trusted-Settings recomputation through one instance-owned resolved bundle, the
  direct-init-disabled descriptor-owning logical-input carrier, and its
  source-manifest/schema-catalog hash bindings; it imports only manifest's narrow view/
  input model plus CP1 resolver types.
- `staging.py`: build advisory lock, build-stage/working markers, held descriptor
  custody, Parquet/database leaves, one-thread/1-GiB bounded stores, abort/discard,
  cleanup, the non-transitioning instance-owned candidate-stage custody capability,
  and its typed atomic expected-accepted transfer boundary without global registries.
- `bronze.py`: source-catalog/row/cell emission and source-audit observations.
- `silver.py`: non-fund normalization staging and one-item-at-a-time public-fund collapse.
- `quality_persistence.py`: D-021 timestamp injection, schema validation, and Bronze joins.
- `reports.py`: the sole exact source-audit and quality-summary models, nested contracts,
  semantic projections/hashes, and later phased producers/verifier port.
- `links.py`: exact link/evidence models, raw join, conflicts, pair hash, and bidirectional evidence checks.
- `database.py`: self-contained DuckDB construction, read-only open, and bounded typed `EXCEPT ALL` verification.
- `publication.py`: target/backup/tombstone marker ownership, expected-authorization
  transition ports, guarded rename/rollback/commit, target recognition, and remnant
  recovery; it consumes staging custody but staging never imports it.
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
- Produces private `ArtifactLogicalContractPayload`, which has the exact strict
  baseline-neutral structural shape, and public/internal
  `ExpectedPhase1ArtifactContract` as its official-value-constrained subtype. Produces
  `ExpectedPhase1ArtifactContract.load(path: Path) -> ExpectedPhase1ArtifactContract`
  and `compare_expected_artifact_contract(actual: ArtifactLogicalContractView,
  expected: ExpectedPhase1ArtifactContract) -> None`; the expected dataset version is
  exactly `2026-07-11`, the loader rejects every symlink path component and reads
  through a held no-follow descriptor chain with identity checks, and the comparator
  first reconstructs actual through `ArtifactLogicalContractPayload` before canonical
  comparison. Thus `bool`/`int`, wrong nested scalar/container types, missing
  properties, and reordered inventories fail as `invalid_actual_contract`, while every
  well-shaped wrong baseline value—including a row count—appears in complete RFC 6901
  difference paths. Checkpoint 8's `VerifiedArtifactSet` structurally conforms to this
  CP1-owned protocol.
- Produces closed `RuntimeArtifactResource(StrEnum)` values for exactly `finproof/resources/schemas/artifact_manifest.schema.json`, `finproof/resources/schemas/quality_issue.schema.json`, and, only after Checkpoint 8, `finproof/resources/contracts/expected_phase1_artifacts.json`; no public or internal loader accepts a caller-supplied path.
- Produces: `artifact_manifest_schema_bytes() -> bytes`, `quality_issue_schema_bytes() -> bytes`, and, only after Checkpoint 8, `expected_phase1_contract_bytes() -> bytes`. Each calls one internal closed loader that uses `importlib.resources` as the installed-wheel primary. Its sole fallback calls `importlib.metadata.distribution("finproof").locate_file(exact_frozen_destination)` for standard Hatch editable shadowing, then requires that the distribution-relative destination is unchanged, every existing component from the distribution root through the destination is nonsymlink, and the leaf is an existing regular file opened through a held no-follow descriptor with before/opened/after identity checks. Neither route uses CWD, repository/source parent discovery, caller paths, or a path search.
- Produces internal `CandidateBaselineProbe(Protocol)` with `source_exists() -> bool`, `resource_exists() -> bool`, and `second_check() -> None`, plus a production probe that checks the real repository expected source and packaged expected resource without exposing their paths. CP1's repository-only `assert_candidate_bootstrap_allowed(probe: CandidateBaselineProbe) -> None` performs only the initial absent/source-present/resource-present guard; Checkpoint 7's actual wrapper owns the post-transform `second_check` race boundary.

- [x] **Step 1: Establish clean preconditions and prove the official baseline is absent**

Run:

```bash
python3 tools/verify_handoff.py
python3 tools/audit_source_data.py --check
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
git status --short
```

Expected: handoff reports 61 required files, 9 official inputs, and 41,384,928 bytes; source audit reports 145,393 rows at `2026-07-11`; both expected-contract paths are absent; only the approved Task 5 plan commit is present before implementation starts.

- [x] **Step 2: Write focused REDs for repository anchoring, path safety, options, and safe errors**

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

- [x] **Step 3: Confirm the accumulated serial settings/options/error boundary**

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

- [x] **Step 4: Write REDs for the exact artifact config, expected model, packaged schemas, and candidate refusal**

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

- [x] **Step 5: Finish the serial foundations and synchronize their assembled dependency/resource state**

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

- [x] **Step 6: Run GREEN and checkpoint gates**

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

- [x] **Step 7: Run regressions, commit, and obtain a fresh review**

Run the unchanged Task 1-4 regression command, `git diff --check`, and verify `find source_material -type f -perm -222 -print` returns no path. Commit:

```bash
git add pyproject.toml uv.lock .env.example .gitignore config/artifact_build.yaml \
  src/finproof/core/settings.py src/finproof/data/artifacts src/finproof/resources \
  tools/build_candidate_artifacts.py tests/helpers/artifacts.py \
  tests/unit/core/test_artifact_settings.py tests/unit/data/artifacts \
  tests/contract/test_artifact_resources.py
git commit -m "feat: add artifact build foundations"
```

Fresh review must specifically check protected-path aliases/symlinks, error-path leakage, duplicate YAML keys, runtime dependency/resource loading outside the checkout CWD, deep immutability, baseline absence, and candidate non-publication/non-packaging. Do not start Checkpoint 2 until review is 0 Critical / 0 Important.

Observed completion evidence on 2026-08-15:

- Reviewed CP1 commits: `2546833`, `fa7b98e`, and final correction `756a791`.
- Final independent review at `756a791`: Critical 0 / Important 0 / Minor 0.
- Exact CP1 focused suite: 277 passed; unchanged Task 1–4 regression: 533 passed;
  reviewer-selected focused regression: 12 passed.
- Full implementation suite: 920 passed in 574.36 seconds. Ruff format/check and
  mypy passed over 91 source files.
- Source audit remained 145,393 rows at `2026-07-11`; handoff remained 61 required
  files, 9 official inputs, and 41,384,928 bytes; schema catalog remained 207 columns.
- The final worktree was clean, official source files remained read-only, and the
  official expected-contract source remained absent.
- Exact next task: Checkpoint 2, strict manifest, recursive inventory, and canonical
  logical hashing. Task 5, the Phase 1 gate, and Checkpoints 2–8 remain incomplete.

---

### Checkpoint 2: Strict manifest, recursive inventory, and canonical logical hashing

**Files:**

- Modify: `schemas/artifact_manifest.schema.json`
- Modify: `src/finproof/data/artifacts/errors.py`
- Modify: `src/finproof/data/artifacts/expected_contract.py`
- Create: `src/finproof/data/artifacts/hashing.py`
- Create: `src/finproof/data/artifacts/manifest.py`
- Create: `src/finproof/data/artifacts/reports.py`
- Create: `tests/unit/data/artifacts/test_hashing.py`
- Create: `tests/unit/data/artifacts/test_manifest.py`
- Create: `tests/unit/data/artifacts/test_reports.py`
- Modify: `tests/unit/data/artifacts/test_foundations.py`
- Create: `tests/contract/test_artifact_manifest_schema.py`
- Modify: `tests/contract/test_artifact_resources.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Produces: `canonical_json_bytes(value: object, *, terminal_newline: bool = True) -> bytes` and `canonical_scalar(value: object) -> object`.
- Produces internal `ColumnSpecIdentity` with exact `name`, `logical_type`,
  `arrow_type`, `duckdb_type`, and `nullable` properties. Produces internal
  `TableSpecIdentity` with exact `table_name`, `grain`, ordered
  `tuple[ColumnSpecIdentity, ...]`, `unique_key`, `sort_key`, and
  `logical_projection`. Checkpoint 3's frozen `ColumnSpec`/`TableSpec` implement these
  protocols directly.
- Produces exact `schema_sha256(spec: TableSpecIdentity) -> str`,
  `table_logical_hash(spec: TableSpecIdentity, *, row_count: int,
  rows: Iterable[Mapping[str, object]]) -> str`,
  `report_logical_hash(report: SemanticReportIdentity) -> str`, and
  `manifest_logical_hash(manifest: ManifestLogicalIdentity) -> str`.
- Produces strict frozen `ArtifactInput`, `ArtifactVersions`, `ArtifactFile`,
  `ArtifactTable`, and `ArtifactManifest`, plus the live internal
  `VerifiedPhysicalEntry`/`VerifiedPhysicalInventory` capability from design section
  10.2. It imports CP1's exact `ExpectedLogicalInput`, `ExpectedLogicalTable`,
  `ExpectedSemanticReport`, and `ArtifactLogicalContractView`; it defines no competing
  expected-entry types and no CP7 `VerifiedArtifactSet`.
- Produces: `ArtifactManifest.load(path: Path) -> ArtifactManifest`.
- Produces internal `verify_declared_inventory(manifest: ArtifactManifest, root: Path)
  -> VerifiedPhysicalInventory`, which reparses `root/manifest.json` through the held
  root and whose `open_verified` is the only final-artifact reopen boundary. It is
  unavailable to CP4-6 pre-manifest construction, which uses CP3's distinct staged
  contract over CP4's owned leaf.
- Produces internal `ClosedTableSpecRegistry`, `ArtifactTableVerifier`,
  `VerifiedTableHandle`, `TableVerificationResult`, `ArtifactReportVerifier`, `ArtifactDatabaseVerifier`,
  `ArtifactExpectedComparator`, `ReportVerificationResult`,
  `ArtifactCoreVerificationResult`, `ArtifactExpectedVerificationResult`, and
  `ArtifactVerificationKernel` with the CP2-approved path-root signatures. Design
  section 10.2 additionally freezes the CP7/8 managed-root extension; CP2 does not
  preimplement that future stage-custody entry.
  The CP2-approved `verify_candidate_core` orders inventory -> tables -> reports ->
  overall -> database -> final rescan; `verify_expected` inserts expected between
  database and final rescan. CP7/8 later add the design-section-10.2 managed-root
  entries over the same private execution path so a held stage is never reconstructed
  as a raw path, descriptor, basename, or from a stage object's private fields.
  Missing required ports fail before filesystem work. CP2 production leaves all five
  ports unavailable and therefore cannot return an internal result; no caller-supplied port
  enters a public API.
- `TableVerificationResult` disables direct construction and exposes only
  `from_verified(*, inventory, tables, handles)` plus `validate_against(inventory)`.
  Its exact CP1 logical entries and eleven handles must match one-to-one, and every
  handle entry must be the exact object-identity-owned member of that still-live
  inventory through `inventory.require_owned(entry)`. Report/overall/database stages
  revalidate that same immutable result; CP3's final-only `VerifiedParquetTable`
  implements the handle and CP7 may reopen it only through
  `inventory.open_verified(handle.entry)`. `StagedParquetHandle` has no entry and cannot
  implement or enter this result.
- Adds exact error code `ArtifactErrorCode.VERIFICATION_INCOMPLETE`; missing kernel
  ports fail before filesystem work with `reason=missing_verification_ports` and unique
  sorted port names as compact canonical JSON in string-only internal context.
- Produces the exact strict `SourceAuditReport`/`QualitySummaryReport` field inventories,
  nested entry models, tuple order, equality/group invariants, and
  `semantic_projection()` contracts from design section 7. CP2 constructs only
  synthetic report fixtures; CP5/6 own real semantic producers and CP7 owns report-file
  reparse/verification.
- Tightens CP1 expected models to literal artifact identity, exact official date,
  lowercase SHA-256, exact tuple entry types/order/grains, nonnegative exact-int
  sizes/counts, known non-quality counts, frozen pair hash, and evidence 371. Updates
  `compare_expected_artifact_contract` to include every unique sorted RFC 6901 pointer
  in canonical JSON `internal_context["difference_paths"]` without any differing value.

The CP2 report implementation uses these exact top-level declaration orders (nested
models and invariants are copied verbatim from design section 7):

```text
SourceAuditReport:
  report_id, report_contract_version, artifact_contract_version,
  source_snapshot_date, source_manifest_sha256, schema_catalog_sha256,
  source_tables, silver_tables, quarantine_source_rows, exact_links,
  exact_link_evidence, exact_link_pair_sha256

QualitySummaryReport:
  report_id, report_contract_version, artifact_contract_version, total_issues,
  distinct_affected_source_rows, by_source_table, by_rule, by_severity,
  by_quality_status, by_quarantine_flag, quarantined_issue_count,
  quarantined_source_row_count, excluded_silver_records,
  quality_table_logical_hash
```

For both, `semantic_projection()` contains every top-level field exactly once in that
order and recursively uses the exact nested declaration order; it has no parameter and
accepts no caller projection. The canonical hash sorts JSON object keys, so declaration
order is an independently tested model/API contract rather than a hidden source of hash
variation.

- [x] **Step 1: Execute the exact serial hashing skeleton/behavior selector loop**

Create `test_hashing.py` with a test-only canonical encoder that imports no production
hashing. Author and close only one selector before adding the next. For the first
selector, run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py::test_canonical_json_bytes_null -q
```

Expected skeleton RED: import of `finproof.data.artifacts.hashing` fails. Add only the
six public function names (`canonical_scalar`, `canonical_json_bytes`, and the four
hash functions) plus the four exact internal identity protocols; only the function
bodies raise `NotImplementedError("canonical hashing unavailable")`. Rerun the same
selector.
Expected narrower RED: that exact `NotImplementedError`. Implement only the null case
and terminal-newline switch, rerun to GREEN, then execute this exact one-selector-at-a-
time order:

```text
test_canonical_json_bytes_exact_bool_int_and_text
test_canonical_decimal_zero_trailing_scale_and_decimal_38_18_bounds
test_canonical_datetime_date_enum_and_pure_posix_path
test_canonical_mapping_and_array_order_utf8_and_newline
test_canonical_scalar_rejects_float_subclasses_and_unsupported_values
test_column_and_table_identity_protocols_reject_every_wrong_shape
test_schema_hash_uses_exact_identity_projection
test_schema_hash_changes_only_for_identity_fields  # derived first-GREEN acceptance
test_table_hash_writes_exact_header_before_first_row
test_table_hash_requires_exact_logical_projection_keys
test_table_hash_consumes_rows_once_and_requires_exact_final_count
test_report_hash_uses_only_closed_semantic_projection
test_manifest_hash_uses_only_closed_logical_projection
```

For each selector except the explicitly labeled derived acceptance selector, run exactly
`UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest
tests/unit/data/artifacts/test_hashing.py::<selector> -q`, observe every parameter ID
fail for the one missing branch/invariant, implement only that branch, and rerun the
same selector to GREEN before authoring the next selector. The independent encoder
asserts exact bytes for all design-section-8.1 scalars. The Decimal family includes
nonfinite, >18 fractional digits, >20 integer digits, exponent expansion, and no-
rounding failures. The temporal family requires six microseconds, naive local time with
no suffix, exact-zero-offset aware time with `Z`, and rejects every nonzero offset.

`test_schema_hash_changes_only_for_identity_fields` is authored only after
`test_schema_hash_uses_exact_identity_projection` is GREEN. It must pass on its first
run because it is a derived metamorphic acceptance of that already RED-driven generic
projection algorithm; it is never cited as new-behavior RED evidence and production
code must not be weakened or special-cased to manufacture a failure.

The protocol selector uses synthetic objects to require exact tuples, exact strings,
exact bool nullability, unique columns, existing unique/sort/projection columns, and a
nonempty unique logical projection. The exact table header is:

```python
expected_header = {
    "schema_sha256": schema_hash,
    "logical_projection": ["id", "value"],
    "row_count": 2,
}
```

Path/layer/compression mutations stay invariant; table name, grain, ordered column
name/logical/Arrow/DuckDB/nullability, unique key, or sort key changes schema identity.
Logical-projection/header/count/row changes alter table identity. A sentinel raises if
the row iterator is requested before the header, iterated twice, measured with `len`,
or retained/materialized. Use only synthetic rows; CP3 owns operational table
projections.

- [x] **Step 2: Run the hashing aggregate only after every selector is GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py -q
```

Expected GREEN: production bytes match the independent encoder; schema/table/report/
manifest hashes contain no path, layer, writer option, persistence timestamp, physical
size/hash, database bytes, or arbitrary model dump. Record this only as an aggregate
gate, never as RED evidence.

- [x] **Step 3: Execute exact strict-report, manifest, inventory, and kernel selector loops**

Author and close each selector below in exactly this order. Each command is
`UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest <file>::<selector> -q`;
every parameter ID must reach the intended assertion. Except for the one selector
explicitly labeled derived first-GREEN acceptance, a missing module/symbol permits
only a raising skeleton, followed by the same selector's narrower behavioral RED.
The one force-included schema transition has an inline pause described immediately
after the ordered list; it is closed RED -> GREEN before the next selector begins.

```text
tests/unit/data/artifacts/test_reports.py::test_source_audit_report_exact_fields_and_declaration_order
tests/unit/data/artifacts/test_reports.py::test_source_audit_report_exact_semantic_projection
tests/unit/data/artifacts/test_reports.py::test_source_audit_report_rejects_every_inventory_and_inequality
tests/unit/data/artifacts/test_reports.py::test_quality_summary_report_exact_fields_and_declaration_order
tests/unit/data/artifacts/test_reports.py::test_quality_summary_report_exact_semantic_projection
tests/unit/data/artifacts/test_reports.py::test_quality_summary_rejects_group_order_duplicates_and_aggregate_mismatch
tests/unit/data/artifacts/test_manifest.py::test_artifact_manifest_exact_valid_shape
tests/unit/data/artifacts/test_manifest.py::test_artifact_file_requires_explicit_report_null_policy
tests/unit/data/artifacts/test_manifest.py::test_artifact_manifest_rejects_each_inventory_path_version_and_scalar_mutation
tests/contract/test_artifact_manifest_schema.py::test_artifact_manifest_schema_accepts_only_exact_model_shape
tests/contract/test_artifact_resources.py::test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd
tests/contract/test_artifact_manifest_schema.py::test_artifact_manifest_schema_checks_every_format_error  # derived first-GREEN acceptance
tests/unit/data/artifacts/test_manifest.py::test_manifest_load_parses_only_without_opening_declared_files
tests/unit/data/artifacts/test_manifest.py::test_verified_inventory_exact_tree_and_entry_identities
tests/unit/data/artifacts/test_manifest.py::test_verified_inventory_rejects_every_unsafe_tree_shape_without_mutation
tests/unit/data/artifacts/test_manifest.py::test_verified_inventory_binds_manifest_to_held_root
tests/unit/data/artifacts/test_manifest.py::test_verified_entry_reopen_rejects_forged_foreign_or_copied_entry
tests/unit/data/artifacts/test_manifest.py::test_verified_entry_reopen_rejects_each_leaf_parent_and_root_swap
tests/unit/data/artifacts/test_manifest.py::test_inventory_detects_same_inode_same_size_byte_mutation_between_stages
tests/unit/data/artifacts/test_manifest.py::test_inventory_fails_closed_without_descriptor_scandir_or_nofollow_support
tests/unit/data/artifacts/test_manifest.py::test_verification_kernel_requires_every_port_before_filesystem_work
tests/unit/data/artifacts/test_manifest.py::test_table_verification_result_requires_exact_live_inventory_owned_entries
tests/unit/data/artifacts/test_manifest.py::test_verification_kernel_exact_expected_order_and_short_circuit
tests/unit/data/artifacts/test_manifest.py::test_verification_kernel_candidate_core_skips_only_expected
tests/unit/data/artifacts/test_foundations.py::test_expected_contract_enforces_literals_hashes_counts_and_grains
```

For `test_artifact_manifest_schema_accepts_only_exact_model_shape`, the first ordinary
`uv run` is RED because the legacy schema rejects the approved valid fixture. Implement
the exact root schema, then rerun that same selector with `uv run --no-sync` to GREEN.
Before any other selector or command, author the immediately following resource
selector and run it with `uv run --no-sync`; expected RED is now only that the active
standard-editable metadata fallback still returns the old bytes/SHA while the root
schema is valid. Run exactly:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups \
  --reinstall-package finproof
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py::test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd \
  tests/contract/test_artifact_resources.py::test_active_standard_editable_schema_loader_matches_current_repository_sources_outside_cwd -q
```

Expected GREEN: manifest and unchanged quality schema bytes/SHA match outside the
checkout CWD. Only then resume the list with the format-error selector using ordinary
`uv run`. Thus no RED remains open while another behavior is authored, and no ordinary
`uv run` can auto-refresh away the required stale-resource RED.

The format-error selector is a derived first-GREEN acceptance, not new-behavior RED
evidence: the preceding exact-root-schema selector freezes the complete schema,
including every SHA/path/date-time `format` and pattern rule from design Section 10.1.
After resource refresh, the format-error selector independently mutates each frozen
format and must pass on its first run. Do not omit and later re-add a format rule or
special-case production/schema content merely to manufacture a RED.

The first source-audit selector gets only an importable symbol skeleton that rejects the
otherwise-valid full fixture; rerun that same fields/order selector to prove the
narrower RED, then implement only its exact fields/nested types/declaration order and
rerun GREEN. Only then author the semantic-projection selector: its first RED is the
still-raising `NotImplementedError("report projection unavailable")`; implement the
exact projection and rerun GREEN before authoring the invariant selector. Repeat that
same three-selector sequence independently for quality summary. Thus no report's field
inventory/order or projection is implemented without its own focused RED. The
first manifest selector gets only importable strict model skeletons that reject the
valid fixture; rerun before implementing shape validation. The first inventory selector
gets only `verify_declared_inventory` raising
`NotImplementedError("physical inventory unavailable")`; rerun before any traversal.
The first kernel selector gets the exact protocols/signatures with both
`verify_candidate_core` and `verify_expected` raising
`NotImplementedError("verification kernel unavailable")`; rerun before dependency or
order behavior. Do not add a later selector until its predecessor is GREEN.
The expected-constraint RED parameter family contains only CP2-missing cases (wrong
artifact/set literal, uppercase/malformed hash, negative/bool count, wrong grain, wrong
known non-quality count, pair hash, and evidence count), and every ID must fail by
being accepted before the GREEN. CP1's already-rejected dataset date/inventory reorder/
wrong entry type cases run afterward as regression assertions, not claimed REDs.

`tests/helpers/artifacts.py` creates one complete synthetic tree: held-root
`manifest.json`, eleven Parquet-named regular files, two strict reports,
`finproof.duckdb`, and only `parquet/`/`reports/` directories. Manifest tests cover exact
9-input, 14-file, and 11-table order/kinds; exact versions/literals; deep immutability;
safe canonical POSIX paths; lowercase SHA-256; nonnegative exact-int sizes/counts;
terminal-`Z`; database/file identity; and the required explicit `report_id`/
`logical_hash` nulls. Inventory attack IDs are extra-file, extra-directory, file-
symlink, directory-symlink, FIFO, socket, device when supported, hardlink,
missing-file, WAL, canonical/case duplicate, size mismatch, checksum mismatch,
manifest-from-other-root, root swap, parent swap, leaf swap, and post-read rescan swap.
Snapshot every target byte first and require byte identity after every refusal.
The dedicated same-inode selector mutates one byte in place without changing length
after initial inventory, once during an `open_verified` consumer and once between the
database/expected stages and final rescan. It requires post-consumer and final
`assert_unchanged()` SHA rejection respectively, with no result escape.

The report fixtures use every exact field and nested type from design section 7. They
prove source table order, Silver order, expected=observed construction, lexical report
groups, `False` then `True`, aggregate equality, strict no-extra/no-omission, and
semantic-path invariance. They do not create real build observations.

The expected-route order spy records exactly:

```python
["inventory", "tables", "reports", "overall", "database", "expected", "rescan"]
```

The candidate-core spy records exactly the same list without `"expected"`. Inject one
failure at every reachable element of both routes and assert no later call, no returned
core/expected result, and closed inventory descriptors. Synthetic table
port returns a factory-created live-inventory-owned `TableVerificationResult`; the
synthetic report port returns `ReportVerificationResult` containing only CP1 expected
report-entry types. A valid all-stub run may return
the route-specific internal result for orchestration testing, but production CP2 assembly has
missing later ports and cannot run.

The table-result selector first proves the direct constructor is unavailable, then
uses `from_verified` with one forged structurally equal entry, one entry from another
live inventory, one copied handle, one closed owner, and each table/handle identity
mismatch. Every case is rejected. The valid result calls `validate_against` at each
downstream boundary and becomes invalid immediately when its owner closes; structural
dataclass equality is never an ownership check.

After every serial behavior selector is GREEN, add
`test_cp2_exports_no_public_manifest_verify_or_verified_artifact_set` and run it once as
a negative-capability regression fence. It must be first-GREEN because CP2 has never
introduced either public symbol; it is acceptance evidence, not a production behavior
RED/GREEN cycle.

After the serial loops, run this aggregate only:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/contract/test_artifact_manifest_schema.py -q
```

Expected GREEN: all strict structural, report, inventory, root-binding, kernel, and
expected-comparator behaviors are present. This aggregate is not RED evidence.

- [x] **Step 4: Implement the exact schema, strict models, load, and all-or-nothing inventory**

This step is the implementation summary for the serial GREEN changes above, not
permission for batch implementation after one RED. Replace the legacy schema with the
exact Section 10.1 model and explicit report null policy. Call
`Draft202012Validator.check_schema`, construct it with `FormatChecker`, collect every
error, and reject before opening declared files. `load` reads only its manifest leaf
through the held-file reader and parses schema/domain; it does not touch a declared
artifact file.

Implement descriptor traversal only as `os.scandir(held_directory_fd)` followed by
`DirEntry.stat(follow_symlinks=False)`; `os.scandir` itself receives no
`follow_symlinks` keyword. Open required child directories/leaves relative to retained
parent descriptors with `O_DIRECTORY`/`O_NOFOLLOW`, compare `DirEntry.stat` to `fstat`,
require regular-file `st_nlink == 1`, stream size/SHA through the held leaf, then
after every consumer re-stream exact size/SHA from that same held descriptor before
descriptor-relative restat and rescan. Retain root/required-directory descriptors in
the live `VerifiedPhysicalInventory` through every `open_verified` call. Reach the
absolute root from the filesystem anchor through a retained no-follow directory-
descriptor chain, and identity-revalidate every ancestor/root through its held parent.
Reparse held-root `manifest.json`, require it be a nonsymlink regular file with
`st_nlink == 1`, and require exact manifest-model equality. Reject unavailable fd-
scandir/no-follow support and every close/revalidation failure; do not fall back to
`Path.iterdir`, lexical `resolve`, or precheck/reopen.

Implement `assert_unchanged()` as a content check, not merely an inode/tree scan: reopen
all fourteen exact-owned entries through retained parents, recheck identity/type/link,
stream declared size/SHA, reparse/equality-check held `manifest.json`, and only then
repeat ancestor/exact-tree inventory. It runs immediately before every stage reopen and
at both kernel routes' final rescan.

Implement the exact design-section-10.2 kernel ports/result/order. Overall reconstruction
uses declared logical inputs/versions, verified CP1 table/report entries, and only the
report result's pair hash/evidence count. It compares the recomputed overall hash with
the manifest before database. The expected route compares after database; the guarded
candidate-core route skips only that comparison. Both rescan before their distinct
internal result type escapes. CP2 production wiring intentionally cannot call either
route under D-024.

- [x] **Step 5: Reconfirm the already-closed editable resource boundary**

The stale-resource RED/reinstall/GREEN occurred inline at its exact serial position in
Step 3. Run the two resource selectors again as regression only:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/contract/test_artifact_resources.py::test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd \
  tests/contract/test_artifact_resources.py::test_active_standard_editable_schema_loader_matches_current_repository_sources_outside_cwd -q
```

Expected GREEN: from an unrelated CWD, the source package shadows copied data, the
metadata fallback resolves only the frozen schema destinations, and both bytes/SHA
values equal their root sources. This is regression evidence, not a second behavior
cycle.

- [x] **Step 6: Close new expected-difference selectors, then run independent mutation acceptance**

Author and close only these two still-new production behaviors one at a time:

```text
test_expected_comparator_reports_every_nested_difference_without_writeback
test_internal_difference_paths_escapes_tokens_and_root_pointer
```

The expected selector rewrites/reloads only its temporary expected
file with valid outer syntax/hashes, so strict reconstruction succeeds before comparison.
The public comparator selector mutates reachable fixed contract fields in multiple
arrays/objects at once and requires their complete unique Unicode-sorted RFC 6901 paths
in compact canonical JSON; input objects and expected file bytes remain unchanged. Its
first GREEN may implement only the fixed-contract object/array paths reachable from two
strict models. Only then author the internal pure-difference helper selector, directly
supplying arbitrary mapping tokens and root scalars; its RED proves `~0`/`~1`, array
indices, or `""` root behavior is still missing, and its smallest GREEN extends the same
helper used by the comparator. No differing scalar value appears in error context.
Both failures use `REPRODUCIBILITY_MISMATCH` and return no partial logical result.

After those RED/GREEN cycles, independently author and run these three acceptance/
regression selectors:

```text
test_verified_inventory_detects_physical_byte_mutation_without_mutating_tree
test_closed_report_semantic_mutation_changes_only_report_logical_hash
test_manifest_input_mutation_changes_only_overall_logical_hash
```

They are deliberately **not** new RED evidence. Physical checksum behavior was first
driven by the Step 3 inventory attack matrix; report semantic hashing and manifest
logical hashing were first driven by their exact Step 1 selectors. The physical
acceptance mutates one byte and expects `CHECKSUM_MISMATCH` with byte-identical refusal.
The report acceptance independently recomputes canonical bytes and proves path/pretty
rendering invariant while one semantic value changes only `report_logical_hash`; it
does not invent a CP2 concrete report port or `REPORT_MISMATCH`. The overall acceptance
changes one logical input hash, recomputes all earlier inputs, and proves only the
overall logical hash changes. These tests cross-check already-GREEN primitives without
forcing an artificial temporary error, a synthetic production error code, or a second
behavior cycle.

Parquet logical-row/schema/sort/unique and Bronze/quality operational timestamp
mutations are deliberate CP3/CP5 REDs. Concrete report-file verification, exact-link
relation recheck, same-count/different-value DuckDB, and packaged expected comparison
are deliberate CP7 REDs under D-024.

- [x] **Step 7: Run the complete CP2 focused GREEN gate**

Do not add any later capability here. Run:

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

Expected GREEN: canonical independent bytes/hashes agree; both report shapes and
semantic projections are exact; all structural/path/mutation cases fail at their
intended CP2 boundary; a valid synthetic manifest loads and its descriptor-bound
physical inventory/reopen capability verifies immutably; exhaustive expected
differences are stable; and the orchestration refuses a missing later port and never
returns or exports a prematurely trusted artifact set.

- [x] **Step 8: Run full checkpoint/repository gates, commit, and obtain a fresh review**

Run the exact checkpoint gate plus unchanged behavior and repository gates:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/contract/test_artifact_manifest_schema.py \
  tests/contract/test_artifact_resources.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/core tests/unit/domain tests/unit/registry \
  tests/unit/data/normalization tests/contract/test_quality_issue_schema.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy src tests tools
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/audit_source_data.py --check
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/verify_handoff.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/extract_schema_catalog.py --check
PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache \
  UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pre-commit run --all-files
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv build --wheel \
  --out-dir /private/tmp/finproof-task5-cp2-wheel
git diff --check
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
test ! -e artifacts
git check-ignore -v artifacts/manifest.json artifacts/finproof.duckdb \
  .artifacts.finproof-stage-op .artifacts.finproof-backup-op \
  .artifacts.finproof-cleanup-op .artifacts.finproof-build.lock
find source_material -type f -perm -222 -print
git status --short
```

Expected: full suite passes; source audit is 145,393 at `2026-07-11`; handoff is
61/9/41,384,928; catalog is 207; wheel contains byte-identical manifest/quality schema
resources and no expected contract/candidate tooling; both expected-contract paths and
runtime artifact root are absent; all ignore probes match; writable-source search and
pre-commit/diff output contain no failure. Inspect `git diff --stat` and confirm only
the CP2 file map plus these governing docs changed before commit.

Then commit implementation files only:

```bash
git add schemas/artifact_manifest.schema.json src/finproof/data/artifacts \
  tests/helpers/artifacts.py tests/unit/data/artifacts \
  tests/contract/test_artifact_manifest_schema.py \
  tests/contract/test_artifact_resources.py
git commit -m "feat: add strict artifact manifest and logical hashing"
```

Fresh review must independently reproduce canonical bytes, inspect every manifest/schema conditional, attack recursive inventory without following links, verify no physical/report/path/timestamp field leaks into logical identity, and confirm no incomplete verifier can return a trusted set. Require 0 Critical / 0 Important.

The reviewer must also inspect held-root manifest binding and every retained descriptor/
reopen identity, confirm the implementation uses `os.scandir(dir_fd)` rather than an
invalid keyword API or lexical fallback, recompute exact report projections, exercise
RFC 6901 difference paths, and verify D-024 ownership. After review is 0 Critical /
0 Important, require `git status --porcelain` empty, both expected-contract paths and
`artifacts/` absent, and official sources still read-only before Checkpoint 3 starts.

Observed completion evidence on 2026-08-15:

- Reviewed CP2 commits: implementation `0db3e79`, review correction `ac5d4ee`, and
  residual Mapping-snapshot correction `75a2bfc`.
- Final independent review at `75a2bfc`: Critical 0 / Important 0 / Minor 0.
- Hashing regression: 46 passed; exact CP2 focused suite: 341 passed; CP1+CP2
  aggregate: 576 passed; unchanged Task 1–4 regression: 533 passed.
- Full implementation suite: 1,248 passed and 1 explicit AF_UNIX-unavailable skip in
  578.71 seconds. Ruff format/check and mypy passed over 98 source files.
- Source audit remained 145,393 rows at `2026-07-11`; handoff remained 61 required
  files, 9 official inputs, and 41,384,928 bytes; schema catalog remained 207 columns.
- Wheel/resource checks passed with byte-identical manifest and quality schemas and no
  expected-contract resource or candidate tooling. Both expected-contract paths and
  `artifacts/` remained absent, official sources remained read-only, and the final
  worktree was clean.
- Exact next task: Checkpoint 3, frozen table specs, strict projections, and bounded
  Parquet I/O. Task 5, the Phase 1 gate, and Checkpoints 3–8 remain incomplete.

---

### Checkpoint 3: Frozen table specs, strict projections, and bounded Parquet I/O

**Clean-redo execution boundary (2026-08-15):** execute this checkpoint from exact
base `d983f1a`. Commit `065f68a` and the dirty worktree
`/Users/ss020/Dev/Mirae_Agent/.worktrees/phase1-task5-artifact-build-fifth` are
reference-only review evidence: prove `065f68a` is not an ancestor of the redo branch,
and do not cherry-pick it or copy its production/test files wholesale. The selector
sequence below supersedes that attempt's incomplete TDD evidence. The initial
implementation sequence has exactly eight selectors labeled derived first-GREEN
acceptances: exact-signature/Fund derivation,
frozen-spec hash metamorphism, the non-Bronze timestamp signature, serializer
fingerprint integration, quality-specific duplicate integration, common-checker
canonical-JSON integration, logical-mutation/physical-reencoding hash integration, and
writer/verifier fingerprint integration. Every other behavior selector, including every substantive
review-gap selector added below, is a mandatory newly observed RED on the clean-redo
lineage. The post-review correction adds 22 mandatory RED/GREEN selectors and four
separate derived first-GREEN behavioral regressions; neither category rewrites the
initial 69/8 evidence. The third fresh-review correction adds seven more mandatory
RED/GREEN selectors and no derived acceptance; it is reported separately from both
earlier matrices. The fourth fresh-review correction adds five mandatory RED/GREEN
selectors and no derived acceptance. The fifth fresh-review correction adds two
mandatory RED/GREEN selectors and no derived acceptance. Never alter production code or manufacture a
failure to turn one of the twelve total derived acceptances into RED evidence.

**Files:**

- Create: `src/finproof/data/artifacts/table_specs.py`
- Create: `src/finproof/data/artifacts/serialization.py`
- Create: `src/finproof/data/artifacts/parquet_io.py`
- Modify: `src/finproof/data/artifacts/hashing.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Create: `tests/unit/data/artifacts/test_table_specs.py`
- Create: `tests/unit/data/artifacts/test_serialization.py`
- Create: `tests/unit/data/artifacts/test_parquet_io.py`
- Modify: `tests/unit/data/artifacts/test_manifest.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/artifacts/__init__.py`
- Create: `tests/integration/artifacts/test_parquet_verification.py`
- Modify: `tests/helpers/artifacts.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**

- Produces strict frozen `ColumnSpec(name, logical_type, arrow_type, duckdb_type, nullable)`, `TableSpec(table_name, layer, grain, columns, unique_key, sort_key, logical_projection, parquet_path)`, and deeply immutable `TABLE_SPECS` in exact artifact order. Produces the sole `TABLE_SPEC_REGISTRY = ClosedTableSpecRegistry(TABLE_SPECS)`: before touching an input element or requesting an iterator it requires an exact tuple, exact `TABLE_SPECS` object, exact length, and exact indexed member identities; `ordered_specs()` returns that exact tuple for CP2's kernel port after revalidating every frozen spec fingerprint.
- Produces `derive_wide_columns(model_type: type[BaseModel]) -> tuple[ColumnSpec, ...]`;
  there is no `skip_fields` parameter. Only exact `FundItem.contributing_rows` is
  skipped, and only when `model_type is FundItem`.
- Produces `canonical_record_json(model: BaseModel) -> str`,
  `serialize_table_row(spec: TableSpec, value: object) -> Mapping[str, object]`, and
  `serialize_bronze_source_row(spec: TableSpec, value: SourceRow, *,
  persistence_timestamp: datetime) -> Mapping[str, object]`. Only the latter accepts a
  timestamp. Quality accepts an already persisted CP5 row; all model/spec pairs are
  exact closed-registry identities and are revalidated on every call. The quality and
  fund serializers project every physical scalar from the same strict model instance
  used to produce canonical `record_json`; reopened logical projection reconstructs
  that model and compares the complete physical projection, not a selected subset.
  FundItem wide revalidation uses exact strict Python scalar/wrapper/model identities;
  it recursively validates every `SourceCellLocator` and every contributing
  `SourceRow`/`SourceCell` child as well; it never JSON-round-trips an untrusted model
  as a validation/coercion mechanism.
- Produces internal `OwnedStageArtifactOwner(Protocol)` and
  `OwnedStageParquetLeaf(Protocol)` with exact design-section-9.1 methods. CP3 has only
  test implementations; CP4 supplies the production marker/descriptor-owned
  capabilities. Every staged owner registration/require/replace method is annotated
  with the exact forward-referenced `StagedParquetVerification`,
  `StagedParquetHandle`, or `StagedParquetSet` type it consumes; no `object`-typed
  staged value/handle/set parameter is permitted. CP4 separately owns the section-9.2 database-stage protocols/results;
  no CP3 module references a CP7 result type. Produces
  `ParquetBatchWriter(spec: TableSpec, leaf:
  OwnedStageParquetLeaf)` with `write_batch`, `close() -> None`, `abort()`, and metrics.
  No API accepts a raw output/reopen `Path`.
- Produces direct-construction-disabled `StagedParquetHandle` and
  `StagedParquetVerification`, plus `verify_staged_parquet_table(*, owner:
  OwnedStageArtifactOwner, leaf: OwnedStageParquetLeaf, spec: TableSpec) ->
  StagedParquetVerification`. These are the
  per-leaf facts, but the only CP4-7 pre-manifest cross-stage table capability is
  direct-construction-disabled `StagedParquetSet.from_verified(owner=...,
  verifications=...)`, its exact `extend_verified(*, owner:
  OwnedStageArtifactOwner, verifications:
  tuple[StagedParquetVerification, ...]) -> StagedParquetSet`, and
  `require_complete() -> None`. It validates one exact
  opaque owner token/object identity, every exact leaf/handle identity, frozen order,
  and the owner's UTC persistence timestamp; every consumer calls `assert_live()`,
  `require_tables(...)`, and `require_owned(...)`, while CP7 also calls
  `require_complete()`. The owner registers the exact canonical set object; extension
  validates the whole prospective tuple before it atomically registers the successor
  and supersedes its predecessor. A failed extension leaves the predecessor live; a
  successful extension invalidates it exactly once. UTC timestamps compare by exact
  value, not Python object identity. Copies,
  `object.__new__`/equal-field forgeries, superseded sets, and bare/mixed-session handle
  tuples are forbidden. Each verification carries logical facts plus staged physical
  size/SHA and the opaque token from atomic owner registration of that exact
  verification/handle pair; no leaf/public method can mint it. The handle retains the
  same frozen physical/identity facts. `verification_for(name)` revalidates logical and
  physical facts, while `table_declarations()` returns logical declarations only; CP7
  pairs each with its revalidated verification to construct the physical manifest
  file entry. `verification_for(name)` performs a fresh same-descriptor size/SHA and
  leaf-identity check before returning, and every consumer encloses batch use plus the
  post-read check in `finally`; an exception in caller code cannot skip the rescan or
  exact context exit. All facts are
  independently recomputed on reopen; later final
  verification trusts none of them. `StagedParquetHandle.iter_batches(*,
  batch_size=65_536)` is a context manager that retains the leaf/stream/`ParquetFile`
  through iteration and fixes `use_threads=False`; production refuses values above
  65,536 and tests inject only smaller positive limits.
- Produces one private common bounded stream checker and a secure marker-owned managed
  exact unique-key-index context with one thread, `1GiB`, bounded inserts, owned spill,
  external access/extensions disabled, close-before-cleanup, and exact marker/
  directory/leaf identity deletion. The workspace root itself is opened beneath a
  held trusted-parent descriptor, all setup/rescan/cleanup is descriptor-relative, and
  successful cleanup removes registered children in fixed order and the ownership
  marker last. Default trusted-parent open/dup/fstat/identity acquisition is inside the same typed setup
  boundary with exact descriptor release. Before any held descriptor is passed to
  `os.close`, its current owner atomically clears or transfers the ownership slot; a
  close attempt is never retried by numeric descriptor even when the call closes the
  kernel object and then raises. Every cleanup rename records its retained
  state in one fixed-size bounded summary before any fallible post-rename check. No database/spill path or generic connection escapes. It catches
  nonadjacent duplicates across more than two batches and uses no
  Python key set or previous-key-only uniqueness.
  `OwnedStageParquetLeaf.create_verification_workspace()` supplies CP4's exact staged
  scratch capability; the final adapter uses its own trusted-OS-temp implementation of
  the same `OwnedParquetVerificationWorkspace` protocol. Neither accepts a caller path.
- Produces the distinct final-only `VerifiedParquetTable` and concrete
  `ParquetArtifactTableVerifier`, implementing CP2
  `ArtifactTableVerifier.verify_tables(...)`. Only this adapter accepts
  `VerifiedPhysicalInventory`/`VerifiedPhysicalEntry`; it independently reruns the
  common checker after the complete manifest tree exists. The common checker returns
  only direct-construction-disabled immutable checked facts; it owns no authority and
  never mints a final capability. Each `verify_tables` invocation creates one private
  invocation-local issuer. Only after the exact inventory entry context exits cleanly,
  the returned facts match the manifest, the deep spec fingerprint is rechecked, and
  the live inventory rescans unchanged may that issuer mint an exact-object-registered,
  one-use final-check seal. `VerifiedPhysicalInventory` accepts that exact seal and
  atomically consumes it while issuing/registering the corresponding
  `VerifiedParquetTable`; public fields, copied/equal/`object.__new__` objects, staged
  seals, and foreign-inventory seals can never authorize issuance. The adapter compares
  every fact with `ArtifactTable`, and returns
  `TableVerificationResult.from_verified(inventory=inventory, tables=..., handles=...)`.
  The inventory alone issues/registers each exact final handle object, and the result
  factory requires those exact live registered objects. A staged handle has no final
  entry and cannot be cast/promoted into this result. CP3 implements/tests the adapter
  with a complete synthetic 14-file tree but does not wire the kernel; CP7 is the first
  production invocation.

- [x] **Step 1: Close exact table-spec behaviors through strict serial selectors**

Author only one selector after its predecessor is GREEN. Run each as
`UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest
tests/unit/data/artifacts/test_table_specs.py::<selector> -q` in this exact order:

```text
test_table_spec_module_skeleton_rejects_closed_registry_fixture
test_table_registry_has_exact_eleven_names_and_paths
test_bronze_explicit_specs_have_exact_columns_types_and_keys
test_fund_attribute_and_quality_specs_have_exact_columns_types_and_keys
test_gold_specs_have_exact_columns_types_and_keys
test_bond_wide_spec_matches_independent_model_derivation
test_domestic_wide_spec_matches_independent_model_derivation
test_overseas_wide_spec_matches_independent_model_derivation
test_fund_item_wide_spec_matches_independent_model_derivation
test_derive_wide_columns_exact_signature_and_fund_contributing_rows_absence
test_derive_wide_columns_rejects_foreign_unregistered_and_subclass_models
test_model_drift_guard_rejects_insert_remove_and_reorder
test_registry_rejects_forged_equal_spec_and_wrong_model_pair
test_registered_spec_fingerprint_rejects_every_scalar_key_and_nested_column_mutation
```

The first missing-import RED permits only importable `ColumnSpec`, `TableSpec`, and an
empty/raising registry skeleton; rerun the same selector for the narrower rejected-
fixture RED before implementing names. Each explicit/wide selector implements only its
named table family. The drift selector is one coherent parameter family only when all
insert/remove/reorder IDs reach their intended rejection in the same run. No later
selector may be authored from the first module-missing failure.

The exact-signature/Fund selector is a **derived first-GREEN acceptance**, not RED
evidence: inspect the exact one-positional-argument signature, prove only exact
`FundItem.contributing_rows` is absent, and prove every other declared field remains.
Only after that acceptance is recorded, author the separate mandatory behavioral RED
for a foreign `BaseModel`, an unregistered model, and subclasses of each registered
model. Require every parameter ID to reach admission by the permissive exact-one-arg
helper before adding the smallest closed-registry identity guard. A first-GREEN
signature assertion cannot authorize or be cited for this admission behavior.

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

For every explicit Bronze/fund-attribute/quality/Gold table, assert the exact column order, nullability, Arrow/DuckDB types, key, grain, and Parquet path from Sections 5.1-5.3 and 5.8-5.11. In particular,
`silver_quality_issue.unique_key == ("issue_id",)` while its full source-location sort
key remains unchanged; the unique key is not the sort key. For each wide table,
independently derive its expected sequence from the frozen domain model declaration and assert it equals the hard-coded reviewed `TableSpec`; never generate the production spec at runtime from the same helper used by the test.

Add synthetic Pydantic models with one inserted, removed, and reordered field and prove `assert_model_matches_frozen_spec(...)` rejects each. Exact model-to-table registration rejects subclasses, wrong model/table pairs, and structurally equal copied specs. At registry construction, capture a deeply immutable canonical fingerprint for each exact `TableSpec` and all nested `ColumnSpec` values. The final mutation family must use `object.__setattr__` to mutate, one reached ID at a time, every table scalar/key field (`table_name`, `layer`, `grain`, `parquet_path`, `columns`, `unique_key`, `sort_key`, and `logical_projection`) and every nested column field (`name`, `logical_type`, `arrow_type`, `duckdb_type`, and `nullable`), and prove identity-only registration is RED before the fingerprint check makes all IDs GREEN. Restore the canonical object in a `finally` block so no case masks the next. `table_spec(...)`, `require_registered_spec(...)`, and every later serializer/writer/verifier boundary must compare both exact identity and this canonical fingerprint. After all behavior selectors are GREEN, add `test_frozen_spec_hash_metamorphisms` as a labeled first-GREEN acceptance: changing only `layer` or `parquet_path` leaves `schema_sha256` unchanged, while name/grain/column/type/nullability/unique/sort changes it. CP2 already RED-drove the generic hash projection; do not manufacture another failure.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_table_specs.py -q
```

Expected aggregate GREEN only after every recorded selector RED/GREEN and the derived
hash acceptance. Record exactly 13 mandatory RED/GREEN selectors plus the two derived
first-GREEN acceptances (exact-signature/Fund derivation and hash metamorphisms) for
Step 1. This grouped command is never module/behavior RED evidence.

- [x] **Step 2: Implement the closed type/spec registry and model-drift guard**

Map only the frozen physical types: UTF-8/VARCHAR, int64/BIGINT, decimal128(38,18)/DECIMAL(38,18), date32/DATE, timestamp[us]/TIMESTAMP, timestamp[us, UTC]/TIMESTAMPTZ, and bool/BOOLEAN. Reject caller names and any unregistered logical type.

The wide derivation algorithm is exact and has no caller skip set:

1. emit `grain`;
2. traverse Pydantic fields in declaration order;
3. skip `contributing_rows` only when the exact model is `FundItem`; skip nothing for
   every other model and reject any caller/subclass attempt to alter that rule;
4. `NormalizedValue[T]` emits `<field>` then `<field>__quality_status`;
5. `DerivedValue[T]` emits `<field>`, `<field>__quality_status`, then `<field>__as_of_date`;
6. **`FundItemValue[T]` emits `<field> = representative.normalized_value` then `<field>__quality_status = representative.quality_status`; `equivalent_sources` remains only in `record_json`;**
7. emit `record_json` last.

Hard-code the reviewed resulting columns in `TABLE_SPECS`; use derivation only as a drift assertion. Validate exactly 17 normalized plus four derived bond fields, 30 normalized plus one derived domestic fields, 49 overseas fields, and 44 fund representative fields.

- [x] **Step 3: Close serializer behaviors through strict serial selectors**

Use the same one-selector RED/skeleton/narrower-RED/GREEN rule for every unlabeled
mandatory selector and this exact order in
`tests/unit/data/artifacts/test_serialization.py`. The inline-labeled signature selector
is a derived first-GREEN acceptance and is excluded from the RED requirement:

```text
test_serialization_module_skeleton_rejects_valid_bond
test_bond_record_json_round_trip_and_projection
test_domestic_record_json_round_trip_and_projection
test_overseas_record_json_round_trip_and_projection
test_fund_item_record_json_round_trip_representative_and_lineage
test_explicit_table_serializers_cover_bronze_attribute_quality_and_gold
test_bronze_source_row_alone_accepts_and_injects_persistence_timestamp
test_persisted_quality_requires_typed_json_timestamp_agreement
test_non_bronze_serializers_expose_no_persistence_timestamp_parameter  # derived first-GREEN acceptance
test_decimal_date_local_datetime_enum_null_and_utc_encoding
test_serialization_rejects_aware_source_local_and_nonexact_utc_timestamps
test_explicit_gold_decimal_rejects_decimal_38_18_integer_and_fractional_overflow
test_serialization_rejects_nonfinite_overflow_and_scale_loss
test_logical_projection_rejects_noncanonical_record_json
test_serialization_revalidates_exact_registered_spec_and_model_pair
test_serialization_rejects_mutated_registered_spec_fingerprint
```

The skeleton implements only names with raising bodies. Each model selector adds only
that exact model/table projection. The non-Bronze timestamp selector is a derived
first-GREEN signature acceptance: the minimal initial contract already defines
`serialize_table_row(spec, value)` while only
`serialize_bronze_source_row(..., persistence_timestamp=...)` accepts a timestamp, so
the signature inspection and call-binding rejection necessarily follow from the API
split driven by the preceding Bronze selector. Record its first-run GREEN honestly;
do not add, remove, or temporarily expose a generic timestamp parameter to manufacture
a RED. It still executes the runtime inspection/call fence and does not rely only on
mypy. The forged-spec selector supplies equal-looking copies,
subclasses, and wrong model/table pairs only, and every ID must reach the same intended
exact-identity rejection. It does not mutate a registered object; the Step 1 fingerprint
family exclusively owns that behavior's RED.

Treat the physical scalar boundary as exact, not coercive. A source-local
`timestamp[us]` accepts an exact naive `datetime` only and rejects aware values. A UTC
`timestamp[us, UTC]` accepts an exact timezone-aware `datetime` whose offset is zero and
rejects naive values, nonzero offsets, strings, and non-datetime values. Exact integer
columns reject `bool`; exact date columns reject `datetime`; string and Boolean columns
accept only their exact Python scalar types; null is accepted only when the frozen
column is nullable. Exercise every frozen physical type, not merely representative
wide-table columns. Gold confidence is finite exact `Decimal(38,18)`: reject more than
20 integer digits or more than 18 fractional digits, including `Decimal("1e20")` and
`Decimal("1e-19")`, without rounding or text coercion.

The noncanonical-JSON selector supplies otherwise physically valid rows whose
`record_json` has changed key order/spacing, a mismatched typed leaf, an omitted or
extra model leaf, or a representation that parses but is not the exact canonical JSON
of the registered model. Require all IDs to RED at the logical-projection boundary,
then strict-parse through the exact registered model, rebuild canonical JSON, and
compare exact bytes before hashing or returning a logical row. The final fingerprint
selector repeats representative canonical registered `TableSpec` and nested
`ColumnSpec` mutations after Step 1 is GREEN and is a **derived first-GREEN integration
acceptance**. It proves the serializer reaches the already-RED-driven canonical
fingerprint guard; do not change production code or manufacture a serializer-specific
failure for this selector.

Using current complete SourceRow helpers, normalize one bond, domestic-listed, overseas, and two-row fund item. For every model field, assert:

```python
payload = canonical_record_json(record)
round_tripped = type(record).model_validate_json(payload)
row = serialize_table_row(TABLE_SPECS[table_name], record)
assert round_tripped == record
assert row["record_json"] == payload
```

Then assert each wide scalar and quality/as-of field equals its exact wrapper. Add explicit fund assertions that the projected scalar is `item.ksd_id.representative.normalized_value`, the quality is `item.ksd_id.representative.quality_status.value`, and every `equivalent_sources` plus `contributing_rows` survives only in parsed `record_json`. Add raw/padded attribute-code, source-local datetime-without-timezone, Decimal scale-preservation in `record_json`, null scalar, enum string, and UTC terminal-`Z` cases. Reject NaN/Infinity, Decimal overflow/scale loss, mismatched spec/model, and noncanonical model JSON through the separate selectors above.

For `bronze_source_row`, call only `serialize_bronze_source_row` and prove the typed
physical `loaded_at` is the injected UTC value while its logical projection is null.
For `silver_quality_issue`, call only `serialize_table_row` with an already-persisted
CP5 strict row; prove typed/strict JSON timestamps agree physically and both become null
only through strict model reconstruction for logical hashing. Every other model has no
timestamp parameter and rejects one at Python call binding.

Expected: every mandatory named behavior records its own RED/GREEN; no grouped import
failure masks a later model, timestamp, numeric, or forged-spec branch. Record exactly
14 mandatory RED/GREEN selectors plus two derived first-GREEN acceptances (the
non-Bronze timestamp signature and fingerprint integration) for Step 3; do not count
either acceptance as RED evidence.

- [x] **Step 4: Implement canonical strict-model JSON and typed row serializers**

Use `model.model_dump(mode="json")` followed only by sorted keys, compact separators, UTF-8, and JSON escaping. Do not pass payload leaves through `canonical_scalar`. Parse the resulting JSON back through the exact model in tests. Convert wide wrapper values according to `ColumnSpec`; reject any conversion that changes Decimal value/scale beyond `DECIMAL(38,18)` or adds a timezone to a source-local timestamp.

Validate exact Python physical types before Arrow construction: no Pydantic/Arrow
coercion may establish the contract. Enforce the `Decimal(38,18)` 20-integer/18-scale
bounds by exact Decimal tuple/value inspection. Require exact UTC offset zero for UTC
operational values and exact naivety for source-local timestamps. Re-run the registered
spec's canonical deep fingerprint immediately before each serialization/projection;
Pydantic `frozen=True` and object identity alone are insufficient against
`object.__setattr__` mutation.

For quality rows, `serialize_table_row` accepts only an already-persisted strict issue
with a non-null UTC `first_detected_at`, emits its physical typed/JSON values, and
computes a separate null-timestamp logical `record_json` by strict model reconstruction.
It does not inject persistence time; that pure-to-persisted adapter begins with a CP5
RED. Do not replace timestamp text in a string. Only
`serialize_bronze_source_row(..., persistence_timestamp=...)` injects time, and its
logical projection replaces only `loaded_at` with null. Revalidate exact registry spec
object and exact model type immediately before projection; derivation-time validation
alone is insufficient.

- [x] **Step 5: Close writer, staged verification, uniqueness, and final-adapter selectors serially**

Use exact node selectors, one at a time, in this order:

```text
tests/unit/data/artifacts/test_parquet_io.py::test_parquet_module_skeleton_rejects_valid_owned_leaf
tests/unit/data/artifacts/test_parquet_io.py::test_writer_creates_only_exact_owned_leaf_exclusively_nofollow
tests/unit/data/artifacts/test_parquet_io.py::test_writer_uses_exact_schema_options_and_row_group_limit
tests/unit/data/artifacts/test_parquet_io.py::test_writer_enforces_bounded_batches_without_early_logical_hash
tests/unit/data/artifacts/test_parquet_io.py::test_writer_snapshots_lying_length_and_mutating_sequence_once_with_65537_cap
tests/unit/data/artifacts/test_parquet_io.py::test_writer_close_flush_failure_and_reuse_lifecycle
tests/unit/data/artifacts/test_parquet_io.py::test_writer_leaf_enter_failure_is_typed_and_never_writes
tests/unit/data/artifacts/test_parquet_io.py::test_writer_leaf_exit_failure_is_typed_and_preserves_ambiguous_leaf
tests/unit/data/artifacts/test_parquet_io.py::test_writer_abort_unlinks_only_exact_writer_created_inode
tests/unit/data/artifacts/test_parquet_io.py::test_writer_abort_close_exit_and_unlink_faults_are_typed_and_ordered
tests/integration/artifacts/test_parquet_verification.py::test_staged_reopen_keeps_stream_and_parquetfile_inside_owned_context
tests/integration/artifacts/test_parquet_verification.py::test_staged_reopen_checks_exact_schema_metadata_row_groups_and_count
tests/integration/artifacts/test_parquet_verification.py::test_reopened_rows_enforce_every_exact_physical_type
tests/integration/artifacts/test_parquet_verification.py::test_staged_reopen_hashes_known_count_header_before_bounded_rows
tests/integration/artifacts/test_parquet_verification.py::test_staged_reopen_checks_canonical_sort_with_previous_key_only
tests/integration/artifacts/test_parquet_verification.py::test_bounded_unique_index_rejects_nonadjacent_duplicate_beyond_two_batches
tests/integration/artifacts/test_parquet_verification.py::test_quality_issue_unique_index_rejects_same_issue_id_at_nonadjacent_sorted_locations
tests/integration/artifacts/test_parquet_verification.py::test_staged_unique_index_is_managed_pathless_spillable_and_exact_owned
tests/integration/artifacts/test_parquet_verification.py::test_final_unique_index_is_managed_pathless_spillable_and_exact_owned
tests/integration/artifacts/test_parquet_verification.py::test_unique_workspace_disables_external_access_install_and_autoload
tests/integration/artifacts/test_parquet_verification.py::test_unique_workspace_preserves_external_symlink_victim_bytes_and_mode
tests/integration/artifacts/test_parquet_verification.py::test_unique_workspace_revalidates_exact_modes_marker_bytes_and_every_identity
tests/integration/artifacts/test_parquet_verification.py::test_unique_workspace_closes_before_cleanup_and_rejects_aba_or_ambiguity
tests/integration/artifacts/test_parquet_verification.py::test_unique_workspace_setup_and_close_failures_are_typed_and_retained
tests/integration/artifacts/test_parquet_verification.py::test_common_checker_rejects_noncanonical_record_json
tests/integration/artifacts/test_parquet_verification.py::test_writer_and_verifier_reject_mutated_registered_spec_fingerprint
tests/integration/artifacts/test_parquet_verification.py::test_staged_reopen_detects_logical_mutation_but_ignores_physical_reencoding  # derived first-GREEN acceptance
tests/integration/artifacts/test_parquet_verification.py::test_staged_verification_rejects_unissued_facts_and_forged_registration_token
tests/integration/artifacts/test_parquet_verification.py::test_staged_verification_atomically_registers_exact_verification_and_handle_objects
tests/integration/artifacts/test_parquet_verification.py::test_staged_verification_rejects_copied_equal_and_object_new_forge
tests/integration/artifacts/test_parquet_verification.py::test_staged_handle_rejects_foreign_copy_closed_owner_and_leaf_substitution
tests/integration/artifacts/test_parquet_verification.py::test_staged_handle_freezes_physical_facts_and_owner_registration
tests/integration/artifacts/test_parquet_verification.py::test_staged_handle_detects_same_inode_same_size_mutation_during_read
tests/integration/artifacts/test_parquet_verification.py::test_staged_handle_detects_same_inode_same_size_mutation_between_reads
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_skeleton_rejects_valid_verified_fixture
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_factory_binds_owner_timestamp_and_exact_verifications
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_rejects_naive_nonzero_offset_and_non_datetime_timestamp
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_extension_supersedes_predecessor_and_preserves_frozen_order
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_rejects_reordered_and_duplicate_verified_tables
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_require_methods_revalidate_registration_and_verified_facts
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_rejects_copy_object_new_equal_forge_and_mixed_owner
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_rejects_closed_or_substituted_owner_and_leaf
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_manifest_declarations_revalidate_physical_facts
tests/integration/artifacts/test_parquet_verification.py::test_final_adapter_requires_complete_manifest_inventory_and_declared_entry
tests/integration/artifacts/test_parquet_verification.py::test_final_adapter_independently_rechecks_all_facts_and_returns_inventory_owned_result
tests/integration/artifacts/test_parquet_verification.py::test_complete_final_result_requires_inventory_issued_registered_exact_handle_objects
```

The first selector permits only exact protocols/types and raising bodies. Every later
selector is authored after its predecessor is GREEN. Four Step 5 selectors are
explicit derived first-GREEN integration acceptances rather than new behavior REDs:
`test_quality_issue_unique_index_rejects_same_issue_id_at_nonadjacent_sorted_locations`,
`test_common_checker_rejects_noncanonical_record_json`, and
`test_writer_and_verifier_reject_mutated_registered_spec_fingerprint`, plus the inline-
labeled logical-mutation/physical-reencoding selector. All other Step 5
selectors are mandatory RED/GREEN. Writer schema, bounds, lifecycle, abort, reopen
metadata, hash, sort, uniqueness, ownership, and final transition are independent
behaviors; a missing module or the first bad parameter cannot stand in for their REDs.

Use a test-only internal limit of two, write two batches through an exact test
`OwnedStageParquetLeaf`, close, and assert `close() is None`: closing never creates a
verified handle. Reopen only through `verify_staged_parquet_table`. Assert exact
physical schema, row order, metadata, compression `ZSTD`, statistics, row-group maximum,
and values. Include all-null Decimal/date/local-time/UTC/bool columns. Assert over-limit
rows, wrong/missing/extra columns, incompatible Decimal, write/flush/close failure, and
reuse-after-close fail typed. The writer neither counts/hash-verifies by reopening nor
attempts a final logical hash before close.

`write_batch` never trusts `len()` and never iterates caller rows twice. Consume the
outer iterable exactly once into a bounded ordinary snapshot, stop after at most 65,537
items, reject empty or more than 65,536, then validate and write that same snapshot.
The dedicated mandatory RED family uses a lying-`len` sequence, a sequence whose first
iteration yields one row and any later iteration yields two, a one-pass iterator, and
exact 65,536/65,537 boundaries; assert the caller iterator count and that no second
caller access can alter the written batch.

All capability/context lifecycle failures are typed
`ArtifactContractError(SERIALIZATION_FAILED)`: failure entering
`leaf.create_exclusive()`, Parquet writer create/write/close, sink `__exit__`, and abort
close/exit/unlink. Exercise them as the separate selectors above. Close the Parquet
writer and sink before exact-inode unlink; if close/exit makes ownership ambiguous,
retain the leaf and fail closed rather than attempting unsafe cleanup. No error leaks a
raw `OSError`, permits reuse, or lets `abort()` delete a substituted inode.

The staged handle's context-managed `iter_batches(batch_size=2)` test holds the leaf
stream and `ParquetFile` live until iterator/context exit, observes `use_threads=False`,
rejects zero/negative/>65,536, and proves no escaped iterator works after close. On
reopened verification, prove the known final row count enters the logical header before
the first row. The later logical-mutation/physical-reencoding selector is a derived
first-GREEN acceptance: this earlier mandatory known-count selector's smallest generic
implementation already computes `table_logical_hash` from the reopened logical rows,
so a changed logical cell must alter the hash while physically reencoded identical
typed rows must retain it. Record the first-run GREEN with no production change; never
bypass, weaken, or temporarily replace the generic logical-row hash merely to
manufacture a RED. The acceptance still mutates one logical cell and requires hash
drift, then physically reencodes identical typed rows and requires stable logical
identity.
Mutate one byte in place without changing inode/length during iteration and between two
opens; pre/post same-descriptor size/SHA plus owner rescan must reject both without a
staged or final result.

The common verifier accepts the exact owner explicitly, seals verification/handle only
after all reads/rescans, and atomically registers those exact object identities with the
owner. Its three registration selectors separately reject missing/forged tokens, prove
the valid atomic pair, and reject copied/equal/`object.__new__` facts; no public leaf
method or caller can issue a token.

After the registration and three physical/identity handle selectors are independently GREEN,
author the staged-set skeleton and then each named set selector serially. The skeleton
may expose only raising factory/method bodies. Factory/timestamp, extension/order,
require-method behavior, copy/forge/mixed owner, and closed/substituted owner are
separate REDs. Register only the exact factory-created set object; extension atomically
supersedes it. Mix one structurally valid handle from a second live session,
copy/`object.__new__`/equal-forge a handle/set, reorder or duplicate a table,
use a superseded set, close/substitute the owner, and pass a bare tuple; every ID must
reach its intended rejection before any batch or database/report relation is read.
Finally require `table_declarations()` to revalidate the registered objects/logical
facts and pair every table with `verification_for(name)` to revalidate physical size/
SHA before producing CP7's separate table/file manifest entries; between-verification
physical mutation must fail rather than emit either declaration.

The set's persistence timestamp must be an exact `datetime`, timezone-aware with UTC
offset zero, and exactly equal to the live owner's timestamp. The dedicated family
must reach naive, nonzero-offset, string, and non-datetime IDs before the exact validator
is added. Revalidate this timestamp at factory, extension, and every live consumer
method. The explicit reorder/duplicate selector must reach those domain branches with
otherwise live, same-owner registered handles; a prior length, copy, or foreign-owner
failure cannot mask them.

For exact uniqueness, choose a frozen table whose `unique_key` is not the sort-key
prefix (quality `issue_id`), place the duplicate in batch 1 and after more than two full
test batches while maintaining valid sort order, and require rejection. Sentinels fail
on Python `set`, table-sized list/tuple/DataFrame, second input iteration, or retained
prior batches. Separately exercise the staged-owner workspace and final trusted-temp
workspace. Each exposes only a managed closed unique-index operation, never a raw
database/spill path or generic connection; assert external access and extension install/
load are disabled, production fixes one thread/1 GiB, and only the internal focused-
test seam can lower the positive memory/batch limits to force spill. Fault-inject
create, insert, query, close, marker/directory/store/spill substitution, ABA replacement,
and cleanup. Every failure closes before exact cleanup and never deletes an ambiguous
workspace or leaf.

The quality duplicate fixture must use two distinct, canonically sorted source rows
with the same `issue_id`, including a nonadjacent placement after more than two batches;
it proves the exact one-column unique key rather than a full-sort-key surrogate. This
selector is authored only after Step 1 froze `unique_key == ("issue_id",)` and the
generic bounded unique-index selector drove nonadjacent duplicate rejection; it must be
recorded as first-GREEN integration acceptance with no production change. The managed
uniqueness implementation must never call `duckdb.connect`, `chmod`, or open a
caller/mutable filesystem path before exclusive no-follow ownership is established.
Use a pathless database or an owner-created exclusive leaf/capability. The private root
is exact mode `0700`, marker/store leaves exact mode `0600`, and spill directories exact
mode `0700`; retain and revalidate every dev/inode/type/link/mode identity plus exact
marker bytes and marker SHA before cleanup. Same-inode marker-byte mutation, chmod,
component/leaf ABA replacement, symlink substitution, and a symlink to an external
victim must reject while preserving the victim's bytes and mode.

Configure DuckDB through supported configuration/SQL so external access,
`allow_unsigned_extensions`, `autoinstall_known_extensions`, and
`autoload_known_extensions` are disabled; neither `INSTALL` nor `LOAD` may succeed.
Temp-root, marker, store, and spill setup failures are typed. A connection-close failure
makes cleanup ambiguous: record the retained workspace, prevent any outer/finally
cleanup from deleting it, and raise only after attempting the exact close-before-clean
order. Successful cleanup enumerates only registered owned leaves, revalidates them,
removes them in fixed order, and removes the marker last.

Likewise, the common-checker canonical-JSON selector is authored only after Step 3's
`test_logical_projection_rejects_noncanonical_record_json` is GREEN, and the
writer/verifier fingerprint selector is authored only after Step 1's mutation family
and Step 3's serializer integration acceptance are GREEN. Both must pass on first run
through the already-driven shared boundaries. Record them as derived integration
acceptances and make no production change; deliberately bypassing the shared guard to
obtain RED is prohibited.

The final adapter fixture is a complete CP2-valid root with `manifest.json`, eleven
Parquets, two reports, DuckDB, and no extras. It opens each exact manifest entry through
the live CP2 inventory, reruns the common checker rather than copying staged facts,
compares schema/count/sort/unique/logical/physical declarations, and creates final
handles only through the CP2 result factory. Missing report/database/manifest, partial
tree, staged handle, foreign entry, and declared mismatch all fail before a result.

The final mandatory RED is one complete-eleven-table parameter family, authored before
the final registration implementation. It first proves the verifier can create the
real control handles, then requires the live final inventory to be the sole issuer and
registrar of each exact `VerifiedParquetTable` object after the common checker succeeds.
`TableVerificationResult.from_verified(...)` must call back into that inventory to
require every exact registered object, not merely compare its entry and public facts.
The reached invalid IDs are a `copy.copy` final handle, an `object.__new__` final handle
with injected matching facts, a real staged handle with an injected final `entry`, a
copied staged handle, and a relabeled staged handle. All invalid IDs must be observed
accepted in the RED run; tuple-length validation cannot mask them. Add only the
inventory issuer/register/require-exact-object mechanism and result-factory call for
GREEN. Staged and final handles remain runtime- and typing-noninterchangeable under
D-025; slots alone are not the trust boundary. Extend CP2's manifest contract test with
the same complete-result exact-object requirement so later adapters cannot regress it.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
```

Expected aggregate GREEN only after every mandatory selector's RED/GREEN and every
derived acceptance's observed first-GREEN. This grouped command is never evidence for
the individual writer/reopen/uniqueness/ownership behaviors. Record exactly 42
mandatory RED/GREEN selectors plus the four derived first-GREEN integration
acceptances for Step 5. Across Steps 1, 3, and 5, the authoring matrix is 69 mandatory
RED/GREEN selectors and eight explicitly derived first-GREEN acceptances; report the two
categories separately and never inflate the RED count with an acceptance.

- [x] **Step 6: Implement the incremental PyArrow writer and table-aware verifier**

Construct `pyarrow.parquet.ParquetWriter` only on the binary sink yielded by
`leaf.create_exclusive()`, with exact explicit Arrow schema and supported constructor
options `compression="zstd"`, `compression_level=3`, `write_statistics=True`, and
`data_page_size=1_048_576`. Reject any input batch above 65,536 before constructing its
Arrow table, then call `writer.write_table(arrow_batch, row_group_size=65_536)` for each
bounded batch; `row_group_size` is deliberately a `write_table` argument, not a
`ParquetWriter` constructor keyword. The writer tracks only prospective count/key
bounds needed for early failures, does not reopen or compute the table logical hash,
and `close()` only flushes/closes. `abort()` delegates exact-inode deletion to the leaf
capability and fails closed on substitution/ambiguity.

After close, `verify_staged_parquet_table` reopens through the live stage leaf. The
final adapter separately reopens through CP2 inventory only after a complete manifest
tree exists. Both enter one common checker, construct `ParquetFile(stream)` inside the
owning context, and call only `iter_batches(batch_size=65_536, use_threads=False)` in
production. Obtain and validate final row count and exact schema first. Initialize the logical hash with the now-known exact header
`{schema_sha256, logical_projection, row_count}`, then bounded-stream reopened typed
logical rows while validating count/sort keys and updating the hash. Verify uniqueness
through canonical typed key bytes in the fixed marker-owned one-thread/1-GiB spillable
DuckDB index; close then exact-clean it on every path. Never use
serialized Arrow buffers, Parquet row bytes, row-group encoding, compression bytes, or
the outer file SHA as logical identity. Return staged verification only after stage
owner/content rescans agree, atomically register the exact verification/handle objects
with the owner, and freeze the physical size/SHA plus returned opaque token in both.
Every later batch/declaration access repeats those
checks; return final `VerifiedParquetTable` only after CP2
post-consumer same-descriptor physical size/SHA and entry/ancestor/content rescans agree.
Never convert one result into the other. Implement the CP2 table-verifier port, but
under D-024 do not assemble/invoke it in production or expose a complete artifact
verifier before CP7.

- [x] **Step 7: Run GREEN, focused gates, and model coverage probes**

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts tests/unit/data/artifacts tests/integration/artifacts
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts tests/unit/data/artifacts tests/integration/artifacts
```

Expected GREEN: exact eleven specs are immutable; all four wide models have complete
projection/round-trip coverage including the `FundItemValue.representative` rule;
writer close is not verification; staged handles remain stage-owned; the final adapter
independently returns only CP2-inventory-owned handles; streaming, spillable uniqueness,
and all cleanup/ownership failures remain bounded.

- [x] **Step 8: Run exact repository gates, commit for review, then close status separately**

Update `docs/implementation/STATUS.md` with every observed selector RED/GREEN, focused
counts, mandatory command results, the CP3 capability split, unresolved risk if any,
and exact next task **fresh independent Checkpoint 3 review**. Do not claim CP3 complete
or name CP4 as next yet. Then run all gates on the exact implementation tree:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_hashing.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/core tests/unit/domain tests/unit/registry \
  tests/unit/data/normalization tests/contract/test_quality_issue_schema.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy src tests tools
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/audit_source_data.py --check
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/verify_handoff.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/extract_schema_catalog.py --check
PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache \
  UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pre-commit run --all-files
git diff --check
git diff --stat
git diff --name-only
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
test ! -e artifacts
find source_material -type f -perm -222 -print
git status --short
```

Required observations: full suite and all focused/static gates pass; source audit stays
145,393 at `2026-07-11`; handoff stays 61/9/41,384,928; catalog stays 207; both expected
contract paths and runtime `artifacts/` remain absent; writable-source output is empty.
Before commit, `git diff --name-only` contains exactly the CP3 file map and
`docs/implementation/STATUS.md`: the only CP2-owned source file admitted is
`manifest.py` for final-handle issuance/registration enforcement; there is no config,
schema, source material, or later-checkpoint module. Formatting/pre-commit may make
only mechanical changes inside that exact list and must be rerun if they do.

Commit only:

```bash
git add src/finproof/data/artifacts/hashing.py \
  src/finproof/data/artifacts/manifest.py \
  src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/helpers/artifacts.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/__init__.py \
  tests/integration/artifacts/__init__.py \
  tests/integration/artifacts/test_parquet_verification.py \
  docs/implementation/STATUS.md
git commit -m "feat: freeze artifact table and Parquet contracts"
git status --porcelain
```

Expected post-commit status is empty. Dispatch a fresh reviewer against the commit.
Review must enumerate all table columns independently, test model insertion/removal/
reorder and forged pairs, verify fund representative/record-only lineage, inspect exact
Decimal/timestamp APIs, attack exclusive leaf/abort/substitution boundaries, prove
stage/final capabilities cannot cross even in a complete eleven-table result, attack
copied/object-new/injected handles against final-inventory object registration, force a
nonadjacent quality `issue_id` duplicate beyond two batches with spill/cleanup faults,
mutate every registered spec/nested-column field, inspect stream lifetime and
`use_threads=False`, and confirm one-pass 65,537-bounded ingestion with no table-sized
collection. Require 0 Critical / 0 Important. Any correction begins with
one focused observed RED, gets a separate `fix: close Task 5 checkpoint 3 review gaps`
commit, reruns the complete Step 8 gates, and receives another independent 0/0 review.

#### Checkpoint 3 post-review correction: close verdict 1C / 8I / 1M serially

Commit `065e9fc` is the reviewed implementation candidate, not an accepted checkpoint.
The reviewer found 1 Critical, 8 Important, and 1 Minor issue. Obtain independent
approval of this correction plan before changing production or tests. After plan
approval, commit only this dedicated plan as a separate documentation commit with
subject `docs: plan Task 5 checkpoint 3 review corrections`, require an empty status,
and record that commit as the clean correction base. No correction RED may be authored
from the current uncommitted plan tree. Do not amend the
initial report's 69 mandatory RED/GREEN selectors or eight derived acceptances; append
a clearly separated correction section to the ignored report instead. Do not update
`docs/implementation/STATUS.md`, mark this step complete, or name Checkpoint 4 as next
until the correction commit itself receives a fresh 0 Critical / 0 Important verdict.

After the plan-review approval and before implementation, run the separate plan commit
boundary exactly:

```bash
git diff --check
git diff --name-only
git status --short
git add docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: plan Task 5 checkpoint 3 review corrections"
git status --porcelain
```

The two name-only outputs must contain only this dedicated plan, and the final status
must be empty. Record the resulting plan hash as the correction base in the ignored
report before authoring the first RED.

The correction implementation has this exact file map:

- Modify: `src/finproof/data/artifacts/serialization.py`
- Modify: `src/finproof/data/artifacts/parquet_io.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Modify: `tests/unit/data/artifacts/test_serialization.py`
- Modify: `tests/unit/data/artifacts/test_parquet_io.py`
- Modify: `tests/unit/data/artifacts/test_manifest.py`
- Modify: `tests/integration/artifacts/test_parquet_verification.py`
- Modify only when a fixture genuinely requires it:
  `tests/helpers/artifacts.py`

No config, schema, source data, hashing primitive, table registry, later-checkpoint
module, legacy plan, this plan, or STATUS file belongs in the correction implementation
commit. A changed file outside that map is a stop condition requiring plan/reviewer
approval, not an invitation to broaden the commit silently.

This subsection is the explicit post-review override of Step 8's original implementation
file map and its instruction to update/add STATUS before the implementation commit.
For this correction only, use the narrower file map above and leave STATUS untouched
through implementation and re-review. Every Step 8 verification command, absence gate,
source write-permission gate, diff check, clean-worktree requirement, separate fix
commit, and fresh-review requirement remains mandatory.

Author and execute exactly one selector only after its predecessor is GREEN. For a
parameter family, first add only enough test fixture to make every ID reach the intended
production boundary; a missing import, first invalid ID, permissive spy, or shared setup
failure is not family RED evidence. Observe the current defect, make the smallest
production change, rerun the exact node GREEN, and run its immediately affected prior
selectors before authoring the next node. Use this exact order:

```text
tests/integration/artifacts/test_parquet_verification.py::test_common_checker_returns_facts_only_and_final_adapter_mints_local_seal_after_clean_entry_exit
tests/unit/data/artifacts/test_manifest.py::test_inventory_requires_exact_unconsumed_local_authority_seal_before_final_handle_issuance
tests/integration/artifacts/test_parquet_verification.py::test_final_seal_rejects_copy_equal_object_new_staged_foreign_and_second_consumption  # derived first-GREEN seal-adversarial acceptance
tests/unit/data/artifacts/test_serialization.py::test_quality_logical_projection_compares_each_uncovered_scalar_to_canonical_record_json
tests/unit/data/artifacts/test_serialization.py::test_fund_attribute_logical_projection_compares_every_physical_column_to_canonical_record_json
tests/integration/artifacts/test_parquet_verification.py::test_common_checker_rejects_each_quality_and_fund_attribute_physical_json_mismatch  # derived first-GREEN JSON-integration acceptance
tests/unit/data/artifacts/test_parquet_io.py::test_writer_snapshots_each_yielded_mapping_before_requesting_the_next_row
tests/unit/data/artifacts/test_parquet_io.py::test_writer_accepts_mapping_rows_and_rejects_each_non_mapping_before_arrow
tests/unit/data/artifacts/test_parquet_io.py::test_writer_validates_every_exact_physical_scalar_on_each_frozen_snapshot
tests/unit/data/artifacts/test_parquet_io.py::test_parquet_writer_constructor_failure_is_typed_and_exits_sink_exactly_once
tests/integration/artifacts/test_parquet_verification.py::test_writer_rechecks_deep_spec_fingerprint_at_each_uncovered_post_construction_boundary
tests/integration/artifacts/test_parquet_verification.py::test_staged_verifier_rechecks_deep_spec_fingerprint_at_each_uncovered_post_open_boundary
tests/integration/artifacts/test_parquet_verification.py::test_final_verifier_rechecks_deep_spec_fingerprint_at_each_uncovered_post_open_boundary
tests/integration/artifacts/test_parquet_verification.py::test_staged_set_exposes_only_exact_extend_verified_and_require_complete_signatures
tests/integration/artifacts/test_parquet_verification.py::test_extend_verified_requires_explicit_owner_tuple_and_accepts_distinct_value_equal_utc
tests/integration/artifacts/test_parquet_verification.py::test_extend_verified_supersession_is_atomic_on_validation_and_owner_registration_faults
tests/integration/artifacts/test_parquet_verification.py::test_require_complete_accepts_only_exact_eleven_registered_tables_in_frozen_order
tests/integration/artifacts/test_parquet_verification.py::test_staged_handle_and_verification_retain_exact_frozen_leaf_identity
tests/integration/artifacts/test_parquet_verification.py::test_verification_for_reopens_and_rechecks_exact_bytes_and_leaf_identity_on_every_call
tests/integration/artifacts/test_parquet_verification.py::test_staged_consumers_run_post_read_checks_and_context_exit_in_finally
tests/integration/artifacts/test_parquet_verification.py::test_unique_workspace_root_is_created_and_held_beneath_a_trusted_parent_descriptor
tests/integration/artifacts/test_parquet_verification.py::test_unique_workspace_cleanup_is_descriptor_relative_preflighted_and_removes_marker_last
tests/integration/artifacts/test_parquet_verification.py::test_workspace_root_child_and_marker_substitution_never_touch_external_victims  # derived first-GREEN victim-substitution acceptance
tests/integration/artifacts/test_parquet_verification.py::test_workspace_cleanup_fault_retains_ambiguous_owned_remainder_without_victim_deletion
tests/integration/artifacts/test_parquet_verification.py::test_workspace_faults_have_exact_nonreserved_typed_operations_and_redacted_context
tests/integration/artifacts/test_parquet_verification.py::test_actual_install_and_load_fail_under_locked_workspace_configuration  # derived first-GREEN behavioral regression
```

Exactly 22 selectors are mandatory correction RED/GREEN evidence. The four inline-
labeled seal-adversarial, JSON-integration, victim-substitution, and actual `INSTALL`/
`LOAD` selectors are derived first-GREEN acceptances. The already-GREEN settings
selector froze `enable_external_access=false`, `allow_unsigned_extensions=false`,
`autoinstall_known_extensions=false`, and `autoload_known_extensions=false`; therefore
the derived selector monkeypatches `duckdb.connect` with a test-only proxy around a real
saved `duckdb.connect(":memory:")`. The proxy forwards every production `SET` to the real
connection. Immediately and synchronously after it forwards the final
`SET autoload_known_extensions = false`, and before the managed index context can yield,
the proxy itself attempts real `INSTALL httpfs` and `LOAD httpfs` statements and records
the two exact `duckdb.PermissionException` results in its closed test spy. It then
continues forwarding only the production index DDL/DML/close calls. Neither the real
connection nor a generic `execute` capability is returned by the managed workspace or
exposed to the test/caller; the spy exposes only the immutable recorded statement/error
facts after closure. Both attempts must fail without another production change. Record
that first-run GREEN as behavioral regression evidence. Never enable an extension
temporarily, add a bypass, or weaken configuration merely to manufacture a RED.

The common checker returns only a private direct-construction-disabled immutable facts
record containing its independently recomputed logical facts, physical size/SHA, leaf
identity, and deep spec fingerprint. That record is evidence, never authority: the
checker has no issuer registry and cannot create a staged or final seal. Each
`ParquetArtifactTableVerifier.verify_tables` call creates one private local authority
whose lifetime cannot escape that invocation. Only after the exact
`inventory.open_verified(entry)` context has exited without a body or `__exit__`
failure, the immutable facts match `ArtifactTable`, the registered spec's deep
fingerprint is checked again, and `inventory.assert_unchanged()` succeeds may this
authority mint/register a direct-construction-disabled one-use final seal. The seal
binds by exact object identity to that local authority, live inventory,
`VerifiedPhysicalEntry`, exact registered `TableSpec`, checked-facts object, and final
facts. There is no public constructor, token accessor, leaf minting method, structural
protocol shortcut, or caller-supplied facts route.

`VerifiedPhysicalInventory.issue_verified_table_handle(*, seal=...)` validates through
the seal's still-live local authority and performs one atomic transition: either it
consumes that exact seal and registers one exact newly constructed final handle, or it
does neither and exposes no handle. A second call cannot consume the same seal. A
missing, copied, equal-field, `object.__new__`, foreign-inventory, staged,
already-consumed, post-exit-failure, or post-seal-mutated capability fails before any
handle exists. The third selector is deliberately a derived first-GREEN adversarial
acceptance authored only after the first two mandatory selectors have driven the local
authority and atomic issuance mechanism; it must require no further production change.
This correction is owned jointly by CP3's checker/final adapter and CP2's inventory
issuance hook; it does not alter CP2 tree inventory semantics or permit a staged-to-final
promotion.

For `silver_quality_issue`, the mandatory correction family owns only the uncovered
scalar columns and derives each expected value from strict `DataQualityIssue` parsed
from canonical `record_json`: `issue_id`, `rule_id`, `rule_version`, `severity`, `quality_status`,
`source_table`, `source_file`, `source_sheet`, `source_row_number`,
`source_column_name`, `source_column_number`, `source_column_letter`,
`source_checksum`, `source_snapshot_date`, `source_applicable_date`, `reason`,
`quarantined`, and `raw_payload_sha256`. It explicitly excludes `first_detected_at` and
`record_json`. Before authoring this new quality selector, rerun the
already-GREEN `test_persisted_quality_requires_typed_json_timestamp_agreement` and
`test_logical_projection_rejects_noncanonical_record_json` controls; timestamp-only
agreement and canonical-byte rejection remain separate regression evidence and are not
claimed as correction REDs.

The fund target is exact `FundItemAttribute` at
`silver_fund_item_attribute`, not the already-complete wide
`silver_public_fund_item`/`FundItemValue` projection. Independently derive and compare
`grain`, `fund_item_id`, `fund_item_id__quality_status`, `attribute_code`,
`attribute_code__quality_status`, `attribute_code_raw`, `source_row_number`, and
canonical `record_json` from the strict parsed `FundItemAttribute`. The quality
mandatory selector mutates each listed uncovered scalar, while the fund-attribute
mandatory selector mutates each of its projected physical columns one at a time. The
later common-checker selector combines those reached guards with the prior-GREEN quality
timestamp/canonical-JSON controls in otherwise valid Parquet. Because the
two mandatory logical-projection guards already entail rejection at the shared checker,
record that integration selector first-GREEN without production changes. Production
must parse once, canonicalize once, and compare the full projection; a handpicked field
list or comparing JSON only to itself is forbidden.

`ParquetBatchWriter.write_batch` consumes one outer iterable once. On each yield it
requires `isinstance(row, Mapping)`, copies the exact ordered string-key mapping
immediately before requesting the next item, and validates every column's exact
physical scalar against that frozen copy before Arrow conversion. Exercise a reused
mutable mapping that changes between yields, a custom read-once `Mapping`, dict and
mapping-subclass controls, and non-mapping sequence/object IDs. Include all exact
string/int/date/local-naive-datetime/UTC-aware-datetime/Decimal(38,18)/bool/null
boundaries. No `len`, second iteration, delayed references to caller mappings, or
Arrow coercion may define acceptance. Wrap the `pq.ParquetWriter(...)` constructor in
the typed `SERIALIZATION_FAILED` boundary; constructor failure closes/exits the owned
sink context exactly once with the original exception triple, marks the writer closed,
does not unlink an ambiguous leaf, and never leaks the raw exception. Existing
write/close/abort tests remain regression coverage for the same exactly-once exit rule.

Recompute and compare the canonical deep `TableSpec` fingerprint at every trust
boundary. The existing first-GREEN fingerprint integration already covers writer
construction and verifier entry; rerun those IDs only as regressions and never count
them as correction REDs. The three mandatory families contain only uncovered hooks:
writer after construction and before each batch snapshot, Arrow write, close, and abort;
staged verification after leaf open and before each read batch, after the last read,
before registration, on every handle batch access, and on every set lookup/declaration;
final verification after inventory entry open and before each read batch, checked-facts
return, local-authority seal mint, inventory issuance, and result construction. Fault
hooks mutate every top-level spec field and every nested `ColumnSpec` field at each
uncovered boundary and restore it only after the assertion. Every mandatory ID must
first fail for that uncovered hook and then fail closed before it can return facts, a
seal, a handle, or a result.

Replace the accidental `extend` surface with only
`extend_verified(*, owner: OwnedStageArtifactOwner, verifications:
tuple[StagedParquetVerification, ...]) -> StagedParquetSet`; keep direct construction
disabled. Add exact
`require_complete() -> None`. The first interface selector may make raising skeletons
GREEN, after which the valid extension, atomic supersession, and completeness selectors
must each independently RED before their behavior is added. Extension accepts a
distinct but value-equal exact aware-UTC `datetime`, requires `owner is self._owner`,
validates the exact supplied tuple and all prospective members, same-owner
registrations, timestamp values, prefix/order/duplicates, and frozen leaf/
spec/physical facts before calling the owner's one atomic replacement operation. If
validation or owner registration raises, the predecessor remains the sole live set and
no successor token escapes; on success the exact registered successor becomes live and
the predecessor is superseded exactly once. `require_complete` accepts only the exact
eleven registered tables in `TABLE_SPECS` order and reruns all live checks.

Each staged verification and handle freezes the exact leaf object plus relative path,
descriptor-derived device/inode/type/mode/link facts, owner registration identity,
physical size/SHA, and deep spec fingerprint observed by the successful read. No caller
can edit or replace these facts to pass registration. `verification_for(name)` must
locate the exact registered pair, reopen the owner-held leaf, recompute size/SHA on the
same descriptor, compare all frozen leaf/spec facts, close, run the owner rescan, and
only then return it. `iter_batches` and every set/report/database consumer put the
post-read digest, owner rescan, and exact context exit in `finally`; inject a consumer
exception before the first batch, between batches, and after the final batch, plus
digest/rescan/exit faults, and prove exactly-once close with no successful downstream
fact.

Replace lexical `Path` workspace ownership with a held trusted-parent directory
descriptor capability. Production chooses and opens the trusted OS temp parent
internally; the test seam supplies only a pre-opened descriptor/identity capability,
never a mutable path. Generate an internal bounded random root basename, call
`os.mkdir(name, mode=0o700, dir_fd=parent_fd)` with bounded `EEXIST` retries, then open
that root using `O_DIRECTORY | O_NOFOLLOW` relative to the held parent and freeze its
descriptor identity. Create the spill directory with descriptor-relative `os.mkdir`
then open/revalidate it the same way; create only the ownership marker with
descriptor-relative `O_CREAT | O_EXCL | O_NOFOLLOW`, exact `0o600` mode, and frozen
descriptor identity. The unique-key database remains pathless `:memory:`; there is no
root-level DuckDB store leaf, and any `keys.duckdb` or other unexpected root entry is an
ambiguity that is preserved, never opened or removed. DuckDB may create bounded spill
files only below the owned spill directory. Keep parent, root, and spill descriptors
held through their last safe use. The lifecycle order is exact: first close DuckDB; only
after a successful close enumerate and preflight the root, marker, spill directory, and
every spill entry through held descriptors; remove only the exact registered spill
entries in fixed order; close the spill descriptor and remove the spill directory
relative to the root; remove the ownership marker last among root entries; revalidate
that the root descriptor still identifies the frozen empty directory; close the root
descriptor and remove that exact root relative to the held parent; then close the parent
descriptor. A DuckDB close failure authorizes no enumeration or deletion and retains
the entire workspace tree byte-for-byte; it only releases held OS descriptors without
mutating the tree. A later unlink/rmdir failure retains the exact remaining tree and
reports the last proven ownership state.
Root/child/marker ABA,
same-inode marker mutation, hardlink/symlink substitution, ambiguous enumeration, or a
cleanup fault fails closed, records only redacted recovery state, and never opens,
chmods, truncates, unlinks, or otherwise changes an external victim.

Workspace failures use this closed non-publication taxonomy; the reserved catch-all
`VERIFICATION_INCOMPLETE` is forbidden here. Freeze the exact mapping:

- `parquet-workspace-create`, `parquet-workspace-open`, and
  `parquet-workspace-revalidate` use `ArtifactContractError(EXACT_TREE_MISMATCH)` for
  descriptor/tree creation, ownership, identity, marker content, mode/link,
  unexpected-entry, and pre-cleanup rescan failures.
- `parquet-workspace-configure`, `parquet-unique-index-create`,
  `parquet-unique-index-insert`, `parquet-unique-index-query`, and
  `parquet-unique-index-close` use
  `ArtifactContractError(DATABASE_VALIDATION_FAILED)` for DuckDB connect/configuration,
  operation, or connection-close failures.
- `parquet-workspace-cleanup` uses
  `ArtifactContractError(STAGING_CLEANUP_FAILED)` once cleanup is authorized, including
  descriptor close, unlink, rmdir, or retained-remainder failure.

An observed duplicate remains only
`UNIQUE_KEY_MISMATCH`/`verify-parquet-unique-key`. These paths never reuse CP7
publication/rollback codes or reserve a target basename. Public context contains no
path or SQL; immutable internal context contains only exact allowlisted reason labels.
Parameterize every fault site and assert exact code/operation/published-false/redaction,
close ordering, retention state, and absence of a raw DuckDB/Arrow/OS exception.
The external-victim selector is a derived first-GREEN acceptance authored after the
mandatory descriptor-root and marker-last cleanup selectors have driven the no-follow,
identity-preflight, and no-ambiguous-delete behavior; it must require no production
change.

After all 22 mandatory selectors and the four derived acceptances are individually
recorded, run these correction-focused aggregates before the full Step 8 gates:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/integration/artifacts/test_parquet_verification.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  src/finproof/data/artifacts/manifest.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  src/finproof/data/artifacts/manifest.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  src/finproof/data/artifacts/manifest.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/integration/artifacts/test_parquet_verification.py
```

Then rerun every command in Step 8, including full pytest, source audit, handoff,
schema catalog, pre-commit, expected-resource/artifact absence, writable-source check,
diff check, and status. Before the correction commit, `git diff --name-only` must equal
the correction file map actually used and must not contain STATUS or any plan. Append
the exact 22 RED/GREEN observations, four first-GREEN regressions, focused/full gate
outputs, file list, and unresolved risk to the ignored correction report; label it
“candidate for fresh review,” never “complete” or “Checkpoint 4 next.” Run
`git diff --check`, stage only that exact implementation/test list, run
`git diff --cached --check` and `git diff --cached --name-only`, then commit:

```bash
git add src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  src/finproof/data/artifacts/manifest.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/integration/artifacts/test_parquet_verification.py
git diff --cached --check
git diff --cached --name-only
git commit -m "fix: close Task 5 checkpoint 3 review gaps"
git status --porcelain
```

If and only if the approved fixture condition was actually reached, add
`tests/helpers/artifacts.py` in a separate `git add` before the cached checks and require
it in the cached name-only output. Otherwise it must be absent.

Require an empty post-commit status and dispatch a fresh independent review of the
original candidate plus correction commit. The reviewer must replay every finding,
attack the private final seal and one-use inventory transition, enumerate every
quality/fund physical/JSON field, mutate every spec boundary, fault every workspace
operation, and verify descriptor-relative marker-last no-victim cleanup. Any remaining
Critical or Important restarts this correction loop with a new focused RED and separate
fix commit. STATUS and the three documentation-closure files remain untouched until a
fresh 0 Critical / 0 Important verdict is recorded.

#### Checkpoint 3 third correction: close fresh verdict 0C / 4I serially

Fresh review of `07aeca26` found 0 Critical and 4 Important issues. That commit remains
an unaccepted CP3 candidate. This third correction owns only the four findings below;
it does not rewrite the initial 69/8 evidence or the prior correction's 22/4 evidence.
Obtain independent approval of this plan-only addition first. After approval, make one
separate documentation commit from the current plan-only diff, then require a clean
worktree before authoring any new test:

```bash
git diff --check
git diff --name-only
git status --short
git add docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: plan Task 5 checkpoint 3 third review correction"
git status --porcelain
```

Both name-only outputs must contain only this dedicated plan, and final status must be
empty. Record the resulting docs commit as the clean third-correction base in the
ignored CP3 report. This subsection again overrides Step 8's original instruction to
update/add STATUS before implementation: STATUS, the legacy plan, and all completion
checkboxes remain untouched through the fix commit and its fresh review. All Step 8
repository gates and absence/source-permission/diff/clean checks remain mandatory.

The exact third-correction implementation file map is:

- Modify: `src/finproof/data/artifacts/table_specs.py`
- Modify: `src/finproof/data/artifacts/serialization.py`
- Modify: `src/finproof/data/artifacts/parquet_io.py`
- Modify: `tests/unit/data/artifacts/test_table_specs.py`
- Modify: `tests/unit/data/artifacts/test_serialization.py`
- Modify: `tests/unit/data/artifacts/test_parquet_io.py`
- Modify: `tests/integration/artifacts/test_parquet_verification.py`
- Modify: `tests/helpers/artifacts.py`

No manifest implementation, other helper, config, schema, hashing primitive, source data,
later-checkpoint module, STATUS, legacy plan, or this plan belongs in the implementation
commit. Stop for plan/reviewer approval if the correction truly requires any other
file.

Author one selector only after its predecessor is GREEN. These are seven mandatory
RED/GREEN selectors and there are no derived acceptances in this third correction. All
symbols already exist at `07aeca26`, so a missing import, newly inserted raising
skeleton, broad exception assertion, or earlier invalid fixture is not acceptable RED
evidence. Each parameter family must prove every ID reaches the one uncovered boundary;
do not reuse already-rejected foreign models, pre-close workspace faults, or earlier
copy/forge cases as new REDs. Run the exact nodes in this order:

```text
tests/unit/data/artifacts/test_table_specs.py::test_closed_table_spec_registry_accepts_only_exact_frozen_table_specs_tuple
tests/unit/data/artifacts/test_table_specs.py::test_closed_table_spec_registry_ordered_specs_satisfies_cp2_kernel_port
tests/unit/data/artifacts/test_serialization.py::test_fund_wide_revalidation_rejects_json_coercible_forged_decimal_string_and_nested_model_leaves
tests/unit/data/artifacts/test_parquet_io.py::test_owned_stage_owner_protocol_resolves_exact_staged_types_without_object_parameters
tests/integration/artifacts/test_parquet_verification.py::test_post_close_spill_enumeration_os_fault_is_typed_exact_tree_mismatch
tests/integration/artifacts/test_parquet_verification.py::test_workspace_parent_and_precleanup_revalidation_os_faults_are_typed_exact_tree_mismatch
tests/integration/artifacts/test_parquet_verification.py::test_workspace_cleanup_os_faults_are_typed_staging_cleanup_failed
```

The concrete `ClosedTableSpecRegistry` in `table_specs.py` is the sole production
implementation of CP2 manifest's structural `ClosedTableSpecRegistry` port. Its
constructor requires `type(specs) is tuple`, `specs is TABLE_SPECS`, exact length/order,
and `specs[index] is TABLE_SPECS[index]` for all eleven entries; construct the singleton
only after the frozen tuple exists. Reject a list, generator/arbitrary iterable,
equal-valued rebuilt tuple, tuple containing one copied/equal `TableSpec`, foreign spec,
short/long tuple, duplicate, and adjacent/full reversal. Every invalid parameter ID
uses otherwise valid frozen specs and must be observed admitted by the current
constructor before the exact identity gate is added. Export only
`TABLE_SPEC_REGISTRY = ClosedTableSpecRegistry(TABLE_SPECS)`; do not add a general
registry factory or caller-extensible registration route.

Only after that constructor family is GREEN, author the missing-port selector.
`ordered_specs() -> tuple[TableSpec, ...]` must re-run the existing exact registered/deep
fingerprint guard for each member and return `TABLE_SPECS` itself, not a list, rebuilt
tuple, structural copy, iterator, or mutable view. Type a local assignment from
`TABLE_SPEC_REGISTRY` to CP2 manifest's `ClosedTableSpecRegistry` protocol and pass it
through a synthetic kernel spy that calls `ordered_specs()` and observes the exact
eleven identities/order. This selector's RED is the genuinely absent method, not one of
the constructor failures. Focused and repository mypy must prove the structural port
without changing CP2's protocol or kernel.

The FundItem selector targets only the remaining Fund-specific JSON-coercion hole.
Build an otherwise exact registered `silver_fund_item`/`FundItem` pair, then use
test-only `model_construct`/`object.__setattr__` to place: a JSON-coercible `str` where
one nested representative normalized value is declared `Decimal`; a `str` subclass in
an exact string leaf; and an equal-field subclass/forged instance at a nested
`FundItemValue` or representative `NormalizedValue` model boundary. Every ID must be
accepted by the current Fund-only canonical-JSON round trip and reach no earlier
top-level registered-pair or Decimal-range failure. `_revalidate_wide` must instead
validate the original Python object graph with exact model/wrapper/scalar identities
and strict Python-mode reconstruction. It rejects before producing canonical JSON or
physical columns; it never invokes `canonical_record_json`/`model_validate_json` as a
validation step, never converts string to Decimal/path/date/enum, and preserves the
already-GREEN valid FundItem round trip plus representative/lineage behavior. Do not
claim the existing top-level subclass, nonfinite Decimal, overflow, or generic physical
scalar selectors as new RED evidence.

Resolve the staged owner protocol annotations through forward references rather than
weakening them to `object`. Freeze these exact parameters while token return/arguments
remain opaque `object`:

```python
def _register_staged_verification(
    self,
    value: "StagedParquetVerification",
    handle: "StagedParquetHandle",
) -> object: ...

def _require_registered_staged_verification(
    self,
    value: "StagedParquetVerification",
    handle: "StagedParquetHandle",
    token: object,
) -> None: ...

def _require_registered_staged_handle(
    self,
    handle: "StagedParquetHandle",
    token: object,
) -> None: ...

def _register_staged_set(self, value: "StagedParquetSet") -> object: ...

def _replace_registered_staged_set(
    self,
    previous: "StagedParquetSet",
    value: "StagedParquetSet",
) -> object: ...

def _require_registered_staged_set(
    self,
    value: "StagedParquetSet",
    token: object,
) -> None: ...
```

Use the quoted annotations shown because the protocol precedes the three classes.
`typing.get_type_hints` must resolve every value/handle/set parameter to the exact class
and find no `object` there. In `tests/helpers/artifacts.py`, update all staged
value/handle/set parameters across its six owner registration/require/replace methods
to the same quoted exact staged types; only opaque token parameters and token returns
remain `object`. Update other CP3 test owner/spy annotations to conform without adding
`Any`, casts, or cross-domain unions. Rerun the already-GREEN staged
registration/copy/forge/mixed-owner selectors as regressions: exact runtime type checks
must still prevent an arbitrary object from reaching an owner registration/require/
replace callback. The new RED is only the protocol's current object-typed parameter
surface; do not manufacture another runtime acceptance already covered by those prior
selectors.

The final workspace has three distinct typed OS-fault phases. First, after DuckDB closes
successfully but before deletion is authorized, enumerate spill entries and revalidate
their relative identities. Inject `OSError` independently at post-close spill
`listdir`/`scandir`, relative `stat/open`, and descriptor `fstat` sites; every ID must
raise only `ArtifactContractError(EXACT_TREE_MISMATCH)` with operation
`parquet-workspace-revalidate`, `published=False`, redacted public output, and the exact
allowlisted internal reason. Second, inject the same OS fault class at trusted-parent,
root, marker, and spill pre-cleanup descriptor/relative revalidation sites, including
parent `fstat`, root/spill enumeration, marker open/read/close, and relative identity
checks. They have the same exact-tree code/operation. No family may use
`pytest.raises(Exception)` or accept a raw/wrapped-only `OSError`; every parameter ID
asserts the exact `ArtifactContractError` fields and that no deletion began.

Third, once cleanup is authorized, every OS failure belongs only to
`ArtifactContractError(STAGING_CLEANUP_FAILED)` with operation
`parquet-workspace-cleanup`, including spill-entry rename/unlink, spill descriptor
close, spill rmdir, marker rename/read/close/unlink, empty-root verification, root
rename/descriptor close/rmdir, parent revalidation/descriptor close, and any retained
remainder. Introduce an explicit internal cleanup phase so helpers translate according
to phase rather than their generic pre-cleanup reason. Inject one otherwise valid fault
at every named site and prove no raw `OSError` escapes, no external/unowned entry is
touched, already ambiguous entries are retained, and the exact remaining owned tree is
reported only in immutable internal context. Connection close remains the prior
`DATABASE_VALIDATION_FAILED` boundary because deletion has not been authorized. These
three selectors are intentionally split so post-close enumeration, ordinary
revalidation, and destructive cleanup cannot mask one another.

After all seven selectors have individual RED/GREEN and immediate regression evidence,
run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check \
  src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/helpers/artifacts.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/helpers/artifacts.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/helpers/artifacts.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
```

Then run every Step 8 command unchanged: focused CP2/CP3 tests, unchanged Task 1-4
regressions, repository Ruff format/check, repository mypy, full pytest, source audit,
handoff, schema catalog, pre-commit, expected-resource/artifact absence, writable-source
check, diff check/stat/name-only, and status. Append a distinct “third correction”
section to the ignored report with all seven exact RED reasons, smallest GREEN results,
aggregate/full outputs, diff list, and unresolved risk; label it only “candidate for
fresh review.” Before commit, name-only must contain exactly the eight implementation/
test files above and no docs/STATUS. Stage and commit only:

```bash
git add src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/helpers/artifacts.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
git diff --cached --check
git diff --cached --name-only
git commit -m "fix: close Task 5 checkpoint 3 registry and boundary gaps"
git status --porcelain
```

Require empty status and dispatch a fresh independent review against `07aeca26`, the
approved third-correction plan commit, and the fix commit. The reviewer must independently
attack registry container/member identity/order/length and CP2 port conformance, forged
Fund nested models/scalars without JSON coercion, every post-close/revalidation/cleanup
OS fault mapping, and resolved staged-owner annotations plus mypy. Any Critical or
Important finding restarts a new serial correction with its own approved plan and fix
commit. Only a fresh 0 Critical / 0 Important verdict unlocks the existing docs-only
closure below.

#### Checkpoint 3 fourth correction: close fresh verdict 0C / 4I serially

Fresh review of `aa3f4107` found 0 Critical and 4 Important issues. Keep that commit as
an unaccepted candidate. This fourth correction is additive evidence only: it does not
rewrite the initial 69/8, first-correction 22/4, or third-correction 7/0 matrices.
Obtain independent approval of this plan-only addition, then create a separate
documentation commit and a clean implementation base before writing any RED:

```bash
git diff --check
git diff --name-only
git status --short
git add docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: plan Task 5 checkpoint 3 fourth review correction"
git status --porcelain
```

The name-only outputs contain only this plan and final status is empty. Record the docs
hash as the fourth-correction base in the ignored report. This subsection overrides
Step 8's pre-review STATUS/file-map instruction only for this correction; every Step 8
verification, absence, source-permission, diff, clean-status, fix-commit, and independent
review gate remains mandatory. STATUS, legacy plan, and completion checkboxes stay
unchanged until the new fix receives 0 Critical / 0 Important.

The exact fourth-correction implementation file map is:

- Modify: `src/finproof/data/artifacts/table_specs.py`
- Modify: `src/finproof/data/artifacts/serialization.py`
- Modify: `src/finproof/data/artifacts/parquet_io.py`
- Modify: `tests/unit/data/artifacts/test_table_specs.py`
- Modify: `tests/unit/data/artifacts/test_serialization.py`
- Modify: `tests/integration/artifacts/test_parquet_verification.py`

No manifest/helper/config/schema/hashing/source/later-checkpoint module, unit Parquet
test, STATUS, legacy plan, or this plan belongs in the implementation commit. Stop for
plan/reviewer approval if another file is truly required.

Author one selector only after the previous selector and its immediate regressions are
GREEN. These are five mandatory RED/GREEN selectors and no derived acceptances. Every
symbol already exists at `aa3f4107`; do not add a missing-symbol skeleton or cite an
aggregate failure. Parameter families prove every ID reaches the uncovered boundary.
Do not count the already-GREEN foreign tuple, Fund wrapper/representative, pre-cleanup
workspace typing, or generic cleanup-code selectors again. Use this exact order:

```text
tests/unit/data/artifacts/test_table_specs.py::test_closed_registry_rejects_foreign_generator_typed_without_pulling_it
tests/unit/data/artifacts/test_serialization.py::test_fund_python_graph_recursively_rejects_exact_model_children_with_forged_scalar_subclasses
tests/integration/artifacts/test_parquet_verification.py::test_default_trusted_parent_open_dup_and_fstat_faults_are_typed_and_release_every_descriptor
tests/integration/artifacts/test_parquet_verification.py::test_trusted_parent_identity_fault_is_typed_and_releases_before_workspace_creation
tests/integration/artifacts/test_parquet_verification.py::test_cleanup_post_rename_fault_context_matches_spill_entry_spill_marker_and_root_filesystem_state
```

`ClosedTableSpecRegistry.__init__` performs its closed gate before duplicate-column or
any other element validation. The exact sequence is: reject `type(specs) is not tuple`
with `TypeError`; require `specs is TABLE_SPECS`; require exact length eleven; require
each indexed member `specs[index] is TABLE_SPECS[index]`; only after all four gates may
production inspect a spec or iterate the accepted tuple for deep validation. The first
selector supplies a foreign generator whose `__iter__`/`__next__` increments a counter
and raises a sentinel if touched. Current code pulls it in the duplicate-column loop;
the RED must observe that pull. GREEN requires immediate typed rejection with the
counter still zero. Include non-tuple iterable, list, and iterator controls in the same
reached family, but rerun prior equal-copy/order/length/member cases only as GREEN
regressions. Do not call `tuple(specs)`, `len` on a foreign non-tuple, `iter`, `next`, or
access an element before rejecting its runtime container type.

Preserve the original duplicate-column contract after moving the closed gate. Rewrite
the already-GREEN
`test_table_spec_module_skeleton_rejects_closed_registry_fixture` fixture so it does
not pass a foreign tuple: under `try/finally`, use test-only `object.__setattr__` to
temporarily replace the `columns` of one exact `TABLE_SPECS` member with an otherwise
valid tuple containing one duplicate name,
call `ClosedTableSpecRegistry(TABLE_SPECS)`, require the same duplicate-column
`ValueError`, then restore the exact original columns object and rerun the registered
deep-fingerprint guard. This is regression evidence, not a sixth RED. The production
constructor must perform container/object/length/indexed-member gates first and then
retain its duplicate-column validation for the accepted exact tuple. Do not delete,
weaken, bypass, or change that selector to merely expect the earlier closed-gate error.

The Fund selector starts from an otherwise exact registered `FundItem`, then forges
inside exact outer model instances so earlier top-level/wrapper identity guards remain
GREEN. Recursively validate the original Python graph before strict model reconstruction:

- every wrapper and representative is its exact declared Pydantic class;
- every representative/equivalent `SourceCellLocator` is exact and every locator field
  has exact runtime type (`str`, `PurePosixPath`, `int` but never `bool`/an `int`
  subclass, exact `date` but never `datetime`/a subclass, or `None` where declared);
- `contributing_rows` is an exact tuple of exact `SourceRow`; every SourceRow scalar,
  `raw_payload` tuple/string child, `cells` tuple, exact `SourceCell`, and SourceCell
  scalar/date child has its declared exact runtime type;
- every normalized leaf uses exactly its declared scalar type or `None`, every raw/rule
  field is exact `str`, every quality field is exact `QualityStatus`, and all
  tuple/model boundaries remain exact.

Use `model_construct`/`object.__setattr__` only in the test to inject independently an
`int` subclass into locator/row/cell positions, a `str` subclass into locator,
raw-payload/cell/raw/rule positions, a forged child model with otherwise equal fields,
and a date/datetime subclass at applicable/snapshot positions. All IDs are accepted by
the current shallow exact-model checks and must reach the new recursive guard. Monkeypatch
`canonical_record_json` with a fail-on-call sentinel for every invalid case: rejection
must occur first, and neither canonical JSON nor `model_validate_json` may be called.
Keep valid Fund serialization/round-trip, Decimal, representative/equivalent lineage,
and contributing-row consistency tests GREEN. Do not duplicate the already-driven
JSON-coercible Decimal-string or outer nested-model REDs.

Default trusted-parent acquisition is one typed setup transaction. Put
`tempfile.gettempdir`, parent `os.open`, `_TrustedWorkspaceParent` descriptor `os.dup`,
duplicate `os.fstat`, original-descriptor release, and capability `_take`
inside the `_final_verification_workspace` setup `try` before any root name/mkdir. Map
every OS failure only to `ArtifactContractError(EXACT_TREE_MISMATCH)` with operation
`parquet-workspace-open`, `published=False`, redacted output, and an exact allowlisted
reason literal `workspace_open_failed`. Track acquired descriptors explicitly: on every failure close each successfully
acquired original/duplicate/taken descriptor exactly once, never close an unacquired or
already-transferred descriptor, and create no root/marker/spill entry.

The first trusted-parent selector injects independent failures at default parent open,
dup, and fstat of the duplicate; a descriptor ledger proves no leak or double close and
no raw `OSError`. Only concrete `os.open`, `os.dup`, and `os.fstat` hooks are faulted;
there is no invented transfer hook. Only after it is GREEN, the second selector makes
the concrete fstat identity differ at the capability identity check for both default
and supplied trusted-parent capabilities. On that failed identity check the capability
or setup owner releases its one descriptor
exactly once, no descriptor is lost between owners, and root creation is never reached.
Do not reuse the prior root/spill/marker creation or pre-cleanup revalidation IDs as new
RED evidence.

Cleanup retained state is a transactional observation, not a prediction. Split rename
from its fallible post-rename identity/content check. Immediately after each successful
`os.rename`, the very next non-fallible statement updates the in-memory state from
`owned` to its exact tombstone name/state before any `stat`, `open`, `read`, hash,
descriptor close, unlink, or rmdir can fail. After successful deletion, update that
state to `removed`. Do not list per-file names or one field per spill entry in error
context. Freeze one fixed-field, fixed-width, path-free summary string:

```text
v1;r=O;s=O;m=O;n=0000000000000000;o=0000000000000000;t=0000000000000000;d=0000000000000000;a=0000000000000000;p=N;u=0000000000000000
```

`r`/`s`/`m` are one-character root/spill/marker phases `O` (owned), `T`
(tombstone), or `R` (removed). `n`, `o`, `t`, `d`, and `u` are exact 16-lowercase-hex
unsigned counts for total, owned, tombstoned, removed, and unexpected spill/root
entries; require `o + t + d == n`. `a` is the exact 16-hex active spill-entry index and
`p` is its one-character phase `N/O/T/R`; when `p=N`, `a` is all zeroes and ignored.
Reject a count outside unsigned-64 range before cleanup authorization. This constant
number of bounded fields makes `internal_context["retained_state"]` a fixed-size
representation independent of spill-file count while still describing every aggregate
phase needed to reconcile the filesystem. It contains no temp/root path or entry name.

Immediately after a spill-entry rename, decrement `o`, increment `t`, set `a` to that
entry's frozen-order index, and set `p=T`; after its unlink, decrement `t`, increment
`d`, and set `p=R`. Directory/marker/root renames update their one-character state
immediately. These assignments are non-raising state transitions and precede every
post-rename check.

The final selector is one coherent four-ID family. For a spill entry, spill directory,
marker, and root, allow the exact rename to succeed and then fault the first
post-rename identity/content check. Catch only
`ArtifactContractError(STAGING_CLEANUP_FAILED)`/
`parquet-workspace-cleanup`. Inspect the held test parent filesystem independently and
assert its original versus tombstone names and removed entries exactly equal the parsed
fixed summary counts, active index/phase, and root/spill/marker phases for every ID.
Current code records spill-entry removal only after
unlink and records spill/marker/root tombstone only after the helper's post-rename
check, so all four IDs must expose the mismatch in the RED run. GREEN may add a
non-raising transition callback or split helper, but must not weaken the post-rename
identity check, retry/delete an ambiguous entry, expose a path, or touch an external
victim. Rerun all earlier cleanup phase/error/marker-last/no-victim selectors as
regressions.

After all five serial selectors have recorded expected RED and smallest GREEN, run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check \
  src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/integration/artifacts/test_parquet_verification.py
```

Then rerun every Step 8 command unchanged, including full pytest, source audit,
handoff, schema catalog, pre-commit, expected-resource/artifact absence, writable-source
check, diff/stat/name-only/cached checks, and status. Append a distinct fourth-correction
section to the ignored report with five per-selector RED/GREEN observations, focused and
full outputs, exact diff, and unresolved risks; call it only a candidate for fresh
review. Before commit, name-only contains exactly the six implementation/test files
above and no docs/STATUS. Stage and commit only:

```bash
git add src/finproof/data/artifacts/table_specs.py \
  src/finproof/data/artifacts/serialization.py \
  src/finproof/data/artifacts/parquet_io.py \
  tests/unit/data/artifacts/test_table_specs.py \
  tests/unit/data/artifacts/test_serialization.py \
  tests/integration/artifacts/test_parquet_verification.py
git diff --cached --check
git diff --cached --name-only
git commit -m "fix: close Task 5 checkpoint 3 recursive trust gaps"
git status --porcelain
```

Require empty status and dispatch a fresh independent review against `aa3f4107`, the
approved fourth-correction plan commit, and the fix commit. The reviewer independently
proves zero-pull registry rejection and valid CP2-port behavior, recursive exact Fund
lineage/scalar validation before canonical JSON, typed/leak-free trusted-parent setup,
and retained-state/filesystem equality after each cleanup rename. Any Critical or
Important finding starts another approved serial correction. The review of `94ee69e`
found the two descriptor-ownership gaps owned by the fifth correction below, so that
candidate does not unlock docs closure.

#### Checkpoint 3 fifth correction: close fresh verdict 0C / 2I serially

Fresh review of `94ee69e` found 0 Critical and 2 Important issues. Keep that commit as
an unaccepted candidate. This fifth correction owns only descriptor ownership across
`os.close` calls that close the kernel descriptor and then raise. It does not reopen or
rewrite the initial 69/8, first-correction 22/4, third-correction 7/0, or
fourth-correction 5/0 evidence. Obtain independent approval of this plan-only addition,
then create a separate documentation commit and a clean implementation base before
authoring either RED:

```bash
git diff --check
git diff --name-only
git status --short
git add docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: plan Task 5 checkpoint 3 fifth review correction"
git status --porcelain
```

The unstaged and cached name-only outputs contain exactly this dedicated plan, and the
final status is empty. Record the approved plan commit as the fifth-correction base in
the ignored report. This subsection overrides Step 8's pre-review STATUS/file-map
instruction only for this correction. STATUS, the legacy plan, all checkpoint boxes,
and the final docs closure remain unchanged until the fifth-correction fix receives a
fresh 0 Critical / 0 Important verdict.

The exact fifth-correction implementation file map is:

- Modify: `src/finproof/data/artifacts/parquet_io.py`
- Modify: `tests/integration/artifacts/test_parquet_verification.py`

No manifest, table-spec, serialization, hashing, helper, config, schema, source,
unit-test, STATUS, legacy-plan, or documentation file belongs in the implementation
commit. Stop for plan/reviewer approval if another file is truly required.

Author one selector only after the preceding selector and its immediate regressions are
GREEN. Both selectors are mandatory newly observed RED/GREEN evidence and there are no
derived acceptances in this correction. The existing generic open/dup/fstat release,
cleanup error-code, retained-state, marker-last, and descriptor-relative selectors are
prior-GREEN regressions, not additional REDs. Use this exact order:

```text
tests/integration/artifacts/test_parquet_verification.py::test_default_trusted_parent_close_then_raise_invalidates_original_and_releases_duplicate_once
tests/integration/artifacts/test_parquet_verification.py::test_workspace_cleanup_close_then_raise_releases_each_owned_descriptor_once_without_fd_reuse
```

The first selector reaches the default trusted-parent path only after parent `os.open`,
duplicate acquisition, and duplicate `fstat` have succeeded. Its close wrapper targets
only the original parent descriptor: it delegates to the saved real `os.close`, places
a live sentinel onto that now-free exact numeric descriptor with the saved real
`os.open`/`os.dup2`, and then raises `OSError`. Record every attempted close and every
acquired descriptor. The expected typed result is
`ArtifactContractError(EXACT_TREE_MISMATCH)`, operation `parquet-workspace-open`,
`published=False`, exact internal reason `workspace_open_failed`, no raw `OSError`, and
no root/marker/spill creation. The sentinel must remain live through an independent
saved-real `os.fstat`, proving the original number was never retried or used to close an
unrelated object. The capability's successfully acquired duplicate must be invalidated
and closed exactly once because setup aborted; assert its saved-real `os.fstat` fails.
Clean the sentinel through saved real functions after the assertions.

The smallest GREEN treats descriptor ownership as a state transition before a system
call, not as the return value of that call. Once
`_TrustedWorkspaceParent._from_open_descriptor(...)` succeeds, keep the duplicate
capability under explicit setup ownership. Immediately before closing the original,
copy its integer to a local, set the owning `parent_descriptor` slot to `-1`, and only
then call `os.close(local_descriptor)`. If that call raises, never retry the original
integer. Before disposing the duplicate on this aborted acquisition, similarly copy
the capability descriptor, set the capability's `_descriptor` to `-1`, and then close
the copied integer exactly once. The exception is still translated at the existing
typed setup boundary. Do not call `_take`, create a workspace entry, suppress the
original close error into success, or add a second numeric-FD cleanup owner.

Only after that selector and the earlier default/supplied trusted-parent regressions are
GREEN, author the second selector as one coherent three-ID family: `spill`, `root`, and
`parent`. Start with a valid workspace that is cleanup-authorized and capture the exact
three held descriptor identities. For each ID independently, let all earlier cleanup
operations succeed, then wrap only its normal cleanup `os.close`: call the saved real
close first, put a live sentinel on the same numeric descriptor using saved real
`os.open`/`os.dup2`, record the attempt, and raise `OSError`. Assert the public result is
only `ArtifactContractError(STAGING_CLEANUP_FAILED)` with operation
`parquet-workspace-cleanup`, `published=False`, and the already-frozen bounded retained
state matching the filesystem phase. Assert exactly one close attempt for the faulted
descriptor, one release for each other descriptor that was still owned at the failure
boundary, no attempt against a descriptor already transferred, and no duplicate close
number in the release ledger. Each sentinel remains live by saved-real `os.fstat`, and
an unrelated control descriptor remains live, proving cleanup never closes an FD that
the process reused. Clean test sentinels/control descriptors only through saved real
functions after all assertions.

The smallest GREEN freezes the same transfer-before-close rule at every cleanup close:

```python
descriptor = self._spill_fd
self._spill_fd = -1
os.close(descriptor)
```

Apply the identical ordering to `_root_fd` and `_parent_fd`; the actual attribute is
cleared before `os.close`, never after it. `_release_descriptors()` likewise copies one
nonnegative field to a local, clears that field first, and makes at most one suppressed
close attempt against the local. It may release other descriptors still owned after a
failure, but it must never retry a transferred numeric descriptor. A close-then-raise
fault stops the destructive cleanup sequence, preserves the already-recorded
retained-state/filesystem facts, and enters the existing typed cleanup wrapper; it does
not continue deleting, roll ownership back to the old integer, infer success from
`fstat`, close an unrelated replacement, or broaden cleanup. Rerun the prior cleanup
fault matrix—including its existing spill/root/parent close IDs—as GREEN regression
evidence, but do not count those prior selectors as newly authored behavior.

Run each new selector alone for its expected RED and smallest GREEN, in the frozen
order:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest -q \
  tests/integration/artifacts/test_parquet_verification.py::test_default_trusted_parent_close_then_raise_invalidates_original_and_releases_duplicate_once
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest -q \
  tests/integration/artifacts/test_parquet_verification.py::test_workspace_cleanup_close_then_raise_releases_each_owned_descriptor_once_without_fd_reuse
```

Then run the exact focused correction regressions and static gates:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check \
  src/finproof/data/artifacts/parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts/parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts/parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
```

Rerun every Step 8 command unchanged after those focused checks, including full pytest,
source audit, handoff verification, schema catalog, pre-commit, expected-resource and
artifact absence, writable-source scan, diff/stat/name-only/cached checks, and status.
Append a distinct fifth-correction section to the ignored report with the two serial
RED/GREEN observations, all three reached cleanup IDs, descriptor call/identity
ledgers, live-sentinel evidence, focused/full outputs, exact diff, and unresolved risk.
Call the result only a candidate for fresh review.

Before the fix commit, name-only contains exactly the two implementation/test files
above and no docs/STATUS. Stage and commit only:

```bash
git diff --check
git diff --name-only
git diff --stat
git status --short
git add src/finproof/data/artifacts/parquet_io.py \
  tests/integration/artifacts/test_parquet_verification.py
git diff --cached --check
git diff --cached --name-only
git commit -m "fix: close Task 5 checkpoint 3 descriptor ownership gaps"
git status --porcelain
```

Require empty status and dispatch a fresh independent review against `94ee69e`, the
approved fifth-correction plan commit, and the fix commit. The reviewer independently
faults the default original close after the real kernel close, proves the duplicate is
disposed exactly once, forces exact numeric-FD reuse at each spill/root/parent cleanup
close, and proves no release path retries or closes the unrelated replacement. Any
Critical or Important finding starts another approved serial correction with its own
plan and fix commits. Only a fresh 0 Critical / 0 Important verdict unlocks the
docs-only closure below.

Only after the final 0/0 verdict, make a separate docs-only closure: update
`docs/implementation/STATUS.md` with reviewed commit hash(es), reviewer counts/evidence,
all observed gate results, unresolved risk, and exact next task Checkpoint 4; mark CP3's
steps/evidence complete in this dedicated plan; and mark only legacy Task 5 Checkpoint 3
complete with Checkpoint 4 as the first incomplete legacy task. Run:

```bash
git diff --check
git diff --name-only
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
test ! -e artifacts
find source_material -type f -perm -222 -print
git status --short
git add docs/implementation/STATUS.md \
  docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md \
  docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md
git diff --cached --check
git commit -m "docs: close Task 5 checkpoint 3 review"
git status --porcelain
```

Require empty writable-source output and final status, no expected/artifact path, and
the pre-add diff list exactly these three files in lexical order:
`docs/implementation/STATUS.md`, the legacy phase plan, and this dedicated plan. No
decision/design/code/test/schema/config file belongs in the closure. CP4 may start only
after that clean closure commit; implementation, correction, and review-closure
evidence never share a commit.

Checkpoint 3 closure evidence recorded on 2026-08-15:

- approved redo base `d983f1a`; implementation and correction lineage: `065e9fc`,
  `07aeca2`, `aa3f410`, `94ee69e`, and `a80ef32`, with their separately approved
  plan/evidence commits `ec2ad7e`, `bd055cb`, `4d5bc9b`, `ac7d8eb`, `d61cca7`,
  `97473d2`, and `45c330f`;
- final independent review of `a80ef32`: Critical 0 / Important 0 / Minor 0;
- final exact correction aggregate: 617 passed and 1 skipped; CP2+CP3 focused: 802
  passed, 1 skipped, and 4 warnings; Task 1–4 regression: 533 passed; full repository:
  1,837 passed with 4 warnings in 322.38 seconds;
- Ruff format/check and mypy passed over 107 files; audit stayed 145,393 rows at
  `2026-07-11`; handoff stayed 61/9/41,384,928; catalog stayed 207; pre-commit,
  expected/artifact absence, source-read-only, diff, and clean-tree gates passed;
- no unresolved Checkpoint 3 blocker remains. The official expected baseline is still
  absent and deferred to Checkpoint 8. Exact next task: Checkpoint 4, complete generic
  Bronze streaming and bounded external staging, ordering, spill, and cleanup behavior.

---

### Checkpoint 4: Complete Bronze streaming, external staging, and source-audit observations

**Approved-plan boundary:** begin implementation only from clean `544cde44` plus this
independently approved documentation correction. Before code or tests, require reviewer
verdict 0 Critical / 0 Important, then stage exactly:

```bash
git diff --check
git diff --name-only
git status --short
git add docs/superpowers/specs/2026-08-14-phase1-task5-artifact-build-design.md \
  docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md \
  docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: harden Task 5 checkpoint 4 contracts"
git status --porcelain
```

Name-only must contain those three docs and final porcelain must be empty. Record that
commit as the clean CP4 implementation base in the ignored RED/GREEN report. Do not
edit `docs/implementation/STATUS.md`, code, tests, schemas, config, or decisions in this
plan-approval commit. D-025 already assigns these stage capabilities to CP4 and D-022/
D-024 already reserve expected authorization/publication activation for CP8, so this
correction clarifies their implementation boundary without editing or superseding a
frozen decision.

**Files:**

- Create: `src/finproof/data/artifacts/staging.py`
- Create: `src/finproof/data/artifacts/input_identity.py`
- Create: `src/finproof/data/artifacts/bronze.py`
- Create: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/config.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Modify: `src/finproof/data/source_manifest.py`
- Modify: `src/finproof/data/xlsx_stream.py`
- Create: `tests/unit/data/artifacts/test_staging.py`
- Create: `tests/unit/data/artifacts/test_input_identity.py`
- Create: `tests/unit/data/artifacts/test_bronze.py`
- Modify: `tests/unit/data/artifacts/test_foundations.py`
- Modify: `tests/unit/data/artifacts/test_manifest.py`
- Modify: `tests/unit/data/artifacts/test_reports.py`
- Create: `tests/integration/artifacts/test_bronze_fixture_build.py`
- Create: `tests/performance/test_artifact_external_staging.py`
- Modify: `tests/source_contract/test_source_manifest.py`
- Modify: `tests/source_contract/test_xlsx_stream.py`
- Modify: `tests/helpers/xlsx.py`

`tests/unit/data/artifacts/test_parquet_io.py` remains outside this checkpoint's exact
file map and must stay byte-identical. An initial incremental/cache-state mypy run
reported two `[import-untyped]` diagnostics for its line-138 local PyArrow import, but a
clean nonincremental analysis proves the existing top-level directive already
suppresses them; adding an inline ignore instead produces `[unused-ignore]`. Therefore
CP4 authorizes no edit, ignore, config change, or restaging of that file. Its existing
48-test file, focused Ruff checks, and fresh isolated nonincremental mypy run are
acceptance evidence only, followed by a mandatory fresh rerun of the standard full
`mypy src tests tools` gate. The selector count remains 53.

**Interfaces:**

- Produces direct-construction-disabled `ExternalOrderStore` only through
  `ArtifactBuildSession.open_external_order_store(config: ArtifactBuildConfig) ->
  AbstractContextManager[ExternalOrderStore]`. The production entry accepts only the
  live owner and strict config, fixes one thread, `1GiB`,
  `preserve_insertion_order=false`, private owner-created database/spill identities,
  and bounded batches, and accepts no caller path or limit. Module-private
  `_open_external_order_store_for_test(*, owner: ArtifactBuildSession, config:
  ArtifactBuildConfig, limits: ExternalOrderStoreTestLimits)` is the only low-limit
  test seam and is absent from production assembly. The store exposes only closed
  relations, `insert_batch`, `iter_ordered_batches`, failure cleanup, and success-only
  `close_and_remove_working_state()`. The latter preserves emitted Parquet/output
  stage content but closes the connection and removes only exact store-owned
  database/WAL/spill/temp/marker identities; it never removes the build-stage marker.
- Produces: `iter_bronze_columns(catalog: SourceSchemaCatalog) -> Iterator[Mapping[str, object]]`.
- Produces internal `SourceRowConsumer` protocol with exactly `consume(row: SourceRow) -> None`; it owns no workbook iterator and may not request/rescan source rows.
- Produces internal `BronzeFanoutSink(..., consumer: SourceRowConsumer | None)` with `consume_source_row(row: SourceRow) -> None`; the method enqueues that row's complete Bronze row and cells first, then invokes the registered consumer exactly once. `None` is valid for the CP4 Bronze-only fixture.
- Produces direct-init-disabled, noncopyable `ResolvedBuildInputBundle.from_settings(
  settings: Settings)`, which internally calls the CP1 resolver and binds its exact
  nine member objects to one per-instance owner capability without a module-global
  registry. Produces the held-nine verifier result only through
  `verify_build_inputs(settings: Settings, resolved: ResolvedBuildInputBundle) ->
  AbstractContextManager[HeldVerifiedBuildInputs]`. It accepts the exact live bundle,
  independently recomputes both roots and all nine namespace/path/kind/absolute-path
  declarations from trusted Settings, opens/
  retains every parent/name/file generation no-follow, computes
  observed size/SHA from those streams, and exposes only one-use
  `issue_identity_seal() -> object` plus `close()`. Issuance revalidates all nine
  identities and held-stream digests, transfers them to one opaque instance-owned seal,
  and invalidates the result.
- Produces direct-init-disabled `BuildInputIdentity.from_verified(*, seal: object)`,
  which consumes only that exact one-use held-nine seal, derives the exact ordered
  `ArtifactInput` tuple and entry-zero/one hashes, and becomes the sole descriptor
  owner. It accepts no tuple/path/hash/descriptor/caller-token argument and exposes only
  exact facts, `open_verified_input(kind=...)`, `assert_unchanged()`, and `close()`.
  Replacement, same-inode/same-size mutation, stale supplied SHA, copied/equal/forged
  seal/carrier, subclass, `object.__new__`, or reuse fails. The exact object is retained by the
  session and every build result; CP7's sole `ArtifactManifest.from_build(...,
  input_identity=...)` must consume that same object, retain it in the private frozen
  nonserialized `_build_input_identity` slot, and emit its tuple unchanged. Only
  `require_build_input_identity(value) -> None` observes this build authorization;
  JSON load/validation cannot mint it.
- Adds only held-stream parsing entries in their owning modules:
  `ArtifactBuildConfig.from_held_stream(stream: BinaryIO, *, versions: VersionBundle)
  -> ArtifactBuildConfig`, `validate_build_registry_versions_from_held_streams(*,
  datasets: BinaryIO, quality: BinaryIO, rating: BinaryIO, state: BinaryIO, versions:
  VersionBundle) -> None`, and `SourceFileManifest.from_held_streams(*,
  manifest_stream: BinaryIO, schema_catalog_stream: BinaryIO) -> SourceFileManifest`.
  They bounded-read/strict-parse but never close the exact
  seekable binary streams yielded by the identity; they accept no path/root/raw fd/
  caller bytes. Surrounding identity contexts revalidate digest, roots, parent mutation
  facts, basename, and leaf generation after parsing, so A-to-B-to-A replacement fails
  before parsed state enters the session. Earlier path loaders remain compatibility
  only and are absent from Task 5 assembly.
- CP2 `manifest.py` owns only `BuildInputIdentityView(Protocol)` with exact read-only
  `logical_inputs`, `source_manifest_sha256`, `schema_catalog_sha256`, and
  `assert_unchanged() -> None` plus `take_manifest_identity_seal() -> object`. Concrete
  identity issuance asks manifest's module-private issuer to register its exact object/
  frozen facts; `ArtifactManifest.from_build` accepts the view, validates/consumes that
  one-use seal, calls revalidation, and retains the exact object reference. It never imports or constructs
  concrete `BuildInputIdentity`, and `require_build_input_identity(value)` requires
  `value is` that stored view before another revalidation.
- Produces internal `ArtifactBuildSession.initialize(settings, versions, options, *,
  input_identity: BuildInputIdentity) ->
  AbstractContextManager[ArtifactBuildSession]` and `ingest_bronze(*, consumer:
  SourceRowConsumer | None = None) -> BronzeBuildResult`; it writes only to a
  recognized sibling stage and never publishes. Its exact state is `LIVE`, `CLOSING`,
  or `CLOSED`. Only `LIVE` can create/consume a capability. Abort removes only a fully
  recognized exact stage; ambiguity retains it, closes held child descriptors, and
  releases the advisory lock only after the last safe managed-exit action. CP7's
  one-use `transfer_candidate_stage()` moves the held parent/stage/parquet descriptors,
  marker identity, registrations, held-nine-input carrier close responsibility, and
  lock into a direct-init-disabled
  `OwnedCandidateStage`, closes the session, and leaves no path/basename/reconstructed
  second owner. Its one-use `issue_candidate_custody()` transfers those slots into one
  direct-init-disabled, noncopyable `CandidateStageCustody` and invalidates the bare
  stage object. CP7 `CandidateArtifactSet` retains that exact instance; no module-global
  candidate/stage/custody registry exists. `CandidateStageCustody` exposes only
  `open_verification_root()`, typed one-use `transfer_expected_accepted(...)`,
  `discard_if_exact()`, and `close()`; it
  exposes no path, descriptor, basename, rename, rollback, target, backup, or tombstone
  method. It also owns the held input descriptors until exact candidate discard or CP8
  publication completion. The managed root adapter is the only artifact-tree
  verification custody seam.
- `ArtifactBuildSession` is CP4's sole production `OwnedStageArtifactOwner` and
  `OwnedStageDatabaseOwner`, with one
  opaque owner token, injected UTC persistence timestamp, retained descriptors, and
  liveness checks. `claim_parquet_leaf(spec: TableSpec) -> OwnedStageParquetLeaf` binds
  that exact owner, stage marker, retained stage/`parquet` directory descriptors,
  frozen relative path, and one exclusive leaf identity;
  `claim_database_leaf() -> OwnedStageDatabaseLeaf` similarly reserves only
  `finproof.duckdb`. Its Parquet `create_verification_workspace()` exposes only a
  managed configured unique-key-index context over a separate exact marker-owned mode-
  0700 scratch child and owned mode-0600 store/spill identities, never their paths.
  CP4 `staging.py` also owns direct-init-disabled `SealedStageDatabase`; its managed
  database build returns only this neutral exact owner/leaf-registered physical seal,
  never a CP7 type.
  `BronzeBuildResult` carries the one owner-bound three-table `StagedParquetSet` plus
  observations; it has no bare handle tuple, CP2 inventory, or final handle.
- Copies the complete Section 9.2 CP4 database contracts into `staging.py` unchanged:
  `OwnedStageDatabaseLeaf`, `OwnedStageDatabaseOwner`, `ManagedStageDatabaseBuild`, and
  direct-init-disabled `SealedStageDatabase`; the exact signatures are frozen below.
  CP7 receives an explicit `owner` argument and cannot infer it from a leaf or set.
- Extends `VerifiedSourceFile` with exact manifest `size_bytes`. `iter_xlsx_rows`
  retains a no-follow parent directory descriptor and exact workbook descriptor,
  computes size/SHA from the same rewound stream passed to `ZipFile`, and revalidates
  parent/name/descriptor identity before metadata, before every yield, after the final
  row, on generator close, and after a same-stream size/SHA rescan. It never reopens the
  workbook path.
- Produces only strict frozen `BronzeSourceAuditObservations.from_bronze(...)` with the
  exact design prefix fields. CP4 defines no Silver/Complete type, transition, or
  report-producer factory. `BronzeBuildResult` carries the exact Bronze runtime type
  plus the same `BuildInputIdentity` object; CP4 rejects a fake/subclass/copy/forged
  later phase and cannot cast, serialize/reparse, phase-mutate, or render Bronze as a
  report. CP5 owns the Silver type/transition; CP6 owns Complete and the producer.

The exact CP4-owned database interfaces are copied here so implementation does not have
to infer them from a later checkpoint:

```python
class OwnedStageDatabaseLeaf(Protocol):
    @property
    def relative_path(self) -> PurePosixPath: ...
    def create_exclusive(self) -> AbstractContextManager[BinaryIO]: ...
    def open_verified(self) -> AbstractContextManager[BinaryIO]: ...
    def assert_unchanged(self) -> None: ...
    def unlink_if_exact_writer_owned(self) -> None: ...


class OwnedStageDatabaseOwner(OwnedStageArtifactOwner, Protocol):
    def claim_database_leaf(self) -> OwnedStageDatabaseLeaf: ...
    def create_database_build_workspace(
        self,
    ) -> AbstractContextManager["ManagedStageDatabaseBuild"]: ...
    def require_owned_database_leaf(self, leaf: OwnedStageDatabaseLeaf) -> None: ...
    def _register_sealed_database(
        self, value: "SealedStageDatabase", leaf: OwnedStageDatabaseLeaf
    ) -> tuple[object, object]: ...
    def _require_registered_sealed_database(
        self,
        value: "SealedStageDatabase",
        leaf: OwnedStageDatabaseLeaf,
        owner_token: object,
        leaf_token: object,
    ) -> None: ...


@dataclass(frozen=True, init=False)
class SealedStageDatabase:
    _owner: OwnedStageDatabaseOwner
    _leaf: OwnedStageDatabaseLeaf
    _owner_registration: object
    _leaf_issuance_token: object
    persistence_timestamp: datetime
    physical_size_bytes: int
    physical_sha256: str

    def validate_against(self, owner: OwnedStageDatabaseOwner) -> None: ...


class ManagedStageDatabaseBuild(Protocol):
    def open_writer(self) -> AbstractContextManager[duckdb.DuckDBPyConnection]: ...
    def checkpoint_close_and_seal(
        self, *, leaf: OwnedStageDatabaseLeaf
    ) -> SealedStageDatabase: ...
```

The verification-root seam is exact and path-free:

```python
class ManagedArtifactVerificationRoot(Protocol):
    def open_inventory(
        self, *, manifest: ArtifactManifest
    ) -> AbstractContextManager[VerifiedPhysicalInventory]: ...
    def take_expected_acceptance_seal(self) -> object: ...


@dataclass(frozen=True, init=False)
class HeldArtifactRootAdoption:
    pass


def adopt_held_artifact_root(
    adoption: HeldArtifactRootAdoption,
) -> AbstractContextManager[ManagedArtifactVerificationRoot]: ...


class OwnedCandidateStage:
    def assert_live(self) -> None: ...
    def issue_candidate_custody(self) -> "CandidateStageCustody": ...
    def close(self) -> None: ...


@dataclass(frozen=True, init=False)
class CandidateStageCustody:
    def open_verification_root(
        self,
    ) -> AbstractContextManager[ManagedArtifactVerificationRoot]: ...
    def transfer_expected_accepted(
        self,
        *,
        expected_acceptance_seal: object,
        receiver: "ExpectedAcceptedCustodyReceiver",
    ) -> None: ...
    def discard_if_exact(self) -> None: ...
    def close(self) -> None: ...


class ExpectedAcceptedCustodyReceiver(Protocol):
    def accept_transferred_custody(
        self, custody: "TransferredCandidateCustody"
    ) -> None: ...
```

CP2 `manifest.py` owns the direct-init-disabled registered one-use adoption value,
factory, and concrete managed root. CP4's stage duplicates only its exact held parent/
root descriptors through the CP2-private issuer and immediately passes the opaque value
to the public-in-package factory. Issuance/adoption revalidate the same parent/name/root
generation, transfer duplicate ownership once, and close every transferred descriptor
once on any exit; no caller receives the adoption, descriptor, basename, path, or
private field. `take_expected_acceptance_seal` fails unless the CP8 expected entry has
completed its final rescan on that exact still-live root and is one-use.

CP4 implements the held stage adapter but not a kernel call. CP7 adds
`ArtifactVerificationKernel.verify_candidate_core_from_root(...)` and CP8 adds/activates
`verify_expected_from_root(...)`; both consume only `ManagedArtifactVerificationRoot`
and neither accepts `Path`, descriptor integers, basenames, or private stage fields.

The source-audit typestate field inventory/order is exact:

```text
BronzeSourceAuditObservations
  source_snapshot_date
  source_manifest_sha256
  schema_catalog_sha256
  source_tables  # SourceTableAudit in PRBD01N001/PREF01N001/PREF02N001/PRFD01N001 order

SilverSourceAuditObservations
  source_snapshot_date
  source_manifest_sha256
  schema_catalog_sha256
  source_tables
  silver_tables  # five NamedExpectedObservedCount entries in report order
  quarantine_source_rows

CompleteSourceAuditObservations
  source_snapshot_date
  source_manifest_sha256
  schema_catalog_sha256
  source_tables
  silver_tables
  quarantine_source_rows
  exact_links
  exact_link_evidence
  exact_link_pair_sha256
```

All hashes are lowercase SHA-256; all expected/observed pairs are exact strict objects
with equal values; tuple order is closed. CP4 implements/tests only the Bronze prefix
and exact-type rejection. CP5 later drives the Silver successor; CP6 later drives the
Complete successor and report factory. Each successor must preserve exact predecessor
objects/values/order and add only its declared suffix. Extra/missing/reordered fields,
boolean counts, unequal values, wrong hashes, direct wrong-phase construction, and a
Bronze/Silver report input fail at the checkpoint that first owns that boundary.

- [x] **Step 1: Write REDs for fixed staging settings, ownership, spill, and cleanup**

Use one permanent report at
`/private/tmp/finproof-task5-checkpoint4-red-green.md`. Before production changes,
record exact base/selector/command, the observed missing-behavior failure, and the
smallest GREEN diff for each selector. Author and close these staging selectors in this
exact order; do not batch-author them or use one earlier failure as evidence for a
later family:

```text
tests/unit/data/artifacts/test_input_identity.py::test_held_build_inputs_skeleton_rejects_exact_resolved_bundle_fixture
tests/unit/data/artifacts/test_input_identity.py::test_resolved_build_input_bundle_recomputes_every_path_from_trusted_settings_and_rejects_foreign_members
tests/unit/data/artifacts/test_input_identity.py::test_held_build_inputs_open_exact_nine_nofollow_generations_and_freeze_observed_facts
tests/unit/data/artifacts/test_input_identity.py::test_held_build_inputs_reject_replacement_and_same_inode_mutation_before_seal
tests/unit/data/artifacts/test_input_identity.py::test_build_input_identity_consumes_only_one_use_held_seal_owns_revalidation_and_rejects_stale_tuple
tests/unit/data/artifacts/test_foundations.py::test_artifact_config_and_registry_parsers_consume_only_held_streams
tests/source_contract/test_source_manifest.py::test_source_manifest_and_catalog_parser_consume_only_held_streams
tests/source_contract/test_source_manifest.py::test_held_source_manifest_parse_rejects_basename_aba_before_context_exit
```

The skeleton adds only direct-init-disabled raising names. The bundle selector's RED is
the missing instance-owned resolver boundary; its smallest GREEN creates the bundle
from trusted Settings, independently recomputes both roots and all nine declarations,
and rejects copied/deepcopied/equal/subclass/`object.__new__`/foreign bundle or member
admission without a module-global registry. The held-open selector owns
the exact bundle/member identity/order/length admission, nine parent/name/file no-follow
opens, regular/single-link checks, and observed size/SHA facts; every mutation ID reaches
that boundary. The race selector separately replaces a basename and mutates bytes in
place with unchanged size/inode after initial hashing; issuance must revalidate/re-hash
the held generations and reject each case. The final
selector drives one-use result-to-seal-to-carrier ownership, exact entry-zero/one hash
derivation, open/assert/close, and copy/equal/subclass/`object.__new__`/token/reuse
rejection, including manifest-owned one-use identity-seal issuance that a structural
view fake cannot mint. It also constructs a well-formed stale `tuple[ArtifactInput, ...]` containing
the pre-replacement SHA and proves that tuple cannot enter any issuance signature.
The two parser selectors add only the owning-module held-stream APIs and prove config,
four registry headers, source manifest, and catalog parse from the exact retained
streams with no `Path`/root/fd/caller-bytes overload or compatibility-loader call. The
ABA selector changes a held basename A-to-B-to-A during parsing and requires the
identity context's parent-mutation/name/leaf/digest revalidation to reject before the
parsed object is returned to session assembly. Each parser leaves stream close and
after-parse revalidation to the surrounding identity context.

Before staging, close CP2's held artifact-root adoption extension serially:

```text
tests/unit/data/artifacts/test_manifest.py::test_held_artifact_root_adoption_skeleton_rejects_valid_issued_generation
tests/unit/data/artifacts/test_manifest.py::test_held_artifact_root_adoption_consumes_same_descriptor_generation_once_revalidates_and_closes
```

The first selector adds only CP2-owned raising adoption/managed-root names without
changing the approved path-root verifier. The second uses real held parent/root
descriptors and parameter IDs for copied/forged/reused issuance, foreign descriptor,
parent/name/root substitution, adoption failure, inventory failure, normal exit, and
close-then-reuse. It requires the same `_HeldArtifactTree` inventory behavior and
exactly-once close without exposing a raw fd, basename, path, or private attribute.
At CP4 `take_expected_acceptance_seal()` is present but always fails typed because no
expected route has run; the selector must not pre-authorize a transfer.

Only after all ten input/parser/adoption selectors are GREEN continue with staging:

```text
tests/unit/data/artifacts/test_staging.py::test_staging_module_skeleton_rejects_valid_session_fixture
tests/unit/data/artifacts/test_staging.py::test_artifact_module_ownership_excludes_identity_cycle_and_publication_transition_from_staging
tests/unit/data/artifacts/test_staging.py::test_build_session_initializes_exact_lock_marker_and_descriptor_owned_stage
tests/unit/data/artifacts/test_staging.py::test_build_session_rejects_concurrent_lock_and_ambiguous_orphan_without_mutation
tests/unit/data/artifacts/test_staging.py::test_build_session_enforces_live_closing_closed_state
tests/unit/data/artifacts/test_staging.py::test_build_session_abort_removes_only_exact_recognized_stage
tests/unit/data/artifacts/test_staging.py::test_build_session_ambiguous_abort_retains_stage_until_safe_lock_release
tests/unit/data/artifacts/test_staging.py::test_build_session_candidate_transfer_moves_descriptors_marker_registrations_input_custody_and_lock_once
tests/unit/data/artifacts/test_staging.py::test_candidate_stage_custody_is_instance_owned_and_opens_only_capability_bound_managed_verification_root
tests/unit/data/artifacts/test_staging.py::test_build_session_claims_exact_registry_parquet_leaf_exclusively
tests/unit/data/artifacts/test_staging.py::test_owned_parquet_leaf_rejects_foreign_copy_closed_owner_and_inode_substitution
tests/unit/data/artifacts/test_staging.py::test_external_order_store_production_entry_is_pathless_owner_config_only
tests/unit/data/artifacts/test_staging.py::test_external_order_store_fixes_production_settings_and_isolates_private_test_limits
tests/unit/data/artifacts/test_staging.py::test_external_order_store_orders_bounded_single_pass_batches_without_materialization
tests/unit/data/artifacts/test_staging.py::test_external_order_store_closes_before_exact_marker_last_cleanup
tests/unit/data/artifacts/test_staging.py::test_external_order_store_faults_retain_ambiguous_owned_state_and_preserve_target
```

The skeleton adds only raising names. The immediately following module-boundary
selector first rejects the incomplete/incorrect ownership map, then its smallest GREEN
places only raising protocol/type skeletons in their exact modules with the one-way
imports; it requires that manifest never import input identity while input identity
imports only manifest's narrow view/model, staging never imports publication, builder
owns no filesystem primitive, only the candidate holding the exact instance custody
may call its staging-owned typed transfer method, and only CP8 publication may call
that candidate bridge. It forbids candidate/stage/receiver/custody module-global
registries. It
implements no later runtime behavior. The session initialization,
concurrent/orphan refusal, lifecycle, exact abort, ambiguous retention, candidate
transfer, held managed verification-root custody, leaf claim,
leaf forgery/substitution, production API surface, fixed configuration/test seam,
bounded ordering, successful cleanup, and fault cleanup are independent behavior
families. Every parameter ID reaches its named boundary. A production signature that
contains `Path`, `stage_root`, `temp_directory`, `memory_limit`, `threads`, a DuckDB
connection, or caller SQL fails the pathless-interface selector even if runtime
defaults happen to be safe.

Create a private stage fixture and spy on the internal DuckDB configuration boundary;
assert exactly one thread, `1GiB`, `preserve_insertion_order=false`, and a temp
directory derived from the owner-created private descriptor child without exposing that
spelling through the store API/result. Insert unsorted keys in batches, externally
order into batches of at most the configured limit, and prove no table-sized `list`,
DataFrame, or tuple is created by using an iterator that raises on `len`, second
iteration, or retained weak references.

Fault-inject disk-full/write, close, spill-directory removal, marker removal, and connection-close failures. Each must raise its typed pre-publication error, leave a pre-existing published target byte-identical, close before cleanup, and never delete an unmarked or mismatched directory. Concurrent lock ownership and ambiguous orphan-stage markers must fail without mutation. On the success path, first deliberately omit `close_and_remove_working_state()` and prove exact-tree readiness fails because store-owned database/WAL/spill/temp/marker state remains; then call it and assert emitted Parquet/stage ownership bytes remain while only verified store-owned working state disappears. Parameterize partial cleanup, inode substitution, symlink, wrong marker, and ambiguous path; each must fail closed without broadening deletion.

Close CP4's separately owned database-stage behaviors serially in
`tests/unit/data/artifacts/test_staging.py`. Author only the next selector after the
previous one has reached its intended RED and smallest GREEN:

```text
tests/unit/data/artifacts/test_staging.py::test_database_stage_skeleton_rejects_valid_owner_fixture
tests/unit/data/artifacts/test_staging.py::test_database_stage_claims_one_same_owner_final_leaf
tests/unit/data/artifacts/test_staging.py::test_database_stage_build_uses_pathless_owned_scratch_and_fixed_settings
tests/unit/data/artifacts/test_staging.py::test_database_stage_checkpoints_closes_and_rejects_wal_before_seal
tests/unit/data/artifacts/test_staging.py::test_database_stage_exclusively_nofollow_copies_fsyncs_and_closes_final_leaf
tests/unit/data/artifacts/test_staging.py::test_database_stage_reopens_hashes_and_rescans_final_leaf
tests/unit/data/artifacts/test_staging.py::test_database_stage_closes_before_cleanup_and_rejects_abort_or_substitution_ambiguity
tests/unit/data/artifacts/test_staging.py::test_sealed_stage_database_requires_same_owner_registration_and_exact_leaf
tests/unit/data/artifacts/test_staging.py::test_sealed_stage_database_rejects_copy_equal_object_new_and_token_forge
```

The skeleton may add only raising names. Leaf claim, scratch creation/settings,
checkpoint/close/WAL, final copy/fsync/close, final reopen/hash/rescan, cleanup/abort/
substitution, valid seal registration, and seal forgery are independent behavior
families. Every parameter ID must reach the named boundary; no generic
`ExternalOrderStore` failure or earlier database failure is evidence for a later RED.

Expected: each named database-stage selector records its own RED/GREEN in order;
the sixteen preceding staging selectors also each have an individually observed RED
and smallest GREEN. The report has 25 ordered staging/database entries before Step 2.

- [x] **Step 2: Implement bounded staging and marker-owned cleanup only**

Step 2 records/refactors the already serially closed database-stage GREEN behavior; it
does not bulk-implement an unobserved database branch after one Step 1 failure.

Create the sibling lock/stage names exactly from the managed target basename and opaque operation ID. Create sidecar marker mode 0600 with operation ID, artifact-set ID, contract version, and target basename. Use static allowlisted DDL and parameters; no caller SQL/table name/path. On failure remove only a nonsymlink, exact-basename, exact-marker-owned private stage after the connection closes. If cleanup fails, preserve the recognized stage and raise `STAGING_CLEANUP_FAILED`.

Implement `ArtifactBuildSession` as the sole owner/context, not as a collection of
paths. Initialization acquires and retains the sibling-parent descriptor and advisory
lock, creates/opens the stage and `parquet/` directories descriptor-relatively, and
registers every exact leaf/store/seal/set object. `__exit__`, `abort`, and
`transfer_candidate_stage` each perform `LIVE -> CLOSING -> CLOSED` once. A normal
abort closes registered stores/writers, unlinks only exact registered children and the
marker in frozen order, closes descriptors, and releases the lock. On ambiguity it
does not delete; it records bounded recovery identity, closes child descriptors, and
releases the lock only as the final managed-exit step. Candidate transfer is available
only after all working state is closed/removed and atomically moves the exact held
parent/stage/parquet descriptors, marker identity, registration authority, and lock to
one `OwnedCandidateStage`, together with sole responsibility to close the exact retained
input carrier. It clears the session ownership slots before transfer and
leaves the closed session unusable. The stage then one-use issues an instance-owned
`CandidateStageCustody`, invalidates its bare interface, and returns only that opaque
noncopyable capability for candidate retention. No registry, stage path, or independently reconstructable
basename escapes. The custody can only open a managed verification-root
adapter through CP2's opaque one-use adoption of duplicated exact parent/root
descriptors, discard the exact still-staged generation, or close. It cannot rename/
rollback or name a target. The adapter's
`open_inventory(manifest=...)` creates one CP2 inventory bound to that descriptor and
closes it on every exit; neither side reads private fields or constructs `/dev/fd`.
The CP2 adoption factory owns same-generation revalidation, transferred-descriptor
close, and copied/forged/reused adoption refusal; staging never constructs
`_HeldArtifactTree` or passes a raw descriptor/path to a kernel/caller.

Create the resolved bundle, held-nine verifier, and `BuildInputIdentity` in
`input_identity.py` before session work. The bundle is constructed from trusted
Settings and retains the exact resolver members under one instance owner; the verifier
receives the same Settings, recomputes every root/path independently, and the identity
consumes only its one-use descriptor seal. Session initialization calls
`assert_unchanged`, requires the exact object, assumes its close responsibility, and
every result/manifest property returns that same object identity without becoming a
second descriptor owner. Parse build config and registry headers only through
`config.py`'s held-stream APIs, and source manifest/catalog only through
`source_manifest.py`'s held-stream API, while their exact carrier contexts remain open
for after-parse revalidation. Bronze manifest/catalog bytes and hashes are read only
from its held entries zero/one. No staging/bronze function accepts a parallel input tuple,
path, descriptor, or hash argument. Candidate discard and CP8 publication completion
close the carrier exactly once.

Keep imports acyclic: `manifest.py` owns `ArtifactInput`,
`BuildInputIdentityView`, held-root adoption, and managed-root types without importing
input identity/staging/publication; `input_identity.py` imports only that narrow view/
model plus CP1 resolver types; `staging.py` imports CP2/CP3 capabilities plus input
identity and owns build lock/marker/descriptor custody; `config.py` and
`source_manifest.py` own path-free held-stream parsers but never import input identity;
`bronze.py` consumes staging; `builder.py` later owns the `CandidateArtifactSet`
no-private-field bridge retaining one exact custody instance and orchestrates without
filesystem primitives. Publication defines only its narrow
candidate-method protocol and never imports builder; builder may import publication in
CP8. CP4 does
not create/import `publication.py`. CP7 publication later imports only staging's narrow
custody/typed-receiver contracts and never `OwnedCandidateStage` or a custody private field; staging never
imports publication. Target/
backup/tombstone markers and every authorization/rename/rollback/commit/recovery
transition belong only to publication, not staging. The module-boundary selector
inspects both the import graph and exported surfaces: a rename/helper/target marker in
staging, a filesystem primitive in `builder.py`, or a publication import from staging
fails before runtime staging work.

Open and retain the stage then `parquet/` directories descriptor-relatively with
no-follow checks. `claim_parquet_leaf` accepts only the exact registry spec, reserves
one path once, and its `create_exclusive` uses mode 0600
`O_CREAT | O_EXCL | O_NOFOLLOW`; open/assert/unlink revalidate the exact leaf and every
owner/marker ancestor. A copied/foreign/closed leaf or substituted inode fails. CP3
writer abort may request deletion only of its exact created inode; session cleanup owns
all broader recognized-stage cleanup and never treats a CP3 staged handle as a final
manifest entry.

`claim_database_leaf` is also single-use and same-owner. Separately,
`create_database_build_workspace()` creates a pathless unique marker-owned private
scratch capability whose `open_writer()` alone exposes the configured DuckDB connection
to CP7. The final database leaf itself exposes only binary `create_exclusive`,
`open_verified`, assert, and exact abort operations; it is not precreated/opened as an
empty DuckDB database. The CP4 managed seal, later invoked by CP7, creates the final leaf mode 0600 with
`O_CREAT | O_EXCL | O_NOFOLLOW`, bounded-copies a closed/WAL-free verified scratch DB,
fsyncs/closes, and reopens/hash/rescans it. Scratch/final substitution, close/checkpoint/
WAL/copy/fsync/hash/reopen failure, or cleanup/abort ambiguity blocks; cleanup removes
only exact owned scratch/final inodes and never an unowned name.

For successful completion, close the DuckDB connection first, enumerate the closed finite set of store-owned working paths, revalidate each nonsymlink inode and exact operation marker, remove children in the fixed safe order, and unlink the store marker last. `close_and_remove_working_state()` is idempotent only after a recorded successful cleanup; missing/partial/ambiguous state raises instead of guessing. It preserves all Parquet files, reports/models in memory, and the separate build-stage marker needed by publication.

Implement the production order store only behind
`session.open_external_order_store(config)`. Validate that config carries exactly one
thread and `1GiB`; derive all scratch leaves and DuckDB `temp_directory` internally
from descriptor-owned session children. The private test factory requires the same
live concrete session/config and accepts only a strict positive low-limit object. The
store never exposes its connection or filesystem spelling, and every CP5/6 consumer
uses its typed relation/batch methods inside the context. Preserve the nine database
interfaces/selectors above exactly; CP4 does not return a CP7
`StagedDatabaseVerification` or accept a CP7 callback.

- [x] **Step 3: Write REDs for full canonical Bronze fixture streaming**

Continue the same report and close the held-workbook boundary first, one selector at a
time in this exact order:

```text
tests/source_contract/test_source_manifest.py::test_verified_source_file_preserves_exact_manifest_size_bytes
tests/source_contract/test_xlsx_stream.py::test_xlsx_stream_parses_zip_from_one_held_nofollow_descriptor
tests/source_contract/test_xlsx_stream.py::test_xlsx_stream_rejects_workbook_swap_before_descriptor_open
tests/source_contract/test_xlsx_stream.py::test_xlsx_stream_rejects_workbook_swap_during_row_iteration
tests/source_contract/test_xlsx_stream.py::test_xlsx_stream_rejects_workbook_swap_after_last_yield_before_success
```

The second selector spies on `os.open` and `ZipFile` and proves only one no-follow
workbook open, regular/single-link descriptor admission, a file-object `ZipFile`, and
exactly-once close; its smallest GREEN need not yet add manifest digest or repeated
entry checks. The before-open replacement selector then drives exact manifest size/SHA
from that same held stream before parsing. The during-iteration selector independently
drives held-parent/name/descriptor identity revalidation before every yield. The
after-last-yield selector independently drives terminal identity plus rewound
same-stream size/SHA revalidation on normal exhaustion and generator close. The three
swap selectors use real atomic replacement of the verified basename before the
generator first advances, after its first yielded row, and after its last yielded row
but before the terminal `next()`/close. They require a typed source-contract error, no
success count, and exactly-once descriptor release. A same-size/same-inode byte mutation
is a reached parameter ID only of the terminal selector. No earlier selector may
pre-implement a later recheck, and no test-only production hook, second path open, or
path-derived `ZipFile` is permitted.

Only after all five held-reader selectors are GREEN, author these Bronze/audit selectors
serially and append every RED/GREEN observation to the report:

```text
tests/unit/data/artifacts/test_bronze.py::test_bronze_module_skeleton_rejects_complete_fixture
tests/unit/data/artifacts/test_bronze.py::test_bronze_columns_follow_exact_manifest_catalog_order
tests/unit/data/artifacts/test_bronze.py::test_bronze_source_row_preserves_payload_hash_locator_and_timestamp
tests/unit/data/artifacts/test_bronze.py::test_bronze_source_cells_reconstruct_each_exact_source_row
tests/unit/data/artifacts/test_bronze.py::test_bronze_sinks_flush_bounded_batches_in_manifest_order
tests/unit/data/artifacts/test_bronze.py::test_bronze_fanout_enqueues_complete_row_before_one_consumer_call
tests/integration/artifacts/test_bronze_fixture_build.py::test_bronze_ingestion_opens_and_iterates_each_workbook_once
tests/integration/artifacts/test_bronze_fixture_build.py::test_bronze_ingestion_accepts_none_consumer_without_rescan
tests/integration/artifacts/test_bronze_fixture_build.py::test_bronze_result_retains_exact_session_build_input_identity
tests/integration/artifacts/test_bronze_fixture_build.py::test_bronze_failure_aborts_once_without_retry_or_published_mutation
tests/unit/data/artifacts/test_reports.py::test_bronze_observations_require_exact_hashes_and_four_ordered_source_tables
tests/unit/data/artifacts/test_reports.py::test_cp4_bronze_observations_reject_forged_later_typestate_and_report_admission
```

The input-result selector requires `result.input_identity is session.input_identity`
and exact equality to the object created before session initialization; copies and
parallel tuple/hash parameters are forbidden. The two CP4 report selectors parameterize
every Bronze field/type/order/hash/equality rejection, but each ID reaches the Bronze
boundary rather than an earlier fixture error. Bronze has exactly snapshot, the two
carrier-bound hashes, and four ordered `SourceTableAudit` values. It has no
`with_silver`, Silver/Complete class, or report-producer factory in CP4. Structurally
equal fakes, subclasses, copies, `object.__new__` forgeries, injected suffix fields,
and dict/model-dump later-phase admission fail exact-type checks. Do not implement a
valid Silver or Complete transition to make this selector GREEN; CP5 and CP6 own those
separate REDs.

Extend the XLSX fixture to write all four complete canonical header sets. Include at least one valid row per table, one domestic malformed ID, one fund malformed ID, two interleaved valid rows for one fund item, one domestic ETF/fund exact pair, one ETN non-link, and unsorted product IDs.

Assert catalog rows follow manifest table order and contiguous column order. Assert every SourceRow is written before normalization, each `raw_payload_json` is the compact JSON array of exact strings, each payload SHA is NUL-join SHA-256, `loaded_at` is identical, every cell reconstructs the payload, and the exact complete locator joins its catalog/row once. With a test batch limit of two, assert max live row/cell batch is two and weakrefs from prior batches are released.

Register a spy `SourceRowConsumer` and assert, for every row, that the complete Bronze row/cell set has already been enqueued when `consume(row)` is called, the identical `SourceRow` object is passed, and the call occurs exactly once. Add a source iterable/workbook-open sentinel that raises on a second iteration or second open; require the combined Bronze-plus-spy flow to succeed with one pass. Run the same fixture with `consumer=None` and require the Bronze-only result to remain valid. Freeze the one-method protocol: the fan-out may not hand consumers the workbook iterator, a callback for fetching the next row, or a partially emitted row.

Add expected/observed `BronzeSourceAuditObservations` mismatch cases for every
manifest/catalog hash and Bronze row/cell/column count; construction/validation must
fail and no `SourceAuditReport` may exist or be written at CP4. Add serialization/
checksum/count/consumer failure after one batch and prove the published target is
unchanged and the managed session performs one exact abort; the consumer failure must
not cause retry or a second `consume` call.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/source_contract/test_source_manifest.py \
  tests/source_contract/test_xlsx_stream.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/unit/data/artifacts/test_input_identity.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/integration/artifacts/test_bronze_fixture_build.py -q
```

Expected GREEN only after every exact selector above has its individual RED and
smallest GREEN recorded. This aggregate run is regression evidence, never a substitute
for a missing selector entry.

- [x] **Step 4: Implement one-pass Bronze ingestion and streaming hashes**

Construct `ResolvedBuildInputBundle.from_settings(settings)`, pass that exact
instance plus the same trusted Settings into `verify_build_inputs`, and require the
verifier to recompute every namespace root/path/kind before opening. Issue the held
result's one-use seal after its second identity/
digest revalidation, then call `BuildInputIdentity.from_verified(seal=...)` and pass
that exact descriptor-owning object into the managed session. Validate dataset/rule
versions and snapshot only by opening the retained config/registry entries and invoking
their owning `config.py` held-stream parsers, never from a free tuple or stale path.
Open entries zero/one together and call only
`SourceFileManifest.from_held_streams(...).verify(source_root)` while both retained
contexts remain live through parser return and after-parse ABA/digest revalidation.
Do not call any path loader from Task5 assembly. Add exact manifest `size_bytes` to
each `VerifiedSourceFile`. For every data workbook, `iter_xlsx_rows` opens/retains the
parent and basename descriptors, validates size/SHA on the held stream, rewinds that
stream into `ZipFile`, performs the frozen before-each-yield identity checks, and
rechecks the same stream/entry on exhaustion or close. The builder neither opens a
workbook itself nor rechecks by raw path. Stream each verified workbook exactly once in
manifest order and write catalog once. For each `SourceRow`,
`BronzeFanoutSink.consume_source_row` enqueues one complete Bronze row and all of its
cells into bounded sinks, updates Bronze observations, and only then invokes the
registered `SourceRowConsumer.consume(row)` once. Because the sort key begins with
frozen source table order, write final Bronze Parquet in bounded batches without a
Python sort. The consumer never owns or iterates the workbook; a consumer exception
fails the managed session without retry. This seam is the only CP5 normalization feed,
so no official workbook is rescanned.

After each Bronze writer closes, reopen only via its owned leaf and create the CP3
three-table `StagedParquetSet` through the live session owner. Track input/
catalog/Bronze observed counts in immutable accumulators and construct only
`BronzeSourceAuditObservations` after exact config equality, using only the retained
input carrier's two hashes. `BronzeBuildResult` returns the same carrier object. Do not construct, serialize,
hash, or stage a `SourceAuditReport`, CP2 inventory, final `VerifiedParquetTable`, or
`TableVerificationResult`: the remaining Parquets/reports/database/manifest do not yet
exist.

- [x] **Step 5: Add external-sort scale RED/GREEN and run checkpoint gates**

Author
`tests/performance/test_artifact_external_staging.py::test_external_order_store_spills_and_orders_131073_rows_with_bounded_state`
as the next mandatory RED and append it to the report. Set
`pytestmark = pytest.mark.performance`, generate exactly 131,073 unsorted unique keys
(more than two final row groups), and force spill only through the private test factory
with the same live owner/config. Assert output order, uniqueness, maximum emitted batch
65,536, one thread, private unexposed spill identity, no retained input rows, and exact
close-before-cleanup. First observe the intended missing scale/spill behavior, implement
the smallest GREEN. Without editing or staging the pre-existing Parquet test file,
prove its behavior and the clean static-analysis result directly:

```bash
git diff --exit-code -- tests/unit/data/artifacts/test_parquet_io.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/data/artifacts/test_parquet_io.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check \
  tests/unit/data/artifacts/test_parquet_io.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  tests/unit/data/artifacts/test_parquet_io.py
FINPROOF_CP4_MYPY_CACHE="$(mktemp -d /private/tmp/finproof-cp4-mypy.XXXXXX)"
MYPY_CACHE_DIR="$FINPROOF_CP4_MYPY_CACHE" \
  UV_CACHE_DIR=/private/tmp/finproof-uv-cache \
  uv run mypy --no-incremental src tests tools
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy src tests tools
git diff --exit-code -- tests/unit/data/artifacts/test_parquet_io.py
```

Record the focused pytest result as exactly 48 passed, both focused Ruff commands as
GREEN, the isolated no-incremental full mypy result as GREEN, and the immediately
following standard full mypy rerun as GREEN. The two diff commands must be empty. An
incremental-only diagnostic is recorded as a cache anomaly, never converted into a
repository edit or suppression. Then run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/source_contract/test_source_manifest.py \
  tests/source_contract/test_xlsx_stream.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/unit/data/artifacts/test_input_identity.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/integration/artifacts/test_bronze_fixture_build.py \
  tests/performance/test_artifact_external_staging.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/artifacts/input_identity.py \
  src/finproof/data/artifacts/config.py \
  src/finproof/data/artifacts/manifest.py \
  src/finproof/data/artifacts/bronze.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/reports.py \
  src/finproof/data/source_manifest.py \
  src/finproof/data/xlsx_stream.py \
  tests/helpers/xlsx.py \
  tests/source_contract/test_source_manifest.py \
  tests/source_contract/test_xlsx_stream.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/unit/data/artifacts/test_input_identity.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/integration/artifacts/test_bronze_fixture_build.py \
  tests/performance/test_artifact_external_staging.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/artifacts/input_identity.py \
  src/finproof/data/artifacts/config.py \
  src/finproof/data/artifacts/manifest.py \
  src/finproof/data/artifacts/bronze.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/reports.py \
  src/finproof/data/source_manifest.py \
  src/finproof/data/xlsx_stream.py \
  tests/helpers/xlsx.py \
  tests/source_contract/test_source_manifest.py \
  tests/source_contract/test_xlsx_stream.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/unit/data/artifacts/test_input_identity.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/integration/artifacts/test_bronze_fixture_build.py \
  tests/performance/test_artifact_external_staging.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/artifacts/input_identity.py \
  src/finproof/data/artifacts/config.py \
  src/finproof/data/artifacts/manifest.py \
  src/finproof/data/artifacts/bronze.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/reports.py \
  src/finproof/data/source_manifest.py \
  src/finproof/data/xlsx_stream.py \
  tests/helpers/xlsx.py \
  tests/source_contract/test_source_manifest.py \
  tests/source_contract/test_xlsx_stream.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/unit/data/artifacts/test_input_identity.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/integration/artifacts/test_bronze_fixture_build.py \
  tests/performance/test_artifact_external_staging.py
```

Expected GREEN: fixture Bronze is complete/reconstructable, the optional consumer receives each already-enqueued row exactly once with no rescan, staging is externally sorted/bounded, all failures isolate the published target, and a Bronze/input observation mismatch cannot be advanced or rendered as a successful source-audit report.

- [x] **Step 6: Run full gates, commit the exact implementation, review, then close docs**

The report must contain eight held-input/identity/parser selectors, two CP2 held-root-adoption
selectors, all 25 staging/database selectors, five held-reader selectors, twelve
Bronze/typestate selectors, and the one performance selector—53 total—in their exact
authoring order, each with its own
observed RED and smallest GREEN. Record derived
first-GREEN behavior honestly and stop for plan correction; never manufacture a
failure. Then run every repository gate on the exact candidate:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/core tests/unit/domain tests/unit/registry \
  tests/unit/data/normalization tests/contract/test_quality_issue_schema.py -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy src tests tools
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/audit_source_data.py --check
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/verify_handoff.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/extract_schema_catalog.py --check
PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache \
  UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pre-commit run --all-files
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
test ! -e artifacts
find source_material -type f -perm -222 -print
test -z "$(find source_material -type f -perm -222 -print)"
git diff --check
git diff --stat
git diff --name-only
git status --short
```

The report has a separate unchanged Task 1–4 regression section containing that exact
command, start/end time, exit code, observed pass/fail/skip counts and duration, and the
implementation commit hash. It may not cite the full-suite result as a substitute. Any
Task 1–4 failure is a hard stop before commit/review.

The exact implementation name-only inventory is these twenty files and no others:

```text
src/finproof/data/artifacts/bronze.py
src/finproof/data/artifacts/builder.py
src/finproof/data/artifacts/config.py
src/finproof/data/artifacts/input_identity.py
src/finproof/data/artifacts/manifest.py
src/finproof/data/artifacts/reports.py
src/finproof/data/artifacts/staging.py
src/finproof/data/source_manifest.py
src/finproof/data/xlsx_stream.py
tests/helpers/xlsx.py
tests/integration/artifacts/test_bronze_fixture_build.py
tests/performance/test_artifact_external_staging.py
tests/source_contract/test_source_manifest.py
tests/source_contract/test_xlsx_stream.py
tests/unit/data/artifacts/test_bronze.py
tests/unit/data/artifacts/test_foundations.py
tests/unit/data/artifacts/test_input_identity.py
tests/unit/data/artifacts/test_manifest.py
tests/unit/data/artifacts/test_reports.py
tests/unit/data/artifacts/test_staging.py
```

STATUS, the legacy plan, this dedicated plan, design/decision docs, schemas, config,
source files, CP5+ modules, the ignored report, and
`tests/unit/data/artifacts/test_parquet_io.py` are absent. Stage exact names rather than
directories, recheck the cache, commit the 20 behavioral files, and require clean
status:

```bash
git add src/finproof/data/artifacts/bronze.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/config.py \
  src/finproof/data/artifacts/input_identity.py \
  src/finproof/data/artifacts/manifest.py \
  src/finproof/data/artifacts/reports.py \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/source_manifest.py \
  src/finproof/data/xlsx_stream.py \
  tests/helpers/xlsx.py \
  tests/integration/artifacts/test_bronze_fixture_build.py \
  tests/performance/test_artifact_external_staging.py \
  tests/source_contract/test_source_manifest.py \
  tests/source_contract/test_xlsx_stream.py \
  tests/unit/data/artifacts/test_bronze.py \
  tests/unit/data/artifacts/test_foundations.py \
  tests/unit/data/artifacts/test_input_identity.py \
  tests/unit/data/artifacts/test_manifest.py \
  tests/unit/data/artifacts/test_reports.py \
  tests/unit/data/artifacts/test_staging.py
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: stream complete Bronze artifacts"
git status --porcelain
```

Fresh review compares the approved CP4 plan base, implementation commit, and report.
It traces one raw value through held-workbook size/SHA/catalog/row/cell/hash, forces the
before/during/after swap cases, checks every session lifecycle/lock-transfer and
abort-retain boundary, attacks held-nine input issuance/replacement/mutation/stale-SHA
and same-object result/manifest retention, rejects forged/copy-resolved members through
trusted-Settings bundle recomputation, forces config/registry/manifest/catalog held-
stream parsing plus A-to-B-to-A basename replacement, proves stage custody has no transition
authority and opens only CP2's same-generation opaque-adopted managed kernel-root
adapter with exactly-once descriptor closure, verifies pathless fixed-bound stores and all exact Section 9.2
database APIs, attacks the Bronze typestate plus absence/rejection of CP5/6 producers,
checks the staging-to-publication one-way import boundary, direct candidate custody
retention, typed atomic receiver acceptance, and absence of global custody registries,
forces external spill and
every close/cleanup fault, verifies the separately recorded Task 1–4 regression, and
proves no pre-publication failure mutates a target.
Require 0 Critical / 0 Important; any finding receives a separately approved plan/fix
cycle and another fresh review.

Only after the fresh 0/0 verdict, create a separate docs-only closure. Update
`docs/implementation/STATUS.md` with exact commit/reviewer/report/gate evidence and
Checkpoint 5 as next; mark only CP4 steps/evidence complete here; mark only legacy
Task 5 Checkpoint 4 complete. Run the full absence/source-permission/diff gates again,
stage exactly those three docs, commit `docs: close Task 5 checkpoint 4 review`, and
require empty porcelain. No design, decision, code, test, schema, config, expected
contract, or artifact file belongs in that closure.

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/audit_source_data.py --check
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/verify_handoff.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/extract_schema_catalog.py --check
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
test ! -e artifacts
find source_material -type f -perm -222 -print
test -z "$(find source_material -type f -perm -222 -print)"
git diff --check
git diff --name-only
git status --short
git add docs/implementation/STATUS.md \
  docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md \
  docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: close Task 5 checkpoint 4 review"
git status --porcelain
```

Checkpoint 4 closure evidence recorded on 2026-08-15:

- implementation/correction lineage: `e91ed04` -> `278d20ce` -> `4bdebfbf`;
- final independent narrow verification of `4bdebfbf`: Critical 0 / Important 0,
  with no backlog item;
- final lifecycle selector matrix: 4 passed; related Parquet/staging/Bronze regression:
  140 passed; CP4 focused aggregate: 761 passed and 1 explicit AF_UNIX-unavailable
  capability skip; unchanged Task 1–4 regression at the implementation checkpoint:
  533 passed;
- final network-enabled full repository suite: 2,015 passed with 4 deliberate
  adversarial Pydantic serialization warnings in 324.75 seconds;
- Ruff format/check and fresh no-incremental plus clean-cache standard mypy passed over
  116 source files; audit stayed 145,393 rows at `2026-07-11`; handoff stayed
  61/9/41,384,928; catalog stayed 207; pre-commit, expected/artifact absence,
  source-read-only, diff, and clean-tree gates passed;
- the official expected baseline remains absent and deferred to Checkpoint 8. Exact
  next task: Checkpoint 5, implement wide Silver products/attributes, bounded
  public-fund item collapse, D-021 quality persistence and quarantine, the Silver
  source-audit typestate, and deterministic quality-summary reporting.

---

### Checkpoint 5: Wide Silver, one-group public-fund collapse, persisted D-021 quality, and deterministic reports

**Files:**

- Modify: `src/finproof/registry/rating.py`
- Modify: `src/finproof/data/normalization/public_funds.py`
- Create: `src/finproof/data/artifacts/silver.py`
- Create: `src/finproof/data/artifacts/quality_persistence.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/staging.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Modify: `tests/unit/registry/test_rating_registry.py`
- Create: `tests/unit/data/normalization/test_public_fund_group_adapter.py`
- Modify: `tests/unit/data/artifacts/test_staging.py`
- Create: `tests/unit/data/artifacts/test_silver.py`
- Create: `tests/unit/data/artifacts/test_quality_persistence.py`
- Create: `tests/unit/data/artifacts/test_quality_report.py`
- Create: `tests/integration/artifacts/test_silver_fixture_build.py`
- Modify: `tests/performance/test_artifact_external_staging.py`
- Create: `tests/performance/test_artifact_fund_streaming.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Extends `RatingRegistry` with
  `from_held_stream(stream: BinaryIO) -> RatingRegistry`. It bounded-reads and applies
  the exact `from_yaml` duplicate-key, shape, and semantic rules without closing the
  stream. The builder opens `RATING_SCALE_REGISTRY` only through its retained exact
  `BuildInputIdentity`, parses inside that held context, and completes the carrier's
  after-parse revalidation; Task 5 never reopens a rating path.
- Extends CP4's closed `ExternalOrderStore` with the exact relation names, typed
  `ExternalOrderRow`, typed batch insert/export, closed `ExternalOrderJoinOperation`,
  and typed bounded join export frozen in the design. Numeric key components are real
  nonboolean integer columns and string components remain exact strings, so numeric
  `2` orders before `10`; relation names, key schemas, SQL, connection, cursor, paths,
  and registration names remain private/closed. The three CP6 relation names and
  verifier methods are interface-compatible now but cannot produce successful CP6
  evidence before CP6 populates the required tables.
- Owns `BoundedRelationVerifier(Protocol)`, `QualityJoinObservations`,
  `ExactLinkedSide`, and `LinkedRecordJson` in `reports.py`, plus the stage-backed
  `StagedBoundedRelationVerifier` in `quality_persistence.py`. Every operation accepts
  and revalidates one live CP3 `StagedParquetSet`; it exposes no handle tuple, generic
  execute, caller SQL/table/path, CP2 inventory, or final handle. The implementation
  uses only the owner-managed `ExternalOrderStore`, fixed one-thread/1-GiB settings,
  static allowlisted joins, and batches of at most 65,536.
- Produces strict frozen `FundRowKeyClassification(item_key: str | None, issue: DataQualityIssue | None)`.
- Produces public `classify_public_fund_row(row: SourceRow) -> FundRowKeyClassification`; it invokes only the authoritative key validator and never `normalize_fund_attribute`.
- Produces public `normalize_public_fund_item_group(rows: Sequence[SourceRow]) -> FundCollapseResult`; it accepts one unique, source-row-ordered item group, invokes `normalize_fund_attribute` exactly once per valid row, and delegates the existing authoritative collapse behavior.
- Imports and persists only exact `finproof.domain.quality.DataQualityIssue`; no local
  alias, DTO, persisted-row wrapper, mapping, or shape-compatible substitute is
  accepted. Produces
  `persist_quality_issue(issue: DataQualityIssue, *, persistence_timestamp: datetime)
  -> DataQualityIssue` and validates the exact returned model and canonical D-021 JSON.
- Produces direct-construction-disabled `SilverArtifactEmitter` through only
  `for_session(*, session: ArtifactBuildSession, config: ArtifactBuildConfig,
  versions: VersionBundle, rating_registry: RatingRegistry) -> SilverArtifactEmitter`,
  with source method `consume(row: SourceRow) -> None` and
  `finalize(*, bronze_result: BronzeBuildResult) -> SilverBuildResult`. Builder must:
  open/parse held rating, create the emitter, call
  `bronze_result = session.ingest_bronze(consumer=emitter)`, then call
  `emitter.finalize(bronze_result=bronze_result)` exactly once. Finalization validates
  that exact result/input/owner/three-table set/observations/timestamp, closes source
  admission, drains/orders/writes/reopens six Silver tables, atomically extends the
  same set from three to nine in frozen order, verifies quality relations, constructs
  observations/report/instrumentation, and only then returns. There is no public
  `finish_fund_groups` or parameterless `finalize`.
- Produces direct-construction-disabled `SilverBuildResult` with exactly, in order,
  `input_identity`, `staged_tables`, `observations`,
  `quality_join_observations`, `quality_report`, and `instrumentation`. It retains the
  exact Bronze input carrier, the exact nine-table set, the predecessor-issued Silver
  observations, verified join observations, factory-issued report, and strict bounded
  `SilverBuildInstrumentation`; copy/subclass/object-new/equal-field/foreign-owner or
  reconstructed-member forgery is rejected. CP6 consumes this one object, never a
  parallel argument bundle.
- Extends exact `BronzeSourceAuditObservations` only through
  `observations.with_silver(silver_counts, quarantine_counts) ->
  SilverSourceAuditObservations`; the returned distinct type contains only verified
  Silver/quarantine observations and cannot enter the complete-only report factory.
  CP5 is the first owner of this method and runtime type; CP4 contains neither.
- Produces: `QualitySummaryReport.from_verified_quality(...) -> QualitySummaryReport` with closed lexical group ordering and timestamp-free semantic content.
- Populates the exact CP2 `QualitySummaryReport` model and its frozen
  `semantic_projection`; it does not implement CP2's artifact-file
  `ArtifactReportVerifier` port or wire the full kernel. CP7 reparses the written report
  through the retained inventory capability and supplies that concrete port.
- Freezes an acyclic import direction: rating imports no artifact module; staging
  imports no Silver/quality/report implementation; reports imports domain/closed model
  contracts only; quality persistence imports staging/parquet/report/domain but not
  Silver/builder; Silver imports its predecessors and authoritative normalizers;
  builder alone orchestrates forward. Runtime local imports may not hide a cycle.

**Serial selector ledger (31 mandatory RED/GREEN + 5 derived first-GREEN):**

Each numbered selector below is authored alone, run to its stated missing-behavior
RED, given the smallest GREEN, and followed by its directly related regression before
the next number is authored. An import/symbol failure authorizes only a skeleton and
the same selector must then reach a narrower behavioral RED. The multi-node commands
later in this checkpoint are aggregate gates, never RED evidence.

```text
01 tests/unit/registry/test_rating_registry.py::test_rating_registry_from_held_stream_parses_valid_yaml
02 tests/unit/registry/test_rating_registry.py::test_rating_registry_from_held_stream_matches_path_parser_and_never_closes_stream
03 tests/unit/registry/test_rating_registry.py::test_rating_registry_held_stream_preserves_duplicate_shape_and_semantic_errors
04 tests/unit/data/normalization/test_public_fund_group_adapter.py::test_public_fund_row_classifier_matches_authoritative_valid_and_malformed_keys
05 tests/unit/data/normalization/test_public_fund_group_adapter.py::test_public_fund_group_adapter_matches_global_collapse_for_order_variants
06 tests/unit/data/normalization/test_public_fund_group_adapter.py::test_public_fund_group_adapter_calls_attribute_normalizer_exactly_once_per_valid_row [derived first-GREEN acceptance: selector 05's generic one-group implementation already calls the authoritative normalizer exactly once per accepted row; do not manufacture a failure]
07 tests/unit/data/normalization/test_public_fund_group_adapter.py::test_public_fund_group_adapter_rejects_invalid_group_shapes_before_normalization
08 tests/unit/data/normalization/test_public_fund_group_adapter.py::test_global_public_fund_normalizer_reuses_classifier_and_group_adapter_without_drift
09 tests/unit/data/artifacts/test_staging.py::test_external_order_store_cp5_relation_inventory_is_exact_and_closed
10 tests/unit/data/artifacts/test_staging.py::test_external_order_store_typed_batch_insert_and_export_are_bounded
11 tests/unit/data/artifacts/test_staging.py::test_external_order_store_preserves_numeric_and_string_key_order
12 tests/unit/data/artifacts/test_staging.py::test_external_order_store_rejects_wrong_arity_bool_coercion_noncanonical_payload_and_duplicate_key
13 tests/unit/data/artifacts/test_staging.py::test_external_order_store_exposes_no_public_connection_sql_table_cursor_or_path_surface [derived first-GREEN acceptance: CP4 already froze this no-public-surface contract; do not manufacture a failure]
14 tests/unit/data/artifacts/test_staging.py::test_bounded_relation_verifier_has_exact_cp5_cp6_closed_signatures
15 tests/unit/data/artifacts/test_staging.py::test_external_order_store_closed_quality_join_revalidates_exact_live_staged_set
16 tests/unit/data/artifacts/test_quality_persistence.py::test_quality_persistence_accepts_only_exact_untimestamped_data_quality_issue_and_utc_build_time
17 tests/unit/data/artifacts/test_quality_persistence.py::test_persisted_quality_row_and_record_json_match_exact_d021_schema [derived first-GREEN acceptance: CP3's exact serializer/schema boundary composed with selector 16's persisted issue already entails this row/record contract; do not manufacture a failure]
18 tests/unit/data/artifacts/test_quality_persistence.py::test_quality_relation_external_sort_is_unique_and_globally_ordered
19 tests/unit/data/artifacts/test_quality_persistence.py::test_quality_join_observations_are_immutable_strict_and_internally_consistent
20 tests/unit/data/artifacts/test_quality_persistence.py::test_quality_relation_rejects_foreign_copied_incomplete_reordered_closed_or_timestamp_mismatched_set
21 tests/unit/data/artifacts/test_quality_persistence.py::test_quality_relation_rejects_missing_row_cell_raw_hash_timestamp_and_record_json_mismatches
22 tests/unit/data/artifacts/test_quality_report.py::test_quality_report_factory_accepts_only_exact_persisted_issue_stream_and_verified_join_observations
23 tests/unit/data/artifacts/test_quality_report.py::test_quality_report_derives_closed_lexical_groups_counts_and_excluded_grains [derived first-GREEN acceptance: selector 22 cannot construct the strict report without deriving these required closed groups and counts; do not manufacture a failure]
24 tests/unit/data/artifacts/test_quality_report.py::test_quality_report_semantic_projection_is_timestamp_path_and_rendering_independent [derived first-GREEN acceptance: CP2's timestamp-free semantic model composed with selector 22's factory already entails this independence; do not manufacture a failure]
25 tests/unit/data/artifacts/test_silver.py::test_silver_emitter_factory_accepts_exact_live_session_and_held_rating_registry
26 tests/integration/artifacts/test_silver_fixture_build.py::test_silver_builder_opens_rating_only_through_exact_build_input_identity_and_calls_in_order
27 tests/unit/data/artifacts/test_silver.py::test_silver_emitter_uses_exact_nonfund_normalizers
28 tests/unit/data/artifacts/test_silver.py::test_silver_emitter_consumes_each_row_once_only_after_bronze_enqueue
29 tests/unit/data/artifacts/test_silver.py::test_silver_emitter_stages_fund_keys_and_keeps_only_one_group_live
30 tests/unit/data/artifacts/test_silver.py::test_silver_finalize_requires_exact_bronze_result_owner_input_set_observations_and_timestamp
31 tests/unit/data/artifacts/test_silver.py::test_silver_finalize_drains_relations_and_extends_exact_set_from_three_to_nine
32 tests/unit/data/artifacts/test_silver.py::test_silver_finalize_faults_issue_no_result_and_leave_cleanup_with_session
33 tests/unit/data/artifacts/test_silver.py::test_silver_build_result_is_factory_only_with_exact_six_field_order_and_object_identity
34 tests/unit/data/artifacts/test_silver.py::test_silver_instrumentation_has_exact_names_counts_and_bounds
35 tests/unit/data/artifacts/test_quality_report.py::test_silver_observations_preserve_exact_bronze_prefix_and_reject_forged_or_complete_phase_admission
36 tests/performance/test_artifact_fund_streaming.py::test_silver_fund_and_relation_pipeline_stays_within_closed_streaming_bounds
```

- [ ] **Step 1: Implement held rating parsing with selectors 1-3**

Selector 1 initially fails because the classmethod is absent; add only a signature that
raises `NotImplementedError`, rerun the same final-success selector to the narrower
behavioral RED, then implement bounded valid parsing. Selector 2 owns equal registry
output and no-close behavior. Selector 3 reuses every path-parser duplicate-key,
invalid-shape, invalid-code/range and semantic fixture and requires identical typed
failure.

- [ ] **Step 2: Implement the public-fund adapter with selectors 4-8**

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

Instrument `normalize_fund_attribute` and assert exactly one call per accepted row.
Empty/multi-key/unsorted/duplicate-location/malformed-key groups fail before attribute
normalization. Promote only the authoritative classifier and one-group adapter; make
global `normalize_public_funds` reuse them and keep every Task 4 edge fixture unchanged.

- [ ] **Step 3: Extend typed external ordering and the bounded relation port with selectors 9-15**

Add only the exact relation enum inventory and typed row/join models before relation
behavior. Each boundary checks exact enum/runtime scalar/key arity, canonical payload,
unique key, owner/liveness and fixed batch size. Verify mixed keys against an oracle
where numeric `2 < 10` and string spelling remains byte-exact; bool and numeric strings
are rejected, not coerced. `StagedBoundedRelationVerifier` alone invokes the four
closed joins. Its quality join succeeds with the exact live staged set; foreign,
copied, closed, incomplete or substituted sets fail before any batch. CP6 signatures
are statically present but fail closed until the CP6 table set exists. Prove that no
connection, SQL, table spelling, cursor, registration name, filesystem path or generic
execute/join surface is caller-accessible. Underscored state may be touched only by the
owning module and narrow fault-injection tests, never a production consumer.

- [ ] **Step 4: Persist and verify D-021 quality/report semantics with selectors 16-24**

Pure normalizer issues retain `first_detected_at is None`. The persistence boundary
accepts only exact `DataQualityIssue`, rejects alias/mapping/subclass/pre-timestamped/
naive/non-UTC inputs, reconstructs a new strict model with the one build timestamp,
serializes terminal `Z`, and validates exact canonical JSON with the packaged/root
schema and explicit `FormatChecker`. It preserves source, raw hash, rule/version,
severity, reason, state and quarantine without caller aggregates.

Stage every issue by the frozen quality key and reject duplicate issue IDs or global
disorder. Define strict immutable `QualityJoinObservations` before the relation returns
one. The relation verifier then accepts only the exact nine-table set and streams
bounded mismatches/counts for Bronze row/cell/raw-SHA, typed/JSON timestamp, distinct
timestamps and logical hash. Sentinels reject `len`, second iteration, table-sized
list/tuple/DataFrame, or retention of a prior batch. The fixture observes two distinct
quarantined source rows; the issue total remains observed and is never frozen to 6,032.

The sole report factory single-pass consumes exact persisted issues plus that
observation and closed excluded-native-grain counts, derives every lexical group and
independently recomputes the timestamp-neutral quality logical hash. Moving or
pretty-rendering the report cannot change its semantic projection; timestamp/path
cannot enter it.

- [ ] **Step 5: Build the one-pass Silver emitter/result with selectors 25-35**

Selector 25 first fails on the absent factory. Add only the direct-init-disabled class,
then rerun the same final-success selector to the narrower factory-behavior RED before
issuing it for one exact live session and held-parsed rating registry. Selector 26
gives the builder a valid exact `BuildInputIdentity`, replaces every path opener with a
sentinel, swaps the rating basename before/after parse including A-to-B-to-A, and proves
the exact sequence `open_verified_input(kind=RATING_SCALE_REGISTRY)` -> held parser ->
emitter factory -> `ingest_bronze(consumer=emitter)` ->
`finalize(bronze_result=that_exact_result)`. The stream cannot outlive its context.

Then use unsorted bond/domestic/overseas rows and interleaved funds. Compare every wide
row/`record_json` with strict direct normalizer output; malformed domestic/fund rows
remain in Bronze, emit no normal Silver row and yield canonical exact issues.

During the only source pass,
`ArtifactBuildSession.ingest_bronze(consumer=emitter)` enqueues Bronze row/cells before
calling `consume` exactly once. The consumer performs:

- PRBD01N001 calls `normalize_bond(row, versions.dataset_version, rating_registry)` once and stages a wide row by product ID;
- PREF01N001 calls `normalize_domestic_listed(row, versions.dataset_version)` once and stages a wide row by product ID;
- PREF02N001 calls `normalize_overseas_listed(row)` once and stages a wide row by product ID;
- PRFD01N001 calls `classify_public_fund_row(row)`; malformed issues go directly to quality staging, valid canonical SourceRow JSON plus item key/source row enter the fund staging relation.

After ingestion, `finalize(bronze_result=exact_result)` validates every same-object
boundary before source admission closes. It externally drains one fund group at a
time, writes and reopens/verifies the six Silver tables, then atomically calls the
frozen set extension once in exact nine-table order. No caller may call a public drain
method. Failure at each drain/write/reopen/set/relation/report/result boundary issues
no result and keeps cleanup ownership in the live session. The successful factory
retains exactly the six frozen members and exact object identities. Instrumentation
has the exact four source IDs and five relation names in frozen order, nonboolean
nonnegative counts, exactly-once sums, and configured maxima.

`with_silver` preserves the exact Bronze prefix and adds only the five frozen Silver
counts plus the quarantine fact. It rejects direct/copy/subclass/object-new/equal predecessor,
wrong expected/observed values, repeated transition, link/evidence suffixes and report
admission. CP5 does not create Complete observations or `SourceAuditReport`.

- [ ] **Step 6: Prove closed memory/batch bounds with selector 36, then run aggregate gates**

Mark the performance file explicitly. Generate thousands of interleaved fund rows with
maximum group 16, reverse/interleave them and force external spill. Require byte-equal
logical item/attribute output, `max_live_fund_group_rows <= 16`, writer/relation batch
`<= 65_536`, released prior-group weakrefs, no second source iteration, and no call to
global full-dataset `normalize_public_funds`. Then run the exact CP5 aggregate:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/unit/registry/test_rating_registry.py \
  tests/unit/data/normalization/test_public_fund_group_adapter.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_silver.py \
  tests/unit/data/artifacts/test_quality_persistence.py \
  tests/unit/data/artifacts/test_quality_report.py \
  tests/integration/artifacts/test_silver_fixture_build.py \
  tests/performance/test_artifact_external_staging.py \
  tests/performance/test_artifact_fund_streaming.py -q
```

Record all 31 mandatory RED reasons and smallest-GREEN results plus selectors 6, 13,
17, 23, and 24's derived first-GREEN acceptances separately. Then run the unchanged
Task 1-4 regression command from the checkpoint execution rule and record its exact
start/end time, exit code, pass/fail/skip counts and duration. Run static checks over
the exact 17-file implementation inventory, then the full required gates:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check \
  src/finproof/registry/rating.py \
  src/finproof/data/normalization/public_funds.py \
  src/finproof/data/artifacts/silver.py \
  src/finproof/data/artifacts/quality_persistence.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/artifacts/reports.py \
  tests/unit/registry/test_rating_registry.py \
  tests/unit/data/normalization/test_public_fund_group_adapter.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_silver.py \
  tests/unit/data/artifacts/test_quality_persistence.py \
  tests/unit/data/artifacts/test_quality_report.py \
  tests/integration/artifacts/test_silver_fixture_build.py \
  tests/performance/test_artifact_external_staging.py \
  tests/performance/test_artifact_fund_streaming.py \
  tests/helpers/artifacts.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check \
  src/finproof/registry/rating.py \
  src/finproof/data/normalization/public_funds.py \
  src/finproof/data/artifacts/silver.py \
  src/finproof/data/artifacts/quality_persistence.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/artifacts/reports.py \
  tests/unit/registry/test_rating_registry.py \
  tests/unit/data/normalization/test_public_fund_group_adapter.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_silver.py \
  tests/unit/data/artifacts/test_quality_persistence.py \
  tests/unit/data/artifacts/test_quality_report.py \
  tests/integration/artifacts/test_silver_fixture_build.py \
  tests/performance/test_artifact_external_staging.py \
  tests/performance/test_artifact_fund_streaming.py \
  tests/helpers/artifacts.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy \
  src/finproof/registry/rating.py \
  src/finproof/data/normalization/public_funds.py \
  src/finproof/data/artifacts/silver.py \
  src/finproof/data/artifacts/quality_persistence.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/artifacts/reports.py \
  tests/unit/registry/test_rating_registry.py \
  tests/unit/data/normalization/test_public_fund_group_adapter.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_silver.py \
  tests/unit/data/artifacts/test_quality_persistence.py \
  tests/unit/data/artifacts/test_quality_report.py \
  tests/integration/artifacts/test_silver_fixture_build.py \
  tests/performance/test_artifact_external_staging.py \
  tests/performance/test_artifact_fund_streaming.py \
  tests/helpers/artifacts.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run ruff check .
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run mypy src tests tools
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest -q
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/audit_source_data.py --check
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/verify_handoff.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/extract_schema_catalog.py --check
PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache \
  UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pre-commit run --all-files
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
test ! -e artifacts
find source_material -type f -perm -222 -print
test -z "$(find source_material -type f -perm -222 -print)"
git diff --check
git diff --stat
git diff --name-only
git status --short
```

Expected GREEN: all 31 mandatory RED/GREEN selectors, the five derived first-GREEN
selectors, and aggregate/static/full gates pass;
direct/current normalizers and serialized Silver agree from one Bronze-fed source pass;
fund behavior is item-bounded/order-invariant; D-021 timestamps/joins are exact; the
quality report contains no operational identity; Silver observations are valid while
Complete/source-audit production remains impossible before CP6.

- [ ] **Step 7: Stage exactly 17 files, commit, review, then close with exactly three docs**

Before staging, `git diff --name-only` must be exactly the following inventory and no
other file. In particular no docs, STATUS, schema, config, source material, expected
contract or generated artifact belongs in the implementation commit:

```text
src/finproof/registry/rating.py
src/finproof/data/normalization/public_funds.py
src/finproof/data/artifacts/silver.py
src/finproof/data/artifacts/quality_persistence.py
src/finproof/data/artifacts/builder.py
src/finproof/data/artifacts/staging.py
src/finproof/data/artifacts/reports.py
tests/unit/registry/test_rating_registry.py
tests/unit/data/normalization/test_public_fund_group_adapter.py
tests/unit/data/artifacts/test_staging.py
tests/unit/data/artifacts/test_silver.py
tests/unit/data/artifacts/test_quality_persistence.py
tests/unit/data/artifacts/test_quality_report.py
tests/integration/artifacts/test_silver_fixture_build.py
tests/performance/test_artifact_external_staging.py
tests/performance/test_artifact_fund_streaming.py
tests/helpers/artifacts.py
```

```bash
git add src/finproof/registry/rating.py \
  src/finproof/data/normalization/public_funds.py \
  src/finproof/data/artifacts/silver.py \
  src/finproof/data/artifacts/quality_persistence.py \
  src/finproof/data/artifacts/builder.py \
  src/finproof/data/artifacts/staging.py \
  src/finproof/data/artifacts/reports.py \
  tests/unit/registry/test_rating_registry.py \
  tests/unit/data/normalization/test_public_fund_group_adapter.py \
  tests/unit/data/artifacts/test_staging.py \
  tests/unit/data/artifacts/test_silver.py \
  tests/unit/data/artifacts/test_quality_persistence.py \
  tests/unit/data/artifacts/test_quality_report.py \
  tests/integration/artifacts/test_silver_fixture_build.py \
  tests/performance/test_artifact_external_staging.py \
  tests/performance/test_artifact_fund_streaming.py \
  tests/helpers/artifacts.py
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: stream Silver and persisted quality artifacts"
git status --porcelain
```

Fresh review compares the clean approved CP5 plan base, implementation commit, and
36-selector report, explicitly distinguishing 31 mandatory RED/GREEN selectors from
the five derived first-GREEN acceptances. It verifies held rating identity/revalidation, every typed external
relation/key/join boundary, exact call order and one-use finalization, same-object
result issuance, all wide fields, Task 4 public-fund equivalence, bounded one-pass
collapse, exact D-021 type/schema/timestamp/order, quality-to-Bronze relation/hash,
Silver typestate, report semantics, fault cleanup, full gates, and the separate
unchanged Task 1-4 regression evidence. It confirms 6,032 is observation-only. Require
0 Critical / 0 Important; any finding gets a new focused failing selector, smallest
fix, separate correction commit and another fresh review.

Only after a fresh 0/0 verdict, make a separate docs-only closure. Update exactly this
dedicated plan, the legacy phase plan, and `docs/implementation/STATUS.md` with all 31
mandatory RED/GREEN observations and the five derived first-GREEN acceptances, exact gate results, implementation/correction hashes, review
verdict/report, clean tree, and Checkpoint 6 as the exact next task. Mark only CP5
complete. Re-run audit/handoff/catalog/absence/source-permission/diff checks, stage
exactly the three docs, commit, and require empty porcelain:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/audit_source_data.py --check
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/verify_handoff.py
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run python tools/extract_schema_catalog.py --check
test ! -e config/expected_phase1_artifacts.json
test ! -e src/finproof/resources/contracts/expected_phase1_artifacts.json
test ! -e artifacts
find source_material -type f -perm -222 -print
test -z "$(find source_material -type f -perm -222 -print)"
git diff --check
git diff --name-only
git status --short
git add docs/implementation/STATUS.md \
  docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md \
  docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: close Task 5 checkpoint 5 review"
git status --porcelain
```

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
- Produces: `verify_exact_link_evidence(*, tables: StagedParquetSet, relation_verifier: BoundedRelationVerifier) -> ExactEvidenceVerificationObservations` with complete bidirectional validation. The set must contain/revalidate the required link, evidence, Bronze-cell, domestic, and fund handles under one live owner/timestamp; CP6 passes CP5's `StagedBoundedRelationVerifier` and does not introduce a bare tuple, final-inventory, or CP7-forward concrete type.
- Produces: `canonical_link_pair_tsv(rows: Iterable[ExactCrossSourceLink]) -> bytes` and `exact_link_pair_sha256(...) -> str`.
- Completes exact `SilverSourceAuditObservations` only through
  `observations.with_links(link_count, evidence_count, pair_sha256) ->
  CompleteSourceAuditObservations`, then produces
  `SourceAuditReport.from_complete_observations(config=..., observations:
  CompleteSourceAuditObservations) -> SourceAuditReport`. Both operations refuse the
  wrong typestate, unequal expected/observed, or reordered/recomputed pair data; this
  is the first checkpoint where the Complete runtime type, its transition, and the
  final strict source-audit report producer can exist.
- Populates the exact CP2 source-audit model/semantic projection only; report-file
  write/reparse/hash comparison remains the CP7 concrete `ArtifactReportVerifier` port.

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

First close CP6's Complete/report authorization boundary in this exact serial order,
one focused RED and smallest GREEN at a time:

```text
tests/unit/data/artifacts/test_source_audit_report.py::test_complete_observations_skeleton_rejects_valid_silver_fixture
tests/unit/data/artifacts/test_source_audit_report.py::test_silver_observations_with_links_preserves_exact_prefix_and_adds_closed_link_facts
tests/unit/data/artifacts/test_source_audit_report.py::test_source_audit_report_factory_accepts_only_exact_complete_observations
```

The skeleton adds only the direct-init-disabled Complete name and rejects a valid
Silver fixture. The transition selector requires CP5's exact Silver object/type,
preserves every prefix object/value/order, and adds only the closed equal link/evidence
counts and canonical pair hash. The factory selector is the first build-producer
authorization: it rejects Bronze/Silver, direct/copy/subclass/`object.__new__`/equal-
looking Complete forgeries, repeated extension, and model-dump/reparse/cast bypasses.
CP2 parsing remains verification-only and cannot satisfy this producer gate.

For one link with multiple fund source rows, assert one left evidence at role order 0/ordinal 0 and every right `ksd_itm_no` locator at role order 1/contiguous ordinal in exact `equivalent_sources` order. Parameterize missing, duplicate, reordered, swapped-role, noncontiguous ordinal, wrong field, wrong raw value, wrong parent link, wrong Bronze locator, omitted authoritative locator, and extra proximity-derived locator. Each must fail verification.

Assert every evidence row joins exactly one complete Bronze cell, `evidence.raw_identifier == bronze.raw_value == parent.matched_raw_identifier`, and the evidence relation is bidirectionally equal to the two authoritative wrapper sources. Permit buffering only the bounded 47 link keys and 371 evidence keys. Require the verifier to select and strict-parse only the linked 47 domestic and 47 fund `record_json` values by exact IDs, and validate all Bronze locator/raw joins through internal allowlisted typed SQL plus bounded mismatch streams. Sentinels must fail on `len`, second iteration, whole-table list/tuple/DataFrame creation, parsing any unrelated wide record, or retaining a previous stream batch.

Repeat the staged-set boundary mutations at CP6: foreign/copied/mixed/closed owner,
wrong timestamp, missing/reordered required table, and bare handles all fail before a
link/evidence/Bronze relation is registered. The accepted case uses the exact CP5 set
extended under the same owner.

In `test_source_audit_report.py`, begin from a CP5 Silver/quarantine-complete observation fixture. Assert the exact-link/evidence counts and canonical pair hash extend it to the complete phase, and only that complete phase can construct the final strict `SourceAuditReport`. Parameterize missing/extra/repeated phases, wrong expected or observed count, wrong source-manifest/catalog hash, changed pair hash, link/evidence relation mismatch, and attempts to copy the tests baseline; each must fail before report serialization. Assert the report is timestamp/path-free and semantically stable across pretty rendering.

Expected RED: evidence construction/verification is absent or incomplete.

- [ ] **Step 4: Implement exact evidence emission and bidirectional validation**

Emit evidence from the staged authoritative candidates, never from inferred adjacent Bronze cells. Validate relation cardinality and order before Parquet writing and again after reopen. Use external stage ordering for links/evidence; no table-sized list or Python sort. The reopened validation passes only the same live owner-bound `StagedParquetSet` to the one-thread/1-GiB relation verifier, which resolves and revalidates exact required handles; it buffers the closed small link/evidence key sets, filters wide records by those exact IDs before strict JSON parsing, and streams Bronze join mismatches/counts. It never scans wide `record_json` into Python or materializes the Bronze cell table. After the reopened staged relations establish exact counts and `exact_link_pair_sha256`, advance the CP5 observations once and construct the final `SourceAuditReport` from `config/artifact_build.yaml` expected values plus the fully observed source/catalog/Bronze/Silver/quarantine/link/evidence data. Keep the strict model and staged set in the private live build session only; CP7 owns writing reports/database/manifest, checking the set timestamp against the manifest, creating the final CP2 inventory, independently rebuilding final handles, and full verification.

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

### Checkpoint 7: Self-contained DuckDB, complete core verification, guarded publication mechanics, and safe CLI

Keep one checkpoint number but make three independently reviewable commits, 7A/7B/7C. Obtain one fresh checkpoint review over all three commits; any review correction gets a fourth dedicated fix commit.

The global single-selector RED/smallest-GREEN loop applies independently to every named mutation, security boundary, fault-injection state, candidate guard, and CLI behavior in 7A/7B/7C. The grouped commands below are aggregate gates and cannot substitute for the recorded per-selector REDs.

#### Checkpoint 7A: Database construction and the first complete concrete core verifier

**Files:**

- Create: `src/finproof/data/artifacts/database.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Modify: `src/finproof/data/artifacts/staging.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Create: `tests/integration/artifacts/test_artifact_duckdb.py`
- Create: `tests/integration/artifacts/test_artifact_equality.py`
- Create: `tests/integration/artifacts/test_artifact_tampering.py`
- Create: `tests/unit/data/artifacts/test_runtime_temp.py`
- Create: `tests/performance/test_artifact_verifier_bounds.py`
- Modify: `tests/helpers/artifacts.py`

**Interfaces:**

- Produces private `build_self_contained_database(*, owner:
  OwnedStageDatabaseOwner, tables: StagedParquetSet, database_leaf:
  OwnedStageDatabaseLeaf) -> StagedDatabaseVerification`. It requires
  the complete frozen-order set, revalidates the one live owner/timestamp and every
  handle, requires `tables` and `database_leaf` against the explicit exact `owner`, and
  passes that same owner to `StagedDatabaseVerification.from_sealed`. No caller/raw
  input or output path is accepted; CP4's owner-managed scratch returns only its
  registered neutral `SealedStageDatabase`, which CP7 validates and wraps. Before manifest construction,
  `StagedDatabaseVerification.validate_against(owner)` repeats owner/token/liveness/
  timestamp/leaf identity and physical fact checks.
- `StagedDatabaseVerification` is created in CP7 `database.py`, not CP3 `parquet_io.py`;
  its direct constructor is disabled and its sole `from_sealed` factory accepts CP4's
  direct-init-disabled owner-registered `SealedStageDatabase`. The CP7 result stores the
  exact `_owner` object and opaque owner/final-leaf tokens plus timestamp, size, and SHA;
  `validate_against` requires `owner is _owner` and live exact registrations. Foreign/
  equal-looking seal or owner, copy, `object.__new__`, and token forgery are rejected.
- Produces public `open_read_only_database(path: Path) -> duckdb.DuckDBPyConnection` for application/runtime reads only.
- Produces private `verify_database_against_parquet(*, inventory:
  VerifiedPhysicalInventory, database_entry: VerifiedPhysicalEntry, tables:
  TableVerificationResult, runtime_tmp_root: Path | None = None) -> None`. It accepts no
  published/raw database path and uses its own trusted internally allowlisted
  verification connection and marker-owned OS temp.
- Produces the private concrete CP2 ports `StrictArtifactReportVerifier`,
  `DuckDBArtifactDatabaseVerifier`, and `PackagedArtifactExpectedComparator`; each reads
  only through the retained inventory/resource boundary and accepts no caller path,
  verifier, SQL, or expected payload.
- `StrictArtifactReportVerifier` independently rebuilds both complete semantic
  projections from strict manifest inputs and the same owned verified table handles,
  compares parsed-vs-rebuilt models before hash acceptance, binds
  `quality_table_logical_hash` to the verified quality handle, and enforces quality
  `quarantined_source_row_count ==` source-audit
  `quarantine_source_rows.observed`. It never treats two mutually edited report files or
  attacker-recomputed outer hashes as observations.
- The report/timestamp/link and database ports consume CP3's exact
  `TableVerificationResult`; they register/reopen only its eleven handles through the
  still-live inventory and never rediscover a table by path or build a second unbound
  handle set.
- Privately assembles the CP2 `ArtifactVerificationKernel` with CP3's closed table
  registry and final `ParquetArtifactTableVerifier` plus these CP7 ports. This is the
  first production invocation of that adapter: it receives the complete CP2 inventory,
  independently rebuilds eleven final `VerifiedParquetTable` handles, and accepts no
  CP4-6 staged handle/fact. Candidate core order is inventory -> tables ->
  reports -> overall -> database -> final rescan. CP7 implements the packaged comparator
  and expected-route assembly shape, but the official resource remains deliberately
  absent, so no production/public expected-route success is possible yet.
- Before report/database/manifest construction CP7 calls `tables.require_complete()`;
  the database writer and every staged report relation consume that same set. Once the
  manifest is written, CP7 requires `tables.persistence_timestamp ==
  manifest.persistence_timestamp` in addition to CP5's Bronze/quality equality. A
  copied/mixed/closed/timestamp-mismatched set or foreign database leaf fails before
  final inventory creation.
- The already guarded repository-only candidate path enters the exact CP4 custody's
  `open_verification_root()` and calls `verify_candidate_core_from_root`, projects its
  `ArtifactCoreVerificationResult` to candidate JSON, never publishes, and
  exposes no package/runtime skip; it does not install a no-op comparator or duplicate
  the kernel. CP8 alone activates `verify_expected_from_root`, exposes
  `ArtifactManifest.verify`, and wraps `ArtifactExpectedVerificationResult` as
  `VerifiedArtifactSet` after the reviewed resource exists.
- Produces private live direct-construction-disabled `CandidateArtifactSet`, consuming
  the exact one-use CP4 `ArtifactBuildSession.transfer_candidate_stage()` result and
  immediately consuming its one-use `issue_candidate_custody()` result. The candidate
  directly retains that exact instance-owned opaque `CandidateStageCustody`, which is
  the sole owner of parent/stage/parquet descriptors, marker/leaf identities, input-
  close responsibility, and advisory lock; there is no module-global candidate/stage/
  receiver/custody registry. The candidate also retains only its manifest and
  `ArtifactCoreVerificationResult` and the exact same `BuildInputIdentity` object
  retained by the build session/results; it accepts no raw path/basename or
  reconstructed stage/input fact, is nonserializable, and is not trusted for
  publication. The sole manifest builder accepts that carrier, emits
  its exact ordered nine-tuple as `source_inputs`, retains the same carrier in the
  private frozen nonserialized `_build_input_identity` slot, and binds the report
  manifest/catalog hashes to entries zero/one. Candidate admission calls
  `manifest.require_build_input_identity(input_identity)`; no tuple or parallel hash
  arguments are accepted. It exposes only `open_verification_root() ->
  AbstractContextManager[ManagedArtifactVerificationRoot]` and the package-private
  `transfer_expected_accepted_custody(*, expected_acceptance_seal: object, receiver:
  ExpectedAcceptedCustodyReceiver) -> None` bridge; both delegate to the retained exact
  custody instance and neither reveals its private state. The bridge is the only caller
  of `CandidateStageCustody.transfer_expected_accepted(...)`, and only CP8 publication
  may call the bridge.
  Produces internal `build_verified_candidate_stage(settings,
  versions, options) -> CandidateArtifactSet`, which fully core-verifies but does not
  compare expected, publish, or expose its stage path publicly.

- [ ] **Step 1: Write 7A REDs for exact self-contained DuckDB construction**

Author these database-construction selectors one at a time, running each exact node and
reaching its intended RED before the smallest GREEN:

```text
test_database_module_skeleton_rejects_complete_owned_stage_fixture
test_database_builder_requires_canonical_complete_set_and_same_owner_leaf
test_database_builder_materializes_exact_tables_through_cp4_managed_writer
test_database_builder_orchestrates_cp4_seal_then_cp7_verified_wrapper
test_staged_database_verification_wraps_only_exact_owner_registered_seal
test_staged_database_verification_revalidates_owner_timestamp_identity_and_hash
test_staged_database_verification_rejects_foreign_equal_copy_object_new_and_token_forge
test_candidate_core_verifier_consumes_managed_stage_root_without_path_or_private_field_access
test_candidate_manifest_retains_exact_build_input_identity_and_bound_source_hashes
```

The skeleton exposes only raising names. CP7's new behaviors are complete-set/owner
admission, exact eleven-table materialization into the already-frozen CP4 managed
writer, CP4-seal-to-CP7-wrapper orchestration, and CP7 result identity/revalidation.
The managed-root selector requires one `CandidateArtifactSet.open_verification_root()`
context delegating to the exact retained custody instance, one `open_inventory(manifest=...)`
context, and closure on success and every
port failure. The managed entry/caller signatures and spies reject any `Path`,
descriptor integer, basename, `/dev/fd`, or access to stage private fields; CP2's
already-approved private path-root entries are unchanged regressions. The input selector requires
`candidate.input_identity is session.input_identity`, manifest build-identity object
identity, exact serialized nine-entry order/type/value equality, and the manifest/
catalog hashes from entries zero/one; copied carriers, JSON-loaded manifests without
build authorization, reorder, separately supplied hash, or result-to-stage mixing
fails before inventory. It also requires exact candidate-to-custody object retention;
a copied/equal/forged candidate, copied custody, replaced private slot, or superseded/
closed custody cannot open a root or invoke the transfer bridge.

CP4 scratch/checkpoint/WAL/copy/fsync/final-close/reopen/hash/cleanup/abort internals are
already GREEN and remain regression assertions here; CP7 neither claims new REDs for
them nor reimplements them.

Build the complete small fixture Parquet set. Assert DuckDB contains exactly the eleven table names, exact information-schema column order/types/nullability, exact counts, and no view/external path. Assert materialization uses explicit frozen column lists and final `ORDER BY`; database close/checkpoint leaves no `.wal`. Reopen it and compare Decimal/date/local timestamp/UTC timestamp/null values without text coercion.

Supply the complete owner-bound set plus its exact same-session database leaf. CP7's
focused admission/orchestration selectors RED on a
bare tuple, mixed/copied/closed/timestamp-substituted set, foreign database leaf,
or forged CP7 wrapper. Rerun CP4 regression cases for pre-existing/symlink/hardlink
output, inode substitution before/after DuckDB close, WAL, ambiguous abort, exclusive
no-follow mode 0600 creation, hash/rescan, close-before-exact-cleanup, and no deletion
of an unowned inode; do not count those already-implemented mechanics as CP7 REDs.

Mutate one DuckDB cell while preserving table schema/count and recompute the physical database hash/manifest entry. The full verifier must reject it through bidirectional typed `EXCEPT ALL`; a count-only verifier is an observed RED. Add deleted/duplicated row variants too.

Run:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/integration/artifacts/test_artifact_duckdb.py \
  tests/integration/artifacts/test_artifact_equality.py -q
```

Expected RED: database builder/public reader/private equality verifier and full manifest verifier are missing.

- [ ] **Step 2: Implement separate public-reader and private-verifier connections**

The CP7 writer orchestrator uses `threads=1`, `preserve_insertion_order=true`, `TimeZone=UTC`, static allowlisted DDL, and trusted stage capabilities only. It first revalidates the complete one-owner `StagedParquetSet`, obtains each `verification_for(...)`, and inserts bounded batches with explicit frozen columns/order through CP4's already-verified pathless `ManagedStageDatabaseBuild.open_writer()`. It then invokes CP4's already-GREEN `checkpoint_close_and_seal(leaf=database_leaf)` and wraps the returned owner-registered `SealedStageDatabase` only through `StagedDatabaseVerification.from_sealed(owner=..., sealed=...)`; CP7 does not implement or duplicate scratch/leaf creation, WAL, copy, fsync, close, reopen, hash, or cleanup mechanics. The private equality verifier later uses only CP7's independently rebuilt final handles.

`open_read_only_database` first `lstat`s an existing nonsymlink regular file, then opens `read_only=True` and permanently sets `enable_external_access=false`, `allow_unsigned_extensions=false`, `autoinstall_known_extensions=false`, `autoload_known_extensions=false`, and `lock_configuration=true`. Do not use this hardened connection to call `read_parquet`.

The private verifier creates one unique mode-0700 marker-owned directory below trusted OS temp or a containment-validated `FINPROOF_RUNTIME_TMP_ROOT`. It creates mode-0600 `database-copy.duckdb` with `O_CREAT | O_EXCL | O_NOFOLLOW`, bounded-stream-copies only from `inventory.open_verified(database_entry)`, closes it, and requires held-fd/lstat identity, regular type, `st_nlink == 1`, exact bytes, and SHA equality with the owned entry/manifest before DuckDB receives the private-copy path. The source context must first finish leaf/ancestor/tree revalidation. It places private spill in the same owned directory, uses `threads=1`/`memory_limit=1GiB`, and runs internally generated typed `EXCEPT ALL` in both directions using only `TABLE_SPECS`. After DuckDB closes, it repeats private-copy identity/size/SHA verification before marker-owned cleanup. Source swap during copy, private-copy substitution, mismatch, ambiguous ownership, close, or cleanup failure blocks; there is no fallback reopen of the published path. Its `RuntimeBoundedRelationVerifier` is the second concrete implementation of CP5's closed `BoundedRelationVerifier`, separate from the stage-backed implementation: quality/Bronze and evidence/Bronze checks are allowlisted SQL relations over internally registered verified handles whose mismatch/count output is bounded; link/evidence validation buffers only the closed 47/371 keys and strict-parses only exact-ID-filtered 47 domestic plus 47 fund records. It never accepts caller SQL/table/path, materializes full Bronze/wide relations in Python, or writes in artifact root or its parent.

- [ ] **Step 3: Write 7A REDs for read-only security and runtime-temp failures**

Through the public reader, require persistent `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, external `ATTACH`, and `COPY TO` to fail. Assert TEMP objects are explicitly not promised but no public FinProof API exposes raw SQL. Test missing/symlink/directory database paths.

Make artifact root and its parent read-only and verify successfully using the private OS temp. Assert mode 0700, one thread, 1-GiB limit, spill actually occurs under forced low synthetic limits, and no artifact-parent entry appears. Fault-inject temp creation/marker/close/spill/removal failure; close before cleanup, delete only exact marker-owned temp, retain ambiguous temp, and raise a bounded typed verification error.

Also swap the source database inode during the bounded copy, substitute the private-copy
inode before DuckDB open and after DuckDB close, mutate a copied byte, change its link
count, and fault each source-context revalidation/hash/close boundary. Every case must
fail before equality acceptance, never reopen the published path, close DuckDB before
cleanup when it was opened, and remove only an exact marker-owned temp directory.

Expected RED: public hardening or private temp ownership/settings/cleanup is incomplete.

- [ ] **Step 4: Assemble the complete concrete core verifier and mutation matrix**

Before assembly, author and close these report-port behaviors in exact order, one
selector RED/smallest-GREEN at a time:

```text
tests/integration/artifacts/test_artifact_tampering.py::test_report_verifier_rebuilds_source_inputs_and_bronze_counts
tests/integration/artifacts/test_artifact_tampering.py::test_report_verifier_rebuilds_silver_and_quarantine_counts
tests/integration/artifacts/test_artifact_tampering.py::test_report_verifier_rebuilds_exact_link_and_evidence_semantics
tests/integration/artifacts/test_artifact_tampering.py::test_report_verifier_rebuilds_quality_groups_and_aggregates
tests/integration/artifacts/test_artifact_tampering.py::test_report_verifier_binds_quality_table_logical_hash
tests/integration/artifacts/test_artifact_tampering.py::test_report_verifier_rejects_cross_report_quarantine_mismatch_with_all_outer_hashes_recomputed
```

Each selector changes only its named parsed field family while recomputing report bytes,
physical hashes, report logical hashes, and overall manifest hash; the rebuilt table-
derived projection must still reject before the next selector is authored. The last edits both
otherwise locally valid reports so their quarantine counts disagree, recomputes every
attacker-controlled outer field, and requires rejection before a report result or later
kernel port. Smallest GREEN reuses the CP5/6 pure observation/grouping functions over
bounded reopened handles; it does not add a second report rule implementation.

The private candidate-core verifier now executes the frozen kernel, all-or-nothing:

1. strict load/schema and exact recursive inventory;
2. every physical size/SHA;
3. every Parquet exact schema/count/sort/unique/logical hash;
4. both strict report IDs/logical hashes;
5. overall manifest logical hash;
6. manifest/Bronze/quality typed/quality-JSON timestamp consistency;
7. exact link/evidence/bidirectional Bronze relation;
8. exact DuckDB information schema/count and typed bidirectional `EXCEPT ALL` equality;
9. final descriptor-bound tree rescan.

Only after all nine does the private logical result become the strict
`ArtifactCoreVerificationResult`; it is never a `VerifiedArtifactSet`. In boundary 6/7,
pass reopened verified Parquet handles to the private relation verifier;
never expose raw table iterators to a materializing helper. Add adversarial fixtures
that mutate one boundary and recompute every attacker-controlled outer field; each
deeper boundary must still reject. Recheck the tree through
`VerifiedPhysicalInventory.assert_unchanged()` immediately before each reopen and
immediately before returning; a swapped inode, newly added file, or symlink replacement
blocks. That call re-streams size/SHA for every declared file and reparses/equality-
checks held `manifest.json`, so a same-inode/same-size byte mutation between any two
stages also blocks. Add finalizer selectors for one omitted
`ExternalOrderStore.close_and_remove_working_state`, each partially removed working-
state member, an ambiguous marker/path, and inode replacement between cleanup
validation/removal; all must block before report/manifest creation and preserve declared
output Parquets.

In `test_artifact_verifier_bounds.py`, set `pytestmark = pytest.mark.performance`, build scale relations with 145,393 Bronze rows and 6,401,851 generated Bronze cells (or reuse the fully verified official-size fixture when available), but only 47 links/371 evidence locators. Install `len`/second-iteration/materialization and prior-batch-retention sentinels. Assert `max_verifier_batch_rows <= 65_536`, exactly 47 domestic plus 47 fund strict `record_json` parses, at most 47 link and 371 evidence keys live, one verifier thread/1-GiB spill, and no Python collection proportional to Bronze cells, quality joins, or any full wide table.

The candidate-stage finalizer first requires the exact complete live CP3
`StagedParquetSet`, validates its timestamp and every owned handle, and uses only that
set for CP5/6 relations and DuckDB/report construction. It
then calls `close_and_remove_working_state()` on every registered `ExternalOrderStore`
and proves no staging database/WAL/spill/temp/store marker remains before writing either
report or beginning the exact-tree inventory. An omitted call, partial cleanup,
substituted inode, or ambiguous working path fails pre-manifest and preserves the build
stage for guarded diagnostics; it cannot be hidden as an undeclared extra tree entry.
Only then does the finalizer write/reparse both reports, materialize/checkpoint/close
and seal DuckDB, call `tables.table_declarations()` plus
`tables.verification_for(name)` for each exact table plus
`database_verification.validate_against(owner)` to revalidate every registered physical
fact, build separate Parquet `ArtifactFile` declarations, record all 14 physical
sizes/SHA values, and write canonical pretty
`manifest.json` with one terminal newline. It discards no staged owner yet, but invokes
the private concrete core verifier through a new CP2 final inventory; CP3's final
adapter independently reopens/rechecks every Parquet and creates new final handles.
No staged fact is promoted. A file that merely closed or only passed staged checks
without complete cleanup/final-inventory verification can never become a candidate.

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
- Produces private exact `PublicationTransitionPort` with only `assert_live() -> None`,
  `rename_stage_to_target() -> None`, `rollback_target_to_stage() -> None`,
  `commit_after_stage_marker_removal() -> None`, and `close() -> None`. It has no path,
  basename, descriptor, manifest/result, or separate stage argument/result. CP7 creates
  no production implementation; its only implementation is the sealed synthetic one
  in `tests/helpers/artifact_filesystem.py`. CP8's
  `ExpectedAcceptedPublicationStage` is the sole production implementation.
- Produces only package-private `_PublicationStateMachine` transition/rollback/recovery
  mechanics. CP7 has no production constructor, `publish_verified_stage`, target-
  recognition wrapper, or builder call site. Tests drive the machine through a
  test-helper-only sealed synthetic authorization, synthetic recognized-target fact,
  and test-only `PublicationTransitionPort` implementation from
  `tests/helpers/artifact_filesystem.py`; none of those wrappers/capabilities exists in
  production under `src/`, accepts a core result, or reconstructs a stage path.
  CP8 adds sole `authorize_candidate_for_publication(candidate: CandidateArtifactSet)
  -> ExpectedAcceptedPublicationStage`, which reruns expected verification while
  retaining and binding the exact CP4 custody. It takes CP2's expected-acceptance seal,
  closes the adopted-root context and all duplicate descriptors, then invokes only
  the candidate bridge to its retained staging-owned
  `CandidateStageCustody.transfer_expected_accepted(*, expected_acceptance_seal,
  receiver: ExpectedAcceptedCustodyReceiver) -> None`. The typed receiver's non-
  fallible `accept_transferred_custody(TransferredCandidateCustody) -> None` atomically
  installs one opaque instance and invalidates the source custody; no raw descriptor,
  private field, path, token, bundle, or global registry crosses modules. Only that CP8 capability implements
  the production `PublicationTransitionPort`, owning one-use descriptor-relative
  stage-to-target, target-to-stage rollback, commit, and close operations; and
  `publish_verified_stage(authorized: ExpectedAcceptedPublicationStage, *, settings:
  Settings, clean: bool, filesystem: ArtifactFilesystem) -> ArtifactManifest`. It never
  accepts a separate result/stage pair. CP8 also adds
  `recover_owned_remnants(settings: Settings, *, filesystem: ArtifactFilesystem) ->
  None`, with recognition obtained only from public expected verification.
- `_PublicationStateMachine` invokes stage-to-target/target-to-stage only through its
  injected `PublicationTransitionPort`; CP7 has only the synthetic test port and CP8
  supplies the production expected-authorized port. `OwnedCandidateStage` and
  `CandidateStageCustody` themselves have no
  rename/rollback/target method. `ArtifactFilesystem`
  exposes only recognized target/backup/tombstone `lstat`, exclusive marker
  create/read, same-filesystem rename, exact unlink, and marker-owned tombstone
  deletion; no stage-path, glob, or broad resolved-delete method exists.

- [ ] **Step 6: Write 7B REDs for no-clean/clean recognition and both rename rollback boundaries**

Through only the test-helper sealed authorization and synthetic transition port, assert
the absent-target transition requests a stage rename only after the synthetic
expected-accepted fact. Existing target
without clean raises `EXISTING_TARGET` byte-identically. With clean, synthetic
recognition refusal for symlink/non-directory/empty/unrecognized/extra-entry/special/
hardlink/WAL/invalid-manifest targets occurs before rename/chmod/unlink; snapshot every
inode/byte/mode. These cases test mechanics, not a CP7 production publication path.

Freeze the target-absent first-publication rollback branch with three selectors separate from every existing-target/backup case:

- `test_first_publish_verification_failure_rolls_target_back_to_marked_stage`: inject reopened target verification failure after `stage -> target`; require the candidate bytes/inodes to return to the exact original marked stage, target absent, no backup/tombstone directory or marker, and every unrelated sibling byte/inode/mode unchanged.
- `test_first_publish_stage_marker_unlink_failure_rolls_target_back_to_marked_stage`: let post-rename verification pass, fail the orphaned stage-marker unlink before the commit point, then require the same target-absent/byte-identical marked-stage/no-backup-or-tombstone/unrelated-sibling state.
- `test_first_publish_target_to_stage_rollback_failure_is_typed_and_preserved`: after either pre-commit fault, fail the exact `target -> stage` rollback rename. Require only `PUBLICATION_ROLLBACK_FAILED`, `published=False`, closed state `TARGET_RENAMED_UNCOMMITTED`, the complete candidate still at target with its exact stage sidecar marker retained for operator recovery, original stage path absent, no backup/tombstone state, unrelated siblings unchanged, exact recovery paths only in internal diagnostics, and no path in safe output.

For a recognized old target, fault-inject old-target-to-backup rename, stage-to-target rename, post-rename target verification, and stage-marker unlink. Before commit point, the old target must remain or be restored byte-identically; failed restoration raises only `PUBLICATION_ROLLBACK_FAILED` and preserves both exact recovery paths in internal diagnostics, never safe output.

Expected RED: no publication state machine exists.

- [ ] **Step 7: Implement pre-commit recognition, rename, verification, and rollback**

Consume the already-held synthetic lock authority for each test state. CP7 tests the
authorization-independent rename/rollback/tombstone state machine directly with sealed
synthetic filesystem states; it creates no production recognition/publish wrapper and
no core result can authorize a rename. CP8 adds the sole wrapper and requires
expected-accepted `ArtifactManifest.verify` both before the first rename and for
reopened-target recognition; that wrapper consumes the CP4-transferred advisory lock
through `ExpectedAcceptedPublicationStage`. Use exact same-filesystem sibling stage/
backup markers and
`lstat` immediately before every rename. The commit point is successful reopened target
verification plus stage-marker removal. Never recursively delete before it.

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
- Produces internal strict frozen `ArtifactCoreBuildOutcome(manifest:
  ArtifactManifest, logical_contract: ArtifactCoreVerificationResult, telemetry:
  ArtifactBuildTelemetry)`. The official baseline validators are not applied to this
  core carrier, so complete small fixtures remain testable. CP8 adds the distinct
  expected-accepted `ArtifactBuildOutcome` only after comparison.
- Defines public `build_artifacts(settings: Settings, versions: VersionBundle, *,
  options: ArtifactBuildOptions) -> ArtifactManifest`, but while CP8's official
  resource is absent it deterministically fails before transform/publication; its first
  success is owned and tested by CP8.
- Completes repository-only `build_candidate_artifacts(settings: Settings, versions:
  VersionBundle, *, options: ArtifactBuildOptions) ->
  ArtifactCoreVerificationResult`. The official CP8 candidate outputs parse as
  `ExpectedPhase1ArtifactContract` because official counts/identities satisfy that
  separate baseline model; small core fixtures need not.
- CLI adds only `finproof build-data [--clean]`.

- [ ] **Step 11: Write 7C REDs for candidate non-publication and production expected comparison**

Use a complete small fixture only through the private transform with an explicitly
constructed strict hermetic test config/closed inputs; assert full core verification,
canonical core logical-contract data, cleanup, and no publication/write. Test the CP7
repository wrapper's orchestration with an instrumented synthetic private transform:
initial absence guard, exactly one transform call, cleanup, second check, then output.
Do not call that a real-default success—the real default is bound to exact official
inputs/counts and is first executed by CP8's two official candidate processes.

In a separate permanent hermetic test, inject a synthetic `CandidateBaselineProbe` that reports both absent at the initial guard, allows one instrumented private transform, then flips source or resource present in `second_check()`. Assert `BASELINE_ALREADY_EXISTS`, zero stdout/contract return, complete marker-owned candidate-stage cleanup, and no publication/write. This is the authoritative post-transform race test before and after baseline creation; do not attempt to reach the second boundary through the real default once the packaged resource exists.

Separately test the private production transform directly and require a complete
`ArtifactCoreBuildOutcome`: exact manifest/logical-contract identity agreement, the
verified injected persistence timestamp, observed fund/writer/verifier/reconstruction/
key/parse maxima, staging/verifier workspace mode `0o700`, true marker/containment/
cleanup facts, actual `threads=1` and `memory_limit="1GiB"`, and exact ordered 14 path/
kind/size/SHA physical entries. Missing/duplicate/reordered physical entries, unverified
hash/timestamp, false workspace fact, unexpected mode/settings, config-only counter
values, path-bearing telemetry, or logical manifest identity mismatch fail strict
construction. These internal transform tests remain permanently valid after baseline
creation.

Reuse CP1's injected read-only `CandidateBaselineProbe`; its synthetic source/resource states cover absent, source present, packaged present, both present, and the post-transform flip described above. The production default probe is not injectable through CLI/public APIs. Assert candidate callable is absent from installed package modules, `finproof` exports, project scripts, and wheel. Once a synthetic expected source or resource exists at the initial guard, every candidate invocation refuses with zero transform calls. In CP7 evaluation mode, `build_artifacts` detects the absent packaged expected contract and blocks before transform/publication; CP8 first tests and implements its expected-accepted success. Extended-demo may receive only an explicitly different expected object through a separate typed internal tooling API and cannot alter evaluation behavior.

Expected RED: exact candidate wrapper/production expected-before-publish boundary is incomplete.

- [ ] **Step 12: Implement the two non-bypassable build modes**

Factor one private production transform that always creates and fully core-verifies a private stage and returns `ArtifactCoreBuildOutcome`. The repository candidate sequence is exact: initial probe guard; private transform; retain only strict outcome/contract data in memory; marker-owned candidate-root cleanup and verification; `probe.second_check()`; then and only then emit one canonical compact contract JSON line to stdout and one canonical compact bounded/path-free telemetry JSON line to stderr/return the core contract. Any transform, cleanup, or second-check failure emits no contract/telemetry and leaves no guessed cleanup. CP7's `_build_evaluation_artifacts_with_outcome` first requires packaged expected bytes and therefore blocks without transformation while they are absent. CP8 completes its expected comparison, private expected-accepted outcome, guarded publication, and public return. Neither mode accepts a public/private skip/update/accept/write-back flag, and no test seam can disable comparison in the public builder.

Export only `ArtifactManifest`, `ArtifactBuildOptions`, `build_artifacts`, and `open_read_only_database` from `finproof.data.artifacts`; do not export the private transform, publication filesystem, candidate wrapper, or recovery paths.

- [ ] **Step 13: Write 7C CLI REDs for arguments, time capture, output, and safe errors**

Assert parser accepts only `build-data` and optional `--clean`; reject timestamp, source, output, SQL, table, version, and expected-path arguments with argparse exit 2. Inject a clock seam and assert it is called once, UTC, then the exact timestamp reaches `ArtifactBuildOptions`.

CP7 proves the absent-baseline CLI failure only: return 2 and exactly one bounded
`error: ...` stderr line with no stdout, stack trace, raw payload, absolute/source/
stage/backup/recovery path and zero transform/publication calls. CP8 owns the first
success stdout and post-commit cleanup wording after expected acceptance is available.

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

Expected GREEN: candidate is full-transform/full-core-verify but unpublished/unpackaged/no-write; evaluation build refuses the missing baseline before transform and cannot skip expected comparison; CP7 CLI arguments and bounded absent-baseline error are closed and safe; the existing installed `verify-handoff`/`audit-source` CLI contracts remain unchanged; official baseline is still absent.

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
- Modify after candidate review only: `src/finproof/data/artifacts/manifest.py`
- Modify after candidate review only: `src/finproof/data/artifacts/builder.py`
- Modify after candidate review only: `src/finproof/data/artifacts/staging.py`
- Modify after candidate review only: `src/finproof/data/artifacts/publication.py`
- Modify after candidate review only: `src/finproof/data/artifacts/__init__.py`
- Modify after candidate review only: `src/finproof/cli/main.py`
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
- Activates the already-frozen expected route only after those bytes exist: public
  `ArtifactManifest.verify(root: Path) -> VerifiedArtifactSet` calls
  CP2's private published-root capability opener and then
  `verify_expected_from_root`; normal target recognition/publication requires that
  trusted type, and public `build_artifacts` returns only after expected acceptance.
  No public API accepts a managed-root capability or exposes its internals. Defines the
  distinct strict `ArtifactBuildOutcome(manifest: ArtifactManifest, logical_contract:
  ArtifactExpectedVerificationResult, telemetry: ArtifactBuildTelemetry)`; CP7's core
  outcome cannot be substituted.
- Produces the internal context-managed `ExpectedAcceptedPublicationStage` only through
  `authorize_candidate_for_publication(candidate)`. It binds that candidate's exact
  CP4-owned held stage/parent descriptors, marker/registration identities, advisory
  lock, exact `BuildInputIdentity`, and expected result. Authorization enters only
  `candidate.open_verification_root()` and `verify_expected_from_root`; after the
  final rescan it takes CP2's one-use expected-acceptance seal, exits the managed-root
  context so all adopted duplicate descriptors close, then creates the direct-init-
  disabled publication receiver implementing `ExpectedAcceptedCustodyReceiver`,
  and calls `candidate.transfer_expected_accepted_custody(...)`, the sole no-private-
  field bridge to the retained custody instance's typed one-use transfer method.
  Its non-fallible `accept_transferred_custody(...)` installs one opaque
  `TransferredCandidateCustody`, invalidates the old custody/candidate, and makes the
  receiver the sole owner of the original descriptors, leaf identities, held-nine-input
  carrier close responsibility, and advisory lock. The receiver implements the sole
  production `PublicationTransitionPort`; publisher accepts only this
  single capability and invokes only that port's descriptor-relative transition
  operations. Mixing verified stage A with candidate stage B, copying/forging a
  capability, closing it, or swapping its bound entry blocks before rename.
  No candidate/stage/receiver/custody/token module-global registry exists; copied,
  foreign, prefilled, or throwing receivers fail during preflight before the source
  ownership slot moves.
- Produces a session-scoped official artifact fixture that launches one fresh child through the same closed `_build_evaluation_artifacts_with_outcome` called by public `build_artifacts`, first calls `ArtifactManifest.load(...).verify(root)`, then `compare_expected_artifact_contract`, and shares that verified generation plus child telemetry across all assertions in the process.
- Consumes the frozen internal `ArtifactBuildOutcome`/`ArtifactBuildTelemetry` from the fresh child and adds only externally measured wall duration, platform-normalized peak RSS bytes, and `sys.platform`; it does not infer counters from logs or expose a public telemetry/skip flag.

- [ ] **Step 1: Write the final resource/acceptance RED without creating or guessing baseline bytes**

Add a contract test that requires source `config/expected_phase1_artifacts.json`, packaged `finproof/resources/contracts/expected_phase1_artifacts.json`, runtime loader availability outside checkout CWD, byte/SHA equality, strict parse, and exact wheel inclusion. Add `test_active_standard_editable_expected_contract_loader_matches_source_outside_cwd`, which runs in the active uv editable from an unrelated CWD and compares the frozen metadata-fallback destination bytes/SHA to the repository expected-contract source. Add `test_standard_editable_expected_contract_loader_uses_distribution_fallback_when_src_shadows`, using a fresh real isolated normal editable install: the regular source package must shadow copied contract data while the exact metadata-located frozen destination supplies source-identical bytes/SHA, with no dev-mode-exact behavior. Add `test_built_wheel_expected_contract_loader_uses_importlib_resources_primary`: install the built wheel alone with dependencies, make metadata fallback fail if called, change to an unrelated CWD, assert exact three-resource inventory/no candidate module, copy the already session-verified official artifact generation (not a small synthetic contract-incompatible tree), and successfully call the public manifest verifier/expected loader without a repository root. In new `tests/source_contract/test_official_artifact_build.py`, declare `pytestmark = pytest.mark.source_contract`; its missing-contract fixture refuses to run without the expected contract and its first assertion loads/verifies the artifact before comparing expected.

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

Only after that stale-resource RED/reinstall/GREEN is closed, activate the frozen
production assembly: `ArtifactManifest.verify` uses only the packaged comparator and
expected route; target recognition/publication accepts only the bound expected-accepted
capability; `_build_evaluation_artifacts_with_outcome` converts the core outcome to
`ArtifactBuildOutcome` only after expected comparison and reopened final rescan;
`build_artifacts`/`finproof build-data` gain their first success path. Add serial
selectors for public small-fixture refusal against the official baseline, official
fixture success, core-result substitution rejection, exact-stage binding, expected
mismatch before rename, normal target recognition, compact success stdout, and
post-commit cleanup wording. Each selector observes its own pre-activation/missing-
behavior RED and smallest GREEN; no expected comparator skip/injection seam enters a
public or production assembly.

Use this exact order, running only
`UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest <file>::<selector> -q` for
each RED and its GREEN before authoring the next selector:

```text
tests/integration/artifacts/test_artifact_tampering.py::test_public_manifest_verify_rejects_small_core_against_official_expected
tests/unit/data/artifacts/test_publication.py::test_publisher_rejects_core_result_substitution_before_filesystem_work
tests/unit/data/artifacts/test_publication.py::test_expected_authorization_atomically_transfers_real_descriptor_lock_and_input_custody_once
tests/integration/artifacts/test_publication_faults.py::test_expected_mismatch_blocks_before_first_rename
tests/source_contract/test_official_artifact_build.py::test_evaluation_build_accepts_official_expected_and_publishes
tests/integration/artifacts/test_publication_recovery.py::test_normal_target_recognition_requires_reopened_expected_acceptance
tests/unit/cli/test_build_data.py::test_build_data_success_emits_only_compact_verified_manifest_summary
tests/unit/cli/test_build_data.py::test_build_data_postcommit_cleanup_error_states_published_verified_target
```

The first selector's RED is the still-absent public method, not expected mismatch; add
only the public expected-route wrapper and make the valid small core fail at the
official comparator. The second freezes the nominal trusted-result gate before any
rename. The next exact custody selector rejects result-A/stage-B mixing, structural
copies/forgeries, closed capabilities, and parent/name/inode swaps, then uses actual
parent/stage/parquet descriptors plus lock/input-close
sentinels: candidate-core verification cannot take the acceptance seal; expected
failure leaves all slots with the retained candidate custody; a copied, foreign,
prefilled, or preflight-throwing typed receiver cannot move a slot; expected success
performs the non-fallible `accept_transferred_custody` instance swap and moves the same numeric
descriptor/lock generations once only after every CP2 adopted duplicate has closed,
makes every old custody/candidate method fail, lets
only the publication capability perform a real same-filesystem sibling stage-to-target
rename plus an injected pre-commit target-to-stage rollback, and produces exactly one
close attempt per
descriptor/lock/input carrier on success, receiver fault, or early close. Forged/
copied/reused acceptance, receiver, stage, or mixed generation fails before any slot
move. Static/module-surface assertions prove the candidate retains the opaque custody
instance directly and no candidate/stage/receiver/custody/token global registry exists;
tests never read a private field or receive a raw descriptor from an API. The
official success selector is the first behavior allowed to construct a
`VerifiedArtifactSet`/`ArtifactBuildOutcome` and must use the reviewed official resource
and exact source inputs; no small fixture is called official. The remaining selectors
then close reopened recognition and CLI outcomes serially.

After the reinstall, add and run this real-default post-baseline acceptance selector:

```bash
UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv run pytest \
  tests/integration/artifacts/test_candidate_builder.py::test_real_candidate_default_permanently_refuses_after_baseline -q
```

Expected GREEN regression: CP1/CP7's already RED-driven initial production guard raises
`BASELINE_ALREADY_EXISTS` with zero transform calls, no stdout/stage/publication, and no
attempt to reach the now-unreachable second boundary. This is a new real-environment
acceptance fixture, not new production RED evidence. Do not weaken or remove the permanent synthetic `CandidateBaselineProbe`
post-transform flip/race tests or the private full-transform
`ArtifactCoreBuildOutcome` tests; run both families and prove they still cover the
second check, cleanup, all guard branches, complete transformation, telemetry, and
logical-contract extraction without a public bypass.

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
find source_material -type f -perm -222 -print
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
- [x] CP2 has no premature table-aware/full verifier; CP3 freezes specs/common checker
  plus non-interchangeable staged/final adapters; CP4-7 use only one owner-bound staged
  set before final inventory; CP7 independently invokes the final adapter and completes
  DuckDB-aware core verification; CP8 alone activates expected-accepted trust.
- [x] D-024 freezes capability ownership: CP2 models/hashing/held inventory/internal
  stub kernel; CP3 staged verification plus final table-port implementation; CP4 stage
  leaf ownership; CP5/6 staged report/timestamp/link semantic producers;
  CP7 concrete report/database ports plus packaged comparator implementation; CP8
  reviewed expected bytes, the activated expected route, and the first public trusted
  result/publication authorization.
- [x] D-025 clarifies D-024 without rewriting it: CP4 owns the opaque stage token,
  timestamp, exact Parquet/database leaves, and `StagedParquetSet`; CP5/6/7 reject bare,
  copied, mixed, closed, incomplete, or timestamp-mismatched sets; CP7 alone transitions
  to independently rebuilt final inventory handles.
- [x] CP2 uses the valid `os.scandir(held_dir_fd)` plus
  `DirEntry.stat(follow_symlinks=False)` API, binds `manifest.json` to the retained root,
  and gives CP3 one identity-revalidating entry reopen capability with no lexical
  fallback.
- [x] CP2 freezes every report field/order/nested invariant/semantic projection and
  every expected-contract literal/hash/count boundary; exhaustive comparator failures
  carry unique Unicode-sorted RFC 6901 pointers as canonical JSON.
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
