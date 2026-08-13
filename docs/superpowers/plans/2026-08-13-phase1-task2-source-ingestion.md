# Phase 1 Task 2 Verified Source Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed official-source boundary that verifies every manifest input and streams the four official data workbooks into immutable rows and cells with complete raw lineage.

**Architecture:** Strict Pydantic models load the manifest and schema catalog, then an all-or-nothing verifier produces immutable `VerifiedSourceFile` descriptors. The production XLSX reader accepts only those descriptors and uses hardened `lxml.etree.iterparse` to emit bounded-memory `SourceRow` values without normalizing raw data.

**Tech Stack:** Python 3.12, Pydantic 2.13, lxml 6, zipfile, hashlib, pytest 9, Ruff, mypy, uv.

## Global Constraints

- Execute only Phase 1 Task 2; do not implement normalization, quarantine, artifacts, query behavior, API behavior, or HCX integration.
- Official source files and `tests/contracts/expected_source_audit.json` are immutable.
- Evaluation snapshot date is exactly `2026-07-11`.
- Production XLSX ingestion accepts `VerifiedSourceFile`, never a caller-supplied `Path` plus table/sheet strings.
- Preserve manifest-relative file, table, sheet, Excel row, Excel column, verified checksum, snapshot, exact raw value, and explicit applicable-date state.
- A raw cell's `applicable_date` defaults to `None`; never copy the dataset snapshot into it as a guess.
- Manifest/catalog/file verification is all-or-nothing and fails closed with `SourceContractError`.
- User-facing errors contain no absolute paths, stack traces, workbook payloads, or raw rows.
- Worksheet XML is streamed and processed elements are cleared; never materialize a full worksheet.
- `tools/xlsx_stream.py` remains an independent standard-library bootstrap reader and is not imported by production code.
- Every behavior change follows strict red-green-refactor TDD with an observed failing test first.
- Use `Decimal` and typed financial parsing only in later normalization tasks, not here.

---

### Task 1: Add structured source errors and immutable raw-lineage models

**Files:**
- Modify: `src/finproof/core/errors.py`
- Create: `src/finproof/domain/__init__.py`
- Create: `src/finproof/domain/source.py`
- Create: `tests/unit/domain/__init__.py`
- Create: `tests/unit/domain/test_source.py`
- Create: `tests/unit/core/test_source_errors.py`

**Interfaces:**
- Produces: `SourceErrorCode(StrEnum)` with the exact categories in the approved design.
- Produces: `SourceContractError(code: SourceErrorCode, message: str, source_file: PurePosixPath | None = None, table_id: str | None = None)`.
- Produces: frozen `SourceCell(column_name: str, excel_column_number: int, excel_column_letter: str, raw_value: str, applicable_date: date | None = None)`.
- Produces: frozen `SourceRow(source_table: str, source_file: PurePosixPath, source_sheet: str, source_row_number: int, source_checksum: str, source_snapshot_date: date, raw_payload: tuple[str, ...], cells: tuple[SourceCell, ...])`.
- Produces: `SourceRow.cell(column_name: str) -> SourceCell` using exact case-sensitive lookup.

- [ ] **Step 1: Write failing error-contract tests**

Create `tests/unit/core/test_source_errors.py`:

```python
from pathlib import PurePosixPath

import pytest

from finproof.core.errors import SourceContractError, SourceErrorCode


def test_source_contract_error_has_stable_safe_context() -> None:
    error = SourceContractError(
        SourceErrorCode.CHECKSUM_MISMATCH,
        "SHA-256 does not match the official manifest",
        source_file=PurePosixPath("data/source.xlsx"),
        table_id="PRBD01N001",
    )

    assert error.code is SourceErrorCode.CHECKSUM_MISMATCH
    assert error.source_file == PurePosixPath("data/source.xlsx")
    assert error.table_id == "PRBD01N001"
    assert str(error) == (
        "checksum_mismatch: data/source.xlsx [PRBD01N001]: "
        "SHA-256 does not match the official manifest"
    )
    assert "/Users/" not in str(error)


def test_source_contract_error_rejects_absolute_path_context() -> None:
    with pytest.raises(ValueError, match="manifest-relative"):
        SourceContractError(
            SourceErrorCode.FILE_MISSING,
            "official input is missing",
            source_file=PurePosixPath("/private/source.xlsx"),
        )
```

Parameterize a second test over every approved category:

```python
EXPECTED_CODES = {
    "manifest_invalid",
    "catalog_invalid",
    "path_escape",
    "file_missing",
    "file_type_invalid",
    "size_mismatch",
    "checksum_mismatch",
    "snapshot_mismatch",
    "duplicate_table",
    "missing_sheet",
    "column_count_mismatch",
    "header_mismatch",
    "blank_header",
    "duplicate_header",
    "duplicate_cell",
    "row_wider_than_header",
    "row_count_mismatch",
    "unsupported_formula",
    "malformed_workbook",
}


def test_source_error_codes_are_stable() -> None:
    assert {code.value for code in SourceErrorCode} == EXPECTED_CODES
```

- [ ] **Step 2: Run the error tests and confirm RED**

Run:

```bash
uv run pytest tests/unit/core/test_source_errors.py -q
```

Expected: test collection fails because `SourceErrorCode` and structured `SourceContractError` do not exist.

- [ ] **Step 3: Implement the smallest structured source error**

In `src/finproof/core/errors.py`, keep `FinProofError` and replace the empty source error with:

```python
from enum import StrEnum
from pathlib import PurePosixPath


class SourceErrorCode(StrEnum):
    MANIFEST_INVALID = "manifest_invalid"
    CATALOG_INVALID = "catalog_invalid"
    PATH_ESCAPE = "path_escape"
    FILE_MISSING = "file_missing"
    FILE_TYPE_INVALID = "file_type_invalid"
    SIZE_MISMATCH = "size_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    SNAPSHOT_MISMATCH = "snapshot_mismatch"
    DUPLICATE_TABLE = "duplicate_table"
    MISSING_SHEET = "missing_sheet"
    COLUMN_COUNT_MISMATCH = "column_count_mismatch"
    HEADER_MISMATCH = "header_mismatch"
    BLANK_HEADER = "blank_header"
    DUPLICATE_HEADER = "duplicate_header"
    DUPLICATE_CELL = "duplicate_cell"
    ROW_WIDER_THAN_HEADER = "row_wider_than_header"
    ROW_COUNT_MISMATCH = "row_count_mismatch"
    UNSUPPORTED_FORMULA = "unsupported_formula"
    MALFORMED_WORKBOOK = "malformed_workbook"


class SourceContractError(FinProofError):
    def __init__(
        self,
        code: SourceErrorCode,
        message: str,
        *,
        source_file: PurePosixPath | None = None,
        table_id: str | None = None,
    ) -> None:
        if source_file is not None and source_file.is_absolute():
            raise ValueError("source_file error context must be manifest-relative")
        self.code = code
        self.source_file = source_file
        self.table_id = table_id
        context = ""
        if source_file is not None:
            context += f": {source_file.as_posix()}"
        if table_id is not None:
            context += f" [{table_id}]"
        super().__init__(f"{code.value}{context}: {message}")
```

Do not accept `Path` in the public error context; this prevents accidental absolute-path rendering.

- [ ] **Step 4: Run error tests to GREEN**

Run:

```bash
uv run pytest tests/unit/core/test_source_errors.py -q
```

Expected: both tests pass.

- [ ] **Step 5: Write failing lineage-model tests**

Create `tests/unit/domain/test_source.py`:

```python
from datetime import date
from pathlib import PurePosixPath

import pytest
from pydantic import ValidationError

from finproof.domain.source import SourceCell, SourceRow


def _row() -> SourceRow:
    cells = (
        SourceCell(
            column_name="PD_NO",
            excel_column_number=1,
            excel_column_letter="A",
            raw_value="00123",
        ),
        SourceCell(
            column_name="PD_NM",
            excel_column_number=2,
            excel_column_letter="B",
            raw_value="  채권 ",
        ),
    )
    return SourceRow(
        source_table="PRBD01N001",
        source_file=PurePosixPath("data/bonds.xlsx"),
        source_sheet="datarows",
        source_row_number=2,
        source_checksum="a" * 64,
        source_snapshot_date=date(2026, 7, 11),
        raw_payload=("00123", "  채권 "),
        cells=cells,
    )


def test_source_row_preserves_exact_values_and_lineage() -> None:
    row = _row()
    assert row.raw_payload == ("00123", "  채권 ")
    assert row.cell("PD_NO").raw_value == "00123"
    assert row.cell("PD_NO").applicable_date is None
    assert row.source_file == PurePosixPath("data/bonds.xlsx")
    assert row.source_snapshot_date == date(2026, 7, 11)


def test_source_row_rejects_payload_cell_disagreement() -> None:
    row = _row()
    with pytest.raises(ValidationError, match="raw_payload"):
        SourceRow.model_validate(
            row.model_dump() | {"raw_payload": ("different", "  채권 ")}
        )


def test_source_models_are_frozen() -> None:
    row = _row()
    with pytest.raises(ValidationError):
        row.source_row_number = 3  # type: ignore[misc]
```

Also assert duplicate cell names, non-contiguous one-based column numbers, incorrect Excel letters, an absolute `source_file`, and a checksum outside lowercase 64-character hex are rejected.

- [ ] **Step 6: Run lineage tests and confirm RED**

Run:

```bash
uv run pytest tests/unit/domain/test_source.py -q
```

Expected: collection fails because `finproof.domain.source` does not exist.

- [ ] **Step 7: Implement frozen source models and invariants**

Create `src/finproof/domain/source.py` with `ConfigDict(frozen=True, extra="forbid")`, constrained positive row/column numbers, a lowercase SHA-256 pattern, and an `after` model validator that enforces:

```python
if self.source_file.is_absolute() or ".." in self.source_file.parts:
    raise ValueError("source_file must be a safe manifest-relative path")
if tuple(cell.raw_value for cell in self.cells) != self.raw_payload:
    raise ValueError("raw_payload must match cells in header order")
if tuple(cell.excel_column_number for cell in self.cells) != tuple(
    range(1, len(self.cells) + 1)
):
    raise ValueError("cells must use contiguous one-based columns")
if len({cell.column_name for cell in self.cells}) != len(self.cells):
    raise ValueError("cell column names must be unique")
```

Implement private `_excel_column_letter(number: int) -> str` and validate each declared letter against its number. Implement exact lookup with:

```python
def cell(self, column_name: str) -> SourceCell:
    for cell in self.cells:
        if cell.column_name == column_name:
            return cell
    raise KeyError(column_name)
```

- [ ] **Step 8: Run focused tests and quality checks**

Run:

```bash
uv run pytest tests/unit/core/test_source_errors.py tests/unit/domain/test_source.py -q
uv run ruff format --check src/finproof/core/errors.py src/finproof/domain tests/unit/core/test_source_errors.py tests/unit/domain
uv run ruff check src/finproof/core/errors.py src/finproof/domain tests/unit/core/test_source_errors.py tests/unit/domain
uv run mypy src/finproof/core/errors.py src/finproof/domain tests/unit/core/test_source_errors.py tests/unit/domain
```

Expected: all pass.

- [ ] **Step 9: Commit the lineage checkpoint**

```bash
git add src/finproof/core/errors.py src/finproof/domain tests/unit/core/test_source_errors.py tests/unit/domain
git commit -m "feat: add immutable source lineage contracts"
```

---

### Task 2: Parse the official manifest and ordered schema catalog strictly

**Files:**
- Create: `src/finproof/data/__init__.py`
- Create: `src/finproof/data/source_manifest.py`
- Create: `tests/helpers/__init__.py`
- Create: `tests/helpers/source_manifest.py`
- Create: `tests/source_contract/__init__.py`
- Create: `tests/source_contract/test_source_manifest.py`

**Interfaces:**
- Consumes: `SourceContractError`, `SourceErrorCode` from Task 1.
- Produces: frozen discriminated manifest entries `TaskPdfEntry`, `DataFileEntry`, and `SchemaFileEntry`.
- Produces: frozen `SourceSchemaCatalog` with ordered headers per table.
- Produces: `SourceFileManifest.load(manifest_path: Path, schema_catalog_path: Path) -> SourceFileManifest`.
- Produces: `SourceFileManifest.data_entry(table_id: str) -> DataFileEntry`.
- The four evaluation table IDs are exactly `PRBD01N001`, `PREF01N001`, `PREF02N001`, and `PRFD01N001`.

- [ ] **Step 1: Add a deterministic official-shaped manifest fixture builder**

Create `tests/helpers/source_manifest.py` with:

```python
TABLE_COLUMNS = {
    "PRBD01N001": ("PD_NO", "PD_NM"),
    "PREF01N001": ("pd_itm_no", "pd_nm"),
    "PREF02N001": ("pd_itm_no", "pd_nm"),
    "PRFD01N001": ("itm_no", "itm_nm"),
}


def write_source_contract_fixture(base_dir: Path) -> tuple[Path, Path]:
    payloads = {"competition_task.pdf": b"pdf"}
    for table_id in TABLE_COLUMNS:
        payloads[f"data/{table_id}_data.xlsx"] = f"{table_id}-data".encode()
        payloads[f"data/{table_id}_schema.xlsx"] = f"{table_id}-schema".encode()
    for relative_path, payload in payloads.items():
        destination = base_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    def common(relative_path: str) -> dict[str, object]:
        payload = payloads[relative_path]
        return {
            "path": relative_path,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    files: list[dict[str, object]] = [
        common("competition_task.pdf") | {"kind": "official_task_pdf"}
    ]
    for table_id, headers in TABLE_COLUMNS.items():
        files.extend(
            [
                common(f"data/{table_id}_data.xlsx")
                | {
                    "kind": "data",
                    "table_id": table_id,
                    "sheet_name": "datarows",
                    "expected_rows": 1,
                    "expected_columns": len(headers),
                },
                common(f"data/{table_id}_schema.xlsx")
                | {
                    "kind": "schema",
                    "table_id": table_id,
                    "sheet_names": ["Sheet1_Schema", "Sheet2_Sample"],
                    "expected_columns": len(headers),
                },
            ]
        )

    manifest = {
        "manifest_version": "1.0.0",
        "competition": "FinProof test fixture",
        "snapshot_date": "2026-07-11",
        "files": files,
    }
    catalog = {
        "catalog_version": "1.0.0",
        "snapshot_date": "2026-07-11",
        "tables": {
            table_id: {
                "axis_warning": "test fixture",
                "column_count": len(headers),
                "columns": [
                    {
                        "column_name": header,
                        "column_type": "text",
                        "example": "",
                        "key": "",
                        "name_ko": "",
                        "schema_excel_row": index + 3,
                    }
                    for index, header in enumerate(headers)
                ],
            }
            for table_id, headers in TABLE_COLUMNS.items()
        },
    }
    manifest_path = base_dir / "input_manifest.json"
    catalog_path = base_dir / "schema_catalog.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest_path, catalog_path
```

Import `hashlib`, `json`, and `Path`. This helper creates only test files under `tmp_path`; it never writes under `source_material/`.

- [ ] **Step 2: Write failing strict-load tests**

Create `tests/source_contract/test_source_manifest.py`:

```python
from pathlib import Path

import pytest

from finproof.core.errors import SourceContractError, SourceErrorCode
from finproof.data.source_manifest import OFFICIAL_TABLE_IDS, SourceFileManifest

ROOT = Path(__file__).resolve().parents[2]


def test_official_manifest_and_catalog_load_with_exact_tables() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    assert tuple(entry.table_id for entry in manifest.data_files) == OFFICIAL_TABLE_IDS
    assert manifest.data_entry("PRBD01N001").expected_rows == 42_394
    assert manifest.expected_headers("PRBD01N001")[0] == "PD_NO"


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SourceContractError) as raised:
        SourceFileManifest.load(manifest_path, catalog_path)
    assert raised.value.code is SourceErrorCode.MANIFEST_INVALID
```

Add one focused mutation test each for catalog unknown fields, manifest snapshot mismatch, catalog snapshot mismatch, duplicate/missing data table, duplicate/missing schema table, PDF count other than one, manifest/catalog column-count disagreement, and duplicate/blank catalog headers.

- [ ] **Step 3: Run strict-load tests and confirm RED**

Run:

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
```

Expected: collection fails because `finproof.data.source_manifest` does not exist.

- [ ] **Step 4: Implement strict manifest/catalog loading**

In `src/finproof/data/source_manifest.py`:

```python
OFFICIAL_SNAPSHOT = date(2026, 7, 11)
OFFICIAL_TABLE_IDS = (
    "PRBD01N001",
    "PREF01N001",
    "PREF02N001",
    "PRFD01N001",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TaskPdfEntry(StrictModel):
    path: PurePosixPath
    kind: Literal["official_task_pdf"]
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DataFileEntry(StrictModel):
    path: PurePosixPath
    kind: Literal["data"]
    table_id: str
    sheet_name: str
    expected_rows: int = Field(ge=0)
    expected_columns: int = Field(gt=0)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SchemaFileEntry(StrictModel):
    path: PurePosixPath
    kind: Literal["schema"]
    table_id: str
    sheet_names: tuple[str, ...]
    expected_columns: int = Field(gt=0)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CatalogColumn(StrictModel):
    column_name: str
    column_type: str
    example: str
    key: str
    name_ko: str
    schema_excel_row: int = Field(gt=0)


class CatalogTable(StrictModel):
    axis_warning: str
    column_count: int = Field(gt=0)
    columns: tuple[CatalogColumn, ...]


class SourceSchemaCatalog(StrictModel):
    catalog_version: str
    snapshot_date: date
    tables: dict[str, CatalogTable]


ManifestEntry = Annotated[
    TaskPdfEntry | DataFileEntry | SchemaFileEntry,
    Field(discriminator="kind"),
]


class SourceFileManifest(StrictModel):
    manifest_version: str
    competition: str
    snapshot_date: date
    files: tuple[ManifestEntry, ...]
    schema_catalog: SourceSchemaCatalog = Field(exclude=True, repr=False)

    @property
    def data_files(self) -> tuple[DataFileEntry, ...]:
        return tuple(entry for entry in self.files if isinstance(entry, DataFileEntry))

    def data_entry(self, table_id: str) -> DataFileEntry:
        for entry in self.data_files:
            if entry.table_id == table_id:
                return entry
        raise KeyError(table_id)

    def expected_headers(self, table_id: str) -> tuple[str, ...]:
        table = self.schema_catalog.tables[table_id]
        return tuple(column.column_name for column in table.columns)
```

Import `Annotated` and `Literal` from `typing`. `load()` parses the two JSON files independently, validates `SourceSchemaCatalog`, and validates `SourceFileManifest` from `manifest_payload | {"schema_catalog": catalog.model_dump()}`. Wrap `JSONDecodeError`, `OSError`, and `ValidationError` in safe `SourceContractError` categories without copying exception text that contains a local path. The model validator compares the exact ordered set of data/schema table IDs with `OFFICIAL_TABLE_IDS`, requires one PDF, requires snapshot agreement, and compares each catalog header count with both manifest entries.

- [ ] **Step 5: Run strict-load tests to GREEN and refactor**

Run:

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
uv run ruff format --check src/finproof/data/source_manifest.py tests/helpers/source_manifest.py tests/source_contract/test_source_manifest.py
uv run ruff check src/finproof/data/source_manifest.py tests/helpers/source_manifest.py tests/source_contract/test_source_manifest.py
uv run mypy src/finproof/data/source_manifest.py tests/helpers/source_manifest.py tests/source_contract/test_source_manifest.py
```

Expected: all pass. Refactor repeated safe-error construction only inside `source_manifest.py`; do not create a generic utility module.

- [ ] **Step 6: Commit the strict metadata checkpoint**

```bash
git add src/finproof/data tests/helpers tests/source_contract/test_source_manifest.py
git commit -m "feat: load strict official source metadata"
```

---

### Task 3: Verify files all-or-nothing and produce immutable descriptors

**Files:**
- Modify: `src/finproof/data/source_manifest.py`
- Modify: `tests/helpers/source_manifest.py`
- Modify: `tests/source_contract/test_source_manifest.py`

**Interfaces:**
- Consumes: strict `SourceFileManifest` from Task 2.
- Produces: frozen `VerifiedSourceFile` with internal absolute access path and public manifest-relative identity.
- Produces: frozen `VerifiedSourceSet.data_file(table_id: str) -> VerifiedSourceFile`.
- Produces: `SourceFileManifest.verify(base_dir: Path) -> VerifiedSourceSet`.

- [ ] **Step 1: Write the failing official verification test**

Append:

```python
def test_official_manifest_verifies_all_files() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")

    bond = verified.data_file("PRBD01N001")
    assert bond.manifest_relative_path == PurePosixPath(
        "data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx"
    )
    assert bond.snapshot_date == date(2026, 7, 11)
    assert bond.sha256 == "728f44a567a986d21cf843d711c6c4dfa1a24d05b39c7da0541b981b57ecccf8"
    assert bond.expected_headers[:3] == ("PD_NO", "PD_EXG_MKT", "PD_NM")
```

- [ ] **Step 2: Write failing verification-error tests**

Using `write_source_contract_fixture(tmp_path)`, add five focused tests. Each test mutates exactly one path and asserts the listed code:

```python
def test_verify_rejects_missing_file(tmp_path: Path) -> None:
    manifest_path, catalog_path = write_source_contract_fixture(tmp_path)
    (tmp_path / "data/PRBD01N001_data.xlsx").unlink()
    manifest = SourceFileManifest.load(manifest_path, catalog_path)

    with pytest.raises(SourceContractError) as raised:
        manifest.verify(tmp_path)

    assert raised.value.code is SourceErrorCode.FILE_MISSING
```

Repeat the same arrange/act/assert shape for a byte append (`SIZE_MISMATCH`), same-size byte replacement (`CHECKSUM_MISMATCH`), replacement by a directory (`FILE_TYPE_INVALID`), and replacement by a symlink to a regular external file (`FILE_TYPE_INVALID`). Skip the symlink assertion only when the platform itself refuses test symlink creation.

Add a `../outside.xlsx` manifest path test that fails with `PATH_ESCAPE` before hashing. Assert `str(error)` contains only the relative manifest path and never `str(tmp_path)`.

Add an all-or-nothing test: corrupt the final schema file, call `verify`, assert it raises and no `VerifiedSourceSet` was returned or cached on the manifest.

- [ ] **Step 3: Run verification tests and confirm RED**

Run:

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
```

Expected: new tests fail because `verify`, `VerifiedSourceFile`, and `VerifiedSourceSet` do not exist.

- [ ] **Step 4: Implement safe path resolution and chunked hashing**

First add the exact immutable descriptor models:

```python
class VerifiedSourceFile(StrictModel):
    manifest_relative_path: PurePosixPath
    verified_absolute_path: Path = Field(exclude=True, repr=False)
    kind: Literal["data"] = "data"
    table_id: str
    sheet_name: str
    snapshot_date: date
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_rows: int = Field(ge=0)
    expected_columns: int = Field(gt=0)
    expected_headers: tuple[str, ...]


class VerifiedSourceSet(StrictModel):
    data_files: tuple[VerifiedSourceFile, ...]

    def data_file(self, table_id: str) -> VerifiedSourceFile:
        for source in self.data_files:
            if source.table_id == table_id:
                return source
        raise KeyError(table_id)
```

Validate that `expected_columns == len(expected_headers)`, the relative path is safe, the internal access path is absolute, and `data_files` have unique table IDs. Because `verified_absolute_path` uses `exclude=True` and `repr=False`, serialization and normal repr output cannot leak it.

Then add private helpers:

```python
def _safe_file(base_dir: Path, relative: PurePosixPath) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise SourceContractError(
            SourceErrorCode.PATH_ESCAPE,
            "manifest path must remain under source root",
            source_file=relative,
        )
    candidate = base_dir / Path(*relative.parts)
    if candidate.is_symlink():
        raise SourceContractError(
            SourceErrorCode.FILE_TYPE_INVALID,
            "official input must be a regular non-symlink file",
            source_file=relative,
        )
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as error:
        raise SourceContractError(
            SourceErrorCode.FILE_MISSING,
            "official input is missing",
            source_file=relative,
        ) from error
    if not resolved.is_relative_to(base_dir.resolve()):
        raise SourceContractError(
            SourceErrorCode.PATH_ESCAPE,
            "manifest path must remain under source root",
            source_file=relative,
        )
    if not resolved.is_file():
        raise SourceContractError(
            SourceErrorCode.FILE_TYPE_INVALID,
            "official input must be a regular file",
            source_file=relative,
        )
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

Check `stat().st_size` before hashing. Build verified descriptors in a local list and instantiate `VerifiedSourceSet` only after every entry succeeds. Populate data descriptors with ordered catalog headers. Do not store the set back onto a mutable module global or manifest cache.

- [ ] **Step 5: Run verification tests to GREEN**

Run:

```bash
uv run pytest tests/source_contract/test_source_manifest.py -q
uv run ruff check src/finproof/data/source_manifest.py tests/helpers/source_manifest.py tests/source_contract/test_source_manifest.py
uv run mypy src/finproof/data/source_manifest.py tests/helpers/source_manifest.py tests/source_contract/test_source_manifest.py
```

Expected: all pass.

- [ ] **Step 6: Commit the verified-descriptor checkpoint**

```bash
git add src/finproof/data/source_manifest.py tests/helpers/source_manifest.py tests/source_contract/test_source_manifest.py
git commit -m "feat: verify official source files"
```

---

### Task 4: Stream XLSX rows through the verified boundary

**Files:**
- Create: `src/finproof/data/xlsx_stream.py`
- Create: `tests/helpers/xlsx.py`
- Create: `tests/source_contract/test_xlsx_stream.py`

**Interfaces:**
- Consumes: `VerifiedSourceFile`, `SourceRow`, `SourceCell`, and structured source errors.
- Produces: `iter_xlsx_rows(source: VerifiedSourceFile) -> Iterator[SourceRow]`.
- No public function in `finproof.data.xlsx_stream` accepts a filesystem `Path`.

- [ ] **Step 1: Build a minimal XLSX fixture writer for tests**

Create `tests/helpers/xlsx.py` using `zipfile.ZipFile` and fixed XML strings. Its interface is:

```python
def write_xlsx(
    path: Path,
    *,
    sheet_name: str = "datarows",
    rows: tuple[tuple[str | None, ...], ...],
    formulas: frozenset[str] = frozenset(),
    duplicate_cells: frozenset[str] = frozenset(),
) -> None:
    """Write the minimum workbook/rels/worksheet parts needed by the reader."""
```

Use inline strings and explicit cell references. `None` omits a cell node, while `""` writes an explicit empty cell. The helper may generate deliberately invalid XML only when a test requests it.

Update `write_source_contract_fixture` so an optional `data_payloads: Mapping[str, bytes]` supplies XLSX bytes before manifest sizes/hashes are calculated.

- [ ] **Step 2: Write the failing successful-row lineage test**

Create `tests/source_contract/test_xlsx_stream.py`:

```python
def test_reader_preserves_omitted_cells_and_exact_raw_lineage(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(
        workbook,
        rows=(("ID", "PADDED", "NULL_TEXT", "TRAILING"), ("00123", None, "NULL", None)),
    )
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID", "PADDED", "NULL_TEXT", "TRAILING"),
        expected_rows=1,
    )

    row = next(iter_xlsx_rows(verified))

    assert row.source_row_number == 2
    assert row.raw_payload == ("00123", "", "NULL", "")
    assert tuple(cell.excel_column_letter for cell in row.cells) == ("A", "B", "C", "D")
    assert all(cell.applicable_date is None for cell in row.cells)
    assert row.source_checksum == verified.sha256
```

`verified_fixture_source` must create a complete official-shaped fixture manifest/catalog, substitute the generated workbook for the requested table, call `SourceFileManifest.load(manifest_path, catalog_path).verify(tmp_path)`, and return `data_file(table_id)`. It does not directly instantiate `VerifiedSourceFile`.

- [ ] **Step 3: Write failing structural-error tests**

Add one test each for:

- missing declared sheet -> `MISSING_SHEET`;
- exact ordered header mismatch -> `HEADER_MISMATCH`;
- blank header -> `BLANK_HEADER`;
- duplicate header -> `DUPLICATE_HEADER`;
- explicit nonblank cell beyond header -> `ROW_WIDER_THAN_HEADER`;
- duplicate cell address -> `DUPLICATE_CELL`;
- formula in header or data -> `UNSUPPORTED_FORMULA`;
- malformed workbook relationship/XML/ZIP -> `MALFORMED_WORKBOOK`;
- emitted data-row count different from `expected_rows` after exhaustion -> `ROW_COUNT_MISMATCH`.

Assert a consumer that takes only the first row does not receive a false full-count success signal; the mismatch is raised only when the iterator is exhausted.

- [ ] **Step 4: Run reader tests and confirm RED**

Run:

```bash
uv run pytest tests/source_contract/test_xlsx_stream.py -q
```

Expected: collection fails because `finproof.data.xlsx_stream` does not exist.

- [ ] **Step 5: Implement secure workbook metadata parsing**

In `src/finproof/data/xlsx_stream.py`:

- define namespace constants for spreadsheet, relationships, and package relationships;
- open only `source.verified_absolute_path`;
- parse `xl/workbook.xml` and `xl/_rels/workbook.xml.rels` with `etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)`;
- resolve the exact declared sheet name and normalize its relationship target with `PurePosixPath`;
- reject targets that are absolute, contain `..`, or resolve outside `xl/`;
- read shared strings once using `iterparse(resolve_entities=False, no_network=True, recover=False, huge_tree=False)`;
- convert `BadZipFile`, missing ZIP members, invalid relationship IDs, `XMLSyntaxError`, invalid cell references, and invalid shared-string indexes into `MALFORMED_WORKBOOK`.

Keep these helpers private: `_sheet_target`, `_shared_strings`, `_column_number`, `_column_letter`, and `_cell_raw_value`.

- [ ] **Step 6: Implement streaming row emission and validation**

Use:

```python
context = etree.iterparse(
    worksheet_stream,
    events=("end",),
    tag=f"{MAIN_NS}row",
    resolve_entities=False,
    no_network=True,
    recover=False,
    huge_tree=False,
)
```

For each row:

1. require a positive integer `r` attribute;
2. build a dictionary keyed by one-based column number;
3. reject a duplicate key before assignment;
4. reject any `<f>` descendant before reading a cached value;
5. obtain inline/shared/plain/boolean raw strings without trimming;
6. treat the first emitted row as header row 1 and compare exact ordered values with `source.expected_headers`;
7. reject a nonblank value beyond the header width;
8. pad every data row to the exact header width;
9. create ordered `SourceCell` values and a `SourceRow`;
10. clear the row and delete preceding siblings so parsed XML cannot accumulate.

Count emitted data rows. After normal iterator exhaustion, compare the count with `source.expected_rows` and raise `ROW_COUNT_MISMATCH` if unequal. Do not catch `GeneratorExit` and do not claim full validation on early close.

- [ ] **Step 7: Run reader tests to GREEN and verify public API shape**

Run:

```bash
uv run pytest tests/source_contract/test_xlsx_stream.py -q
uv run python -c "import inspect; from finproof.data.xlsx_stream import iter_xlsx_rows; print(inspect.signature(iter_xlsx_rows))"
uv run ruff format --check src/finproof/data/xlsx_stream.py tests/helpers/xlsx.py tests/source_contract/test_xlsx_stream.py
uv run ruff check src/finproof/data/xlsx_stream.py tests/helpers/xlsx.py tests/source_contract/test_xlsx_stream.py
uv run mypy src/finproof/data/xlsx_stream.py tests/helpers/xlsx.py tests/source_contract/test_xlsx_stream.py
```

Expected signature: `(source: VerifiedSourceFile) -> Iterator[SourceRow]`; all tests/checks pass.

- [ ] **Step 8: Commit the streaming-reader checkpoint**

```bash
git add src/finproof/data/xlsx_stream.py tests/helpers tests/source_contract/test_xlsx_stream.py
git commit -m "feat: stream verified XLSX source rows"
```

---

### Task 5: Prove official full-source lineage and bootstrap-reader parity

**Files:**
- Create: `tests/source_contract/test_official_xlsx_lineage.py`

**Interfaces:**
- Consumes: official `VerifiedSourceSet`, production `iter_xlsx_rows`, and independent `tools.xlsx_stream.iter_table_dicts`.
- Proves: exact four-table counts, total count, first-row values, lineage metadata, column widths, and selected parity values.

- [ ] **Step 1: Write the official full-lineage acceptance contract**

Create `tests/source_contract/test_official_xlsx_lineage.py`:

```python
from collections import Counter
from pathlib import Path

import pytest

from finproof.data.source_manifest import SourceFileManifest
from finproof.data.xlsx_stream import iter_xlsx_rows

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROWS = {
    "PRBD01N001": 42_394,
    "PREF01N001": 1_734,
    "PREF02N001": 5_646,
    "PRFD01N001": 95_619,
}


@pytest.mark.source_contract
@pytest.mark.slow
def test_official_workbooks_stream_with_complete_lineage() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")
    observed: Counter[str] = Counter()

    for table_id, expected_rows in EXPECTED_ROWS.items():
        source = verified.data_file(table_id)
        for row in iter_xlsx_rows(source):
            observed[table_id] += 1
            assert row.source_table == table_id
            assert row.source_file == source.manifest_relative_path
            assert row.source_sheet == source.sheet_name
            assert row.source_checksum == source.sha256
            assert row.source_snapshot_date == source.snapshot_date
            assert len(row.cells) == source.expected_columns
            assert row.raw_payload == tuple(cell.raw_value for cell in row.cells)
        assert observed[table_id] == expected_rows

    assert sum(observed.values()) == 145_393
```

Add a separate nonduplicated first-row test:

```python
def test_official_first_bond_row_preserves_exact_values() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    source = manifest.verify(ROOT / "source_material").data_file("PRBD01N001")
    row = next(iter_xlsx_rows(source))

    assert row.source_row_number == 2
    assert row.cell("PD_NO").raw_value == "KR101501DA16"
    assert row.cell("PD_NM").raw_value == "국민주택1종채권 20-01"
```

- [ ] **Step 2: Write the independent-reader parity contract**

For each official table, compare the production reader and `tools.xlsx_stream.iter_table_dicts` at Excel rows 2, the midpoint, and the final row. Add this helper and assert both readers return the same mapping:

```python
def _selected_rows(source: VerifiedSourceFile) -> dict[int, dict[str, str]]:
    wanted = {2, source.expected_rows // 2 + 2, source.expected_rows + 1}
    return {
        row.source_row_number: {
            cell.column_name: cell.raw_value for cell in row.cells
        }
        for row in iter_xlsx_rows(source)
        if row.source_row_number in wanted
    }
```

Build the bootstrap-reader mapping from `iter_table_dicts(source.verified_absolute_path, source.sheet_name)` using the same `wanted` set. The full-lineage test above exhausts every production iterator and separately proves row-count validation.

- [ ] **Step 3: Run the official acceptance contracts**

Run:

```bash
uv run pytest tests/source_contract/test_official_xlsx_lineage.py -q -m source_contract
```

Expected: the acceptance contracts pass if Tasks 1–4 fully implement the approved behavior. These tests add full-source evidence rather than new production behavior, so a synthetic RED is neither required nor permitted. If a contract fails, treat it as an unexplained implementation defect and follow Step 4.

- [ ] **Step 4: Make only evidence-driven reader corrections**

If an official contract exposes a reader defect, isolate one failing table/row, write or reduce a focused fixture regression in `test_xlsx_stream.py`, observe it fail, then make the smallest correction in `xlsx_stream.py`. Do not weaken an official expectation or change source files.

If no reader defect appears, leave production code unchanged.

- [ ] **Step 5: Run official, audit, and quality checks**

Run:

```bash
uv run pytest tests/source_contract -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/extract_schema_catalog.py --check
uv run ruff format --check src tests tools
uv run ruff check src tests tools
uv run mypy src tests tools
```

Expected: production/source parity passes, official counts remain `145,393`, schema catalog remains `207`, and all checks pass.

- [ ] **Step 6: Commit the official-contract checkpoint**

```bash
git add tests/source_contract/test_official_xlsx_lineage.py
git commit -m "test: enforce official source lineage"
```

---

### Task 6: Record Task 2 evidence and complete independent review

**Files:**
- Modify: `docs/implementation/STATUS.md`
- Modify: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`
- Modify: this plan's checkboxes

**Interfaces:**
- Produces: durable RED/GREEN evidence, exact observed commands/results, commit hashes, remaining A-011 boundary, and Phase 1 Task 3 as the exact next task.
- Does not mark the Phase 1 gate complete.

- [ ] **Step 1: Run the complete Task 2 and repository gates**

From the isolated Task 2 worktree, run:

```bash
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run pytest tests/source_contract -q -m source_contract
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/extract_schema_catalog.py --check
PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files
git diff --check
```

Record exact counts and output summaries; do not write expected values as observed results before running them.

- [ ] **Step 2: Update authoritative task/status documentation**

In `docs/implementation/STATUS.md`:

- mark only Phase 1 Task 2 complete;
- record every focused RED reason and GREEN result;
- record the final command outputs from Step 1;
- record every Task 2 commit hash;
- state that A-002 is implemented under D-017;
- state that A-011 remains open only for later quality/evidence schemas;
- name `Phase 1 Task 3: normalize domestic bonds and domestic listed products` as the exact next task.

In the Phase 1 plan, mark Task 2 steps complete only after their evidence exists. Do not mark Task 3 or the Phase 1 gate complete.

- [ ] **Step 3: Commit the status checkpoint**

```bash
git add docs/implementation/STATUS.md docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md docs/superpowers/plans/2026-08-13-phase1-task2-source-ingestion.md
git commit -m "docs: record Phase 1 Task 2 verification"
```

- [ ] **Step 4: Request independent code review**

Review every changed file from the Task 2 branch base through HEAD against:

- `AGENTS.md`;
- D-017 and the approved Task 2 design;
- this implementation plan;
- strict TDD evidence;
- source-fidelity, path, XML, error-leakage, iterator-completion, and memory-boundary risks;
- the explicit requirement that Task 3 behavior remains untouched.

Classify findings as Critical, Important, or Minor. Correct Critical and Important findings under strict TDD, rerun the full Step 1 gate, update status evidence, and request re-review until none remain.

- [ ] **Step 5: Verify the final reviewed tree**

On the final reviewed HEAD, rerun every Step 1 command and then:

```bash
git status --short --branch
test -z "$(git status --porcelain)"
```

Expected: all gates pass and the feature worktree is clean. Then use `superpowers:finishing-a-development-branch` and let the user choose local merge, PR, or branch preservation.
