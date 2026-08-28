"""Pure domestic ETF/ETN normalization with exact source-cell lineage."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final, cast

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.numeric import NumericZeroStatus, parse_decimal
from finproof.data.normalization.temporal import parse_yyyymmdd
from finproof.data.normalization.text import parse_identifier, parse_text
from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.domestic_listed import (
    DOMESTIC_FIELD_COLUMNS,
    ListedProduct,
    ListedProductType,
)
from finproof.domain.normalization import NormalizationResult
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue

_TABLE = "PREF01N001"
_RULE_VERSION = "2.0.0"
_ORDINARY_ZERO_STATUS: NumericZeroStatus = QualityStatus.RECORDED_ZERO
_PRODUCT_TYPE_MAP: Final[Mapping[str, ListedProductType]] = MappingProxyType(
    {"ETF": ListedProductType.ETF, "ETN": ListedProductType.ETN}
)
_CURRENCY_MAP: Final[Mapping[str, str]] = MappingProxyType({"CURR_CD_KRW": "KRW"})
_SALE_FLAG_MAP: Final[Mapping[str, bool]] = MappingProxyType({"1": True, "0": False})
_SUSPENSION_FLAG_MAP: Final[Mapping[str, bool]] = MappingProxyType({"0": False, "1": True})
_DATE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "custom_update_date",
        "tracking_error_base_date",
        "difference_rate_base_date",
        "nav_base_date",
        "daily_update_date",
        "volatility_base_date",
        "fundamentals_base_date",
        "portfolio_date",
        "distribution_base_date",
        "distribution_price_base_date",
        "listing_end_date",
        "listing_date",
        "ref_base_date",
        "weekly_update_date",
    }
)
_DECIMAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "other_fee",
        "total_fee",
        "leverage_factor",
        "daily_bid_price",
        "tracking_error",
        "close_price",
        "difference_rate",
        "return_1d",
        "return_1m",
        "return_1y",
        "return_3m",
        "return_6m",
        "return_ytd",
        "daily_high_price",
        "aum_secondary",
        "last_nav",
        "daily_low_price",
        "nav_change_amount",
        "previous_nav",
        "daily_value",
        "daily_value_1m",
        "daily_value_5d",
        "volatility_1m",
        "volatility_1y",
        "volatility_3m",
        "volatility_6m",
        "daily_volume",
        "average_volume_1m",
        "average_volume_5d",
        "average_coupon",
        "average_maturity",
        "effective_duration",
        "effective_maturity",
        "modified_duration",
        "nominal_maturity",
        "circulating_net_assets",
        "circulating_share_count",
        "annual_distribution_amount",
        "distribution_per_share",
        "distribution_income",
        "distribution_nav",
        "distribution_pay_count",
        "distribution_yield",
        "listed_share_count",
        "aum_primary",
        "share_count",
        "realtime_market_price",
        "realtime_market_volume",
    }
)


def normalize_domestic_listed(
    row: SourceRow,
    as_of: date,
) -> NormalizationResult[ListedProduct]:
    """Normalize one verified domestic-listed row without performing I/O."""
    if row.source_table != _TABLE:
        raise NormalizationContractError(expected_table=_TABLE, actual_table=row.source_table)

    product_id = parse_identifier(
        row,
        "pd_itm_no",
        rule_id="domestic_listed.product_id",
        rule_version=_RULE_VERSION,
    )
    product_type = _product_type(row)
    quarantine_issues = _identity_issues(row, product_id, product_type)
    if quarantine_issues:
        return NormalizationResult[ListedProduct](record=None, issues=quarantine_issues)

    values: dict[str, object] = {}
    for field_name, column_name in DOMESTIC_FIELD_COLUMNS.items():
        rule_id = f"domestic_listed.{field_name}"
        if field_name == "product_id":
            wrapped: object = product_id
        elif field_name == "product_type":
            wrapped = product_type
        elif field_name == "currency":
            wrapped = _currency(row)
        elif field_name == "sale_flag":
            wrapped = _flag(row, column_name, mapping=_SALE_FLAG_MAP, rule_id=rule_id)
        elif field_name == "suspension_flag":
            wrapped = _flag(row, column_name, mapping=_SUSPENSION_FLAG_MAP, rule_id=rule_id)
        elif field_name in _DATE_FIELDS:
            wrapped = _date(
                row,
                column_name,
                rule_id,
                allow_max_sentinel=field_name == "listing_end_date",
            )
        elif field_name in _DECIMAL_FIELDS:
            wrapped = _decimal(
                row,
                column_name,
                rule_id,
                zero_status=_ORDINARY_ZERO_STATUS,
            )
        else:
            wrapped = _text(row, column_name, rule_id)
        values[field_name] = wrapped

    sale_flag = cast(NormalizedValue[bool], values["sale_flag"])
    suspension_flag = cast(NormalizedValue[bool], values["suspension_flag"])
    listing_date = cast(NormalizedValue[date], values["listing_date"])
    listing_end_date = cast(NormalizedValue[date], values["listing_end_date"])
    eligibility = _derive_eligibility(
        sale_flag,
        suspension_flag,
        listing_date,
        listing_end_date,
        as_of,
    )
    record = ListedProduct.model_validate(
        values | {"is_eligible_at_as_of": eligibility},
        strict=True,
    )
    issues = tuple(
        _warning_issue(
            row,
            wrapped.source.source_column_name,
            rule_id=wrapped.rule_id,
            quality_status=wrapped.quality_status,
            reason="Domestic listed field is outside its supported source domain.",
        )
        for wrapped in (value for value in values.values() if isinstance(value, NormalizedValue))
        if wrapped.quality_status in {QualityStatus.INVALID_FORMAT, QualityStatus.OUT_OF_DOMAIN}
    )
    return NormalizationResult[ListedProduct](record=record, issues=issues)


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
    return parse_text(row, column_name, rule_id=rule_id, rule_version=_RULE_VERSION)


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


def _flag(
    row: SourceRow,
    column_name: str,
    *,
    mapping: Mapping[str, bool],
    rule_id: str,
) -> NormalizedValue[bool]:
    raw_value = row.cell(column_name).raw_value
    normalized_value = mapping.get(raw_value)
    return make_normalized_value(
        row,
        column_name,
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.MISSING_BLANK
            if not raw_value.strip()
            else QualityStatus.VALID
            if normalized_value is not None
            else QualityStatus.OUT_OF_DOMAIN
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
