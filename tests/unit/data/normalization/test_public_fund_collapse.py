"""Deterministic public-fund item-grain collapse tests."""

import json
from collections.abc import Iterator
from random import Random

import pytest
from pydantic import BaseModel, ValidationError

from finproof.data.normalization.public_funds import (
    collapse_fund_items,
    normalize_fund_attribute,
    normalize_public_funds,
)
from finproof.domain.locators import SourceCellLocator
from finproof.domain.public_funds import (
    FUND_ITEM_FIELD_COLUMNS,
    FundAttributeRow,
    FundCollapseResult,
    FundItem,
    FundItemAttribute,
)
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize("model", [FundItemAttribute, FundItem, FundCollapseResult])
def test_collapse_output_models_are_strict_frozen(model: type[BaseModel]) -> None:
    """Collapse records must reject mutation, coercion, and undeclared fields."""
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["strict"] is True


def _normalized(*rows: SourceRow) -> tuple[FundAttributeRow, ...]:
    records: list[FundAttributeRow] = []
    for row in rows:
        record = normalize_fund_attribute(row).record
        assert record is not None
        records.append(record)
    return tuple(records)


def _bounded_orders(rows: tuple[SourceRow, ...]) -> tuple[tuple[SourceRow, ...], ...]:
    canonical = rows
    grouped = tuple(
        sorted(
            canonical,
            key=lambda row: (
                row.cell("itm_no").raw_value,
                row.cell("prfd_attr_cd").raw_value.strip(),
                row.cell("prfd_attr_cd").raw_value,
                row.source_row_number,
            ),
        )
    )
    malformed = tuple(row for row in canonical if row.cell("itm_no").raw_value == '"')
    well_formed = tuple(row for row in canonical if row.cell("itm_no").raw_value != '"')
    orders = [
        canonical,
        canonical[::-1],
        canonical[0::2] + canonical[1::2],
        canonical[1::2] + canonical[0::2],
        grouped,
        malformed + well_formed,
        well_formed + malformed,
    ]
    rng = Random(20260814)  # noqa: S311 - fixed deterministic test permutations
    for _ in range(32):
        sample = list(canonical)
        rng.shuffle(sample)
        orders.append(tuple(sample))
    return tuple(orders)


def test_noncontiguous_rows_group_globally_to_one_complete_item_and_two_attributes() -> None:
    """Adjacent grouping would split one item and lose repeated evidence."""
    first = source_row("PRFD01N001", {"prfd_attr_cd": "B102"}, excel_row=9)
    other_item = source_row(
        "PRFD01N001",
        {"itm_no": "KR5114601002", "prfd_attr_cd": "C101"},
        excel_row=5,
    )
    lowest = source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2)

    result = collapse_fund_items(_normalized(first, other_item, lowest))

    assert [item.fund_item_id.representative.normalized_value for item in result.items] == [
        "KR5114601001",
        "KR5114601002",
    ]
    item = result.items[0]
    assert [row.source_row_number for row in item.contributing_rows] == [2, 9]
    assert item.contributing_rows[0] is lowest
    assert item.contributing_rows[1] is first
    assert [source.source_row_number for source in item.name.equivalent_sources] == [2, 9]
    assert item.name.representative.source.source_row_number == 2
    assert [
        (
            attribute.fund_item_id.normalized_value,
            attribute.attribute_code.normalized_value,
        )
        for attribute in result.attributes
    ] == [
        ("KR5114601001", "A101"),
        ("KR5114601001", "B102"),
        ("KR5114601002", "C101"),
    ]
    assert result.issues == ()


def test_valid_collapse_is_byte_identical_for_bounded_input_orders() -> None:
    """Input encounter order must not change item-grain JSON output."""
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "C102"}, excel_row=11),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=2),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601002", "prfd_attr_cd": "A100"},
            excel_row=7,
        ),
    )
    expected = normalize_public_funds(rows).model_dump_json()

    assert all(
        normalize_public_funds(order).model_dump_json() == expected
        for order in _bounded_orders(rows)
    )


def _two_row_result() -> FundCollapseResult:
    return normalize_public_funds(
        (
            source_row("PRFD01N001", {"prfd_attr_cd": "B101"}, excel_row=9),
            source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
        )
    )


def _item_payload(item: FundItem) -> dict[str, object]:
    return {name: getattr(item, name) for name in type(item).model_fields}


def test_collapse_preserves_every_sorted_input_source_row_by_identity() -> None:
    """Reconstructing contributing rows would sever the verified-reader identity."""
    high = source_row("PRFD01N001", {"prfd_attr_cd": "B101"}, excel_row=9)
    low = source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2)

    item = normalize_public_funds((high, low)).items[0]

    assert item.contributing_rows[0] is low
    assert item.contributing_rows[1] is high


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "reordered"])
def test_fund_item_rejects_incomplete_or_noncanonical_contributing_rows(
    mutation: str,
) -> None:
    """Rows must be nonempty, unique, and strictly increasing by Excel row."""
    item = _two_row_result().items[0]
    rows = item.contributing_rows
    replacements = {
        "empty": (),
        "duplicate": (rows[0], rows[0]),
        "reordered": rows[::-1],
    }

    with pytest.raises(ValidationError):
        FundItem.model_validate(_item_payload(item) | {"contributing_rows": replacements[mutation]})


def test_fund_item_rejects_missing_locator_and_nonlowest_representative() -> None:
    """Each field must preserve every row locator and the lowest-row representative."""
    item = _two_row_result().items[0]
    missing = item.name.model_copy(update={"equivalent_sources": item.name.equivalent_sources[:1]})
    second_name = normalize_fund_attribute(item.contributing_rows[1]).record
    assert second_name is not None
    nonlowest = item.name.model_copy(update={"representative": second_name.name})

    with pytest.raises(ValidationError):
        FundItem.model_validate(_item_payload(item) | {"name": missing})
    with pytest.raises(ValidationError):
        FundItem.model_validate(_item_payload(item) | {"name": nonlowest})


def test_fund_item_rejects_hidden_non_attribute_raw_disagreement() -> None:
    """Direct construction cannot hide a changed raw cell behind old item values."""
    item = _two_row_result().items[0]
    original = item.contributing_rows[1]
    cells = list(original.cells)
    name_index = next(index for index, cell in enumerate(cells) if cell.column_name == "itm_nm")
    cells[name_index] = cells[name_index].model_copy(update={"raw_value": "changed"})
    changed = SourceRow(
        **(
            original.model_dump(exclude={"cells", "raw_payload"})
            | {
                "cells": tuple(cells),
                "raw_payload": tuple(cell.raw_value for cell in cells),
            }
        )
    )

    with pytest.raises(ValidationError):
        FundItem.model_validate(
            _item_payload(item) | {"contributing_rows": (item.contributing_rows[0], changed)}
        )


def test_fund_item_rejects_noncanonical_python_row_before_required_cell_lookup() -> None:
    """A short exact SourceRow must become typed validation failure, not leak KeyError."""
    item = _two_row_result().items[0]
    complete = item.contributing_rows[0]
    first_cell = complete.cells[0]
    identity_only = SourceRow(
        source_table=complete.source_table,
        source_file=complete.source_file,
        source_sheet=complete.source_sheet,
        source_row_number=complete.source_row_number,
        source_checksum=complete.source_checksum,
        source_snapshot_date=complete.source_snapshot_date,
        raw_payload=(first_cell.raw_value,),
        cells=(first_cell,),
    )

    with pytest.raises(ValidationError, match="canonical column order"):
        FundItem.model_validate(_item_payload(item) | {"contributing_rows": (identity_only,)})


def test_fund_item_rejects_noncanonical_nested_source_row_json() -> None:
    """Each contributing row uses the same exact structural JSON boundary."""
    item = _two_row_result().items[0]
    payload = json.loads(item.model_dump_json())
    payload["contributing_rows"][1]["source_file"] = "data//file.xlsx"

    with pytest.raises(ValidationError, match="canonical SourceRow JSON shape"):
        FundItem.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source_row_number",), "9"),
        (("source_row_number",), True),
        (("source_snapshot_date",), "20260711"),
        (("cells", 0, "excel_column_number"), "1"),
        (("cells", 0, "excel_column_number"), True),
        (("cells", 0, "applicable_date"), "2026-7-1"),
    ],
)
def test_fund_item_rejects_noncanonical_nested_source_row_json_scalars(
    path: tuple[str | int, ...], value: object
) -> None:
    """Nested rows reject coercible scalars before Pydantic can normalize them."""
    payload = json.loads(_two_row_result().items[0].model_dump_json())
    row_payload = payload["contributing_rows"][1]
    assert isinstance(row_payload, dict)
    if len(path) == 1:
        row_key = path[0]
        assert isinstance(row_key, str)
        row_payload[row_key] = value
    else:
        cells = row_payload["cells"]
        assert isinstance(cells, list)
        cell_index = path[1]
        cell_key = path[2]
        assert isinstance(cell_index, int)
        assert isinstance(cell_key, str)
        cell = cells[cell_index]
        assert isinstance(cell, dict)
        cell[cell_key] = value

    with pytest.raises(ValidationError, match="canonical SourceRow JSON shape"):
        FundItem.model_validate_json(json.dumps(payload))


def test_result_round_trip_preserves_complete_item_attribute_relation() -> None:
    """A valid result round-trip retains every item, row, field locator, and attribute."""
    result = _two_row_result()
    encoded = result.model_dump_json()

    restored = FundCollapseResult.model_validate_json(encoded)

    assert restored == result
    assert restored.model_dump_json() == encoded


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered", "orphan"])
def test_result_rejects_incomplete_duplicate_reordered_or_orphan_attributes(
    mutation: str,
) -> None:
    """The sibling attribute relation must cover each contributing row exactly once."""
    result = _two_row_result()
    attributes = result.attributes
    orphan = normalize_public_funds(
        (
            source_row(
                "PRFD01N001",
                {"itm_no": "KR5114601002", "prfd_attr_cd": "Z999"},
                excel_row=20,
            ),
        )
    ).attributes[0]
    replacements = {
        "missing": attributes[:1],
        "duplicate": (*attributes, attributes[0]),
        "reordered": attributes[::-1],
        "orphan": (*attributes, orphan),
    }

    with pytest.raises(ValidationError):
        FundCollapseResult(
            items=result.items,
            attributes=replacements[mutation],
            issues=result.issues,
        )


def test_result_rejects_reordered_items() -> None:
    """Item order is the normalized identifier order, never caller order."""
    result = normalize_public_funds(
        (
            source_row(
                "PRFD01N001",
                {"itm_no": "KR5114601002", "prfd_attr_cd": "A101"},
                excel_row=9,
            ),
            source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
        )
    )

    with pytest.raises(ValidationError):
        FundCollapseResult(
            items=result.items[::-1],
            attributes=result.attributes,
            issues=result.issues,
        )


def test_result_rejects_duplicate_issue_ids() -> None:
    """A duplicated deterministic issue ID cannot appear twice in one result."""
    row = source_row("PRFD01N001", {"itm_no": '"'}, excel_row=17)
    issue = DataQualityIssue.from_row(
        row,
        "itm_no",
        rule_id="public_fund.malformed_item",
        rule_version="1.0.0",
        severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason="Public-fund item identifier has an invalid source format.",
        quarantined=True,
    )

    with pytest.raises(ValidationError):
        FundCollapseResult(items=(), attributes=(), issues=(issue, issue))


_COLLAPSE_REASONS = {
    "public_fund.attribute_key.raw_duplicate": (
        "Public-fund raw item-attribute key is duplicated."
    ),
    "public_fund.attribute_key.normalized_collision": (
        "Public-fund attribute values collide after normalization."
    ),
    "public_fund.item.non_attribute_disagreement": (
        "Public-fund non-attribute source values disagree within one item."
    ),
}


def _assert_collapse_issue(
    issue: DataQualityIssue,
    row: SourceRow,
    column_name: str,
    rule_id: str,
) -> None:
    expected = DataQualityIssue.from_row(
        row,
        column_name,
        rule_id=rule_id,
        rule_version="1.0.0",
        severity=IssueSeverity.HIGH,
        quality_status=QualityStatus.MIXED_SOURCE_VALUES,
        reason=_COLLAPSE_REASONS[rule_id],
        quarantined=True,
    )
    assert issue.rule_id == rule_id
    assert issue.rule_version == "1.0.0"
    assert issue.severity is IssueSeverity.HIGH
    assert issue.quality_status is QualityStatus.MIXED_SOURCE_VALUES
    assert issue.reason == _COLLAPSE_REASONS[rule_id]
    assert issue.quarantined is True
    assert issue.raw_payload_sha256 == expected.raw_payload_sha256
    assert issue.source == SourceCellLocator.from_row(row, column_name)
    assert issue.first_detected_at is None


def test_raw_duplicate_emits_one_issue_per_participating_cell_and_excludes_item() -> None:
    """A repeated exact primary-key pair has no authoritative participant."""
    rows = tuple(
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=row_number)
        for row_number in (2, 8, 11)
    )

    result = normalize_public_funds(rows)

    assert result.items == ()
    assert result.attributes == ()
    assert len(result.issues) == 3
    assert [issue.source.source_row_number for issue in result.issues] == [2, 8, 11]
    for issue, row in zip(result.issues, rows, strict=True):
        _assert_collapse_issue(
            issue,
            row,
            "prfd_attr_cd",
            "public_fund.attribute_key.raw_duplicate",
        )


def test_normalized_collision_emits_one_issue_per_distinct_raw_participant() -> None:
    """Padded and unpadded raw codes cannot silently merge after trimming."""
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=2),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA"}, excel_row=9),
    )

    result = normalize_public_funds(rows)

    assert result.items == ()
    assert result.attributes == ()
    assert len(result.issues) == 2
    for issue, row in zip(result.issues, rows, strict=True):
        _assert_collapse_issue(
            issue,
            row,
            "prfd_attr_cd",
            "public_fund.attribute_key.normalized_collision",
        )


def test_duplicate_raw_form_plus_trim_collision_has_additive_cardinality() -> None:
    """Independent duplicate and collision rules add rather than mask evidence."""
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=2),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA"}, excel_row=6),
        source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=9),
    )

    result = normalize_public_funds(rows)

    assert result.items == ()
    assert result.attributes == ()
    assert len(result.issues) == 5
    assert [issue.rule_id for issue in result.issues] == [
        "public_fund.attribute_key.normalized_collision",
        "public_fund.attribute_key.raw_duplicate",
        "public_fund.attribute_key.normalized_collision",
        "public_fund.attribute_key.normalized_collision",
        "public_fund.attribute_key.raw_duplicate",
    ]
    row_by_number = {row.source_row_number: row for row in rows}
    for issue in result.issues:
        _assert_collapse_issue(
            issue,
            row_by_number[issue.source.source_row_number],
            "prfd_attr_cd",
            issue.rule_id,
        )


def test_two_disagreeing_columns_emit_rows_times_columns_issues_and_exclude_group() -> None:
    """Every participant in every disagreeing column is retained as evidence."""
    rows = (
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "A101", "itm_nm": "A", "curr_cd": "KRW"},
            excel_row=2,
        ),
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "B101", "itm_nm": "B", "curr_cd": "USD"},
            excel_row=5,
        ),
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "C101", "itm_nm": "A", "curr_cd": "KRW"},
            excel_row=8,
        ),
    )

    result = normalize_public_funds(rows)
    collapse_issues = [
        issue
        for issue in result.issues
        if issue.rule_id == "public_fund.item.non_attribute_disagreement"
    ]

    assert result.items == ()
    assert result.attributes == ()
    assert len(collapse_issues) == 6
    assert {issue.source.source_column_name for issue in collapse_issues} == {
        "curr_cd",
        "itm_nm",
    }
    assert {issue.source.source_row_number for issue in collapse_issues} == {2, 5, 8}
    row_by_number = {row.source_row_number: row for row in rows}
    for issue in collapse_issues:
        _assert_collapse_issue(
            issue,
            row_by_number[issue.source.source_row_number],
            issue.source.source_column_name,
            "public_fund.item.non_attribute_disagreement",
        )


_NUMERIC_FUND_COLUMNS = frozenset(
    {
        "fd_mm18_ern_r",
        "fd_mm1_ern_r",
        "fd_mm3_ern_r",
        "fd_mm6_ern_r",
        "fd_nast_suma",
        "fd_wk1_ern_r",
        "fd_yr1_ern_r",
        "fd_yr2_ern_r",
        "fd_yr3_ern_r",
        "fd_yr5_ern_r",
    }
)
_DISAGREEMENT_COLUMNS = tuple(
    column_name for column_name in FUND_ITEM_FIELD_COLUMNS.values() if column_name != "itm_no"
)


@pytest.mark.parametrize("column_name", _DISAGREEMENT_COLUMNS)
def test_every_non_key_non_attribute_column_is_compared_by_exact_raw_value(
    column_name: str,
) -> None:
    """Omitting any one of the 43 payload columns would silently choose a value."""
    if column_name == "curr_cd":
        replacement = "USD"
    elif column_name in _NUMERIC_FUND_COLUMNS:
        replacement = "1"
    else:
        replacement = "changed"
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
        source_row(
            "PRFD01N001",
            {"prfd_attr_cd": "B101", column_name: replacement},
            excel_row=9,
        ),
    )

    result = normalize_public_funds(rows)
    collapse_issues = [
        issue
        for issue in result.issues
        if issue.rule_id == "public_fund.item.non_attribute_disagreement"
    ]

    assert result.items == ()
    assert result.attributes == ()
    assert len(collapse_issues) == 2
    assert [issue.source.source_column_name for issue in collapse_issues] == [
        column_name,
        column_name,
    ]
    for issue, row in zip(collapse_issues, rows, strict=True):
        _assert_collapse_issue(
            issue,
            row,
            column_name,
            "public_fund.item.non_attribute_disagreement",
        )


def _mixed_rows() -> tuple[SourceRow, ...]:
    return (
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601004", "prfd_attr_cd": "D001"},
            excel_row=40,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601001", "prfd_attr_cd": "B101"},
            excel_row=3,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": '"', "prfd_attr_cd": "해외"},
            excel_row=84_563,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601005", "prfd_attr_cd": "USA "},
            excel_row=51,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601002", "prfd_attr_cd": "A201", "or_attr_desc": "06"},
            excel_row=20,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601006", "prfd_attr_cd": "F001", "itm_nm": "B"},
            excel_row=61,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601003", "prfd_attr_cd": "A301", "fd_mm18_ern_r": "-100.01"},
            excel_row=30,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601004", "prfd_attr_cd": "D001"},
            excel_row=41,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601001", "prfd_attr_cd": "A101"},
            excel_row=2,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601005", "prfd_attr_cd": "USA"},
            excel_row=52,
        ),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601006", "prfd_attr_cd": "E001", "itm_nm": "A"},
            excel_row=60,
        ),
    )


def test_mixed_results_have_one_total_issue_order_and_bounded_order_bytes() -> None:
    """Row warnings, malformed keys, and collapse failures share one stable order."""
    rows = _mixed_rows()
    row_by_number = {row.source_row_number: row for row in rows}
    expected = normalize_public_funds(rows)
    expected_json = expected.model_dump_json()

    assert len(_bounded_orders(rows)) == 39
    assert all(
        normalize_public_funds(order).model_dump_json() == expected_json
        for order in _bounded_orders(rows)
    )
    assert [item.fund_item_id.representative.normalized_value for item in expected.items] == [
        "KR5114601001",
        "KR5114601002",
        "KR5114601003",
    ]
    assert len(expected.attributes) == 4
    assert len({issue.issue_id for issue in expected.issues}) == len(expected.issues)
    assert all(issue.first_detected_at is None for issue in expected.issues)

    def frozen_key(issue: DataQualityIssue) -> tuple[str, str, int, int, str, str]:
        row = row_by_number[issue.source.source_row_number]
        raw_item = row.cell("itm_no").raw_value
        normalized_item = raw_item if raw_item != '"' else ""
        quarantine_raw = raw_item if normalized_item == "" else ""
        return (
            normalized_item,
            quarantine_raw,
            issue.source.source_row_number,
            issue.source.source_column_number,
            issue.rule_id,
            issue.issue_id,
        )

    assert expected.issues == tuple(sorted(expected.issues, key=frozen_key))
    malformed = [
        issue for issue in expected.issues if issue.rule_id == "public_fund.malformed_item"
    ]
    assert len(malformed) == 1
    assert frozen_key(malformed[0])[:2] == ("", '"')
    assert all('"' not in issue.reason for issue in expected.issues)


def test_authoritative_path_propagates_iterator_failure_without_partial_result() -> None:
    """A failed source iterator must not be mistaken for a complete collapse."""

    def failing_rows() -> Iterator[SourceRow]:
        yield source_row("PRFD01N001", excel_row=2)
        raise RuntimeError("synthetic iterator failure")

    with pytest.raises(RuntimeError, match="synthetic iterator failure"):
        normalize_public_funds(failing_rows())
