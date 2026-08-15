# Repository and Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, source-faithful data foundation that converts the eight official workbooks into typed, quality-audited Parquet and read-only DuckDB artifacts.

**Architecture:** A manifest validates immutable inputs. A streaming XLSX layer emits rows with exact Excel lineage. Product-specific normalizers produce Silver records and quality issues; a deterministic builder writes Parquet, Gold views, exact identifier links, reports, and an artifact manifest.

**Tech Stack:** Python 3.12, Pydantic, lxml/fastexcel, Polars, Parquet, DuckDB, pytest, Hypothesis, Ruff, mypy, uv.

## Global Constraints

- Official source files and expected audit values are immutable.
- Snapshot date is exactly `2026-07-11`.
- Preserve raw values and source row/column lineage.
- Public-fund default item grain is `itm_no`; source attribute grain is `(itm_no, prfd_attr_cd)`.
- `pd_tr_yn = "0"` is not suspended under the frozen domestic listed-product rule.
- Malformed records are quarantined, never silently deleted.
- Every behavior follows red-green-refactor TDD.

---

### Task 1: Bootstrap typed settings, version bundle, CLI, and source checks

**Files:**
- Create: `src/finproof/core/__init__.py`
- Create: `src/finproof/core/settings.py`
- Create: `src/finproof/core/versions.py`
- Create: `src/finproof/core/errors.py`
- Create: `src/finproof/cli/__init__.py`
- Create: `src/finproof/cli/main.py`
- Create: `tests/unit/core/test_settings.py`
- Create: `tests/unit/core/test_versions.py`
- Create: `tests/contract/test_handoff_commands.py`
- Create: `tests/contract/test_repository_automation.py`
- Create: `.env.example`
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/ci.yml`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `Settings.model_validate({}) -> Settings`
- Produces: `VersionBundle(dataset_version: date, metric_registry_version: str, state_rule_version: str, quality_rule_version: str, rating_rule_version: str, answer_policy_version: str, planner_version: str)`
- Produces: `finproof.cli.main.main(argv: Sequence[str] | None = None) -> int`
- CLI subcommands: `verify-handoff`, `audit-source`, `show-versions`

- [x] **Step 1: Write the failing settings tests**

```python
from datetime import date
from pathlib import Path

from finproof.core.settings import ExecutionMode, Settings


def test_settings_use_frozen_snapshot_and_evaluation_defaults(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "source",
        artifact_dir=tmp_path / "artifacts",
        database_path=tmp_path / "artifacts" / "finproof.duckdb",
    )

    assert settings.dataset_snapshot_date == date(2026, 7, 11)
    assert settings.execution_mode is ExecutionMode.EVALUATION
    assert settings.default_top_k == 5
    assert settings.max_top_k == 50
    assert settings.default_top_k <= settings.max_top_k
```

- [x] **Step 2: Run the focused test and observe the missing-module failure**

Run:

```bash
uv run pytest tests/unit/core/test_settings.py -q
```

Expected: FAIL because `finproof.core.settings` does not exist.

- [x] **Step 3: Implement the minimal typed settings**

```python
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExecutionMode(StrEnum):
    EVALUATION = "evaluation"
    EXTENDED_DEMO = "extended_demo"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINPROOF_", env_file=".env", extra="ignore")

    execution_mode: ExecutionMode = ExecutionMode.EVALUATION
    dataset_snapshot_date: date = date(2026, 7, 11)
    data_dir: Path = Path("source_material/data")
    artifact_dir: Path = Path("artifacts")
    database_path: Path = Path("artifacts/finproof.duckdb")
    default_top_k: int = Field(default=5, ge=1)
    max_top_k: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def validate_limits(self) -> "Settings":
        if self.default_top_k > self.max_top_k:
            raise ValueError("default_top_k must not exceed max_top_k")
        return self
```

Add typed error classes without transport dependencies:

```python
class FinProofError(Exception):
    """Base domain/application error."""


class SourceContractError(FinProofError):
    """Raised when an official source violates its frozen contract."""
```

- [x] **Step 4: Run settings tests to green**

```bash
uv run pytest tests/unit/core/test_settings.py -q
```

Expected: PASS.

- [x] **Step 5: Write failing tests for immutable versions and CLI exit codes**

```python
from datetime import date

import pytest

from finproof.core.versions import VersionBundle


def test_version_bundle_is_immutable() -> None:
    bundle = VersionBundle(dataset_version=date(2026, 7, 11))
    with pytest.raises(Exception):
        bundle.dataset_version = date(2026, 7, 12)  # type: ignore[misc]
```

```python
from finproof.cli.main import main


def test_show_versions_exits_zero(capsys) -> None:
    assert main(["show-versions"]) == 0
    assert "2026-07-11" in capsys.readouterr().out
```

- [x] **Step 6: Run and observe failures, then implement versions and CLI dispatch**

Run:

```bash
uv run pytest tests/unit/core/test_versions.py tests/contract/test_handoff_commands.py -q
```

Expected: FAIL for missing interfaces.

Implement an immutable Pydantic `VersionBundle` with seed versions from config and an `argparse` CLI that delegates `verify-handoff` and `audit-source` to importable functions from `tools` using subprocess-free Python calls. `main()` returns an integer and `if __name__ == "__main__": raise SystemExit(main())`.

- [x] **Step 7: Run task checks**

```bash
uv run pytest tests/unit/core tests/contract/test_handoff_commands.py -q
uv run ruff check src/finproof/core src/finproof/cli tests/unit/core tests/contract/test_handoff_commands.py
uv run mypy src/finproof/core src/finproof/cli tests/unit/core tests/contract/test_handoff_commands.py
uv run pytest tests/contract/test_repository_automation.py -q
uv run pre-commit run --all-files
python tools/verify_handoff.py
python tools/audit_source_data.py --check
```

Expected: all PASS.

- [x] **Step 8: Update status and commit**

```bash
git add src/finproof/core src/finproof/cli tests/unit/core tests/contract docs/implementation/STATUS.md
git commit -m "feat: bootstrap typed FinProof core and CLI"
```

---

### Task 2: Implement source manifest and streaming workbook rows with lineage

> **Approved detailed plan:** `docs/superpowers/plans/2026-08-13-phase1-task2-source-ingestion.md`
>
> D-017 supersedes the legacy path-based reader examples below. Production ingestion must use `VerifiedSourceFile`, and the complete raw lineage includes manifest-relative file, table, sheet, Excel row/column, verified checksum, dataset snapshot, raw payload/value, and an explicit optional cell applicable date. Execute and track the approved detailed plan; do not implement `iter_xlsx_rows(path, table_id, sheet_name)`.
>
> D-020 records the final-review hardening: catalog mappings are deeply immutable;
> malformed metadata/path failures are safely typed; every parsed XML part rejects
> declarations and ambiguous roots/direct metadata; and D-019 target validation applies
> before and after decoding with canonical round-tripping before ZIP access.

**Files:**
- Create: `src/finproof/data/__init__.py`
- Create: `src/finproof/data/source_manifest.py`
- Create: `src/finproof/data/xlsx_stream.py`
- Create: `src/finproof/domain/__init__.py`
- Create: `src/finproof/domain/source.py`
- Create: `tests/source_contract/test_source_manifest.py`
- Create: `tests/source_contract/test_xlsx_stream.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `SourceFileManifest.load(manifest_path: Path, schema_catalog_path: Path) -> SourceFileManifest`
- Produces: `SourceFileManifest.verify(base_dir: Path) -> VerifiedSourceSet`
- Produces: `VerifiedSourceSet.data_file(table_id: str) -> VerifiedSourceFile`
- Produces: frozen `SourceCell` and `SourceRow` contracts defined in D-017
- Produces: `iter_xlsx_rows(source: VerifiedSourceFile) -> Iterator[SourceRow]`
- Consumes: `source_material/input_manifest.json`

- [x] **Step 1: Write a failing manifest checksum test**

```python
from pathlib import Path

from finproof.data.source_manifest import SourceFileManifest


def test_official_manifest_verifies_all_files() -> None:
    repo = Path(__file__).resolve().parents[2]
    manifest = SourceFileManifest.load(
        repo / "source_material/input_manifest.json",
        repo / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(repo / "source_material")
    assert verified.data_file("PRBD01N001").expected_rows == 42_394
```

- [x] **Step 2: Run and observe the missing implementation failure**

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
```

Expected: FAIL because the manifest model/loader does not exist.

- [x] **Step 3: Implement strict manifest models and chunked SHA-256 verification**

Use Pydantic models with `extra="forbid"`. Verify path remains under `base_dir`, size matches, SHA-256 matches, and table/snapshot metadata matches the manifest. Raise `SourceContractError` with file name and mismatch category but not a misleading automatic update suggestion.

- [x] **Step 4: Run manifest test to green**

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
```

- [x] **Step 5: Write failing row-lineage tests against the official first data row**

```python
from pathlib import Path

from finproof.data.source_manifest import SourceFileManifest
from finproof.data.xlsx_stream import iter_xlsx_rows


def test_bond_reader_emits_excel_row_and_header_named_cells() -> None:
    repo = Path(__file__).resolve().parents[2]
    manifest = SourceFileManifest.load(
        repo / "source_material/input_manifest.json",
        repo / "source_material/schema_catalog.json",
    )
    source = manifest.verify(repo / "source_material").data_file("PRBD01N001")
    row = next(iter_xlsx_rows(source))

    values = {cell.column_name: cell.raw_value for cell in row.cells}
    assert row.source_row_number == 2
    assert values["PD_NO"] == "KR101501DA16"
    assert values["PD_NM"] == "국민주택1종채권 20-01"
```

Also test that empty trailing cells are represented by header name and empty raw value rather than shifting later columns.

- [x] **Step 6: Run the failing reader tests**

```bash
uv run pytest tests/source_contract/test_xlsx_stream.py -q
```

Expected: FAIL because `iter_xlsx_rows` does not exist.

- [x] **Step 7: Implement streaming XLSX parsing**

Use the approved detailed plan to implement `zipfile.ZipFile` and hardened `lxml.etree.iterparse` parsing that:

- resolve workbook sheet name to XML target
- load shared strings once per workbook
- compare the header row exactly with the ordered schema catalog
- map Excel column references to zero-based indices
- emit data rows without loading the worksheet XML into memory
- preserve empty cells, exact raw strings, checksum, snapshot, and optional applicable-date state
- clear parsed elements to bound memory
- raise `SourceContractError` for missing sheet, duplicate/blank header, or row wider than header

Do not use OCR, pandas, or openpyxl for this lineage path.

- [x] **Step 8: Run reader and source contract checks**

```bash
uv run pytest tests/source_contract/test_xlsx_stream.py tests/source_contract/test_source_manifest.py -q
uv run python tools/audit_source_data.py --check
```

Expected: PASS and frozen audit unchanged.

- [x] **Step 9: Commit**

```bash
git add src/finproof/data src/finproof/domain/source.py tests/source_contract docs/implementation/STATUS.md
git commit -m "feat: add verified streaming source ingestion"
```

---

### Task 3: Normalize domestic bonds and domestic ETF/ETN

> **Approved design:** `docs/superpowers/specs/2026-08-14-phase1-task3-domestic-normalization-design.md`
>
> **Authoritative detailed plan:** `docs/superpowers/plans/2026-08-14-phase1-task3-domestic-normalization.md`
>
> The approved design and dedicated plan supersede the legacy combined-model/
> `common.py` sketch. Execute the dedicated plan's six reviewer-worthy tasks in
> order under strict RED -> GREEN -> REFACTOR and its required independent reviews.

**Files:**

- Create focused quality/value/locator/result contracts under `src/finproof/domain/`
- Create focused pure parsers under `src/finproof/data/normalization/`
- Create the strict immutable rating registry in `src/finproof/registry/rating.py`
- Create separate domestic bond and domestic listed product models/normalizers
- Create complete synthetic `SourceRow` fixtures and focused unit tests
- Create `tests/source_contract/test_official_domestic_normalization.py`
- Modify `docs/implementation/STATUS.md` and the two Task 3 plan files only after evidence exists

**Authoritative interfaces:**

- Consumes: existing frozen `SourceRow`/`SourceCell` values from the verified Task 2 reader; normalizers accept no arbitrary source path or invented locator data.
- Produces: frozen strict `SourceCellLocator`, `NormalizedValue[T]`, `DerivedValue[T]`, `DataQualityIssue`, and `NormalizationResult[T]` contracts from the dedicated plan.
- Produces: `RatingRegistry.from_yaml(path: Path) -> RatingRegistry`, `RatingRegistry.resolve(value: str) -> RatingResolution`, and `RatingRegistry.compare(left: str, right: str) -> int`.
- Produces: `normalize_bond(row: SourceRow, as_of: date, rating_registry: RatingRegistry) -> NormalizationResult[BondInstrument]`.
- Produces: `normalize_domestic_listed(row: SourceRow, as_of: date) -> NormalizationResult[ListedProduct]`.
- Proves: 42,394 bond records/zero quarantined; 1,733 domestic listed records/one quarantined at Excel row 1,155; source groups 1,202 ETF/532 ETN; identity uniqueness and complete raw/locator fidelity across all 44,128 rows.

- [x] **Checkpoint 1: Shared quality/value/locator/result contracts and complete `SourceRow` fixture**
- [x] **Checkpoint 2: Pure text/identifier/temporal/decimal/integer parsers**
- [x] **Checkpoint 3: Strict immutable rating registry, including unregistered `C0`/`CC0`**
- [x] **Checkpoint 4: Domestic bond model and normalizer**
- [x] **Checkpoint 5: Domestic ETF/ETN model and normalizer**
- [x] **Checkpoint 6: Official 44,128-row acceptance, evidence, all gates, and final independent review**

Do not mark this Task 3 section complete until the dedicated plan records observed
focused RED/GREEN evidence, all mandatory gates, per-task reviews, the final whole-branch
review, status evidence, and clean-tree evidence. Task 3 does not start overseas/public-
fund normalization, artifact building, or Phase 1 gate closure.

---

### Task 4: Normalize overseas ETF/ETN and public funds with item/attribute split

> **Approved design:** `docs/superpowers/specs/2026-08-14-phase1-task4-overseas-public-normalization-design.md`
>
> **Authoritative detailed plan:** `docs/superpowers/plans/2026-08-14-phase1-task4-overseas-public-normalization.md`
>
> The approved design and detailed plan supersede this section's legacy domestic-model,
> inert-`as_of`, dynamic-metric, path-based, and caller-reconstructed-quarantine sketches.
> Execute the seven reviewer-worthy checkpoints below under their exact RED -> GREEN,
> commit, review, official-acceptance, and final-gate instructions.

**Authoritative interfaces:**

- `normalize_overseas_listed(row: SourceRow) -> NormalizationResult[OverseasListedProduct]`
- `normalize_fund_attribute(row: SourceRow) -> NormalizationResult[FundAttributeRow]`
- `collapse_fund_items(rows: Iterable[FundAttributeRow]) -> FundCollapseResult`
- `normalize_public_funds(rows: Iterable[SourceRow]) -> FundCollapseResult`
- D-021 canonical quality issue JSON with explicit Draft 2020-12 `FormatChecker`
- Strict frozen all-field records, normalizer `SourceRow` identity, exact-type Python
  acceptance/rejection, canonical-shape JSON validation, complete repeated locators,
  global item grouping, and deterministic issue/result ordering
- No `src/finproof/data/quarantine.py` utility bucket; focused persistence belongs to Task 5

- [x] **Checkpoint 1: D-021 canonical quality schema and partial A-011 resolution**
- [x] **Checkpoint 2: complete fixtures, shared listed type, exact helpers, and `FundItemValue`**
- [x] **Checkpoint 3: complete 49-field overseas model/normalizer with no eligibility inference**
- [x] **Checkpoint 4: complete 45-field fund row, identity/exact-type Python boundary, and canonical JSON**
- [x] **Checkpoint 5: global item collapse, completeness, exact failure cardinalities/order, and bounded-order invariance**
- [x] **Checkpoint 6: verified official 101,265-row acceptance**
- [x] **Checkpoint 7: repository gates, status evidence, independent whole-branch review, and clean tree**

Do not mark Task 4 complete until the dedicated plan records every focused RED/GREEN,
per-checkpoint review, official count/fidelity assertion, final whole-branch review,
mandatory gate, and clean-tree result. Task 4 does not build artifacts, exact links,
families, query/API behavior, or eligibility rules.

---

### Task 5: Build reproducible Parquet/DuckDB artifacts and exact links

> **Approved specification:**
> `docs/superpowers/specs/2026-08-14-phase1-task5-artifact-build-design.md`
>
> **Authoritative detailed plan:**
> `docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md`

D-022, D-023, D-024, and D-025 supersede the removed legacy two-argument builder, undeclared
`table_hashes`, generic atomic-directory replacement, count-only DuckDB validation,
trim-ambiguous link, and tracked runtime-artifact examples. Do not reconstruct or
execute those examples from Git history.

The dedicated plan must implement the approved specification under strict RED -> GREEN
-> REFACTOR with these eight reviewer-worthy checkpoints:

- [x] **Checkpoint 1: build settings/options, runtime schema resources, artifact config,
  expected-contract types/comparison and synthetic bootstrap boundary, dependencies,
  and typed errors; no official baseline content**
- [x] **Checkpoint 2: strict manifest/load, descriptor-bound physical inventory,
  canonical schema/table/report/overall hash primitives, exact report contracts,
  exhaustive expected-contract comparison, and an internal synthetic-port kernel; no
  public trusted verifier/result**
- [x] **Checkpoint 3: frozen table specs, wide projection/strict `record_json`
  serializers, exact Decimal/time behavior, capability-bound Parquet writers, one
  bounded stream/unique checker, D-025 single-owner staged-set verification contracts
  for CP4-7, and the distinct final CP2-inventory adapter implementation first invoked
  by CP7**
- [x] **Checkpoint 4: complete held-descriptor one-pass Bronze streaming; the exact
  Bronze source-audit typestate plus forged-later-phase rejection; exact-nine immutable
  descriptor-held build-input identity issued only after a trusted-Settings-recomputed,
  instance-owned resolved-nine bundle and held verifier seal; owning-module held-stream
  config/registry/manifest/catalog parsing with ABA rejection; CP2-owned opaque held-root adoption; and one managed live/closing/closed stage owner with pathless
  fixed-bound external ordering, CP4-owned Parquet/database capabilities, capability-
  bound verification-root custody without publication transitions, exact abort/
  retention/lock transfer into an instance-owned candidate custody without global
  registries, spill, and cleanup behavior (CP5 first adds Silver, CP6
  first adds Complete/report, CP8 first atomically consumes expected-bound custody into
  the sole production publication transition owner)**
- [ ] **Checkpoint 5: wide Silver products/attributes, bounded fund-item collapse,
  D-021 quality persistence, quarantine, the first exact Silver source-audit typestate,
  and deterministic quality-summary reporting**
- [ ] **Checkpoint 6: exact raw-identifier links, full bidirectional locator evidence,
  pair hash, conflict rejection, the first exact Complete source-audit typestate, and
  the sole source-audit report producer**
- [ ] **Checkpoint 7: concrete report/database ports and packaged-comparator
  implementation, complete private core verification, self-contained DuckDB exact-
  content verification, authorization-independent publication/rollback/recovery state
  mechanics, read-only access, guarded unpublished candidate, and safe absent-baseline
  CLI behavior**
- [ ] **Checkpoint 8: two-build official logical reproduction, independently reviewed
  official expected-contract creation plus wheel-byte test, activation of the sole
  public expected-accepted verifier/result, typed same-generation one-use instance
  custody transfer into the sole production publication owner, and publication recognition, acceptance,
  bounded-memory evidence, all Phase 1 gates, status, review, and clean tree**

Exact next checkpoint: Checkpoint 5, wide Silver products/attributes, bounded
public-fund item collapse, D-021 quality persistence and quarantine, the Silver
source-audit typestate, and deterministic quality-summary reporting.

The dedicated plan is the sole Task 5 execution authority after independent plan
review. No Task 5 production code starts before that review passes. Runtime files under
`artifacts/` remain generated and untracked; only the timestamp-free official logical
contract is tracked.
