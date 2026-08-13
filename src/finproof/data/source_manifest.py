"""Strict loading for the immutable official manifest and schema catalog."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from json import JSONDecodeError
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Annotated, Literal, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from finproof.core.errors import SourceContractError, SourceErrorCode

OFFICIAL_SNAPSHOT = date(2026, 7, 11)
OFFICIAL_TABLE_IDS = (
    "PRBD01N001",
    "PREF01N001",
    "PREF02N001",
    "PRFD01N001",
)


ManifestRelativePath = PurePosixPath


class StrictModel(BaseModel):
    """Immutable model that rejects source fields outside the frozen contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class VerifiedSourceFile(StrictModel):
    """One verified data workbook with a safe internal access path."""

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

    @model_validator(mode="after")
    def validate_verified_source_file(self) -> Self:
        """Require a descriptor that cannot escape its verified source root."""
        if self.manifest_relative_path.is_absolute() or ".." in self.manifest_relative_path.parts:
            raise ValueError("manifest_relative_path must be safe and traversal-free")
        if not self.verified_absolute_path.is_absolute():
            raise ValueError("verified_absolute_path must be absolute")
        if self.expected_columns != len(self.expected_headers):
            raise ValueError("expected_columns must match expected_headers")
        return self


class VerifiedSourceSet(StrictModel):
    """All verified data workbooks from one all-or-nothing source check."""

    data_files: tuple[VerifiedSourceFile, ...]

    @model_validator(mode="after")
    def validate_unique_table_ids(self) -> Self:
        """Prevent ambiguous lookup in a verified source set."""
        table_ids = tuple(source.table_id for source in self.data_files)
        if len(set(table_ids)) != len(table_ids):
            raise ValueError("data_files must have unique table IDs")
        return self

    def data_file(self, table_id: str) -> VerifiedSourceFile:
        """Return one verified data workbook by its exact official table ID."""
        for source in self.data_files:
            if source.table_id == table_id:
                return source
        raise KeyError(table_id)


class TaskPdfEntry(StrictModel):
    """The one official competition task document."""

    path: ManifestRelativePath
    kind: Literal["official_task_pdf"]
    size_bytes: int = Field(ge=0, strict=True)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DataFileEntry(StrictModel):
    """Expected metadata for one official data workbook."""

    path: ManifestRelativePath
    kind: Literal["data"]
    table_id: str
    sheet_name: str
    expected_rows: int = Field(ge=0, strict=True)
    expected_columns: int = Field(gt=0, strict=True)
    size_bytes: int = Field(ge=0, strict=True)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SchemaFileEntry(StrictModel):
    """Expected metadata for one official schema workbook."""

    path: ManifestRelativePath
    kind: Literal["schema"]
    table_id: str
    sheet_names: tuple[str, ...]
    expected_columns: int = Field(gt=0, strict=True)
    size_bytes: int = Field(ge=0, strict=True)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CatalogColumn(StrictModel):
    """One schema-catalog header in source-defined order."""

    column_name: str
    column_type: str
    example: str
    key: str
    name_ko: str
    schema_excel_row: int = Field(gt=0, strict=True)


class CatalogTable(StrictModel):
    """The ordered columns for one source table."""

    axis_warning: str
    column_count: int = Field(gt=0, strict=True)
    columns: tuple[CatalogColumn, ...]
    sample: Mapping[str, str] = Field(default_factory=dict, validate_default=True)
    sample_axis_columns: tuple[str, ...] = ()
    schema_file: str = ""
    source_snapshot_label: str = ""
    table_id: str = ""
    total_row_label: str = ""

    @field_validator("sample", mode="after")
    @classmethod
    def freeze_sample(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        """Keep nested catalog sample metadata immutable after validation."""
        return MappingProxyType(dict(value))

    @field_serializer("sample")
    def serialize_sample(self, value: Mapping[str, str]) -> dict[str, str]:
        """Serialize immutable sample metadata as an ordered JSON object."""
        return dict(value)


class SourceSchemaCatalog(StrictModel):
    """Strict ordered source headers, paired with the input manifest on load."""

    catalog_version: Literal["1.0.0"]
    snapshot_date: date
    tables: Mapping[str, CatalogTable]

    @field_validator("tables", mode="after")
    @classmethod
    def freeze_tables(cls, value: Mapping[str, CatalogTable]) -> Mapping[str, CatalogTable]:
        """Prevent replacement of a table after catalog validation."""
        return MappingProxyType(dict(value))

    @field_serializer("tables")
    def serialize_tables(self, value: Mapping[str, CatalogTable]) -> dict[str, CatalogTable]:
        """Serialize the immutable ordered mapping predictably."""
        return dict(value)

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

    manifest_version: Literal["1.0.0"]
    competition: str
    snapshot_date: date
    files: tuple[ManifestEntry, ...]
    schema_catalog: SourceSchemaCatalog = Field(exclude=True, repr=False)

    @classmethod
    def load(cls, manifest_path: Path, schema_catalog_path: Path) -> Self:
        """Load both metadata files and fail closed on malformed source contracts."""
        manifest_payload = _load_json(manifest_path, SourceErrorCode.MANIFEST_INVALID)
        catalog_payload = _load_json(schema_catalog_path, SourceErrorCode.CATALOG_INVALID)
        if "schema_catalog" in manifest_payload:
            raise SourceContractError(
                SourceErrorCode.MANIFEST_INVALID,
                "manifest must not contain an injected schema catalog",
            )
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

    def verify(self, base_dir: Path) -> VerifiedSourceSet:
        """Verify every official input before exposing any data workbook descriptor."""
        data_files: list[VerifiedSourceFile] = []
        for entry in self.files:
            verified_path = _safe_file(base_dir, entry.path)
            table_id = (
                entry.table_id if isinstance(entry, (DataFileEntry, SchemaFileEntry)) else None
            )
            try:
                size_bytes = verified_path.stat().st_size
            except OSError as error:
                raise _source_access_error(entry.path, error, table_id=table_id) from error
            if size_bytes != entry.size_bytes:
                raise SourceContractError(
                    SourceErrorCode.SIZE_MISMATCH,
                    "official input size does not match the manifest",
                    source_file=_safe_error_path(entry.path),
                    table_id=table_id,
                )
            try:
                sha256 = _sha256(verified_path)
            except OSError as error:
                raise _source_access_error(entry.path, error, table_id=table_id) from error
            if sha256 != entry.sha256:
                raise SourceContractError(
                    SourceErrorCode.CHECKSUM_MISMATCH,
                    "official input SHA-256 does not match the manifest",
                    source_file=_safe_error_path(entry.path),
                    table_id=table_id,
                )
            if isinstance(entry, DataFileEntry):
                data_files.append(
                    VerifiedSourceFile(
                        manifest_relative_path=entry.path,
                        verified_absolute_path=verified_path,
                        table_id=entry.table_id,
                        sheet_name=entry.sheet_name,
                        snapshot_date=self.snapshot_date,
                        sha256=entry.sha256,
                        expected_rows=entry.expected_rows,
                        expected_columns=entry.expected_columns,
                        expected_headers=self.expected_headers(entry.table_id),
                    )
                )
        return VerifiedSourceSet(data_files=tuple(data_files))


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


def _safe_file(base_dir: Path, relative: PurePosixPath) -> Path:
    """Resolve one manifest path without following links or escaping ``base_dir``."""
    error_source = _safe_error_path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise SourceContractError(
            SourceErrorCode.PATH_ESCAPE,
            "manifest path must remain under source root",
            source_file=error_source,
        )
    candidate = base_dir / Path(*relative.parts)
    try:
        current = base_dir
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise SourceContractError(
                    SourceErrorCode.FILE_TYPE_INVALID,
                    "official input path must not contain symlinks",
                    source_file=error_source,
                )
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as error:
        raise SourceContractError(
            SourceErrorCode.FILE_MISSING,
            "official input is missing",
            source_file=error_source,
        ) from error
    except OSError as error:
        raise _source_access_error(relative, error) from error
    except RuntimeError as error:
        raise SourceContractError(
            SourceErrorCode.FILE_TYPE_INVALID,
            "official input path could not be resolved safely",
            source_file=error_source,
        ) from error
    try:
        if not resolved.is_relative_to(base_dir.resolve()):
            raise SourceContractError(
                SourceErrorCode.PATH_ESCAPE,
                "manifest path must remain under source root",
                source_file=error_source,
            )
        if not resolved.is_file():
            raise SourceContractError(
                SourceErrorCode.FILE_TYPE_INVALID,
                "official input must be a regular file",
                source_file=error_source,
            )
    except OSError as error:
        raise _source_access_error(relative, error) from error
    except RuntimeError as error:
        raise SourceContractError(
            SourceErrorCode.FILE_TYPE_INVALID,
            "official input path could not be resolved safely",
            source_file=error_source,
        ) from error
    return resolved


def _safe_error_path(path: PurePosixPath) -> PurePosixPath | None:
    """Prevent absolute manifest input from leaking through error formatting."""
    return None if path.is_absolute() else path


def _source_access_error(
    path: PurePosixPath, error: OSError, *, table_id: str | None = None
) -> SourceContractError:
    """Map an OS access failure to a safe, stable source-contract error."""
    if isinstance(error, FileNotFoundError):
        return SourceContractError(
            SourceErrorCode.FILE_MISSING,
            "official input is missing",
            source_file=_safe_error_path(path),
            table_id=table_id,
        )
    return SourceContractError(
        SourceErrorCode.FILE_TYPE_INVALID,
        "official input could not be accessed safely",
        source_file=_safe_error_path(path),
        table_id=table_id,
    )


def _sha256(path: Path) -> str:
    """Calculate SHA-256 with bounded memory usage."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
