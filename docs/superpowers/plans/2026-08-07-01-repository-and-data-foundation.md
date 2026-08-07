# Repository and Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED REPOSITORY CONTRACT: follow
> `docs/implementation/QUALITY_LOOP.md` for the one task selected by `STATUS.md`. Skills are
> optional aids and may not expand scope, writable paths, ownership, or review gates. Steps use
> checkbox (`- [ ]`) syntax for tracking.

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
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `Settings.model_validate({}) -> Settings`
- Produces: `VersionBundle(dataset_version: date, metric_registry_version: str, state_rule_version: str, quality_rule_version: str, rating_rule_version: str, answer_policy_version: str, planner_version: str)`
- Produces: `finproof.cli.main.main(argv: Sequence[str] | None = None) -> int`
- CLI subcommands: `verify-handoff`, `audit-source`, `show-versions`

- [ ] **Step 1: Write the failing settings tests**

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

- [ ] **Step 2: Run the focused test and observe the missing-module failure**

Run:

```bash
uv run pytest tests/unit/core/test_settings.py -q
```

Expected: FAIL because `finproof.core.settings` does not exist.

- [ ] **Step 3: Implement the minimal typed settings**

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

- [ ] **Step 4: Run settings tests to green**

```bash
uv run pytest tests/unit/core/test_settings.py -q
```

Expected: PASS.

- [ ] **Step 5: Write failing tests for immutable versions and CLI exit codes**

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

- [ ] **Step 6: Run and observe failures, then implement versions and CLI dispatch**

Run:

```bash
uv run pytest tests/unit/core/test_versions.py tests/contract/test_handoff_commands.py -q
```

Expected: FAIL for missing interfaces.

Implement an immutable Pydantic `VersionBundle` with seed versions from config and an `argparse` CLI that delegates `verify-handoff` and `audit-source` to importable functions from `tools` using subprocess-free Python calls. `main()` returns an integer and `if __name__ == "__main__": raise SystemExit(main())`.

- [ ] **Step 7: Run task checks**

```bash
uv run pytest tests/unit/core tests/contract/test_handoff_commands.py -q
uv run ruff check src/finproof/core src/finproof/cli tests/unit/core tests/contract/test_handoff_commands.py
uv run mypy src/finproof/core src/finproof/cli tests/unit/core tests/contract/test_handoff_commands.py
python tools/verify_handoff.py
python tools/audit_source_data.py --check
```

Expected: all PASS.

- [ ] **Step 8: Update status and commit**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/core/__init__.py src/finproof/core/settings.py src/finproof/core/versions.py src/finproof/core/errors.py src/finproof/cli/__init__.py src/finproof/cli/main.py tests/unit/core/test_settings.py tests/unit/core/test_versions.py tests/contract/test_handoff_commands.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: bootstrap typed FinProof core and CLI"
```

---

### Task 2: Implement source manifest and streaming workbook rows with lineage

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
- Produces: `SourceFileManifest.load(path: Path) -> SourceFileManifest`
- Produces: `SourceFileManifest.verify(base_dir: Path) -> None`
- Produces: `SourceCell(column_name: str, column_index: int, raw_value: str)`
- Produces: `SourceRow(table_id: str, source_file: str, sheet_name: str, excel_row_number: int, cells: tuple[SourceCell, ...])`
- Produces: `iter_xlsx_rows(path: Path, table_id: str, sheet_name: str) -> Iterator[SourceRow]`
- Consumes: `source_material/input_manifest.json`

- [ ] **Step 1: Write a failing manifest checksum test**

```python
from pathlib import Path

from finproof.data.source_manifest import SourceFileManifest


def test_official_manifest_verifies_all_files() -> None:
    repo = Path(__file__).resolve().parents[2]
    manifest = SourceFileManifest.load(repo / "source_material/input_manifest.json")
    manifest.verify(repo / "source_material")
```

- [ ] **Step 2: Run and observe the missing implementation failure**

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
```

Expected: FAIL because the manifest model/loader does not exist.

- [ ] **Step 3: Implement strict manifest models and chunked SHA-256 verification**

Use Pydantic models with `extra="forbid"`. Verify path remains under `base_dir`, size matches, SHA-256 matches, and table/snapshot metadata matches the manifest. Raise `SourceContractError` with file name and mismatch category but not a misleading automatic update suggestion.

- [ ] **Step 4: Run manifest test to green**

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
```

- [ ] **Step 5: Write failing row-lineage tests against the official first data row**

```python
from pathlib import Path

from finproof.data.xlsx_stream import iter_xlsx_rows


def test_bond_reader_emits_excel_row_and_header_named_cells() -> None:
    path = Path("source_material/data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx")
    row = next(iter_xlsx_rows(path, table_id="PRBD01N001", sheet_name="datarows"))

    values = {cell.column_name: cell.raw_value for cell in row.cells}
    assert row.excel_row_number == 2
    assert values["PD_NO"] == "KR101501DA16"
    assert values["PD_NM"] == "국민주택1종채권 20-01"
```

Also test that empty trailing cells are represented by header name and empty raw value rather than shifting later columns.

- [ ] **Step 6: Run the failing reader tests**

```bash
uv run pytest tests/source_contract/test_xlsx_stream.py -q
```

Expected: FAIL because `iter_xlsx_rows` does not exist.

- [ ] **Step 7: Implement streaming XLSX parsing**

Use `zipfile.ZipFile` and `lxml.etree.iterparse` to:

- resolve workbook sheet name to XML target
- load shared strings once per workbook
- parse header row exactly
- map Excel column references to zero-based indices
- emit data rows without loading the worksheet XML into memory
- preserve empty cells and exact raw strings
- clear parsed elements to bound memory
- raise `SourceContractError` for missing sheet, duplicate/blank header, or row wider than header

Do not use OCR, pandas, or openpyxl for this lineage path.

- [ ] **Step 8: Run reader and source contract checks**

```bash
uv run pytest tests/source_contract/test_xlsx_stream.py tests/source_contract/test_source_manifest.py -q
uv run python tools/audit_source_data.py --check
```

Expected: PASS and frozen audit unchanged.

- [ ] **Step 9: Commit**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/data/__init__.py src/finproof/data/source_manifest.py src/finproof/data/xlsx_stream.py src/finproof/domain/__init__.py src/finproof/domain/source.py tests/source_contract/test_source_manifest.py tests/source_contract/test_xlsx_stream.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: add verified streaming source ingestion"
```

---

### Task 3: Normalize domestic bonds and domestic ETF/ETN

**Files:**
- Create: `src/finproof/domain/quality.py`
- Create: `src/finproof/domain/products.py`
- Create: `src/finproof/data/normalization/__init__.py`
- Create: `src/finproof/data/normalization/common.py`
- Create: `src/finproof/data/normalization/bonds.py`
- Create: `src/finproof/data/normalization/domestic_listed.py`
- Create: `src/finproof/registry/__init__.py`
- Create: `src/finproof/registry/rating.py`
- Create: `tests/unit/data/test_bond_normalization.py`
- Create: `tests/unit/data/test_domestic_listed_normalization.py`
- Create: `tests/unit/registry/test_rating_registry.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `normalize_bond(row: SourceRow, as_of: date, rating_registry: RatingRegistry) -> NormalizationResult[BondInstrument]`
- Produces: `normalize_domestic_listed(row: SourceRow, as_of: date) -> NormalizationResult[ListedProduct]`
- Produces: `NormalizationResult[T](record: T | None, issues: tuple[DataQualityIssue, ...])`
- Produces: `RatingRegistry.from_yaml(path: Path) -> RatingRegistry`
- Produces: `RatingRegistry.compare(left: str, right: str) -> int`

- [ ] **Step 1: Write failing bond date/source-fidelity tests**

```python
from datetime import date

from finproof.data.normalization.bonds import normalize_bond
from tests.helpers.source_rows import source_row


def test_bond_recalculates_remaining_days_without_overwriting_raw_value(rating_registry) -> None:
    row = source_row(
        "PRBD01N001",
        2,
        {"PD_NO": "B1", "PD_NM": "채권", "MAT_DT": "20260720", "REMAINING_DAYS": "999"},
    )
    result = normalize_bond(row, date(2026, 7, 11), rating_registry)

    assert result.record is not None
    assert result.record.remaining_days_at_as_of == 9
    assert result.record.source_remaining_days.raw_value == "999"
```

Add separate tests for `MAT_DT` blank, `0`, `99991231`, invalid calendar date, positive quantity on matured bond, missing rating, and mixed agency text.

- [ ] **Step 2: Run and observe failure**

```bash
uv run pytest tests/unit/data/test_bond_normalization.py tests/unit/registry/test_rating_registry.py -q
```

- [ ] **Step 3: Implement typed value wrappers, quality issues, rating registry, and bond normalization**

Use `Decimal` for yields/amounts and `date` for dates. `NormalizedValue[T]` contains raw string, parsed value, quality status, rule ID, and source-cell locator. A malformed product ID is a quarantine issue; a missing optional metric is not.

Rating ordering comes solely from `config/rating_scale.yaml`; missing/Not Rated has no ordinal pass for `AA-` filtering.

- [ ] **Step 4: Run bond/rating tests to green**

```bash
uv run pytest tests/unit/data/test_bond_normalization.py tests/unit/registry/test_rating_registry.py -q
```

- [ ] **Step 5: Write failing domestic listed-product state tests**

```python
from datetime import date

from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from tests.helpers.source_rows import source_row


def test_domestic_etf_is_eligible_when_sale_on_not_suspended_and_dates_valid() -> None:
    row = source_row(
        "PREF01N001",
        2,
        {
            "pd_itm_no": "KR7000000001",
            "pd_nm": "테스트 ETF",
            "pd_grp_no": "ETF",
            "pd_sale_yn": "1",
            "pd_tr_yn": "0",
            "pd_lstg_dt": "20200101",
            "pd_lste_dt": "99991231",
        },
    )
    result = normalize_domestic_listed(row, date(2026, 7, 11))
    assert result.record is not None
    assert result.record.is_eligible_at_as_of is True
```

Add tests proving `pd_tr_yn="1"` is suspended, ETN remains type ETN, `pd_net_tamt` is primary AUM, and zero tracking error retains recorded zero.

- [ ] **Step 6: Run, implement, and rerun domestic listed tests**

```bash
uv run pytest tests/unit/data/test_domestic_listed_normalization.py -q
```

Implement explicit type/state/date parsing and metric wrappers; do not reuse a generic state flag with inverted semantics.

```bash
uv run pytest tests/unit/data/test_domestic_listed_normalization.py -q
```

Expected: PASS.

- [ ] **Step 7: Run task checks and commit**

```bash
uv run pytest tests/unit/data tests/unit/registry -q
uv run ruff check src/finproof/data/normalization src/finproof/domain src/finproof/registry tests/unit/data tests/unit/registry
uv run mypy src/finproof/data/normalization src/finproof/domain src/finproof/registry
```

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/domain/quality.py src/finproof/domain/products.py src/finproof/data/normalization/__init__.py src/finproof/data/normalization/common.py src/finproof/data/normalization/bonds.py src/finproof/data/normalization/domestic_listed.py src/finproof/registry/__init__.py src/finproof/registry/rating.py tests/unit/data/test_bond_normalization.py tests/unit/data/test_domestic_listed_normalization.py tests/unit/registry/test_rating_registry.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: normalize bonds and domestic listed products"
```

---

### Task 4: Normalize overseas ETF/ETN and public funds with item/attribute split

**Files:**
- Create: `src/finproof/data/normalization/overseas_listed.py`
- Create: `src/finproof/data/normalization/public_funds.py`
- Create: `src/finproof/data/quarantine.py`
- Create: `tests/unit/data/test_overseas_listed_normalization.py`
- Create: `tests/unit/data/test_public_fund_normalization.py`
- Create: `tests/source_contract/test_public_fund_grain.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `normalize_overseas_listed(row: SourceRow, as_of: date) -> NormalizationResult[ListedProduct]`
- Produces: `normalize_fund_attribute(row: SourceRow) -> NormalizationResult[FundAttributeRow]`
- Produces: `collapse_fund_items(rows: Iterable[FundAttributeRow]) -> FundCollapseResult`
- Produces: `FundCollapseResult(items: tuple[FundItem, ...], attributes: tuple[FundItemAttribute, ...], issues: tuple[DataQualityIssue, ...])`

- [ ] **Step 1: Write failing overseas zero/tie preservation tests**

```python
from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from tests.helpers.source_rows import source_row


def test_overseas_fee_zero_is_preserved_and_flagged() -> None:
    row = source_row(
        "PREF02N001",
        2,
        {"pd_itm_no": "US1", "pd_nm": "ETF", "pd_grp_no": "ETF", "pd_trd_ccy": "USD", "cu_charge_rt": "0"},
    )
    result = normalize_overseas_listed(row, as_of=SNAPSHOT_DATE)
    fee = result.record.metrics["total_fee"]  # type: ignore[union-attr]
    assert fee.value == Decimal("0")
    assert fee.quality_status is QualityStatus.RECORDED_ZERO_UNVERIFIED
```

Add tests for ETF/ETN type, USD read from field, constant-zero return retained, and rich strategy text treated as data.

- [ ] **Step 2: Run, implement minimal overseas normalizer, and rerun**

```bash
uv run pytest tests/unit/data/test_overseas_listed_normalization.py -q
```

Expected RED, then implement and obtain PASS.

- [ ] **Step 3: Write failing public-fund item/attribute tests**

```python
from finproof.data.normalization.public_funds import collapse_fund_items, normalize_fund_attribute


def test_two_attribute_rows_collapse_to_one_fund_item() -> None:
    rows = [
        normalize_fund_attribute(fund_source_row("F1", "A", name="펀드")).record,
        normalize_fund_attribute(fund_source_row("F1", "B", name="펀드")).record,
    ]
    result = collapse_fund_items(row for row in rows if row is not None)
    assert [item.fund_item_id for item in result.items] == ["F1"]
    assert {(a.fund_item_id, a.attribute_code) for a in result.attributes} == {("F1", "A"), ("F1", "B")}
```

Add tests for:

- literal `NULL` risk -> missing-literal-null
- `or_attr_desc="06"` -> unmapped code
- KRW/USD currency preserved
- disagreement in non-attribute fields -> quarantine/high issue, not silent representative selection
- malformed `itm_no='"'` -> no normal item and `malformed_source_row`
- deterministic representative row chooses lowest Excel row only when fields agree

- [ ] **Step 4: Run, implement, and rerun public-fund tests**

```bash
uv run pytest tests/unit/data/test_public_fund_normalization.py -q
```

Implement a sort/group pass keyed by `itm_no`, compare canonical non-attribute payload hashes, emit attributes separately, and preserve all source locators.

```bash
uv run pytest tests/unit/data/test_public_fund_normalization.py -q
```

- [ ] **Step 5: Add the full-source grain contract test**

```python
@pytest.mark.source_contract
@pytest.mark.slow
def test_official_public_fund_grain_matches_frozen_counts() -> None:
    result = build_public_fund_records(OFFICIAL_FUND_PATH)
    assert result.source_rows == 95_619
    assert result.unique_item_ids == 11_139
    assert result.valid_items == 11_138
    assert result.unique_item_attribute_pairs == 95_619
    assert result.non_attribute_disagreement_items == 0
```

- [ ] **Step 6: Run source contract and audit**

```bash
uv run pytest tests/source_contract/test_public_fund_grain.py -q -m source_contract
uv run python tools/audit_source_data.py --check
```

- [ ] **Step 7: Commit**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/data/normalization/overseas_listed.py src/finproof/data/normalization/public_funds.py src/finproof/data/quarantine.py tests/unit/data/test_overseas_listed_normalization.py tests/unit/data/test_public_fund_normalization.py tests/source_contract/test_public_fund_grain.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: normalize overseas products and public fund grain"
```

---

### Task 5: Build reproducible Parquet/DuckDB artifacts and exact links

**Files:**
- Create: `src/finproof/data/build.py`
- Create: `src/finproof/data/artifact_manifest.py`
- Create: `src/finproof/storage/__init__.py`
- Create: `src/finproof/storage/schema.sql`
- Create: `src/finproof/storage/database.py`
- Create: `src/finproof/cli/build_data.py`
- Create: `tests/integration/data/test_artifact_build.py`
- Create: `tests/integration/data/test_exact_cross_source_links.py`
- Create: `tests/integration/data/test_build_reproducibility.py`
- Create: `artifacts/manifest.json`
- Create: `artifacts/reports/source_audit.json`
- Create: `artifacts/reports/quality_summary.json`
- Modify: `src/finproof/cli/main.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `build_artifacts(settings: Settings, versions: VersionBundle) -> ArtifactManifest`
- Produces: `ArtifactManifest.load(path: Path) -> ArtifactManifest`
- Produces: `open_read_only_database(path: Path) -> duckdb.DuckDBPyConnection`
- CLI: `finproof build-data --clean`

- [ ] **Step 1: Write a failing small-fixture artifact build test**

```python
from finproof.data.build import build_artifacts


def test_build_writes_manifest_parquet_database_and_quality_report(fixture_settings, versions) -> None:
    manifest = build_artifacts(fixture_settings, versions)
    assert manifest.database_path.name == "finproof.duckdb"
    assert "silver_fund_item" in manifest.tables
    assert manifest.tables["silver_fund_item"].row_count == 1
    assert (fixture_settings.artifact_dir / "reports/source_audit.json").is_file()
    assert (fixture_settings.artifact_dir / "reports/quality_summary.json").is_file()
```

- [ ] **Step 2: Run and observe failure**

```bash
uv run pytest tests/integration/data/test_artifact_build.py -q
```

- [ ] **Step 3: Implement deterministic build transaction**

Build into a temporary sibling directory, then atomically replace the target only after:

- source manifest passes
- all rows normalize
- expected tables and schemas are present
- quality issues are written
- DuckDB views/counts validate
- artifact files receive SHA-256

Use stable sort keys and deterministic Parquet settings. Exclude wall-clock timestamps from logical reproducibility hashes; store operational build time separately.

- [ ] **Step 4: Run small build test to green**

```bash
uv run pytest tests/integration/data/test_artifact_build.py -q
```

- [ ] **Step 5: Write failing exact-link and reproducibility tests**

```python
@pytest.mark.source_contract
@pytest.mark.slow
def test_official_exact_domestic_etf_fund_links_equal_47(official_artifacts) -> None:
    with open_read_only_database(official_artifacts.database_path) as conn:
        count = conn.execute("select count(*) from gold_exact_cross_source_link").fetchone()[0]
    assert count == 47
```

```python
def test_two_fixture_builds_have_same_logical_manifest(build_twice) -> None:
    first, second = build_twice
    assert first.logical_hash == second.logical_hash
    assert first.table_hashes == second.table_hashes
```

- [ ] **Step 6: Run, implement exact identifier link and stable manifest, rerun**

```bash
uv run pytest tests/integration/data/test_exact_cross_source_links.py tests/integration/data/test_build_reproducibility.py -q
```

Link only `PREF01N001.pd_itm_no = PRFD01N001.ksd_itm_no`. Store rule/evidence and reject duplicate/conflicting exact mappings.

- [ ] **Step 7: Build official artifacts and run the complete Phase 1 gate**

```bash
uv run finproof build-data --clean
uv run pytest -q tests/unit/data tests/unit/registry tests/source_contract tests/integration/data
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

Inspect DuckDB counts against `tests/contracts/expected_source_audit.json`.

- [ ] **Step 8: Update phase status, record artifact hashes, and commit**

```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- src/finproof/data/build.py src/finproof/data/artifact_manifest.py src/finproof/storage/__init__.py src/finproof/storage/schema.sql src/finproof/storage/database.py src/finproof/cli/build_data.py tests/integration/data/test_artifact_build.py tests/integration/data/test_exact_cross_source_links.py tests/integration/data/test_build_reproducibility.py artifacts/manifest.json artifacts/reports/source_audit.json artifacts/reports/quality_summary.json src/finproof/cli/main.py docs/implementation/STATUS.md
git diff --cached --name-status --
git commit -m "feat: build reproducible FinProof data artifacts"
```

Do not commit large generated Parquet/database files unless the organizer repository policy requires them. If excluded, record their build command and shared immutable artifact link/checksum in the submission docs.
