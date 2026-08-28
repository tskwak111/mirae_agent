from collections.abc import MutableMapping
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.domain import domestic_listed as domestic_listed_contract
from finproof.domain.domestic_listed import ListedProduct, ListedProductType
from finproof.domain.quality import IssueSeverity, QualityStatus
from tests.helpers.source_rows import DOMESTIC_LISTED_COLUMNS, source_row

AS_OF = date(2026, 8, 22)

EXPECTED_FIELD_COLUMNS = {
    "base_index": "cu_base_index",
    "other_fee": "cu_charge_etc_rt",
    "total_fee": "cu_charge_rt",
    "manager": "cu_fund_mgmt_co",
    "leverage_factor": "cu_lev_fector",
    "strategy": "cu_strtegy",
    "custom_update_date": "cu_upt_dt",
    "daily_bid_price": "du_bpr",
    "tracking_error": "du_chas_errt",
    "tracking_error_base_date": "du_chas_errt_base_dt",
    "close_price": "du_clpr",
    "difference_rate": "du_diff_rt",
    "difference_rate_base_date": "du_diff_rt_base_dt",
    "return_1d": "du_er_1d",
    "return_1m": "du_er_1m",
    "return_1y": "du_er_1y",
    "return_3m": "du_er_3m",
    "return_6m": "du_er_6m",
    "return_ytd": "du_er_ytd",
    "daily_high_price": "du_hpr",
    "aum_secondary": "du_last_aum",
    "last_nav": "du_last_nav",
    "daily_low_price": "du_lpr",
    "nav_base_date": "du_nav_base_dt",
    "nav_change_amount": "du_nav_rnf_amt",
    "previous_nav": "du_nav_yday",
    "daily_update_date": "du_upt_dt",
    "daily_value": "du_val_1d",
    "daily_value_1m": "du_val_1m",
    "daily_value_5d": "du_val_5d",
    "volatility_1m": "du_vlty_1m",
    "volatility_1y": "du_vlty_1y",
    "volatility_3m": "du_vlty_3m",
    "volatility_6m": "du_vlty_6m",
    "volatility_base_date": "du_vlty_base_dt",
    "daily_volume": "du_vol_1d",
    "average_volume_1m": "du_vol_avg_1m",
    "average_volume_5d": "du_vol_avg_5d",
    "average_coupon": "fn_average_coupon",
    "average_maturity": "fn_average_maturity",
    "average_quality": "fn_average_quality",
    "fundamentals_base_date": "fn_base_dt",
    "effective_duration": "fn_effective_duration",
    "effective_maturity": "fn_effective_maturity",
    "modified_duration": "fn_modified_duration",
    "nominal_maturity": "fn_nominal_maturity",
    "portfolio_date": "fn_portfolio_dt",
    "short_name": "pd_abrv_nm",
    "circulating_net_assets": "pd_circ_net_tamt",
    "circulating_share_count": "pd_circ_stk_cnt",
    "currency": "pd_curr_cd",
    "currency_name": "pd_curr_nm",
    "annual_distribution_amount": "pd_divd_amt_ann",
    "distribution_per_share": "pd_divd_amt_pshr",
    "distribution_base_date": "pd_dvid_base_dt",
    "distribution_cycle": "pd_dvid_cycl",
    "distribution_income": "pd_dvid_inc_dist",
    "distribution_nav": "pd_dvid_nav",
    "distribution_pay_count": "pd_dvid_pay_cnt",
    "distribution_pay_months": "pd_dvid_pay_months",
    "distribution_price_base_date": "pd_dvid_prc_base_dt",
    "distribution_tax_basis": "pd_dvid_tax_basis",
    "distribution_yield": "pd_dvid_yield",
    "exchange_market_code": "pd_exg_mkt_cd",
    "exchange_market_name": "pd_exg_mkt_nm",
    "product_type": "pd_grp_no",
    "isin": "pd_isin_cd",
    "product_id": "pd_itm_no",
    "market_identifier": "pd_itm_no_ma",
    "listed_share_count": "pd_lst_stk_cnt",
    "listing_end_date": "pd_lste_dt",
    "listing_date": "pd_lstg_dt",
    "market_code": "pd_mkt_id",
    "market_name": "pd_mkt_nm",
    "aum_primary": "pd_net_tamt",
    "name": "pd_nm",
    "pension_risk_name": "pd_pen_risk_nm",
    "pension_trade_flag_raw": "pd_pen_tr_yn",
    "ric": "pd_ric",
    "risk_code": "pd_risk_cd",
    "risk_name": "pd_risk_nm",
    "sale_flag": "pd_sale_yn",
    "sector_code": "pd_sect_cd",
    "spac_flag_raw": "pd_spac_yn",
    "share_count": "pd_stk_cnt",
    "ticker": "pd_ticker",
    "suspension_flag": "pd_tr_yn",
    "ref_asset_type": "ref_ast_type",
    "ref_base_date": "ref_base_dt",
    "ref_base_index": "ref_base_index",
    "ref_manager": "ref_fund_mgmt_co",
    "ref_region": "ref_geo_focus",
    "realtime_market_price": "ru_mkt_price",
    "realtime_market_volume": "ru_mkt_volume",
    "core_flag_raw": "wu_core_yn",
    "asset_type": "wu_inv_ast_type",
    "region": "wu_inv_rgn",
    "weekly_update_date": "wu_upt_dt",
}


def test_domestic_listed_rejects_wrong_source_table_as_programmer_error() -> None:
    with pytest.raises(NormalizationContractError, match="PREF01N001"):
        normalize_domestic_listed(source_row("PRBD01N001"), AS_OF)


def test_domestic_listed_model_is_explicitly_frozen_forbid_and_strict() -> None:
    assert ListedProduct.model_config["frozen"] is True
    assert ListedProduct.model_config["extra"] == "forbid"
    assert ListedProduct.model_config["strict"] is True


@pytest.mark.parametrize(
    ("group", "product_type"),
    [("ETF", ListedProductType.ETF), ("ETN", ListedProductType.ETN)],
)
def test_domestic_listed_keeps_etf_and_etn_distinct(
    group: str, product_type: ListedProductType
) -> None:
    result = normalize_domestic_listed(source_row("PREF01N001", {"pd_grp_no": group}), AS_OF)
    assert result.record is not None
    assert result.record.grain == "listed_product"
    assert result.record.product_type.normalized_value is product_type


def test_domestic_listed_shared_type_keeps_existing_json_round_trip() -> None:
    """Moving the enum must not change the Task 3 model's JSON contract."""
    record = normalize_domestic_listed(source_row("PREF01N001"), AS_OF).record
    assert record is not None

    restored = ListedProduct.model_validate_json(record.model_dump_json())

    assert restored == record
    assert restored.product_type.normalized_value is ListedProductType.ETF


def test_valid_domestic_listed_maps_all_98_refreshed_columns() -> None:
    values = {
        "pd_itm_no": "KR7000000001",
        "pd_itm_no_ma": "A000001",
        "pd_grp_no": "ETF",
        "pd_nm": "상품명",
        "pd_abrv_nm": "단축명",
        "pd_curr_cd": "CURR_CD_KRW",
        "pd_lstg_dt": "20200101",
        "pd_lste_dt": "99991231",
        "pd_sale_yn": "1",
        "pd_tr_yn": "0",
        "pd_net_tamt": "100",
        "du_last_aum": "90",
        "cu_charge_rt": "0.1",
        "du_chas_errt": "0.2",
        "du_diff_rt": "0.3",
        "du_er_1d": "1",
        "du_er_1m": "2",
        "du_er_3m": "3",
        "du_er_6m": "4",
        "du_er_1y": "5",
        "du_er_ytd": "6",
        "pd_risk_cd": "2",
        "pd_risk_nm": "위험",
        "cu_base_index": "지수",
        "cu_fund_mgmt_co": "운용사",
        "wu_inv_ast_type": "주식",
        "wu_inv_rgn": "한국",
        "cu_upt_dt": "20260709",
        "du_upt_dt": "20260710",
        "wu_upt_dt": "20260708",
    }
    row = source_row("PREF01N001", values)
    record = normalize_domestic_listed(row, AS_OF).record
    assert record is not None
    field_columns = domestic_listed_contract.DOMESTIC_FIELD_COLUMNS
    assert dict(field_columns) == EXPECTED_FIELD_COLUMNS
    assert tuple(field_columns.values()) == DOMESTIC_LISTED_COLUMNS
    assert len(field_columns) == len(set(field_columns.values())) == 98
    mutable_view = cast(MutableMapping[str, str], field_columns)
    with pytest.raises(TypeError):
        mutable_view["product_id"] = "pd_itm_no_ma"
    for attribute, column in EXPECTED_FIELD_COLUMNS.items():
        wrapped = getattr(record, attribute)
        cell = row.cell(column)
        assert wrapped.raw_value == cell.raw_value
        assert wrapped.source.source_table == "PREF01N001"
        assert wrapped.source.source_file == row.source_file
        assert wrapped.source.source_sheet == row.source_sheet
        assert wrapped.source.source_row_number == row.source_row_number
        assert wrapped.source.source_column_name == column
        assert wrapped.source.source_column_number == cell.excel_column_number
        assert wrapped.source.source_column_letter == cell.excel_column_letter
        assert wrapped.source.source_checksum == row.source_checksum
        assert wrapped.source.source_snapshot_date == row.source_snapshot_date
        assert wrapped.source.source_applicable_date == cell.applicable_date
    assert record.currency.normalized_value == "KRW"
    assert record.sale_flag.normalized_value is True
    assert record.suspension_flag.normalized_value is False
    assert record.is_eligible_at_as_of.value is True
    assert record.is_eligible_at_as_of.quality_status is QualityStatus.VALID
    assert record.is_eligible_at_as_of.as_of_date == AS_OF
    assert tuple(locator.source_column_name for locator in record.is_eligible_at_as_of.inputs) == (
        "pd_sale_yn",
        "pd_tr_yn",
        "pd_lstg_dt",
        "pd_lste_dt",
    )


def test_valid_domestic_listed_zero_policy_is_field_specific() -> None:
    record = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "cu_charge_rt": "0",
                "du_chas_errt": "0",
                "du_diff_rt": "0",
                "pd_net_tamt": "0",
                "du_last_aum": "0",
                "du_er_1d": "0",
                "du_er_1m": "0",
                "du_er_3m": "0",
                "du_er_6m": "0",
                "du_er_1y": "0",
                "du_er_ytd": "0",
            },
        ),
        AS_OF,
    ).record
    assert record is not None
    assert record.total_fee.quality_status is QualityStatus.RECORDED_ZERO
    assert record.tracking_error.quality_status is QualityStatus.RECORDED_ZERO
    assert record.difference_rate.quality_status is QualityStatus.RECORDED_ZERO
    ordinary_zeroes = (
        record.aum_primary,
        record.aum_secondary,
        record.tracking_error,
        record.difference_rate,
        record.return_1d,
        record.return_1m,
        record.return_3m,
        record.return_6m,
        record.return_1y,
        record.return_ytd,
    )
    assert all(wrapped.quality_status is QualityStatus.RECORDED_ZERO for wrapped in ordinary_zeroes)
    assert all(
        wrapped.quality_status is not QualityStatus.CONSTANT_METRIC
        for wrapped in (record.total_fee, *ordinary_zeroes)
    )


def test_domestic_primary_aum_is_never_backfilled_from_secondary() -> None:
    record = normalize_domestic_listed(
        source_row("PREF01N001", {"pd_net_tamt": "", "du_last_aum": "123.45"}),
        AS_OF,
    ).record
    assert record is not None
    assert record.aum_primary.raw_value == ""
    assert record.aum_primary.normalized_value is None
    assert record.aum_primary.quality_status is QualityStatus.MISSING_BLANK
    assert record.aum_secondary.normalized_value == Decimal("123.45")


@pytest.mark.parametrize(
    ("values", "column"),
    [
        ({"pd_itm_no": "KR"}, "pd_itm_no"),
        ({"pd_itm_no": " kr7000000001"}, "pd_itm_no"),
        ({"pd_grp_no": "etf"}, "pd_grp_no"),
        ({"pd_grp_no": "FUND"}, "pd_grp_no"),
        ({"pd_grp_no": ""}, "pd_grp_no"),
    ],
)
def test_malformed_listed_identity_or_type_quarantines_one_row(
    values: dict[str, str], column: str
) -> None:
    row = source_row("PREF01N001", values, excel_row=1155)
    result = normalize_domestic_listed(row, AS_OF)
    assert result.record is None
    assert any(
        issue.quarantined
        and issue.severity is IssueSeverity.BLOCKER
        and issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
        and issue.source.source_column_name == column
        and issue.source.source_row_number == 1155
        for issue in result.issues
    )
    assert all(
        value not in issue.reason for value in values.values() if value for issue in result.issues
    )


def test_simultaneous_invalid_type_and_identity_emit_ordered_safe_blockers() -> None:
    result = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {"pd_grp_no": "FUND", "pd_itm_no": "KR"},
            excel_row=1155,
        ),
        AS_OF,
    )

    assert result.record is None
    assert len(result.issues) == 2
    assert tuple(issue.source.source_column_name for issue in result.issues) == (
        "pd_grp_no",
        "pd_itm_no",
    )
    assert tuple(issue.source.source_column_number for issue in result.issues) == (66, 68)
    assert all(
        issue.quarantined
        and issue.severity is IssueSeverity.BLOCKER
        and issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
        for issue in result.issues
    )
    assert tuple(issue.reason for issue in result.issues) == (
        "Domestic listed product group has an invalid source format.",
        "Domestic listed product identifier has an invalid source format.",
    )


@pytest.mark.parametrize(
    ("sale", "suspended", "expected_sale", "expected_suspended"),
    [
        ("1", "0", True, False),
        ("0", "1", False, True),
        ("", "", None, None),
        ("Y", "N", None, None),
        ("true", "false", None, None),
    ],
)
def test_domestic_flags_use_only_exact_source_codes(
    sale: str,
    suspended: str,
    expected_sale: bool | None,
    expected_suspended: bool | None,
) -> None:
    result = normalize_domestic_listed(
        source_row("PREF01N001", {"pd_sale_yn": sale, "pd_tr_yn": suspended}),
        AS_OF,
    )
    assert result.record is not None
    assert result.record.sale_flag.normalized_value is expected_sale
    assert result.record.suspension_flag.normalized_value is expected_suspended
    expected_warnings = sum(
        value is None and raw != ""
        for raw, value in ((sale, expected_sale), (suspended, expected_suspended))
    )
    assert (
        sum(
            issue.source.source_column_name in {"pd_sale_yn", "pd_tr_yn"} for issue in result.issues
        )
        == expected_warnings
    )


@pytest.mark.parametrize(
    ("column", "field_name"),
    [("pd_sale_yn", "sale_flag"), ("pd_tr_yn", "suspension_flag")],
)
def test_blank_domestic_flag_is_missing_without_warning_and_makes_eligibility_unavailable(
    column: str,
    field_name: str,
) -> None:
    result = normalize_domestic_listed(source_row("PREF01N001", {column: ""}), AS_OF)

    assert result.record is not None
    wrapped = getattr(result.record, field_name)
    assert wrapped.raw_value == ""
    assert wrapped.normalized_value is None
    assert wrapped.quality_status is QualityStatus.MISSING_BLANK
    assert not any(issue.source.source_column_name == column for issue in result.issues)
    assert result.record.is_eligible_at_as_of.value is None
    assert result.record.is_eligible_at_as_of.quality_status is QualityStatus.MISSING_BLANK


@pytest.mark.parametrize(
    ("sale", "suspended", "start", "end", "eligible", "eligible_status"),
    [
        ("1", "0", "20260822", "20260822", True, QualityStatus.VALID),
        ("1", "0", "20200101", "99991231", True, QualityStatus.VALID),
        ("1", "0", "20200101", "", True, QualityStatus.VALID),
        ("0", "0", "", "bad", False, QualityStatus.VALID),
        ("1", "1", "", "bad", False, QualityStatus.VALID),
        ("0", "", "", "bad", False, QualityStatus.VALID),
        ("", "1", "", "bad", False, QualityStatus.VALID),
        ("1", "0", "20260823", "99991231", False, QualityStatus.VALID),
        ("1", "0", "20200101", "20260710", False, QualityStatus.VALID),
        (
            "",
            "0",
            "20200101",
            "99991231",
            None,
            QualityStatus.MISSING_BLANK,
        ),
        (
            "1",
            "",
            "20200101",
            "99991231",
            None,
            QualityStatus.MISSING_BLANK,
        ),
        (
            "1",
            "0",
            "",
            "99991231",
            None,
            QualityStatus.MISSING_BLANK,
        ),
        (
            "1",
            "0",
            "0",
            "99991231",
            None,
            QualityStatus.SENTINEL_ZERO,
        ),
        (
            "1",
            "0",
            "bad",
            "99991231",
            None,
            QualityStatus.INVALID_FORMAT,
        ),
        (
            "1",
            "0",
            "20200101",
            "0",
            None,
            QualityStatus.SENTINEL_ZERO,
        ),
        (
            "1",
            "0",
            "20200101",
            "bad",
            None,
            QualityStatus.INVALID_FORMAT,
        ),
    ],
)
def test_domestic_eligibility_uses_false_before_unknown(
    sale: str,
    suspended: str,
    start: str,
    end: str,
    eligible: bool | None,
    eligible_status: QualityStatus,
) -> None:
    result = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "pd_sale_yn": sale,
                "pd_tr_yn": suspended,
                "pd_lstg_dt": start,
                "pd_lste_dt": end,
            },
        ),
        AS_OF,
    )
    assert result.record is not None
    assert result.record.is_eligible_at_as_of.value is eligible
    assert result.record.is_eligible_at_as_of.quality_status is eligible_status
    assert result.record.is_eligible_at_as_of.as_of_date == AS_OF
    assert result.record.is_eligible_at_as_of.inputs == (
        result.record.sale_flag.source,
        result.record.suspension_flag.source,
        result.record.listing_date.source,
        result.record.listing_end_date.source,
    )


def test_max_date_sentinel_is_enabled_only_for_listing_end() -> None:
    record = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "pd_lstg_dt": "99991231",
                "pd_lste_dt": "99991231",
                "cu_upt_dt": "99991231",
                "wu_upt_dt": "99991231",
            },
        ),
        AS_OF,
    ).record
    assert record is not None
    assert record.listing_date.normalized_value == date(9999, 12, 31)
    assert record.listing_end_date.normalized_value is None
    assert record.listing_end_date.quality_status is QualityStatus.SENTINEL_MAX_DATE
    assert record.custom_update_date.normalized_value == date(9999, 12, 31)
    assert record.weekly_update_date.normalized_value == date(9999, 12, 31)
    assert record.is_eligible_at_as_of.value is False
    assert record.is_eligible_at_as_of.quality_status is QualityStatus.VALID


@pytest.mark.parametrize(
    ("column", "attribute", "expected_status"),
    [
        ("pd_net_tamt", "aum_primary", QualityStatus.RECORDED_ZERO),
        ("du_last_aum", "aum_secondary", QualityStatus.RECORDED_ZERO),
        (
            "cu_charge_rt",
            "total_fee",
            QualityStatus.RECORDED_ZERO,
        ),
        ("du_chas_errt", "tracking_error", QualityStatus.RECORDED_ZERO),
        ("du_diff_rt", "difference_rate", QualityStatus.RECORDED_ZERO),
        ("du_er_1d", "return_1d", QualityStatus.RECORDED_ZERO),
        ("du_er_1m", "return_1m", QualityStatus.RECORDED_ZERO),
        ("du_er_3m", "return_3m", QualityStatus.RECORDED_ZERO),
        ("du_er_6m", "return_6m", QualityStatus.RECORDED_ZERO),
        ("du_er_1y", "return_1y", QualityStatus.RECORDED_ZERO),
        ("du_er_ytd", "return_ytd", QualityStatus.RECORDED_ZERO),
    ],
)
def test_domestic_numeric_zero_policy_is_field_specific(
    column: str, attribute: str, expected_status: QualityStatus
) -> None:
    record = normalize_domestic_listed(source_row("PREF01N001", {column: "0"}), AS_OF).record
    assert record is not None
    wrapped = getattr(record, attribute)
    assert wrapped.normalized_value == Decimal("0")
    assert wrapped.quality_status is expected_status
    assert wrapped.quality_status is not QualityStatus.CONSTANT_METRIC


@pytest.mark.parametrize(
    ("column", "attribute"),
    [
        ("du_er_1m", "return_1m"),
        ("du_er_3m", "return_3m"),
        ("du_er_6m", "return_6m"),
        ("du_er_1y", "return_1y"),
        ("du_er_ytd", "return_ytd"),
    ],
)
def test_exact_minus_one_hundred_returns_remain_valid_recorded_values(
    column: str, attribute: str
) -> None:
    record = normalize_domestic_listed(source_row("PREF01N001", {column: "-100"}), AS_OF).record
    assert record is not None
    wrapped = getattr(record, attribute)
    assert wrapped.raw_value == "-100"
    assert wrapped.normalized_value == Decimal("-100")
    assert wrapped.quality_status is QualityStatus.VALID


@pytest.mark.parametrize(
    ("raw", "value", "status", "warning"),
    [
        ("CURR_CD_KRW", "KRW", QualityStatus.VALID, False),
        ("", None, QualityStatus.MISSING_BLANK, False),
        ("CURR_CD_000", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("KRW", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("CURR_CD_USD", None, QualityStatus.OUT_OF_DOMAIN, True),
    ],
)
def test_domestic_currency_uses_only_the_explicit_code_map(
    raw: str, value: str | None, status: QualityStatus, warning: bool
) -> None:
    result = normalize_domestic_listed(
        source_row("PREF01N001", {"pd_curr_cd": raw, "pd_nm": "원화 USD 이름"}),
        AS_OF,
    )
    assert result.record is not None
    assert result.record.currency.raw_value == raw
    assert result.record.currency.normalized_value == value
    assert result.record.currency.quality_status is status
    assert (
        any(issue.source.source_column_name == "pd_curr_cd" for issue in result.issues) is warning
    )


def test_domestic_metrics_keep_distinct_source_dates_and_applicable_dates() -> None:
    row = source_row(
        "PREF01N001",
        {
            "cu_upt_dt": "20260709",
            "du_upt_dt": "20260710",
            "wu_upt_dt": "20260708",
            "du_chas_errt_base_dt": "20260707",
            "du_diff_rt_base_dt": "20260706",
            "du_chas_errt": "0.12",
            "du_er_1y": "7.5",
        },
        applicable_dates={
            "du_chas_errt": date(2026, 7, 7),
            "du_er_1y": date(2026, 7, 10),
        },
    )
    record = normalize_domestic_listed(row, AS_OF).record
    assert record is not None
    assert record.custom_update_date.normalized_value == date(2026, 7, 9)
    assert record.daily_update_date.normalized_value == date(2026, 7, 10)
    assert record.weekly_update_date.normalized_value == date(2026, 7, 8)
    assert record.tracking_error_base_date.normalized_value == date(2026, 7, 7)
    assert record.difference_rate_base_date.normalized_value == date(2026, 7, 6)
    assert record.tracking_error.source.source_applicable_date == date(2026, 7, 7)
    assert record.return_1y.source.source_applicable_date == date(2026, 7, 10)


def test_invalid_optional_metric_emits_warning_but_does_not_quarantine() -> None:
    result = normalize_domestic_listed(source_row("PREF01N001", {"du_er_1m": "NaN"}), AS_OF)
    assert result.record is not None
    assert result.record.return_1m.quality_status is QualityStatus.INVALID_FORMAT
    assert any(
        issue.source.source_column_name == "du_er_1m"
        and issue.quality_status is QualityStatus.INVALID_FORMAT
        and not issue.quarantined
        for issue in result.issues
    )
