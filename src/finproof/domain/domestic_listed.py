"""Immutable domain contract for one normalized domestic listed product."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from finproof.domain.listed import ListedProductType as ListedProductType
from finproof.domain.values import DerivedValue, NormalizedValue

DOMESTIC_FIELD_COLUMNS: Final[Mapping[str, str]] = MappingProxyType(
    {
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
)


class ListedProduct(BaseModel):
    """One domestic ETF or ETN at its native listed-product grain."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["listed_product"] = "listed_product"
    base_index: NormalizedValue[str]
    other_fee: NormalizedValue[Decimal]
    total_fee: NormalizedValue[Decimal]
    manager: NormalizedValue[str]
    leverage_factor: NormalizedValue[Decimal]
    strategy: NormalizedValue[str]
    custom_update_date: NormalizedValue[date]
    daily_bid_price: NormalizedValue[Decimal]
    tracking_error: NormalizedValue[Decimal]
    tracking_error_base_date: NormalizedValue[date]
    close_price: NormalizedValue[Decimal]
    difference_rate: NormalizedValue[Decimal]
    difference_rate_base_date: NormalizedValue[date]
    return_1d: NormalizedValue[Decimal]
    return_1m: NormalizedValue[Decimal]
    return_1y: NormalizedValue[Decimal]
    return_3m: NormalizedValue[Decimal]
    return_6m: NormalizedValue[Decimal]
    return_ytd: NormalizedValue[Decimal]
    daily_high_price: NormalizedValue[Decimal]
    aum_secondary: NormalizedValue[Decimal]
    last_nav: NormalizedValue[Decimal]
    daily_low_price: NormalizedValue[Decimal]
    nav_base_date: NormalizedValue[date]
    nav_change_amount: NormalizedValue[Decimal]
    previous_nav: NormalizedValue[Decimal]
    daily_update_date: NormalizedValue[date]
    daily_value: NormalizedValue[Decimal]
    daily_value_1m: NormalizedValue[Decimal]
    daily_value_5d: NormalizedValue[Decimal]
    volatility_1m: NormalizedValue[Decimal]
    volatility_1y: NormalizedValue[Decimal]
    volatility_3m: NormalizedValue[Decimal]
    volatility_6m: NormalizedValue[Decimal]
    volatility_base_date: NormalizedValue[date]
    daily_volume: NormalizedValue[Decimal]
    average_volume_1m: NormalizedValue[Decimal]
    average_volume_5d: NormalizedValue[Decimal]
    average_coupon: NormalizedValue[Decimal]
    average_maturity: NormalizedValue[Decimal]
    average_quality: NormalizedValue[str]
    fundamentals_base_date: NormalizedValue[date]
    effective_duration: NormalizedValue[Decimal]
    effective_maturity: NormalizedValue[Decimal]
    modified_duration: NormalizedValue[Decimal]
    nominal_maturity: NormalizedValue[Decimal]
    portfolio_date: NormalizedValue[date]
    short_name: NormalizedValue[str]
    circulating_net_assets: NormalizedValue[Decimal]
    circulating_share_count: NormalizedValue[Decimal]
    currency: NormalizedValue[str]
    currency_name: NormalizedValue[str]
    annual_distribution_amount: NormalizedValue[Decimal]
    distribution_per_share: NormalizedValue[Decimal]
    distribution_base_date: NormalizedValue[date]
    distribution_cycle: NormalizedValue[str]
    distribution_income: NormalizedValue[Decimal]
    distribution_nav: NormalizedValue[Decimal]
    distribution_pay_count: NormalizedValue[Decimal]
    distribution_pay_months: NormalizedValue[str]
    distribution_price_base_date: NormalizedValue[date]
    distribution_tax_basis: NormalizedValue[str]
    distribution_yield: NormalizedValue[Decimal]
    exchange_market_code: NormalizedValue[str]
    exchange_market_name: NormalizedValue[str]
    product_type: NormalizedValue[ListedProductType]
    isin: NormalizedValue[str]
    product_id: NormalizedValue[str]
    market_identifier: NormalizedValue[str]
    listed_share_count: NormalizedValue[Decimal]
    listing_end_date: NormalizedValue[date]
    listing_date: NormalizedValue[date]
    market_code: NormalizedValue[str]
    market_name: NormalizedValue[str]
    aum_primary: NormalizedValue[Decimal]
    name: NormalizedValue[str]
    pension_risk_name: NormalizedValue[str]
    pension_trade_flag_raw: NormalizedValue[str]
    ric: NormalizedValue[str]
    risk_code: NormalizedValue[str]
    risk_name: NormalizedValue[str]
    sale_flag: NormalizedValue[bool]
    sector_code: NormalizedValue[str]
    spac_flag_raw: NormalizedValue[str]
    share_count: NormalizedValue[Decimal]
    ticker: NormalizedValue[str]
    suspension_flag: NormalizedValue[bool]
    ref_asset_type: NormalizedValue[str]
    ref_base_date: NormalizedValue[date]
    ref_base_index: NormalizedValue[str]
    ref_manager: NormalizedValue[str]
    ref_region: NormalizedValue[str]
    realtime_market_price: NormalizedValue[Decimal]
    realtime_market_volume: NormalizedValue[Decimal]
    core_flag_raw: NormalizedValue[str]
    asset_type: NormalizedValue[str]
    region: NormalizedValue[str]
    weekly_update_date: NormalizedValue[date]
    is_eligible_at_as_of: DerivedValue[bool]

    @model_validator(mode="after")
    def validate_complete_source_lineage(self) -> Self:
        """Reject wrapper swaps and lineage assembled from unrelated rows."""
        anchor = self.base_index.source
        expected_lineage = (
            anchor.source_file,
            anchor.source_sheet,
            anchor.source_row_number,
            anchor.source_checksum,
            anchor.source_snapshot_date,
        )
        for column_number, (field_name, source_column) in enumerate(
            DOMESTIC_FIELD_COLUMNS.items(), start=1
        ):
            source = getattr(self, field_name).source
            if source.source_table != "PREF01N001":
                raise ValueError("domestic wrapper must name PREF01N001")
            if source.source_column_name != source_column:
                raise ValueError("domestic wrapper source column does not match field")
            if source.source_column_number != column_number:
                raise ValueError("domestic wrapper source column order is invalid")
            actual_lineage = (
                source.source_file,
                source.source_sheet,
                source.source_row_number,
                source.source_checksum,
                source.source_snapshot_date,
            )
            if actual_lineage != expected_lineage:
                raise ValueError("domestic wrappers must share one source row")
        return self
