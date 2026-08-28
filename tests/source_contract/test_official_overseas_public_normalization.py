"""Official exhaustive acceptance for overseas and public-fund normalization."""

import resource
import sys
from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest

from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from finproof.data.normalization.public_funds import normalize_public_fund_item
from finproof.data.source_manifest import SourceFileManifest, VerifiedSourceSet
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.listed import ListedProductType
from finproof.domain.locators import SourceCellLocator
from finproof.domain.overseas_listed import OVERSEAS_FIELD_COLUMNS
from finproof.domain.public_funds import (
    PUBLIC_FUND_FIELD_COLUMNS,
    PUBLIC_FUND_SOURCE_COLUMNS,
    FundItem,
    PublicFundItem,
)
from finproof.domain.quality import QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

ROOT = Path(__file__).resolve().parents[2]
pytestmark = [
    pytest.mark.source_contract,
    pytest.mark.slow,
    pytest.mark.filterwarnings(
        "ignore:record_property is incompatible with junit_family 'xunit2':pytest.PytestWarning"
    ),
]

EXPECTED_OVERSEAS_FIELD_COLUMNS = {
    "base_index": "cu_base_index",
    "total_fee": "cu_charge_rt",
    "etn_flag_raw": "cu_etn_yn",
    "manager": "cu_fund_mgmt_co",
    "replication_method": "cu_index_repl_mthd",
    "index_tracking_flag_raw": "cu_index_tracking_yn",
    "inverse_short_flag_raw": "cu_inverse_short_yn",
    "leverage_factor": "cu_lev_fector",
    "strategy": "cu_strtegy",
    "custom_update_date": "cu_upt_dt",
    "daily_base_date_match_raw": "du_base_dt_match_yn",
    "daily_bid_price": "du_bpr",
    "close_price": "du_clpr",
    "close_price_base_date": "du_clpr_base_dt",
    "daily_close_source": "du_clpr_src",
    "difference_rate_raw_metric": "du_diff_rt",
    "return_1d": "du_er_1d",
    "daily_high_price": "du_hpr",
    "aum": "du_last_aum",
    "last_nav": "du_last_nav",
    "daily_low_price": "du_lpr",
    "nav_base_date": "du_nav_base_dt",
    "daily_open_price": "du_opr",
    "daily_update_date": "du_upt_dt",
    "daily_value": "du_val_1d",
    "daily_volume": "du_vol_1d",
    "ticker": "pd_abrv_nm",
    "source_currency_raw": "pd_curr_cd",
    "exchange_market_code": "pd_exg_mkt_cd",
    "product_type": "pd_grp_no",
    "isin": "pd_isin_cd",
    "product_id": "pd_itm_no",
    "market_identifier": "pd_itm_no_ma",
    "lipper_id": "pd_lipper_id",
    "listing_date": "pd_lstg_dt",
    "listing_price": "pd_lst_price",
    "listed_share_count": "pd_lst_stk_cnt",
    "market_code": "pd_mkt_id",
    "name": "pd_nm",
    "sale_flag_raw": "pd_sale_yn",
    "trading_currency": "pd_trd_ccy",
    "suspension_flag_raw": "pd_tr_yn",
    "us_cik": "pd_us_cik",
    "realtime_market_price": "ru_mkt_price",
    "realtime_market_volume": "ru_mkt_volume",
    "core_flag_raw": "wu_core_yn",
    "asset_type": "wu_inv_ast_type",
    "region": "wu_inv_rgn",
    "weekly_update_date": "wu_upt_dt",
}


def _verified() -> VerifiedSourceSet:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    return manifest.verify(ROOT / "source_material")


def _assert_wrapper_matches_row(wrapped: NormalizedValue[Any], row: SourceRow, column: str) -> None:
    assert wrapped.raw_value == row.cell(column).raw_value
    assert wrapped.source == SourceCellLocator.from_row(row, column)


def test_official_overseas_normalization_exhausts_all_rows_and_preserves_all_fields() -> None:
    source = _verified().data_file("PREF02N001")
    assert dict(OVERSEAS_FIELD_COLUMNS) == EXPECTED_OVERSEAS_FIELD_COLUMNS
    assert tuple(OVERSEAS_FIELD_COLUMNS.values()) == source.expected_headers

    source_rows = records = quarantines = 0
    product_ids: set[str] = set()
    groups: Counter[ListedProductType] = Counter()
    currency = fee_zero = fee_positive = 0
    source_currency: Counter[str | None] = Counter()
    return_blank = return_zero = 0
    aum_blank = aum_zero = aum_positive = 0
    core_nonblank: Counter[str] = Counter()
    replication_nonblank = listing_sentinel = sale_blank = trade_blank = 0

    for row in iter_xlsx_rows(source):
        source_rows += 1
        result = normalize_overseas_listed(row)
        quarantines += result.record is None
        assert result.record is not None
        records += 1
        record = result.record
        product_id = record.product_id.normalized_value
        assert product_id is not None
        assert product_id not in product_ids
        product_ids.add(product_id)
        product_type = record.product_type.normalized_value
        assert product_type is not None
        groups[product_type] += 1
        for field_name, column in OVERSEAS_FIELD_COLUMNS.items():
            _assert_wrapper_matches_row(getattr(record, field_name), row, column)

        currency += record.trading_currency.normalized_value == "USD"
        source_currency[record.source_currency_raw.normalized_value] += 1
        fee_zero += record.total_fee.quality_status is QualityStatus.RECORDED_ZERO
        fee_positive += (record.total_fee.normalized_value or Decimal(0)) > 0
        return_blank += record.return_1d.quality_status is QualityStatus.MISSING_BLANK
        return_zero += record.return_1d.quality_status is QualityStatus.RECORDED_ZERO
        aum_blank += record.aum.quality_status is QualityStatus.MISSING_BLANK
        aum_zero += record.aum.quality_status is QualityStatus.RECORDED_ZERO
        aum_positive += (record.aum.normalized_value or Decimal(0)) > 0
        for name in ("base_index", "manager", "strategy", "asset_type", "region"):
            core_nonblank[name] += getattr(record, name).normalized_value is not None
        replication_nonblank += record.replication_method.normalized_value is not None
        listing_sentinel += record.listing_date.quality_status is QualityStatus.SENTINEL_ZERO
        sale_blank += record.sale_flag_raw.quality_status is QualityStatus.MISSING_BLANK
        trade_blank += record.suspension_flag_raw.quality_status is QualityStatus.MISSING_BLANK
        assert record.return_1d.quality_status is not QualityStatus.CONSTANT_METRIC
        assert "return_1y" not in record.__class__.model_fields

    assert (source_rows, records, quarantines, len(product_ids)) == (6_037, 6_037, 0, 6_037)
    assert groups == Counter({ListedProductType.ETF: 5_972, ListedProductType.ETN: 65})
    assert currency == 6_037
    assert source_currency == Counter({"USD": 6_025, None: 11, "INR": 1})
    assert (fee_zero, fee_positive) == (419, 5_618)
    assert (return_zero, return_blank) == (125, 14)
    assert (aum_positive, aum_zero, aum_blank) == (5_821, 11, 205)
    assert core_nonblank == Counter(
        {
            "base_index": 6_026,
            "manager": 6_025,
            "strategy": 6_026,
            "asset_type": 6_026,
            "region": 6_026,
        }
    )
    assert replication_nonblank == 2_407
    assert listing_sentinel == 11
    assert (sale_blank, trade_blank) == (14, 14)


def test_official_public_fund_rows_map_one_to_one_with_item_attributes(
    record_property: Callable[[str, object], None],
) -> None:
    source = _verified().data_file("PRFD01N001")
    assert source.expected_headers == PUBLIC_FUND_SOURCE_COLUMNS
    assert FundItem is PublicFundItem

    source_rows = records = quarantines = empty_lists = token_count = 0
    item_ids: set[str] = set()
    max_attribute_count = 0
    issue_rules: Counter[str] = Counter()
    rss_before_native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started_at = perf_counter()

    for row in iter_xlsx_rows(source):
        source_rows += 1
        result = normalize_public_fund_item(row)
        issue_rules.update(issue.rule_id for issue in result.issues)
        if result.record is None:
            quarantines += 1
            continue
        records += 1
        record = result.record
        assert record.source_row is row
        item_id = record.fund_item_id.normalized_value
        assert item_id is not None
        assert item_id not in item_ids
        item_ids.add(item_id)

        raw_codes = row.cell("prfd_attr_cds").raw_value
        expected_codes = () if raw_codes == "" else tuple(raw_codes.split(","))
        assert record.attribute_codes == expected_codes
        assert record.attribute_count.normalized_value == len(expected_codes)
        assert record.attribute_count.source == SourceCellLocator.from_row(row, "prfd_attr_cnt")
        assert record.attribute_search_text.source == SourceCellLocator.from_row(
            row, "prfd_attr_search_text"
        )
        empty_lists += not expected_codes
        token_count += len(expected_codes)
        max_attribute_count = max(max_attribute_count, len(expected_codes))
        for field_name, column in PUBLIC_FUND_FIELD_COLUMNS.items():
            _assert_wrapper_matches_row(getattr(record, field_name), row, column)

    wall_seconds = perf_counter() - started_at
    rss_after_native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    multiplier = 1 if sys.platform == "darwin" else 1024
    record_property("normalization_wall_seconds", round(wall_seconds, 6))
    record_property("peak_rss_before_bytes", rss_before_native * multiplier)
    record_property("peak_rss_after_bytes", rss_after_native * multiplier)

    assert (source_rows, records, quarantines, len(item_ids)) == (
        23_676,
        23_676,
        0,
        23_676,
    )
    assert (empty_lists, token_count, max_attribute_count) == (12_396, 96_720, 16)
    assert "public_fund.attribute_count_mismatch" not in issue_rules
    assert {"attributes", "attribute_rows", "contributing_rows"}.isdisjoint(
        PublicFundItem.model_fields
    )
