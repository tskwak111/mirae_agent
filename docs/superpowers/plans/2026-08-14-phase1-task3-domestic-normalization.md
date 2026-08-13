# Phase 1 Task 3 Domestic Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize verified `PRBD01N001` domestic-bond rows and verified `PREF01N001` domestic ETF/ETN rows into immutable typed domain records while preserving exact raw value lineage.

**Architecture:** The Task 2 reader established a fail-closed `VerifiedSourceFile -> SourceRow` boundary. Task 3 adds a pure, deterministic `SourceRow -> NormalizationResult[T]` boundary. Every transformed source field is a frozen `NormalizedValue[T]` carrying the exact raw string, typed value, quality state, versioned rule, and complete source-cell locator; derived states use a separate `DerivedValue[T]` carrying their explicit `as_of_date` and input locators.

**Tech Stack:** Python 3.12; frozen strict Pydantic models; `Decimal`; `date`; timezone-naive source `datetime`; PyYAML 6; pytest 9; Ruff; mypy; uv.

## Global Constraints

- Inputs are only immutable `SourceRow` values produced by the verified Task 2 reader or equivalent complete synthetic fixtures.
- Normalizers perform no filesystem, database, network, clock, or environment I/O.
- Raw values are never trimmed, replaced, or overwritten. Normalized text may be trimmed only in the typed value beside the raw string.
- `Decimal` is used for quantities, amounts, yields, fees, returns, duration, and prices. `float` is prohibited in normalization contracts.
- Financial dates use `date`; the domestic listed daily update timestamp uses a timezone-naive source `datetime` because the source contains no timezone.
- A field-level applicable date is not inferred from a nearby update column unless an explicit registry rule maps them. Task 3 preserves update columns separately and leaves the source cell's `applicable_date` unchanged.
- Missing optional metrics do not quarantine a product. Invalid mandatory identity or product-type fields do.
- `NormalizationResult.record is None` if and only if the row is quarantined.
- Official source files and `tests/contracts/expected_source_audit.json` remain immutable.
- This task does not write artifacts, mutate official inputs, normalize overseas products or public funds, or implement query/API behavior.
- Every production behavior follows strict RED -> GREEN -> REFACTOR: write one focused test, observe the expected missing symbol or behavior, implement the smallest behavior, rerun the focused test and related suite, refactor only while green, then commit.
- Acceptance-only tests in Task 6 may pass immediately because Tasks 1-5 already implement their behavior; never manufacture a production RED for acceptance evidence.
- Normalizers accept `SourceRow`, never a caller-supplied `Path`, table name, sheet name, checksum, row number, or arbitrary locator mapping. `RatingRegistry.from_yaml(path: Path)` is the sole Task 3 configuration-path interface.
- Public issue reasons are fixed safe strings and never contain raw payloads, absolute paths, stack traces, or product text.
- Rule IDs and rule versions are nonempty. Task 3 uses rule version `1.0.0`, matching the checked-in rating, quality, and state policy versions.
- Every new Pydantic contract uses `ConfigDict(frozen=True, extra="forbid", strict=True)`. Raw YAML is first checked by an explicit strict internal configuration model with strict scalar fields, then deliberately converted into immutable public registry values; no validation depends on Pydantic coercion.
- Keep each module focused. Do not create `common.py`, a generic utility bucket, a combined product model, or a normalizer that dispatches across unrelated product types.

---

### Task 1: Add shared quality, value, locator, and result contracts plus a complete `SourceRow` fixture

**Files:**

- Modify: `src/finproof/core/errors.py`
- Create: `src/finproof/domain/locators.py`
- Create: `src/finproof/domain/values.py`
- Create: `src/finproof/domain/quality.py`
- Create: `src/finproof/domain/normalization.py`
- Modify: `src/finproof/domain/__init__.py`
- Create: `tests/helpers/source_rows.py`
- Create: `tests/unit/domain/test_normalization_contracts.py`

**Interfaces:**

- Consumes: the existing frozen `SourceRow` and `SourceCell` from `finproof.domain.source`; specifically `SourceRow.cell(column_name: str) -> SourceCell` with exact case-sensitive lookup.
- Produces: `NormalizationContractError(expected_table: str, actual_table: str)` with no path or payload argument.
- Produces: the exact `QualityStatus(StrEnum)` values `valid`, `missing_blank`, `missing_literal_null`, `sentinel_zero`, `sentinel_max_date`, `recorded_zero`, `recorded_zero_unverified`, `invalid_format`, `out_of_domain`, `constant_metric`, `stale`, `mixed_source_values`, and `malformed_source_row`.
- Produces: `IssueSeverity(StrEnum)` values `info`, `warning`, `high`, and `blocker`.
- Produces: frozen strict `SourceCellLocator.from_row(row: SourceRow, column_name: str) -> SourceCellLocator` with `source_table`, manifest-relative `source_file`, `source_sheet`, Excel row, exact source column name/number/letter, checksum, snapshot date, and the cell's unchanged applicable date.
- Produces: frozen strict generic `NormalizedValue[T](raw_value: str, normalized_value: T | None, quality_status: QualityStatus, rule_id: str, rule_version: str, source: SourceCellLocator)`.
- Produces: frozen strict generic `DerivedValue[T](value: T | None, quality_status: QualityStatus, rule_id: str, rule_version: str, as_of_date: date, inputs: tuple[SourceCellLocator, ...])`.
- Produces: frozen strict `DataQualityIssue(issue_id: str, rule_id: str, rule_version: str, severity: IssueSeverity, quality_status: QualityStatus, source: SourceCellLocator, reason: str, quarantined: bool, raw_payload_sha256: str, first_detected_at: datetime | None)`.
- Produces: frozen strict generic `NormalizationResult[T](record: T | None, issues: tuple[DataQualityIssue, ...])`; `record=None` requires at least one quarantined issue, while a result with a record rejects every quarantined issue.
- Produces: `DataQualityIssue.from_row(row: SourceRow, column_name: str, *, rule_id: str, rule_version: str, severity: IssueSeverity, quality_status: QualityStatus, reason: str, quarantined: bool) -> DataQualityIssue`; normalization always leaves `first_detected_at=None`.
- Produces: `source_row(table_id: Literal["PRBD01N001", "PREF01N001"], values: Mapping[str, str] | None = None, *, excel_row: int = 2, applicable_dates: Mapping[str, date | None] | None = None) -> SourceRow`. It creates every official cell in schema order with fixed safe fixture lineage and accepts no path, checksum, sheet, column-number, or raw-payload override.

- [ ] **Step 1: Write the complete synthetic-row helper before tests use it**

Create `tests/helpers/source_rows.py` with these exact official ordered headers and fixed valid defaults:

```python
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import PurePosixPath
from typing import Literal

from finproof.domain.source import SourceCell, SourceRow

SNAPSHOT_DATE = date(2026, 7, 11)

BOND_COLUMNS = (
    "PD_NO", "PD_EXG_MKT", "PD_NM", "PD_ABRV_NM", "PD_ENG_NM",
    "PD_ABRV_ENG_NM", "PD_CTRY_CD", "PD_PBCM", "STD_PD_MCLS_NM",
    "STD_PD_SCLS_NM", "BD_KND", "CURR_CD", "ISU_BAL_AMT", "ISU_DT",
    "MAT_DT", "SRFC_IRT", "PD_EVCO_CRD_GRD", "PD_RISK_GCD",
    "PD_STD_INFO_UPDATE", "BUY_YIELD", "CORP_PRETAX_YIELD",
    "CORP_AFTER_TAX_YIELD", "AFTER_TAX_YIELD", "PREF_TAX_YIELD",
    "AVG_ANNUAL_TAX_YIELD", "DEPO_EQUIV_YIELD_154", "BUYABLE_QUANTITY",
    "REMAINING_DAYS", "DUR", "COV", "NDY_DUR", "NDY_COV", "EVAL_PRICE",
    "APPLIED_YIELD", "DIRTY", "NDY_EVAL_PRICE", "NDY_APPLIED_YIELD",
    "NDY_DIRTY", "CRD_GRD", "CRD_GRD_DT",
)

DOMESTIC_LISTED_COLUMNS = (
    "cu_base_index", "cu_charge_etc_rt", "cu_charge_rt", "cu_fund_mgmt_co",
    "cu_lev_fector", "cu_strtegy", "cu_upt_dt", "du_bpr", "du_chas_errt",
    "du_clpr", "du_diff_rt", "du_er_1d", "du_er_1m", "du_er_1y",
    "du_er_3m", "du_er_6m", "du_er_ytd", "du_hpr", "du_last_aum",
    "du_last_nav", "du_lpr", "du_nav_rnf_amt", "du_nav_yday", "du_upt_dt",
    "du_val_1d", "du_val_1m", "du_val_5d", "du_vol_1d", "du_vol_avg_1m",
    "du_vol_avg_5d", "nru_mkt_diff_rt", "nru_mkt_inav", "pd_abrv_nm",
    "pd_circ_net_tamt", "pd_circ_stk_cnt", "pd_curr_cd", "pd_curr_nm",
    "pd_divd_amt_pshr", "pd_dvid_cycl", "pd_dvid_yield", "pd_exg_mkt_cd",
    "pd_exg_mkt_nm", "pd_grp_no", "pd_itm_no", "pd_itm_no_ma",
    "pd_lst_price", "pd_lst_stk_cnt", "pd_lste_dt", "pd_lstg_dt", "pd_mkt_id",
    "pd_mkt_nm", "pd_nav_pshr", "pd_net_ast_pshr", "pd_net_prft_pshr",
    "pd_net_rt_ast_pshr", "pd_net_tamt", "pd_nm", "pd_pen_risk_nm",
    "pd_pen_tr_yn", "pd_risk_cd", "pd_risk_nm", "pd_sale_yn", "pd_sect_cd",
    "pd_sect_nm", "pd_spac_yn", "pd_stk_cnt", "pd_tr_yn", "ru_mkt_price",
    "ru_mkt_volume", "wu_core_yn", "wu_inv_ast_type", "wu_inv_rgn", "wu_upt_dt",
)

TableId = Literal["PRBD01N001", "PREF01N001"]


def _excel_column_letter(number: int) -> str:
    letters: list[str] = []
    remaining = number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def source_row(
    table_id: TableId,
    values: Mapping[str, str] | None = None,
    *,
    excel_row: int = 2,
    applicable_dates: Mapping[str, date | None] | None = None,
) -> SourceRow:
    columns = BOND_COLUMNS if table_id == "PRBD01N001" else DOMESTIC_LISTED_COLUMNS
    defaults = (
        {
            "PD_NO": "KR0000000001", "PD_NM": "테스트 채권", "PD_ABRV_NM": "채권",
            "CURR_CD": "KRW", "BD_KND": "회사채", "ISU_DT": "20200101",
            "MAT_DT": "20270711", "BUYABLE_QUANTITY": "1", "REMAINING_DAYS": "365",
        }
        if table_id == "PRBD01N001"
        else {
            "pd_itm_no": "KR7000000001", "pd_itm_no_ma": "A000001",
            "pd_grp_no": "ETF", "pd_nm": "테스트 ETF", "pd_abrv_nm": "테스트",
            "pd_curr_cd": "CURR_CD_KRW", "pd_sale_yn": "1", "pd_tr_yn": "0",
            "pd_lstg_dt": "20200101", "pd_lste_dt": "99991231",
        }
    )
    supplied = dict(values or {})
    unknown = set(supplied) - set(columns)
    if unknown:
        raise KeyError(f"unknown source columns: {sorted(unknown)}")
    dates = dict(applicable_dates or {})
    unknown_dates = set(dates) - set(columns)
    if unknown_dates:
        raise KeyError(f"unknown applicable-date columns: {sorted(unknown_dates)}")
    raw = {column: "" for column in columns} | defaults | supplied
    cells = tuple(
        SourceCell(
            column_name=column,
            excel_column_number=number,
            excel_column_letter=_excel_column_letter(number),
            raw_value=raw[column],
            applicable_date=dates.get(column),
        )
        for number, column in enumerate(columns, start=1)
    )
    return SourceRow(
        source_table=table_id,
        source_file=PurePosixPath(f"data/{table_id}_fixture.xlsx"),
        source_sheet="datarows",
        source_row_number=excel_row,
        source_checksum="a" * 64,
        source_snapshot_date=SNAPSHOT_DATE,
        raw_payload=tuple(cell.raw_value for cell in cells),
        cells=cells,
    )
```

- [ ] **Step 2: Write failing enum, helper-completeness, and locator tests**

Create `tests/unit/domain/test_normalization_contracts.py` with literal equality checks rather than subset checks:

```python
from datetime import date

import pytest

from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import IssueSeverity, QualityStatus
from tests.helpers.source_rows import BOND_COLUMNS, DOMESTIC_LISTED_COLUMNS, source_row


def test_quality_and_severity_values_are_exact() -> None:
    assert {status.value for status in QualityStatus} == {
        "valid", "missing_blank", "missing_literal_null", "sentinel_zero",
        "sentinel_max_date", "recorded_zero", "recorded_zero_unverified",
        "invalid_format", "out_of_domain", "constant_metric", "stale",
        "mixed_source_values", "malformed_source_row",
    }
    assert {severity.value for severity in IssueSeverity} == {
        "info", "warning", "high", "blocker",
    }


@pytest.mark.parametrize(
    ("table_id", "columns"),
    [("PRBD01N001", BOND_COLUMNS), ("PREF01N001", DOMESTIC_LISTED_COLUMNS)],
)
def test_source_row_helper_builds_every_official_cell_in_order(
    table_id: str, columns: tuple[str, ...]
) -> None:
    row = source_row(table_id)  # type: ignore[arg-type]
    assert tuple(cell.column_name for cell in row.cells) == columns
    assert row.raw_payload == tuple(cell.raw_value for cell in row.cells)


def test_locator_is_built_only_from_exact_row_and_cell_lineage() -> None:
    row = source_row(
        "PRBD01N001",
        {"PD_NO": "XS0000000001"},
        excel_row=19,
        applicable_dates={"PD_NO": date(2026, 7, 10)},
    )
    locator = SourceCellLocator.from_row(row, "PD_NO")
    assert locator.source_table == "PRBD01N001"
    assert locator.source_file.as_posix() == "data/PRBD01N001_fixture.xlsx"
    assert locator.source_sheet == "datarows"
    assert locator.source_row_number == 19
    assert locator.source_column_name == "PD_NO"
    assert locator.source_column_number == 1
    assert locator.source_column_letter == "A"
    assert locator.source_checksum == "a" * 64
    assert locator.source_snapshot_date == date(2026, 7, 11)
    assert locator.source_applicable_date == date(2026, 7, 10)
    with pytest.raises(KeyError, match="pd_no"):
        SourceCellLocator.from_row(row, "pd_no")
```

- [ ] **Step 3: Run Step 2 and confirm the expected RED**

Run:

```bash
uv run pytest tests/unit/domain/test_normalization_contracts.py -q
```

Expected: collection fails with `ModuleNotFoundError` for `finproof.domain.locators` or `finproof.domain.quality`; no production contract exists yet. A failure in `source_row()` itself means the fixture is incomplete and must be corrected before production code is added.

- [ ] **Step 4: Implement the exact enums and locator, then rerun to GREEN**

Implement frozen strict Pydantic models. Every model created in `locators.py`, `values.py`, `quality.py`, and `normalization.py` must declare `ConfigDict(frozen=True, extra="forbid", strict=True)`; do not inherit an implicit non-strict default. `SourceCellLocator.from_row` must call `row.cell(column_name)` and copy every value; it must not accept any locator field as an argument:

```python
class SourceCellLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_table: str
    source_file: PurePosixPath
    source_sheet: str
    source_row_number: int = Field(gt=0)
    source_column_name: str
    source_column_number: int = Field(gt=0)
    source_column_letter: str
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_date: date
    source_applicable_date: date | None

    @classmethod
    def from_row(cls, row: SourceRow, column_name: str) -> SourceCellLocator:
        cell = row.cell(column_name)
        return cls(
            source_table=row.source_table,
            source_file=row.source_file,
            source_sheet=row.source_sheet,
            source_row_number=row.source_row_number,
            source_column_name=cell.column_name,
            source_column_number=cell.excel_column_number,
            source_column_letter=cell.excel_column_letter,
            source_checksum=row.source_checksum,
            source_snapshot_date=row.source_snapshot_date,
            source_applicable_date=cell.applicable_date,
        )
```

Run:

```bash
uv run pytest tests/unit/domain/test_normalization_contracts.py -q
```

Expected: the three Step 2 tests pass.

- [ ] **Step 5: Write failing wrapper, issue-hash, immutability, and result-invariant tests**

Append these exact behaviors to `test_normalization_contracts.py`:

```python
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from finproof.domain.normalization import NormalizationResult
from finproof.domain.quality import DataQualityIssue
from finproof.domain.values import DerivedValue, NormalizedValue


@pytest.mark.parametrize(
    "model",
    [SourceCellLocator, NormalizedValue, DerivedValue, DataQualityIssue, NormalizationResult],
)
def test_new_normalization_contracts_enable_frozen_forbid_and_strict(
    model: type[BaseModel],
) -> None:
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["strict"] is True


def test_normalized_and_derived_values_are_frozen_and_reject_empty_rules() -> None:
    row = source_row("PRBD01N001", {"BUY_YIELD": " 3.50 "})
    value = NormalizedValue[Decimal](
        raw_value=" 3.50 ", normalized_value=Decimal("3.50"),
        quality_status=QualityStatus.VALID, rule_id="bond.buy_yield",
        rule_version="1.0.0", source=SourceCellLocator.from_row(row, "BUY_YIELD"),
    )
    derived = DerivedValue[int](
        value=9, quality_status=QualityStatus.VALID,
        rule_id="bond.remaining_days_at_as_of", rule_version="1.0.0",
        as_of_date=date(2026, 7, 11),
        inputs=(SourceCellLocator.from_row(row, "MAT_DT"),),
    )
    assert value.raw_value == " 3.50 "
    assert derived.inputs[0].source_column_name == "MAT_DT"
    with pytest.raises(ValidationError):
        value.raw_value = "3.50"
    with pytest.raises(ValidationError, match="at least 1 character"):
        DerivedValue[int](
            value=9, quality_status=QualityStatus.VALID, rule_id="",
            rule_version="1.0.0", as_of_date=date(2026, 7, 11),
            inputs=(SourceCellLocator.from_row(row, "MAT_DT"),),
        )


def test_quality_issue_is_deterministic_clock_free_and_payload_safe() -> None:
    row = source_row("PREF01N001", {"pd_itm_no": "KR"}, excel_row=1155)
    kwargs = {
        "rule_id": "domestic_listed.product_id",
        "rule_version": "1.0.0",
        "severity": IssueSeverity.BLOCKER,
        "quality_status": QualityStatus.MALFORMED_SOURCE_ROW,
        "reason": "domestic listed product identifier is malformed",
        "quarantined": True,
    }
    first = DataQualityIssue.from_row(row, "pd_itm_no", **kwargs)
    second = DataQualityIssue.from_row(row, "pd_itm_no", **kwargs)
    expected_payload_hash = hashlib.sha256("\0".join(row.raw_payload).encode("utf-8")).hexdigest()
    assert first == second
    assert first.issue_id == first.issue_id.lower()
    assert len(first.issue_id) == 64
    assert first.raw_payload_sha256 == expected_payload_hash
    assert first.first_detected_at is None
    assert "KR" not in first.reason
    assert "/Users/" not in first.reason


def test_persisted_issue_timestamp_must_be_timezone_aware() -> None:
    row = source_row("PREF01N001", {"pd_itm_no": "KR"})
    issue = DataQualityIssue.from_row(
        row, "pd_itm_no", rule_id="domestic_listed.product_id",
        rule_version="1.0.0", severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason="domestic listed product identifier is malformed", quarantined=True,
    )
    with pytest.raises(ValidationError, match="timezone-aware"):
        DataQualityIssue.model_validate(
            issue.model_dump() | {"first_detected_at": datetime(2026, 7, 11, 9, 0)}
        )
    persisted = DataQualityIssue.model_validate(
        issue.model_dump()
        | {"first_detected_at": datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)}
    )
    assert persisted.first_detected_at is not None


def test_normalization_result_enforces_quarantine_equivalence() -> None:
    row = source_row("PREF01N001", {"pd_itm_no": "KR"})
    blocker = DataQualityIssue.from_row(
        row, "pd_itm_no", rule_id="domestic_listed.product_id",
        rule_version="1.0.0", severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason="domestic listed product identifier is malformed", quarantined=True,
    )
    warning = DataQualityIssue.from_row(
        row, "pd_curr_cd", rule_id="domestic_listed.currency",
        rule_version="1.0.0", severity=IssueSeverity.WARNING,
        quality_status=QualityStatus.OUT_OF_DOMAIN,
        reason="domestic listed currency code is unregistered", quarantined=False,
    )
    assert NormalizationResult[str](record=None, issues=(blocker,)).record is None
    assert NormalizationResult[str](record="record", issues=(warning,)).record == "record"
    with pytest.raises(ValidationError, match="quarantined issue"):
        NormalizationResult[str](record=None, issues=())
    with pytest.raises(ValidationError, match="record cannot contain"):
        NormalizationResult[str](record="record", issues=(blocker,))
```

- [ ] **Step 6: Run Step 5 and confirm RED, then implement the smallest contracts**

Run:

```bash
uv run pytest tests/unit/domain/test_normalization_contracts.py -q
```

Expected: collection fails for missing `NormalizedValue`, `DerivedValue`, `DataQualityIssue`, or `NormalizationResult`.

Implement the exact fields from the approved design. Use `Annotated[str, StringConstraints(min_length=1)]` for rule IDs/versions. `DataQualityIssue.issue_id` is SHA-256 over the UTF-8 NUL-separated sequence below, and `raw_payload_sha256` is SHA-256 over `"\0".join(row.raw_payload).encode("utf-8")`:

```text
rule_id, rule_version, source_table, source_file.as_posix(), source_sheet,
source_row_number, source_column_name, source_column_number, source_column_letter,
source_checksum, source_snapshot_date.isoformat(),
source_applicable_date.isoformat() or ""
```

`DataQualityIssue.from_row` always supplies `first_detected_at=None`. The model accepts a non-`None` value only when `utcoffset()` is non-`None`. Add `NormalizationContractError` to `core/errors.py` with fixed expected/actual table text and no row payload.

- [ ] **Step 7: Run focused quality gates and refactor only while green**

Run:

```bash
uv run pytest tests/unit/domain/test_normalization_contracts.py tests/unit/domain/test_source.py -q
uv run ruff format --check src/finproof/domain src/finproof/core/errors.py tests/helpers/source_rows.py tests/unit/domain
uv run ruff check src/finproof/domain src/finproof/core/errors.py tests/helpers/source_rows.py tests/unit/domain
uv run mypy src/finproof/domain src/finproof/core/errors.py tests/helpers/source_rows.py tests/unit/domain
```

Expected: all commands pass; existing Task 2 source models remain unchanged.

- [ ] **Step 8: Commit the shared-contract checkpoint**

```bash
git add src/finproof/core/errors.py src/finproof/domain tests/helpers/source_rows.py tests/unit/domain
git commit -m "feat: add normalization quality contracts"
```

- [ ] **Step 9: Complete the independent Task 1 review before Task 2**

Have a fresh reviewer inspect `HEAD^..HEAD` against Task 1, with special attention to caller-invented locators, mutable nested state, empty rule IDs, clock use, safe issue text, hash determinism, and both directions of the quarantine invariant. Do not begin Task 2 until no Critical or Important finding remains. Any behavioral correction starts with a focused regression in `test_normalization_contracts.py`, demonstrates RED, makes the smallest implementation change, reruns Step 7, and receives a separate review-fix commit.

---

### Task 2: Add shared pure text, identifier, temporal, decimal, and integer parsers

**Files:**

- Create: `src/finproof/data/normalization/__init__.py`
- Create: `src/finproof/data/normalization/value_factory.py`
- Create: `src/finproof/data/normalization/text.py`
- Create: `src/finproof/data/normalization/temporal.py`
- Create: `src/finproof/data/normalization/numeric.py`
- Create: `tests/unit/data/normalization/__init__.py`
- Create: `tests/unit/data/normalization/test_text_parsers.py`
- Create: `tests/unit/data/normalization/test_temporal_parsers.py`
- Create: `tests/unit/data/normalization/test_numeric_parsers.py`

**Interfaces:**

- Consumes: `SourceRow`, `SourceCellLocator.from_row`, `NormalizedValue[T]`, and `QualityStatus` from Task 1.
- Produces: `make_normalized_value(row: SourceRow, column_name: str, *, normalized_value: T | None, quality_status: QualityStatus, rule_id: str, rule_version: str) -> NormalizedValue[T]` in `value_factory.py`.
- Produces: `parse_text(row: SourceRow, column_name: str, *, rule_id: str, rule_version: str) -> NormalizedValue[str]`.
- Produces: `parse_identifier(row: SourceRow, column_name: str, *, rule_id: str, rule_version: str) -> NormalizedValue[str]`; identifiers are exactly 12 uppercase ASCII alphanumeric characters and are never trimmed or case-folded.
- Produces: `parse_yyyymmdd(row: SourceRow, column_name: str, *, allow_max_sentinel: bool, rule_id: str, rule_version: str) -> NormalizedValue[date]`.
- Produces: `parse_source_datetime(row: SourceRow, column_name: str, *, rule_id: str, rule_version: str) -> NormalizedValue[datetime]`; returned values are timezone-naive.
- Produces: `NumericZeroStatus = Literal[QualityStatus.RECORDED_ZERO, QualityStatus.RECORDED_ZERO_UNVERIFIED]`.
- Produces: `parse_decimal(row: SourceRow, column_name: str, *, zero_status: NumericZeroStatus, rule_id: str, rule_version: str) -> NormalizedValue[Decimal]`.
- Produces: `parse_integer(row: SourceRow, column_name: str, *, zero_status: NumericZeroStatus, rule_id: str, rule_version: str) -> NormalizedValue[int]`; decimal syntax is accepted only when mathematically integral.
- Emits no issues and performs no I/O. Product normalizers own issue construction and mandatory-field quarantine decisions.

- [ ] **Step 1: Write failing text and identifier parser tests**

Create `test_text_parsers.py`:

```python
import pytest

from finproof.data.normalization.text import parse_identifier, parse_text
from finproof.domain.quality import QualityStatus
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize(
    ("raw", "normalized", "status"),
    [
        ("  채권\u3000", "채권", QualityStatus.VALID),
        ("", None, QualityStatus.MISSING_BLANK),
        (" \t\u3000", None, QualityStatus.MISSING_BLANK),
        ("NULL", "NULL", QualityStatus.VALID),
    ],
)
def test_text_preserves_raw_and_only_trims_normalized_value(
    raw: str, normalized: str | None, status: QualityStatus
) -> None:
    row = source_row("PRBD01N001", {"PD_NM": raw})
    result = parse_text(
        row, "PD_NM", rule_id="bond.name", rule_version="1.0.0"
    )
    assert result.raw_value == raw
    assert result.normalized_value == normalized
    assert result.quality_status is status
    assert result.source == result.source.from_row(row, "PD_NM")


@pytest.mark.parametrize("raw", ["KR0000000001", "XS0000000001", "A1B2C3D4E5F6"])
def test_identifier_accepts_only_exact_uppercase_ascii_shape(raw: str) -> None:
    result = parse_identifier(
        source_row("PRBD01N001", {"PD_NO": raw}), "PD_NO",
        rule_id="bond.product_id", rule_version="1.0.0",
    )
    assert result.normalized_value == raw
    assert result.quality_status is QualityStatus.VALID


@pytest.mark.parametrize(
    "raw", ["", "KR", " KR0000000001", "KR0000000001 ", "kr0000000001", "ＫＲ0000000001"]
)
def test_identifier_rejects_blank_short_padded_lowercase_and_non_ascii(raw: str) -> None:
    result = parse_identifier(
        source_row("PRBD01N001", {"PD_NO": raw}), "PD_NO",
        rule_id="bond.product_id", rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value is None
    assert result.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
```

- [ ] **Step 2: Run the text tests and confirm RED**

Run:

```bash
uv run pytest tests/unit/data/normalization/test_text_parsers.py -q
```

Expected: collection fails because `finproof.data.normalization.text` does not exist.

- [ ] **Step 3: Implement the value factory, text parser, and exact identifier parser**

`make_normalized_value` obtains `raw_value` only from `row.cell(column_name)` and the locator only from `SourceCellLocator.from_row(row, column_name)`. `parse_text` uses `raw.strip()` only for the normalized value. `parse_identifier` applies `re.fullmatch(r"[A-Z0-9]{12}", raw, flags=re.ASCII)` to the exact raw string and never calls `strip()` or `upper()`.

Run:

```bash
uv run pytest tests/unit/data/normalization/test_text_parsers.py -q
```

Expected: all text and identifier tests pass.

- [ ] **Step 4: Write failing strict date and source-datetime tests**

Create `test_temporal_parsers.py`:

```python
from datetime import date, datetime

import pytest

from finproof.data.normalization.temporal import parse_source_datetime, parse_yyyymmdd
from finproof.domain.quality import QualityStatus
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize(
    ("raw", "allow_max", "value", "status"),
    [
        ("", False, None, QualityStatus.MISSING_BLANK),
        (" \t", False, None, QualityStatus.MISSING_BLANK),
        ("0", True, None, QualityStatus.SENTINEL_ZERO),
        ("00000000", False, None, QualityStatus.SENTINEL_ZERO),
        ("99991231", True, None, QualityStatus.SENTINEL_MAX_DATE),
        ("99991231", False, date(9999, 12, 31), QualityStatus.VALID),
        ("20260711", False, date(2026, 7, 11), QualityStatus.VALID),
        ("20260230", False, None, QualityStatus.INVALID_FORMAT),
        ("2026-07-11", False, None, QualityStatus.INVALID_FORMAT),
        ("２０２６０７１１", False, None, QualityStatus.INVALID_FORMAT),
        (" 20260711", False, None, QualityStatus.INVALID_FORMAT),
    ],
)
def test_yyyymmdd_parser_distinguishes_every_date_state(
    raw: str, allow_max: bool, value: date | None, status: QualityStatus
) -> None:
    row = source_row("PRBD01N001", {"MAT_DT": raw})
    result = parse_yyyymmdd(
        row, "MAT_DT", allow_max_sentinel=allow_max,
        rule_id="bond.maturity_date", rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value == value
    assert result.quality_status is status


@pytest.mark.parametrize(
    ("raw", "value", "status"),
    [
        ("", None, QualityStatus.MISSING_BLANK),
        ("2026-07-11 09:30:00", datetime(2026, 7, 11, 9, 30), QualityStatus.VALID),
        ("2026-07-11T09:30:00", None, QualityStatus.INVALID_FORMAT),
        ("2026-07-11 09:30", None, QualityStatus.INVALID_FORMAT),
        ("2026-07-11 09:30:00+09:00", None, QualityStatus.INVALID_FORMAT),
    ],
)
def test_source_datetime_is_exact_and_timezone_naive(
    raw: str, value: datetime | None, status: QualityStatus
) -> None:
    row = source_row("PREF01N001", {"du_upt_dt": raw})
    result = parse_source_datetime(
        row, "du_upt_dt", rule_id="domestic_listed.daily_update_at",
        rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value == value
    assert result.quality_status is status
    if result.normalized_value is not None:
        assert result.normalized_value.tzinfo is None
```

- [ ] **Step 5: Run temporal tests to RED, implement strict parsers, and rerun to GREEN**

Run:

```bash
uv run pytest tests/unit/data/normalization/test_temporal_parsers.py -q
```

Expected: collection fails because `finproof.data.normalization.temporal` does not exist.

Implement ASCII `YYYYMMDD` validation before `datetime.strptime(..., "%Y%m%d").date()`. Only blank/whitespace detection may strip. For nonblank dates, parse the exact raw string. Check zero sentinels before max sentinel; treat `99991231` as a real date when `allow_max_sentinel=False`. Parse `du_upt_dt` only with `datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")` after rejecting leading/trailing whitespace.

Run the same focused command and expect all temporal tests to pass.

- [ ] **Step 6: Write failing Decimal, zero-policy, finite-value, and integral tests**

Create `test_numeric_parsers.py`:

```python
from decimal import Decimal

import pytest

from finproof.data.normalization.numeric import parse_decimal, parse_integer
from finproof.domain.quality import QualityStatus
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize(
    ("raw", "zero_status", "value", "status"),
    [
        ("", QualityStatus.RECORDED_ZERO, None, QualityStatus.MISSING_BLANK),
        (" \t", QualityStatus.RECORDED_ZERO, None, QualityStatus.MISSING_BLANK),
        ("0", QualityStatus.RECORDED_ZERO, Decimal("0"), QualityStatus.RECORDED_ZERO),
        ("-0.00", QualityStatus.RECORDED_ZERO_UNVERIFIED, Decimal("-0.00"), QualityStatus.RECORDED_ZERO_UNVERIFIED),
        ("3.500", QualityStatus.RECORDED_ZERO, Decimal("3.500"), QualityStatus.VALID),
        ("-100", QualityStatus.RECORDED_ZERO, Decimal("-100"), QualityStatus.VALID),
        ("NaN", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
        ("Infinity", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
        ("1,000", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
        (" 3.5", QualityStatus.RECORDED_ZERO, None, QualityStatus.INVALID_FORMAT),
    ],
)
def test_decimal_parser_preserves_exact_finite_values_and_field_zero_status(
    raw: str,
    zero_status: QualityStatus,
    value: Decimal | None,
    status: QualityStatus,
) -> None:
    row = source_row("PREF01N001", {"cu_charge_rt": raw})
    result = parse_decimal(
        row, "cu_charge_rt", zero_status=zero_status,  # type: ignore[arg-type]
        rule_id="domestic_listed.total_fee", rule_version="1.0.0",
    )
    assert result.raw_value == raw
    assert result.normalized_value == value
    assert result.quality_status is status


@pytest.mark.parametrize(
    ("raw", "value", "status"),
    [
        ("12", 12, QualityStatus.VALID),
        ("12.0", 12, QualityStatus.VALID),
        ("0.0", 0, QualityStatus.RECORDED_ZERO),
        ("12.5", None, QualityStatus.INVALID_FORMAT),
        ("NaN", None, QualityStatus.INVALID_FORMAT),
        ("1e2", 100, QualityStatus.VALID),
    ],
)
def test_integer_parser_accepts_decimal_syntax_only_when_integral(
    raw: str, value: int | None, status: QualityStatus
) -> None:
    row = source_row("PRBD01N001", {"REMAINING_DAYS": raw})
    result = parse_integer(
        row, "REMAINING_DAYS", zero_status=QualityStatus.RECORDED_ZERO,
        rule_id="bond.source_remaining_days", rule_version="1.0.0",
    )
    assert result.normalized_value == value
    assert result.quality_status is status
```

- [ ] **Step 7: Run numeric tests to RED, implement the smallest finite Decimal path, and rerun**

Run:

```bash
uv run pytest tests/unit/data/normalization/test_numeric_parsers.py -q
```

Expected: collection fails because `finproof.data.normalization.numeric` does not exist.

For nonblank values, reject leading/trailing whitespace, then construct `Decimal(raw)` inside an `InvalidOperation`/`ValueError` guard and require `value.is_finite()`. Preserve the exact `Decimal` exponent. Compare with `Decimal(0)` for the declared zero state. For integers, require `decimal_value == decimal_value.to_integral_value()` before `int(decimal_value)`. Reject any `zero_status` outside `recorded_zero` and `recorded_zero_unverified` with `ValueError`.

Run the focused test and expect all numeric tests to pass.

- [ ] **Step 8: Run the parser suite and focused static gates**

```bash
uv run pytest tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_temporal_parsers.py tests/unit/data/normalization/test_numeric_parsers.py -q
uv run ruff format --check src/finproof/data/normalization tests/unit/data/normalization
uv run ruff check src/finproof/data/normalization tests/unit/data/normalization
uv run mypy src/finproof/data/normalization tests/unit/data/normalization
```

Expected: all commands pass; parser tests prove exact raw retention, literal `NULL` as ordinary domestic text, every date sentinel, finite Decimal behavior, integral parsing, and both row-level zero statuses.

- [ ] **Step 9: Commit the shared-parser checkpoint**

```bash
git add src/finproof/data/normalization tests/unit/data/normalization
git commit -m "feat: add pure source-row parsers"
```

- [ ] **Step 10: Complete the independent Task 2 review before Task 3**

Have a fresh reviewer inspect `HEAD^..HEAD` for exact raw retention, ASCII/date strictness, NaN/Infinity rejection, integral conversion, accidental `float`, arbitrary locator construction, I/O, and a hidden `constant_metric` assignment. Do not begin Task 3 until no Critical or Important finding remains. Review corrections require a focused RED regression, Step 8 rerun, and a separate review-fix commit.

---

### Task 3: Add the strict immutable rating registry

**Files:**

- Modify: `src/finproof/core/errors.py`
- Create: `src/finproof/registry/__init__.py`
- Create: `src/finproof/registry/rating.py`
- Create: `tests/unit/registry/__init__.py`
- Create: `tests/unit/registry/test_rating_registry.py`

**Interfaces:**

- Consumes: only `config/rating_scale.yaml` through the explicit `RatingRegistry.from_yaml(path: Path)` construction boundary; row normalizers receive an already-built registry.
- Produces: `RatingRegistryConfigurationError` for missing, unreadable, malformed, wrong-version, extra-key, empty missing-token collection, invalid-ordinal, or dangling-alias configuration, without file contents or absolute paths in the message. The configured empty-string token itself remains valid.
- Produces: `RatingNotComparableError` for missing, unrated, or unregistered comparison operands.
- Produces: frozen strict `RatingResolution(raw_value: str, normalized_value: str | None, ordinal: int | None, quality_status: QualityStatus)` with `ConfigDict(frozen=True, extra="forbid", strict=True)`.
- Produces: immutable strict `RatingRegistry.missing_tokens: tuple[str, ...]`, `RatingRegistry.ratings: Mapping[str, int]`, and `RatingRegistry.aliases: Mapping[str, str]`; the public registry also declares `ConfigDict(frozen=True, extra="forbid", strict=True)`.
- Produces: `RatingRegistry.from_yaml(path: Path) -> RatingRegistry`, accepting only version `1.0.0` and the exact top-level keys `version`, `missing_tokens`, `ratings`, and `aliases`.
- Produces: `RatingRegistry.resolve(value: str) -> RatingResolution`; it strips surrounding Unicode whitespace, applies one exact alias, and never infers an unconfigured grade.
- Produces: `RatingRegistry.resolve_agencies(value: str) -> tuple[RatingResolution, ...]`; it splits on commas and resolves every independently trimmed token in source order.
- Produces: `RatingRegistry.compare(left: str, right: str) -> int`; `-1` means left stronger, `0` equal ordinal, and `+1` left weaker.

- [ ] **Step 1: Write failing official-config, canonical, alias, missing, and comparison tests**

Create `tests/unit/registry/test_rating_registry.py`:

```python
from pathlib import Path

import pytest

from finproof.core.errors import RatingNotComparableError
from finproof.domain.quality import QualityStatus
from finproof.registry.rating import RatingRegistry, RatingResolution

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def registry() -> RatingRegistry:
    return RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")


def test_official_rating_registry_resolves_canonical_alias_and_same_ordinal(
    registry: RatingRegistry,
) -> None:
    assert registry.resolve(" AAA ").normalized_value == "AAA"
    alias = registry.resolve(" AA０ ")
    assert alias.normalized_value == "AA0"
    assert alias.ordinal == 3
    assert alias.quality_status is QualityStatus.VALID
    assert registry.compare("AAA", "AA-") == -1
    assert registry.compare("AA-", "AAA") == 1
    assert registry.compare("AA", "AA0") == 0


def test_public_rating_models_are_explicitly_frozen_forbid_and_strict() -> None:
    for model in (RatingResolution, RatingRegistry):
        assert model.model_config["frozen"] is True
        assert model.model_config["extra"] == "forbid"
        assert model.model_config["strict"] is True


@pytest.mark.parametrize("raw", ["", "  ", "NULL", "N/A", "NR", "Not Rated", "무등급"])
def test_missing_or_unrated_grades_never_compare(
    registry: RatingRegistry, raw: str
) -> None:
    resolution = registry.resolve(raw)
    expected = (
        QualityStatus.MISSING_BLANK
        if raw.strip() == ""
        else QualityStatus.MISSING_LITERAL_NULL
    )
    assert resolution.normalized_value is None
    assert resolution.ordinal is None
    assert resolution.quality_status is expected
    with pytest.raises(RatingNotComparableError, match="not comparable"):
        registry.compare(raw, "AA-")


@pytest.mark.parametrize("raw", ["C0", "CC0", "AA1", "aaa"])
def test_unregistered_grades_stay_out_of_domain_and_noncomparable(
    registry: RatingRegistry, raw: str
) -> None:
    resolution = registry.resolve(raw)
    assert resolution.raw_value == raw
    assert resolution.normalized_value is None
    assert resolution.ordinal is None
    assert resolution.quality_status is QualityStatus.OUT_OF_DOMAIN
    with pytest.raises(RatingNotComparableError, match="not comparable"):
        registry.compare(raw, "AA-")


def test_agency_tokens_are_resolved_independently_in_source_order(
    registry: RatingRegistry,
) -> None:
    resolutions = registry.resolve_agencies(" AA, AA0 , C0, NR ")
    assert tuple(item.normalized_value for item in resolutions) == (
        "AA", "AA0", None, None,
    )
    assert tuple(item.quality_status for item in resolutions) == (
        QualityStatus.VALID, QualityStatus.VALID,
        QualityStatus.OUT_OF_DOMAIN, QualityStatus.MISSING_LITERAL_NULL,
    )
```

- [ ] **Step 2: Run Step 1 and confirm RED**

Run:

```bash
uv run pytest tests/unit/registry/test_rating_registry.py -q
```

Expected: collection fails because `finproof.registry.rating` and the typed rating errors do not exist.

- [ ] **Step 3: Implement the strict loader, immutable mappings, resolver, and compare semantics**

Validate the direct `yaml.safe_load` result through this explicit raw model before constructing the public registry:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class _RatingConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    version: Literal["1.0.0"]
    missing_tokens: list[StrictStr]
    ratings: dict[StrictStr, StrictInt]
    aliases: dict[StrictStr, StrictStr]
```

The raw model intentionally uses `list[StrictStr]` because YAML sequences load as Python lists; after strict validation, explicitly copy them into the public `tuple[str, ...]`. `StrictInt` must reject booleans and strings such as `"1"`; validators then require positive ordinals, a nonempty unique missing-token list (the configured empty-string member is valid), nonempty rating keys, and aliases whose nonempty targets are canonical keys. Reject alias keys that collide with canonical keys or missing tokens. Construct `RatingResolution` and `RatingRegistry` only with already-typed values and give both public models `ConfigDict(frozen=True, extra="forbid", strict=True)`. Freeze mappings with `MappingProxyType(dict(value))` after copying; never call non-strict `model_validate` to coerce raw YAML.

Catch `OSError`, `yaml.YAMLError`, and Pydantic `ValidationError`, then raise `RatingRegistryConfigurationError` with a fixed category and at most `path.name`; never include YAML content or `path.resolve()`. `compare` resolves both operands and raises `RatingNotComparableError` unless both ordinals are present.

Run:

```bash
uv run pytest tests/unit/registry/test_rating_registry.py -q
```

Expected: all Step 1 tests pass.

- [ ] **Step 4: Write failing immutability and malformed-YAML/version tests**

Append these tests:

```python
from collections.abc import Mapping

import yaml

from finproof.core.errors import RatingRegistryConfigurationError


def _write_rating_yaml(path: Path, document: Mapping[str, object]) -> None:
    path.write_text(yaml.safe_dump(dict(document), allow_unicode=True), encoding="utf-8")


def test_registry_state_is_deeply_immutable(registry: RatingRegistry) -> None:
    with pytest.raises(TypeError):
        registry.ratings["AAA"] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        registry.aliases["AA０"] = "AAA"  # type: ignore[index]
    with pytest.raises(AttributeError):
        registry.missing_tokens.append("UNKNOWN")  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("document", "category"),
    [
        ({"version": "2.0.0", "missing_tokens": [""], "ratings": {"AAA": 1}, "aliases": {}}, "version"),
        ({"version": "1.0.0", "missing_tokens": [], "ratings": {"AAA": 1}, "aliases": {}}, "missing"),
        ({"version": "1.0.0", "missing_tokens": [""], "ratings": {"AAA": 0}, "aliases": {}}, "ordinal"),
        ({"version": "1.0.0", "missing_tokens": [""], "ratings": {"AAA": True}, "aliases": {}}, "ordinal"),
        ({"version": "1.0.0", "missing_tokens": [""], "ratings": {"AAA": "1"}, "aliases": {}}, "ordinal"),
        ({"version": "1.0.0", "missing_tokens": [""], "ratings": {"AAA": 1}, "aliases": {"AA０": "AA0"}}, "alias"),
        ({"version": "1.0.0", "missing_tokens": [""], "ratings": {"AAA": 1}, "aliases": {}, "extra": 1}, "configuration"),
    ],
)
def test_registry_rejects_wrong_version_and_malformed_contracts(
    tmp_path: Path, document: Mapping[str, object], category: str
) -> None:
    path = tmp_path / "rating.yaml"
    _write_rating_yaml(path, document)
    with pytest.raises(RatingRegistryConfigurationError, match=category) as captured:
        RatingRegistry.from_yaml(path)
    assert str(tmp_path) not in str(captured.value)


def test_registry_wraps_yaml_syntax_error_without_file_content(tmp_path: Path) -> None:
    path = tmp_path / "rating.yaml"
    path.write_text("ratings: [unclosed", encoding="utf-8")
    with pytest.raises(RatingRegistryConfigurationError, match="configuration") as captured:
        RatingRegistry.from_yaml(path)
    assert "unclosed" not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)
```

- [ ] **Step 5: Run Step 4 to RED, harden the loader, then rerun to GREEN**

Run:

```bash
uv run pytest tests/unit/registry/test_rating_registry.py -q
```

Expected: at least the wrong-version, deep-immutability, strict-ordinal, dangling-alias, extra-key, or safe-error assertions fail against the minimal Step 3 implementation. Preserve the observed failure in the work log.

Implement only the missing strictness, then rerun the same command. Expected: all rating tests pass, including official `C0`/`CC0` non-comparability.

- [ ] **Step 6: Run focused rating and static gates**

```bash
uv run pytest tests/unit/registry/test_rating_registry.py tests/unit/data/normalization -q
uv run ruff format --check src/finproof/registry src/finproof/core/errors.py tests/unit/registry
uv run ruff check src/finproof/registry src/finproof/core/errors.py tests/unit/registry
uv run mypy src/finproof/registry src/finproof/core/errors.py tests/unit/registry
```

Expected: all commands pass and the parser suite remains green.

- [ ] **Step 7: Commit the rating-registry checkpoint**

```bash
git add src/finproof/core/errors.py src/finproof/registry tests/unit/registry
git commit -m "feat: add strict rating registry"
```

- [ ] **Step 8: Complete the independent Task 3 review before Task 4**

Have a fresh reviewer inspect `HEAD^..HEAD` for YAML coercion, unsupported versions, mutable mappings, missing-token comparison, alias inference, same-ordinal comparison, `C0`/`CC0`, error-content leakage, and hidden filesystem work after registry construction. Do not begin Task 4 until no Critical or Important finding remains. Review corrections require a focused RED regression, Step 6 rerun, and a separate review-fix commit.

---

### Task 4: Add the domestic bond product model and normalizer

**Files:**

- Create: `src/finproof/domain/bonds.py`
- Create: `src/finproof/data/normalization/bonds.py`
- Create: `tests/unit/data/normalization/test_bonds.py`

**Interfaces:**

- Consumes: only `row: SourceRow`, explicit `as_of: date`, an already-loaded `rating_registry: RatingRegistry`, Task 1 contracts, and Task 2 pure parsers.
- Produces: frozen strict `BondInstrument` with native grain literal `instrument` and the exact wrapped fields below.
- Produces: `normalize_bond(row: SourceRow, as_of: date, rating_registry: RatingRegistry) -> NormalizationResult[BondInstrument]`.
- Raises: `NormalizationContractError(expected_table="PRBD01N001", actual_table=row.source_table)` only for a wrong table; bad rows in `PRBD01N001` become deterministic results/issues.
- Quarantines: malformed `PD_NO` with a blocker `malformed_source_row` issue. Missing or invalid optional values do not quarantine.
- Emits: warning issues for `invalid_format`, `out_of_domain`, `mixed_source_values`, and positive quantity on a matured bond; expected missing values and date sentinels emit no issue.
- Preserves: no rating agency value backfills `CRD_GRD`; comparable agency ordinal disagreement uses `mixed_source_values`; `AA` and `AA0` are not a disagreement; unregistered `C0`/`CC0` remain out-of-domain.
- Checkpoint rule: Task 4 has one commit only after every Step 1-10 test/gate is green. No independently callable committed `normalize_bond` may contain placeholder/unresolved derived values, provisional currency/rating behavior, or another intentionally incomplete state; intermediate RED/GREEN edits remain uncommitted inside Task 4.

- [ ] **Step 1: Write the failing bond model, table contract, valid happy path, and quarantine tests**

Create `tests/unit/data/normalization/test_bonds.py`:

```python
from datetime import date
from pathlib import Path

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.bonds import normalize_bond
from finproof.domain.bonds import BondInstrument
from finproof.domain.quality import IssueSeverity, QualityStatus
from finproof.registry.rating import RatingRegistry
from tests.helpers.source_rows import source_row

ROOT = Path(__file__).resolve().parents[4]
AS_OF = date(2026, 7, 11)


@pytest.fixture(scope="module")
def rating_registry() -> RatingRegistry:
    return RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")


def test_bond_rejects_wrong_source_table_as_programmer_error(
    rating_registry: RatingRegistry,
) -> None:
    row = source_row("PREF01N001")
    with pytest.raises(NormalizationContractError, match="PRBD01N001"):
        normalize_bond(row, AS_OF, rating_registry)


def test_bond_model_is_explicitly_frozen_forbid_and_strict() -> None:
    assert BondInstrument.model_config["frozen"] is True
    assert BondInstrument.model_config["extra"] == "forbid"
    assert BondInstrument.model_config["strict"] is True


@pytest.mark.parametrize("product_id", ["KR0000000001", "XS0000000001"])
def test_bond_accepts_observed_kr_and_xs_identifier_shapes(
    product_id: str, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"PD_NO": product_id}), AS_OF, rating_registry
    )
    assert result.record is not None
    assert result.record.grain == "instrument"
    assert result.record.product_id.normalized_value == product_id
    assert not any(issue.quarantined for issue in result.issues)


def test_valid_bond_maps_every_declared_source_column(
    rating_registry: RatingRegistry,
) -> None:
    values = {
        "PD_NO": "KR0000000001", "PD_NM": "채권명", "PD_ABRV_NM": "단축명",
        "CURR_CD": "KRW", "BD_KND": "회사채", "ISU_DT": "20200101",
        "MAT_DT": "20270711", "PD_STD_INFO_UPDATE": "20260710",
        "SRFC_IRT": "1.1", "BUY_YIELD": "2.2", "BUYABLE_QUANTITY": "3",
        "REMAINING_DAYS": "365", "CRD_GRD": "AA0",
        "PD_EVCO_CRD_GRD": "AA", "CRD_GRD_DT": "20260709", "DUR": "4.4",
        "EVAL_PRICE": "10000",
    }
    columns = {
        "product_id": "PD_NO", "name": "PD_NM", "short_name": "PD_ABRV_NM",
        "currency": "CURR_CD", "bond_kind_raw": "BD_KND", "issue_date": "ISU_DT",
        "maturity_date": "MAT_DT", "source_update_date": "PD_STD_INFO_UPDATE",
        "coupon_rate": "SRFC_IRT", "buy_yield": "BUY_YIELD",
        "buyable_quantity": "BUYABLE_QUANTITY", "source_remaining_days": "REMAINING_DAYS",
        "credit_rating": "CRD_GRD", "credit_rating_agencies_raw": "PD_EVCO_CRD_GRD",
        "credit_rating_date": "CRD_GRD_DT", "duration": "DUR",
        "evaluation_price": "EVAL_PRICE",
    }
    row = source_row("PRBD01N001", values)
    record = normalize_bond(row, AS_OF, rating_registry).record
    assert record is not None
    for attribute, column in columns.items():
        wrapped = getattr(record, attribute)
        assert wrapped.raw_value == values[column]
        assert wrapped.source.source_column_name == column
    assert record.currency.normalized_value == "KRW"
    assert record.credit_rating.normalized_value == "AA0"
    assert record.remaining_days_at_as_of.value == 365
    assert record.is_matured_at_as_of.value is False
    assert record.has_positive_buyable_quantity.value is True
    assert record.is_buyable_validated_at_as_of.value is True
    assert tuple(
        locator.source_column_name
        for locator in record.is_buyable_validated_at_as_of.inputs
    ) == ("BUYABLE_QUANTITY", "MAT_DT")


@pytest.mark.parametrize("product_id", ["", "KR", " kr0000000001", "KR0000000001 "])
def test_malformed_bond_identifier_quarantines_with_safe_blocker(
    product_id: str, rating_registry: RatingRegistry
) -> None:
    row = source_row("PRBD01N001", {"PD_NO": product_id}, excel_row=77)
    result = normalize_bond(row, AS_OF, rating_registry)
    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.quarantined is True
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.source.source_row_number == 77
    assert issue.source.source_column_name == "PD_NO"
    if product_id:
        assert product_id not in issue.reason
```

- [ ] **Step 2: Run Step 1 and confirm RED**

Run:

```bash
uv run pytest tests/unit/data/normalization/test_bonds.py -q
```

Expected: collection fails because `finproof.domain.bonds` or `finproof.data.normalization.bonds` does not exist.

- [ ] **Step 3: Implement the frozen `BondInstrument` fields and Step 1 tested happy path**

Define these exact types; do not use a dynamic field/metric dictionary:

```python
class BondInstrument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["instrument"] = "instrument"
    product_id: NormalizedValue[str]
    name: NormalizedValue[str]
    short_name: NormalizedValue[str]
    currency: NormalizedValue[str]
    bond_kind_raw: NormalizedValue[str]
    issue_date: NormalizedValue[date]
    maturity_date: NormalizedValue[date]
    source_update_date: NormalizedValue[date]
    coupon_rate: NormalizedValue[Decimal]
    buy_yield: NormalizedValue[Decimal]
    buyable_quantity: NormalizedValue[Decimal]
    source_remaining_days: NormalizedValue[int]
    credit_rating: NormalizedValue[str]
    credit_rating_agencies_raw: NormalizedValue[str]
    credit_rating_date: NormalizedValue[date]
    duration: NormalizedValue[Decimal]
    evaluation_price: NormalizedValue[Decimal]
    remaining_days_at_as_of: DerivedValue[int]
    is_matured_at_as_of: DerivedValue[bool]
    has_positive_buyable_quantity: DerivedValue[bool]
    is_buyable_validated_at_as_of: DerivedValue[bool]
```

Check `row.source_table` before any cell lookup. For malformed `PD_NO`, return immediately with one fixed-reason blocker issue and no record. For a valid ID, construct every field from its declared source column, even when blank. Implement the Step 1 valid-default happy path now: exact `KRW` currency, configured `AA0` primary rating, 365 derived remaining days, not matured, positive quantity, and validated buyability with the exact quantity/maturity input locators. Reuse the already-tested shared parsers; every numeric field maps through `Decimal` except `source_remaining_days: int`. Do not add placeholder/unresolved values merely to make model construction succeed. The later RED cycles add sentinel/error/boundary/tri-state, out-of-domain currency, and rating-disagreement completeness around this tested happy path.

Run the Step 2 command. Expected: the table, valid-ID, complete field mapping, valid-default derived/state, grain, and quarantine tests pass. Do not commit this partial task; continue through Step 10 before the Task 4 checkpoint.

- [ ] **Step 4: Write failing date-state, source-versus-derived, boundary, and applicable-date tests**

Append:

```python
@pytest.mark.parametrize(
    ("raw", "status"),
    [
        ("", QualityStatus.MISSING_BLANK),
        ("0", QualityStatus.SENTINEL_ZERO),
        ("00000000", QualityStatus.SENTINEL_ZERO),
        ("99991231", QualityStatus.SENTINEL_MAX_DATE),
        ("20260230", QualityStatus.INVALID_FORMAT),
    ],
)
def test_bond_maturity_states_never_become_derived_dates(
    raw: str, status: QualityStatus, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"MAT_DT": raw}), AS_OF, rating_registry
    )
    assert result.record is not None
    assert result.record.maturity_date.raw_value == raw
    assert result.record.maturity_date.normalized_value is None
    assert result.record.maturity_date.quality_status is status
    assert result.record.remaining_days_at_as_of.value is None
    assert result.record.is_matured_at_as_of.value is None
    assert result.record.remaining_days_at_as_of.quality_status is status
    assert any(issue.source.source_column_name == "MAT_DT" for issue in result.issues) is (
        status is QualityStatus.INVALID_FORMAT
    )


def test_bond_recalculates_remaining_days_without_overwriting_source_value(
    rating_registry: RatingRegistry,
) -> None:
    row = source_row(
        "PRBD01N001", {"MAT_DT": "20260720", "REMAINING_DAYS": "999"},
        applicable_dates={"MAT_DT": date(2026, 7, 10)},
    )
    record = normalize_bond(row, AS_OF, rating_registry).record
    assert record is not None
    assert record.source_remaining_days.raw_value == "999"
    assert record.source_remaining_days.normalized_value == 999
    assert record.remaining_days_at_as_of.value == 9
    assert record.remaining_days_at_as_of.as_of_date == AS_OF
    assert record.remaining_days_at_as_of.inputs == (record.maturity_date.source,)
    assert record.maturity_date.source.source_applicable_date == date(2026, 7, 10)


@pytest.mark.parametrize(
    ("maturity", "remaining", "matured"),
    [
        ("20260710", -1, True),
        ("20260711", 0, False),
        ("20260712", 1, False),
    ],
)
def test_bond_maturity_is_strictly_before_as_of(
    maturity: str, remaining: int, matured: bool, rating_registry: RatingRegistry
) -> None:
    record = normalize_bond(
        source_row("PRBD01N001", {"MAT_DT": maturity}), AS_OF, rating_registry
    ).record
    assert record is not None
    assert record.remaining_days_at_as_of.value == remaining
    assert record.is_matured_at_as_of.value is matured


def test_update_date_is_preserved_without_inferred_applicable_date(
    rating_registry: RatingRegistry,
) -> None:
    row = source_row(
        "PRBD01N001", {"PD_STD_INFO_UPDATE": "20260224", "MAT_DT": "20260720"}
    )
    record = normalize_bond(row, AS_OF, rating_registry).record
    assert record is not None
    assert record.source_update_date.normalized_value == date(2026, 2, 24)
    assert record.source_update_date.source.source_applicable_date is None
    assert record.maturity_date.source.source_applicable_date is None


def test_max_date_sentinel_is_enabled_only_for_bond_maturity(
    rating_registry: RatingRegistry,
) -> None:
    record = normalize_bond(
        source_row(
            "PRBD01N001",
            {
                "ISU_DT": "99991231", "MAT_DT": "99991231",
                "PD_STD_INFO_UPDATE": "99991231", "CRD_GRD_DT": "99991231",
            },
        ),
        AS_OF,
        rating_registry,
    ).record
    assert record is not None
    assert record.maturity_date.normalized_value is None
    assert record.maturity_date.quality_status is QualityStatus.SENTINEL_MAX_DATE
    assert record.issue_date.normalized_value == date(9999, 12, 31)
    assert record.source_update_date.normalized_value == date(9999, 12, 31)
    assert record.credit_rating_date.normalized_value == date(9999, 12, 31)
```

- [ ] **Step 5: Run Step 4 to RED, implement derived maturity values, and rerun**

Run:

```bash
uv run pytest tests/unit/data/normalization/test_bonds.py -q
```

Expected: the new tests fail because derived values are absent, raw `REMAINING_DAYS` is copied into the derivation, sentinel status is collapsed, the as-of boundary uses `<=`, or applicable dates are inferred.

Implement `remaining_days_at_as_of` strictly as `(maturity_date - as_of).days`. Propagate the maturity wrapper's quality state when no valid maturity exists. `is_matured_at_as_of` is `remaining_days < 0`. Both derived values use only the exact `MAT_DT` locator and explicit `as_of`.

Run the same command and expect all date/source-fidelity tests to pass.

- [ ] **Step 6: Write failing quantity/buyability tri-state, zero, currency, and warning tests**

Append:

```python
@pytest.mark.parametrize(
    ("quantity", "maturity", "positive", "buyable"),
    [
        ("1", "20260712", True, True),
        ("0", "20260712", False, False),
        ("-1", "20260712", False, False),
        ("", "20260712", None, None),
        ("bad", "20260712", None, None),
        ("1", "20260710", True, False),
        ("", "20260710", None, False),
        ("0", "", False, False),
        ("1", "", True, None),
    ],
)
def test_bond_buyability_uses_explicit_false_before_unknown(
    quantity: str,
    maturity: str,
    positive: bool | None,
    buyable: bool | None,
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row(
            "PRBD01N001", {"BUYABLE_QUANTITY": quantity, "MAT_DT": maturity}
        ),
        AS_OF,
        rating_registry,
    )
    assert result.record is not None
    assert result.record.has_positive_buyable_quantity.value is positive
    assert result.record.is_buyable_validated_at_as_of.value is buyable
    assert result.record.is_buyable_validated_at_as_of.inputs == (
        result.record.buyable_quantity.source,
        result.record.maturity_date.source,
    )


def test_positive_quantity_on_matured_bond_is_preserved_and_warned(
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"BUYABLE_QUANTITY": "7", "MAT_DT": "20260710"}),
        AS_OF,
        rating_registry,
    )
    assert result.record is not None
    assert result.record.buyable_quantity.normalized_value == 7
    assert result.record.is_buyable_validated_at_as_of.value is False
    assert any(
        issue.rule_id == "bond.matured_positive_quantity"
        and issue.severity is IssueSeverity.WARNING
        and issue.quality_status is QualityStatus.MIXED_SOURCE_VALUES
        and not issue.quarantined
        for issue in result.issues
    )


@pytest.mark.parametrize(
    ("column", "attribute"),
    [
        ("SRFC_IRT", "coupon_rate"), ("BUY_YIELD", "buy_yield"),
        ("BUYABLE_QUANTITY", "buyable_quantity"), ("DUR", "duration"),
        ("EVAL_PRICE", "evaluation_price"),
    ],
)
def test_ordinary_bond_numeric_zero_is_recorded_zero(
    column: str, attribute: str, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {column: "0"}), AS_OF, rating_registry
    )
    assert result.record is not None
    wrapped = getattr(result.record, attribute)
    assert wrapped.normalized_value == 0
    assert wrapped.quality_status is QualityStatus.RECORDED_ZERO


@pytest.mark.parametrize(
    ("raw", "value", "status", "has_warning"),
    [
        ("KRW", "KRW", QualityStatus.VALID, False),
        ("USD", "USD", QualityStatus.VALID, False),
        ("000", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("krw", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("", None, QualityStatus.MISSING_BLANK, False),
    ],
)
def test_bond_currency_requires_exact_uppercase_three_letter_code(
    raw: str,
    value: str | None,
    status: QualityStatus,
    has_warning: bool,
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"CURR_CD": raw}), AS_OF, rating_registry
    )
    assert result.record is not None
    assert result.record.currency.raw_value == raw
    assert result.record.currency.normalized_value == value
    assert result.record.currency.quality_status is status
    assert any(issue.source.source_column_name == "CURR_CD" for issue in result.issues) is has_warning
```

- [ ] **Step 7: Run Step 6 to RED, implement exact buyability precedence and field policies, and rerun**

Run the full bond test file. Expected: tri-state, matured-positive warning, ordinary zero, or exact currency assertions fail before their production rules exist.

Use this buyability order: already-matured valid date -> `False`; valid quantity `<= 0` -> `False`; unavailable/invalid quantity or unavailable/invalid maturity -> `None`; otherwise -> `True`. `has_positive_buyable_quantity` depends only on quantity. Preserve positive source quantity even when matured. Do not infer currency from country/issuer.

Run the same command and expect all quantity/currency tests to pass.

- [ ] **Step 8: Write failing primary/agency rating, missing, unregistered, and no-backfill tests**

Append:

```python
@pytest.mark.parametrize(
    ("primary", "status"),
    [
        ("", QualityStatus.MISSING_BLANK),
        ("NR", QualityStatus.MISSING_LITERAL_NULL),
        ("C0", QualityStatus.OUT_OF_DOMAIN),
        ("CC0", QualityStatus.OUT_OF_DOMAIN),
    ],
)
def test_missing_and_unregistered_primary_ratings_remain_unavailable(
    primary: str, status: QualityStatus, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"CRD_GRD": primary}), AS_OF, rating_registry
    )
    assert result.record is not None
    assert result.record.credit_rating.normalized_value is None
    assert result.record.credit_rating.quality_status is status
    assert any(issue.source.source_column_name == "CRD_GRD" for issue in result.issues) is (
        status is QualityStatus.OUT_OF_DOMAIN
    )


def test_agency_rating_never_backfills_missing_primary(
    rating_registry: RatingRegistry,
) -> None:
    record = normalize_bond(
        source_row("PRBD01N001", {"CRD_GRD": "", "PD_EVCO_CRD_GRD": "AAA"}),
        AS_OF,
        rating_registry,
    ).record
    assert record is not None
    assert record.credit_rating.normalized_value is None
    assert record.credit_rating_agencies_raw.raw_value == "AAA"
    assert record.credit_rating_agencies_raw.normalized_value == "AAA"


@pytest.mark.parametrize(
    ("primary", "agencies", "mixed"),
    [
        ("AA", "AA0, AA", False),
        ("AA", "AA, AA-", True),
        ("AA-", "AA", True),
        ("", "AA, AA-", True),
        ("", "AA, AA0", False),
    ],
)
def test_agency_disagreement_uses_ordinals_and_preserves_primary(
    primary: str,
    agencies: str,
    mixed: bool,
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row(
            "PRBD01N001", {"CRD_GRD": primary, "PD_EVCO_CRD_GRD": agencies}
        ),
        AS_OF,
        rating_registry,
    )
    assert result.record is not None
    assert result.record.credit_rating.raw_value == primary
    assert any(issue.rule_id == "bond.rating_disagreement" for issue in result.issues) is mixed
```

- [ ] **Step 9: Run Step 8 to RED, implement rating wrappers/disagreement, and rerun**

Run the bond test file. Expected: at least `C0`/`CC0`, configured missing-token status, agency normalization, same-ordinal handling, missing-primary no-backfill, or disagreement warnings fail.

Build `credit_rating` from `RatingRegistry.resolve(CRD_GRD)`. Build `credit_rating_agencies_raw` with `parse_text` so the exact comma-separated source remains in `raw_value` and only surrounding whitespace is removed in `normalized_value`; call `resolve_agencies(PD_EVCO_CRD_GRD)` separately for comparison in source order. A disagreement exists only when two or more comparable ordinals across agencies differ, or a comparable primary ordinal differs from a comparable agency ordinal. Missing/unmapped agency tokens produce their own fixed warning only when out-of-domain; they never become the primary grade.

Run the same command and expect the entire bond test file to pass.

- [ ] **Step 10: Run bond, shared-contract, parser, and rating regression gates**

```bash
uv run pytest tests/unit/data/normalization/test_bonds.py tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_temporal_parsers.py tests/unit/data/normalization/test_numeric_parsers.py tests/unit/domain/test_normalization_contracts.py tests/unit/registry/test_rating_registry.py -q
uv run ruff format --check src/finproof/domain/bonds.py src/finproof/data/normalization/bonds.py tests/unit/data/normalization/test_bonds.py
uv run ruff check src/finproof/domain/bonds.py src/finproof/data/normalization/bonds.py tests/unit/data/normalization/test_bonds.py
uv run mypy src/finproof/domain/bonds.py src/finproof/data/normalization/bonds.py tests/unit/data/normalization/test_bonds.py
```

Expected: all commands pass; no test loads an XLSX path or constructs a locator by hand.

- [ ] **Step 11: Commit the domestic-bond checkpoint**

```bash
git add src/finproof/domain/bonds.py src/finproof/data/normalization/bonds.py tests/unit/data/normalization/test_bonds.py
git commit -m "feat: normalize domestic bonds"
```

- [ ] **Step 12: Complete the independent Task 4 review before Task 5**

Have a fresh reviewer inspect `HEAD^..HEAD` for incorrect maturity boundaries, copied `REMAINING_DAYS`, loss of raw values/locators, quantity/maturity tri-state precedence, inferred currencies/ratings, `float`, agency backfill, C0/CC0 inference, issue leakage, and accidental quarantine of optional fields. Do not begin Task 5 until no Critical or Important finding remains. Corrections require a focused RED regression, Step 10 rerun, and a separate review-fix commit.

---

### Task 5: Add the domestic ETF/ETN product model and normalizer

**Files:**

- Create: `src/finproof/domain/domestic_listed.py`
- Create: `src/finproof/data/normalization/domestic_listed.py`
- Create: `tests/unit/data/normalization/test_domestic_listed.py`

**Interfaces:**

- Consumes: only `row: SourceRow`, explicit `as_of: date`, Task 1 contracts, and Task 2 pure parsers. It does not consume a source path, verified descriptor, rating registry, clock, environment, or database.
- Produces: `ListedProductType(StrEnum)` with exact values `ETF` and `ETN`.
- Produces: frozen strict `ListedProduct` with native grain literal `listed_product` and every wrapped field listed in Step 3.
- Produces: `normalize_domestic_listed(row: SourceRow, as_of: date) -> NormalizationResult[ListedProduct]`.
- Raises: `NormalizationContractError(expected_table="PREF01N001", actual_table=row.source_table)` only for a wrong table.
- Quarantines: malformed `pd_itm_no` or `pd_grp_no` other than exact `ETF`/`ETN`, each with a blocker `malformed_source_row` issue. Missing/invalid optional values, flags, dates, currency, and metrics do not quarantine.
- Emits: deterministic nonquarantine warnings for `invalid_format` and `out_of_domain`; declared missing/sentinels/zeroes emit no issue.
- Maps currency: exact `CURR_CD_KRW -> KRW`; blank stays `missing_blank`; `CURR_CD_000`, `KRW`, and every other code are `out_of_domain` with no name-based inference.
- Maps flags: exact `pd_sale_yn="1" -> True`, `"0" -> False`; exact `pd_tr_yn="0" -> False` (not suspended), `"1" -> True`; other/blank values are out-of-domain and typed `None`.
- Produces tri-state `is_eligible_at_as_of`: any explicit disqualifier -> `False`; otherwise an unknown/invalid prerequisite -> `None`; otherwise `True`.
- Checkpoint rule: Task 5 has one commit only after every Step 1-10 test/gate is green. No independently callable committed `normalize_domestic_listed` may contain placeholder/unresolved state, provisional currency handling, or an intentionally wrong zero policy; intermediate RED/GREEN edits remain uncommitted inside Task 5.

- [ ] **Step 1: Write failing table/type, valid state/metric happy path, and quarantine tests**

Create `tests/unit/data/normalization/test_domestic_listed.py`:

```python
from datetime import date, datetime
from decimal import Decimal

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.domain.domestic_listed import ListedProduct, ListedProductType
from finproof.domain.quality import IssueSeverity, QualityStatus
from tests.helpers.source_rows import source_row

AS_OF = date(2026, 7, 11)


def test_domestic_listed_rejects_wrong_source_table_as_programmer_error() -> None:
    with pytest.raises(NormalizationContractError, match="PREF01N001"):
        normalize_domestic_listed(source_row("PRBD01N001"), AS_OF)


def test_domestic_listed_model_is_explicitly_frozen_forbid_and_strict() -> None:
    assert ListedProduct.model_config["frozen"] is True
    assert ListedProduct.model_config["extra"] == "forbid"
    assert ListedProduct.model_config["strict"] is True


@pytest.mark.parametrize(
    ("group", "product_type"),
    [("ETF", ListedProductType.ETF), ("ETN", ListedProductType.ETN)],
)
def test_domestic_listed_keeps_etf_and_etn_distinct(
    group: str, product_type: ListedProductType
) -> None:
    result = normalize_domestic_listed(
        source_row("PREF01N001", {"pd_grp_no": group}), AS_OF
    )
    assert result.record is not None
    assert result.record.grain == "listed_product"
    assert result.record.product_type.normalized_value is product_type


def test_valid_domestic_listed_maps_every_declared_source_column() -> None:
    values = {
        "pd_itm_no": "KR7000000001", "pd_itm_no_ma": "A000001",
        "pd_grp_no": "ETF", "pd_nm": "상품명", "pd_abrv_nm": "단축명",
        "pd_curr_cd": "CURR_CD_KRW", "pd_lstg_dt": "20200101",
        "pd_lste_dt": "99991231", "pd_sale_yn": "1", "pd_tr_yn": "0",
        "pd_net_tamt": "100", "du_last_aum": "90", "cu_charge_rt": "0.1",
        "du_chas_errt": "0.2", "du_diff_rt": "0.3", "du_er_1d": "1",
        "du_er_1m": "2", "du_er_3m": "3", "du_er_6m": "4",
        "du_er_1y": "5", "du_er_ytd": "6", "pd_risk_cd": "2",
        "pd_risk_nm": "위험", "cu_base_index": "지수", "cu_fund_mgmt_co": "운용사",
        "wu_inv_ast_type": "주식", "wu_inv_rgn": "한국", "cu_upt_dt": "20260709",
        "du_upt_dt": "2026-07-10 09:30:00", "wu_upt_dt": "20260708",
    }
    columns = {
        "product_id": "pd_itm_no", "market_identifier": "pd_itm_no_ma",
        "product_type": "pd_grp_no", "name": "pd_nm", "short_name": "pd_abrv_nm",
        "currency": "pd_curr_cd", "listing_date": "pd_lstg_dt",
        "listing_end_date": "pd_lste_dt", "sale_flag": "pd_sale_yn",
        "suspension_flag": "pd_tr_yn", "aum_primary": "pd_net_tamt",
        "aum_secondary": "du_last_aum", "total_fee": "cu_charge_rt",
        "tracking_error": "du_chas_errt", "difference_rate": "du_diff_rt",
        "return_1d": "du_er_1d", "return_1m": "du_er_1m",
        "return_3m": "du_er_3m", "return_6m": "du_er_6m",
        "return_1y": "du_er_1y", "return_ytd": "du_er_ytd",
        "risk_code": "pd_risk_cd", "risk_name": "pd_risk_nm",
        "base_index": "cu_base_index", "manager": "cu_fund_mgmt_co",
        "asset_type": "wu_inv_ast_type", "region": "wu_inv_rgn",
        "custom_update_date": "cu_upt_dt", "daily_update_at": "du_upt_dt",
        "weekly_update_date": "wu_upt_dt",
    }
    row = source_row("PREF01N001", values)
    record = normalize_domestic_listed(row, AS_OF).record
    assert record is not None
    for attribute, column in columns.items():
        wrapped = getattr(record, attribute)
        assert wrapped.raw_value == values[column]
        assert wrapped.source.source_column_name == column
    assert record.currency.normalized_value == "KRW"
    assert record.sale_flag.normalized_value is True
    assert record.suspension_flag.normalized_value is False
    assert record.is_eligible_at_as_of.value is True
    assert record.is_eligible_at_as_of.as_of_date == AS_OF
    assert tuple(
        locator.source_column_name for locator in record.is_eligible_at_as_of.inputs
    ) == ("pd_sale_yn", "pd_tr_yn", "pd_lstg_dt", "pd_lste_dt")


def test_valid_domestic_listed_zero_policy_is_field_specific() -> None:
    record = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "cu_charge_rt": "0", "du_chas_errt": "0", "du_diff_rt": "0",
                "pd_net_tamt": "0", "du_last_aum": "0", "du_er_1d": "0",
                "du_er_1m": "0", "du_er_3m": "0", "du_er_6m": "0",
                "du_er_1y": "0", "du_er_ytd": "0",
            },
        ),
        AS_OF,
    ).record
    assert record is not None
    assert record.total_fee.quality_status is QualityStatus.RECORDED_ZERO_UNVERIFIED
    assert record.tracking_error.quality_status is QualityStatus.RECORDED_ZERO
    assert record.difference_rate.quality_status is QualityStatus.RECORDED_ZERO
    ordinary_zeroes = (
        record.aum_primary, record.aum_secondary, record.tracking_error,
        record.difference_rate, record.return_1d, record.return_1m,
        record.return_3m, record.return_6m, record.return_1y, record.return_ytd,
    )
    assert all(
        wrapped.quality_status is QualityStatus.RECORDED_ZERO
        for wrapped in ordinary_zeroes
    )
    assert all(
        wrapped.quality_status is not QualityStatus.CONSTANT_METRIC
        for wrapped in (record.total_fee, *ordinary_zeroes)
    )


def test_domestic_primary_aum_is_never_backfilled_from_secondary() -> None:
    record = normalize_domestic_listed(
        source_row(
            "PREF01N001", {"pd_net_tamt": "", "du_last_aum": "123.45"}
        ),
        AS_OF,
    ).record
    assert record is not None
    assert record.aum_primary.raw_value == ""
    assert record.aum_primary.normalized_value is None
    assert record.aum_primary.quality_status is QualityStatus.MISSING_BLANK
    assert record.aum_secondary.normalized_value == Decimal("123.45")


@pytest.mark.parametrize(
    ("values", "column"),
    [
        ({"pd_itm_no": "KR"}, "pd_itm_no"),
        ({"pd_itm_no": " kr7000000001"}, "pd_itm_no"),
        ({"pd_grp_no": "etf"}, "pd_grp_no"),
        ({"pd_grp_no": "FUND"}, "pd_grp_no"),
        ({"pd_grp_no": ""}, "pd_grp_no"),
    ],
)
def test_malformed_listed_identity_or_type_quarantines_one_row(
    values: dict[str, str], column: str
) -> None:
    row = source_row("PREF01N001", values, excel_row=1155)
    result = normalize_domestic_listed(row, AS_OF)
    assert result.record is None
    assert any(
        issue.quarantined
        and issue.severity is IssueSeverity.BLOCKER
        and issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
        and issue.source.source_column_name == column
        and issue.source.source_row_number == 1155
        for issue in result.issues
    )
    assert all(
        value not in issue.reason
        for value in values.values()
        if value
        for issue in result.issues
    )
```

- [ ] **Step 2: Run Step 1 and confirm RED**

Run:

```bash
uv run pytest tests/unit/data/normalization/test_domestic_listed.py -q
```

Expected: collection fails because `finproof.domain.domestic_listed` or `finproof.data.normalization.domestic_listed` does not exist.

- [ ] **Step 3: Implement the frozen `ListedProduct` fields and Step 1 tested happy path**

Define exact fields rather than a metrics dictionary:

```python
class ListedProduct(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["listed_product"] = "listed_product"
    product_id: NormalizedValue[str]
    market_identifier: NormalizedValue[str]
    product_type: NormalizedValue[ListedProductType]
    name: NormalizedValue[str]
    short_name: NormalizedValue[str]
    currency: NormalizedValue[str]
    listing_date: NormalizedValue[date]
    listing_end_date: NormalizedValue[date]
    sale_flag: NormalizedValue[bool]
    suspension_flag: NormalizedValue[bool]
    aum_primary: NormalizedValue[Decimal]
    aum_secondary: NormalizedValue[Decimal]
    total_fee: NormalizedValue[Decimal]
    tracking_error: NormalizedValue[Decimal]
    difference_rate: NormalizedValue[Decimal]
    return_1d: NormalizedValue[Decimal]
    return_1m: NormalizedValue[Decimal]
    return_3m: NormalizedValue[Decimal]
    return_6m: NormalizedValue[Decimal]
    return_1y: NormalizedValue[Decimal]
    return_ytd: NormalizedValue[Decimal]
    risk_code: NormalizedValue[str]
    risk_name: NormalizedValue[str]
    base_index: NormalizedValue[str]
    manager: NormalizedValue[str]
    asset_type: NormalizedValue[str]
    region: NormalizedValue[str]
    custom_update_date: NormalizedValue[date]
    daily_update_at: NormalizedValue[datetime]
    weekly_update_date: NormalizedValue[date]
    is_eligible_at_as_of: DerivedValue[bool]
```

Check the table before cell lookup. Parse `pd_itm_no` with the exact identifier parser. Parse `pd_grp_no` without trimming/case conversion. If both identity and type are malformed, emit two deterministic blocker issues in source-column order and return no record. For a valid identity/type, populate every field from its declared column, even when blank, using the shared parser appropriate to its declared type. Implement the Step 1 valid-default happy path now: `CURR_CD_KRW -> KRW`, sale enabled, not suspended, open-ended listing, and eligible at `AS_OF` with the exact four state/date input locators. Implement the exact field-specific zero policy asserted by Step 1 before any zero-policy production code: `recorded_zero_unverified` for `cu_charge_rt`, `recorded_zero` for tracking/difference and every ordinary amount/return field, and never row-level `constant_metric`. Do not introduce a provisional alternative merely to create a later RED; later cycles cover invalid/unknown/boundary states and currency/error edges.

Run the Step 2 command. Expected: all table/type/quarantine, complete field mapping, valid-default state/eligibility, and metric-policy tests pass. Do not commit this partial task; continue through Step 10 before the Task 5 checkpoint.

- [ ] **Step 4: Write failing exact flag and eligibility truth-table tests**

Append:

```python
@pytest.mark.parametrize(
    ("sale", "suspended", "expected_sale", "expected_suspended"),
    [
        ("1", "0", True, False),
        ("0", "1", False, True),
        ("", "", None, None),
        ("Y", "N", None, None),
        ("true", "false", None, None),
    ],
)
def test_domestic_flags_use_only_exact_source_codes(
    sale: str,
    suspended: str,
    expected_sale: bool | None,
    expected_suspended: bool | None,
) -> None:
    result = normalize_domestic_listed(
        source_row("PREF01N001", {"pd_sale_yn": sale, "pd_tr_yn": suspended}),
        AS_OF,
    )
    assert result.record is not None
    assert result.record.sale_flag.normalized_value is expected_sale
    assert result.record.suspension_flag.normalized_value is expected_suspended
    expected_warnings = sum(value is None for value in (expected_sale, expected_suspended))
    assert sum(
        issue.source.source_column_name in {"pd_sale_yn", "pd_tr_yn"}
        for issue in result.issues
    ) == expected_warnings


@pytest.mark.parametrize(
    ("sale", "suspended", "start", "end", "eligible"),
    [
        ("1", "0", "20260711", "20260711", True),
        ("1", "0", "20200101", "99991231", True),
        ("1", "0", "20200101", "", True),
        ("0", "0", "", "bad", False),
        ("1", "1", "", "bad", False),
        ("0", "", "", "bad", False),
        ("", "1", "", "bad", False),
        ("1", "0", "20260712", "99991231", False),
        ("1", "0", "20200101", "20260710", False),
        ("", "0", "20200101", "99991231", None),
        ("1", "", "20200101", "99991231", None),
        ("1", "0", "", "99991231", None),
        ("1", "0", "0", "99991231", None),
        ("1", "0", "bad", "99991231", None),
        ("1", "0", "20200101", "0", None),
        ("1", "0", "20200101", "bad", None),
    ],
)
def test_domestic_eligibility_uses_false_before_unknown(
    sale: str, suspended: str, start: str, end: str, eligible: bool | None
) -> None:
    result = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "pd_sale_yn": sale,
                "pd_tr_yn": suspended,
                "pd_lstg_dt": start,
                "pd_lste_dt": end,
            },
        ),
        AS_OF,
    )
    assert result.record is not None
    assert result.record.is_eligible_at_as_of.value is eligible
    assert result.record.is_eligible_at_as_of.as_of_date == AS_OF
    assert result.record.is_eligible_at_as_of.inputs == (
        result.record.sale_flag.source,
        result.record.suspension_flag.source,
        result.record.listing_date.source,
        result.record.listing_end_date.source,
    )


def test_max_date_sentinel_is_enabled_only_for_listing_end() -> None:
    record = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "pd_lstg_dt": "99991231", "pd_lste_dt": "99991231",
                "cu_upt_dt": "99991231", "wu_upt_dt": "99991231",
            },
        ),
        AS_OF,
    ).record
    assert record is not None
    assert record.listing_date.normalized_value == date(9999, 12, 31)
    assert record.listing_end_date.normalized_value is None
    assert record.listing_end_date.quality_status is QualityStatus.SENTINEL_MAX_DATE
    assert record.custom_update_date.normalized_value == date(9999, 12, 31)
    assert record.weekly_update_date.normalized_value == date(9999, 12, 31)
```

- [ ] **Step 5: Run Step 4 to RED, implement exact flags and tri-state eligibility, and rerun**

Run the complete domestic-listed test file. Expected: flag inversion/truthiness or one or more tri-state/boundary cases fail before the state rule exists.

Implement the exact D-007 flag maps. Listing start uses max sentinel disabled; listing end uses max sentinel enabled. For eligibility, check explicit disqualifiers first: `sale_flag=False`, `suspension_flag=True`, valid start after as-of, or valid end before as-of -> `False`. If none applies and sale, suspension, or start is unavailable/invalid, or end is invalid (but not blank/max sentinel), return `None`; blank/max-sentinel end is open-ended. Otherwise return `True`.

Run the same command and expect all flag/eligibility tests to pass.

- [ ] **Step 6: Add broader AUM/return regression coverage without new production behavior**

Append:

```python
@pytest.mark.parametrize(
    ("column", "attribute", "expected_status"),
    [
        ("pd_net_tamt", "aum_primary", QualityStatus.RECORDED_ZERO),
        ("du_last_aum", "aum_secondary", QualityStatus.RECORDED_ZERO),
        ("cu_charge_rt", "total_fee", QualityStatus.RECORDED_ZERO_UNVERIFIED),
        ("du_chas_errt", "tracking_error", QualityStatus.RECORDED_ZERO),
        ("du_diff_rt", "difference_rate", QualityStatus.RECORDED_ZERO),
        ("du_er_1d", "return_1d", QualityStatus.RECORDED_ZERO),
        ("du_er_1m", "return_1m", QualityStatus.RECORDED_ZERO),
        ("du_er_3m", "return_3m", QualityStatus.RECORDED_ZERO),
        ("du_er_6m", "return_6m", QualityStatus.RECORDED_ZERO),
        ("du_er_1y", "return_1y", QualityStatus.RECORDED_ZERO),
        ("du_er_ytd", "return_ytd", QualityStatus.RECORDED_ZERO),
    ],
)
def test_domestic_numeric_zero_policy_is_field_specific(
    column: str, attribute: str, expected_status: QualityStatus
) -> None:
    record = normalize_domestic_listed(
        source_row("PREF01N001", {column: "0"}), AS_OF
    ).record
    assert record is not None
    wrapped = getattr(record, attribute)
    assert wrapped.normalized_value == Decimal("0")
    assert wrapped.quality_status is expected_status
    assert wrapped.quality_status is not QualityStatus.CONSTANT_METRIC


@pytest.mark.parametrize(
    ("column", "attribute"),
    [
        ("du_er_1m", "return_1m"), ("du_er_3m", "return_3m"),
        ("du_er_6m", "return_6m"), ("du_er_1y", "return_1y"),
        ("du_er_ytd", "return_ytd"),
    ],
)
def test_exact_minus_one_hundred_returns_remain_valid_recorded_values(
    column: str, attribute: str
) -> None:
    record = normalize_domestic_listed(
        source_row("PREF01N001", {column: "-100"}), AS_OF
    ).record
    assert record is not None
    wrapped = getattr(record, attribute)
    assert wrapped.raw_value == "-100"
    assert wrapped.normalized_value == Decimal("-100")
    assert wrapped.quality_status is QualityStatus.VALID
```

- [ ] **Step 7: Run the broader metric regressions and refactor only while green**

Run the domestic-listed test file. Expected: PASS because the source-column mapping, no-backfill structure, finite `Decimal`/`-100` parser behavior, and every field-specific zero state were already introduced by RED tests in Tasks 2 and 5 Step 1. These tests broaden regression coverage only; do not create a synthetic RED and do not add new production policy here. If a test unexpectedly fails, treat that as evidence that Step 3 did not satisfy its earlier RED contract: correct the existing implementation minimally and rerun from Step 2 before proceeding.

Refactor repeated field-to-parser declarations only if the explicit mapping remains readable and typed. Keep every metric sourced from its own declared column, use `recorded_zero_unverified` only for `cu_charge_rt`, never assign `constant_metric` in a row normalizer, and never replace `aum_primary` with `aum_secondary`.

Run the same command and expect all AUM/zero/return tests to pass.

- [ ] **Step 8: Write failing currency allowlist and independent update-field tests**

Append:

```python
@pytest.mark.parametrize(
    ("raw", "value", "status", "warning"),
    [
        ("CURR_CD_KRW", "KRW", QualityStatus.VALID, False),
        ("", None, QualityStatus.MISSING_BLANK, False),
        ("CURR_CD_000", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("KRW", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("CURR_CD_USD", None, QualityStatus.OUT_OF_DOMAIN, True),
    ],
)
def test_domestic_currency_uses_only_the_explicit_code_map(
    raw: str, value: str | None, status: QualityStatus, warning: bool
) -> None:
    result = normalize_domestic_listed(
        source_row(
            "PREF01N001", {"pd_curr_cd": raw, "pd_nm": "원화 USD 이름"}
        ),
        AS_OF,
    )
    assert result.record is not None
    assert result.record.currency.raw_value == raw
    assert result.record.currency.normalized_value == value
    assert result.record.currency.quality_status is status
    assert any(issue.source.source_column_name == "pd_curr_cd" for issue in result.issues) is warning


def test_domestic_update_fields_remain_independent_and_do_not_supply_applicable_dates() -> None:
    row = source_row(
        "PREF01N001",
        {
            "cu_upt_dt": "20260709",
            "du_upt_dt": "2026-07-10 09:30:00",
            "wu_upt_dt": "20260708",
            "pd_net_tamt": "100",
        },
    )
    record = normalize_domestic_listed(row, AS_OF).record
    assert record is not None
    assert record.custom_update_date.normalized_value == date(2026, 7, 9)
    assert record.daily_update_at.normalized_value == datetime(2026, 7, 10, 9, 30)
    assert record.daily_update_at.normalized_value.tzinfo is None
    assert record.weekly_update_date.normalized_value == date(2026, 7, 8)
    assert record.aum_primary.source.source_applicable_date is None


def test_invalid_optional_metric_emits_warning_but_does_not_quarantine() -> None:
    result = normalize_domestic_listed(
        source_row("PREF01N001", {"du_er_1m": "NaN"}), AS_OF
    )
    assert result.record is not None
    assert result.record.return_1m.quality_status is QualityStatus.INVALID_FORMAT
    assert any(
        issue.source.source_column_name == "du_er_1m"
        and issue.quality_status is QualityStatus.INVALID_FORMAT
        and not issue.quarantined
        for issue in result.issues
    )
```

- [ ] **Step 9: Run Step 8 to RED, implement currency/update/issue behavior, and rerun**

Run the domestic-listed test file. Expected: unregistered currency handling, name-based inference, update parsing, applicable-date inference, or optional-invalid issue behavior fails.

Implement one explicit immutable mapping `{"CURR_CD_KRW": "KRW"}`. Parse update fields separately from `cu_upt_dt`, `du_upt_dt`, and `wu_upt_dt`. Do not mutate source locators or infer a metric applicable date. Convert parser states `invalid_format`/`out_of_domain` to fixed-reason warning issues only; keep the record.

Run the same command and expect the entire domestic-listed test file to pass.

- [ ] **Step 10: Run domestic-listed and all prior Task 3 unit gates**

```bash
uv run pytest tests/unit/data/normalization tests/unit/domain/test_normalization_contracts.py tests/unit/registry/test_rating_registry.py -q
uv run ruff format --check src/finproof/domain/domestic_listed.py src/finproof/data/normalization/domestic_listed.py tests/unit/data/normalization/test_domestic_listed.py
uv run ruff check src/finproof/domain/domestic_listed.py src/finproof/data/normalization/domestic_listed.py tests/unit/data/normalization/test_domestic_listed.py
uv run mypy src/finproof/domain/domestic_listed.py src/finproof/data/normalization/domestic_listed.py tests/unit/data/normalization/test_domestic_listed.py
```

Expected: all commands pass; D-007, ETF/ETN separation, primary AUM, update-time independence, zero policy, and tri-state eligibility are covered.

- [ ] **Step 11: Commit the domestic-listed checkpoint**

```bash
git add src/finproof/domain/domestic_listed.py src/finproof/data/normalization/domestic_listed.py tests/unit/data/normalization/test_domestic_listed.py
git commit -m "feat: normalize domestic listed products"
```

- [ ] **Step 12: Complete the independent Task 5 review before acceptance**

Have a fresh reviewer inspect `HEAD^..HEAD` for ETF/ETN conflation, flag inversion/truthiness, eligibility false-before-unknown precedence, listing-end sentinel handling, primary-AUM backfill, row-level `constant_metric`, wrong fee/tracking/difference zero states, currency inference, update/applicable-date conflation, `float`, issue leakage, and optional-field quarantine. Do not begin Task 6 until no Critical or Important finding remains. Corrections require a focused RED regression, Step 10 rerun, and a separate review-fix commit.

---

### Task 6: Prove all 44,128 official domestic rows, record evidence, and complete final review

**Files:**

- Create: `tests/source_contract/test_official_domestic_normalization.py`
- Modify: `docs/implementation/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`
- Modify: `docs/superpowers/plans/2026-08-14-phase1-task3-domestic-normalization.md` only to check completed steps after evidence exists
- Inspect: `docs/10_DECISION_LOG.md`; do not change it unless an actual higher-priority conflict or new frozen decision is discovered

**Interfaces:**

- Consumes: `SourceFileManifest.load(manifest_path: Path, schema_catalog_path: Path) -> SourceFileManifest`, `SourceFileManifest.verify(base_dir: Path) -> VerifiedSourceSet`, `VerifiedSourceSet.data_file(table_id: str) -> VerifiedSourceFile`, `iter_xlsx_rows(source: VerifiedSourceFile) -> Iterator[SourceRow]`, `normalize_bond`, `normalize_domestic_listed`, and one `RatingRegistry` loaded from the checked-in `config/rating_scale.yaml`.
- Proves: normal exhaustion of exactly 44,128 source rows without an unexpected exception: 42,394 bond source rows plus 1,734 domestic-listed source rows.
- Proves: 42,394 `BondInstrument` records and zero quarantined bond rows.
- Proves: 1,733 `ListedProduct` records and one quarantined domestic-listed row, exactly Excel row 1,155 with raw `pd_itm_no="KR"` and a blocker issue located at that cell.
- Proves: source product-group counts of exactly 1,202 ETF and 532 ETN rows before quarantine.
- Proves: produced identity uniqueness within each native grain: 42,394 unique bond IDs and 1,733 unique domestic-listed IDs.
- Proves: complete raw/locator fidelity for every wrapped source field and complete derived-input locator fidelity for every produced record; no wrapped field may point to a different row or column.
- Produces: durable focused RED/GREEN evidence, acceptance counts, commands/results, review outcomes, commit hashes, unresolved risks/questions, and exact next task in `docs/implementation/STATUS.md`.
- Preserves: A-011 as open for the later artifact quality/evidence schema; Task 3 does not persist issues and does not resolve that artifact contract.
- Does not: alter official inputs, `tests/contracts/expected_source_audit.json`, Task 4+ behavior, artifacts, overseas/public-fund code, query code, API code, or the Phase 1 gate checkbox.

- [ ] **Step 1: Write the full official acceptance contract; do not manufacture RED**

Create `tests/source_contract/test_official_domestic_normalization.py` with module marks and explicit field-to-column maps:

```python
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from finproof.data.normalization.bonds import normalize_bond
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.data.source_manifest import SourceFileManifest
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.bonds import BondInstrument
from finproof.domain.domestic_listed import ListedProduct, ListedProductType
from finproof.domain.quality import DataQualityIssue
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue
from finproof.registry.rating import RatingRegistry

ROOT = Path(__file__).resolve().parents[2]
AS_OF = date(2026, 7, 11)
pytestmark = [pytest.mark.source_contract, pytest.mark.slow]

BOND_COLUMNS = {
    "product_id": "PD_NO", "name": "PD_NM", "short_name": "PD_ABRV_NM",
    "currency": "CURR_CD", "bond_kind_raw": "BD_KND", "issue_date": "ISU_DT",
    "maturity_date": "MAT_DT", "source_update_date": "PD_STD_INFO_UPDATE",
    "coupon_rate": "SRFC_IRT", "buy_yield": "BUY_YIELD",
    "buyable_quantity": "BUYABLE_QUANTITY", "source_remaining_days": "REMAINING_DAYS",
    "credit_rating": "CRD_GRD", "credit_rating_agencies_raw": "PD_EVCO_CRD_GRD",
    "credit_rating_date": "CRD_GRD_DT", "duration": "DUR",
    "evaluation_price": "EVAL_PRICE",
}

LISTED_COLUMNS = {
    "product_id": "pd_itm_no", "market_identifier": "pd_itm_no_ma",
    "product_type": "pd_grp_no", "name": "pd_nm", "short_name": "pd_abrv_nm",
    "currency": "pd_curr_cd", "listing_date": "pd_lstg_dt",
    "listing_end_date": "pd_lste_dt", "sale_flag": "pd_sale_yn",
    "suspension_flag": "pd_tr_yn", "aum_primary": "pd_net_tamt",
    "aum_secondary": "du_last_aum", "total_fee": "cu_charge_rt",
    "tracking_error": "du_chas_errt", "difference_rate": "du_diff_rt",
    "return_1d": "du_er_1d", "return_1m": "du_er_1m",
    "return_3m": "du_er_3m", "return_6m": "du_er_6m",
    "return_1y": "du_er_1y", "return_ytd": "du_er_ytd",
    "risk_code": "pd_risk_cd", "risk_name": "pd_risk_nm",
    "base_index": "cu_base_index", "manager": "cu_fund_mgmt_co",
    "asset_type": "wu_inv_ast_type", "region": "wu_inv_rgn",
    "custom_update_date": "cu_upt_dt", "daily_update_at": "du_upt_dt",
    "weekly_update_date": "wu_upt_dt",
}


def _assert_wrapped_source_fidelity(
    record: BondInstrument | ListedProduct,
    row: SourceRow,
    field_columns: dict[str, str],
) -> None:
    for field_name, column_name in field_columns.items():
        wrapped = getattr(record, field_name)
        assert isinstance(wrapped, NormalizedValue)
        cell = row.cell(column_name)
        assert wrapped.raw_value == cell.raw_value
        assert wrapped.source.source_table == row.source_table
        assert wrapped.source.source_file == row.source_file
        assert wrapped.source.source_sheet == row.source_sheet
        assert wrapped.source.source_row_number == row.source_row_number
        assert wrapped.source.source_column_name == cell.column_name
        assert wrapped.source.source_column_number == cell.excel_column_number
        assert wrapped.source.source_column_letter == cell.excel_column_letter
        assert wrapped.source.source_checksum == row.source_checksum
        assert wrapped.source.source_snapshot_date == row.source_snapshot_date
        assert wrapped.source.source_applicable_date == cell.applicable_date


def _assert_derived_inputs(record: BondInstrument | ListedProduct) -> None:
    derived_columns = (
        {
            "remaining_days_at_as_of": ("MAT_DT",),
            "is_matured_at_as_of": ("MAT_DT",),
            "has_positive_buyable_quantity": ("BUYABLE_QUANTITY",),
            "is_buyable_validated_at_as_of": ("BUYABLE_QUANTITY", "MAT_DT"),
        }
        if isinstance(record, BondInstrument)
        else {
            "is_eligible_at_as_of": (
                "pd_sale_yn", "pd_tr_yn", "pd_lstg_dt", "pd_lste_dt"
            )
        }
    )
    for field_name, expected_columns in derived_columns.items():
        derived = getattr(record, field_name)
        assert isinstance(derived, DerivedValue)
        assert derived.as_of_date == AS_OF
        assert tuple(locator.source_column_name for locator in derived.inputs) == expected_columns
        for locator in derived.inputs:
            assert locator.source_table in {"PRBD01N001", "PREF01N001"}
            assert locator.source_row_number == record.product_id.source.source_row_number
            assert locator.source_file == record.product_id.source.source_file
            assert locator.source_checksum == record.product_id.source.source_checksum


def test_official_domestic_normalization_exhausts_all_rows_with_exact_counts_and_fidelity() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")
    rating_registry = RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")

    bond_ids: set[str] = set()
    bond_source_rows = bond_records = bond_quarantined = 0
    for row in iter_xlsx_rows(verified.data_file("PRBD01N001")):
        bond_source_rows += 1
        assert row.source_snapshot_date == AS_OF
        result = normalize_bond(row, AS_OF, rating_registry)
        bond_quarantined += result.record is None
        assert result.record is not None
        bond_records += 1
        product_id = result.record.product_id.normalized_value
        assert product_id is not None
        assert result.record.product_id.source.source_snapshot_date == AS_OF
        assert product_id not in bond_ids
        bond_ids.add(product_id)
        _assert_wrapped_source_fidelity(result.record, row, BOND_COLUMNS)
        _assert_derived_inputs(result.record)

    listed_ids: set[str] = set()
    listed_source_rows = listed_records = listed_quarantined = 0
    source_groups: Counter[str] = Counter()
    produced_groups: Counter[ListedProductType] = Counter()
    quarantined_rows: list[tuple[int, str, tuple[DataQualityIssue, ...]]] = []
    for row in iter_xlsx_rows(verified.data_file("PREF01N001")):
        listed_source_rows += 1
        assert row.source_snapshot_date == AS_OF
        source_groups[row.cell("pd_grp_no").raw_value] += 1
        result = normalize_domestic_listed(row, AS_OF)
        if result.record is None:
            listed_quarantined += 1
            quarantined_rows.append(
                (row.source_row_number, row.cell("pd_itm_no").raw_value, result.issues)
            )
            continue
        listed_records += 1
        product_id = result.record.product_id.normalized_value
        assert product_id is not None
        assert result.record.product_id.source.source_snapshot_date == AS_OF
        assert product_id not in listed_ids
        listed_ids.add(product_id)
        product_type = result.record.product_type.normalized_value
        assert product_type is not None
        produced_groups[product_type] += 1
        _assert_wrapped_source_fidelity(result.record, row, LISTED_COLUMNS)
        _assert_derived_inputs(result.record)

    assert bond_source_rows == 42_394
    assert bond_records == 42_394
    assert bond_quarantined == 0
    assert len(bond_ids) == 42_394
    assert listed_source_rows == 1_734
    assert listed_records == 1_733
    assert listed_quarantined == 1
    assert len(listed_ids) == 1_733
    assert source_groups == Counter({"ETF": 1_202, "ETN": 532})
    assert produced_groups == Counter(
        {ListedProductType.ETF: 1_201, ListedProductType.ETN: 532}
    )
    assert bond_source_rows + listed_source_rows == 44_128
    assert len(quarantined_rows) == 1
    excel_row, raw_product_id, issues = quarantined_rows[0]
    assert excel_row == 1_155
    assert raw_product_id == "KR"
    assert any(
        issue.quarantined
        and issue.source.source_row_number == 1_155
        and issue.source.source_column_name == "pd_itm_no"
        for issue in issues
    )
```

The `produced_groups` assertion proves the one quarantined source row belongs to the ETF source group without altering the required 1,202 ETF/532 ETN source counts.

- [ ] **Step 2: Run the acceptance test; passing immediately is valid, synthetic RED is prohibited**

Run:

```bash
uv run pytest tests/source_contract/test_official_domestic_normalization.py -q -m source_contract
```

Expected: PASS after Tasks 1-5. This test adds full-source evidence rather than new production behavior, so a synthetic production failure is neither required nor permitted. If it fails, stop broad implementation work: isolate the exact table/Excel row/field, add one focused unit regression to the owning Task 1-5 test file, observe that focused regression fail, apply the smallest correction, rerun the owning task gate and this acceptance test. Never weaken an official count or add a correction list.

- [ ] **Step 3: Commit the official acceptance checkpoint**

```bash
git add tests/source_contract/test_official_domestic_normalization.py
git commit -m "test: enforce official domestic normalization"
```

- [ ] **Step 4: Run the complete implementation and repository gates**

From the isolated Task 3 worktree, run every command and record its observed output; do not copy expected results into status as though they were observed:

```bash
uv sync --frozen --all-groups
uv run pytest tests/unit/data/normalization tests/unit/domain/test_normalization_contracts.py tests/unit/registry/test_rating_registry.py -q
uv run pytest tests/source_contract/test_official_domestic_normalization.py -q -m source_contract
uv run pytest tests/source_contract -q -m source_contract
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/extract_schema_catalog.py --check
PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files
git diff --check
git diff --cached --check
```

Expected source evidence remains exactly 145,393 official rows overall, snapshot `2026-07-11`, 207 schema columns, and the Task 3 acceptance counts from Step 1. Any unexplained failure is a stop condition.

- [ ] **Step 5: Update status and plans using only observed evidence**

In `docs/implementation/STATUS.md`:

- mark only Phase 1 Task 3 complete;
- record each Task 1-5 focused RED reason and GREEN command result;
- explicitly record that Task 6 acceptance was allowed to pass immediately and that no synthetic RED was introduced;
- record the 42,394/0 bond result, 1,733/1 listed result, 1,202 ETF/532 ETN source groups, 44,128 normal exhaustion, identity uniqueness, complete wrapper locator fidelity, and Excel-row-1,155 quarantine;
- record all Step 4 commands and exact observed summaries;
- record each implementation, review-fix, acceptance, and documentation commit hash;
- state whether the decision-log inspection found a real conflict. If none, record that no decision-log change was necessary and A-011 remains open for the later artifact quality/evidence schema;
- name `Phase 1 Task 4: normalize overseas listed products and public funds with quarantine` as the exact next task;
- leave Phase 1 Tasks 4-5 and the Phase 1 gate unchecked.

In `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`, mark the Task 3 pointer/checkpoint complete only after the evidence above exists; do not change Task 4+ behavior. In this dedicated plan, check a box only after its command/evidence exists.

- [ ] **Step 6: Commit the Task 3 evidence checkpoint**

```bash
git add docs/implementation/STATUS.md docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md docs/superpowers/plans/2026-08-14-phase1-task3-domestic-normalization.md
git commit -m "docs: record Phase 1 Task 3 verification"
```

- [ ] **Step 7: Request the final independent whole-branch review**

Have a fresh reviewer inspect the Task 3 branch base through HEAD against `AGENTS.md`, D-003/D-006/D-007/D-008/D-017, the approved design, this plan, the current Task 2 interfaces, and every official acceptance invariant. Require explicit review of:

- only `SourceRow` normalizer inputs and no arbitrary path/locator construction;
- exact raw values and complete locators for every wrapped source field;
- frozen/strict value, result, product, and registry contracts;
- safe deterministic issue IDs/payload hashes and no clock/path/payload leakage;
- exact date/sentinel/numeric/zero/rating/flag/tri-state behavior;
- `C0`/`CC0`, missing/unrated non-comparability, and no agency backfill;
- D-007 and false-before-unknown domestic eligibility;
- official 44,128-row normal exhaustion/counts/uniqueness/fidelity;
- strict RED -> GREEN evidence for every production behavior and no synthetic acceptance RED;
- no official source, expected-audit, Task 4+, artifact, query, or API change.

Classify findings as Critical, Important, or Minor. For every Critical or Important behavior finding, add a focused regression to the owning test file, observe RED, make the smallest correction, rerun that task's gate and Step 4, commit the correction separately, update status evidence, and request re-review. Repeat until no Critical or Important finding remains.

- [ ] **Step 8: Run the final reviewed-tree gate and prove cleanliness**

On the final reviewed HEAD, rerun every Step 4 command, then run:

```bash
git status --short --branch
test -z "$(git status --porcelain)"
```

Expected: every gate passes, the final independent review has no Critical or Important finding, the feature worktree is clean, Phase 1 Task 3 alone is checked, and Task 4 is the next incomplete task. Then use `superpowers:finishing-a-development-branch` and let the user choose local merge, PR, or branch preservation.

---
