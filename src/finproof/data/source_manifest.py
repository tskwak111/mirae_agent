"""Strict loading for the immutable official manifest and schema catalog."""

from __future__ import annotations

import json
from datetime import date
from json import JSONDecodeError
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from finproof.core.errors import SourceContractError, SourceErrorCode

OFFICIAL_SNAPSHOT = date(2026, 7, 11)
OFFICIAL_TABLE_IDS = (
    "PRBD01N001",
    "PREF01N001",
    "PREF02N001",
    "PRFD01N001",
)


class StrictModel(BaseModel):
    """Immutable model that rejects source fields outside the frozen contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class TaskPdfEntry(StrictModel):
    """The one official competition task document."""

    path: PurePosixPath
    kind: Literal["official_task_pdf"]
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DataFileEntry(StrictModel):
    """Expected metadata for one official data workbook."""

    path: PurePosixPath
    kind: Literal["data"]
    table_id: str
    sheet_name: str
    expected_rows: int = Field(ge=0)
    expected_columns: int = Field(gt=0)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SchemaFileEntry(StrictModel):
    """Expected metadata for one official schema workbook."""

    path: PurePosixPath
    kind: Literal["schema"]
    table_id: str
    sheet_names: tuple[str, ...]
    expected_columns: int = Field(gt=0)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CatalogColumn(StrictModel):
    """One schema-catalog header in source-defined order."""

    column_name: str
    column_type: str
    example: str
    key: str
    name_ko: str
    schema_excel_row: int = Field(gt=0)


class CatalogTable(StrictModel):
    """The ordered columns for one source table."""

    axis_warning: str
    column_count: int = Field(gt=0)
    columns: tuple[CatalogColumn, ...]
    sample: dict[str, str] = Field(default_factory=dict)
    sample_axis_columns: tuple[str, ...] = ()
    schema_file: str = ""
    source_snapshot_label: str = ""
    table_id: str = ""
    total_row_label: str = ""


class SourceSchemaCatalog(StrictModel):
    """Strict ordered source headers, paired with the input manifest on load."""

    catalog_version: str
    snapshot_date: date
    tables: dict[str, CatalogTable]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        """Reject catalog table/header ambiguity before a workbook is read."""
        if self.snapshot_date != OFFICIAL_SNAPSHOT:
            raise SourceContractError(
                SourceErrorCode.SNAPSHOT_MISMATCH,
                "schema catalog snapshot does not match the official snapshot",
            )
        if tuple(self.tables) != OFFICIAL_TABLE_IDS:
            raise SourceContractError(
                SourceErrorCode.CATALOG_INVALID,
                "schema catalog table IDs must match the official ordered table set",
            )
        for table_id, table in self.tables.items():
            headers = tuple(column.column_name for column in table.columns)
            if table.column_count != len(headers):
                raise SourceContractError(
                    SourceErrorCode.COLUMN_COUNT_MISMATCH,
                    "schema catalog column count does not match its ordered headers",
                    table_id=table_id,
                )
            if any(not header for header in headers):
                raise SourceContractError(
                    SourceErrorCode.BLANK_HEADER,
                    "schema catalog headers must not be blank",
                    table_id=table_id,
                )
            if len(set(headers)) != len(headers):
                raise SourceContractError(
                    SourceErrorCode.DUPLICATE_HEADER,
                    "schema catalog headers must be unique",
                    table_id=table_id,
                )
        return self


ManifestEntry = Annotated[
    TaskPdfEntry | DataFileEntry | SchemaFileEntry,
    Field(discriminator="kind"),
]


class SourceFileManifest(StrictModel):
    """The complete immutable official input manifest and ordered schema catalog."""

    manifest_version: str
    competition: str
    snapshot_date: date
    files: tuple[ManifestEntry, ...]
    schema_catalog: SourceSchemaCatalog = Field(exclude=True, repr=False)

    @classmethod
    def load(cls, manifest_path: Path, schema_catalog_path: Path) -> Self:
        """Load both metadata files and fail closed on malformed source contracts."""
        manifest_payload = _load_json(manifest_path, SourceErrorCode.MANIFEST_INVALID)
        catalog_payload = _load_json(schema_catalog_path, SourceErrorCode.CATALOG_INVALID)
        try:
            catalog = SourceSchemaCatalog.model_validate(catalog_payload)
        except SourceContractError:
            raise
        except ValidationError as error:
            raise _invalid_error(SourceErrorCode.CATALOG_INVALID, error) from None
        try:
            return cls.model_validate(manifest_payload | {"schema_catalog": catalog.model_dump()})
        except SourceContractError:
            raise
        except ValidationError as error:
            raise _invalid_error(SourceErrorCode.MANIFEST_INVALID, error) from None

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        """Require the exact official source inventory and metadata agreement."""
        if self.snapshot_date != OFFICIAL_SNAPSHOT:
            raise SourceContractError(
                SourceErrorCode.SNAPSHOT_MISMATCH,
                "manifest snapshot does not match the official snapshot",
            )
        if self.snapshot_date != self.schema_catalog.snapshot_date:
            raise SourceContractError(
                SourceErrorCode.SNAPSHOT_MISMATCH,
                "manifest and schema catalog snapshots must agree",
            )

        task_pdfs = tuple(entry for entry in self.files if isinstance(entry, TaskPdfEntry))
        if len(task_pdfs) != 1:
            raise SourceContractError(
                SourceErrorCode.MANIFEST_INVALID,
                "manifest must contain exactly one official task PDF",
            )

        data_entries = self.data_files
        schema_entries = tuple(entry for entry in self.files if isinstance(entry, SchemaFileEntry))
        _validate_manifest_table_ids(data_entries, "data")
        _validate_manifest_table_ids(schema_entries, "schema")

        for table_id in OFFICIAL_TABLE_IDS:
            data_entry = self.data_entry(table_id)
            schema_entry = next(entry for entry in schema_entries if entry.table_id == table_id)
            catalog_table = self.schema_catalog.tables[table_id]
            if (
                data_entry.expected_columns != catalog_table.column_count
                or schema_entry.expected_columns != catalog_table.column_count
            ):
                raise SourceContractError(
                    SourceErrorCode.COLUMN_COUNT_MISMATCH,
                    "manifest and schema catalog column counts must agree",
                    table_id=table_id,
                )
        return self

    @property
    def data_files(self) -> tuple[DataFileEntry, ...]:
        """Return official data entries in their manifest-defined order."""
        return tuple(entry for entry in self.files if isinstance(entry, DataFileEntry))

    def data_entry(self, table_id: str) -> DataFileEntry:
        """Return the exact official data entry for one table identifier."""
        for entry in self.data_files:
            if entry.table_id == table_id:
                return entry
        raise KeyError(table_id)

    def expected_headers(self, table_id: str) -> tuple[str, ...]:
        """Return the immutable source header order for one official table."""
        table = self.schema_catalog.tables[table_id]
        return tuple(column.column_name for column in table.columns)


def _load_json(path: Path, error_code: SourceErrorCode) -> dict[str, object]:
    """Read JSON without allowing parser or filesystem details into errors."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (JSONDecodeError, OSError):
        raise SourceContractError(error_code, "official metadata could not be read") from None
    if not isinstance(payload, dict):
        raise SourceContractError(error_code, "official metadata must be a JSON object")
    return cast(dict[str, object], payload)


def _invalid_error(code: SourceErrorCode, error: ValidationError) -> SourceContractError:
    """Convert Pydantic's detailed, local-input errors into one stable safe error."""
    del error
    return SourceContractError(code, "official metadata violates the required schema")


def _validate_manifest_table_ids(
    entries: tuple[DataFileEntry, ...] | tuple[SchemaFileEntry, ...], kind: str
) -> None:
    """Reject duplicate, missing, or unexpected source table identities."""
    table_ids = tuple(entry.table_id for entry in entries)
    if len(set(table_ids)) != len(table_ids):
        raise SourceContractError(
            SourceErrorCode.DUPLICATE_TABLE,
            f"manifest contains duplicate {kind} table entries",
        )
    if table_ids != OFFICIAL_TABLE_IDS:
        raise SourceContractError(
            SourceErrorCode.MANIFEST_INVALID,
            f"manifest {kind} table IDs must match the official ordered table set",
        )
