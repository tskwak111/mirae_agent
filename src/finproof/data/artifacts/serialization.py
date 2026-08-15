"""Strict canonical model and physical-row serialization."""

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from finproof.data.artifacts.table_specs import (
    TABLE_SPEC_BY_NAME,
    TableSpec,
    require_registered_spec,
    require_registered_table_spec,
)
from finproof.domain.bonds import BondInstrument
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.public_funds import FundItem, FundItemAttribute, FundItemValue
from finproof.domain.quality import DataQualityIssue
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue


class _ExplicitArtifactRow(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class BronzeSourceColumnRecord(_ExplicitArtifactRow):
    catalog_version: Literal["1.0.0"]
    source_snapshot_date: date
    source_table_order: int
    source_table: str
    source_column_number: int
    source_column_letter: str
    source_column_name: str
    source_declared_type: str
    source_example: str
    source_key_marker: str
    source_name_ko: str
    schema_file: str
    schema_excel_row: int


class BronzeSourceCellRecord(_ExplicitArtifactRow):
    source_table_order: int
    source_table: str
    source_file: PurePosixPath
    source_sheet: str
    source_row_number: int
    source_column_name: str
    source_column_number: int
    source_column_letter: str
    source_checksum: str
    source_snapshot_date: date
    source_applicable_date: date | None
    raw_value: str


class ExactCrossSourceLinkRecord(_ExplicitArtifactRow):
    link_id: str
    left_table: Literal["silver_domestic_listed_product"]
    left_product_id: str
    left_identifier_field: Literal["pd_itm_no"]
    right_table: Literal["silver_fund_item"]
    right_product_id: str
    right_identifier_field: Literal["ksd_itm_no"]
    matched_raw_identifier: str
    link_type: Literal["exact_identifier"]
    confidence: Decimal
    rule_id: Literal["cross_source.domestic_etf_public_fund.exact_raw_identifier"]
    rule_version: Literal["1.0.0"]


class ExactCrossSourceLinkEvidenceRecord(_ExplicitArtifactRow):
    link_id: str
    evidence_role: Literal["left_identifier", "right_identifier"]
    evidence_role_order: int
    evidence_ordinal: int
    raw_identifier: str
    source_table: str
    source_file: PurePosixPath
    source_sheet: str
    source_row_number: int
    source_column_name: str
    source_column_number: int
    source_column_letter: str
    source_checksum: str
    source_snapshot_date: date
    source_applicable_date: date | None


_EXPLICIT_MODEL_BY_SPEC_ID: dict[int, type[BaseModel]] = {
    id(TABLE_SPEC_BY_NAME["bronze_source_column"]): BronzeSourceColumnRecord,
    id(TABLE_SPEC_BY_NAME["bronze_source_cell"]): BronzeSourceCellRecord,
    id(TABLE_SPEC_BY_NAME["silver_fund_item_attribute"]): FundItemAttribute,
    id(TABLE_SPEC_BY_NAME["silver_quality_issue"]): DataQualityIssue,
    id(TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"]): ExactCrossSourceLinkRecord,
    id(
        TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"]
    ): ExactCrossSourceLinkEvidenceRecord,
}

_EXPLICIT_MODEL_BY_TABLE_NAME: dict[str, type[BaseModel]] = {
    TABLE_SPEC_BY_NAME["bronze_source_column"].table_name: BronzeSourceColumnRecord,
    TABLE_SPEC_BY_NAME["bronze_source_cell"].table_name: BronzeSourceCellRecord,
    TABLE_SPEC_BY_NAME["silver_fund_item_attribute"].table_name: FundItemAttribute,
    TABLE_SPEC_BY_NAME["silver_quality_issue"].table_name: DataQualityIssue,
    TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"].table_name: ExactCrossSourceLinkRecord,
    TABLE_SPEC_BY_NAME[
        "gold_exact_cross_source_link_evidence"
    ].table_name: ExactCrossSourceLinkEvidenceRecord,
}

_WIDE_MODEL_BY_SPEC_ID: dict[int, type[BaseModel]] = {
    id(TABLE_SPEC_BY_NAME["silver_bond_instrument"]): BondInstrument,
    id(TABLE_SPEC_BY_NAME["silver_domestic_listed_product"]): ListedProduct,
    id(TABLE_SPEC_BY_NAME["silver_overseas_listed_product"]): OverseasListedProduct,
    id(TABLE_SPEC_BY_NAME["silver_fund_item"]): FundItem,
}


def canonical_record_json(model: BaseModel) -> str:
    """Return the exact canonical JSON-mode representation of a strict model."""
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _physical_scalar(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def validate_physical_row(spec: TableSpec, row: Mapping[str, object]) -> None:
    """Validate one exact ordered row against the registered physical contract."""
    require_registered_table_spec(spec)
    if tuple(row) != tuple(column.name for column in spec.columns):
        raise ValueError("physical row columns/order do not match the registered spec")
    for column in spec.columns:
        value = row[column.name]
        if value is None:
            if not column.nullable:
                raise ValueError("physical non-nullable column contains null")
            continue
        if column.logical_type == "string":
            valid = type(value) is str
        elif column.logical_type == "int64":
            valid = type(value) is int
        elif column.logical_type == "date":
            valid = type(value) is date
        elif column.logical_type == "bool":
            valid = type(value) is bool
        elif column.logical_type == "timestamp":
            if type(value) is not datetime or value.tzinfo is not None:
                raise ValueError("source-local timestamp must be an exact naive datetime")
            valid = True
        elif column.logical_type == "timestamp_utc":
            offset = value.utcoffset() if type(value) is datetime else None
            if (
                type(value) is not datetime
                or value.tzinfo is None
                or offset is None
                or offset.total_seconds() != 0
            ):
                raise ValueError("UTC timestamp must be an exact zero-offset datetime")
            valid = True
        elif column.logical_type == "decimal":
            if type(value) is not Decimal or not value.is_finite():
                raise ValueError("Decimal(38,18) requires an exact finite Decimal")
            exponent = value.as_tuple().exponent
            if type(exponent) is not int:
                raise ValueError("Decimal(38,18) requires a finite exponent")
            fractional_digits = max(-exponent, 0)
            integer_digits = max(value.adjusted() + 1, 0) if value else 0
            if integer_digits > 20 or fractional_digits > 18:
                raise ValueError("Decimal(38,18) precision or scale exceeded")
            valid = True
        else:  # pragma: no cover - closed TableSpec registry
            raise ValueError("physical column uses an unknown logical type")
        if not valid:
            raise ValueError("physical column has the wrong exact Python type")


def _serialize_explicit(spec: TableSpec, value: BaseModel) -> Mapping[str, object]:
    if type(value) is FundItemAttribute:
        item = value.fund_item_id
        attribute = value.attribute_code
        row: dict[str, object] = {
            "grain": value.grain,
            "fund_item_id": item.normalized_value,
            "fund_item_id__quality_status": item.quality_status.value,
            "attribute_code": attribute.normalized_value,
            "attribute_code__quality_status": attribute.quality_status.value,
            "attribute_code_raw": attribute.raw_value,
            "source_row_number": attribute.source.source_row_number,
            "record_json": canonical_record_json(value),
        }
    elif type(value) is DataQualityIssue:
        if value.first_detected_at is None:
            raise ValueError("quality issue must already be persisted")
        source = value.source
        row = {
            "issue_id": value.issue_id,
            "rule_id": value.rule_id,
            "rule_version": value.rule_version,
            "severity": value.severity.value,
            "quality_status": value.quality_status.value,
            "source_table": source.source_table,
            "source_file": source.source_file.as_posix(),
            "source_sheet": source.source_sheet,
            "source_row_number": source.source_row_number,
            "source_column_name": source.source_column_name,
            "source_column_number": source.source_column_number,
            "source_column_letter": source.source_column_letter,
            "source_checksum": source.source_checksum,
            "source_snapshot_date": source.source_snapshot_date,
            "source_applicable_date": source.source_applicable_date,
            "reason": value.reason,
            "quarantined": value.quarantined,
            "raw_payload_sha256": value.raw_payload_sha256,
            "first_detected_at": value.first_detected_at,
            "record_json": canonical_record_json(value),
        }
    else:
        row = {
            name: raw.as_posix() if type(raw) is PurePosixPath else _physical_scalar(raw)
            for name, raw in value.model_dump(mode="python").items()
        }
    if tuple(row) != spec.logical_projection:
        raise ValueError("explicit projection does not match registered columns")
    validate_physical_row(spec, row)
    return row


def _revalidate_wide(model_type: type[BaseModel], value: BaseModel) -> BaseModel:
    dumped = value.model_dump(mode="python")
    pending: list[object] = [dumped]
    while pending:
        item = pending.pop()
        if type(item) is Decimal:
            if not item.is_finite():
                raise ValueError("Decimal(38,18) requires an exact finite Decimal")
            exponent = item.as_tuple().exponent
            if type(exponent) is not int:
                raise ValueError("Decimal(38,18) requires a finite exponent")
            if (max(item.adjusted() + 1, 0) if item else 0) > 20 or max(-exponent, 0) > 18:
                raise ValueError("Decimal(38,18) precision or scale exceeded")
        elif isinstance(item, Mapping):
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)
    try:
        if model_type is FundItem:
            return FundItem.model_validate_json(canonical_record_json(value))
        return model_type.model_validate(dumped, strict=True)
    except ValidationError as exc:
        raise ValueError("physical model values do not match the frozen contract") from exc


def serialize_table_row(spec: TableSpec, value: object) -> Mapping[str, object]:
    """Serialize one exact registered row without coercing physical scalars."""
    explicit_model = _EXPLICIT_MODEL_BY_TABLE_NAME.get(spec.table_name)
    if explicit_model is not None:
        require_registered_table_spec(spec)
        if type(value) is not explicit_model:
            raise ValueError("registered spec and model pair do not match")
        validated = explicit_model.model_validate(value.model_dump(mode="python"), strict=True)
        return _serialize_explicit(spec, validated)
    if isinstance(value, BondInstrument):
        model_type: type[BaseModel] = BondInstrument
    elif isinstance(value, ListedProduct):
        model_type = ListedProduct
    elif isinstance(value, OverseasListedProduct):
        model_type = OverseasListedProduct
    elif isinstance(value, FundItem):
        model_type = FundItem
    else:
        raise NotImplementedError
    if type(value) is not model_type:
        raise ValueError("registered spec and model pair do not match")
    require_registered_spec(spec, model_type)
    validated_value = _revalidate_wide(model_type, value)
    row: dict[str, object] = {"grain": getattr(validated_value, "grain")}  # noqa: B009
    for name in model_type.model_fields:
        if name == "grain" or (model_type is FundItem and name == "contributing_rows"):
            continue
        wrapped = getattr(validated_value, name)
        if isinstance(wrapped, NormalizedValue):
            row[name] = _physical_scalar(wrapped.normalized_value)
            row[f"{name}__quality_status"] = wrapped.quality_status.value
        elif isinstance(wrapped, DerivedValue):
            row[name] = _physical_scalar(wrapped.value)
            row[f"{name}__quality_status"] = wrapped.quality_status.value
            row[f"{name}__as_of_date"] = wrapped.as_of_date
        elif isinstance(wrapped, FundItemValue):
            row[name] = _physical_scalar(wrapped.representative.normalized_value)
            row[f"{name}__quality_status"] = wrapped.representative.quality_status.value
        else:
            raise TypeError("registered wide model contains an unsupported wrapper")
    row["record_json"] = canonical_record_json(validated_value)
    validate_physical_row(spec, row)
    return row


def serialize_bronze_source_row(
    spec: TableSpec,
    value: SourceRow,
    *,
    persistence_timestamp: datetime,
) -> Mapping[str, object]:
    """Serialize one source row with the sole CP3 persistence-time injection."""
    require_registered_spec(spec, SourceRow)
    if type(value) is not SourceRow:
        raise TypeError("bronze source row must be an exact SourceRow")
    table_order = {
        "PRBD01N001": 0,
        "PREF01N001": 1,
        "PREF02N001": 2,
        "PRFD01N001": 3,
    }
    try:
        source_table_order = table_order[value.source_table]
    except KeyError as exc:
        raise ValueError("source table is not in the frozen order") from exc
    raw_payload_json = json.dumps(
        value.raw_payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    row = {
        "source_table_order": source_table_order,
        "source_table": value.source_table,
        "source_file": value.source_file.as_posix(),
        "source_sheet": value.source_sheet,
        "source_row_number": value.source_row_number,
        "source_checksum": value.source_checksum,
        "source_snapshot_date": value.source_snapshot_date,
        "raw_payload_json": raw_payload_json,
        "raw_payload_sha256": hashlib.sha256(
            "\0".join(value.raw_payload).encode("utf-8")
        ).hexdigest(),
        "loaded_at": persistence_timestamp,
    }
    validate_physical_row(spec, row)
    return row


def logical_table_row(spec: TableSpec, row: Mapping[str, object]) -> Mapping[str, object]:
    """Return one timestamp-neutral logical row from a typed physical projection."""
    require_registered_table_spec(spec)
    if tuple(row) != tuple(column.name for column in spec.columns):
        raise ValueError("physical row does not match registered columns")
    logical = {name: row[name] for name in spec.logical_projection}
    wide_model = _WIDE_MODEL_BY_SPEC_ID.get(id(spec))
    if wide_model is not None:
        record_json = row["record_json"]
        if type(record_json) is not str:
            raise ValueError("record_json must be an exact string")
        try:
            parsed = wide_model.model_validate_json(record_json)
        except ValidationError as exc:
            raise ValueError("record_json does not match the registered model") from exc
        if canonical_record_json(parsed) != record_json:
            raise ValueError("record_json is not canonical")
        if dict(serialize_table_row(spec, parsed)) != dict(row):
            raise ValueError("record_json and typed projection do not agree")
    if spec is TABLE_SPEC_BY_NAME["bronze_source_row"]:
        logical["loaded_at"] = None
    elif spec is TABLE_SPEC_BY_NAME["silver_fund_item_attribute"]:
        record_json = row["record_json"]
        if type(record_json) is not str:
            raise ValueError("fund attribute record_json must be an exact string")
        try:
            parsed_attribute = FundItemAttribute.model_validate_json(record_json)
        except ValidationError as exc:
            raise ValueError("fund attribute record_json is invalid") from exc
        if canonical_record_json(parsed_attribute) != record_json:
            raise ValueError("fund attribute record_json must be canonical")
        if dict(_serialize_explicit(spec, parsed_attribute)) != dict(row):
            raise ValueError("fund attribute typed/JSON projection agreement is required")
    elif spec is TABLE_SPEC_BY_NAME["silver_quality_issue"]:
        record_json = row["record_json"]
        if type(record_json) is not str:
            raise ValueError("quality record_json must be an exact string")
        parsed = DataQualityIssue.model_validate_json(record_json)
        if canonical_record_json(parsed) != record_json:
            raise ValueError("quality record_json must be canonical")
        if parsed.first_detected_at is None:
            raise ValueError("quality issue must already be persisted")
        if parsed.first_detected_at != row["first_detected_at"]:
            raise ValueError("quality typed/JSON timestamp agreement is required")
        if dict(_serialize_explicit(spec, parsed)) != dict(row):
            raise ValueError("quality typed/JSON projection agreement is required")
        neutral = DataQualityIssue.model_validate(
            {**parsed.model_dump(mode="python"), "first_detected_at": None},
            strict=True,
        )
        logical["first_detected_at"] = None
        logical["record_json"] = canonical_record_json(neutral)
    return logical
