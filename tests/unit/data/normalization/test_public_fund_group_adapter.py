"""Regression: one refreshed source row maps directly to one fund item."""

import pytest

from finproof.data.normalization import public_funds
from tests.helpers.source_rows import source_row


def test_public_fund_group_adapter_and_classifier_are_retired() -> None:
    row = source_row("PRFD01N001")
    with pytest.raises(RuntimeError, match="retired"):
        public_funds.normalize_public_fund_item_group((row,))
    with pytest.raises(RuntimeError, match="retired"):
        public_funds.classify_public_fund_row(row)


def test_distinct_source_rows_cannot_be_grouped_into_one_product() -> None:
    records = tuple(
        public_funds.normalize_public_fund_item(
            source_row(
                "PRFD01N001",
                {"itm_no": item_id, "prfd_attr_cds": "A,A", "prfd_attr_cnt": "2"},
                excel_row=row_number,
            )
        ).record
        for item_id, row_number in (("KR5114601001", 2), ("KR5114601002", 3))
    )

    assert all(record is not None for record in records)
    assert tuple(record.fund_item_id.normalized_value for record in records if record) == (
        "KR5114601001",
        "KR5114601002",
    )
