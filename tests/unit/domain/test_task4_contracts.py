"""Task 4 shared normalization-contract tests."""

from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Literal

import pytest
from pydantic import ValidationError

from finproof.domain.locators import SourceCellLocator
from finproof.domain.public_funds import FundItemValue
from finproof.domain.quality import QualityStatus
from finproof.domain.values import NormalizedValue
from tests.helpers.source_rows import (
    OVERSEAS_LISTED_COLUMNS,
    PUBLIC_FUND_COLUMNS,
    source_row,
)

Task4TableId = Literal["PREF02N001", "PRFD01N001"]


@pytest.mark.parametrize(
    ("table_id", "columns"),
    [
        ("PREF02N001", OVERSEAS_LISTED_COLUMNS),
        ("PRFD01N001", PUBLIC_FUND_COLUMNS),
    ],
)
def test_task4_fixture_has_every_official_cell_in_canonical_order(
    table_id: Task4TableId, columns: tuple[str, ...]
) -> None:
    """Removing or reordering an official fixture cell breaks raw-lineage parity."""
    row = source_row(table_id)
    assert tuple(cell.column_name for cell in row.cells) == columns
    assert row.raw_payload == tuple(cell.raw_value for cell in row.cells)


def test_task4_fixture_rejects_unknown_value_and_applicable_date_columns() -> None:
    """Task 4 fixtures must not accept invented cells outside the catalog."""
    with pytest.raises(KeyError, match="unknown source columns"):
        source_row("PREF02N001", {"not_a_column": "x"})
    with pytest.raises(KeyError, match="unknown applicable-date columns"):
        source_row("PRFD01N001", applicable_dates={"not_a_column": None})


def test_shared_listed_type_is_the_domestic_reexport() -> None:
    """Domestic and overseas listed records must serialize one exact enum class."""
    from finproof.domain.domestic_listed import ListedProductType as DomesticType
    from finproof.domain.listed import ListedProductType

    assert DomesticType is ListedProductType
    assert tuple(member.value for member in ListedProductType) == ("ETF", "ETN")


def _fund_value(
    row_number: int,
    raw: str = "100.00",
    applicable_date: date | None = None,
) -> NormalizedValue[Decimal]:
    row = source_row(
        "PRFD01N001",
        {"fd_nast_suma": raw},
        excel_row=row_number,
        applicable_dates=({} if applicable_date is None else {"fd_nast_suma": applicable_date}),
    )
    return NormalizedValue[Decimal](
        raw_value=raw,
        normalized_value=Decimal(raw),
        quality_status=QualityStatus.VALID,
        rule_id="public_fund.net_assets",
        rule_version="1.0.0",
        source=SourceCellLocator.from_row(row, "fd_nast_suma"),
    )


def test_fund_item_value_is_strict_frozen_and_forbids_extra_fields() -> None:
    """The shared collapse value must remain an immutable strict boundary."""
    assert FundItemValue.model_config["frozen"] is True
    assert FundItemValue.model_config["extra"] == "forbid"
    assert FundItemValue.model_config["strict"] is True


def test_fund_item_value_preserves_representative_and_all_sorted_sources() -> None:
    """Dropping a repeated agreeing source or its typed value breaks round trips."""
    representative = _fund_value(2)
    second = _fund_value(9)
    value = FundItemValue[Decimal](
        representative=representative,
        equivalent_sources=(representative.source, second.source),
    )

    restored = FundItemValue[Decimal].model_validate_json(value.model_dump_json())

    assert restored == value
    assert restored.representative.normalized_value == Decimal("100.00")
    assert restored.equivalent_sources == (representative.source, second.source)


def test_fund_item_value_preserves_distinct_row_and_applicable_date_locators() -> None:
    """Per-cell applicable dates are not part of shared-lineage equality."""
    representative = _fund_value(2, applicable_date=date(2026, 6, 1))
    second = _fund_value(9, applicable_date=date(2026, 6, 30))
    value = FundItemValue[Decimal](
        representative=representative,
        equivalent_sources=(representative.source, second.source),
    )

    assert tuple(source.source_row_number for source in value.equivalent_sources) == (
        2,
        9,
    )
    assert tuple(source.source_applicable_date for source in value.equivalent_sources) == (
        date(2026, 6, 1),
        date(2026, 6, 30),
    )


@pytest.mark.parametrize(
    "sources",
    [
        (),
        (_fund_value(9).source, _fund_value(2).source),
    ],
)
def test_fund_item_value_rejects_empty_or_reordered_sources(
    sources: tuple[SourceCellLocator, ...],
) -> None:
    """The representative must be first in a nonempty ascending locator tuple."""
    with pytest.raises(ValidationError):
        FundItemValue[Decimal](representative=_fund_value(2), equivalent_sources=sources)


def test_fund_item_value_rejects_later_sources_out_of_order() -> None:
    """All locators, not only the representative, must use ascending source order."""
    representative = _fund_value(2)

    with pytest.raises(ValidationError):
        FundItemValue[Decimal](
            representative=representative,
            equivalent_sources=(
                representative.source,
                _fund_value(9).source,
                _fund_value(5).source,
            ),
        )


def test_fund_item_value_rejects_duplicate_wrong_column_or_wrong_table() -> None:
    """A value cannot claim repeated or unrelated source cells as equivalent."""
    representative = _fund_value(2)
    other_fund_row = source_row("PRFD01N001", excel_row=9)
    invalid_source_sets = (
        (representative.source, representative.source),
        (
            representative.source,
            SourceCellLocator.from_row(other_fund_row, "fd_wk1_ern_r"),
        ),
        (
            representative.source,
            SourceCellLocator.from_row(source_row("PREF02N001", excel_row=9), "du_last_aum"),
        ),
    )
    for sources in invalid_source_sets:
        with pytest.raises(ValidationError):
            FundItemValue[Decimal](
                representative=representative,
                equivalent_sources=sources,
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_file", PurePosixPath("data/other.xlsx")),
        ("source_sheet", "other_sheet"),
        ("source_checksum", "b" * 64),
        ("source_snapshot_date", date(2026, 7, 10)),
    ],
)
def test_fund_item_value_rejects_invented_shared_lineage(field: str, value: object) -> None:
    """Every non-row lineage field must match the representative exactly."""
    representative = _fund_value(2)
    second = _fund_value(9).source.model_copy(update={field: value})

    with pytest.raises(ValidationError):
        FundItemValue[Decimal](
            representative=representative,
            equivalent_sources=(representative.source, second),
        )


def test_fund_item_value_rejects_same_source_position_with_invented_date() -> None:
    """One source row cannot be counted twice by inventing a different cell date."""
    representative = _fund_value(2)
    duplicate_position = representative.source.model_copy(
        update={"source_applicable_date": date(2026, 6, 1)}
    )

    with pytest.raises(ValidationError):
        FundItemValue[Decimal](
            representative=representative,
            equivalent_sources=(representative.source, duplicate_position),
        )
