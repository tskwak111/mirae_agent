"""Frozen table-spec contracts for artifact persistence."""

from inspect import signature

import pytest


def _column_contract(
    name: str, logical_type: str = "string", *, nullable: bool = False
) -> tuple[str, str, str, str, bool]:
    physical = {
        "string": ("string", "VARCHAR"),
        "int64": ("int64", "BIGINT"),
        "date": ("date32[day]", "DATE"),
        "timestamp_utc": ("timestamp[us, tz=UTC]", "TIMESTAMPTZ"),
        "timestamp": ("timestamp[us]", "TIMESTAMP"),
        "bool": ("bool", "BOOLEAN"),
        "decimal": ("decimal128(38, 18)", "DECIMAL(38,18)"),
    }
    arrow_type, duckdb_type = physical[logical_type]
    return name, logical_type, arrow_type, duckdb_type, nullable


def _observed_columns(spec: object) -> tuple[tuple[str, str, str, str, bool], ...]:
    return tuple(
        (
            column.name,
            column.logical_type,
            column.arrow_type,
            column.duckdb_type,
            column.nullable,
        )
        for column in spec.columns  # type: ignore[attr-defined]
    )


def _wide_columns(
    fields: tuple[tuple[str, str, bool], ...],
) -> tuple[tuple[str, str, str, str, bool], ...]:
    result = [_column_contract("grain")]
    for name, logical_type, derived in fields:
        result.extend(
            (
                _column_contract(name, logical_type, nullable=True),
                _column_contract(f"{name}__quality_status"),
            )
        )
        if derived:
            result.append(_column_contract(f"{name}__as_of_date", "date"))
    result.append(_column_contract("record_json"))
    return tuple(result)


def test_table_spec_module_skeleton_rejects_closed_registry_fixture() -> None:
    from finproof.data.artifacts.table_specs import (
        ClosedTableSpecRegistry,
        ColumnSpec,
        TableSpec,
    )

    duplicate = ColumnSpec(
        name="duplicate",
        logical_type="text",
        arrow_type="utf8",
        duckdb_type="VARCHAR",
        nullable=False,
    )
    malformed = TableSpec(
        table_name="not_registered",
        layer="bronze",
        grain="test",
        columns=(duplicate, duplicate),
        unique_key=("duplicate",),
        sort_key=("duplicate",),
        logical_projection=("duplicate",),
        parquet_path="parquet/not_registered.parquet",
    )

    with pytest.raises(ValueError, match="column names"):
        ClosedTableSpecRegistry((malformed,))


def test_table_registry_has_exact_eleven_names_and_paths() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TABLE_SPECS

    expected_names = (
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

    assert tuple(spec.table_name for spec in TABLE_SPECS) == expected_names
    assert tuple(TABLE_SPEC_BY_NAME) == expected_names
    assert tuple(spec.parquet_path for spec in TABLE_SPECS) == tuple(
        f"parquet/{name}.parquet" for name in expected_names
    )


def test_bronze_explicit_specs_have_exact_columns_types_and_keys() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    expected = {
        "bronze_source_column": (
            "source_column",
            (
                _column_contract("catalog_version"),
                _column_contract("source_snapshot_date", "date"),
                _column_contract("source_table_order", "int64"),
                _column_contract("source_table"),
                _column_contract("source_column_number", "int64"),
                _column_contract("source_column_letter"),
                _column_contract("source_column_name"),
                _column_contract("source_declared_type"),
                _column_contract("source_example"),
                _column_contract("source_key_marker"),
                _column_contract("source_name_ko"),
                _column_contract("schema_file"),
                _column_contract("schema_excel_row", "int64"),
            ),
            ("source_table", "source_column_number"),
            ("source_table_order", "source_column_number"),
        ),
        "bronze_source_row": (
            "source_row",
            (
                _column_contract("source_table_order", "int64"),
                _column_contract("source_table"),
                _column_contract("source_file"),
                _column_contract("source_sheet"),
                _column_contract("source_row_number", "int64"),
                _column_contract("source_checksum"),
                _column_contract("source_snapshot_date", "date"),
                _column_contract("raw_payload_json"),
                _column_contract("raw_payload_sha256"),
                _column_contract("loaded_at", "timestamp_utc"),
            ),
            ("source_table", "source_file", "source_sheet", "source_row_number"),
            ("source_table_order", "source_file", "source_sheet", "source_row_number"),
        ),
        "bronze_source_cell": (
            "source_cell",
            (
                _column_contract("source_table_order", "int64"),
                _column_contract("source_table"),
                _column_contract("source_file"),
                _column_contract("source_sheet"),
                _column_contract("source_row_number", "int64"),
                _column_contract("source_column_name"),
                _column_contract("source_column_number", "int64"),
                _column_contract("source_column_letter"),
                _column_contract("source_checksum"),
                _column_contract("source_snapshot_date", "date"),
                _column_contract("source_applicable_date", "date", nullable=True),
                _column_contract("raw_value"),
            ),
            (
                "source_table",
                "source_file",
                "source_sheet",
                "source_row_number",
                "source_column_number",
            ),
            (
                "source_table_order",
                "source_file",
                "source_sheet",
                "source_row_number",
                "source_column_number",
            ),
        ),
    }

    for name, (grain, columns, unique_key, sort_key) in expected.items():
        spec = TABLE_SPEC_BY_NAME[name]
        assert spec.layer == "bronze"
        assert spec.grain == grain
        assert _observed_columns(spec) == columns
        assert spec.unique_key == unique_key
        assert spec.sort_key == sort_key
        assert spec.logical_projection == tuple(column[0] for column in columns)
        assert spec.parquet_path == f"parquet/{name}.parquet"


def test_fund_attribute_and_quality_specs_have_exact_columns_types_and_keys() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    attribute_columns = tuple(
        _column_contract(name, "int64" if name == "source_row_number" else "string")
        for name in (
            "grain",
            "fund_item_id",
            "fund_item_id__quality_status",
            "attribute_code",
            "attribute_code__quality_status",
            "attribute_code_raw",
            "source_row_number",
            "record_json",
        )
    )
    quality_columns = (
        *(
            _column_contract(name)
            for name in (
                "issue_id",
                "rule_id",
                "rule_version",
                "severity",
                "quality_status",
                "source_table",
                "source_file",
                "source_sheet",
            )
        ),
        _column_contract("source_row_number", "int64"),
        _column_contract("source_column_name"),
        _column_contract("source_column_number", "int64"),
        _column_contract("source_column_letter"),
        _column_contract("source_checksum"),
        _column_contract("source_snapshot_date", "date"),
        _column_contract("source_applicable_date", "date", nullable=True),
        _column_contract("reason"),
        _column_contract("quarantined", "bool"),
        _column_contract("raw_payload_sha256"),
        _column_contract("first_detected_at", "timestamp_utc"),
        _column_contract("record_json"),
    )

    attribute = TABLE_SPEC_BY_NAME["silver_fund_item_attribute"]
    assert attribute.grain == "fund_attribute"
    assert _observed_columns(attribute) == attribute_columns
    assert attribute.unique_key == (
        "fund_item_id",
        "attribute_code",
        "attribute_code_raw",
        "source_row_number",
    )
    assert attribute.sort_key == attribute.unique_key

    quality = TABLE_SPEC_BY_NAME["silver_quality_issue"]
    assert quality.grain == "quality_issue"
    assert _observed_columns(quality) == quality_columns
    assert quality.unique_key == ("issue_id",)
    assert quality.sort_key == (
        "source_table",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_column_number",
        "rule_id",
        "issue_id",
    )

    for spec in (attribute, quality):
        assert spec.layer == "silver"
        assert spec.logical_projection == tuple(column.name for column in spec.columns)
        assert spec.parquet_path == f"parquet/{spec.table_name}.parquet"


def test_gold_specs_have_exact_columns_types_and_keys() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    link = TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"]
    assert link.grain == "exact_cross_source_link"
    assert _observed_columns(link) == tuple(
        _column_contract(name, "decimal" if name == "confidence" else "string")
        for name in (
            "link_id",
            "left_table",
            "left_product_id",
            "left_identifier_field",
            "right_table",
            "right_product_id",
            "right_identifier_field",
            "matched_raw_identifier",
            "link_type",
            "confidence",
            "rule_id",
            "rule_version",
        )
    )
    assert link.unique_key == ("left_product_id", "right_product_id", "rule_version")
    assert link.sort_key == link.unique_key

    evidence = TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"]
    evidence_types = {
        "evidence_role_order": "int64",
        "evidence_ordinal": "int64",
        "source_row_number": "int64",
        "source_column_number": "int64",
        "source_snapshot_date": "date",
        "source_applicable_date": "date",
    }
    evidence_names = (
        "link_id",
        "evidence_role",
        "evidence_role_order",
        "evidence_ordinal",
        "raw_identifier",
        "source_table",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_column_name",
        "source_column_number",
        "source_column_letter",
        "source_checksum",
        "source_snapshot_date",
        "source_applicable_date",
    )
    assert evidence.grain == "exact_cross_source_link_evidence"
    assert _observed_columns(evidence) == tuple(
        _column_contract(
            name,
            evidence_types.get(name, "string"),
            nullable=name == "source_applicable_date",
        )
        for name in evidence_names
    )
    assert evidence.unique_key == ("link_id", "evidence_role_order", "evidence_ordinal")
    assert evidence.sort_key == evidence.unique_key

    for spec in (link, evidence):
        assert spec.layer == "gold"
        assert spec.logical_projection == tuple(column.name for column in spec.columns)
        assert spec.parquet_path == f"parquet/{spec.table_name}.parquet"


def test_bond_wide_spec_matches_independent_model_derivation() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    fields = (
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
    spec = TABLE_SPEC_BY_NAME["silver_bond_instrument"]

    assert spec.grain == "instrument"
    assert _observed_columns(spec) == _wide_columns(fields)
    assert spec.unique_key == ("product_id",)
    assert spec.sort_key == ("product_id",)
    assert spec.logical_projection == tuple(column.name for column in spec.columns)


def test_domestic_wide_spec_matches_independent_model_derivation() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    types = {
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
    names = (
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
    fields = tuple(
        (name, types.get(name, "string"), name == "is_eligible_at_as_of") for name in names
    )
    spec = TABLE_SPEC_BY_NAME["silver_domestic_listed_product"]

    assert spec.grain == "listed_product"
    assert _observed_columns(spec) == _wide_columns(fields)
    assert spec.unique_key == ("product_id",)
    assert spec.sort_key == ("product_id",)


def test_overseas_wide_spec_matches_independent_model_derivation() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    names = (
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
    decimals = {
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
    dates = {
        "custom_update_date",
        "close_price_base_date",
        "daily_update_date",
        "listing_date",
        "weekly_update_date",
    }
    fields = tuple(
        (
            name,
            "decimal"
            if name in decimals
            else "date"
            if name in dates
            else "timestamp"
            if name == "nav_base_at"
            else "string",
            False,
        )
        for name in names
    )
    spec = TABLE_SPEC_BY_NAME["silver_overseas_listed_product"]

    assert spec.grain == "listed_product"
    assert _observed_columns(spec) == _wide_columns(fields)
    assert spec.unique_key == ("product_id",)
    assert spec.sort_key == ("product_id",)


def test_fund_item_wide_spec_matches_independent_model_derivation() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    names = (
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
    decimals = {
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
    fields = tuple((name, "decimal" if name in decimals else "string", False) for name in names)
    spec = TABLE_SPEC_BY_NAME["silver_fund_item"]

    assert spec.grain == "fund_item"
    assert _observed_columns(spec) == _wide_columns(fields)
    assert spec.unique_key == ("fund_item_id",)
    assert spec.sort_key == ("fund_item_id",)


def test_derive_wide_columns_exact_signature_and_fund_contributing_rows_absence() -> None:
    from finproof.data.artifacts.table_specs import (
        TABLE_SPEC_BY_NAME,
        derive_wide_columns,
    )
    from finproof.domain.bonds import BondInstrument
    from finproof.domain.domestic_listed import ListedProduct
    from finproof.domain.overseas_listed import OverseasListedProduct
    from finproof.domain.public_funds import FundItem

    parameters = tuple(signature(derive_wide_columns).parameters.values())
    assert len(parameters) == 1
    assert parameters[0].name == "model_type"
    assert parameters[0].default is parameters[0].empty
    assert parameters[0].kind is parameters[0].POSITIONAL_OR_KEYWORD

    registered = (
        (BondInstrument, "silver_bond_instrument"),
        (ListedProduct, "silver_domestic_listed_product"),
        (OverseasListedProduct, "silver_overseas_listed_product"),
        (FundItem, "silver_fund_item"),
    )
    for model_type, table_name in registered:
        derived = derive_wide_columns(model_type)
        assert derived == TABLE_SPEC_BY_NAME[table_name].columns
        names = tuple(column.name for column in derived)
        expected_fields = tuple(
            name
            for name in model_type.model_fields
            if name != "grain" and not (model_type is FundItem and name == "contributing_rows")
        )
        for name in expected_fields:
            assert name in names

    assert "contributing_rows" not in tuple(column.name for column in derive_wide_columns(FundItem))


@pytest.mark.parametrize(
    "case",
    [
        "foreign_base_model",
        "unregistered_shape",
        "bond_subclass",
        "domestic_subclass",
        "overseas_subclass",
        "fund_subclass",
    ],
)
def test_derive_wide_columns_rejects_foreign_unregistered_and_subclass_models(
    case: str,
) -> None:
    from typing import Literal

    from pydantic import BaseModel, ConfigDict

    from finproof.data.artifacts.table_specs import derive_wide_columns
    from finproof.domain.bonds import BondInstrument
    from finproof.domain.domestic_listed import ListedProduct
    from finproof.domain.overseas_listed import OverseasListedProduct
    from finproof.domain.public_funds import FundItem
    from finproof.domain.values import NormalizedValue

    class ForeignWide(BaseModel):
        model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

        grain: Literal["foreign"] = "foreign"
        value: NormalizedValue[str]

    class UnregisteredShape(BaseModel):
        model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

        grain: Literal["unregistered"] = "unregistered"
        product_id: NormalizedValue[str]

    candidates = {
        "foreign_base_model": ForeignWide,
        "unregistered_shape": UnregisteredShape,
        "bond_subclass": type("BondSubclass", (BondInstrument,), {}),
        "domestic_subclass": type("DomesticSubclass", (ListedProduct,), {}),
        "overseas_subclass": type("OverseasSubclass", (OverseasListedProduct,), {}),
        "fund_subclass": type("FundSubclass", (FundItem,), {}),
    }

    with pytest.raises(TypeError, match="registered"):
        derive_wide_columns(candidates[case])


@pytest.mark.parametrize("mutation", ["insert", "remove", "reorder"])
def test_model_drift_guard_rejects_insert_remove_and_reorder(
    mutation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finproof.data.artifacts.table_specs import (
        TABLE_SPEC_BY_NAME,
        assert_model_matches_frozen_spec,
    )
    from finproof.domain.bonds import BondInstrument

    fields = dict(BondInstrument.model_fields)
    if mutation == "insert":
        fields["inserted"] = fields["product_id"]
    elif mutation == "remove":
        fields.pop("name")
    else:
        items = list(fields.items())
        items[1], items[2] = items[2], items[1]
        fields = dict(items)
    monkeypatch.setattr(BondInstrument, "model_fields", fields)

    with pytest.raises(ValueError, match="drift"):
        assert_model_matches_frozen_spec(
            BondInstrument, TABLE_SPEC_BY_NAME["silver_bond_instrument"]
        )


@pytest.mark.parametrize(
    "case", ["equal_copy", "model_subclass", "wrong_model", "wrong_table_pair"]
)
def test_registry_rejects_forged_equal_spec_and_wrong_model_pair(case: str) -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, require_registered_spec
    from finproof.domain.bonds import BondInstrument
    from finproof.domain.domestic_listed import ListedProduct

    bond = TABLE_SPEC_BY_NAME["silver_bond_instrument"]
    domestic = TABLE_SPEC_BY_NAME["silver_domestic_listed_product"]
    candidates = {
        "equal_copy": (bond.model_copy(), BondInstrument),
        "model_subclass": (bond, type("BondSubclass", (BondInstrument,), {})),
        "wrong_model": (bond, ListedProduct),
        "wrong_table_pair": (domestic, BondInstrument),
    }

    with pytest.raises(ValueError, match="registered"):
        require_registered_spec(*candidates[case])


@pytest.mark.parametrize(
    "target",
    [
        "table_name",
        "layer",
        "grain",
        "parquet_path",
        "columns",
        "unique_key",
        "sort_key",
        "logical_projection",
        "column.name",
        "column.logical_type",
        "column.arrow_type",
        "column.duckdb_type",
        "column.nullable",
    ],
)
def test_registered_spec_fingerprint_rejects_every_scalar_key_and_nested_column_mutation(
    target: str,
) -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, require_registered_spec
    from finproof.domain.bonds import BondInstrument

    spec = TABLE_SPEC_BY_NAME["silver_bond_instrument"]
    owner = spec.columns[0] if target.startswith("column.") else spec
    field = target.split(".")[-1]
    original = getattr(owner, field)
    replacements = {
        "table_name": "forged_table",
        "layer": "gold",
        "grain": "forged_grain",
        "parquet_path": "parquet/forged.parquet",
        "columns": tuple(reversed(spec.columns)),
        "unique_key": ("name",),
        "sort_key": ("name",),
        "logical_projection": tuple(reversed(spec.logical_projection)),
        "name": "forged_column",
        "logical_type": "int64",
        "arrow_type": "int64",
        "duckdb_type": "BIGINT",
        "nullable": True,
    }
    try:
        object.__setattr__(owner, field, replacements[field])
        with pytest.raises(ValueError, match="fingerprint"):
            require_registered_spec(spec, BondInstrument)
    finally:
        object.__setattr__(owner, field, original)


def test_frozen_spec_hash_metamorphisms() -> None:
    from finproof.data.artifacts.hashing import schema_sha256
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    spec = TABLE_SPEC_BY_NAME["silver_bond_instrument"]
    baseline = schema_sha256(spec)
    assert schema_sha256(spec.model_copy(update={"layer": "gold"})) == baseline
    assert (
        schema_sha256(spec.model_copy(update={"parquet_path": "parquet/physical-only.parquet"}))
        == baseline
    )

    last = spec.columns[-1]
    renamed = last.model_copy(update={"name": "record_json_changed"})
    renamed_projection = tuple(
        "record_json_changed" if name == "record_json" else name for name in spec.logical_projection
    )
    changed = (
        spec.model_copy(update={"table_name": "changed"}),
        spec.model_copy(update={"grain": "changed"}),
        spec.model_copy(
            update={
                "columns": (*spec.columns[:-1], renamed),
                "logical_projection": renamed_projection,
            }
        ),
        spec.model_copy(
            update={
                "columns": (
                    *spec.columns[:-1],
                    last.model_copy(
                        update={
                            "logical_type": "int64",
                            "arrow_type": "int64",
                            "duckdb_type": "BIGINT",
                        }
                    ),
                )
            }
        ),
        spec.model_copy(
            update={"columns": (*spec.columns[:-1], last.model_copy(update={"nullable": True}))}
        ),
        spec.model_copy(update={"unique_key": ("name",)}),
        spec.model_copy(update={"sort_key": ("name",)}),
    )
    assert all(schema_sha256(candidate) != baseline for candidate in changed)
