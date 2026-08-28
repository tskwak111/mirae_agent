"""Regression: the superseded source-row collapse path stays retired."""

import pytest

from finproof.data.normalization import public_funds
from tests.helpers.source_rows import source_row


def test_public_fund_collapse_api_is_retired() -> None:
    row = source_row("PRFD01N001")
    for retired in (
        public_funds.collapse_fund_items,
        public_funds.normalize_public_funds,
        public_funds.normalize_fund_attribute,
    ):
        with pytest.raises(RuntimeError, match="retired"):
            retired((row,))


def test_comma_list_duplicates_remain_one_item_property() -> None:
    result = public_funds.normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {"prfd_attr_cds": "opaque,opaque,X?", "prfd_attr_cnt": "3"},
        )
    )

    assert result.record is not None
    assert result.record.attribute_codes == ("opaque", "opaque", "X?")
    assert "attributes" not in result.__class__.model_fields


def test_noncontiguous_rows_group_globally_to_one_complete_item_and_two_attributes() -> None:
    """Retain the critical-regression import while proving the refreshed equivalent."""
    result = public_funds.normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {"prfd_attr_cds": "A101,B102", "prfd_attr_cnt": "2"},
            excel_row=9,
        )
    )

    assert result.record is not None
    assert result.record.attribute_codes == ("A101", "B102")
    assert "contributing_rows" not in result.record.__class__.model_fields
