"""Frozen physical and logical table declarations for artifacts."""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Literal, cast, get_args

from pydantic import BaseModel, ConfigDict

from finproof.domain.bonds import BondInstrument
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.public_funds import FundItem, FundItemAttribute, FundItemValue
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
    """Private closed-registry skeleton; validation is added behavior-by-behavior."""

    def __init__(self, specs: Iterable[TableSpec]) -> None:
        self._specs = tuple(specs)
        for spec in self._specs:
            names = tuple(column.name for column in spec.columns)
            if len(names) != len(set(names)):
                raise ValueError("column names must be unique")


_TABLE_NAMES = (
    "bronze_source_column",
    "bronze_source_row",
    "bronze_source_cell",
    "silver_bond_instrument",
    "silver_domestic_listed_product",
    "silver_overseas_listed_product",
    "silver_fund_item",
    "silver_fund_item_attribute",
    "silver_quality_issue",
    "gold_exact_cross_source_link",
    "gold_exact_cross_source_link_evidence",
)


def _placeholder_spec(name: str) -> TableSpec:
    column = _column("grain")
    return TableSpec(
        table_name=name,
        layer=cast(Literal["bronze", "silver", "gold"], name.split("_", 1)[0]),
        grain="placeholder",
        columns=(column,),
        unique_key=("grain",),
        sort_key=("grain",),
        logical_projection=("grain",),
        parquet_path=f"parquet/{name}.parquet",
    )


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


_BOND_SPEC = _explicit_spec(
    "silver_bond_instrument",
    "instrument",
    _frozen_wide_columns(
        (
            ("product_id", "string", False),
            ("name", "string", False),
            ("short_name", "string", False),
            ("currency", "string", False),
            ("bond_kind_raw", "string", False),
            ("issue_date", "date", False),
            ("maturity_date", "date", False),
            ("source_update_date", "date", False),
            ("coupon_rate", "decimal", False),
            ("buy_yield", "decimal", False),
            ("buyable_quantity", "decimal", False),
            ("source_remaining_days", "int64", False),
            ("credit_rating", "string", False),
            ("credit_rating_agencies_raw", "string", False),
            ("credit_rating_date", "date", False),
            ("duration", "decimal", False),
            ("evaluation_price", "decimal", False),
            ("remaining_days_at_as_of", "int64", True),
            ("is_matured_at_as_of", "bool", True),
            ("has_positive_buyable_quantity", "bool", True),
            ("is_buyable_validated_at_as_of", "bool", True),
        )
    ),
    unique_key=("product_id",),
    sort_key=("product_id",),
)

_DOMESTIC_TYPES = {
    "listing_date": "date",
    "listing_end_date": "date",
    "sale_flag": "bool",
    "suspension_flag": "bool",
    "aum_primary": "decimal",
    "aum_secondary": "decimal",
    "total_fee": "decimal",
    "tracking_error": "decimal",
    "difference_rate": "decimal",
    "return_1d": "decimal",
    "return_1m": "decimal",
    "return_3m": "decimal",
    "return_6m": "decimal",
    "return_1y": "decimal",
    "return_ytd": "decimal",
    "custom_update_date": "date",
    "daily_update_at": "timestamp",
    "weekly_update_date": "date",
    "is_eligible_at_as_of": "bool",
}
_DOMESTIC_NAMES = (
    "product_id",
    "market_identifier",
    "product_type",
    "name",
    "short_name",
    "currency",
    "listing_date",
    "listing_end_date",
    "sale_flag",
    "suspension_flag",
    "aum_primary",
    "aum_secondary",
    "total_fee",
    "tracking_error",
    "difference_rate",
    "return_1d",
    "return_1m",
    "return_3m",
    "return_6m",
    "return_1y",
    "return_ytd",
    "risk_code",
    "risk_name",
    "base_index",
    "manager",
    "asset_type",
    "region",
    "custom_update_date",
    "daily_update_at",
    "weekly_update_date",
    "is_eligible_at_as_of",
)
_DOMESTIC_SPEC = _explicit_spec(
    "silver_domestic_listed_product",
    "listed_product",
    _frozen_wide_columns(
        tuple(
            (
                name,
                _DOMESTIC_TYPES.get(name, "string"),
                name == "is_eligible_at_as_of",
            )
            for name in _DOMESTIC_NAMES
        )
    ),
    unique_key=("product_id",),
    sort_key=("product_id",),
)

_OVERSEAS_NAMES = (
    "base_index",
    "total_fee",
    "etn_flag_raw",
    "manager",
    "replication_method",
    "index_tracking_flag_raw",
    "inverse_short_flag_raw",
    "leverage_factor",
    "strategy",
    "custom_update_date",
    "daily_base_date_match_raw",
    "daily_bid_price",
    "close_price",
    "close_price_base_date",
    "daily_close_source",
    "difference_rate_raw_metric",
    "return_1d",
    "daily_high_price",
    "aum",
    "last_nav",
    "daily_low_price",
    "nav_base_at",
    "daily_open_price",
    "daily_update_date",
    "daily_value",
    "daily_volume",
    "ticker",
    "source_currency_raw",
    "exchange_market_code",
    "product_type",
    "isin",
    "product_id",
    "market_identifier",
    "lipper_id",
    "listing_date",
    "listing_price",
    "listed_share_count",
    "market_code",
    "name",
    "sale_flag_raw",
    "trading_currency",
    "suspension_flag_raw",
    "us_cik",
    "realtime_market_price",
    "realtime_market_volume",
    "core_flag_raw",
    "asset_type",
    "region",
    "weekly_update_date",
)
_OVERSEAS_DECIMALS = {
    "total_fee",
    "leverage_factor",
    "daily_bid_price",
    "close_price",
    "difference_rate_raw_metric",
    "return_1d",
    "daily_high_price",
    "aum",
    "last_nav",
    "daily_low_price",
    "daily_open_price",
    "daily_value",
    "daily_volume",
    "listing_price",
    "listed_share_count",
    "realtime_market_price",
    "realtime_market_volume",
}
_OVERSEAS_DATES = {
    "custom_update_date",
    "close_price_base_date",
    "daily_update_date",
    "listing_date",
    "weekly_update_date",
}
_OVERSEAS_SPEC = _explicit_spec(
    "silver_overseas_listed_product",
    "listed_product",
    _frozen_wide_columns(
        tuple(
            (
                name,
                "decimal"
                if name in _OVERSEAS_DECIMALS
                else "date"
                if name in _OVERSEAS_DATES
                else "timestamp"
                if name == "nav_base_at"
                else "string",
                False,
            )
            for name in _OVERSEAS_NAMES
        )
    ),
    unique_key=("product_id",),
    sort_key=("product_id",),
)

_FUND_NAMES = (
    "benchmark_english_name",
    "benchmark_name",
    "currency",
    "exchange_traded_flag_raw",
    "establishment_country_code",
    "region_description",
    "return_18m",
    "return_1m",
    "return_3m",
    "return_6m",
    "net_assets",
    "establishment_type_code",
    "return_1w",
    "return_1y",
    "return_2y",
    "return_3y",
    "return_5y",
    "foreign_base_price_flag_raw",
    "fss_item_id",
    "hedge_fund_flag_raw",
    "interest_dividend_description",
    "short_name",
    "english_short_name",
    "english_name",
    "name",
    "fund_item_id",
    "kofia_classification_code",
    "ksd_id",
    "manager_item_id",
    "offshore_fund_flag_raw",
    "fund_type_raw",
    "manager_external_code",
    "overseas_fund_description",
    "investor_type_description",
    "professional_sale_control_code",
    "private_fund_description",
    "offering_type_description",
    "family_candidate_key",
    "sale_status_raw",
    "standard_item_id",
    "mirae_sale_flag_raw",
    "trustee_external_code",
    "risk_code",
    "risk_name",
)
_FUND_DECIMALS = {
    "return_18m",
    "return_1m",
    "return_3m",
    "return_6m",
    "net_assets",
    "return_1w",
    "return_1y",
    "return_2y",
    "return_3y",
    "return_5y",
}
_FUND_SPEC = _explicit_spec(
    "silver_fund_item",
    "fund_item",
    _frozen_wide_columns(
        tuple(
            (name, "decimal" if name in _FUND_DECIMALS else "string", False) for name in _FUND_NAMES
        )
    ),
    unique_key=("fund_item_id",),
    sort_key=("fund_item_id",),
)

_FUND_ATTRIBUTE_SPEC = _explicit_spec(
    "silver_fund_item_attribute",
    "fund_attribute",
    (
        _column("grain"),
        _column("fund_item_id"),
        _column("fund_item_id__quality_status"),
        _column("attribute_code"),
        _column("attribute_code__quality_status"),
        _column("attribute_code_raw"),
        _column("source_row_number", "int64"),
        _column("record_json"),
    ),
    unique_key=("fund_item_id", "attribute_code", "attribute_code_raw", "source_row_number"),
    sort_key=("fund_item_id", "attribute_code", "attribute_code_raw", "source_row_number"),
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

TABLE_SPECS = (
    *_BRONZE_SPECS,
    _BOND_SPEC,
    _DOMESTIC_SPEC,
    _OVERSEAS_SPEC,
    _FUND_SPEC,
    _FUND_ATTRIBUTE_SPEC,
    _QUALITY_SPEC,
    _GOLD_LINK_SPEC,
    _GOLD_EVIDENCE_SPEC,
)
TABLE_SPEC_BY_NAME = MappingProxyType({spec.table_name: spec for spec in TABLE_SPECS})
_WIDE_MODEL_TYPES = (BondInstrument, ListedProduct, OverseasListedProduct, FundItem)
_EXACT_MODEL_BY_TABLE = MappingProxyType(
    {
        "bronze_source_row": SourceRow,
        "silver_bond_instrument": BondInstrument,
        "silver_domestic_listed_product": ListedProduct,
        "silver_overseas_listed_product": OverseasListedProduct,
        "silver_fund_item": FundItem,
        "silver_fund_item_attribute": FundItemAttribute,
        "silver_quality_issue": DataQualityIssue,
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
        if model_type is FundItem and name == "contributing_rows":
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
        elif issubclass(annotation, FundItemValue):
            representative_type = annotation.model_fields["representative"].annotation
            if not isinstance(representative_type, type):
                raise TypeError("fund representative wrapper is invalid")
            value_type = _wrapped_value_type(representative_type, "normalized_value")
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
