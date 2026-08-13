# Phase 1 Task 4 Overseas and Public-Fund Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize all verified `PREF02N001` overseas ETF/ETN rows and `PRFD01N001` public-fund attribute rows into immutable typed records, then collapse valid public-fund rows to the frozen `itm_no` grain without losing raw values, source cells, malformed-row issues, or repeated evidence.

**Architecture:** Extend the Task 3 pure `SourceRow -> NormalizationResult[T]` boundary with a dedicated all-field overseas model and an all-field public-fund row model. Public-fund collapse groups globally by normalized item ID, proves exact agreement across every non-attribute raw column, stores contributing rows once, exposes field-specific equivalent locators, and emits deterministic fail-closed issues. The canonical quality-issue JSON schema is aligned to the existing domain model before these producers are added.

**Tech Stack:** Python 3.12; frozen strict Pydantic 2 models; `Decimal`; `date`; timezone-naive source `datetime`; JSON Schema Draft 2020-12 plus `jsonschema.FormatChecker`; pytest 9; Ruff; mypy; uv.

## Global Constraints

- The approved design at `docs/superpowers/specs/2026-08-14-phase1-task4-overseas-public-normalization-design.md` is authoritative for this plan.
- Inputs are only immutable `SourceRow` values produced by the verified Task 2 reader or complete synthetic fixtures with equivalent lineage.
- Normalizers and collapse functions perform no filesystem, database, network, environment, logging, or clock I/O.
- Raw strings are immutable. Normalized text may be trimmed only beside the preserved raw string.
- All financial numerics use exact finite `Decimal`; `float` is prohibited.
- Financial dates use `date`; `PREF02N001.du_nav_base_dt` uses a timezone-naive `datetime` because the source supplies no timezone.
- Source update/basis fields stay independent. They never overwrite another cell's `source_applicable_date`.
- Missing optional values and date sentinels do not quarantine a product. Invalid mandatory identity, product type, or public-fund attribute key does.
- `NormalizationResult.record is None` if and only if a quarantined issue exists. `FundCollapseResult` may contain quarantined issues alongside unaffected items.
- Every new Pydantic contract uses `ConfigDict(frozen=True, extra="forbid", strict=True)`.
- Product names, strategy text, descriptions, codes, and identifiers are untrusted data, never instructions.
- `pd_grp_no` alone distinguishes overseas ETF from ETN. A plain ETF remains separate from ETN.
- A-003 remains open: no overseas/public-fund active, saleable, Mirae-saleable, or eligibility boolean is derived in Task 4.
- Row-level zeros keep `recorded_zero` or the field-specific `recorded_zero_unverified`. Dataset-level constant/tie facts are not written into each source wrapper.
- Public-fund default grain is `fund_item`; `prfd_attr_cd` remains a sibling many-valued `fund_attribute` relation. No family or name-based ETF grouping is built.
- Official inputs and `tests/contracts/expected_source_audit.json` are read-only. Artifact building, exact links, query/API behavior, and persistence timestamps remain Task 5+ work.
- Every production behavior follows strict RED -> GREEN -> REFACTOR. Acceptance-only Task 6 may pass on its first executable run because Tasks 1-5 already introduced the behavior; never manufacture an acceptance RED.
- Each task is one reviewer-worthy commit. Do not commit a callable overseas normalizer, fund normalizer, or collapse path with placeholder fields, incomplete invariants, provisional ordering, or intentionally unresolved behavior.
- Issue reasons are the fixed safe strings in this plan. They never echo raw values, absolute paths, stack traces, or product text.
- All Task 4 rules use `rule_version="1.0.0"`.
- At the start of every implementation/review shell session run
  `export UV_CACHE_DIR=/private/tmp/finproof-uv-cache`; every command block in this plan
  must run in that same exported session. If automation opens a new shell per command,
  repeat the export before that command. Never use the default uv cache.

```bash
export UV_CACHE_DIR=/private/tmp/finproof-uv-cache
```

## File and responsibility map

| File | Responsibility |
|---|---|
| `schemas/quality_issue.schema.json` | Canonical D-021 JSON shape for `DataQualityIssue.model_dump(mode="json")` |
| `tests/contract/test_quality_issue_schema.py` | Draft 2020-12 schema, explicit format checking, canonical/negative serialization cases |
| `src/finproof/domain/listed.py` | Shared exact ETF/ETN enum |
| `src/finproof/domain/overseas_listed.py` | Complete 49-wrapper overseas listed-product contract |
| `src/finproof/domain/public_funds.py` | Fund row/value/item/attribute/result contracts and their lineage/completeness validators |
| `src/finproof/data/normalization/overseas_listed.py` | Pure overseas row parsing and deterministic issues |
| `src/finproof/data/normalization/public_funds.py` | Pure fund-row normalization, global collapse, and total issue ordering |
| `tests/helpers/source_rows.py` | Complete synthetic rows for all four official tables with fixed safe lineage |
| `tests/unit/domain/test_task4_contracts.py` | Shared enum, helper, exact-type Python/identity-preserving builder, canonical JSON, and fund value/result invariants |
| `tests/unit/data/normalization/test_overseas_listed.py` | Overseas mapping, parser, zero/date/type, and issue behavior |
| `tests/unit/data/normalization/test_public_funds.py` | Fund row parsing and early quarantine behavior |
| `tests/unit/data/normalization/test_public_fund_collapse.py` | Global grouping, completeness, exact issue cardinality/order, and bounded-order invariance |
| `tests/performance/test_public_fund_collapse_scale.py` | Bounded synthetic scale and incremental peak-allocation preflight |
| `tests/source_contract/test_official_overseas_public_normalization.py` | Exhaustive verified 101,265-row Task 4 acceptance |

---

### Task 1: Align the canonical quality-issue JSON schema and freeze D-021

**Files:**

- Modify: `schemas/quality_issue.schema.json`
- Create: `tests/contract/test_quality_issue_schema.py`
- Inspect: `docs/10_DECISION_LOG.md`; D-021 and the refined A-011 boundary are frozen with this plan and must not be rewritten during implementation

**Interfaces:**

- Consumes: existing frozen `DataQualityIssue` and `SourceCellLocator` models unchanged.
- Produces: a Draft 2020-12 schema aligned field-for-field with the supported JSON-mode issue serialization, including all ten issue fields and all ten locator fields. The strict domain models remain authoritative for cross-field invariants such as Excel number/letter agreement.
- Requires: consumers construct `Draft202012Validator(schema, format_checker=FormatChecker())`; `format` without this checker is prohibited.
- Requires: `first_detected_at` is `null` or a UTC date-time string ending in `Z`. Naive strings, malformed strings, and valid nonzero-offset date-times fail.
- Consumes: D-021 as frozen and the refined A-011 boundary: only its quality-issue portion is resolved; evidence, golden-case, and metric gaps remain open.

- [ ] **Step 1: Write the failing canonical schema tests**

Create `tests/contract/test_quality_issue_schema.py`:

```python
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from tests.helpers.source_rows import source_row

ROOT = Path(__file__).resolve().parents[2]


def _validator() -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas/quality_issue.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _issue() -> DataQualityIssue:
    return DataQualityIssue.from_row(
        source_row("PREF01N001", {"pd_itm_no": "KR"}, excel_row=1155),
        "pd_itm_no",
        rule_id="domestic_listed.product_id",
        rule_version="1.0.0",
        severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason="Domestic listed product identifier is malformed.",
        quarantined=True,
    )


def _messages(instance: object) -> tuple[str, ...]:
    return tuple(error.message for error in _validator().iter_errors(instance))


def test_pure_domain_issue_json_is_the_canonical_schema_instance() -> None:
    payload = _issue().model_dump(mode="json")
    assert payload["first_detected_at"] is None
    assert _messages(payload) == ()
    assert set(payload) == {
        "issue_id", "rule_id", "rule_version", "severity", "quality_status",
        "source", "reason", "quarantined", "raw_payload_sha256",
        "first_detected_at",
    }
    assert set(payload["source"]) == {
        "source_table", "source_file", "source_sheet", "source_row_number",
        "source_column_name", "source_column_number", "source_column_letter",
        "source_checksum", "source_snapshot_date", "source_applicable_date",
    }


def test_persisted_utc_issue_serializes_with_z_and_validates() -> None:
    issue = DataQualityIssue.model_validate(
        _issue().model_dump()
        | {"first_detected_at": datetime(2026, 7, 11, 0, 0, tzinfo=UTC)}
    )
    payload = issue.model_dump(mode="json")
    assert payload["first_detected_at"] == "2026-07-11T00:00:00Z"
    assert _messages(payload) == ()
```

- [ ] **Step 2: Write the complete failing negative schema suite before editing the schema**

Append:

```python
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issue_id", "A" * 64),
        ("raw_payload_sha256", "0" * 63),
        ("severity", "critical"),
        ("quality_status", "unknown"),
        ("first_detected_at", "2026-07-11T00:00:00"),
        ("first_detected_at", "2026-07-11T09:00:00+09:00"),
        ("first_detected_at", "not-a-date"),
    ],
)
def test_issue_schema_rejects_bad_hash_enum_and_timestamp(
    field: str, value: object
) -> None:
    payload = _issue().model_dump(mode="json") | {field: value}
    assert _messages(payload)


def test_issue_schema_rejects_missing_and_extra_issue_fields() -> None:
    payload = _issue().model_dump(mode="json")
    missing = dict(payload)
    missing.pop("quarantined")
    assert _messages(missing)
    assert _messages(payload | {"raw_payload": "secret"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_file", "/absolute/source.xlsx"),
        ("source_file", "../escape.xlsx"),
        ("source_row_number", 0),
        ("source_column_number", 0),
        ("source_column_letter", "a"),
        ("source_checksum", "g" * 64),
        ("source_snapshot_date", "2026-02-30"),
        ("source_applicable_date", "2026/07/11"),
    ],
)
def test_issue_schema_rejects_incomplete_or_unsafe_locator(
    field: str, value: object
) -> None:
    payload = _issue().model_dump(mode="json")
    payload["source"] = payload["source"] | {field: value}
    assert _messages(payload)


def test_issue_schema_rejects_missing_and_extra_locator_fields() -> None:
    payload = _issue().model_dump(mode="json")
    missing = dict(payload["source"])
    missing.pop("source_column_name")
    payload["source"] = missing
    assert _messages(payload)
    payload = _issue().model_dump(mode="json")
    payload["source"] = payload["source"] | {"absolute_path": "/tmp/source.xlsx"}
    assert _messages(payload)
```

- [ ] **Step 3: Run the schema suite and observe RED**

Run:

```bash
uv run pytest tests/contract/test_quality_issue_schema.py -q
```

Expected: canonical dumps fail because the legacy schema uses abbreviated locator names and omits `raw_payload_sha256`/`first_detected_at`; some invalid status/hash/timestamp instances are also accepted.

- [ ] **Step 4: Replace the schema with the exact D-021 contract**

Use these closed properties:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DataQualityIssue",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "issue_id", "rule_id", "rule_version", "severity", "quality_status",
    "source", "reason", "quarantined", "raw_payload_sha256",
    "first_detected_at"
  ],
  "properties": {
    "issue_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "rule_id": {"type": "string", "minLength": 1},
    "rule_version": {"type": "string", "minLength": 1},
    "severity": {"enum": ["info", "warning", "high", "blocker"]},
    "quality_status": {"enum": [
      "valid", "missing_blank", "missing_literal_null", "sentinel_zero",
      "sentinel_max_date", "recorded_zero", "recorded_zero_unverified",
      "invalid_format", "out_of_domain", "constant_metric", "stale",
      "mixed_source_values", "malformed_source_row"
    ]},
    "source": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "source_table", "source_file", "source_sheet", "source_row_number",
        "source_column_name", "source_column_number", "source_column_letter",
        "source_checksum", "source_snapshot_date", "source_applicable_date"
      ],
      "properties": {
        "source_table": {"type": "string", "minLength": 1},
        "source_file": {
          "type": "string", "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))[^\\u0000]+$"
        },
        "source_sheet": {"type": "string", "minLength": 1},
        "source_row_number": {"type": "integer", "minimum": 1},
        "source_column_name": {"type": "string", "minLength": 1},
        "source_column_number": {"type": "integer", "minimum": 1},
        "source_column_letter": {"type": "string", "pattern": "^[A-Z]+$"},
        "source_checksum": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "source_snapshot_date": {"type": "string", "format": "date"},
        "source_applicable_date": {
          "oneOf": [{"type": "null"}, {"type": "string", "format": "date"}]
        }
      }
    },
    "reason": {"type": "string"},
    "quarantined": {"type": "boolean"},
    "raw_payload_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "first_detected_at": {
      "oneOf": [
        {"type": "null"},
        {
          "type": "string", "format": "date-time",
          "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T.*Z$"
        }
      ]
    }
  }
}
```

Do not edit `DataQualityIssue`, `SourceCellLocator`, or `schemas/evidence_record.schema.json` in this task.

- [ ] **Step 5: Run focused GREEN and static/schema gates**

```bash
uv run pytest tests/contract/test_quality_issue_schema.py tests/unit/domain/test_normalization_contracts.py -q
uv run ruff format --check tests/contract/test_quality_issue_schema.py
uv run ruff check tests/contract/test_quality_issue_schema.py
uv run mypy tests/contract/test_quality_issue_schema.py
uv run python tools/verify_handoff.py
git diff --check
```

Expected: canonical null/UTC issue instances validate, every negative case fails, Task 3 contracts remain green, and the handoff remains verified.

- [ ] **Step 6: Commit and review the quality-schema checkpoint**

```bash
git add schemas/quality_issue.schema.json tests/contract/test_quality_issue_schema.py
git commit -m "fix: align canonical quality issue schema"
```

Have a fresh reviewer inspect `HEAD^..HEAD` for schema/domain drift, missing `FormatChecker`, date-time annotation-only validation, offset acceptance, incomplete/extra locators, A-011 over-closure, and accidental evidence-schema edits. Any correction starts with a failing case in `test_quality_issue_schema.py`, reruns Step 5, and receives a separate review-fix commit. Do not begin Task 2 while Critical or Important findings remain.

---

### Task 2: Add complete Task 4 fixtures, the shared listed type, exact text helpers, and `FundItemValue`

**Files:**

- Create: `src/finproof/domain/listed.py`
- Modify: `src/finproof/domain/domestic_listed.py`
- Modify: `src/finproof/domain/__init__.py`
- Modify: `src/finproof/data/normalization/text.py`
- Create: `src/finproof/domain/public_funds.py`
- Modify: `tests/helpers/source_rows.py`
- Create: `tests/unit/domain/test_task4_contracts.py`
- Modify: `tests/unit/data/normalization/test_text_parsers.py`
- Modify: `tests/unit/data/normalization/test_domestic_listed.py`

**Interfaces:**

- Produces: shared `ListedProductType(StrEnum)` with exact values `ETF` and `ETN`; `finproof.domain.domestic_listed.ListedProductType` re-exports the identical class.
- Produces: `parse_exact_source_identity(row, column_name, *, rule_id, rule_version) -> NormalizedValue[str]`; it accepts an exact nonempty raw value containing non-whitespace only when `raw == raw.strip()`, and preserves case/punctuation/length.
- Produces: `parse_literal_null_text(row, column_name, *, rule_id, rule_version) -> NormalizedValue[str]`; exact uppercase `NULL` becomes `None/missing_literal_null`, while other values follow `parse_text`.
- Produces: strict frozen generic `FundItemValue[T](representative: NormalizedValue[T], equivalent_sources: tuple[SourceCellLocator, ...])`.
- Requires: `FundItemValue.equivalent_sources` is nonempty, unique, sorted by `(source_row_number, source_column_number)`, contains the representative locator first, and every locator matches the representative table/file/sheet/column/checksum/snapshot while shared-lineage comparison explicitly excludes `source_row_number` and `source_applicable_date`. Each locator retains its own exact row and applicable date. JSON-mode dump and strict JSON round trip preserve the generic typed value and locators.
- Extends: `source_row(table_id: Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"], ...)` with every official cell in catalog order and fixed valid defaults.

- [ ] **Step 1: Extend the complete synthetic-row fixture before new tests use it**

Add exact `OVERSEAS_LISTED_COLUMNS` and `PUBLIC_FUND_COLUMNS` tuples from `source_material/schema_catalog.json`:

```python
OVERSEAS_LISTED_COLUMNS = (
    "cu_base_index", "cu_charge_rt", "cu_etn_yn", "cu_fund_mgmt_co",
    "cu_index_repl_mthd", "cu_index_tracking_yn", "cu_inverse_short_yn",
    "cu_lev_fector", "cu_strtegy", "cu_upt_dt", "du_base_dt_match_yn",
    "du_bpr", "du_clpr", "du_clpr_base_dt", "du_clpr_src", "du_diff_rt",
    "du_er_1d", "du_hpr", "du_last_aum", "du_last_nav", "du_lpr",
    "du_nav_base_dt", "du_opr", "du_upt_dt", "du_val_1d", "du_vol_1d",
    "pd_abrv_nm", "pd_curr_cd", "pd_exg_mkt_cd", "pd_grp_no",
    "pd_isin_cd", "pd_itm_no", "pd_itm_no_ma", "pd_lipper_id",
    "pd_lstg_dt", "pd_lst_price", "pd_lst_stk_cnt", "pd_mkt_id", "pd_nm",
    "pd_sale_yn", "pd_trd_ccy", "pd_tr_yn", "pd_us_cik", "ru_mkt_price",
    "ru_mkt_volume", "wu_core_yn", "wu_inv_ast_type", "wu_inv_rgn",
    "wu_upt_dt",
)

PUBLIC_FUND_COLUMNS = (
    "bmrk_eng_nm", "bmrk_nm", "curr_cd", "exchdg_yn", "fd_estb_ctry_cd",
    "fd_ivst_rgn_desc", "fd_mm18_ern_r", "fd_mm1_ern_r", "fd_mm3_ern_r",
    "fd_mm6_ern_r", "fd_nast_suma", "fd_set_pcd", "fd_wk1_ern_r",
    "fd_yr1_ern_r", "fd_yr2_ern_r", "fd_yr3_ern_r", "fd_yr5_ern_r",
    "frc_bpr_itm_yn", "fss_itm_no", "hdge_fd_yn", "int_dvd_desc",
    "itm_abrv_nm", "itm_eabrv_nm", "itm_eng_nm", "itm_nm", "itm_no",
    "kofia_fd_ccd", "ksd_itm_no", "mtco_itm_no", "ofsfd_yn",
    "or_attr_desc", "or_co_xtn_itt_cd", "ovrs_fd_desc", "pers_corp_desc",
    "pfiv_sale_cntl_tcd", "prfd_attr_cd", "prvo_fd_desc", "prvo_pbff_desc",
    "rptt_ksd_itm_no", "sale_yn", "std_itm_no", "thco_sale_yn",
    "trusc_xtn_itt_cd", "zrin_fd_ivst_risk_gcd",
    "zrin_fd_ivst_risk_grd_nm",
)
```

Use these fixed defaults:

```python
OVERSEAS_DEFAULTS = {
    "pd_itm_no": "BND.O", "pd_itm_no_ma": "BND.O", "pd_abrv_nm": "BND",
    "pd_grp_no": "ETF", "pd_nm": "Test Overseas ETF", "pd_trd_ccy": "USD",
    "pd_lstg_dt": "20070403", "cu_charge_rt": "0.020000",
    "du_last_aum": "157396600000.00", "du_er_1d": "0.000000",
    "cu_upt_dt": "20260614", "du_clpr_base_dt": "20260616",
    "du_nav_base_dt": "2026-06-14 00:00:00", "du_upt_dt": "20260616",
    "wu_upt_dt": "20260614",
}
PUBLIC_FUND_DEFAULTS = {
    "itm_no": "KR5114601001", "prfd_attr_cd": "C101",
    "itm_nm": "테스트 공모펀드", "itm_abrv_nm": "테스트펀드", "curr_cd": "KRW",
    "fd_nast_suma": "1000000.0000", "or_attr_desc": "주식형",
    "sale_yn": "판매중", "thco_sale_yn": "Y", "ksd_itm_no": "KR5114601001",
}
```

Update `TableId`, select columns/defaults by exact table ID, and retain the existing unknown-column/applicable-date rejection. Do not expose fixture path/checksum/sheet overrides.

- [ ] **Step 2: Write failing fixture, enum/re-export, exact identity, and literal-null tests**

Create `tests/unit/domain/test_task4_contracts.py` and extend `test_text_parsers.py`:

```python
from typing import Literal

import pytest

from tests.helpers.source_rows import (
    OVERSEAS_LISTED_COLUMNS,
    PUBLIC_FUND_COLUMNS,
    source_row,
)

Task4TableId = Literal["PREF02N001", "PRFD01N001"]


@pytest.mark.parametrize(
    ("table_id", "columns"),
    [
        ("PREF02N001", OVERSEAS_LISTED_COLUMNS),
        ("PRFD01N001", PUBLIC_FUND_COLUMNS),
    ],
)
def test_task4_fixture_has_every_official_cell_in_canonical_order(
    table_id: Task4TableId, columns: tuple[str, ...]
) -> None:
    row = source_row(table_id)
    assert tuple(cell.column_name for cell in row.cells) == columns
    assert row.raw_payload == tuple(cell.raw_value for cell in row.cells)


def test_shared_listed_type_is_the_domestic_reexport() -> None:
    from finproof.domain.domestic_listed import ListedProductType as DomesticType
    from finproof.domain.listed import ListedProductType

    assert DomesticType is ListedProductType
    assert tuple(member.value for member in ListedProductType) == ("ETF", "ETN")
```

```python
@pytest.mark.parametrize("raw", ["BND.O", "XW", "EES", "kr.f", "A/B", "123456789012345"])
def test_exact_source_identity_preserves_nonblank_unpadded_raw_text(raw: str) -> None:
    value = parse_exact_source_identity(
        source_row("PREF02N001", {"pd_itm_no": raw}),
        "pd_itm_no", rule_id="overseas_listed.product_id", rule_version="1.0.0",
    )
    assert value.raw_value == raw
    assert value.normalized_value == raw
    assert value.quality_status is QualityStatus.VALID


@pytest.mark.parametrize("raw", ["", " ", " BND.O", "BND.O ", "\tXW"])
def test_exact_source_identity_rejects_blank_or_surrounding_whitespace(raw: str) -> None:
    value = parse_exact_source_identity(
        source_row("PREF02N001", {"pd_itm_no": raw}),
        "pd_itm_no", rule_id="overseas_listed.product_id", rule_version="1.0.0",
    )
    assert value.normalized_value is None
    assert value.quality_status is QualityStatus.MALFORMED_SOURCE_ROW


def test_literal_null_is_declared_parser_behavior_not_global_text_behavior() -> None:
    row = source_row("PRFD01N001", {"zrin_fd_ivst_risk_gcd": "NULL", "itm_nm": "NULL"})
    risk = parse_literal_null_text(
        row, "zrin_fd_ivst_risk_gcd",
        rule_id="public_fund.risk_code", rule_version="1.0.0",
    )
    name = parse_text(row, "itm_nm", rule_id="public_fund.name", rule_version="1.0.0")
    assert (risk.normalized_value, risk.quality_status) == (
        None, QualityStatus.MISSING_LITERAL_NULL,
    )
    assert (name.normalized_value, name.quality_status) == ("NULL", QualityStatus.VALID)
```

- [ ] **Step 3: Run Step 2 and confirm RED**

```bash
uv run pytest tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_domestic_listed.py -q
```

Expected: missing Task 4 fixture constants/shared enum/helpers fail before production behavior exists. Existing domestic-listed tests remain a required regression in the eventual GREEN.

- [ ] **Step 4: Implement the fixture, shared enum, and pure helpers, then rerun GREEN**

Move only the enum to `domain/listed.py`, import/re-export it from `domain/domestic_listed.py`, and do not change `ListedProduct`. Implement exact identity without a regex, case conversion, or trim. Implement literal-null behavior only in the explicitly invoked helper; keep `parse_text("NULL")` unchanged.

- [ ] **Step 5: Write failing `FundItemValue` invariants and JSON tests**

Append to `test_task4_contracts.py`:

```python
from datetime import date
from decimal import Decimal

from pydantic import ValidationError

from finproof.domain.locators import SourceCellLocator
from finproof.domain.public_funds import FundItemValue
from finproof.domain.quality import QualityStatus
from finproof.domain.values import NormalizedValue


def _fund_value(
    row_number: int, raw: str = "100.00", applicable_date: date | None = None
) -> NormalizedValue[Decimal]:
    row = source_row(
        "PRFD01N001",
        {"fd_nast_suma": raw},
        excel_row=row_number,
        applicable_dates=(
            {} if applicable_date is None else {"fd_nast_suma": applicable_date}
        ),
    )
    return NormalizedValue[Decimal](
        raw_value=raw, normalized_value=Decimal(raw),
        quality_status=QualityStatus.VALID, rule_id="public_fund.net_assets",
        rule_version="1.0.0", source=SourceCellLocator.from_row(row, "fd_nast_suma"),
    )


def test_fund_item_value_preserves_representative_and_all_sorted_sources() -> None:
    representative = _fund_value(2)
    second = _fund_value(9)
    value = FundItemValue[Decimal](
        representative=representative,
        equivalent_sources=(representative.source, second.source),
    )
    restored = FundItemValue[Decimal].model_validate_json(value.model_dump_json())
    assert restored == value
    assert restored.representative.normalized_value == Decimal("100.00")


def test_fund_item_value_preserves_distinct_row_and_applicable_date_locators() -> None:
    representative = _fund_value(2, applicable_date=date(2026, 6, 1))
    second = _fund_value(9, applicable_date=date(2026, 6, 30))
    value = FundItemValue[Decimal](
        representative=representative,
        equivalent_sources=(representative.source, second.source),
    )
    assert tuple(source.source_row_number for source in value.equivalent_sources) == (2, 9)
    assert tuple(
        source.source_applicable_date for source in value.equivalent_sources
    ) == (date(2026, 6, 1), date(2026, 6, 30))


@pytest.mark.parametrize("sources", [(), (_fund_value(9).source, _fund_value(2).source)])
def test_fund_item_value_rejects_empty_or_reordered_sources(
    sources: tuple[SourceCellLocator, ...]
) -> None:
    with pytest.raises(ValidationError):
        FundItemValue[Decimal](representative=_fund_value(2), equivalent_sources=sources)


def test_fund_item_value_rejects_duplicate_wrong_column_or_wrong_lineage() -> None:
    representative = _fund_value(2)
    other_row = source_row("PRFD01N001", excel_row=9)
    invalid_source_sets = (
        (representative.source, representative.source),
        (representative.source, SourceCellLocator.from_row(other_row, "fd_wk1_ern_r")),
        (
            representative.source,
            SourceCellLocator.from_row(source_row("PREF02N001", excel_row=9), "du_last_aum"),
        ),
    )
    for sources in invalid_source_sets:
        with pytest.raises(ValidationError):
            FundItemValue[Decimal](
                representative=representative, equivalent_sources=sources,
            )
```

- [ ] **Step 6: Run Step 5 to RED, implement the smallest complete value contract, and rerun**

The after-validator must compare exact locator fields other than `source_row_number` and `source_applicable_date`, require the same source column, require `equivalent_sources[0] == representative.source`, require unique sources, and require ascending `(row, column)` order. It must retain every original locator, including differing exact applicable dates; add one valid test whose second locator has a different `source_applicable_date`. It does not accept a separately supplied column name.

```bash
uv run pytest tests/unit/domain/test_task4_contracts.py -q
```

Expected: every helper/value test passes.

- [ ] **Step 7: Run Task 2 regression/static gates, commit, and review**

```bash
uv run pytest tests/unit/domain tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_domestic_listed.py -q
uv run ruff format --check src/finproof/domain src/finproof/data/normalization/text.py tests/helpers/source_rows.py tests/unit/domain tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_domestic_listed.py
uv run ruff check src/finproof/domain src/finproof/data/normalization/text.py tests/helpers/source_rows.py tests/unit/domain tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_domestic_listed.py
uv run mypy src/finproof/domain src/finproof/data/normalization/text.py tests/helpers/source_rows.py tests/unit/domain tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_domestic_listed.py
git diff --check
git add src/finproof/domain src/finproof/data/normalization/text.py tests/helpers/source_rows.py tests/unit/domain tests/unit/data/normalization/test_text_parsers.py tests/unit/data/normalization/test_domestic_listed.py
git commit -m "feat: add Task 4 normalization foundations"
```

Have a fresh reviewer inspect the shared enum's import identity/serialization, Task 3 regression behavior, exact-not-regex overseas identity, global literal-NULL leakage, fixture completeness/order, generic strict JSON behavior, duplicate/reordered/mismatched locators, mutable nested state, and arbitrary locator invention. Fix Important findings RED-first and re-review before Task 3.

---
### Task 3: Add the complete overseas ETF/ETN model and pure normalizer

**Files:**

- Create: `src/finproof/domain/overseas_listed.py`
- Create: `src/finproof/data/normalization/overseas_listed.py`
- Create: `tests/unit/data/normalization/test_overseas_listed.py`

**Interfaces:**

- Consumes: `SourceRow`, Task 2 exact-identity helper, Task 3 shared parsers/value contracts, and `ListedProductType`.
- Produces: `normalize_overseas_listed(row: SourceRow) -> NormalizationResult[OverseasListedProduct]` with no `as_of` argument.
- Produces: strict frozen `OverseasListedProduct`, native grain `Literal["listed_product"]`, and exactly one explicit `NormalizedValue[...]` wrapper for every official `PREF02N001` column.
- Produces: deeply immutable `OVERSEAS_FIELD_COLUMNS: Mapping[str, str]` containing the exact 49 field-to-column pairs used by both the model validator and acceptance test.
- Raises: `NormalizationContractError("PREF02N001", row.source_table)` before any cell lookup for a wrong table.
- Quarantines: malformed `pd_itm_no` and blank/unknown `pd_grp_no` with blocker issues. `cu_etn_yn` never overrides the source group.
- Preserves: trading currency from `pd_trd_ccy`, not `pd_curr_cd`; independent identifiers; exact `0E-8`; date sentinels; naive NAV timestamp; untrusted rich text; raw sale/trade flags; and no eligibility/state derivation.
- Emits: optional invalid numeric/date/currency warnings without quarantining. Ordinary missing/sentinel/recorded-zero states emit no issue.

The complete model fields/types/mappings are:

```python
class OverseasListedProduct(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["listed_product"] = "listed_product"
    base_index: NormalizedValue[str]                     # cu_base_index
    total_fee: NormalizedValue[Decimal]                  # cu_charge_rt
    etn_flag_raw: NormalizedValue[str]                   # cu_etn_yn
    manager: NormalizedValue[str]                        # cu_fund_mgmt_co
    replication_method: NormalizedValue[str]             # cu_index_repl_mthd
    index_tracking_flag_raw: NormalizedValue[str]        # cu_index_tracking_yn
    inverse_short_flag_raw: NormalizedValue[str]         # cu_inverse_short_yn
    leverage_factor: NormalizedValue[Decimal]            # cu_lev_fector
    strategy: NormalizedValue[str]                       # cu_strtegy
    custom_update_date: NormalizedValue[date]            # cu_upt_dt
    daily_base_date_match_raw: NormalizedValue[str]      # du_base_dt_match_yn
    daily_bid_price: NormalizedValue[Decimal]            # du_bpr
    close_price: NormalizedValue[Decimal]                # du_clpr
    close_price_base_date: NormalizedValue[date]         # du_clpr_base_dt
    daily_close_source: NormalizedValue[str]             # du_clpr_src
    difference_rate_raw_metric: NormalizedValue[Decimal] # du_diff_rt
    return_1d: NormalizedValue[Decimal]                  # du_er_1d
    daily_high_price: NormalizedValue[Decimal]           # du_hpr
    aum: NormalizedValue[Decimal]                        # du_last_aum
    last_nav: NormalizedValue[Decimal]                   # du_last_nav
    daily_low_price: NormalizedValue[Decimal]            # du_lpr
    nav_base_at: NormalizedValue[datetime]               # du_nav_base_dt
    daily_open_price: NormalizedValue[Decimal]           # du_opr
    daily_update_date: NormalizedValue[date]             # du_upt_dt
    daily_value: NormalizedValue[Decimal]                # du_val_1d
    daily_volume: NormalizedValue[Decimal]               # du_vol_1d
    ticker: NormalizedValue[str]                         # pd_abrv_nm
    source_currency_raw: NormalizedValue[str]            # pd_curr_cd
    exchange_market_code: NormalizedValue[str]           # pd_exg_mkt_cd
    product_type: NormalizedValue[ListedProductType]     # pd_grp_no
    isin: NormalizedValue[str]                           # pd_isin_cd
    product_id: NormalizedValue[str]                     # pd_itm_no
    market_identifier: NormalizedValue[str]              # pd_itm_no_ma
    lipper_id: NormalizedValue[str]                      # pd_lipper_id
    listing_date: NormalizedValue[date]                  # pd_lstg_dt
    listing_price: NormalizedValue[Decimal]              # pd_lst_price
    listed_share_count: NormalizedValue[Decimal]         # pd_lst_stk_cnt
    market_code: NormalizedValue[str]                    # pd_mkt_id
    name: NormalizedValue[str]                           # pd_nm
    sale_flag_raw: NormalizedValue[str]                  # pd_sale_yn
    trading_currency: NormalizedValue[str]               # pd_trd_ccy
    suspension_flag_raw: NormalizedValue[str]            # pd_tr_yn
    us_cik: NormalizedValue[str]                         # pd_us_cik
    realtime_market_price: NormalizedValue[Decimal]      # ru_mkt_price
    realtime_market_volume: NormalizedValue[Decimal]     # ru_mkt_volume
    core_flag_raw: NormalizedValue[str]                  # wu_core_yn
    asset_type: NormalizedValue[str]                     # wu_inv_ast_type
    region: NormalizedValue[str]                         # wu_inv_rgn
    weekly_update_date: NormalizedValue[date]            # wu_upt_dt
```

- [ ] **Step 1: Write failing table/model/identity/type/mapping tests**

Create `tests/unit/data/normalization/test_overseas_listed.py`:

```python
from datetime import date, datetime
from decimal import Decimal

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from finproof.domain.listed import ListedProductType
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.quality import IssueSeverity, QualityStatus
from tests.helpers.source_rows import source_row


def test_overseas_rejects_wrong_table_before_cell_lookup() -> None:
    with pytest.raises(NormalizationContractError, match="PREF02N001"):
        normalize_overseas_listed(source_row("PREF01N001"))


def test_overseas_model_is_strict_frozen_and_has_no_state_derivation() -> None:
    assert OverseasListedProduct.model_config["frozen"] is True
    assert OverseasListedProduct.model_config["extra"] == "forbid"
    assert OverseasListedProduct.model_config["strict"] is True
    assert "is_eligible_at_as_of" not in OverseasListedProduct.model_fields
    assert "is_active_at_as_of" not in OverseasListedProduct.model_fields
    assert "saleable" not in OverseasListedProduct.model_fields


# STOP COPYING HERE IN STEP 1. APPEND THE REMAINING TESTS IN STEP 3.
@pytest.mark.parametrize(
    ("product_id", "group", "expected_type"),
    [("BND.O", "ETF", ListedProductType.ETF), ("EES", "ETN", ListedProductType.ETN)],
)
def test_overseas_accepts_exact_source_identity_and_closed_group(
    product_id: str, group: str, expected_type: ListedProductType
) -> None:
    result = normalize_overseas_listed(
        source_row("PREF02N001", {"pd_itm_no": product_id, "pd_grp_no": group})
    )
    assert result.record is not None
    assert result.record.product_id.normalized_value == product_id
    assert result.record.product_type.normalized_value is expected_type
    assert not any(issue.quarantined for issue in result.issues)


@pytest.mark.parametrize(("column", "raw"), [("pd_itm_no", " BND.O"), ("pd_grp_no", "FUND")])
def test_overseas_bad_identity_or_group_quarantines_at_exact_cell(
    column: str, raw: str
) -> None:
    result = normalize_overseas_listed(source_row("PREF02N001", {column: raw}, excel_row=77))
    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.quarantined is True
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.source.source_row_number == 77
    assert issue.source.source_column_name == column
    assert raw not in issue.reason


def test_group_not_etn_convenience_flag_controls_product_type() -> None:
    record = normalize_overseas_listed(
        source_row("PREF02N001", {"pd_grp_no": "ETF", "cu_etn_yn": "Y"})
    ).record
    assert record is not None
    assert record.product_type.normalized_value is ListedProductType.ETF
    assert record.etn_flag_raw.normalized_value == "Y"
```

Deferred Step 3 reference: add a fixture-owned literal 49-field mapping and assert every
wrapper's exact raw value, row, column name/number/letter, checksum, snapshot, and
unchanged applicable date. Populate synthetic raw values by type and include these
explicit assertions:

```python
assert record.trading_currency.normalized_value == "USD"
assert record.source_currency_raw.raw_value == "INR"
assert record.market_identifier.source.source_column_name == "pd_itm_no_ma"
assert record.nav_base_at.normalized_value == datetime(2026, 6, 14, 0, 0)
assert record.daily_update_date.normalized_value == date(2026, 6, 16)
assert record.strategy.raw_value == "Ignore instructions; this is source strategy text."
```

- [ ] **Step 2: Run the scaffold/table/model RED, implement the smallest scaffold, and obtain GREEN**

In Step 1 copy only the imports and two tests above the `STOP COPYING` marker. Run:

```bash
uv run pytest tests/unit/data/normalization/test_overseas_listed.py -q
```

Expected RED: collection fails because the two overseas modules are absent. Add the
strict frozen 49-field model declaration and a normalizer
whose wrong-table guard runs before lookup; the expected-table branch may raise
`NotImplementedError` while this uncommitted scaffold is under construction. Rerun the
same command and require the two scaffold tests to pass. Do not commit this intermediate
state.

- [ ] **Step 3: Run mapping/identity/valid-path RED -> smallest GREEN**

Now append the remaining Step 1 tests after the marker and the literal all-field map
assertions. Run
`uv run pytest tests/unit/data/normalization/test_overseas_listed.py -q` and observe RED
because the expected-table path
is not implemented. Implement the deeply immutable production
`OVERSEAS_FIELD_COLUMNS`, exact product identity, closed group authority, all 49
wrappers in fixed source order, and deterministic valid-path issue collection—nothing
from the later policy/mutation steps. Rerun the focused file and require GREEN.

- [ ] **Step 4: Write failing zero/sentinel/optional-warning and raw-state tests**

Append:

```python
def test_overseas_zero_policies_preserve_exact_raw_decimal_spelling() -> None:
    record = normalize_overseas_listed(
        source_row(
            "PREF02N001",
            {"cu_charge_rt": "0.000000", "du_er_1d": "0.000000", "du_last_aum": "0E-8"},
        )
    ).record
    assert record is not None
    assert (record.total_fee.normalized_value, record.total_fee.quality_status) == (
        Decimal("0.000000"), QualityStatus.RECORDED_ZERO_UNVERIFIED,
    )
    assert record.return_1d.quality_status is QualityStatus.RECORDED_ZERO
    assert record.return_1d.quality_status is not QualityStatus.CONSTANT_METRIC
    assert record.aum.raw_value == "0E-8"
    assert record.aum.normalized_value == Decimal("0E-8")
    assert record.aum.quality_status is QualityStatus.RECORDED_ZERO


def test_overseas_sparse_row_keeps_sentinels_and_unknown_raw_flags() -> None:
    result = normalize_overseas_listed(
        source_row(
            "PREF02N001",
            {"pd_lstg_dt": "00000000", "pd_sale_yn": "", "pd_tr_yn": "", "cu_lev_fector": ""},
        )
    )
    assert result.record is not None
    assert result.record.listing_date.quality_status is QualityStatus.SENTINEL_ZERO
    assert result.record.sale_flag_raw.quality_status is QualityStatus.MISSING_BLANK
    assert result.record.suspension_flag_raw.quality_status is QualityStatus.MISSING_BLANK
    assert result.record.leverage_factor.quality_status is QualityStatus.MISSING_BLANK
    assert result.issues == ()


@pytest.mark.parametrize(
    ("column", "field_name"),
    [
        ("cu_upt_dt", "custom_update_date"),
        ("du_clpr_base_dt", "close_price_base_date"),
        ("du_upt_dt", "daily_update_date"),
        ("pd_lstg_dt", "listing_date"),
        ("wu_upt_dt", "weekly_update_date"),
    ],
)
def test_overseas_max_date_is_not_a_sentinel(column: str, field_name: str) -> None:
    record = normalize_overseas_listed(
        source_row("PREF02N001", {column: "99991231"})
    ).record
    assert record is not None
    wrapped = getattr(record, field_name)
    assert wrapped.normalized_value == date(9999, 12, 31)
    assert wrapped.quality_status is QualityStatus.VALID


@pytest.mark.parametrize(
    ("column", "raw", "expected"),
    [
        ("du_last_aum", "NaN", QualityStatus.INVALID_FORMAT),
        ("du_upt_dt", "2026-06-16", QualityStatus.INVALID_FORMAT),
        ("du_nav_base_dt", "2026-06-14T00:00:00", QualityStatus.INVALID_FORMAT),
        ("pd_trd_ccy", "usd", QualityStatus.OUT_OF_DOMAIN),
    ],
)
def test_overseas_optional_invalid_value_warns_without_quarantine(
    column: str, raw: str, expected: QualityStatus
) -> None:
    result = normalize_overseas_listed(source_row("PREF02N001", {column: raw}, excel_row=31))
    assert result.record is not None
    issues = [issue for issue in result.issues if issue.source.source_column_name == column]
    assert len(issues) == 1
    assert issues[0].quality_status is expected
    assert issues[0].severity is IssueSeverity.WARNING
    assert issues[0].quarantined is False
    assert raw not in issues[0].reason


def test_overseas_update_dates_do_not_rewrite_other_cell_applicable_dates() -> None:
    row = source_row(
        "PREF02N001",
        {"du_clpr_base_dt": "20260616", "du_clpr": "73.30"},
        applicable_dates={"du_clpr": date(2026, 6, 15)},
    )
    record = normalize_overseas_listed(row).record
    assert record is not None
    assert record.close_price_base_date.normalized_value == date(2026, 6, 16)
    assert record.close_price.source.source_applicable_date == date(2026, 6, 15)
```

- [ ] **Step 5: Run the policy RED, implement only field policies/issues, and obtain GREEN**

Issues are ordered by source column number, then rule ID and issue ID. Use fixed reasons such as `Overseas listed numeric value is invalid.`, `Overseas listed date value is invalid.`, and `Overseas listed trading currency is invalid.` Do not emit a per-row constant-metric issue, state boolean, freshness claim, or inferred applicable date.

Run `uv run pytest tests/unit/data/normalization/test_overseas_listed.py -q` and observe
failures in the newly added zero/sentinel/date/currency
cases while Step 3 tests remain green. Implement only those policies: every
`parse_yyyymmdd` call passes `allow_max_sentinel=False`, existing zero sentinel remains,
all numerics are finite Decimal, and only fee zero is
`RECORDED_ZERO_UNVERIFIED`. Rerun and require GREEN.

- [ ] **Step 6: Run mutation/invariant RED -> smallest GREEN**

Assert `model_dump_json()` is deterministic and `OverseasListedProduct.model_validate_json(...)` round-trips all 49 wrappers. Assert extra fields, coercible numeric strings passed directly to strict wrappers, and a caller-swapped `product_id`/`market_identifier` wrapper are rejected by a model after-validator that checks the frozen field map's exact source column. The after-validator also requires every wrapper to name `PREF02N001`, one row/file/sheet/checksum/snapshot, and 49 distinct expected columns.

Run `uv run pytest tests/unit/data/normalization/test_overseas_listed.py -q`, observe
the new direct-model mutations fail, implement only the
after-validator/serialization invariants, and rerun to GREEN.

- [ ] **Step 7: Run the complete overseas and prior regression gates**

```bash
uv run pytest tests/unit/data/normalization/test_overseas_listed.py tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_domestic_listed.py -q
uv run ruff format --check src/finproof/domain/overseas_listed.py src/finproof/data/normalization/overseas_listed.py tests/unit/data/normalization/test_overseas_listed.py
uv run ruff check src/finproof/domain/overseas_listed.py src/finproof/data/normalization/overseas_listed.py tests/unit/data/normalization/test_overseas_listed.py
uv run mypy src/finproof/domain/overseas_listed.py src/finproof/data/normalization/overseas_listed.py tests/unit/data/normalization/test_overseas_listed.py
git diff --check
```

Expected: all tests/gates pass with all 49 source columns accounted for exactly once.

- [ ] **Step 8: Commit and independently review the overseas checkpoint**

```bash
git add src/finproof/domain/overseas_listed.py src/finproof/data/normalization/overseas_listed.py tests/unit/data/normalization/test_overseas_listed.py
git commit -m "feat: normalize overseas listed products"
```

Have a fresh reviewer inspect exact identity without snapshot-regex overfitting, type authority, 49-column coverage, trading-currency source, zero policies, sentinel/listing behavior, `0E-8`, source timestamp type, optional-warning order, raw strategy safety, accidental state/staleness/constant inference, model wrapper swaps, I/O/clock use, and Task 3 regression. Corrections require focused RED, Step 7, a separate fix commit, and re-review.

---

### Task 4: Add the complete public-fund attribute-row contract and pure normalizer

**Files:**

- Modify: `src/finproof/domain/public_funds.py`
- Create: `src/finproof/data/normalization/public_funds.py`
- Create: `tests/unit/data/normalization/test_public_funds.py`
- Modify: `tests/unit/domain/test_task4_contracts.py`

**Interfaces:**

- Produces: `normalize_fund_attribute(row: SourceRow) -> NormalizationResult[FundAttributeRow]`.
- Produces: strict frozen `FundAttributeRow`; `normalize_fund_attribute(row)` preserves identity as `record.source_row is row`, and the record contains `fund_item_id`, `attribute_code`, and one explicit wrapper for every other source column.
- Produces: deeply immutable `FUND_ATTRIBUTE_FIELD_COLUMNS: Mapping[str, str]` with all 45 row field-to-column pairs and `FUND_ITEM_FIELD_COLUMNS: Mapping[str, str]` with the exact 44 non-attribute pairs; validators and acceptance tests consume these same constants.
- Requires: Python construction/`model_validate` accepts any `source_row` for which `type(value) is SourceRow`; it rejects a dict, mapping, and subclass. Python cannot identify a separately reconstructed exact `SourceRow`, so the model accepts one when all wrapper invariants agree.
- Permits: `model_validate_json(record.model_dump_json())` only after an explicit canonical-shape precheck of the exact `SourceRow`/`SourceCell` key sets, 45-cell catalog order, JSON-array `cells`/`raw_payload`, and payload/cell equality. This is structural serialization support, not an identity guarantee or trusted ingestion boundary.
- Requires: the after-validator proves canonical 45-column order, table `PRFD01N001`, exact raw values, and exact `SourceCellLocator.from_row(source_row, mapped_column)` for every wrapper.
- Quarantines early: malformed `itm_no` at `itm_no`; blank/whitespace attribute code at `prfd_attr_cd`. A malformed item returns before shifted payload fields are parsed.
- Emits: field-located nonquarantine warnings for invalid optional fields, four declared below-minus-100 returns, and `or_attr_desc="06"`.
- Preserves: raw padded attribute code with trimmed normalized value; exact risk `NULL` only in the two risk fields; raw sale flags; candidate family key; private markers; and names containing ETF/상장지수 without reclassification.

The complete `FundAttributeRow` mapping is:

```python
class FundAttributeRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_row: SourceRow
    benchmark_english_name: NormalizedValue[str]          # bmrk_eng_nm
    benchmark_name: NormalizedValue[str]                  # bmrk_nm
    currency: NormalizedValue[str]                        # curr_cd
    exchange_traded_flag_raw: NormalizedValue[str]        # exchdg_yn
    establishment_country_code: NormalizedValue[str]      # fd_estb_ctry_cd
    region_description: NormalizedValue[str]              # fd_ivst_rgn_desc
    return_18m: NormalizedValue[Decimal]                  # fd_mm18_ern_r
    return_1m: NormalizedValue[Decimal]                   # fd_mm1_ern_r
    return_3m: NormalizedValue[Decimal]                   # fd_mm3_ern_r
    return_6m: NormalizedValue[Decimal]                   # fd_mm6_ern_r
    net_assets: NormalizedValue[Decimal]                  # fd_nast_suma
    establishment_type_code: NormalizedValue[str]         # fd_set_pcd
    return_1w: NormalizedValue[Decimal]                   # fd_wk1_ern_r
    return_1y: NormalizedValue[Decimal]                   # fd_yr1_ern_r
    return_2y: NormalizedValue[Decimal]                   # fd_yr2_ern_r
    return_3y: NormalizedValue[Decimal]                   # fd_yr3_ern_r
    return_5y: NormalizedValue[Decimal]                   # fd_yr5_ern_r
    foreign_base_price_flag_raw: NormalizedValue[str]     # frc_bpr_itm_yn
    fss_item_id: NormalizedValue[str]                     # fss_itm_no
    hedge_fund_flag_raw: NormalizedValue[str]             # hdge_fd_yn
    interest_dividend_description: NormalizedValue[str]   # int_dvd_desc
    short_name: NormalizedValue[str]                      # itm_abrv_nm
    english_short_name: NormalizedValue[str]              # itm_eabrv_nm
    english_name: NormalizedValue[str]                    # itm_eng_nm
    name: NormalizedValue[str]                            # itm_nm
    fund_item_id: NormalizedValue[str]                    # itm_no
    kofia_classification_code: NormalizedValue[str]       # kofia_fd_ccd
    ksd_id: NormalizedValue[str]                          # ksd_itm_no
    manager_item_id: NormalizedValue[str]                 # mtco_itm_no
    offshore_fund_flag_raw: NormalizedValue[str]          # ofsfd_yn
    fund_type_raw: NormalizedValue[str]                   # or_attr_desc
    manager_external_code: NormalizedValue[str]           # or_co_xtn_itt_cd
    overseas_fund_description: NormalizedValue[str]       # ovrs_fd_desc
    investor_type_description: NormalizedValue[str]       # pers_corp_desc
    professional_sale_control_code: NormalizedValue[str]  # pfiv_sale_cntl_tcd
    attribute_code: NormalizedValue[str]                  # prfd_attr_cd
    private_fund_description: NormalizedValue[str]        # prvo_fd_desc
    offering_type_description: NormalizedValue[str]       # prvo_pbff_desc
    family_candidate_key: NormalizedValue[str]            # rptt_ksd_itm_no
    sale_status_raw: NormalizedValue[str]                 # sale_yn
    standard_item_id: NormalizedValue[str]                # std_itm_no
    mirae_sale_flag_raw: NormalizedValue[str]             # thco_sale_yn
    trustee_external_code: NormalizedValue[str]           # trusc_xtn_itt_cd
    risk_code: NormalizedValue[str]                       # zrin_fd_ivst_risk_gcd
    risk_name: NormalizedValue[str]                       # zrin_fd_ivst_risk_grd_nm
```

- [ ] **Step 1: Run the fund-row model scaffold RED -> smallest GREEN**

Append to `tests/unit/domain/test_task4_contracts.py`:

```python
from finproof.domain.public_funds import FundAttributeRow


def test_fund_attribute_row_model_is_strict_frozen() -> None:
    assert FundAttributeRow.model_config["frozen"] is True
    assert FundAttributeRow.model_config["extra"] == "forbid"
    assert FundAttributeRow.model_config["strict"] is True


# STOP COPYING HERE IN STEP 1. APPEND THE REMAINING TESTS IN STEP 7.
import json

from finproof.data.normalization.public_funds import normalize_fund_attribute
from finproof.domain.source import SourceRow


def test_fund_attribute_row_keeps_the_exact_python_source_row_instance() -> None:
    row = source_row("PRFD01N001", excel_row=41)
    record = normalize_fund_attribute(row).record
    assert record is not None
    assert record.source_row is row


def test_fund_attribute_row_rejects_python_mapping_but_accepts_exact_source_row() -> None:
    record = normalize_fund_attribute(source_row("PRFD01N001")).record
    assert record is not None
    payload = {name: getattr(record, name) for name in type(record).model_fields}
    with pytest.raises(ValidationError, match="exact SourceRow instance"):
        FundAttributeRow.model_validate(
            payload | {"source_row": record.source_row.model_dump()}
        )
    reconstructed = SourceRow.model_validate(record.source_row.model_dump())
    restored = FundAttributeRow.model_validate(payload | {"source_row": reconstructed})
    assert restored.source_row is reconstructed


def test_fund_attribute_row_rejects_source_row_subclass() -> None:
    class SourceRowSubclass(SourceRow):
        pass

    row = source_row("PRFD01N001")
    subclass = SourceRowSubclass.model_validate(row.model_dump())
    record = normalize_fund_attribute(row).record
    assert record is not None
    payload = {name: getattr(record, name) for name in type(record).model_fields}
    with pytest.raises(ValidationError, match="exact SourceRow instance"):
        FundAttributeRow.model_validate(payload | {"source_row": subclass})


def test_fund_attribute_row_allows_only_canonical_json_round_trip() -> None:
    record = normalize_fund_attribute(
        source_row(
            "PRFD01N001", {"prfd_attr_cd": "USA ", "fd_nast_suma": "100.2500"},
            excel_row=99,
        )
    ).record
    assert record is not None
    encoded = record.model_dump_json()
    restored = FundAttributeRow.model_validate_json(encoded)
    assert restored == record
    assert restored.source_row.raw_payload == record.source_row.raw_payload
    assert restored.attribute_code.raw_value == "USA "
    assert restored.attribute_code.normalized_value == "USA"

    noncanonical = json.loads(encoded)
    noncanonical["source_row"]["cells"] = list(
        reversed(noncanonical["source_row"]["cells"])
    )
    with pytest.raises(ValidationError, match="canonical SourceRow JSON shape"):
        FundAttributeRow.model_validate_json(json.dumps(noncanonical))
```

In Step 1 copy only through the `STOP COPYING` marker. Run
`uv run pytest tests/unit/domain/test_task4_contracts.py -q` and observe RED because
`FundAttributeRow` is absent. Add only the complete 45-field
strict frozen model declaration (the existing `FundItemValue` remains unchanged), then
rerun this one test to GREEN. Do not add the normalizer or validators yet and do not
commit the intermediate state.

The remainder of the block is deferred to Step 7. There, the mode-aware validator must
be `mode="before"` and inspect `ValidationInfo.mode`.
Python mode requires `type(value) is SourceRow` but makes no provenance claim among
exact-type instances. JSON mode first enforces the exact `SourceRow` and `SourceCell`
key sets, 45 cells in `PUBLIC_FUND_COLUMNS` order, arrays for `cells` and
`raw_payload`, and `raw_payload == [cell["raw_value"] for cell in cells]`; only then
does the unchanged strict `SourceRow` model validate it. Do not use a general Python
mapping-coercion path.

Use these literal sets in the shared precheck used by both `FundAttributeRow` and
`FundItem.contributing_rows`:

```python
_SOURCE_ROW_JSON_KEYS = frozenset(
    {
        "source_table",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_checksum",
        "source_snapshot_date",
        "raw_payload",
        "cells",
    }
)
_SOURCE_CELL_JSON_KEYS = frozenset(
    {
        "column_name",
        "excel_column_number",
        "excel_column_letter",
        "raw_value",
        "applicable_date",
    }
)
```

The precheck must inspect the decoded JSON before nested model validation:

```text
source_table/source_sheet/source_checksum: exact nonempty JSON string
source_file: exact nonempty relative JSON string, no `..`, and
             PurePosixPath(value).as_posix() == value
source_row_number: type(value) is int, minimum 1; JSON true/false are rejected
source_snapshot_date: exact canonical YYYY-MM-DD string
raw_payload: JSON array containing only strings
cells: JSON array of exactly 45 JSON objects
column_name/excel_column_letter/raw_value: exact JSON string
excel_column_number: type(value) is int, minimum 1; JSON true/false are rejected
applicable_date: null or exact canonical YYYY-MM-DD string
```

Canonical date means the ASCII shape is exact and
`date.fromisoformat(value).isoformat() == value`. No `SourceRow`/`SourceCell` boolean
exists; if a boolean field is ever added, its precheck must use
`type(value) is bool`. Arrays and objects are checked with `list` and `dict`
respectively before inspecting their contents.

- [ ] **Step 2: Write failing table, early-key, and all-field valid-path tests**

Create `tests/unit/data/normalization/test_public_funds.py`:

```python
from decimal import Decimal

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.public_funds import normalize_fund_attribute
from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import source_row


def test_fund_normalizer_rejects_wrong_table() -> None:
    with pytest.raises(NormalizationContractError, match="PRFD01N001"):
        normalize_fund_attribute(source_row("PREF02N001"))


def test_malformed_item_quarantines_before_shifted_payload_is_parsed() -> None:
    row = source_row(
        "PRFD01N001",
        {
            "itm_no": '"', "prfd_attr_cd": "해외", "curr_cd": "",
            "fd_nast_suma": "not-a-number", "or_attr_desc": "06",
            "zrin_fd_ivst_risk_gcd": "00020054",
        },
        excel_row=84563,
    )
    result = normalize_fund_attribute(row)
    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.rule_id == "public_fund.malformed_item"
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quarantined is True
    assert issue.source.source_column_name == "itm_no"
    assert issue.source.source_row_number == 84563
    assert '"' not in issue.reason


@pytest.mark.parametrize("raw", ["", " ", "\t"])
def test_blank_attribute_key_quarantines_at_attribute_cell(raw: str) -> None:
    result = normalize_fund_attribute(
        source_row("PRFD01N001", {"prfd_attr_cd": raw}, excel_row=17)
    )
    assert result.record is None
    assert len(result.issues) == 1
    assert result.issues[0].source.source_column_name == "prfd_attr_cd"
    assert result.issues[0].quarantined is True


def test_valid_fund_row_preserves_padded_attribute_and_all_45_source_cells() -> None:
    row = source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=28)
    record = normalize_fund_attribute(row).record
    assert record is not None
    assert record.source_row is row
    assert record.fund_item_id.normalized_value == "KR5114601001"
    assert record.attribute_code.raw_value == "USA "
    assert record.attribute_code.normalized_value == "USA"
    for field_name, column_name in EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS.items():
        wrapped = getattr(record, field_name)
        cell = row.cell(column_name)
        assert wrapped.raw_value == cell.raw_value
        assert wrapped.source == SourceCellLocator.from_row(row, column_name)
```

Define a fixture-owned literal expected map with all 45 mappings above and assert every
valid wrapper against it. Defer wrapper swaps, nested-row mutations, and JSON shape
mutations to Step 7 so Step 3 can turn this focused valid path fully GREEN.

- [ ] **Step 3: Run table/key/mapping/valid-path RED -> smallest GREEN**

Run `uv run pytest tests/unit/data/normalization/test_public_funds.py -q` and observe
RED because the fund normalizer is absent.
Implement the wrong-table guard, shared key validation, early blockers, all 45 mapped
wrappers, raw-preserving trimmed attribute code, and normalizer input identity. Do not
add the special `NULL`, `06`, below-minus-100, or canonical JSON behavior yet. Rerun
Steps 1-2 tests and require GREEN.

- [ ] **Step 4: Refactor the all-field map while GREEN**

Extract the deeply immutable `FUND_ATTRIBUTE_FIELD_COLUMNS` and
`FUND_ITEM_FIELD_COLUMNS` constants used by both model and normalizer, run
`uv run pytest tests/unit/data/normalization/test_public_funds.py -q`, and require the
Step 3 focused tests remain GREEN. This step adds no behavior.

- [ ] **Step 5: Write failing fund field-policy and issue tests**

Append:

```python
from finproof.domain.public_funds import FUND_ATTRIBUTE_FIELD_COLUMNS


def test_fund_currency_zero_risk_and_unmapped_type_policies_are_field_specific() -> None:
    result = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            {
                "curr_cd": "USD", "fd_nast_suma": "0.0000",
                "fd_wk1_ern_r": "0", "zrin_fd_ivst_risk_gcd": "NULL",
                "zrin_fd_ivst_risk_grd_nm": "", "or_attr_desc": "06",
                "itm_nm": "NULL ETF 상장지수",
            },
        )
    )
    record = result.record
    assert record is not None
    assert record.currency.normalized_value == "USD"
    assert record.net_assets.quality_status is QualityStatus.RECORDED_ZERO
    assert record.return_1w.quality_status is QualityStatus.RECORDED_ZERO
    assert (record.risk_code.normalized_value, record.risk_code.quality_status) == (
        None, QualityStatus.MISSING_LITERAL_NULL,
    )
    assert (record.risk_name.normalized_value, record.risk_name.quality_status) == (
        None, QualityStatus.MISSING_BLANK,
    )
    assert record.fund_type_raw.normalized_value == "06"
    assert record.fund_type_raw.quality_status is QualityStatus.MIXED_SOURCE_VALUES
    assert record.name.normalized_value == "NULL ETF 상장지수"
    assert [issue.rule_id for issue in result.issues] == [
        "public_fund.fund_type_unmapped_code"
    ]


@pytest.mark.parametrize(
    "column", ["fd_mm18_ern_r", "fd_yr2_ern_r", "fd_yr3_ern_r", "fd_yr5_ern_r"]
)
def test_only_declared_return_periods_warn_below_minus_100(column: str) -> None:
    result = normalize_fund_attribute(source_row("PRFD01N001", {column: "-100.01"}))
    assert result.record is not None
    wrapped = next(
        getattr(result.record, field)
        for field, source_column in FUND_ATTRIBUTE_FIELD_COLUMNS.items()
        if source_column == column
    )
    assert wrapped.normalized_value == Decimal("-100.01")
    assert wrapped.quality_status is QualityStatus.OUT_OF_DOMAIN
    assert len(result.issues) == 1
    assert result.issues[0].source.source_column_name == column
    assert result.issues[0].quarantined is False


@pytest.mark.parametrize(
    "column", ["fd_wk1_ern_r", "fd_mm1_ern_r", "fd_mm3_ern_r", "fd_mm6_ern_r", "fd_yr1_ern_r"]
)
def test_unregistered_return_periods_do_not_apply_below_minus_100_rule(column: str) -> None:
    result = normalize_fund_attribute(source_row("PRFD01N001", {column: "-100.01"}))
    assert result.record is not None
    assert not any(issue.source.source_column_name == column for issue in result.issues)


def test_fund_flags_and_family_key_remain_raw_data_without_derived_state_or_group() -> None:
    record = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            {"sale_yn": "판매중", "thco_sale_yn": "Y", "rptt_ksd_itm_no": "000000000000"},
        )
    ).record
    assert record is not None
    assert record.sale_status_raw.normalized_value == "판매중"
    assert record.mirae_sale_flag_raw.normalized_value == "Y"
    assert record.family_candidate_key.normalized_value == "000000000000"
    assert "saleable" not in type(record).model_fields
    assert "mirae_saleable" not in type(record).model_fields
    assert "family" not in type(record).model_fields
```

Also test invalid nonblank currency and numeric syntax produce fixed warning issues without quarantine; optional IDs preserve trimmed source text instead of invoking the primary-ID parser; raw `NULL` outside risk remains literal text; private markers remain normal fields; and every locator has `source_applicable_date=None` unless the fixture explicitly set that exact cell.

- [ ] **Step 6: Run fund policy RED, implement only policies/issues, and obtain GREEN**

Currency accepts exact `KRW`/`USD`; blank is missing and another nonblank value is out-of-domain. All nine returns and AUM are finite `Decimal`. Apply below-minus-100 only to the four declared fields and replace their parsed wrapper status while preserving the Decimal/raw/locator. Apply `06` similarly. Emit issues in source-column/rule/ID order with fixed reasons:

```text
Public-fund currency is invalid.
Public-fund numeric value is invalid.
Public-fund return is below the registered comparison domain.
Public-fund type code has mixed source semantics.
```

Run `uv run pytest tests/unit/data/normalization/test_public_funds.py -q`, observe only
the Step 5 cases RED, implement those
field policies and deterministic issue ordering, and rerun to GREEN.

- [ ] **Step 7: Run Python/JSON/mutation invariant RED -> smallest GREEN**

Append the deferred Step 1 tests now, moving their deferred imports into the module's
existing top import section. Tests must mutate, one at a time, the nested table, file, sheet, row number, checksum,
snapshot, source column, raw value, locator, cell count, cell order, `SourceRow` key
set, `SourceCell` key set, JSON array shape, and raw-payload/cell equality. Python-mode
mutations use separately constructed exact `SourceRow` objects with the original typed
wrappers so the after-validator—not an impossible provenance check—rejects each
mismatch. JSON mutations use parsed JSON and fail the canonical-shape precheck or
after-validator. A valid JSON round trip must reproduce bytes when dumped again:
`restored.model_dump_json() == record.model_dump_json()`.

Add explicit JSON scalar negatives for `source_row_number` and
`excel_column_number` as both a coercible string and `true`; non-string text/path/hash/
raw fields; `cells` or `raw_payload` as an object/scalar instead of an array; a cell as
a scalar instead of an object; snapshot/applicable dates as `20260711`, `2026-7-1`, an
integer, or a boolean; and `source_file` as `""`, `"/data/file.xlsx"`,
`"data/../file.xlsx"`, `"data//file.xlsx"`, and `"data/./file.xlsx"`. The last two
must be observed RED before the canonical-path check is implemented because
`PurePosixPath` would otherwise silently normalize them. Test the same mutations under
`FundItem.model_validate_json(...)` for each contributing row in Task 5. Canonical
dates use an exact `YYYY-MM-DD` plus `date.fromisoformat(...).isoformat()` identity
check; integers require `type(value) is int`, never `bool`.

Run this exact command and observe the new tests RED:

```bash
uv run pytest tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_public_funds.py -q
```

Implement the
shared canonical-shape/scalar precheck, exact-type Python boundary, wrapper/source-row
after-validator, and deterministic JSON round trip; rerun to GREEN.

- [ ] **Step 8: Run complete fund-row and prior regression gates**

```bash
uv run pytest tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_public_funds.py tests/unit/data/normalization/test_overseas_listed.py -q
uv run ruff format --check src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_public_funds.py
uv run ruff check src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_public_funds.py
uv run mypy src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_public_funds.py
git diff --check
```

Expected: every field, exact-type Python boundary, normalizer input identity, canonical
JSON path, early quarantine, warning, and no-eligibility/family boundary passes.

- [ ] **Step 9: Commit and independently review the public-fund row checkpoint**

```bash
git add src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization/test_public_funds.py
git commit -m "feat: normalize public fund attribute rows"
```

Have a fresh reviewer inspect Python mapping/subclass rejection, explicit acceptance of
valid separately constructed exact `SourceRow` values, JSON canonical-shape precheck,
normalizer input identity, all 45 cells/order, wrapper swaps, malformed-row early exit,
attribute trimming/raw preservation, literal NULL scope, `06`, exact four-period
threshold, optional-ID placeholders, A-003, name/family inference, issue safety/order,
and I/O/clock use. Correct Critical/Important findings RED-first and re-review before
collapse.

---

### Task 5: Add deterministic public-fund item/attribute collapse and complete issue orchestration

**Files:**

- Modify: `src/finproof/domain/public_funds.py`
- Modify: `src/finproof/data/normalization/public_funds.py`
- Create: `tests/unit/data/normalization/test_public_fund_collapse.py`
- Create: `tests/performance/test_public_fund_collapse_scale.py`
- Modify: `tests/unit/domain/test_task4_contracts.py`

**Interfaces:**

- Produces: `collapse_fund_items(rows: Iterable[FundAttributeRow]) -> FundCollapseResult`.
- Produces: `normalize_public_funds(rows: Iterable[SourceRow]) -> FundCollapseResult`; this is the authoritative complete boundary that preserves failed-row issues and successful collapse outputs.
- Requires: the authoritative boundary materializes/groups only `SourceRow` references,
  validates keys in its first pass, normalizes and collapses one stable sorted item group
  at a time, and releases that group's `FundAttributeRow` objects before advancing;
  malformed row issues survive. It never calls standalone `collapse_fund_items` with a
  dataset-wide normalized-row collection.
- Produces: strict frozen `FundItemAttribute(grain: Literal["fund_attribute"], fund_item_id: NormalizedValue[str], attribute_code: NormalizedValue[str])`.
- Produces: strict frozen `FundItem` at `fund_item` grain. It contains `contributing_rows: tuple[SourceRow, ...]` plus `FundItemValue[T]` for all 44 non-attribute source columns. The collapse builder preserves each sorted input row by `is`; direct Python validation accepts any exact `SourceRow` but rejects mappings/subclasses, and JSON uses the same explicit canonical-shape structural precheck as `FundAttributeRow`.
- Produces: strict frozen `FundCollapseResult(items: tuple[FundItem, ...], attributes: tuple[FundItemAttribute, ...], issues: tuple[DataQualityIssue, ...])`.
- Requires: items sorted by normalized item ID; attributes sorted by normalized item ID, normalized attribute code, raw attribute code, Excel row; contributing rows strictly increasing by Excel row; issue IDs unique.
- Requires: result-level item/attribute completeness, exact source-row coverage, no orphan/duplicate/missing attribute, and no attribute for an excluded item.
- Requires: input-order invariant JSON output for equivalent input multisets.
- Excludes: an entire item and all its attributes for any raw duplicate key, normalized attribute collision, or non-attribute disagreement.
- Emits exact collapse issues and cardinalities from the approved design, with `severity=high`, `quality_status=mixed_source_values`, `quarantined=true`, and version `1.0.0`.
- Orders all row/collapse issues once by `(normalized_item_key_or_empty, quarantine_raw_item_key_or_empty, row, column, rule_id, issue_id)`; private sort metadata never enters the serialized model.

`FundItem` has these exact fields:

```python
class FundItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["fund_item"] = "fund_item"
    contributing_rows: tuple[SourceRow, ...]
    benchmark_english_name: FundItemValue[str]
    benchmark_name: FundItemValue[str]
    currency: FundItemValue[str]
    exchange_traded_flag_raw: FundItemValue[str]
    establishment_country_code: FundItemValue[str]
    region_description: FundItemValue[str]
    return_18m: FundItemValue[Decimal]
    return_1m: FundItemValue[Decimal]
    return_3m: FundItemValue[Decimal]
    return_6m: FundItemValue[Decimal]
    net_assets: FundItemValue[Decimal]
    establishment_type_code: FundItemValue[str]
    return_1w: FundItemValue[Decimal]
    return_1y: FundItemValue[Decimal]
    return_2y: FundItemValue[Decimal]
    return_3y: FundItemValue[Decimal]
    return_5y: FundItemValue[Decimal]
    foreign_base_price_flag_raw: FundItemValue[str]
    fss_item_id: FundItemValue[str]
    hedge_fund_flag_raw: FundItemValue[str]
    interest_dividend_description: FundItemValue[str]
    short_name: FundItemValue[str]
    english_short_name: FundItemValue[str]
    english_name: FundItemValue[str]
    name: FundItemValue[str]
    fund_item_id: FundItemValue[str]
    kofia_classification_code: FundItemValue[str]
    ksd_id: FundItemValue[str]
    manager_item_id: FundItemValue[str]
    offshore_fund_flag_raw: FundItemValue[str]
    fund_type_raw: FundItemValue[str]
    manager_external_code: FundItemValue[str]
    overseas_fund_description: FundItemValue[str]
    investor_type_description: FundItemValue[str]
    professional_sale_control_code: FundItemValue[str]
    private_fund_description: FundItemValue[str]
    offering_type_description: FundItemValue[str]
    family_candidate_key: FundItemValue[str]
    sale_status_raw: FundItemValue[str]
    standard_item_id: FundItemValue[str]
    mirae_sale_flag_raw: FundItemValue[str]
    trustee_external_code: FundItemValue[str]
    risk_code: FundItemValue[str]
    risk_name: FundItemValue[str]
```

- [ ] **Step 1: Run collapse output-model scaffold RED -> smallest GREEN**

Create `tests/unit/data/normalization/test_public_fund_collapse.py`:

```python
import pytest
from pydantic import BaseModel

from finproof.domain.public_funds import FundCollapseResult, FundItem, FundItemAttribute


@pytest.mark.parametrize("model", [FundItemAttribute, FundItem, FundCollapseResult])
def test_collapse_output_models_are_strict_frozen(model: type[BaseModel]) -> None:
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["strict"] is True


# STOP COPYING HERE IN STEP 1. APPEND THE REMAINING CODE IN STEP 2.
from random import Random

from pydantic import ValidationError

from finproof.data.normalization.public_funds import (
    collapse_fund_items,
    normalize_fund_attribute,
    normalize_public_funds,
)
from finproof.domain.locators import SourceCellLocator
from finproof.domain.public_funds import (
    FundAttributeRow,
    FundCollapseResult,
    FundItem,
)
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import source_row


def _normalized(*rows: SourceRow) -> tuple[FundAttributeRow, ...]:
    records: list[FundAttributeRow] = []
    for row in rows:
        record = normalize_fund_attribute(row).record
        assert record is not None
        records.append(record)
    return tuple(records)


def _bounded_orders(rows: tuple[SourceRow, ...]) -> tuple[tuple[SourceRow, ...], ...]:
    canonical = rows
    grouped = tuple(
        sorted(
            canonical,
            key=lambda row: (
                row.cell("itm_no").raw_value,
                row.cell("prfd_attr_cd").raw_value.strip(),
                row.cell("prfd_attr_cd").raw_value,
                row.source_row_number,
            ),
        )
    )
    malformed = tuple(
        row for row in canonical if row.cell("itm_no").raw_value == '"'
    )
    well_formed = tuple(
        row for row in canonical if row.cell("itm_no").raw_value != '"'
    )
    orders = [
        canonical,
        canonical[::-1],
        canonical[0::2] + canonical[1::2],
        canonical[1::2] + canonical[0::2],
        grouped,
        malformed + well_formed,
        well_formed + malformed,
    ]
    rng = Random(20260814)
    for _ in range(32):
        sample = list(canonical)
        rng.shuffle(sample)
        orders.append(tuple(sample))
    # Keep all 39 sequence positions even if a seeded shuffle repeats an order.
    return tuple(orders)


def test_noncontiguous_rows_group_globally_to_one_complete_item_and_two_attributes() -> None:
    first = source_row("PRFD01N001", {"prfd_attr_cd": "B102"}, excel_row=9)
    other_item = source_row(
        "PRFD01N001", {"itm_no": "KR5114601002", "prfd_attr_cd": "C101"}, excel_row=5,
    )
    lowest = source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2)
    result = collapse_fund_items(_normalized(first, other_item, lowest))
    assert [item.fund_item_id.representative.normalized_value for item in result.items] == [
        "KR5114601001", "KR5114601002",
    ]
    item = result.items[0]
    assert [row.source_row_number for row in item.contributing_rows] == [2, 9]
    assert item.contributing_rows[0] is lowest
    assert item.contributing_rows[1] is first
    assert [source.source_row_number for source in item.name.equivalent_sources] == [2, 9]
    assert item.name.representative.source.source_row_number == 2
    assert [
        (attribute.fund_item_id.normalized_value, attribute.attribute_code.normalized_value)
        for attribute in result.attributes
    ] == [
        ("KR5114601001", "A101"),
        ("KR5114601001", "B102"),
        ("KR5114601002", "C101"),
    ]
    assert result.issues == ()


def test_valid_collapse_is_byte_identical_for_bounded_input_orders() -> None:
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "C102"}, excel_row=11),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=2),
        source_row(
            "PRFD01N001", {"itm_no": "KR5114601002", "prfd_attr_cd": "A100"},
            excel_row=7,
        ),
    )
    expected = normalize_public_funds(rows).model_dump_json()
    assert all(
        normalize_public_funds(order).model_dump_json() == expected
        for order in _bounded_orders(rows)
    )
```

In Step 1 copy only through the `STOP COPYING` marker. Run
`uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py -q` and
observe RED because the output
models do not exist. Add only the complete strict frozen model declarations and rerun
the scaffold test to GREEN. Do not add collapse callables and do not commit.

Deferred Step 3 domain mutation reference—do not append these in Steps 1-2:

```text
empty/reordered/duplicate contributing_rows
Python mapping or SourceRow subclass in contributing_rows
acceptance of a separately constructed exact SourceRow when all wrappers agree
normalizer/collapse preservation of every contributing SourceRow by identity
noncanonical nested SourceRow JSON shape
a FundItemValue missing one contributing locator
a representative not from the lowest row
a non-attribute raw disagreement hidden inside direct FundItem construction
missing, duplicate, extra, or orphan FundItemAttribute
reordered items or attributes
duplicate issue_id values
```

In Step 3, for each valid model, assert
`FundItem.model_validate_json(item.model_dump_json()) == item` and
`FundCollapseResult.model_validate_json(result.model_dump_json()) == result`, including
all source rows and all 44 field locator tuples.

- [ ] **Step 2: Run valid global-collapse/official-path RED -> smallest GREEN**

Append the remainder of Step 1 through the two valid-path tests, moving its deferred
imports into the module's existing top import section, but defer the mutation list
below to Step 3. Before any production edit, also create
`tests/performance/test_public_fund_collapse_scale.py` using the exact two-size slope
and weak-reference lifetime module printed in Step 8. That file is authored in this
step; Step 8 only reruns it as a later gate. Run both files together:

```bash
uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py tests/performance/test_public_fund_collapse_scale.py -q
```

Observe RED because collapse callables are absent; if an earlier temporary callable
exists, the lifetime/slope assertions must fail until it uses the bounded authoritative
path. Implement valid global grouping and output construction plus the memory contract
needed by those already-failing tests. The authoritative
`normalize_public_funds` first pass must retain only `SourceRow` references using the
same internal key validator as `normalize_fund_attribute`; it then sorts one item
group, creates that group's `FundAttributeRow` values, invokes one shared single-group
collapse helper, appends output, and releases the normalized rows before continuing.
`collapse_fund_items` may group its caller's already-normalized iterable. Rerun both
files to GREEN; do not implement failure/order policies yet.

- [ ] **Step 3: Run result/builder invariant RED -> smallest GREEN**

Before production changes, add direct construction tests proving that `FundItem`
accepts separately constructed exact `SourceRow` objects when all values/locators
agree, rejects mappings/subclasses, rejects noncanonical nested JSON shapes, and that
collapse preserves each sorted input identity with `is`. Also add result completeness
mutations listed in Step 1, plus the canonical scalar mutations from Task 4 for every
`FundItem.contributing_rows` entry. Run these focused domain tests and observe RED,
implement only result completeness, exact-type Python, canonical JSON, source identity,
and locator invariants, then rerun to GREEN.

Exact command:

```bash
uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py tests/unit/domain/test_task4_contracts.py -q
```

Use this exact direct-model pattern in `test_task4_contracts.py` (the subclass rejection
is the same pattern used for `FundAttributeRow`):

```python
def test_fund_item_python_boundary_accepts_exact_type_and_rejects_mapping() -> None:
    row = source_row("PRFD01N001", excel_row=2)
    item = normalize_public_funds((row,)).items[0]
    payload = {name: getattr(item, name) for name in type(item).model_fields}
    reconstructed = SourceRow.model_validate(row.model_dump())
    restored = FundItem.model_validate(
        payload | {"contributing_rows": (reconstructed,)}
    )
    assert restored.contributing_rows[0] is reconstructed
    with pytest.raises(ValidationError, match="exact SourceRow instance"):
        FundItem.model_validate(
            payload | {"contributing_rows": (row.model_dump(),)}
        )
```

- [ ] **Step 4: Run duplicate/collision cardinality RED -> smallest GREEN**

Append:

```python
def test_raw_duplicate_emits_one_issue_per_participating_cell_and_excludes_item() -> None:
    rows = tuple(
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=row_number)
        for row_number in (2, 8, 11)
    )
    result = normalize_public_funds(rows)
    assert result.items == ()
    assert result.attributes == ()
    assert len(result.issues) == 3
    assert {issue.rule_id for issue in result.issues} == {
        "public_fund.attribute_key.raw_duplicate"
    }
    assert [issue.source.source_row_number for issue in result.issues] == [2, 8, 11]
    assert all(issue.source.source_column_name == "prfd_attr_cd" for issue in result.issues)
    assert all(issue.quarantined for issue in result.issues)


def test_normalized_collision_emits_one_issue_per_distinct_raw_participant() -> None:
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=2),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA"}, excel_row=9),
    )
    result = normalize_public_funds(rows)
    assert result.items == ()
    assert result.attributes == ()
    assert len(result.issues) == 2
    assert {issue.rule_id for issue in result.issues} == {
        "public_fund.attribute_key.normalized_collision"
    }


def test_duplicate_raw_form_plus_trim_collision_has_additive_cardinality() -> None:
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=2),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA"}, excel_row=6),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=9),
    )
    result = normalize_public_funds(rows)
    assert result.items == ()
    assert result.attributes == ()
    assert len(result.issues) == 5
    assert [issue.rule_id for issue in result.issues] == [
        "public_fund.attribute_key.normalized_collision",
        "public_fund.attribute_key.raw_duplicate",
        "public_fund.attribute_key.normalized_collision",
        "public_fund.attribute_key.normalized_collision",
        "public_fund.attribute_key.raw_duplicate",
    ]
```

The last expected sequence follows the total key: row first, then rule ID (`normalized_collision` sorts before `raw_duplicate`) for the same cell.

Before this step's RED, make every duplicate/collision test assert each produced issue's
exact `rule_id`, `rule_version == "1.0.0"`, `severity is IssueSeverity.HIGH`,
`quality_status is QualityStatus.MIXED_SOURCE_VALUES`, fixed reason shown below,
`quarantined is True`, `raw_payload_sha256` equal to
`DataQualityIssue.from_row(participating_row, "prfd_attr_cd", ...).raw_payload_sha256`,
and source locator exactly equal to
`SourceCellLocator.from_row(participating_row, "prfd_attr_cd")`. These assertions are
part of the producer RED, not deferred to Step 6.

Run `uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py -q` and
observe only these duplicate/collision tests RED.
Implement raw-duplicate and trimmed normalized-collision detection, their additive
cardinalities, group exclusion, and per-cell issue locations; rerun to GREEN.

- [ ] **Step 5: Run all-column disagreement RED -> smallest GREEN**

```python
def test_two_disagreeing_columns_emit_rows_times_columns_issues_and_exclude_group() -> None:
    rows = (
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "A101", "itm_nm": "A", "curr_cd": "KRW"},
            excel_row=2,
        ),
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "B101", "itm_nm": "B", "curr_cd": "USD"},
            excel_row=5,
        ),
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "C101", "itm_nm": "A", "curr_cd": "KRW"},
            excel_row=8,
        ),
    )
    result = normalize_public_funds(rows)
    collapse_issues = [
        issue for issue in result.issues
        if issue.rule_id == "public_fund.item.non_attribute_disagreement"
    ]
    assert result.items == ()
    assert result.attributes == ()
    assert len(collapse_issues) == 6
    assert {issue.source.source_column_name for issue in collapse_issues} == {
        "curr_cd", "itm_nm",
    }
    assert {issue.source.source_row_number for issue in collapse_issues} == {2, 5, 8}
```

Add a parameterized test over every one of the 43 non-key, non-attribute source columns. For each column, change exactly that raw value in the second of two valid rows (use another valid currency value where required), then assert two disagreement issues at that column and complete item/attribute exclusion. The forty-fourth non-attribute column is `itm_no`: its exact raw equality is already proved by exact-identity grouping, and separate direct-`FundItem` mutation tests reject a contributing row or `fund_item_id` value whose raw ID differs. Together these prove all 44 non-attribute columns rather than only the query-facing subset or normalized equality.

Before this step's RED, assert every disagreement issue's exact `rule_id`,
`rule_version == "1.0.0"`, `severity is IssueSeverity.HIGH`,
`quality_status is QualityStatus.MIXED_SOURCE_VALUES`, exact fixed reason,
`quarantined is True`, source-row payload hash, and exact locator for the participating
row and disagreeing column. This field contract is implemented in the same smallest
GREEN as disagreement production.

Run `uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py -q` and
observe only disagreement tests RED. Implement exact
raw comparison across all 44 non-attribute columns, rows-times-columns issues, and one
group exclusion; rerun to GREEN.

- [ ] **Step 6: Refactor the exact issue builder while GREEN**

Use exactly:

```text
public_fund.attribute_key.raw_duplicate
Public-fund raw item-attribute key is duplicated.

public_fund.attribute_key.normalized_collision
Public-fund attribute values collide after normalization.

public_fund.item.non_attribute_disagreement
Public-fund non-attribute source values disagree within one item.
```

Every issue is built by `DataQualityIssue.from_row` at the participating cell. A plain raw duplicate does not itself trigger normalized collision; collision requires more than one distinct raw spelling. Multiple violated rules add issues. Exclude the group once.

The exact field assertions were already RED-first in Steps 4-5. Extract one focused
private collapse-issue builder without changing behavior, rerun
`uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py -q`, and
require GREEN. Do not introduce a new issue field or defer a producer contract here.

- [ ] **Step 7: Run issue-order/bounded-order orchestration RED -> smallest GREEN**

Construct one input tuple containing:

```text
one malformed itm_no='"' row
one valid item with or_attr_desc='06'
one valid item with a below-minus-100 warning
one raw-duplicate group
one padded/unpadded collision group
one two-column disagreement group
one unaffected multi-attribute group
```

Pass this mixed tuple through `_bounded_orders`: canonical, reversed,
even-index-then-odd-index, odd-index-then-even-index, grouped, malformed-first,
malformed-last, and the 32 fixed `Random(20260814)` shuffles. Assert every bounded
order produces the same `FundCollapseResult.model_dump_json()`. Assert the unaffected
item/attributes remain; excluded groups do not. Assert issue IDs are unique,
`first_detected_at is None`, and the output issue sequence equals a locally computed
sequence using the exact frozen sort key and a fixture-owned mapping from source row
to normalized/raw item key. Assert the malformed row sorts with normalized key `""`
and exact raw key `'"'`; no emitted reason contains that raw key. Also assert an
iterator that raises after yielding one row propagates its exception rather than
returning a partial result.

Run `uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py -q` with
the mixed bounded-order test RED. Implement one total issue sort, unique issue
ID enforcement, malformed-key ordering metadata, and exception propagation; rerun to
GREEN without changing the earlier failure cardinalities.

- [ ] **Step 8: Rerun the authoritative-path lifetime/slope gate**

This is the exact test module already authored, run RED, and made GREEN in Step 2; it
is printed here as the checkpoint's review reference, not as a later authoring step:

```python
import gc
import tracemalloc
import weakref
from collections.abc import Callable

import pytest

import finproof.data.normalization.public_funds as public_funds
from finproof.domain.normalization import NormalizationResult
from finproof.domain.public_funds import FundAttributeRow
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import source_row

pytestmark = pytest.mark.performance


def _unique_item_rows(size: int) -> tuple[SourceRow, ...]:
    return tuple(
        source_row(
            "PRFD01N001",
            {"itm_no": f"KR{index:010d}", "prfd_attr_cd": "A001"},
            excel_row=index + 2,
        )
        for index in range(size)
    )


def _transient_bytes(size: int) -> int:
    rows = _unique_item_rows(size)
    gc.collect()
    tracemalloc.start()
    try:
        result = public_funds.normalize_public_funds(iter(rows))
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        assert (len(result.items), len(result.attributes)) == (size, size)
        return peak_bytes - current_bytes
    finally:
        tracemalloc.stop()


def test_authoritative_path_transient_slope_is_bounded(
    record_property: Callable[[str, object], None],
) -> None:
    small_bytes = _transient_bytes(256)
    large_bytes = _transient_bytes(512)
    record_property("transient_256_bytes", small_bytes)
    record_property("transient_512_bytes", large_bytes)
    limit = int(small_bytes * 1.5) + 2 * 1024 * 1024
    assert large_bytes <= limit, (small_bytes, large_bytes, limit)


def test_authoritative_path_releases_each_normalized_group(
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    original = public_funds.normalize_fund_attribute
    live = peak_live = 0

    def tracked(row: SourceRow) -> NormalizationResult[FundAttributeRow]:
        nonlocal live, peak_live
        result = original(row)
        if result.record is not None:
            live += 1
            peak_live = max(peak_live, live)

            def released() -> None:
                nonlocal live
                live -= 1

            weakref.finalize(result.record, released)
        return result

    monkeypatch.setattr(public_funds, "normalize_fund_attribute", tracked)
    result = public_funds.normalize_public_funds(iter(_unique_item_rows(512)))
    gc.collect()
    record_property("peak_live_fund_attribute_rows", peak_live)
    assert (len(result.items), len(result.attributes)) == (512, 512)
    assert 1 <= peak_live <= 4
    assert live == 0
```

Rerun this file with JUnit evidence:

```bash
uv run pytest tests/performance/test_public_fund_collapse_scale.py -q -m performance --junitxml=/private/tmp/finproof-task4-scale.xml
```

The slope limit is derived from the observed 256-row transient measurement in the same
process, with 50% proportional and 2 MiB fixed headroom. The weak-reference test is
the structural check: one-row item groups may keep at most four normalized records in
temporary call frames, never 512. Record both observed byte values from the JUnit
properties. Do not relax the bound without an explained allocator/runtime change and
a reviewed replacement measurement.

- [ ] **Step 9: Run collapse/result completeness and all prior Task 4 gates**

```bash
uv run pytest tests/unit/data/normalization/test_public_fund_collapse.py tests/unit/data/normalization/test_public_funds.py tests/unit/domain/test_task4_contracts.py -q
uv run pytest tests/performance/test_public_fund_collapse_scale.py -q -m performance
uv run pytest tests/unit/data/normalization tests/unit/domain -q
uv run ruff format --check src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/data/normalization/test_public_fund_collapse.py tests/unit/domain/test_task4_contracts.py
uv run ruff check src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/data/normalization/test_public_fund_collapse.py tests/unit/domain/test_task4_contracts.py
uv run mypy src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/data/normalization/test_public_fund_collapse.py tests/unit/domain/test_task4_contracts.py
git diff --check
```

Expected: valid collapse, direct model invariants, all 44-column agreement checks,
exact issue counts/messages/locations/order, full orchestration, and every exact bounded
mixed order pass.

- [ ] **Step 10: Commit and independently review the complete collapse checkpoint**

```bash
git add src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/unit/data/normalization/test_public_fund_collapse.py tests/unit/domain/test_task4_contracts.py tests/performance/test_public_fund_collapse_scale.py
git commit -m "feat: collapse public funds to item grain"
```

Have a fresh reviewer inspect global versus adjacent grouping, raw and normalized key
uniqueness, additive cardinalities, all 44 columns, representative selection after
agreement, complete equivalent locators, collapse-builder `SourceRow` identity,
exact-type Python acceptance/rejection, attribute completeness/orphans, excluded-group
behavior, issue ordering/ID uniqueness, bounded-order bytes, iterator failures, absence
of a second complete row-record tuple, family/name/state inference, and deterministic
no-I/O/no-clock behavior. Every Critical/Important correction starts with focused RED,
reruns Step 9, gets a separate commit, and receives re-review.

---

### Task 6: Prove the complete official 101,265-row Task 4 acceptance contract

**Files:**

- Create: `tests/source_contract/test_official_overseas_public_normalization.py`

**Interfaces:**

- Consumes: manifest/catalog-verified descriptors only, `iter_xlsx_rows`, `normalize_overseas_listed`, and `normalize_public_funds`.
- Exhausts: exactly 5,646 overseas rows plus 95,619 public-fund rows, with no source iterator truncated or replaced by an arbitrary path helper.
- Proves: all official counts from approved-design section 7, identity uniqueness, exact anomaly cells, raw/normalized attribute collision observations, item/attribute grain, complete wrapper/raw/locator fidelity, item equivalent-source completeness, malformed-row issue survival, no collapse failure on official data, and selected official-group bounded-order invariance.
- Profiles: the bounded synthetic scale preflight runs first; the official command then
  records wall time and peak RSS inside pytest with `perf_counter` and
  `resource.getrusage`, without constructing a second
  complete `FundAttributeRow` tuple or renormalizing emitted attributes.
- Does not: introduce new production behavior, manufacture a RED, or freeze unspecified optional-warning totals.

- [ ] **Step 1: Write the complete verified-source acceptance test**

Create `tests/source_contract/test_official_overseas_public_normalization.py` with module marks `source_contract` and `slow`. Define literal all-field maps by importing the frozen maps exported by the two domain modules and assert their values equal the official catalog column sets, not merely subsets.

Use these helpers:

```python
import resource
import sys
from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest

from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from finproof.data.normalization.public_funds import normalize_public_funds
from finproof.data.source_manifest import SourceFileManifest, VerifiedSourceSet
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.listed import ListedProductType
from finproof.domain.locators import SourceCellLocator
from finproof.domain.overseas_listed import OVERSEAS_FIELD_COLUMNS
from finproof.domain.public_funds import FUND_ITEM_FIELD_COLUMNS
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

ROOT = Path(__file__).resolve().parents[2]
pytestmark = [pytest.mark.source_contract, pytest.mark.slow]


def _verified() -> VerifiedSourceSet:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    return manifest.verify(ROOT / "source_material")


def _assert_wrapper_matches_row(
    wrapped: NormalizedValue[Any], row: SourceRow, column: str
) -> None:
    assert wrapped.raw_value == row.cell(column).raw_value
    assert wrapped.source == SourceCellLocator.from_row(row, column)
```

The overseas acceptance body must contain these exact assertions while it streams once:

```python
def test_official_overseas_normalization_exhausts_all_rows_and_preserves_all_fields() -> None:
    source = _verified().data_file("PREF02N001")
    source_rows = records = quarantines = 0
    product_ids: set[str] = set()
    groups: Counter[ListedProductType] = Counter()
    currency = fee_zero = fee_positive = 0
    return_blank = return_zero = 0
    aum_blank = aum_zero = aum_positive = 0
    core_nonblank: Counter[str] = Counter()
    replication_nonblank = listing_sentinel = sale_blank = trade_blank = 0

    for row in iter_xlsx_rows(source):
        source_rows += 1
        result = normalize_overseas_listed(row)
        quarantines += result.record is None
        assert result.record is not None
        records += 1
        record = result.record
        product_id = record.product_id.normalized_value
        assert product_id is not None and product_id not in product_ids
        product_ids.add(product_id)
        product_type = record.product_type.normalized_value
        assert product_type is not None
        groups[product_type] += 1
        for field_name, column in OVERSEAS_FIELD_COLUMNS.items():
            _assert_wrapper_matches_row(getattr(record, field_name), row, column)

        currency += record.trading_currency.normalized_value == "USD"
        fee_zero += record.total_fee.quality_status is QualityStatus.RECORDED_ZERO_UNVERIFIED
        fee_positive += (record.total_fee.normalized_value or Decimal(0)) > 0
        return_blank += record.return_1d.quality_status is QualityStatus.MISSING_BLANK
        return_zero += record.return_1d.quality_status is QualityStatus.RECORDED_ZERO
        aum_blank += record.aum.quality_status is QualityStatus.MISSING_BLANK
        aum_zero += record.aum.quality_status is QualityStatus.RECORDED_ZERO
        aum_positive += (record.aum.normalized_value or Decimal(0)) > 0
        for name in ("base_index", "manager", "strategy", "asset_type", "region"):
            core_nonblank[name] += getattr(record, name).normalized_value is not None
        replication_nonblank += record.replication_method.normalized_value is not None
        listing_sentinel += record.listing_date.quality_status is QualityStatus.SENTINEL_ZERO
        sale_blank += record.sale_flag_raw.quality_status is QualityStatus.MISSING_BLANK
        trade_blank += record.suspension_flag_raw.quality_status is QualityStatus.MISSING_BLANK
        assert record.return_1d.quality_status is not QualityStatus.CONSTANT_METRIC

    assert (source_rows, records, quarantines, len(product_ids)) == (5_646, 5_646, 0, 5_646)
    assert groups == Counter({ListedProductType.ETF: 5_587, ListedProductType.ETN: 59})
    assert currency == 5_646
    assert (fee_zero, fee_positive) == (363, 5_283)
    assert (return_zero, return_blank) == (5_388, 258)
    assert (aum_positive, aum_zero, aum_blank) == (5_451, 8, 187)
    assert core_nonblank == Counter(
        {"base_index": 5_638, "manager": 5_638, "strategy": 5_638,
         "asset_type": 5_638, "region": 5_638}
    )
    assert replication_nonblank == 2_360
    assert listing_sentinel == 8
    assert (sale_blank, trade_blank) == (10, 10)
```

The public-fund acceptance must materialize the verified rows once because the complete collapse owns all contributing source rows. While reading, collect only the frozen raw counters and the two known 16-attribute groups:

```python
def test_official_public_fund_normalization_and_collapse_preserve_grain_and_lineage(
    record_property: Callable[[str, object], None],
) -> None:
    rows = tuple(iter_xlsx_rows(_verified().data_file("PRFD01N001")))
    assert len(rows) == 95_619
    raw_item_ids = {row.cell("itm_no").raw_value for row in rows}
    raw_pairs = {
        (row.cell("itm_no").raw_value, row.cell("prfd_attr_cd").raw_value)
        for row in rows
    }
    normalized_pairs = {
        (row.cell("itm_no").raw_value, row.cell("prfd_attr_cd").raw_value.strip())
        for row in rows
    }
    raw_attribute_codes = {row.cell("prfd_attr_cd").raw_value for row in rows}
    trimmed_attribute_codes = {raw.strip() for raw in raw_attribute_codes}
    padded_rows = sum(
        row.cell("prfd_attr_cd").raw_value != row.cell("prfd_attr_cd").raw_value.strip()
        for row in rows
    )
    literal_null_rows = sum(
        row.cell("zrin_fd_ivst_risk_gcd").raw_value == "NULL" for row in rows
    )
    type_06_rows = sum(row.cell("or_attr_desc").raw_value == "06" for row in rows)
    below_minus_100_cells = [
        (row.source_row_number, column)
        for row in rows
        for column in ("fd_mm18_ern_r", "fd_yr2_ern_r", "fd_yr3_ern_r", "fd_yr5_ern_r")
        if row.cell(column).raw_value
        and Decimal(row.cell(column).raw_value) < Decimal("-100")
    ]

    rss_before_native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started_at = perf_counter()
    result = normalize_public_funds(rows)
    wall_seconds = perf_counter() - started_at
    rss_after_native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    multiplier = 1 if sys.platform == "darwin" else 1024
    record_property("normalization_wall_seconds", round(wall_seconds, 6))
    record_property("peak_rss_before_bytes", rss_before_native * multiplier)
    record_property("peak_rss_after_bytes", rss_after_native * multiplier)
    assert len(raw_item_ids) == 11_139
    assert len(raw_pairs) == 95_619
    assert len(normalized_pairs) == 95_619
    assert len(raw_attribute_codes) == len(trimmed_attribute_codes) == 228
    assert padded_rows == 1_670
    assert len(result.items) == 11_138
    assert len(result.attributes) == 95_618
    assert max(len(item.contributing_rows) for item in result.items) == 16
```

Continue with exact item/anomaly assertions:

```python
    item_by_id = {
        item.fund_item_id.representative.normalized_value: item for item in result.items
    }
    assert None not in item_by_id
    currencies = Counter(item.currency.representative.normalized_value for item in result.items)
    assert currencies == Counter({"KRW": 11_067, "USD": 71})
    assert literal_null_rows == 18_416
    assert sum(
        item.risk_code.representative.quality_status is QualityStatus.MISSING_LITERAL_NULL
        for item in result.items
    ) == 2_573
    assert type_06_rows == 5_436
    assert sum(
        item.fund_type_raw.representative.quality_status is QualityStatus.MIXED_SOURCE_VALUES
        for item in result.items
    ) == 686
    assert len(below_minus_100_cells) == 20
    assert len({row_number for row_number, _ in below_minus_100_cells}) == 5
    assert set(row_number for row_number, _ in below_minus_100_cells) == {
        302, 11_405, 41_701, 69_297, 86_745,
    }
    assert {
        item_id for item_id, item in item_by_id.items()
        if any(
            getattr(item, field).representative.quality_status is QualityStatus.OUT_OF_DOMAIN
            for field in ("return_18m", "return_2y", "return_3y", "return_5y")
        )
    } == {"KR515303001M"}
```

Prove malformed-row and zero official collapse failures exactly:

```python
    blockers = [issue for issue in result.issues if issue.quarantined]
    malformed = [issue for issue in blockers if issue.rule_id == "public_fund.malformed_item"]
    assert len(malformed) == 1
    assert malformed[0].source.source_row_number == 84_563
    assert malformed[0].source.source_column_name == "itm_no"
    assert malformed[0].quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert not any(
        issue.rule_id in {
            "public_fund.attribute_key.raw_duplicate",
            "public_fund.attribute_key.normalized_collision",
            "public_fund.item.non_attribute_disagreement",
        }
        for issue in result.issues
    )
```

Prove exhaustive item/attribute/raw/locator completeness independently of the Pydantic validators:

```python
    source_by_identity = {
        (row.source_file, row.source_sheet, row.source_row_number): row for row in rows
        if row.cell("itm_no").raw_value != '"'
    }
    seen_attribute_rows: set[tuple[object, ...]] = set()
    for item in result.items:
        assert tuple(row.source_row_number for row in item.contributing_rows) == tuple(
            sorted(row.source_row_number for row in item.contributing_rows)
        )
        for field_name, column in FUND_ITEM_FIELD_COLUMNS.items():
            value = getattr(item, field_name)
            expected = tuple(
                SourceCellLocator.from_row(row, column) for row in item.contributing_rows
            )
            assert value.equivalent_sources == expected
            assert (
                value.representative.raw_value
                == item.contributing_rows[0].cell(column).raw_value
            )
        for row in item.contributing_rows:
            identity = (row.source_file, row.source_sheet, row.source_row_number)
            assert source_by_identity[identity] is row

    for attribute in result.attributes:
        identity = (
            attribute.fund_item_id.source.source_file,
            attribute.fund_item_id.source.source_sheet,
            attribute.fund_item_id.source.source_row_number,
        )
        row = source_by_identity[identity]
        assert attribute.fund_item_id.raw_value == row.cell("itm_no").raw_value
        assert attribute.fund_item_id.normalized_value == row.cell("itm_no").raw_value
        assert attribute.fund_item_id.source == SourceCellLocator.from_row(row, "itm_no")
        assert attribute.attribute_code.raw_value == row.cell("prfd_attr_cd").raw_value
        assert (
            attribute.attribute_code.normalized_value
            == row.cell("prfd_attr_cd").raw_value.strip()
        )
        assert attribute.attribute_code.source == SourceCellLocator.from_row(
            row, "prfd_attr_cd"
        )
        seen_attribute_rows.add(identity)
    assert len(seen_attribute_rows) == 95_618
```

Finally assert no `family`, `family_candidate`, `product_type`, `saleable`, or `is_eligible_at_as_of` output field exists on `FundItem`, and that all 175 raw item names containing `ETF` or `상장지수` remain ordinary fund items. Do not assert an optional warning grand total.

- [ ] **Step 2: Add official multi-attribute bounded-order acceptance**

From the same verified rows, select exact item IDs `KR5116450039` and `KR5153450333`.
Each must contain 16 source rows. Set `canonical` to the 32 selected rows sorted by
`source_row_number`, then use exactly these four orders (indices are zero-based):

```python
orders = (
    canonical,
    canonical[::-1],
    canonical[0::2] + canonical[1::2],  # even indices, then odd indices
    canonical[1::2] + canonical[0::2],  # odd indices, then even indices
)
```

Assert all four produce byte-identical result JSON, 2 items, 32 attributes, and the
same contributing rows/locators. Do not dump the full 95,619-row result to compare
bytes.

- [ ] **Step 3: Run the acceptance test; immediate GREEN is valid**

```bash
uv run pytest tests/source_contract/test_official_overseas_public_normalization.py -q -m source_contract --junitxml=/private/tmp/finproof-task4-official-profile.xml
```

Expected: PASS after Tasks 1-5. Record the JUnit `normalization_wall_seconds` and
before/after peak-RSS byte properties measured inside pytest with `perf_counter` and
`resource.getrusage` as official profile evidence in status. Confirm by code
inspection that neither test nor production creates a second complete
`FundAttributeRow` tuple. This is acceptance evidence, so no synthetic production RED
is allowed. If any count/fidelity assertion fails, stop broad work, identify the exact
table/row/field, add one focused failing unit regression to the owning Task 2-5 test
file, make the smallest correction, rerun the owning task gate and this acceptance
command, and never weaken a frozen official count.

- [ ] **Step 4: Run the complete official source-contract marker gate**

```bash
uv run pytest tests/source_contract -q -m source_contract
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/extract_schema_catalog.py --check
```

Expected: all official tests pass; overall audit remains 145,393 rows at `2026-07-11`, handoff remains 61 required files/9 official inputs/41,384,928 bytes, and schema catalog remains 207 columns.

- [ ] **Step 5: Commit and review the official acceptance checkpoint**

```bash
git add tests/source_contract/test_official_overseas_public_normalization.py
git commit -m "test: enforce official overseas and fund normalization"
```

Have a fresh reviewer inspect verified-descriptor-only loading, normal exhaustion, every
section 7 count, all 49/45/44-column fidelity, malformed row 84,563, zero official
duplicate/collision/disagreement rules, 20 exact anomaly cells, direct SourceRow-cell
attribute completeness, official bounded orders, wall-time/peak-RSS evidence, no
second complete row-record tuple, no optional-warning over-freeze, and no production
behavior in this test-only commit. If an implementation defect is found, follow the
focused RED correction path from Step 3 and re-review.

---

### Task 7: Record evidence, run all gates, obtain whole-branch review, and close only Task 4

**Files:**

- Modify: `docs/implementation/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`
- Modify: `docs/superpowers/plans/2026-08-14-phase1-task4-overseas-public-normalization.md` only to check steps after their evidence exists
- Inspect: `docs/10_DECISION_LOG.md`; D-021/A-011 was already changed in Task 1, and no further edit is allowed without a newly discovered conflict

**Interfaces:**

- Proves: every focused RED reason and GREEN result, every checkpoint review, the complete 101,265-row Task 4 acceptance, all mandatory repository gates, final whole-branch review, and clean feature worktree.
- Records: Task 4 complete; Task 5 and the Phase 1 gate remain unchecked.
- Names: exact next task `Phase 1 Task 5: build reproducible Parquet/DuckDB artifacts, inject quality persistence time, and create exact identifier links`.
- Preserves: A-003 open; A-011 open only for evidence/golden/metric gaps; no artifact or query/API implementation.

- [ ] **Step 1: Run the complete implementation and repository gate on the reviewed implementation tree**

From the isolated Task 4 worktree, export the required cache path and run and observe
every command in this same shell session:

```bash
export UV_CACHE_DIR=/private/tmp/finproof-uv-cache
uv sync --frozen --all-groups
uv run pytest tests/contract/test_quality_issue_schema.py tests/unit/domain tests/unit/data/normalization -q
uv run pytest tests/performance/test_public_fund_collapse_scale.py -q -m performance --junitxml=/private/tmp/finproof-task4-scale.xml
uv run pytest tests/source_contract/test_official_overseas_public_normalization.py -q -m source_contract --junitxml=/private/tmp/finproof-task4-official-profile.xml
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

Expected source evidence remains exactly 145,393 official rows, snapshot `2026-07-11`, 207 schema columns, 61 required files, 9 official inputs, and 41,384,928 source bytes. Any unexplained regression is a hard stop, not permission to weaken a test.

- [ ] **Step 2: Update status and both plans only from observed evidence**

In `docs/implementation/STATUS.md`:

- mark only Phase 1 Task 4 complete;
- summarize each Tasks 1-5 focused RED and GREEN, including exact-type Python
  rejection, normalizer/builder input identity, canonical JSON prechecks, schema
  FormatChecker, all-field overseas/fund wrappers, three collapse rules, issue ordering,
  and bounded-order tests;
- state that Task 6 acceptance was allowed to pass immediately if it did and no synthetic RED was introduced;
- record all official section 7 counts, malformed Excel row 84,563, 20 anomaly cells, zero official duplicate/collision/disagreement groups, and complete representative/equivalent-locator fidelity;
- record D-021 and the remaining A-011/A-003 boundaries;
- record each implementation/review-fix/acceptance/evidence commit hash;
- record every Step 1 command with the exact observed test/file/time summary, including
  the 256/512 transient byte measurements and peak live normalized-row count, plus
  official wall seconds and before/after peak-RSS bytes from the JUnit properties;
- name Phase 1 Task 5 exactly and leave Task 5/Phase 1 gate unchecked.

In the legacy Phase 1 plan, mark Task 4's seven checkpoints complete only after evidence exists. In this dedicated plan, check a box only after the specified command/review exists. Do not change Task 5 behavior or prose.

- [ ] **Step 3: Commit the Task 4 evidence checkpoint**

```bash
git add docs/implementation/STATUS.md docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md docs/superpowers/plans/2026-08-14-phase1-task4-overseas-public-normalization.md
git commit -m "docs: record Phase 1 Task 4 verification"
```

- [ ] **Step 4: Request an independent whole-branch review**

Have a fresh reviewer inspect the Task 4 branch base through HEAD against `AGENTS.md`, D-003/D-004/D-005/D-006/D-008/D-009/D-010/D-017/D-021, A-003/A-011, the approved design, this plan, Task 2/3 interfaces, and every official acceptance invariant. Require explicit review of:

```text
D-021 canonical JSON plus explicit FormatChecker and terminal-Z UTC enforcement
no source paths or caller-invented locator inputs to normalizers
shared ETF/ETN enum compatibility and exact overseas identity behavior
all 49 overseas source wrappers and no active/eligibility/staleness inference
normalizer SourceRow identity, exact-type Python boundary, and canonical-shape JSON round trip
all 45 fund row wrappers and all 44 FundItem values
raw padded attribute preservation and normalized collision safety
literal NULL, fund type 06, zero, date, currency, and below-minus-100 policies
global fund grouping, exact agreement, representative and locator completeness
exact duplicate/collision/disagreement cardinalities and global issue ordering
FundCollapseResult item/attribute completeness and byte bounded-order invariance
official 101,265-row counts/fidelity and malformed row 84,563
strict RED -> GREEN evidence and acceptance-only no-synthetic-RED behavior
no official input, expected audit, artifact, exact-link, family, query, API, or HCX change
```

Classify findings as Critical, Important, or Minor. Every Critical or Important behavior finding must receive one focused failing regression, the smallest correction, the owning task gate plus Step 1 rerun, a separate correction commit, status evidence, and re-review. Repeat until no Critical or Important finding remains.

- [ ] **Step 5: Run the final reviewed-tree gate and prove cleanliness**

On the final reviewed HEAD, rerun every Step 1 command, then:

```bash
git status --short --branch
test -z "$(git status --porcelain)"
```

Expected: all commands pass on the exact reviewed tree, final review has no Critical or Important finding, Task 4 alone is newly checked, Task 5 is the next incomplete item, and the feature worktree is clean.

- [ ] **Step 6: Consume standing authorization for a local fast-forward and continue**

Use `superpowers:finishing-a-development-branch`. The user's standing authorization
already selects local integration, so after the Task 4 branch is reviewed and clean,
leave that feature worktree intact and fast-forward only
`feat/phase1-task4-overseas-public-normalization` from the already-existing main
worktree at `/Users/ss020/Dev/Mirae_Agent`:

```bash
export UV_CACHE_DIR=/private/tmp/finproof-uv-cache
test "$(git -C /Users/ss020/Dev/Mirae_Agent branch --show-current)" = "main"
git -C /Users/ss020/Dev/Mirae_Agent merge --ff-only feat/phase1-task4-overseas-public-normalization
```

A non-fast-forward result is a hard stop; do not create a merge commit or rebase by
assumption. Do not push, open a PR, publish, or otherwise mutate a remote. On the
resulting local `main`, set the command working directory to
`/Users/ss020/Dev/Mirae_Agent`, rerun every Step 1 command (including the bounded scale
test and official wall-time/peak-RSS profile), and prove the main tree clean. The Task 4
documentation commit already contains pre-merge reviewed evidence; record post-merge
gate outputs only in the final report, not by dirtying or recommitting documentation.
Then continue directly with the exact Phase 1 Task 5 named below.

---

## Hard stops

Stop and report rather than guess, weaken a test, or add a correction list when:

- handoff checksums, 41,384,928 official bytes, the 145,393-row audit, or the 207-column schema catalog differs;
- overseas source differs from 5,646 rows/unique IDs or contains a group outside exact ETF/ETN;
- public funds differ from 95,619 rows, 11,139 raw IDs, 11,138 valid items, one malformed row at Excel 84,563, 95,619 raw pairs, zero official raw duplicates, zero normalized collisions, or zero non-attribute disagreement groups;
- official data unexpectedly produces a normalized attribute collision;
- an implementation requires overseas/public-fund eligibility, generic truthiness, risk-system equivalence, family semantics, name-based product conversion, or an inferred field applicable date;
- the complete frozen `DataQualityIssue` JSON cannot validate with Draft 2020-12 plus `FormatChecker`;
- a Task 2/3 regression or any other failure is unexplained;
- a proposed change would mutate official inputs, frozen audit expectations, artifacts, exact links, query/API behavior, or submission-frozen outputs.

Synthetic duplicate, collision, and disagreement fixtures are required deterministic behavior tests and are not hard stops.

## Exact next task after verified completion

Phase 1 Task 5 builds deterministic Parquet/DuckDB artifacts, persists quality issues with an injected UTC first-detection time under D-021, emits quality reports, creates only the exact 47 domestic-listed/public-fund links, and proves logical reproducibility. Do not begin it until Task 4's final reviewed-tree gate is recorded and the worktree is clean.
