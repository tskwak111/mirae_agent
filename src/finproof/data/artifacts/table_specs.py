"""Frozen physical and logical table declarations for artifacts."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Literal, cast, get_args

from pydantic import BaseModel, ConfigDict

from finproof.data.holdings import HoldingCoverageRecord, HoldingRecord
from finproof.domain.bonds import BondInstrument, BondSaleLot
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.public_funds import PublicFundItem
from finproof.domain.quality import DataQualityIssue
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue


class ColumnSpec(BaseModel):
    """One frozen physical column declaration."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str
    logical_type: str
    arrow_type: str
    duckdb_type: str
    nullable: bool


class TableSpec(BaseModel):
    """One frozen table declaration."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    table_name: str
    layer: Literal["bronze", "silver", "gold"]
    grain: str
    columns: tuple[ColumnSpec, ...]
    unique_key: tuple[str, ...]
    sort_key: tuple[str, ...]
    logical_projection: tuple[str, ...]
    parquet_path: str


class ClosedTableSpecRegistry:
    """The sole closed registry for the exact reviewed table-spec tuple."""

    def __init__(self, specs: tuple[TableSpec, ...]) -> None:
        if type(specs) is not tuple:
            raise TypeError("registry requires a tuple")
        if (
            specs is not TABLE_SPECS
            or len(specs) != len(TABLE_SPECS)
            or any(specs[index] is not TABLE_SPECS[index] for index in range(len(specs)))
        ):
            raise ValueError("registry requires the exact frozen table specs tuple")
        for spec in specs:
            names = tuple(column.name for column in spec.columns)
            if len(names) != len(set(names)):
                raise ValueError("column names must be unique")
        self._specs = specs

    def ordered_specs(self) -> tuple[TableSpec, ...]:
        """Return the exact reviewed tuple after revalidating every member."""
        for spec in self._specs:
            require_registered_table_spec(spec)
        return TABLE_SPECS


_TYPE_DETAILS = MappingProxyType(
    {
        "string": ("string", "VARCHAR"),
        "int64": ("int64", "BIGINT"),
        "date": ("date32[day]", "DATE"),
        "timestamp_utc": ("timestamp[us, tz=UTC]", "TIMESTAMPTZ"),
        "timestamp": ("timestamp[us]", "TIMESTAMP"),
        "bool": ("bool", "BOOLEAN"),
        "decimal": ("decimal128(38, 18)", "DECIMAL(38,18)"),
    }
)


def _column(name: str, logical_type: str = "string", *, nullable: bool = False) -> ColumnSpec:
    arrow_type, duckdb_type = _TYPE_DETAILS[logical_type]
    return ColumnSpec(
        name=name,
        logical_type=logical_type,
        arrow_type=arrow_type,
        duckdb_type=duckdb_type,
        nullable=nullable,
    )


def _explicit_spec(
    name: str,
    grain: str,
    columns: tuple[ColumnSpec, ...],
    *,
    unique_key: tuple[str, ...],
    sort_key: tuple[str, ...],
) -> TableSpec:
    return TableSpec(
        table_name=name,
        layer=cast(Literal["bronze", "silver", "gold"], name.split("_", 1)[0]),
        grain=grain,
        columns=columns,
        unique_key=unique_key,
        sort_key=sort_key,
        logical_projection=tuple(column.name for column in columns),
        parquet_path=f"parquet/{name}.parquet",
    )


_BRONZE_SPECS = (
    _explicit_spec(
        "bronze_source_column",
        "source_column",
        (
            _column("catalog_version"),
            _column("source_snapshot_date", "date"),
            _column("source_table_order", "int64"),
            _column("source_table"),
            _column("source_column_number", "int64"),
            _column("source_column_letter"),
            _column("source_column_name"),
            _column("source_declared_type"),
            _column("source_example"),
            _column("source_key_marker"),
            _column("source_name_ko"),
            _column("schema_file"),
            _column("schema_excel_row", "int64"),
        ),
        unique_key=("source_table", "source_column_number"),
        sort_key=("source_table_order", "source_column_number"),
    ),
    _explicit_spec(
        "bronze_source_row",
        "source_row",
        (
            _column("source_table_order", "int64"),
            _column("source_table"),
            _column("source_file"),
            _column("source_sheet"),
            _column("source_row_number", "int64"),
            _column("source_checksum"),
            _column("source_snapshot_date", "date"),
            _column("raw_payload_json"),
            _column("raw_payload_sha256"),
            _column("loaded_at", "timestamp_utc"),
        ),
        unique_key=("source_table", "source_file", "source_sheet", "source_row_number"),
        sort_key=("source_table_order", "source_file", "source_sheet", "source_row_number"),
    ),
    _explicit_spec(
        "bronze_source_cell",
        "source_cell",
        (
            _column("source_table_order", "int64"),
            _column("source_table"),
            _column("source_file"),
            _column("source_sheet"),
            _column("source_row_number", "int64"),
            _column("source_column_name"),
            _column("source_column_number", "int64"),
            _column("source_column_letter"),
            _column("source_checksum"),
            _column("source_snapshot_date", "date"),
            _column("source_applicable_date", "date", nullable=True),
            _column("raw_value"),
        ),
        unique_key=(
            "source_table",
            "source_file",
            "source_sheet",
            "source_row_number",
            "source_column_number",
        ),
        sort_key=(
            "source_table_order",
            "source_file",
            "source_sheet",
            "source_row_number",
            "source_column_number",
        ),
    ),
)


def _frozen_wide_columns(
    fields: tuple[tuple[str, str, bool], ...],
) -> tuple[ColumnSpec, ...]:
    columns = [_column("grain")]
    for name, logical_type, derived in fields:
        columns.extend(
            (
                _column(name, logical_type, nullable=True),
                _column(f"{name}__quality_status"),
            )
        )
        if derived:
            columns.append(_column(f"{name}__as_of_date", "date"))
    columns.append(_column("record_json"))
    return tuple(columns)


def _model_wide_columns(
    model_type: type[BaseModel], *, json_only: frozenset[str] = frozenset()
) -> tuple[ColumnSpec, ...]:
    fields: list[tuple[str, str, bool]] = []
    for name, field in model_type.model_fields.items():
        if name == "grain" or name in json_only:
            continue
        wrapper = field.annotation
        if not isinstance(wrapper, type) or not issubclass(
            wrapper, (NormalizedValue, DerivedValue)
        ):
            raise TypeError("wide artifact field must be a normalized or derived wrapper")
        wrapped_field = "value" if issubclass(wrapper, DerivedValue) else "normalized_value"
        args = tuple(
            arg
            for arg in get_args(wrapper.model_fields[wrapped_field].annotation)
            if arg is not type(None)
        )
        if len(args) != 1 or not isinstance(args[0], type):
            raise TypeError("wide artifact wrapper must contain one scalar type")
        value_type = args[0]
        logical_type = (
            "bool"
            if value_type is bool
            else "int64"
            if value_type is int
            else "decimal"
            if value_type is Decimal
            else "timestamp"
            if value_type is datetime
            else "date"
            if value_type is date
            else "string"
        )
        fields.append((name, logical_type, issubclass(wrapper, DerivedValue)))
    return _frozen_wide_columns(tuple(fields))


_BOND_LOT_WIDE_COLUMNS = _model_wide_columns(
    BondSaleLot, json_only=frozenset({"source_row", "source_key"})
)
_BOND_LOT_SPEC = _explicit_spec(
    "silver_bond_sale_lot",
    "bond_sale_lot",
    (
        *_BOND_LOT_WIDE_COLUMNS[:-1],
        _column("source_row_number", "int64"),
        _BOND_LOT_WIDE_COLUMNS[-1],
    ),
    unique_key=(
        "product_id",
        "exchange_market",
        "info_base_date",
        "info_sequence",
        "source_row_number",
    ),
    sort_key=(
        "product_id",
        "exchange_market",
        "info_base_date",
        "info_sequence",
        "source_row_number",
    ),
)


_BOND_SPEC = _explicit_spec(
    "silver_bond_instrument",
    "instrument",
    _model_wide_columns(
        BondInstrument,
        json_only=frozenset({"selected_lot_key", "field_sources", "buy_yield_range"}),
    ),
    unique_key=("product_id",),
    sort_key=("product_id",),
)

_DOMESTIC_SPEC = _explicit_spec(
    "silver_domestic_listed_product",
    "listed_product",
    _model_wide_columns(ListedProduct),
    unique_key=("product_id",),
    sort_key=("product_id",),
)

_OVERSEAS_SPEC = _explicit_spec(
    "silver_overseas_listed_product",
    "listed_product",
    _model_wide_columns(OverseasListedProduct),
    unique_key=("product_id",),
    sort_key=("product_id",),
)

_FUND_SPEC = _explicit_spec(
    "silver_fund_item",
    "fund_item",
    _model_wide_columns(
        PublicFundItem,
        json_only=frozenset({"source_row", "attribute_codes"}),
    ),
    unique_key=("fund_item_id",),
    sort_key=("fund_item_id",),
)

_QUALITY_SORT_KEY = (
    "source_table",
    "source_file",
    "source_sheet",
    "source_row_number",
    "source_column_number",
    "rule_id",
    "issue_id",
)
_QUALITY_SPEC = _explicit_spec(
    "silver_quality_issue",
    "quality_issue",
    (
        _column("issue_id"),
        _column("rule_id"),
        _column("rule_version"),
        _column("severity"),
        _column("quality_status"),
        _column("source_table"),
        _column("source_file"),
        _column("source_sheet"),
        _column("source_row_number", "int64"),
        _column("source_column_name"),
        _column("source_column_number", "int64"),
        _column("source_column_letter"),
        _column("source_checksum"),
        _column("source_snapshot_date", "date"),
        _column("source_applicable_date", "date", nullable=True),
        _column("reason"),
        _column("quarantined", "bool"),
        _column("raw_payload_sha256"),
        _column("first_detected_at", "timestamp_utc"),
        _column("record_json"),
    ),
    unique_key=("issue_id",),
    sort_key=_QUALITY_SORT_KEY,
)

_GOLD_LINK_SPEC = _explicit_spec(
    "gold_exact_cross_source_link",
    "exact_cross_source_link",
    (
        _column("link_id"),
        _column("left_table"),
        _column("left_product_id"),
        _column("left_identifier_field"),
        _column("right_table"),
        _column("right_product_id"),
        _column("right_identifier_field"),
        _column("matched_raw_identifier"),
        _column("link_type"),
        _column("confidence", "decimal"),
        _column("rule_id"),
        _column("rule_version"),
    ),
    unique_key=("left_product_id", "right_product_id", "rule_version"),
    sort_key=("left_product_id", "right_product_id", "rule_version"),
)

_GOLD_EVIDENCE_SPEC = _explicit_spec(
    "gold_exact_cross_source_link_evidence",
    "exact_cross_source_link_evidence",
    (
        _column("link_id"),
        _column("evidence_role"),
        _column("evidence_role_order", "int64"),
        _column("evidence_ordinal", "int64"),
        _column("raw_identifier"),
        _column("source_table"),
        _column("source_file"),
        _column("source_sheet"),
        _column("source_row_number", "int64"),
        _column("source_column_name"),
        _column("source_column_number", "int64"),
        _column("source_column_letter"),
        _column("source_checksum"),
        _column("source_snapshot_date", "date"),
        _column("source_applicable_date", "date", nullable=True),
    ),
    unique_key=("link_id", "evidence_role_order", "evidence_ordinal"),
    sort_key=("link_id", "evidence_role_order", "evidence_ordinal"),
)

_HOLDING_SPEC = _explicit_spec(
    "silver_product_holding",
    "product_holding",
    (
        _column("generation_id"),
        _column("owner_product_type"),
        _column("owner_product_id"),
        _column("owner_source_identifier"),
        _column("owner_identifier_type"),
        _column("owner_link_method"),
        _column("constituent_identifier"),
        _column("constituent_identifier_type"),
        _column("raw_name"),
        _column("display_name"),
        _column("quantity", "decimal", nullable=True),
        _column("quantity_unit", nullable=True),
        _column("market_value", "decimal", nullable=True),
        _column("market_value_currency", nullable=True),
        _column("weight", "decimal", nullable=True),
        _column("weight_unit", nullable=True),
        _column("source_owner"),
        _column("source_kind"),
        _column("direct_source_url"),
        _column("raw_file_sha256"),
        _column("source_as_of_date", "date"),
        _column("publication_date", "date"),
        _column("source_row_ordinal", "int64"),
        _column("quality_state"),
        _column("record_json"),
    ),
    unique_key=("owner_product_type", "owner_product_id", "source_row_ordinal"),
    sort_key=("owner_product_type", "owner_product_id", "source_row_ordinal"),
)

_HOLDING_COVERAGE_SPEC = _explicit_spec(
    "silver_product_holding_coverage",
    "product_holding_coverage",
    (
        _column("owner_product_type"),
        _column("owner_product_id"),
        _column("coverage_state"),
        _column("source_generation_id", nullable=True),
        _column("owner_source_identifier", nullable=True),
        _column("owner_identifier_type", nullable=True),
        _column("owner_link_method", nullable=True),
        _column("source_owner", nullable=True),
        _column("source_kind", nullable=True),
        _column("direct_source_url", nullable=True),
        _column("raw_file_sha256", nullable=True),
        _column("source_as_of_date", "date", nullable=True),
        _column("publication_date", "date", nullable=True),
        _column("observed_holding_count", "int64"),
        _column("limitation_code"),
        _column("record_json"),
    ),
    unique_key=("owner_product_type", "owner_product_id"),
    sort_key=("owner_product_type", "owner_product_id"),
)

TABLE_SPECS = (
    *_BRONZE_SPECS,
    _BOND_LOT_SPEC,
    _BOND_SPEC,
    _DOMESTIC_SPEC,
    _OVERSEAS_SPEC,
    _FUND_SPEC,
    _QUALITY_SPEC,
    _HOLDING_SPEC,
    _HOLDING_COVERAGE_SPEC,
    _GOLD_LINK_SPEC,
    _GOLD_EVIDENCE_SPEC,
)
TABLE_SPEC_REGISTRY = ClosedTableSpecRegistry(TABLE_SPECS)
TABLE_SPEC_BY_NAME = MappingProxyType({spec.table_name: spec for spec in TABLE_SPECS})
_WIDE_MODEL_TYPES = (
    BondSaleLot,
    BondInstrument,
    ListedProduct,
    OverseasListedProduct,
    PublicFundItem,
)
_EXACT_MODEL_BY_TABLE = MappingProxyType(
    {
        "bronze_source_row": SourceRow,
        "silver_bond_sale_lot": BondSaleLot,
        "silver_bond_instrument": BondInstrument,
        "silver_domestic_listed_product": ListedProduct,
        "silver_overseas_listed_product": OverseasListedProduct,
        "silver_fund_item": PublicFundItem,
        "silver_quality_issue": DataQualityIssue,
        "silver_product_holding": HoldingRecord,
        "silver_product_holding_coverage": HoldingCoverageRecord,
    }
)
_EXACT_MODEL_BY_SPEC_ID = MappingProxyType(
    {id(TABLE_SPEC_BY_NAME[name]): model_type for name, model_type in _EXACT_MODEL_BY_TABLE.items()}
)


def _spec_fingerprint(spec: TableSpec) -> tuple[object, ...]:
    return (
        spec.table_name,
        spec.layer,
        spec.grain,
        spec.parquet_path,
        tuple(
            (
                column.name,
                column.logical_type,
                column.arrow_type,
                column.duckdb_type,
                column.nullable,
            )
            for column in spec.columns
        ),
        spec.unique_key,
        spec.sort_key,
        spec.logical_projection,
    )


_SPEC_FINGERPRINT_BY_ID = MappingProxyType(
    {id(spec): _spec_fingerprint(spec) for spec in TABLE_SPECS}
)


def _wrapped_value_type(wrapper: type[BaseModel], field_name: str) -> type[object]:
    annotation = wrapper.model_fields[field_name].annotation
    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if len(args) != 1 or not isinstance(args[0], type):
        raise TypeError("wide wrapper must declare one exact scalar type")
    return args[0]


def _logical_type(value_type: type[object]) -> str:
    if value_type is bool:
        return "bool"
    if value_type is int:
        return "int64"
    if value_type is Decimal:
        return "decimal"
    if value_type is datetime:
        return "timestamp"
    if value_type is date:
        return "date"
    if value_type is str or issubclass(value_type, Enum):
        return "string"
    raise TypeError("unsupported wide scalar type")


def derive_wide_columns(model_type: type[BaseModel]) -> tuple[ColumnSpec, ...]:
    """Derive a wide projection for drift comparison; identity closes separately."""
    if model_type not in _WIDE_MODEL_TYPES:
        raise TypeError("model_type must be an exact registered wide model")
    columns: list[ColumnSpec] = [_column("grain")]
    for name, field in model_type.model_fields.items():
        if name == "grain":
            continue
        if model_type is PublicFundItem and name in {"source_row", "attribute_codes"}:
            continue
        if model_type is BondSaleLot and name in {"source_row", "source_key"}:
            continue
        if model_type is BondInstrument and name in {
            "selected_lot_key",
            "field_sources",
            "buy_yield_range",
        }:
            continue
        annotation = field.annotation
        if not isinstance(annotation, type):
            raise TypeError("wide field must use one exact wrapper model")
        if issubclass(annotation, NormalizedValue):
            value_type = _wrapped_value_type(annotation, "normalized_value")
            columns.extend(
                (
                    _column(name, _logical_type(value_type), nullable=True),
                    _column(f"{name}__quality_status"),
                )
            )
        elif issubclass(annotation, DerivedValue):
            value_type = _wrapped_value_type(annotation, "value")
            columns.extend(
                (
                    _column(name, _logical_type(value_type), nullable=True),
                    _column(f"{name}__quality_status"),
                    _column(f"{name}__as_of_date", "date"),
                )
            )
        else:
            raise TypeError("wide field wrapper is not allowed")
    if model_type is BondSaleLot:
        columns.append(_column("source_row_number", "int64"))
    columns.append(_column("record_json"))
    return tuple(columns)


def assert_model_matches_frozen_spec(model_type: type[BaseModel], spec: TableSpec) -> None:
    """Reject a declared model projection that differs from the reviewed spec."""
    require_registered_spec(spec, model_type)
    if derive_wide_columns(model_type) != spec.columns:
        raise ValueError("wide model drift requires a reviewed table contract")


def require_registered_spec(spec: TableSpec, model_type: type[object]) -> TableSpec:
    """Require exact registered spec and model object identities."""
    require_registered_table_spec(spec)
    expected_model = _EXACT_MODEL_BY_SPEC_ID.get(id(spec))
    if expected_model is not model_type:
        raise ValueError("registered spec and model pair do not match")
    return spec


def require_registered_table_spec(spec: TableSpec) -> TableSpec:
    """Require an exact registry object and its captured deep fingerprint."""
    fingerprint = _SPEC_FINGERPRINT_BY_ID.get(id(spec))
    if fingerprint is None or all(registered is not spec for registered in TABLE_SPECS):
        raise ValueError("spec must be the exact registered object")
    if fingerprint != _spec_fingerprint(spec):
        raise ValueError("registered spec fingerprint changed")
    return spec


def table_spec(name: str) -> TableSpec:
    """Return one exact closed-registry member."""
    try:
        return TABLE_SPEC_BY_NAME[name]
    except (KeyError, TypeError) as exc:
        raise ValueError("unknown artifact table") from exc
