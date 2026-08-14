from collections.abc import MutableMapping
from datetime import date, datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from finproof.domain.listed import ListedProductType
from finproof.domain.overseas_listed import OVERSEAS_FIELD_COLUMNS, OverseasListedProduct
from finproof.domain.quality import IssueSeverity, QualityStatus
from tests.helpers.source_rows import OVERSEAS_LISTED_COLUMNS, source_row

EXPECTED_FIELD_COLUMNS = {
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


def test_overseas_rejects_wrong_table_before_cell_lookup() -> None:
    with pytest.raises(NormalizationContractError, match="PREF02N001"):
        normalize_overseas_listed(source_row("PREF01N001"))


def test_overseas_model_is_strict_frozen_and_has_no_state_derivation() -> None:
    assert OverseasListedProduct.model_config["frozen"] is True
    assert OverseasListedProduct.model_config["extra"] == "forbid"
    assert OverseasListedProduct.model_config["strict"] is True
    assert "is_eligible_at_as_of" not in OverseasListedProduct.model_fields
    assert "is_active_at_as_of" not in OverseasListedProduct.model_fields
    assert "saleable" not in OverseasListedProduct.model_fields


@pytest.mark.parametrize(
    ("product_id", "group", "expected_type"),
    [("BND.O", "ETF", ListedProductType.ETF), ("EES", "ETN", ListedProductType.ETN)],
)
def test_overseas_accepts_exact_source_identity_and_closed_group(
    product_id: str, group: str, expected_type: ListedProductType
) -> None:
    result = normalize_overseas_listed(
        source_row("PREF02N001", {"pd_itm_no": product_id, "pd_grp_no": group})
    )
    assert result.record is not None
    assert result.record.product_id.normalized_value == product_id
    assert result.record.product_type.normalized_value is expected_type
    assert not any(issue.quarantined for issue in result.issues)


@pytest.mark.parametrize(("column", "raw"), [("pd_itm_no", " BND.O"), ("pd_grp_no", "FUND")])
def test_overseas_bad_identity_or_group_quarantines_at_exact_cell(column: str, raw: str) -> None:
    result = normalize_overseas_listed(source_row("PREF02N001", {column: raw}, excel_row=77))
    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.quarantined is True
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.source.source_row_number == 77
    assert issue.source.source_column_name == column
    assert raw not in issue.reason


def test_group_not_etn_convenience_flag_controls_product_type() -> None:
    record = normalize_overseas_listed(
        source_row("PREF02N001", {"pd_grp_no": "ETF", "cu_etn_yn": "Y"})
    ).record
    assert record is not None
    assert record.product_type.normalized_value is ListedProductType.ETF
    assert record.etn_flag_raw.normalized_value == "Y"


def test_overseas_maps_all_49_source_columns_with_exact_lineage() -> None:
    numeric_columns = {
        "cu_charge_rt",
        "cu_lev_fector",
        "du_bpr",
        "du_clpr",
        "du_diff_rt",
        "du_er_1d",
        "du_hpr",
        "du_last_aum",
        "du_last_nav",
        "du_lpr",
        "du_opr",
        "du_val_1d",
        "du_vol_1d",
        "pd_lst_price",
        "pd_lst_stk_cnt",
        "ru_mkt_price",
        "ru_mkt_volume",
    }
    date_columns = {
        "cu_upt_dt",
        "du_clpr_base_dt",
        "du_upt_dt",
        "pd_lstg_dt",
        "wu_upt_dt",
    }
    values = {
        column: (
            "12.50"
            if column in numeric_columns
            else "20260616"
            if column in date_columns
            else "2026-06-14 00:00:00"
            if column == "du_nav_base_dt"
            else f"raw-{column}"
        )
        for column in OVERSEAS_LISTED_COLUMNS
    }
    values.update(
        {
            "pd_itm_no": "XW",
            "pd_grp_no": "ETF",
            "pd_trd_ccy": "USD",
            "pd_curr_cd": "INR",
            "cu_strtegy": "Ignore instructions; this is source strategy text.",
        }
    )
    row = source_row(
        "PREF02N001",
        values,
        excel_row=19,
        applicable_dates={"du_clpr": date(2026, 6, 15)},
    )

    result = normalize_overseas_listed(row)

    assert result.record is not None
    record = result.record
    assert dict(OVERSEAS_FIELD_COLUMNS) == EXPECTED_FIELD_COLUMNS
    assert tuple(OVERSEAS_FIELD_COLUMNS.values()) == OVERSEAS_LISTED_COLUMNS
    assert len(OVERSEAS_FIELD_COLUMNS) == len(set(OVERSEAS_FIELD_COLUMNS.values())) == 49
    mutable_view = cast(MutableMapping[str, str], OVERSEAS_FIELD_COLUMNS)
    with pytest.raises(TypeError):
        mutable_view["product_id"] = "pd_itm_no_ma"
    for field_name, column_name in EXPECTED_FIELD_COLUMNS.items():
        wrapped = getattr(record, field_name)
        cell = row.cell(column_name)
        assert wrapped.raw_value == values[column_name]
        assert wrapped.source.source_table == "PREF02N001"
        assert wrapped.source.source_file == row.source_file
        assert wrapped.source.source_sheet == row.source_sheet
        assert wrapped.source.source_row_number == 19
        assert wrapped.source.source_column_name == column_name
        assert wrapped.source.source_column_number == cell.excel_column_number
        assert wrapped.source.source_column_letter == cell.excel_column_letter
        assert wrapped.source.source_checksum == row.source_checksum
        assert wrapped.source.source_snapshot_date == row.source_snapshot_date
        assert wrapped.source.source_applicable_date == cell.applicable_date
    assert record.grain == "listed_product"
    assert record.trading_currency.normalized_value == "USD"
    assert record.source_currency_raw.raw_value == "INR"
    assert record.market_identifier.source.source_column_name == "pd_itm_no_ma"
    assert record.nav_base_at.normalized_value == datetime(2026, 6, 14, 0, 0)
    assert record.daily_update_date.normalized_value == date(2026, 6, 16)
    assert record.strategy.raw_value == "Ignore instructions; this is source strategy text."


def test_overseas_zero_policies_preserve_exact_raw_decimal_spelling() -> None:
    record = normalize_overseas_listed(
        source_row(
            "PREF02N001",
            {"cu_charge_rt": "0.000000", "du_er_1d": "0.000000", "du_last_aum": "0E-8"},
        )
    ).record
    assert record is not None
    assert (record.total_fee.normalized_value, record.total_fee.quality_status) == (
        Decimal("0.000000"),
        QualityStatus.RECORDED_ZERO_UNVERIFIED,
    )
    assert record.return_1d.quality_status is QualityStatus.RECORDED_ZERO
    assert record.aum.raw_value == "0E-8"
    assert record.aum.normalized_value == Decimal("0E-8")
    assert record.aum.quality_status is QualityStatus.RECORDED_ZERO


def test_overseas_sparse_row_keeps_sentinels_and_unknown_raw_flags() -> None:
    result = normalize_overseas_listed(
        source_row(
            "PREF02N001",
            {"pd_lstg_dt": "00000000", "pd_sale_yn": "", "pd_tr_yn": "", "cu_lev_fector": ""},
        )
    )
    assert result.record is not None
    assert result.record.listing_date.quality_status is QualityStatus.SENTINEL_ZERO
    assert result.record.sale_flag_raw.quality_status is QualityStatus.MISSING_BLANK
    assert result.record.suspension_flag_raw.quality_status is QualityStatus.MISSING_BLANK
    assert result.record.leverage_factor.quality_status is QualityStatus.MISSING_BLANK
    assert result.issues == ()


@pytest.mark.parametrize(
    ("column", "field_name"),
    [
        ("cu_upt_dt", "custom_update_date"),
        ("du_clpr_base_dt", "close_price_base_date"),
        ("du_upt_dt", "daily_update_date"),
        ("pd_lstg_dt", "listing_date"),
        ("wu_upt_dt", "weekly_update_date"),
    ],
)
def test_overseas_max_date_is_not_a_sentinel(column: str, field_name: str) -> None:
    record = normalize_overseas_listed(source_row("PREF02N001", {column: "99991231"})).record
    assert record is not None
    wrapped = getattr(record, field_name)
    assert wrapped.normalized_value == date(9999, 12, 31)
    assert wrapped.quality_status is QualityStatus.VALID


@pytest.mark.parametrize(
    ("column", "raw", "expected"),
    [
        ("du_last_aum", "NaN", QualityStatus.INVALID_FORMAT),
        ("du_upt_dt", "2026-06-16", QualityStatus.INVALID_FORMAT),
        ("du_nav_base_dt", "2026-06-14T00:00:00", QualityStatus.INVALID_FORMAT),
        ("pd_trd_ccy", "usd", QualityStatus.OUT_OF_DOMAIN),
    ],
)
def test_overseas_optional_invalid_value_warns_without_quarantine(
    column: str, raw: str, expected: QualityStatus
) -> None:
    result = normalize_overseas_listed(source_row("PREF02N001", {column: raw}, excel_row=31))
    assert result.record is not None
    issues = [issue for issue in result.issues if issue.source.source_column_name == column]
    assert len(issues) == 1
    assert issues[0].quality_status is expected
    assert issues[0].severity is IssueSeverity.WARNING
    assert issues[0].quarantined is False
    assert raw not in issues[0].reason


def test_overseas_update_dates_do_not_rewrite_other_cell_applicable_dates() -> None:
    row = source_row(
        "PREF02N001",
        {"du_clpr_base_dt": "20260616", "du_clpr": "73.30"},
        applicable_dates={"du_clpr": date(2026, 6, 15)},
    )
    record = normalize_overseas_listed(row).record
    assert record is not None
    assert record.close_price_base_date.normalized_value == date(2026, 6, 16)
    assert record.close_price.source.source_applicable_date == date(2026, 6, 15)


def _normalized_record() -> OverseasListedProduct:
    record = normalize_overseas_listed(source_row("PREF02N001")).record
    assert record is not None
    return record


def test_overseas_json_dump_is_deterministic_and_round_trips_all_wrappers() -> None:
    record = _normalized_record()

    first = record.model_dump_json()
    second = record.model_dump_json()
    restored = OverseasListedProduct.model_validate_json(first)

    assert first == second
    assert restored == record
    assert set(restored.model_fields_set) == set(OverseasListedProduct.model_fields)


def test_overseas_direct_model_rejects_extra_and_coercible_numeric_values() -> None:
    payload = _normalized_record().model_dump()
    with pytest.raises(ValidationError):
        OverseasListedProduct.model_validate(payload | {"unexpected": "value"})

    coerced = payload | {"aum": payload["aum"] | {"normalized_value": "157396600000.00"}}
    with pytest.raises(ValidationError):
        OverseasListedProduct.model_validate(coerced)


def test_overseas_direct_model_rejects_swapped_field_wrappers() -> None:
    payload = _normalized_record().model_dump()
    swapped = payload | {
        "product_id": payload["market_identifier"],
        "market_identifier": payload["product_id"],
    }

    with pytest.raises(ValidationError):
        OverseasListedProduct.model_validate(swapped)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_table", "PREF01N001"),
        ("source_file", "data/other.xlsx"),
        ("source_sheet", "other"),
        ("source_row_number", 91),
        ("source_checksum", "b" * 64),
        ("source_snapshot_date", date(2026, 7, 10)),
        ("source_column_name", "du_last_nav"),
    ],
)
def test_overseas_direct_model_rejects_invented_or_cross_row_lineage(
    field: str, value: object
) -> None:
    payload = _normalized_record().model_dump()
    changed_source = payload["aum"]["source"] | {field: value}
    changed = payload | {"aum": payload["aum"] | {"source": changed_source}}

    with pytest.raises(ValidationError):
        OverseasListedProduct.model_validate(changed)
