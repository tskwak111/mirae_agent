"""Pure overseas ETF/ETN normalization with exact source-cell lineage."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.numeric import NumericZeroStatus, parse_decimal
from finproof.data.normalization.temporal import parse_yyyymmdd
from finproof.data.normalization.text import parse_exact_source_identity, parse_text
from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.listed import ListedProductType
from finproof.domain.normalization import NormalizationResult
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

_TABLE = "PREF02N001"
_RULE_VERSION = "2.0.0"
_ORDINARY_ZERO_STATUS: NumericZeroStatus = QualityStatus.RECORDED_ZERO
_PRODUCT_TYPE_MAP: Final[Mapping[str, ListedProductType]] = MappingProxyType(
    {"ETF": ListedProductType.ETF, "ETN": ListedProductType.ETN}
)


def normalize_overseas_listed(
    row: SourceRow,
) -> NormalizationResult[OverseasListedProduct]:
    """Normalize one verified overseas-listed row without performing I/O."""
    if row.source_table != _TABLE:
        raise NormalizationContractError(
            expected_table=_TABLE,
            actual_table=row.source_table,
        )

    product_id = parse_exact_source_identity(
        row,
        "pd_itm_no",
        rule_id="overseas_listed.product_id",
        rule_version=_RULE_VERSION,
    )
    product_type = _product_type(row)
    quarantine_issues = _identity_issues(row, product_id, product_type)
    if quarantine_issues:
        return NormalizationResult[OverseasListedProduct](
            record=None,
            issues=quarantine_issues,
        )

    record = OverseasListedProduct(
        base_index=_text(row, "cu_base_index", "overseas_listed.base_index"),
        total_fee=_decimal(
            row,
            "cu_charge_rt",
            "overseas_listed.total_fee",
            zero_status=_ORDINARY_ZERO_STATUS,
        ),
        etn_flag_raw=_text(row, "cu_etn_yn", "overseas_listed.etn_flag_raw"),
        manager=_text(row, "cu_fund_mgmt_co", "overseas_listed.manager"),
        replication_method=_text(row, "cu_index_repl_mthd", "overseas_listed.replication_method"),
        index_tracking_flag_raw=_text(
            row,
            "cu_index_tracking_yn",
            "overseas_listed.index_tracking_flag_raw",
        ),
        inverse_short_flag_raw=_text(
            row,
            "cu_inverse_short_yn",
            "overseas_listed.inverse_short_flag_raw",
        ),
        leverage_factor=_decimal(row, "cu_lev_fector", "overseas_listed.leverage_factor"),
        strategy=_text(row, "cu_strtegy", "overseas_listed.strategy"),
        custom_update_date=_date(row, "cu_upt_dt", "overseas_listed.custom_update_date"),
        daily_base_date_match_raw=_text(
            row,
            "du_base_dt_match_yn",
            "overseas_listed.daily_base_date_match_raw",
        ),
        daily_bid_price=_decimal(row, "du_bpr", "overseas_listed.daily_bid_price"),
        close_price=_decimal(row, "du_clpr", "overseas_listed.close_price"),
        close_price_base_date=_date(
            row,
            "du_clpr_base_dt",
            "overseas_listed.close_price_base_date",
        ),
        daily_close_source=_text(row, "du_clpr_src", "overseas_listed.daily_close_source"),
        difference_rate_raw_metric=_decimal(
            row,
            "du_diff_rt",
            "overseas_listed.difference_rate_raw_metric",
        ),
        return_1d=_decimal(row, "du_er_1d", "overseas_listed.return_1d"),
        daily_high_price=_decimal(row, "du_hpr", "overseas_listed.daily_high_price"),
        aum=_decimal(row, "du_last_aum", "overseas_listed.aum"),
        last_nav=_decimal(row, "du_last_nav", "overseas_listed.last_nav"),
        daily_low_price=_decimal(row, "du_lpr", "overseas_listed.daily_low_price"),
        nav_base_date=_date(row, "du_nav_base_dt", "overseas_listed.nav_base_date"),
        daily_open_price=_decimal(row, "du_opr", "overseas_listed.daily_open_price"),
        daily_update_date=_date(row, "du_upt_dt", "overseas_listed.daily_update_date"),
        daily_value=_decimal(row, "du_val_1d", "overseas_listed.daily_value"),
        daily_volume=_decimal(row, "du_vol_1d", "overseas_listed.daily_volume"),
        ticker=_text(row, "pd_abrv_nm", "overseas_listed.ticker"),
        source_currency_raw=_text(row, "pd_curr_cd", "overseas_listed.source_currency_raw"),
        exchange_market_code=_text(
            row,
            "pd_exg_mkt_cd",
            "overseas_listed.exchange_market_code",
        ),
        product_type=product_type,
        isin=_text(row, "pd_isin_cd", "overseas_listed.isin"),
        product_id=product_id,
        market_identifier=_text(row, "pd_itm_no_ma", "overseas_listed.market_identifier"),
        lipper_id=_text(row, "pd_lipper_id", "overseas_listed.lipper_id"),
        listing_date=_date(row, "pd_lstg_dt", "overseas_listed.listing_date"),
        listing_price=_decimal(row, "pd_lst_price", "overseas_listed.listing_price"),
        listed_share_count=_decimal(
            row,
            "pd_lst_stk_cnt",
            "overseas_listed.listed_share_count",
        ),
        market_code=_text(row, "pd_mkt_id", "overseas_listed.market_code"),
        name=_text(row, "pd_nm", "overseas_listed.name"),
        sale_flag_raw=_text(row, "pd_sale_yn", "overseas_listed.sale_flag_raw"),
        trading_currency=_currency(row),
        suspension_flag_raw=_text(row, "pd_tr_yn", "overseas_listed.suspension_flag_raw"),
        us_cik=_text(row, "pd_us_cik", "overseas_listed.us_cik"),
        realtime_market_price=_decimal(
            row,
            "ru_mkt_price",
            "overseas_listed.realtime_market_price",
        ),
        realtime_market_volume=_decimal(
            row,
            "ru_mkt_volume",
            "overseas_listed.realtime_market_volume",
        ),
        core_flag_raw=_text(row, "wu_core_yn", "overseas_listed.core_flag_raw"),
        asset_type=_text(row, "wu_inv_ast_type", "overseas_listed.asset_type"),
        region=_text(row, "wu_inv_rgn", "overseas_listed.region"),
        weekly_update_date=_date(row, "wu_upt_dt", "overseas_listed.weekly_update_date"),
    )
    numeric_fields = (
        record.total_fee,
        record.leverage_factor,
        record.daily_bid_price,
        record.close_price,
        record.difference_rate_raw_metric,
        record.return_1d,
        record.daily_high_price,
        record.aum,
        record.last_nav,
        record.daily_low_price,
        record.daily_open_price,
        record.daily_value,
        record.daily_volume,
        record.listing_price,
        record.listed_share_count,
        record.realtime_market_price,
        record.realtime_market_volume,
    )
    date_fields = (
        record.custom_update_date,
        record.close_price_base_date,
        record.nav_base_date,
        record.daily_update_date,
        record.listing_date,
        record.weekly_update_date,
    )
    issues = [
        _warning_issue(
            row,
            wrapped.source.source_column_name,
            rule_id=wrapped.rule_id,
            quality_status=QualityStatus.INVALID_FORMAT,
            reason="Overseas listed numeric value is invalid.",
        )
        for wrapped in numeric_fields
        if wrapped.quality_status is QualityStatus.INVALID_FORMAT
    ]
    issues.extend(
        _warning_issue(
            row,
            wrapped.source.source_column_name,
            rule_id=wrapped.rule_id,
            quality_status=QualityStatus.INVALID_FORMAT,
            reason="Overseas listed date value is invalid.",
        )
        for wrapped in date_fields
        if wrapped.quality_status is QualityStatus.INVALID_FORMAT
    )
    if record.trading_currency.quality_status is QualityStatus.OUT_OF_DOMAIN:
        issues.append(
            _warning_issue(
                row,
                "pd_trd_ccy",
                rule_id=record.trading_currency.rule_id,
                quality_status=QualityStatus.OUT_OF_DOMAIN,
                reason="Overseas listed trading currency is invalid.",
            )
        )
    return NormalizationResult[OverseasListedProduct](
        record=record,
        issues=tuple(sorted(issues, key=_issue_sort_key)),
    )


def _product_type(row: SourceRow) -> NormalizedValue[ListedProductType]:
    normalized_value = _PRODUCT_TYPE_MAP.get(row.cell("pd_grp_no").raw_value)
    return make_normalized_value(
        row,
        "pd_grp_no",
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.VALID
            if normalized_value is not None
            else QualityStatus.MALFORMED_SOURCE_ROW
        ),
        rule_id="overseas_listed.product_type",
        rule_version=_RULE_VERSION,
    )


def _identity_issues(
    row: SourceRow,
    product_id: NormalizedValue[str],
    product_type: NormalizedValue[ListedProductType],
) -> tuple[DataQualityIssue, ...]:
    candidates = (
        (
            product_type,
            "pd_grp_no",
            "overseas_listed.product_type",
            "Overseas listed product group has an invalid source format.",
        ),
        (
            product_id,
            "pd_itm_no",
            "overseas_listed.product_id",
            "Overseas listed product identifier has an invalid source format.",
        ),
    )
    issues = (
        DataQualityIssue.from_row(
            row,
            column_name,
            rule_id=rule_id,
            rule_version=_RULE_VERSION,
            severity=IssueSeverity.BLOCKER,
            quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
            reason=reason,
            quarantined=True,
        )
        for wrapped, column_name, rule_id, reason in candidates
        if wrapped.normalized_value is None
    )
    return tuple(sorted(issues, key=_issue_sort_key))


def _text(row: SourceRow, column_name: str, rule_id: str) -> NormalizedValue[str]:
    return parse_text(
        row,
        column_name,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _decimal(
    row: SourceRow,
    column_name: str,
    rule_id: str,
    *,
    zero_status: NumericZeroStatus = _ORDINARY_ZERO_STATUS,
) -> NormalizedValue[Decimal]:
    return parse_decimal(
        row,
        column_name,
        zero_status=zero_status,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _date(row: SourceRow, column_name: str, rule_id: str) -> NormalizedValue[date]:
    return parse_yyyymmdd(
        row,
        column_name,
        allow_max_sentinel=False,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _currency(row: SourceRow) -> NormalizedValue[str]:
    raw_value = row.cell("pd_trd_ccy").raw_value
    if not raw_value.strip():
        return _text(row, "pd_trd_ccy", "overseas_listed.trading_currency")
    normalized_value = (
        raw_value
        if len(raw_value) == 3
        and raw_value.isascii()
        and raw_value.isalpha()
        and raw_value.isupper()
        else None
    )
    return make_normalized_value(
        row,
        "pd_trd_ccy",
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.VALID if normalized_value is not None else QualityStatus.OUT_OF_DOMAIN
        ),
        rule_id="overseas_listed.trading_currency",
        rule_version=_RULE_VERSION,
    )


def _issue_sort_key(issue: DataQualityIssue) -> tuple[int, str, str]:
    return (
        issue.source.source_column_number,
        issue.rule_id,
        issue.issue_id,
    )


def _warning_issue(
    row: SourceRow,
    column_name: str,
    *,
    rule_id: str,
    quality_status: QualityStatus,
    reason: str,
) -> DataQualityIssue:
    return DataQualityIssue.from_row(
        row,
        column_name,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        severity=IssueSeverity.WARNING,
        quality_status=quality_status,
        reason=reason,
        quarantined=False,
    )
