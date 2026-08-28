"""Retained Task-4 domain boundaries after the refreshed public-fund migration."""

import json

import pytest
from pydantic import ValidationError

from finproof.data.normalization.public_funds import normalize_public_fund_item
from finproof.domain.domestic_listed import ListedProductType as DomesticListedProductType
from finproof.domain.listed import ListedProductType
from finproof.domain.public_funds import FundItem, PublicFundItem
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import (
    DOMESTIC_LISTED_COLUMNS,
    OVERSEAS_LISTED_COLUMNS,
    PUBLIC_FUND_COLUMNS,
    source_row,
)


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("PREF01N001", DOMESTIC_LISTED_COLUMNS),
        ("PREF02N001", OVERSEAS_LISTED_COLUMNS),
        ("PRFD01N001", PUBLIC_FUND_COLUMNS),
    ],
)
def test_task4_fixture_has_every_official_cell_in_canonical_order(
    table: str,
    columns: tuple[str, ...],
) -> None:
    row = source_row(table, {})  # type: ignore[arg-type]
    assert tuple(cell.column_name for cell in row.cells) == columns
    assert row.raw_payload == tuple(cell.raw_value for cell in row.cells)


def test_task4_fixture_rejects_unknown_value_and_applicable_date_columns() -> None:
    with pytest.raises(KeyError, match="unknown source columns"):
        source_row("PRFD01N001", {"not_a_column": "x"})
    with pytest.raises(KeyError, match="unknown applicable-date columns"):
        source_row("PREF02N001", applicable_dates={"not_a_column": None})


def test_shared_listed_type_is_the_domestic_reexport() -> None:
    assert ListedProductType is DomesticListedProductType
    assert ListedProductType.ETF.value == "ETF"
    assert ListedProductType.ETN.value == "ETN"


def _fund_item() -> PublicFundItem:
    record = normalize_public_fund_item(source_row("PRFD01N001", excel_row=7)).record
    assert record is not None
    return record


def _python_payload(item: PublicFundItem) -> dict[str, object]:
    return {name: getattr(item, name) for name in PublicFundItem.model_fields}


def test_public_fund_item_model_is_strict_frozen_and_forbids_extra_fields() -> None:
    item = _fund_item()
    assert PublicFundItem.model_config["frozen"] is True
    assert PublicFundItem.model_config["extra"] == "forbid"
    assert PublicFundItem.model_config["strict"] is True
    with pytest.raises(ValidationError):
        PublicFundItem.model_validate(_python_payload(item) | {"extra": "x"})
    with pytest.raises(ValidationError):
        item.name = item.name


def test_public_fund_runtime_item_name_points_to_the_direct_item_contract() -> None:
    assert FundItem is PublicFundItem


def test_public_fund_item_keeps_exact_python_source_row_and_rejects_mapping() -> None:
    item = _fund_item()
    assert PublicFundItem.model_validate(_python_payload(item)).source_row is item.source_row
    with pytest.raises(ValidationError, match="exact SourceRow"):
        PublicFundItem.model_validate(
            _python_payload(item) | {"source_row": item.source_row.model_dump()}
        )


def test_public_fund_item_rejects_source_row_subclass() -> None:
    class SourceRowSubclass(SourceRow):
        pass

    item = _fund_item()
    subclass = SourceRowSubclass.model_validate(item.source_row.model_dump())
    with pytest.raises(ValidationError, match="exact SourceRow"):
        PublicFundItem.model_validate(_python_payload(item) | {"source_row": subclass})


def test_public_fund_item_json_round_trip_preserves_row_attributes_and_lineage() -> None:
    item = _fund_item()
    restored = PublicFundItem.model_validate_json(item.model_dump_json())
    assert restored == item
    assert restored.attribute_codes == ("C101", "V101", "D102")
    assert restored.attribute_count.source == item.attribute_count.source
    assert restored.attribute_search_text.source == item.attribute_search_text.source


def test_public_fund_item_rejects_attribute_codes_not_derived_from_raw_cell() -> None:
    payload = json.loads(_fund_item().model_dump_json())
    payload["attribute_codes"] = ["invented"]
    with pytest.raises(ValidationError, match="comma split"):
        PublicFundItem.model_validate_json(json.dumps(payload))


def test_public_fund_item_rejects_wrapper_raw_or_locator_swap() -> None:
    item = _fund_item()
    wrong_raw = item.name.model_copy(update={"raw_value": "invented"})
    wrong_source = item.name.model_copy(update={"source": item.currency.source})
    with pytest.raises(ValidationError, match="raw value"):
        PublicFundItem.model_validate(_python_payload(item) | {"name": wrong_raw})
    with pytest.raises(ValidationError, match="locator"):
        PublicFundItem.model_validate(_python_payload(item) | {"name": wrong_source})


def test_public_fund_item_rejects_noncanonical_source_row_json() -> None:
    item = _fund_item()
    payload = json.loads(item.model_dump_json())
    source_row_payload = payload["source_row"]
    assert isinstance(source_row_payload, dict)
    source_row_payload["unexpected"] = "x"
    with pytest.raises(ValidationError, match="canonical SourceRow"):
        PublicFundItem.model_validate_json(json.dumps(payload))


def test_public_fund_item_exposes_no_group_or_expanded_attribute_relation() -> None:
    assert {"contributing_rows", "attributes", "attribute_rows"}.isdisjoint(
        PublicFundItem.model_fields
    )
