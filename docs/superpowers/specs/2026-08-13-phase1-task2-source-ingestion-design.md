# Phase 1 Task 2 — Verified Source Manifest and Streaming XLSX Lineage Design

**Date:** 2026-08-13

**Status:** Approved for implementation planning

## 1. Goal

Implement only Phase 1 Task 2: turn the checked-in official-source manifest and schema catalog into verified, immutable source descriptors, then stream each official data workbook into typed rows and cells with complete raw lineage.

This task establishes the trusted input boundary for later normalization. It does not parse financial types, normalize product data, quarantine malformed products, build artifacts, query data, or serve answers.

## 2. Chosen boundary

Production XLSX ingestion accepts a `VerifiedSourceFile`, not an arbitrary path plus caller-supplied table and sheet strings.

```text
input_manifest.json + schema_catalog.json
                  -> strict models
                  -> path, size, SHA-256, snapshot, table, sheet, header checks
                  -> immutable VerifiedSourceSet
                  -> one VerifiedSourceFile per official data workbook
                  -> iter_xlsx_rows(verified_source)
                  -> Iterator[SourceRow]
```

This prevents a caller from pairing an overseas workbook with a domestic-bond table ID, reading a modified workbook without checksum verification, or attaching a false snapshot to source rows. Python objects are not cryptographic capabilities; the guarantee is an explicit production API boundary, strict construction through manifest verification, and tests that prohibit the path-based production reader.

## 3. Components and interfaces

### Strict manifest and catalog models

`finproof.data.source_manifest` owns strict Pydantic models with `extra="forbid"` for `source_material/input_manifest.json` and the table/header subset of `source_material/schema_catalog.json`.

The public flow is:

```python
manifest = SourceFileManifest.load(manifest_path, schema_catalog_path)
verified_sources = manifest.verify(base_dir)
bond_source = verified_sources.data_file("PRBD01N001")
```

`SourceFileManifest.load()` validates:

- manifest and catalog versions;
- the official snapshot date `2026-07-11` in both files;
- exactly one data workbook and one schema workbook for each of `PRBD01N001`, `PREF01N001`, `PREF02N001`, and `PRFD01N001`;
- one official task PDF;
- data-workbook table, sheet, expected row, and expected column metadata;
- catalog table IDs, ordered header names, and column counts;
- agreement between manifest column counts and catalog column counts;
- no missing, duplicated, or unexpected official table identities.

`verify(base_dir)` then validates every manifest file before returning any verified set:

- manifest-relative paths only;
- resolved paths remain under the resolved `base_dir`;
- regular files only, with no symlink target accepted for an official input;
- exact byte size;
- chunked SHA-256 equality.

Verification is all-or-nothing. A partially verified set is never returned.

### Verified source descriptors

`VerifiedSourceSet` is immutable and provides lookup by table ID. `data_file(table_id)` returns an immutable `VerifiedSourceFile` containing:

```text
manifest_relative_path
verified_absolute_path          # internal file access only
kind
table_id
sheet_name
snapshot_date
sha256
expected_rows
expected_columns
expected_headers
```

The absolute path is never copied into evidence, logs intended for users, API output, or domain errors. The manifest-relative path is the durable source identity.

### Raw lineage models

`finproof.domain.source` defines frozen Pydantic models:

```text
SourceCell
- column_name
- excel_column_number           # one-based
- excel_column_letter
- raw_value
- applicable_date               # date | None

SourceRow
- source_table
- source_file                   # manifest-relative path
- source_sheet
- source_row_number             # Excel row number; header is row 1
- source_checksum
- source_snapshot_date
- raw_payload                   # tuple of exact raw strings in header order
- cells                         # tuple[SourceCell, ...] in header order
```

`SourceRow.cell(column_name)` performs exact header-name lookup and returns the cell without normalizing it. The row plus cell contains every raw locator component needed to construct later transformed-value and evidence records.

`source_snapshot_date` and `SourceCell.applicable_date` are different concepts. The official snapshot is always `2026-07-11` for evaluation sources. A cell-specific applicable date is `None` at raw-reader time unless the source contract directly supplies it without interpretation. Task 2 does not copy the snapshot into every cell as a guessed applicable date. Later versioned normalization rules may derive or attach an applicable date while retaining the complete row/cell lineage.

### Streaming XLSX reader

`finproof.data.xlsx_stream.iter_xlsx_rows(source: VerifiedSourceFile) -> Iterator[SourceRow]` is the only production row-reader interface.

It uses `zipfile.ZipFile` and hardened `lxml.etree.iterparse` to:

- resolve the manifest-declared sheet through workbook relationships;
- load shared strings once per workbook;
- reject XML entity/network resolution;
- parse the first worksheet row as the header;
- compare the exact ordered header with `expected_headers` from the schema catalog;
- translate Excel cell references to one-based numbers and letters;
- preserve omitted intermediate and trailing cells as empty raw strings;
- emit rows incrementally without materializing the worksheet;
- clear processed XML elements to bound worksheet memory;
- validate the final emitted row count when the iterator is exhausted.

A caller that deliberately stops iteration early has consumed only a prefix and has not established full-workbook row-count validity. All official ingestion and source-contract gates exhaust the iterator.

## 4. Raw-value policy

The reader performs no financial normalization. Examples remain exact strings:

```text
"00123"   -> "00123"
"  채권 " -> "  채권 "
"NULL"    -> "NULL"
"0"       -> "0"
empty cell -> ""
```

Header names are compared exactly with the ordered schema catalog. No trimming or case folding is used to make an invalid official header appear valid. Numeric conversion, date parsing, whitespace normalization, literal-null handling, sentinel handling, and quality classification begin in later tasks.

Formula cells are rejected. The official data workbooks contain no formulas, and Task 2 does not execute or trust formula expressions or cached formula values as immutable raw source data.

## 5. Failure behavior

Expected input failures raise `SourceContractError` with a stable machine-readable category, a manifest-relative file name when available, an optional table ID, and a safe description.

Categories include:

```text
manifest_invalid
catalog_invalid
path_escape
file_missing
file_type_invalid
size_mismatch
checksum_mismatch
snapshot_mismatch
duplicate_table
missing_sheet
column_count_mismatch
header_mismatch
blank_header
duplicate_header
duplicate_cell
row_wider_than_header
row_count_mismatch
unsupported_formula
malformed_workbook
```

No source-contract error suggests updating the manifest to fit observed data. It exposes no absolute local path, stack trace, workbook payload, or raw row. A checksum, snapshot, sheet, header, row-count, or workbook-structure mismatch is a stop condition.

## 6. Test strategy

Every production behavior follows strict red-green-refactor TDD.

### Manifest and catalog tests

- official nine-file manifest and four-table catalog verify successfully;
- all four data files are retrieved by exact table ID;
- checksum, byte-size, snapshot, path-escape, symlink, missing-file, duplicate-table, missing-table, extra-field, and manifest/catalog disagreement cases fail with the expected category;
- verification returns no usable set if any file fails.

### Small XLSX fixture tests

- the reader requires `VerifiedSourceFile` rather than a path-based public interface;
- missing sheet, blank/duplicate/mismatched header, wrong column count, duplicate cell reference, nonblank cell wider than the header, formula cell, and malformed XML fail closed;
- intermediate and trailing omissions become `""` without shifting later columns;
- raw strings such as `"00123"`, padded text, `"NULL"`, and `"0"` remain unchanged;
- Excel row numbers, column numbers, and column letters are exact;
- iterator exhaustion enforces the expected row count.

Small fixtures use their own manifest and schema catalog and pass through the same verification factory as official data. Tests do not gain a separate unsafe reader API.

### Official source-contract tests

- the first domestic-bond data row is Excel row 2;
- `PD_NO == "KR101501DA16"` and `PD_NM == "국민주택1종채권 20-01"`;
- every row carries the verified relative file, table, sheet, SHA-256, and snapshot;
- every row has the manifest/catalog column count;
- official counts are `42,394`, `1,734`, `5,646`, and `95,619`, totaling `145,393`;
- production-reader counts and selected raw values agree with the independent bootstrap reader;
- the existing frozen source audit remains unchanged.

Full-workbook contracts use `source_contract` and `slow` markers but remain part of the Task 2 final gate and CI. The structural streaming test establishes incremental `iterparse` consumption and element clearing; exact peak-memory benchmarking belongs to the later full artifact-build task.

## 7. Scope exclusions

Task 2 does not implement:

- numeric, date, whitespace, literal-null, or sentinel normalization;
- bond/listed-product state or eligibility;
- public-fund item collapse or malformed-product quarantine;
- Parquet, DuckDB, artifact manifests, or reports;
- search, sort, rank, aggregation, evidence claims, API, or HCX behavior;
- removal of `tools/xlsx_stream.py`.

The standard-library `tools/xlsx_stream.py` remains an independent pre-install verification path. Production code does not import it. Cross-implementation source-contract tests detect result drift without coupling either implementation to the other.

## 8. Alternatives considered

- **Chosen — verified descriptor input:** separates verification from parsing while making the trusted boundary explicit. It provides the strongest source-fidelity guarantee with one additional type.
- **Rejected — path, table ID, and sheet passed separately:** simple to call and convenient for ad hoc fixtures, but permits incorrect metadata combinations and unverified files unless every caller repeats the contract correctly.
- **Rejected — manifest plus table ID passed directly to the reader:** prevents caller-invented paths, but combines manifest lookup, hashing, and XLSX parsing in one component, repeats verification work, and makes the responsibilities harder to test independently.

## 9. Decision-log effect

This design resolves A-002 by making checksum, dataset snapshot, exact row/cell location, raw payload/value, and an explicit optional applicable-date slot part of the frozen raw-lineage contract.

A-011 is only partially resolved. Task 2 freezes the producer-side raw lineage required here. Quality-issue and evidence-record schemas remain open until their first producers and consumers in Phase 1 Task 4 and Phase 2 Task 6.

## 10. Acceptance criteria

- Official files cannot enter the production reader without manifest/catalog verification.
- Modified, misplaced, structurally different, or incomplete official inputs fail closed.
- All four official data workbooks stream without loading the worksheet into memory.
- Every emitted raw value is traceable to manifest-relative file, table, sheet, Excel row, Excel column, verified checksum, snapshot, exact raw string, and explicit applicable-date state.
- The official total remains `145,393` rows at snapshot `2026-07-11`.
- Existing Task 1 behavior and bootstrap verification remain green.
- Only Phase 1 Task 2 is marked complete after implementation and verification; Phase 1 Task 3 remains the exact next task.
