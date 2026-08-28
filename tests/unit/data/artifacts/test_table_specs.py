"""Frozen table-spec contracts for artifact persistence."""

from collections.abc import Iterator
from inspect import signature
from typing import NoReturn, Self, cast

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
        TABLE_SPECS,
        ClosedTableSpecRegistry,
        require_registered_table_spec,
    )

    spec = TABLE_SPECS[0]
    original_columns = spec.columns
    try:
        object.__setattr__(spec, "columns", (*original_columns, original_columns[0]))
        with pytest.raises(ValueError, match="column names"):
            ClosedTableSpecRegistry(TABLE_SPECS)
    finally:
        object.__setattr__(spec, "columns", original_columns)

    require_registered_table_spec(spec)


def test_refreshed_silver_inventory_contains_lots_not_fund_attribute_rows() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    names = tuple(spec.table_name for spec in TABLE_SPECS)
    assert len(names) == 13
    assert "silver_bond_sale_lot" in names
    assert "silver_fund_item_attribute" not in names


def test_holding_relations_are_the_only_additions_to_final_thirteen_table_inventory() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TABLE_SPECS

    assert len(TABLE_SPECS) == 13
    assert tuple(spec.table_name for spec in TABLE_SPECS[9:11]) == (
        "silver_product_holding",
        "silver_product_holding_coverage",
    )
    assert tuple(spec.layer for spec in TABLE_SPECS) == (
        "bronze",
        "bronze",
        "bronze",
        "silver",
        "silver",
        "silver",
        "silver",
        "silver",
        "silver",
        "silver",
        "silver",
        "gold",
        "gold",
    )
    holding = TABLE_SPEC_BY_NAME["silver_product_holding"]
    assert holding.grain == "product_holding"
    assert holding.unique_key == (
        "owner_product_type",
        "owner_product_id",
        "source_row_ordinal",
    )
    assert holding.sort_key == holding.unique_key
    assert tuple(column.name for column in holding.columns) == (
        "generation_id",
        "owner_product_type",
        "owner_product_id",
        "owner_source_identifier",
        "owner_identifier_type",
        "owner_link_method",
        "constituent_identifier",
        "constituent_identifier_type",
        "raw_name",
        "display_name",
        "quantity",
        "quantity_unit",
        "market_value",
        "market_value_currency",
        "weight",
        "weight_unit",
        "source_owner",
        "source_kind",
        "direct_source_url",
        "raw_file_sha256",
        "source_as_of_date",
        "publication_date",
        "source_row_ordinal",
        "quality_state",
        "record_json",
    )
    coverage = TABLE_SPEC_BY_NAME["silver_product_holding_coverage"]
    assert coverage.grain == "product_holding_coverage"
    assert coverage.unique_key == ("owner_product_type", "owner_product_id")
    assert coverage.sort_key == coverage.unique_key
    assert coverage.columns[-1].name == "record_json"


def test_bond_sale_lot_physical_key_includes_original_row_lineage() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    spec = TABLE_SPEC_BY_NAME["silver_bond_sale_lot"]
    assert spec.unique_key == (
        "product_id",
        "exchange_market",
        "info_base_date",
        "info_sequence",
        "source_row_number",
    )
    assert spec.sort_key == spec.unique_key
    assert "source_row_number" in spec.logical_projection


@pytest.mark.parametrize(
    "case",
    [
        "list",
        "generator",
        "rebuilt-tuple",
        "one-copied-member",
        "foreign-member",
        "short",
        "long",
        "duplicate",
        "adjacent-swap",
        "reversed",
    ],
)
def test_closed_table_spec_registry_accepts_only_exact_frozen_table_specs_tuple(
    case: str,
) -> None:
    from finproof.data.artifacts.table_specs import (
        TABLE_SPECS,
        ClosedTableSpecRegistry,
        TableSpec,
    )

    candidate: object
    if case == "list":
        candidate = list(TABLE_SPECS)
    elif case == "generator":
        candidate = (spec for spec in TABLE_SPECS)
    elif case == "rebuilt-tuple":
        candidate = (*TABLE_SPECS,)
    elif case == "one-copied-member":
        candidate = (TABLE_SPECS[0].model_copy(), *TABLE_SPECS[1:])
    elif case == "foreign-member":
        foreign = TABLE_SPECS[0].model_copy(update={"table_name": "foreign"})
        candidate = (foreign, *TABLE_SPECS[1:])
    elif case == "short":
        candidate = TABLE_SPECS[:-1]
    elif case == "long":
        candidate = (*TABLE_SPECS, TABLE_SPECS[-1])
    elif case == "duplicate":
        candidate = (*TABLE_SPECS[:-1], TABLE_SPECS[0])
    elif case == "adjacent-swap":
        candidate = (TABLE_SPECS[1], TABLE_SPECS[0], *TABLE_SPECS[2:])
    else:
        candidate = tuple(reversed(TABLE_SPECS))

    expected_error = TypeError if case in {"list", "generator"} else ValueError
    expected_message = "tuple" if expected_error is TypeError else "exact frozen table specs"
    with pytest.raises(expected_error, match=expected_message):
        ClosedTableSpecRegistry(cast(tuple[TableSpec, ...], candidate))

    ClosedTableSpecRegistry(TABLE_SPECS)


@pytest.mark.parametrize("case", ["iterable", "generator", "list", "iterator"])
def test_closed_registry_rejects_foreign_generator_typed_without_pulling_it(
    case: str,
) -> None:
    from finproof.data.artifacts.table_specs import ClosedTableSpecRegistry, TableSpec

    pulls = 0

    class ForeignIterable:
        def __iter__(self) -> NoReturn:
            nonlocal pulls
            pulls += 1
            raise RuntimeError("foreign iterable was pulled")

    class ForeignIterator:
        def __iter__(self) -> Self:
            return self

        def __next__(self) -> NoReturn:
            nonlocal pulls
            pulls += 1
            raise RuntimeError("foreign iterator was pulled")

    class ForeignElement:
        @property
        def columns(self) -> NoReturn:
            nonlocal pulls
            pulls += 1
            raise RuntimeError("foreign list element was inspected")

    def foreign_generator() -> Iterator[object]:
        nonlocal pulls
        pulls += 1
        yield ForeignElement()

    candidates = {
        "iterable": ForeignIterable(),
        "generator": foreign_generator(),
        "list": [ForeignElement()],
        "iterator": ForeignIterator(),
    }

    with pytest.raises(TypeError, match="tuple"):
        ClosedTableSpecRegistry(cast(tuple[TableSpec, ...], candidates[case]))

    assert pulls == 0


def test_closed_table_spec_registry_ordered_specs_satisfies_cp2_kernel_port() -> None:
    from finproof.data.artifacts.manifest import ClosedTableSpecRegistry as ManifestRegistry
    from finproof.data.artifacts.table_specs import TABLE_SPEC_REGISTRY, TABLE_SPECS

    registry: ManifestRegistry = TABLE_SPEC_REGISTRY

    def kernel_spy(port: ManifestRegistry) -> tuple[object, ...]:
        return port.ordered_specs()

    observed = kernel_spy(registry)
    assert observed is TABLE_SPECS
    assert len(observed) == 13
    assert all(observed[index] is TABLE_SPECS[index] for index in range(13))


def test_table_registry_has_exact_thirteen_names_and_paths() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TABLE_SPECS

    expected_names = (
        "bronze_source_column",
        "bronze_source_row",
        "bronze_source_cell",
        "silver_bond_sale_lot",
        "silver_bond_instrument",
        "silver_domestic_listed_product",
        "silver_overseas_listed_product",
        "silver_fund_item",
        "silver_quality_issue",
        "silver_product_holding",
        "silver_product_holding_coverage",
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


def test_quality_spec_has_exact_columns_types_and_keys() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

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

    assert quality.layer == "silver"
    assert quality.logical_projection == tuple(column.name for column in quality.columns)
    assert quality.parquet_path == "parquet/silver_quality_issue.parquet"


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


def test_refreshed_wide_specs_match_registered_model_projections() -> None:
    from pydantic import BaseModel

    from finproof.data.artifacts.table_specs import (
        TABLE_SPEC_BY_NAME,
        derive_wide_columns,
    )
    from finproof.domain.bonds import BondInstrument, BondSaleLot
    from finproof.domain.domestic_listed import ListedProduct
    from finproof.domain.overseas_listed import OverseasListedProduct
    from finproof.domain.public_funds import PublicFundItem

    cases: tuple[tuple[type[BaseModel], str, int, frozenset[str]], ...] = (
        (
            BondSaleLot,
            "silver_bond_sale_lot",
            43,
            frozenset({"source_row", "source_key"}),
        ),
        (
            BondInstrument,
            "silver_bond_instrument",
            43,
            frozenset({"selected_lot_key", "field_sources", "buy_yield_range"}),
        ),
        (ListedProduct, "silver_domestic_listed_product", 201, frozenset()),
        (OverseasListedProduct, "silver_overseas_listed_product", 100, frozenset()),
        (
            PublicFundItem,
            "silver_fund_item",
            94,
            frozenset({"source_row", "attribute_codes"}),
        ),
    )
    for model_type, table_name, column_count, json_only in cases:
        spec = TABLE_SPEC_BY_NAME[table_name]
        derived = derive_wide_columns(model_type)
        assert derived == spec.columns
        assert len(spec.columns) == column_count
        assert spec.grain == model_type.model_fields["grain"].default
        assert spec.logical_projection == tuple(column.name for column in spec.columns)
        projected_names = tuple(column.name for column in spec.columns)
        for field_name in model_type.model_fields:
            if field_name != "grain" and field_name not in json_only:
                assert field_name in projected_names

    assert "source_row_number" in TABLE_SPEC_BY_NAME["silver_bond_sale_lot"].logical_projection


def test_derive_wide_columns_exact_signature_and_json_only_fields_absent() -> None:
    from finproof.data.artifacts.table_specs import derive_wide_columns
    from finproof.domain.bonds import BondInstrument, BondSaleLot
    from finproof.domain.public_funds import PublicFundItem

    parameters = tuple(signature(derive_wide_columns).parameters.values())
    assert len(parameters) == 1
    assert parameters[0].name == "model_type"
    assert parameters[0].default is parameters[0].empty
    assert parameters[0].kind is parameters[0].POSITIONAL_OR_KEYWORD

    bond_lot_names = tuple(column.name for column in derive_wide_columns(BondSaleLot))
    assert "source_row" not in bond_lot_names
    assert "source_key" not in bond_lot_names
    assert "source_row_number" in bond_lot_names

    bond_names = tuple(column.name for column in derive_wide_columns(BondInstrument))
    assert "selected_lot_key" not in bond_names
    assert "field_sources" not in bond_names
    assert "buy_yield_range" not in bond_names

    fund_names = tuple(column.name for column in derive_wide_columns(PublicFundItem))
    assert "source_row" not in fund_names
    assert "attribute_codes" not in fund_names


@pytest.mark.parametrize(
    "case",
    [
        "foreign_base_model",
        "unregistered_shape",
        "bond_lot_subclass",
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
    from finproof.domain.bonds import BondInstrument, BondSaleLot
    from finproof.domain.domestic_listed import ListedProduct
    from finproof.domain.overseas_listed import OverseasListedProduct
    from finproof.domain.public_funds import PublicFundItem
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
        "bond_lot_subclass": type("BondLotSubclass", (BondSaleLot,), {}),
        "bond_subclass": type("BondSubclass", (BondInstrument,), {}),
        "domestic_subclass": type("DomesticSubclass", (ListedProduct,), {}),
        "overseas_subclass": type("OverseasSubclass", (OverseasListedProduct,), {}),
        "fund_subclass": type("FundSubclass", (PublicFundItem,), {}),
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
        product_index = next(index for index, item in enumerate(items) if item[0] == "product_id")
        name_index = next(index for index, item in enumerate(items) if item[0] == "name")
        items[product_index], items[name_index] = items[name_index], items[product_index]
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
