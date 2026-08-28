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
from finproof.data.normalization.public_funds import normalize_public_funds
from finproof.data.source_manifest import SourceFileManifest, VerifiedSourceSet
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.listed import ListedProductType
from finproof.domain.locators import SourceCellLocator
from finproof.domain.overseas_listed import OVERSEAS_FIELD_COLUMNS
from finproof.domain.public_funds import (
    FUND_ATTRIBUTE_FIELD_COLUMNS,
    FUND_ITEM_FIELD_COLUMNS,
    FundItem,
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

EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS = {
    "benchmark_english_name": "bmrk_eng_nm",
    "benchmark_name": "bmrk_nm",
    "currency": "curr_cd",
    "exchange_traded_flag_raw": "exchdg_yn",
    "establishment_country_code": "fd_estb_ctry_cd",
    "region_description": "fd_ivst_rgn_desc",
    "return_18m": "fd_mm18_ern_r",
    "return_1m": "fd_mm1_ern_r",
    "return_3m": "fd_mm3_ern_r",
    "return_6m": "fd_mm6_ern_r",
    "net_assets": "fd_nast_suma",
    "establishment_type_code": "fd_set_pcd",
    "return_1w": "fd_wk1_ern_r",
    "return_1y": "fd_yr1_ern_r",
    "return_2y": "fd_yr2_ern_r",
    "return_3y": "fd_yr3_ern_r",
    "return_5y": "fd_yr5_ern_r",
    "foreign_base_price_flag_raw": "frc_bpr_itm_yn",
    "fss_item_id": "fss_itm_no",
    "hedge_fund_flag_raw": "hdge_fd_yn",
    "interest_dividend_description": "int_dvd_desc",
    "short_name": "itm_abrv_nm",
    "english_short_name": "itm_eabrv_nm",
    "english_name": "itm_eng_nm",
    "name": "itm_nm",
    "fund_item_id": "itm_no",
    "kofia_classification_code": "kofia_fd_ccd",
    "ksd_id": "ksd_itm_no",
    "manager_item_id": "mtco_itm_no",
    "offshore_fund_flag_raw": "ofsfd_yn",
    "fund_type_raw": "or_attr_desc",
    "manager_external_code": "or_co_xtn_itt_cd",
    "overseas_fund_description": "ovrs_fd_desc",
    "investor_type_description": "pers_corp_desc",
    "professional_sale_control_code": "pfiv_sale_cntl_tcd",
    "attribute_code": "prfd_attr_cd",
    "private_fund_description": "prvo_fd_desc",
    "offering_type_description": "prvo_pbff_desc",
    "family_candidate_key": "rptt_ksd_itm_no",
    "sale_status_raw": "sale_yn",
    "standard_item_id": "std_itm_no",
    "mirae_sale_flag_raw": "thco_sale_yn",
    "trustee_external_code": "trusc_xtn_itt_cd",
    "risk_code": "zrin_fd_ivst_risk_gcd",
    "risk_name": "zrin_fd_ivst_risk_grd_nm",
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

    assert (source_rows, records, quarantines, len(product_ids)) == (
        6_037,
        6_037,
        0,
        6_037,
    )
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


def test_official_public_fund_normalization_and_collapse_preserve_grain_and_lineage(
    record_property: Callable[[str, object], None],
) -> None:
    source = _verified().data_file("PRFD01N001")
    assert dict(FUND_ATTRIBUTE_FIELD_COLUMNS) == EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS
    assert tuple(FUND_ATTRIBUTE_FIELD_COLUMNS.values()) == source.expected_headers
    assert dict(FUND_ITEM_FIELD_COLUMNS) == {
        field_name: column
        for field_name, column in EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS.items()
        if field_name != "attribute_code"
    }
    assert len(FUND_ITEM_FIELD_COLUMNS) == 44

    rows = tuple(iter_xlsx_rows(source))
    assert len(rows) == 95_619
    raw_item_ids = {row.cell("itm_no").raw_value for row in rows}
    raw_pairs = {(row.cell("itm_no").raw_value, row.cell("prfd_attr_cd").raw_value) for row in rows}
    normalized_pairs = {
        (row.cell("itm_no").raw_value, row.cell("prfd_attr_cd").raw_value.strip()) for row in rows
    }
    raw_attribute_codes = {row.cell("prfd_attr_cd").raw_value for row in rows}
    trimmed_attribute_codes = {raw.strip() for raw in raw_attribute_codes}
    padded_rows = sum(
        row.cell("prfd_attr_cd").raw_value != row.cell("prfd_attr_cd").raw_value.strip()
        for row in rows
    )
    literal_null_rows = sum(row.cell("zrin_fd_ivst_risk_gcd").raw_value == "NULL" for row in rows)
    type_06_rows = sum(row.cell("or_attr_desc").raw_value == "06" for row in rows)
    below_minus_100_cells = [
        (row.source_row_number, column)
        for row in rows
        for column in (
            "fd_mm18_ern_r",
            "fd_yr2_ern_r",
            "fd_yr3_ern_r",
            "fd_yr5_ern_r",
        )
        if row.cell(column).raw_value and Decimal(row.cell(column).raw_value) < Decimal("-100")
    ]
    etf_like_item_ids = {
        row.cell("itm_no").raw_value
        for row in rows
        if row.cell("itm_no").raw_value != '"'
        and ("ETF" in row.cell("itm_nm").raw_value or "상장지수" in row.cell("itm_nm").raw_value)
    }

    rss_before_native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started_at = perf_counter()
    result = normalize_public_funds(rows)
    wall_seconds = perf_counter() - started_at
    rss_after_native = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    multiplier = 1 if sys.platform == "darwin" else 1024
    record_property("normalization_wall_seconds", round(wall_seconds, 6))
    record_property("peak_rss_before_bytes", rss_before_native * multiplier)
    record_property("peak_rss_after_bytes", rss_after_native * multiplier)

    assert len(raw_item_ids) == 11_139
    assert len(raw_pairs) == 95_619
    assert len(normalized_pairs) == 95_619
    assert len(raw_attribute_codes) == len(trimmed_attribute_codes) == 228
    assert padded_rows == 1_670
    assert len(result.items) == 11_138
    assert len(result.attributes) == 95_618
    assert max(len(item.contributing_rows) for item in result.items) == 16

    item_by_id = {item.fund_item_id.representative.normalized_value: item for item in result.items}
    assert None not in item_by_id
    currencies = Counter(item.currency.representative.normalized_value for item in result.items)
    assert currencies == Counter({"KRW": 11_067, "USD": 71})
    assert literal_null_rows == 18_416
    assert (
        sum(
            item.risk_code.representative.quality_status is QualityStatus.MISSING_LITERAL_NULL
            for item in result.items
        )
        == 2_573
    )
    assert type_06_rows == 5_436
    assert (
        sum(
            item.fund_type_raw.representative.quality_status is QualityStatus.MIXED_SOURCE_VALUES
            for item in result.items
        )
        == 686
    )
    anomaly_rows = {302, 11_405, 41_701, 69_297, 86_745}
    anomaly_columns = {
        "fd_mm18_ern_r",
        "fd_yr2_ern_r",
        "fd_yr3_ern_r",
        "fd_yr5_ern_r",
    }
    assert set(below_minus_100_cells) == {
        (row_number, column) for row_number in anomaly_rows for column in anomaly_columns
    }
    assert {
        row.cell("itm_no").raw_value for row in rows if row.source_row_number in anomaly_rows
    } == {"KR515303001M"}
    assert {
        item_id
        for item_id, item in item_by_id.items()
        if any(
            getattr(item, field).representative.quality_status is QualityStatus.OUT_OF_DOMAIN
            for field in ("return_18m", "return_2y", "return_3y", "return_5y")
        )
    } == {"KR515303001M"}

    blockers = [issue for issue in result.issues if issue.quarantined]
    malformed = [issue for issue in blockers if issue.rule_id == "public_fund.malformed_item"]
    assert len(malformed) == 1
    assert malformed[0].source.source_row_number == 84_563
    assert malformed[0].source.source_column_name == "itm_no"
    assert malformed[0].quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert not any(
        issue.rule_id
        in {
            "public_fund.attribute_key.raw_duplicate",
            "public_fund.attribute_key.normalized_collision",
            "public_fund.item.non_attribute_disagreement",
        }
        for issue in result.issues
    )

    source_by_identity = {
        (row.source_file, row.source_sheet, row.source_row_number): row
        for row in rows
        if row.cell("itm_no").raw_value != '"'
    }
    seen_attribute_rows: set[tuple[object, ...]] = set()
    for item in result.items:
        assert tuple(row.source_row_number for row in item.contributing_rows) == tuple(
            sorted(row.source_row_number for row in item.contributing_rows)
        )
        for field_name, column in FUND_ITEM_FIELD_COLUMNS.items():
            value = getattr(item, field_name)
            expected = tuple(
                SourceCellLocator.from_row(row, column) for row in item.contributing_rows
            )
            assert value.equivalent_sources == expected
            assert (
                value.representative.raw_value == item.contributing_rows[0].cell(column).raw_value
            )
        for row in item.contributing_rows:
            identity = (row.source_file, row.source_sheet, row.source_row_number)
            assert source_by_identity[identity] is row

    for attribute in result.attributes:
        identity = (
            attribute.fund_item_id.source.source_file,
            attribute.fund_item_id.source.source_sheet,
            attribute.fund_item_id.source.source_row_number,
        )
        row = source_by_identity[identity]
        assert attribute.fund_item_id.raw_value == row.cell("itm_no").raw_value
        assert attribute.fund_item_id.normalized_value == row.cell("itm_no").raw_value
        assert attribute.fund_item_id.source == SourceCellLocator.from_row(row, "itm_no")
        assert attribute.attribute_code.raw_value == row.cell("prfd_attr_cd").raw_value
        assert (
            attribute.attribute_code.normalized_value == row.cell("prfd_attr_cd").raw_value.strip()
        )
        assert attribute.attribute_code.source == SourceCellLocator.from_row(row, "prfd_attr_cd")
        seen_attribute_rows.add(identity)
    assert len(seen_attribute_rows) == 95_618

    forbidden_fields = {
        "family",
        "family_candidate",
        "product_type",
        "saleable",
        "is_eligible_at_as_of",
    }
    assert forbidden_fields.isdisjoint(FundItem.model_fields)
    assert len(etf_like_item_ids) == 175
    assert etf_like_item_ids <= item_by_id.keys()

    selected_ids = {"KR5116450039", "KR5153450333"}
    canonical = tuple(
        sorted(
            (row for row in rows if row.cell("itm_no").raw_value in selected_ids),
            key=lambda row: row.source_row_number,
        )
    )
    assert Counter(row.cell("itm_no").raw_value for row in canonical) == Counter(
        {"KR5116450039": 16, "KR5153450333": 16}
    )
    orders = (
        canonical,
        canonical[::-1],
        canonical[0::2] + canonical[1::2],
        canonical[1::2] + canonical[0::2],
    )
    ordered_results = tuple(normalize_public_funds(order) for order in orders)
    expected_json = ordered_results[0].model_dump_json()
    assert all(value.model_dump_json() == expected_json for value in ordered_results)
    assert all((len(value.items), len(value.attributes)) == (2, 32) for value in ordered_results)
    expected_lineage = tuple(
        (
            item.fund_item_id.representative.normalized_value,
            tuple(row.source_row_number for row in item.contributing_rows),
            tuple(locator.source_row_number for locator in item.name.equivalent_sources),
        )
        for item in ordered_results[0].items
    )
    assert all(
        tuple(
            (
                item.fund_item_id.representative.normalized_value,
                tuple(row.source_row_number for row in item.contributing_rows),
                tuple(locator.source_row_number for locator in item.name.equivalent_sources),
            )
            for item in value.items
        )
        == expected_lineage
        for value in ordered_results
    )
