"""Canonical logical hashing for Task 5 artifacts."""

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import PurePosixPath
from typing import Protocol, cast

from finproof.data.artifacts.expected_contract import (
    ExpectedLogicalInput,
    ExpectedLogicalTable,
    ExpectedSemanticReport,
)


class ColumnSpecIdentity(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def logical_type(self) -> str: ...

    @property
    def arrow_type(self) -> str: ...

    @property
    def duckdb_type(self) -> str: ...

    @property
    def nullable(self) -> bool: ...


class TableSpecIdentity(Protocol):
    @property
    def table_name(self) -> str: ...

    @property
    def grain(self) -> str: ...

    @property
    def columns(self) -> tuple[ColumnSpecIdentity, ...]: ...

    @property
    def unique_key(self) -> tuple[str, ...]: ...

    @property
    def sort_key(self) -> tuple[str, ...]: ...

    @property
    def logical_projection(self) -> tuple[str, ...]: ...


class SemanticReportIdentity(Protocol):
    @property
    def report_id(self) -> str: ...

    def semantic_projection(self) -> Mapping[str, object]: ...


class ManifestLogicalIdentity(Protocol):
    @property
    def manifest_version(self) -> str: ...

    @property
    def artifact_contract_version(self) -> str: ...

    @property
    def artifact_set_id(self) -> str: ...

    @property
    def dataset_version(self) -> date: ...

    @property
    def logical_inputs(self) -> tuple[ExpectedLogicalInput, ...]: ...

    @property
    def versions(self) -> object: ...

    @property
    def tables(self) -> tuple[ExpectedLogicalTable, ...]: ...

    @property
    def reports(self) -> tuple[ExpectedSemanticReport, ...]: ...


def canonical_scalar(value: object) -> object:
    if value is None:
        return None
    if type(value) in {bool, int, str}:
        return value
    if type(value) is Decimal:
        if not value.is_finite():
            raise ValueError("Decimal must be finite")
        if value.is_zero():
            return "0"
        rendered = format(value, "f")
        signless = rendered.removeprefix("-")
        integer, separator, fraction = signless.partition(".")
        fraction = fraction.rstrip("0")
        significant_integer = integer.lstrip("0") or "0"
        if len(significant_integer) > 20 or len(fraction) > 18:
            raise ValueError("Decimal does not fit decimal128(38,18)")
        prefix = "-" if value.is_signed() else ""
        return prefix + integer + (f".{fraction}" if separator and fraction else "")
    if type(value) is datetime:
        offset = value.utcoffset()
        rendered = value.isoformat(timespec="microseconds")
        if value.tzinfo is None:
            return rendered
        if offset != timedelta(0):
            raise ValueError("aware datetime must have exact UTC offset")
        return rendered.removesuffix("+00:00") + "Z"
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, (StrEnum, Enum)):
        if type(value.value) is not str:
            raise TypeError("enum value must be an exact string")
        return value.value
    if isinstance(value, PurePosixPath):
        return value.as_posix()
    if type(value) in {list, tuple}:
        sequence = cast(list[object] | tuple[object, ...], value)
        return [canonical_scalar(item) for item in sequence]
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise TypeError("mapping keys must be exact strings")
        return {key: canonical_scalar(value[key]) for key in sorted(value)}
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json_bytes(value: object, *, terminal_newline: bool = True) -> bytes:
    encoded = json.dumps(
        canonical_scalar(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return encoded + (b"\n" if terminal_newline else b"")


def _require_exact_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise TypeError(f"{field} must be a non-empty exact string")
    return value


def _require_name_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field} must be an exact tuple")
    for name in value:
        _require_exact_text(name, field=field)
    return value


def _validate_table_spec(spec: TableSpecIdentity) -> None:
    _require_exact_text(spec.table_name, field="table_name")
    _require_exact_text(spec.grain, field="grain")
    if type(spec.columns) is not tuple or not spec.columns:
        raise TypeError("columns must be a non-empty exact tuple")
    column_names: list[str] = []
    for column in spec.columns:
        column_names.append(_require_exact_text(column.name, field="column.name"))
        _require_exact_text(column.logical_type, field="column.logical_type")
        _require_exact_text(column.arrow_type, field="column.arrow_type")
        _require_exact_text(column.duckdb_type, field="column.duckdb_type")
        if type(column.nullable) is not bool:
            raise TypeError("column.nullable must be an exact bool")
    if len(column_names) != len(set(column_names)):
        raise ValueError("column names must be unique")

    known_names = set(column_names)
    unique_key = _require_name_tuple(spec.unique_key, field="unique_key")
    sort_key = _require_name_tuple(spec.sort_key, field="sort_key")
    projection = _require_name_tuple(spec.logical_projection, field="logical_projection")
    if not projection or len(projection) != len(set(projection)):
        raise ValueError("logical_projection must be non-empty and unique")
    if not set(unique_key).issubset(known_names):
        raise ValueError("unique_key contains an unknown column")
    if not set(sort_key).issubset(known_names):
        raise ValueError("sort_key contains an unknown column")
    if not set(projection).issubset(known_names):
        raise ValueError("logical_projection contains an unknown column")


def schema_sha256(spec: TableSpecIdentity) -> str:
    _validate_table_spec(spec)
    projection = {
        "table_name": spec.table_name,
        "grain": spec.grain,
        "columns": [
            {
                "name": column.name,
                "logical_type": column.logical_type,
                "arrow_type": column.arrow_type,
                "duckdb_type": column.duckdb_type,
                "nullable": column.nullable,
            }
            for column in spec.columns
        ],
        "unique_key": spec.unique_key,
        "sort_key": spec.sort_key,
    }
    return hashlib.sha256(canonical_json_bytes(projection)).hexdigest()


def table_logical_hash(
    spec: TableSpecIdentity,
    *,
    row_count: int,
    rows: Iterable[Mapping[str, object]],
) -> str:
    if type(row_count) is not int or row_count < 0:
        raise TypeError("row_count must be an exact nonnegative integer")
    digest = hashlib.sha256()
    digest.update(
        canonical_json_bytes(
            {
                "schema_sha256": schema_sha256(spec),
                "logical_projection": spec.logical_projection,
                "row_count": row_count,
            }
        )
    )
    observed_count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("table row must be a mapping with unique keys")
        row_keys = tuple(row)
        if any(type(key) is not str for key in row_keys) or len(row_keys) != len(set(row_keys)):
            raise TypeError("table row must be a mapping with unique keys")
        if set(row_keys) != set(spec.logical_projection):
            raise ValueError("row keys must equal the logical projection")
        try:
            row_snapshot = {key: row[key] for key in row_keys}
        except Exception as exc:
            raise TypeError("table row changed during snapshot") from exc
        digest.update(canonical_json_bytes(row_snapshot))
        observed_count += 1
    if observed_count != row_count:
        raise ValueError("observed row count does not match row_count")
    return digest.hexdigest()


def report_logical_hash(report: SemanticReportIdentity) -> str:
    report_id = _require_exact_text(report.report_id, field="report_id")
    projection = report.semantic_projection()
    if not isinstance(projection, Mapping):
        raise TypeError("semantic_projection must return a mapping")
    model_fields = getattr(type(report), "model_fields", None)
    if not isinstance(model_fields, Mapping):
        raise TypeError("semantic report must declare Pydantic model fields")
    if tuple(projection) != tuple(model_fields):
        raise ValueError("semantic projection must match declared fields exactly")
    if projection.get("report_id") != report_id:
        raise ValueError("semantic projection report_id mismatch")
    return hashlib.sha256(canonical_json_bytes(projection)).hexdigest()


def manifest_logical_hash(manifest: ManifestLogicalIdentity) -> str:
    manifest_version = _require_exact_text(manifest.manifest_version, field="manifest_version")
    artifact_contract_version = _require_exact_text(
        manifest.artifact_contract_version, field="artifact_contract_version"
    )
    artifact_set_id = _require_exact_text(manifest.artifact_set_id, field="artifact_set_id")
    if type(manifest.dataset_version) is not date:
        raise TypeError("dataset_version must be an exact date")

    logical_inputs = _validated_model_entries(manifest.logical_inputs, ExpectedLogicalInput)
    tables = _validated_model_entries(manifest.tables, ExpectedLogicalTable)
    reports = _validated_model_entries(manifest.reports, ExpectedSemanticReport)
    versions = _validated_versions(manifest.versions)
    projection = {
        "manifest_version": manifest_version,
        "artifact_contract_version": artifact_contract_version,
        "artifact_set_id": artifact_set_id,
        "dataset_version": manifest.dataset_version,
        "logical_inputs": logical_inputs,
        "versions": versions,
        "tables": tables,
        "reports": reports,
    }
    return hashlib.sha256(canonical_json_bytes(projection)).hexdigest()


def _validated_model_entries[EntryModel: object](
    entries: object, entry_type: type[EntryModel]
) -> list[Mapping[str, object]]:
    if type(entries) is not tuple:
        raise TypeError("logical inventory must be an exact tuple")
    validated: list[Mapping[str, object]] = []
    for entry in entries:
        if type(entry) is not entry_type:
            raise TypeError("logical inventory entry has the wrong exact type")
        dump = getattr(entry, "model_dump", None)
        validate = getattr(entry_type, "model_validate", None)
        if not callable(dump) or not callable(validate):
            raise TypeError("logical inventory entries must be strict models")
        data = dump(mode="python", warnings="none")
        validate(data, strict=True)
        validated.append(data)
    return validated


_VERSION_FIELDS = (
    "dataset_version",
    "metric_registry_version",
    "state_rule_version",
    "quality_rule_version",
    "rating_rule_version",
    "answer_policy_version",
    "planner_version",
)


def _validated_versions(versions: object) -> Mapping[str, object]:
    model_fields = getattr(type(versions), "model_fields", None)
    dump = getattr(versions, "model_dump", None)
    if not isinstance(model_fields, Mapping) or not callable(dump):
        raise TypeError("versions must be a strict model")
    if tuple(model_fields) != _VERSION_FIELDS:
        raise ValueError("versions must have the exact seven fields")
    data = dump(mode="python", warnings="none")
    if type(data["dataset_version"]) is not date:
        raise TypeError("versions.dataset_version must be an exact date")
    if any(type(data[field]) is not str for field in _VERSION_FIELDS[1:]):
        raise TypeError("version identifiers must be exact strings")
    return cast(Mapping[str, object], data)
