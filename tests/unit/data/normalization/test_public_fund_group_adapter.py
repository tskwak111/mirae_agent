"""Focused contracts for one-group public-fund normalization."""

from collections.abc import Sequence

import pytest

import finproof.data.normalization.public_funds as public_funds
from finproof.data.normalization.public_funds import (
    classify_public_fund_row,
    normalize_public_fund_item_group,
    normalize_public_funds,
)
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import source_row


@pytest.mark.parametrize(
    ("item", "attribute", "expected_key", "rule_id"),
    [
        pytest.param("KR5114601001", " USA ", "KR5114601001", None, id="valid"),
        pytest.param('"', "USA", None, "public_fund.malformed_item", id="malformed-item"),
        pytest.param(
            "KR5114601001",
            " ",
            "KR5114601001",
            "public_fund.malformed_attribute",
            id="malformed-attribute",
        ),
    ],
)
def test_public_fund_row_classifier_matches_authoritative_valid_and_malformed_keys(
    monkeypatch: pytest.MonkeyPatch,
    item: str,
    attribute: str,
    expected_key: str | None,
    rule_id: str | None,
) -> None:
    row = source_row(
        "PRFD01N001",
        {"itm_no": item, "prfd_attr_cd": attribute},
        excel_row=7,
    )

    def forbidden_normalizer(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("classifier must not perform attribute normalization")

    monkeypatch.setattr(public_funds, "normalize_fund_attribute", forbidden_normalizer)
    classification = classify_public_fund_row(row)

    assert classification.item_key == expected_key
    if rule_id is None:
        assert classification.issue is None
    else:
        assert classification.issue is not None
        assert classification.issue.rule_id == rule_id
        assert classification.issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW


def test_public_fund_group_adapter_matches_global_collapse_for_order_variants() -> None:
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "C102"}, excel_row=11),
        source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
        source_row("PRFD01N001", {"prfd_attr_cd": "B101"}, excel_row=7),
    )
    orders = (rows, rows[::-1], rows[::2] + rows[1::2], rows[1::2] + rows[::2])

    for order in orders:
        ordered_group = tuple(sorted(order, key=lambda row: row.source_row_number))
        assert normalize_public_fund_item_group(ordered_group) == normalize_public_funds(order)


def test_public_fund_group_adapter_calls_attribute_normalizer_exactly_once_per_valid_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
        source_row("PRFD01N001", {"prfd_attr_cd": "B101"}, excel_row=7),
    )
    original = public_funds.normalize_fund_attribute
    calls: list[object] = []

    def counted(row: SourceRow) -> object:
        calls.append(row)
        return original(row)

    monkeypatch.setattr(public_funds, "normalize_fund_attribute", counted)

    normalize_public_fund_item_group(rows)

    assert calls == list(rows)


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param((), id="empty"),
        pytest.param(
            (
                source_row("PRFD01N001", {"itm_no": "KR5114601001"}, excel_row=2),
                source_row("PRFD01N001", {"itm_no": "KR5114601002"}, excel_row=3),
            ),
            id="multiple-items",
        ),
        pytest.param(
            (
                source_row("PRFD01N001", {"prfd_attr_cd": "B101"}, excel_row=7),
                source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
            ),
            id="unsorted",
        ),
        pytest.param(
            (
                source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
                source_row("PRFD01N001", {"prfd_attr_cd": "B101"}, excel_row=2),
            ),
            id="duplicate-location",
        ),
        pytest.param(
            (source_row("PRFD01N001", {"itm_no": '"'}, excel_row=2),),
            id="malformed-key",
        ),
    ],
)
def test_public_fund_group_adapter_rejects_invalid_group_shapes_before_normalization(
    monkeypatch: pytest.MonkeyPatch,
    rows: tuple[object, ...],
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("invalid group reached attribute normalization")

    monkeypatch.setattr(public_funds, "normalize_fund_attribute", forbidden)

    with pytest.raises(ValueError, match="invalid public-fund item group"):
        normalize_public_fund_item_group(rows)  # type: ignore[arg-type]


def test_global_public_fund_normalizer_reuses_classifier_and_group_adapter_without_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = (
        source_row("PRFD01N001", {"prfd_attr_cd": "B101"}, excel_row=7),
        source_row(
            "PRFD01N001",
            {"itm_no": "KR5114601002", "prfd_attr_cd": "A101"},
            excel_row=4,
        ),
        source_row("PRFD01N001", {"prfd_attr_cd": "A101"}, excel_row=2),
        source_row("PRFD01N001", {"itm_no": '"'}, excel_row=9),
    )
    expected = normalize_public_funds(rows)
    original_classifier = public_funds.classify_public_fund_row
    original_adapter = public_funds.normalize_public_fund_item_group
    classified: list[object] = []
    adapted: list[tuple[int, ...]] = []

    def counted_classifier(row: SourceRow) -> object:
        classified.append(row)
        return original_classifier(row)

    def counted_adapter(group: Sequence[SourceRow]) -> object:
        group_tuple: tuple[SourceRow, ...] = tuple(group)
        adapted.append(tuple(row.source_row_number for row in group_tuple))
        return original_adapter(group_tuple)

    monkeypatch.setattr(public_funds, "classify_public_fund_row", counted_classifier)
    monkeypatch.setattr(public_funds, "normalize_public_fund_item_group", counted_adapter)

    actual = normalize_public_funds(iter(rows))

    assert actual == expected
    assert classified == [*rows, rows[2], rows[0], rows[1]]
    assert adapted == [(2, 7), (4,)]
