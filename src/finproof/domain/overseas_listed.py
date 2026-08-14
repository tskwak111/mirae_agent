"""Immutable domain contract for one normalized overseas listed product."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from finproof.domain.listed import ListedProductType
from finproof.domain.values import NormalizedValue

OVERSEAS_FIELD_COLUMNS: Final[Mapping[str, str]] = MappingProxyType(
    {
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
        "nav_base_at": "du_nav_base_dt",
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
)


class OverseasListedProduct(BaseModel):
    """One overseas ETF or ETN at its native listed-product grain."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["listed_product"] = "listed_product"
    base_index: NormalizedValue[str]
    total_fee: NormalizedValue[Decimal]
    etn_flag_raw: NormalizedValue[str]
    manager: NormalizedValue[str]
    replication_method: NormalizedValue[str]
    index_tracking_flag_raw: NormalizedValue[str]
    inverse_short_flag_raw: NormalizedValue[str]
    leverage_factor: NormalizedValue[Decimal]
    strategy: NormalizedValue[str]
    custom_update_date: NormalizedValue[date]
    daily_base_date_match_raw: NormalizedValue[str]
    daily_bid_price: NormalizedValue[Decimal]
    close_price: NormalizedValue[Decimal]
    close_price_base_date: NormalizedValue[date]
    daily_close_source: NormalizedValue[str]
    difference_rate_raw_metric: NormalizedValue[Decimal]
    return_1d: NormalizedValue[Decimal]
    daily_high_price: NormalizedValue[Decimal]
    aum: NormalizedValue[Decimal]
    last_nav: NormalizedValue[Decimal]
    daily_low_price: NormalizedValue[Decimal]
    nav_base_at: NormalizedValue[datetime]
    daily_open_price: NormalizedValue[Decimal]
    daily_update_date: NormalizedValue[date]
    daily_value: NormalizedValue[Decimal]
    daily_volume: NormalizedValue[Decimal]
    ticker: NormalizedValue[str]
    source_currency_raw: NormalizedValue[str]
    exchange_market_code: NormalizedValue[str]
    product_type: NormalizedValue[ListedProductType]
    isin: NormalizedValue[str]
    product_id: NormalizedValue[str]
    market_identifier: NormalizedValue[str]
    lipper_id: NormalizedValue[str]
    listing_date: NormalizedValue[date]
    listing_price: NormalizedValue[Decimal]
    listed_share_count: NormalizedValue[Decimal]
    market_code: NormalizedValue[str]
    name: NormalizedValue[str]
    sale_flag_raw: NormalizedValue[str]
    trading_currency: NormalizedValue[str]
    suspension_flag_raw: NormalizedValue[str]
    us_cik: NormalizedValue[str]
    realtime_market_price: NormalizedValue[Decimal]
    realtime_market_volume: NormalizedValue[Decimal]
    core_flag_raw: NormalizedValue[str]
    asset_type: NormalizedValue[str]
    region: NormalizedValue[str]
    weekly_update_date: NormalizedValue[date]

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
            OVERSEAS_FIELD_COLUMNS.items(), start=1
        ):
            wrapped = getattr(self, field_name)
            source = wrapped.source
            if source.source_table != "PREF02N001":
                raise ValueError("overseas wrapper must name PREF02N001")
            if source.source_column_name != source_column:
                raise ValueError("overseas wrapper source column does not match field")
            if source.source_column_number != column_number:
                raise ValueError("overseas wrapper source column order is invalid")
            actual_lineage = (
                source.source_file,
                source.source_sheet,
                source.source_row_number,
                source.source_checksum,
                source.source_snapshot_date,
            )
            if actual_lineage != expected_lineage:
                raise ValueError("overseas wrappers must share one source row")
        return self
