"""Pure domestic ETF/ETN normalization with exact source-cell lineage."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.numeric import NumericZeroStatus, parse_decimal
from finproof.data.normalization.temporal import parse_source_datetime, parse_yyyymmdd
from finproof.data.normalization.text import parse_identifier, parse_text
from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.domestic_listed import ListedProduct, ListedProductType
from finproof.domain.normalization import NormalizationResult
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue

_TABLE = "PREF01N001"
_RULE_VERSION = "1.0.0"
_ORDINARY_ZERO_STATUS: NumericZeroStatus = QualityStatus.RECORDED_ZERO
_FEE_ZERO_STATUS: NumericZeroStatus = QualityStatus.RECORDED_ZERO_UNVERIFIED
_PRODUCT_TYPE_MAP: Final[Mapping[str, ListedProductType]] = MappingProxyType(
    {
        "ETF": ListedProductType.ETF,
        "ETN": ListedProductType.ETN,
    }
)
_CURRENCY_MAP: Final[Mapping[str, str]] = MappingProxyType({"CURR_CD_KRW": "KRW"})
_SALE_FLAG_MAP: Final[Mapping[str, bool]] = MappingProxyType({"1": True, "0": False})
_SUSPENSION_FLAG_MAP: Final[Mapping[str, bool]] = MappingProxyType({"0": False, "1": True})


def normalize_domestic_listed(
    row: SourceRow,
    as_of: date,
) -> NormalizationResult[ListedProduct]:
    """Normalize one verified domestic-listed row without performing I/O."""
    if row.source_table != _TABLE:
        raise NormalizationContractError(
            expected_table=_TABLE,
            actual_table=row.source_table,
        )

    product_id = parse_identifier(
        row,
        "pd_itm_no",
        rule_id="domestic_listed.product_id",
        rule_version=_RULE_VERSION,
    )
    product_type = _product_type(row)
    quarantine_issues = _identity_issues(row, product_id, product_type)
    if quarantine_issues:
        return NormalizationResult[ListedProduct](
            record=None,
            issues=quarantine_issues,
        )

    market_identifier = _text(
        row,
        "pd_itm_no_ma",
        "domestic_listed.market_identifier",
    )
    name = _text(row, "pd_nm", "domestic_listed.name")
    short_name = _text(row, "pd_abrv_nm", "domestic_listed.short_name")
    currency = _currency(row)
    listing_date = _date(row, "pd_lstg_dt", "domestic_listed.listing_date")
    listing_end_date = _date(
        row,
        "pd_lste_dt",
        "domestic_listed.listing_end_date",
        allow_max_sentinel=True,
    )
    sale_flag = _flag(
        row,
        "pd_sale_yn",
        mapping=_SALE_FLAG_MAP,
        rule_id="domestic_listed.sale_flag",
    )
    suspension_flag = _flag(
        row,
        "pd_tr_yn",
        mapping=_SUSPENSION_FLAG_MAP,
        rule_id="domestic_listed.suspension_flag",
    )
    aum_primary = _decimal(row, "pd_net_tamt", "domestic_listed.aum_primary")
    aum_secondary = _decimal(row, "du_last_aum", "domestic_listed.aum_secondary")
    total_fee = _decimal(
        row,
        "cu_charge_rt",
        "domestic_listed.total_fee",
        zero_status=_FEE_ZERO_STATUS,
    )
    tracking_error = _decimal(
        row,
        "du_chas_errt",
        "domestic_listed.tracking_error",
    )
    difference_rate = _decimal(
        row,
        "du_diff_rt",
        "domestic_listed.difference_rate",
    )
    return_1d = _decimal(row, "du_er_1d", "domestic_listed.return_1d")
    return_1m = _decimal(row, "du_er_1m", "domestic_listed.return_1m")
    return_3m = _decimal(row, "du_er_3m", "domestic_listed.return_3m")
    return_6m = _decimal(row, "du_er_6m", "domestic_listed.return_6m")
    return_1y = _decimal(row, "du_er_1y", "domestic_listed.return_1y")
    return_ytd = _decimal(row, "du_er_ytd", "domestic_listed.return_ytd")
    risk_code = _text(row, "pd_risk_cd", "domestic_listed.risk_code")
    risk_name = _text(row, "pd_risk_nm", "domestic_listed.risk_name")
    base_index = _text(row, "cu_base_index", "domestic_listed.base_index")
    manager = _text(row, "cu_fund_mgmt_co", "domestic_listed.manager")
    asset_type = _text(row, "wu_inv_ast_type", "domestic_listed.asset_type")
    region = _text(row, "wu_inv_rgn", "domestic_listed.region")
    custom_update_date = _date(
        row,
        "cu_upt_dt",
        "domestic_listed.custom_update_date",
    )
    daily_update_at = _datetime(
        row,
        "du_upt_dt",
        "domestic_listed.daily_update_at",
    )
    weekly_update_date = _date(
        row,
        "wu_upt_dt",
        "domestic_listed.weekly_update_date",
    )
    is_eligible_at_as_of = _derive_eligibility(
        sale_flag,
        suspension_flag,
        listing_date,
        listing_end_date,
        as_of,
    )
    issue_candidates = (
        (
            currency.quality_status,
            "pd_curr_cd",
            "domestic_listed.currency",
            "Domestic listed currency is outside the supported source domain.",
        ),
        (
            listing_date.quality_status,
            "pd_lstg_dt",
            "domestic_listed.listing_date",
            "Domestic listed field has an invalid source format.",
        ),
        (
            listing_end_date.quality_status,
            "pd_lste_dt",
            "domestic_listed.listing_end_date",
            "Domestic listed field has an invalid source format.",
        ),
        (
            sale_flag.quality_status,
            "pd_sale_yn",
            "domestic_listed.sale_flag",
            "Domestic listed sale flag is outside the supported source domain.",
        ),
        (
            suspension_flag.quality_status,
            "pd_tr_yn",
            "domestic_listed.suspension_flag",
            "Domestic listed suspension flag is outside the supported source domain.",
        ),
        (
            aum_primary.quality_status,
            "pd_net_tamt",
            "domestic_listed.aum_primary",
            "Domestic listed field has an invalid source format.",
        ),
        (
            aum_secondary.quality_status,
            "du_last_aum",
            "domestic_listed.aum_secondary",
            "Domestic listed field has an invalid source format.",
        ),
        (
            total_fee.quality_status,
            "cu_charge_rt",
            "domestic_listed.total_fee",
            "Domestic listed field has an invalid source format.",
        ),
        (
            tracking_error.quality_status,
            "du_chas_errt",
            "domestic_listed.tracking_error",
            "Domestic listed field has an invalid source format.",
        ),
        (
            difference_rate.quality_status,
            "du_diff_rt",
            "domestic_listed.difference_rate",
            "Domestic listed field has an invalid source format.",
        ),
        (
            return_1d.quality_status,
            "du_er_1d",
            "domestic_listed.return_1d",
            "Domestic listed field has an invalid source format.",
        ),
        (
            return_1m.quality_status,
            "du_er_1m",
            "domestic_listed.return_1m",
            "Domestic listed field has an invalid source format.",
        ),
        (
            return_3m.quality_status,
            "du_er_3m",
            "domestic_listed.return_3m",
            "Domestic listed field has an invalid source format.",
        ),
        (
            return_6m.quality_status,
            "du_er_6m",
            "domestic_listed.return_6m",
            "Domestic listed field has an invalid source format.",
        ),
        (
            return_1y.quality_status,
            "du_er_1y",
            "domestic_listed.return_1y",
            "Domestic listed field has an invalid source format.",
        ),
        (
            return_ytd.quality_status,
            "du_er_ytd",
            "domestic_listed.return_ytd",
            "Domestic listed field has an invalid source format.",
        ),
        (
            custom_update_date.quality_status,
            "cu_upt_dt",
            "domestic_listed.custom_update_date",
            "Domestic listed field has an invalid source format.",
        ),
        (
            daily_update_at.quality_status,
            "du_upt_dt",
            "domestic_listed.daily_update_at",
            "Domestic listed field has an invalid source format.",
        ),
        (
            weekly_update_date.quality_status,
            "wu_upt_dt",
            "domestic_listed.weekly_update_date",
            "Domestic listed field has an invalid source format.",
        ),
    )
    issues = tuple(
        _warning_issue(
            row,
            column_name,
            rule_id=rule_id,
            quality_status=quality_status,
            reason=reason,
        )
        for quality_status, column_name, rule_id, reason in issue_candidates
        if quality_status in {QualityStatus.INVALID_FORMAT, QualityStatus.OUT_OF_DOMAIN}
    )

    record = ListedProduct(
        product_id=product_id,
        market_identifier=market_identifier,
        product_type=product_type,
        name=name,
        short_name=short_name,
        currency=currency,
        listing_date=listing_date,
        listing_end_date=listing_end_date,
        sale_flag=sale_flag,
        suspension_flag=suspension_flag,
        aum_primary=aum_primary,
        aum_secondary=aum_secondary,
        total_fee=total_fee,
        tracking_error=tracking_error,
        difference_rate=difference_rate,
        return_1d=return_1d,
        return_1m=return_1m,
        return_3m=return_3m,
        return_6m=return_6m,
        return_1y=return_1y,
        return_ytd=return_ytd,
        risk_code=risk_code,
        risk_name=risk_name,
        base_index=base_index,
        manager=manager,
        asset_type=asset_type,
        region=region,
        custom_update_date=custom_update_date,
        daily_update_at=daily_update_at,
        weekly_update_date=weekly_update_date,
        is_eligible_at_as_of=is_eligible_at_as_of,
    )
    return NormalizationResult[ListedProduct](record=record, issues=issues)


def _product_type(row: SourceRow) -> NormalizedValue[ListedProductType]:
    raw_value = row.cell("pd_grp_no").raw_value
    normalized_value = _PRODUCT_TYPE_MAP.get(raw_value)
    return make_normalized_value(
        row,
        "pd_grp_no",
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.VALID
            if normalized_value is not None
            else QualityStatus.MALFORMED_SOURCE_ROW
        ),
        rule_id="domestic_listed.product_type",
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
            "domestic_listed.product_type",
            "Domestic listed product group has an invalid source format.",
        ),
        (
            product_id,
            "pd_itm_no",
            "domestic_listed.product_id",
            "Domestic listed product identifier has an invalid source format.",
        ),
    )
    return tuple(
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


def _text(row: SourceRow, column_name: str, rule_id: str) -> NormalizedValue[str]:
    return parse_text(
        row,
        column_name,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _currency(row: SourceRow) -> NormalizedValue[str]:
    raw_value = row.cell("pd_curr_cd").raw_value
    if not raw_value.strip():
        return _text(row, "pd_curr_cd", "domestic_listed.currency")
    normalized_value = _CURRENCY_MAP.get(raw_value)
    return make_normalized_value(
        row,
        "pd_curr_cd",
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.VALID if normalized_value is not None else QualityStatus.OUT_OF_DOMAIN
        ),
        rule_id="domestic_listed.currency",
        rule_version=_RULE_VERSION,
    )


def _date(
    row: SourceRow,
    column_name: str,
    rule_id: str,
    *,
    allow_max_sentinel: bool = False,
) -> NormalizedValue[date]:
    return parse_yyyymmdd(
        row,
        column_name,
        allow_max_sentinel=allow_max_sentinel,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _datetime(
    row: SourceRow,
    column_name: str,
    rule_id: str,
) -> NormalizedValue[datetime]:
    return parse_source_datetime(
        row,
        column_name,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _flag(
    row: SourceRow,
    column_name: str,
    *,
    mapping: Mapping[str, bool],
    rule_id: str,
) -> NormalizedValue[bool]:
    normalized_value = mapping.get(row.cell(column_name).raw_value)
    return make_normalized_value(
        row,
        column_name,
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.VALID if normalized_value is not None else QualityStatus.OUT_OF_DOMAIN
        ),
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


def _derive_eligibility(
    sale_flag: NormalizedValue[bool],
    suspension_flag: NormalizedValue[bool],
    listing_date: NormalizedValue[date],
    listing_end_date: NormalizedValue[date],
    as_of: date,
) -> DerivedValue[bool]:
    sale = sale_flag.normalized_value
    suspended = suspension_flag.normalized_value
    start = listing_date.normalized_value
    end = listing_end_date.normalized_value
    if (
        sale is False
        or suspended is True
        or (start is not None and start > as_of)
        or (end is not None and end < as_of)
    ):
        value = False
        status = QualityStatus.VALID
    elif sale is None:
        value = None
        status = sale_flag.quality_status
    elif suspended is None:
        value = None
        status = suspension_flag.quality_status
    elif start is None:
        value = None
        status = listing_date.quality_status
    elif end is None and listing_end_date.quality_status not in {
        QualityStatus.MISSING_BLANK,
        QualityStatus.SENTINEL_MAX_DATE,
    }:
        value = None
        status = listing_end_date.quality_status
    else:
        value = True
        status = QualityStatus.VALID
    return DerivedValue[bool](
        value=value,
        quality_status=status,
        rule_id="domestic_listed.is_eligible_at_as_of",
        rule_version=_RULE_VERSION,
        as_of_date=as_of,
        inputs=(
            sale_flag.source,
            suspension_flag.source,
            listing_date.source,
            listing_end_date.source,
        ),
    )
