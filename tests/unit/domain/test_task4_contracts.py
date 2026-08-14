"""Task 4 shared normalization-contract tests."""

import json
from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Literal

import pytest
from pydantic import ValidationError

from finproof.data.normalization.public_funds import normalize_fund_attribute
from finproof.domain.locators import SourceCellLocator
from finproof.domain.public_funds import FundAttributeRow, FundItemValue
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue
from tests.helpers.source_rows import (
    OVERSEAS_LISTED_COLUMNS,
    PUBLIC_FUND_COLUMNS,
    source_row,
)

Task4TableId = Literal["PREF02N001", "PRFD01N001"]


def test_fund_attribute_row_model_is_strict_frozen() -> None:
    """The fund source-row contract must reject mutation and undeclared fields."""
    assert FundAttributeRow.model_config["frozen"] is True
    assert FundAttributeRow.model_config["extra"] == "forbid"
    assert FundAttributeRow.model_config["strict"] is True


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


def _fund_record() -> FundAttributeRow:
    record = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "USA ", "fd_nast_suma": "100.2500"},
            excel_row=99,
        )
    ).record
    assert record is not None
    return record


def _fund_record_python_payload(record: FundAttributeRow) -> dict[str, object]:
    return {name: getattr(record, name) for name in type(record).model_fields}


def test_fund_attribute_row_keeps_the_exact_python_source_row_instance() -> None:
    """The normalizer must retain rather than reconstruct its verified input row."""
    row = source_row("PRFD01N001", excel_row=41)

    record = normalize_fund_attribute(row).record

    assert record is not None
    assert record.source_row is row


def test_fund_attribute_row_rejects_python_mapping_but_accepts_exact_source_row() -> None:
    """Python mode accepts exact SourceRow objects, not coercible mappings."""
    record = _fund_record()
    payload = _fund_record_python_payload(record)

    with pytest.raises(ValidationError, match="exact SourceRow instance"):
        FundAttributeRow.model_validate(payload | {"source_row": record.source_row.model_dump()})

    reconstructed = SourceRow.model_validate(record.source_row.model_dump())
    restored = FundAttributeRow.model_validate(payload | {"source_row": reconstructed})
    assert restored.source_row is reconstructed


def test_fund_attribute_row_rejects_source_row_subclass() -> None:
    """A subclass cannot override or weaken the exact SourceRow contract."""

    class SourceRowSubclass(SourceRow):
        pass

    record = _fund_record()
    subclass = SourceRowSubclass.model_validate(record.source_row.model_dump())
    payload = _fund_record_python_payload(record)

    with pytest.raises(ValidationError, match="exact SourceRow instance"):
        FundAttributeRow.model_validate(payload | {"source_row": subclass})


def test_fund_attribute_row_allows_only_canonical_json_round_trip() -> None:
    """Canonical structural JSON round-trips without becoming trusted ingestion."""
    record = _fund_record()
    encoded = record.model_dump_json()

    restored = FundAttributeRow.model_validate_json(encoded)

    assert restored == record
    assert restored.model_dump_json() == encoded
    assert restored.source_row.raw_payload == record.source_row.raw_payload
    assert restored.attribute_code.raw_value == "USA "
    assert restored.attribute_code.normalized_value == "USA"

    noncanonical = json.loads(encoded)
    noncanonical["source_row"]["cells"] = list(reversed(noncanonical["source_row"]["cells"]))
    with pytest.raises(ValidationError, match="canonical SourceRow JSON shape"):
        FundAttributeRow.model_validate_json(json.dumps(noncanonical))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_table", "PREF02N001"),
        ("source_file", PurePosixPath("data/other.xlsx")),
        ("source_sheet", "other"),
        ("source_row_number", 100),
        ("source_checksum", "b" * 64),
        ("source_snapshot_date", date(2026, 7, 10)),
    ],
)
def test_fund_attribute_row_rejects_python_source_lineage_mutation(
    field: str, value: object
) -> None:
    """Typed wrappers cannot be paired with a different exact SourceRow lineage."""
    record = _fund_record()
    mutated_row = record.source_row.model_copy(update={field: value})

    with pytest.raises(ValidationError):
        FundAttributeRow.model_validate(
            _fund_record_python_payload(record) | {"source_row": mutated_row}
        )


def test_fund_attribute_row_rejects_python_source_cell_and_payload_mutation() -> None:
    """A changed raw source cell cannot retain wrappers from the original row."""
    record = _fund_record()
    cells = list(record.source_row.cells)
    cells[0] = cells[0].model_copy(update={"raw_value": "changed"})
    mutated_row = SourceRow(
        **(
            record.source_row.model_dump(exclude={"cells", "raw_payload"})
            | {
                "cells": tuple(cells),
                "raw_payload": tuple(cell.raw_value for cell in cells),
            }
        )
    )

    with pytest.raises(ValidationError):
        FundAttributeRow.model_validate(
            _fund_record_python_payload(record) | {"source_row": mutated_row}
        )


def test_fund_attribute_row_rejects_python_source_column_name_mutation() -> None:
    """The nested row itself must retain the canonical 45-column catalog order."""
    record = _fund_record()
    cells = list(record.source_row.cells)
    cells[0] = cells[0].model_copy(update={"column_name": "wrong_column"})
    mutated_row = SourceRow(
        **(record.source_row.model_dump(exclude={"cells"}) | {"cells": tuple(cells)})
    )

    with pytest.raises(ValidationError):
        FundAttributeRow.model_validate(
            _fund_record_python_payload(record) | {"source_row": mutated_row}
        )


def test_fund_attribute_row_rejects_wrapper_raw_or_locator_swap() -> None:
    """Every wrapper must match its mapped raw cell and exact locator."""
    record = _fund_record()
    payload = _fund_record_python_payload(record)
    wrong_raw = record.benchmark_name.model_copy(update={"raw_value": "changed"})
    wrong_source = record.benchmark_name.model_copy(
        update={"source": record.benchmark_english_name.source}
    )

    with pytest.raises(ValidationError):
        FundAttributeRow.model_validate(payload | {"benchmark_name": wrong_raw})
    with pytest.raises(ValidationError):
        FundAttributeRow.model_validate(payload | {"benchmark_name": wrong_source})


def _mutated_fund_json(mutator: object) -> str:
    payload = json.loads(_fund_record().model_dump_json())
    assert callable(mutator)
    mutator(payload)
    return json.dumps(payload)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload["source_row"].__setitem__("unexpected", "x"),
        lambda payload: payload["source_row"].pop("source_sheet"),
        lambda payload: payload["source_row"]["cells"][0].__setitem__("unexpected", "x"),
        lambda payload: payload["source_row"]["cells"][0].pop("raw_value"),
        lambda payload: payload["source_row"].__setitem__("cells", {}),
        lambda payload: payload["source_row"].__setitem__("raw_payload", {}),
        lambda payload: payload["source_row"]["cells"].__setitem__(0, "cell"),
        lambda payload: payload["source_row"]["cells"].pop(),
        lambda payload: payload["source_row"]["raw_payload"].__setitem__(0, "changed"),
    ],
)
def test_fund_attribute_row_rejects_noncanonical_json_shapes(mutator: object) -> None:
    """JSON arrays, object keys, cell count, and raw payload must be canonical."""
    with pytest.raises(ValidationError, match="canonical SourceRow JSON shape"):
        FundAttributeRow.model_validate_json(_mutated_fund_json(mutator))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_table", 1),
        ("source_table", ""),
        ("source_file", 1),
        ("source_sheet", 1),
        ("source_sheet", ""),
        ("source_checksum", 1),
        ("source_checksum", ""),
        ("source_row_number", "99"),
        ("source_row_number", True),
        ("source_snapshot_date", "20260711"),
        ("source_snapshot_date", "2026-7-1"),
        ("source_snapshot_date", 20260711),
        ("source_snapshot_date", True),
        ("source_file", ""),
        ("source_file", "/data/file.xlsx"),
        ("source_file", "data/../file.xlsx"),
        ("source_file", "data//file.xlsx"),
        ("source_file", "data/./file.xlsx"),
    ],
)
def test_fund_attribute_row_rejects_noncanonical_json_row_scalars(
    field: str, value: object
) -> None:
    """Coercible, unsafe, and noncanonical row scalars fail before Pydantic coercion."""

    def mutate(payload: dict[str, object]) -> None:
        source_row_payload = payload["source_row"]
        assert isinstance(source_row_payload, dict)
        source_row_payload[field] = value

    with pytest.raises(ValidationError, match="canonical SourceRow JSON shape"):
        FundAttributeRow.model_validate_json(_mutated_fund_json(mutate))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("column_name", 1),
        ("excel_column_letter", 1),
        ("raw_value", 1),
        ("excel_column_number", "1"),
        ("excel_column_number", True),
        ("applicable_date", "20260711"),
        ("applicable_date", "2026-7-1"),
        ("applicable_date", 20260711),
        ("applicable_date", True),
    ],
)
def test_fund_attribute_row_rejects_noncanonical_json_cell_scalars(
    field: str, value: object
) -> None:
    """Every nested cell scalar uses an exact JSON type and canonical date."""

    def mutate(payload: dict[str, object]) -> None:
        source_row_payload = payload["source_row"]
        assert isinstance(source_row_payload, dict)
        cells = source_row_payload["cells"]
        assert isinstance(cells, list)
        assert isinstance(cells[0], dict)
        cells[0][field] = value

    with pytest.raises(ValidationError, match="canonical SourceRow JSON shape"):
        FundAttributeRow.model_validate_json(_mutated_fund_json(mutate))


def test_fund_attribute_row_rejects_noncanonical_json_nested_lineage() -> None:
    """Canonical shape still cannot pair a source mutation with stale wrappers."""

    def mutate(payload: dict[str, object]) -> None:
        source_row_payload = payload["source_row"]
        assert isinstance(source_row_payload, dict)
        source_row_payload["source_sheet"] = "other"

    with pytest.raises(ValidationError):
        FundAttributeRow.model_validate_json(_mutated_fund_json(mutate))
