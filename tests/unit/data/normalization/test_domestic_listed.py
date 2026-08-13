from datetime import date, datetime
from decimal import Decimal

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.domain.domestic_listed import ListedProduct, ListedProductType
from finproof.domain.quality import IssueSeverity, QualityStatus
from tests.helpers.source_rows import source_row

AS_OF = date(2026, 7, 11)


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


def test_valid_domestic_listed_maps_every_declared_source_column() -> None:
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
        "du_upt_dt": "2026-07-10 09:30:00",
        "wu_upt_dt": "20260708",
    }
    columns = {
        "product_id": "pd_itm_no",
        "market_identifier": "pd_itm_no_ma",
        "product_type": "pd_grp_no",
        "name": "pd_nm",
        "short_name": "pd_abrv_nm",
        "currency": "pd_curr_cd",
        "listing_date": "pd_lstg_dt",
        "listing_end_date": "pd_lste_dt",
        "sale_flag": "pd_sale_yn",
        "suspension_flag": "pd_tr_yn",
        "aum_primary": "pd_net_tamt",
        "aum_secondary": "du_last_aum",
        "total_fee": "cu_charge_rt",
        "tracking_error": "du_chas_errt",
        "difference_rate": "du_diff_rt",
        "return_1d": "du_er_1d",
        "return_1m": "du_er_1m",
        "return_3m": "du_er_3m",
        "return_6m": "du_er_6m",
        "return_1y": "du_er_1y",
        "return_ytd": "du_er_ytd",
        "risk_code": "pd_risk_cd",
        "risk_name": "pd_risk_nm",
        "base_index": "cu_base_index",
        "manager": "cu_fund_mgmt_co",
        "asset_type": "wu_inv_ast_type",
        "region": "wu_inv_rgn",
        "custom_update_date": "cu_upt_dt",
        "daily_update_at": "du_upt_dt",
        "weekly_update_date": "wu_upt_dt",
    }
    row = source_row("PREF01N001", values)
    record = normalize_domestic_listed(row, AS_OF).record
    assert record is not None
    for attribute, column in columns.items():
        wrapped = getattr(record, attribute)
        assert wrapped.raw_value == values[column]
        assert wrapped.source.source_column_name == column
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
    assert record.total_fee.quality_status is QualityStatus.RECORDED_ZERO_UNVERIFIED
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
    expected_warnings = sum(value is None for value in (expected_sale, expected_suspended))
    assert (
        sum(
            issue.source.source_column_name in {"pd_sale_yn", "pd_tr_yn"} for issue in result.issues
        )
        == expected_warnings
    )


@pytest.mark.parametrize(
    ("sale", "suspended", "start", "end", "eligible", "eligible_status"),
    [
        ("1", "0", "20260711", "20260711", True, QualityStatus.VALID),
        ("1", "0", "20200101", "99991231", True, QualityStatus.VALID),
        ("1", "0", "20200101", "", True, QualityStatus.VALID),
        ("0", "0", "", "bad", False, QualityStatus.VALID),
        ("1", "1", "", "bad", False, QualityStatus.VALID),
        ("0", "", "", "bad", False, QualityStatus.VALID),
        ("", "1", "", "bad", False, QualityStatus.VALID),
        ("1", "0", "20260712", "99991231", False, QualityStatus.VALID),
        ("1", "0", "20200101", "20260710", False, QualityStatus.VALID),
        (
            "",
            "0",
            "20200101",
            "99991231",
            None,
            QualityStatus.OUT_OF_DOMAIN,
        ),
        (
            "1",
            "",
            "20200101",
            "99991231",
            None,
            QualityStatus.OUT_OF_DOMAIN,
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
            QualityStatus.RECORDED_ZERO_UNVERIFIED,
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


def test_domestic_update_fields_remain_independent_and_do_not_supply_applicable_dates() -> None:
    row = source_row(
        "PREF01N001",
        {
            "cu_upt_dt": "20260709",
            "du_upt_dt": "2026-07-10 09:30:00",
            "wu_upt_dt": "20260708",
            "pd_net_tamt": "100",
        },
    )
    record = normalize_domestic_listed(row, AS_OF).record
    assert record is not None
    assert record.custom_update_date.normalized_value == date(2026, 7, 9)
    assert record.daily_update_at.normalized_value == datetime(2026, 7, 10, 9, 30)
    assert record.daily_update_at.normalized_value.tzinfo is None
    assert record.weekly_update_date.normalized_value == date(2026, 7, 8)
    assert record.aum_primary.source.source_applicable_date is None


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
