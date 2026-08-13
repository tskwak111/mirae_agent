"""Pure domestic-bond normalization with complete source-cell lineage."""

import re
from datetime import date
from decimal import Decimal

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.numeric import (
    NumericZeroStatus,
    parse_decimal,
    parse_integer,
)
from finproof.data.normalization.temporal import parse_yyyymmdd
from finproof.data.normalization.text import parse_identifier, parse_text
from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.bonds import BondInstrument
from finproof.domain.normalization import NormalizationResult
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue
from finproof.registry.rating import RatingRegistry

_TABLE = "PRBD01N001"
_RULE_VERSION = "1.0.0"
_ZERO_STATUS: NumericZeroStatus = QualityStatus.RECORDED_ZERO


def normalize_bond(
    row: SourceRow,
    as_of: date,
    rating_registry: RatingRegistry,
) -> NormalizationResult[BondInstrument]:
    """Normalize one verified domestic-bond row without performing I/O."""
    if row.source_table != _TABLE:
        raise NormalizationContractError(
            expected_table=_TABLE,
            actual_table=row.source_table,
        )

    product_id = parse_identifier(
        row,
        "PD_NO",
        rule_id="bond.product_id",
        rule_version=_RULE_VERSION,
    )
    if product_id.normalized_value is None:
        return NormalizationResult[BondInstrument](
            record=None,
            issues=(
                DataQualityIssue.from_row(
                    row,
                    "PD_NO",
                    rule_id="bond.product_id",
                    rule_version=_RULE_VERSION,
                    severity=IssueSeverity.BLOCKER,
                    quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
                    reason="Domestic bond identifier has an invalid source format.",
                    quarantined=True,
                ),
            ),
        )

    name = _text(row, "PD_NM", "bond.name")
    short_name = _text(row, "PD_ABRV_NM", "bond.short_name")
    currency = _currency(row)
    bond_kind_raw = _text(row, "BD_KND", "bond.bond_kind_raw")
    issue_date = _date(row, "ISU_DT", "bond.issue_date")
    maturity_date = _date(
        row,
        "MAT_DT",
        "bond.maturity_date",
        allow_max_sentinel=True,
    )
    source_update_date = _date(
        row,
        "PD_STD_INFO_UPDATE",
        "bond.source_update_date",
    )
    coupon_rate = _decimal(row, "SRFC_IRT", "bond.coupon_rate")
    buy_yield = _decimal(row, "BUY_YIELD", "bond.buy_yield")
    buyable_quantity = _decimal(
        row,
        "BUYABLE_QUANTITY",
        "bond.buyable_quantity",
    )
    source_remaining_days = parse_integer(
        row,
        "REMAINING_DAYS",
        zero_status=_ZERO_STATUS,
        rule_id="bond.source_remaining_days",
        rule_version=_RULE_VERSION,
    )
    credit_rating = _rating(row, rating_registry)
    credit_rating_agencies_raw = _text(
        row,
        "PD_EVCO_CRD_GRD",
        "bond.credit_rating_agencies_raw",
    )
    credit_rating_date = _date(
        row,
        "CRD_GRD_DT",
        "bond.credit_rating_date",
    )
    duration = _decimal(row, "DUR", "bond.duration")
    evaluation_price = _decimal(row, "EVAL_PRICE", "bond.evaluation_price")
    issues: list[DataQualityIssue] = []
    invalid_fields = (
        (issue_date, "ISU_DT", "bond.issue_date"),
        (maturity_date, "MAT_DT", "bond.maturity_date"),
        (source_update_date, "PD_STD_INFO_UPDATE", "bond.source_update_date"),
        (coupon_rate, "SRFC_IRT", "bond.coupon_rate"),
        (buy_yield, "BUY_YIELD", "bond.buy_yield"),
        (buyable_quantity, "BUYABLE_QUANTITY", "bond.buyable_quantity"),
        (source_remaining_days, "REMAINING_DAYS", "bond.source_remaining_days"),
        (credit_rating_date, "CRD_GRD_DT", "bond.credit_rating_date"),
        (duration, "DUR", "bond.duration"),
        (evaluation_price, "EVAL_PRICE", "bond.evaluation_price"),
    )
    for wrapped, column_name, rule_id in invalid_fields:
        if wrapped.quality_status is not QualityStatus.INVALID_FORMAT:
            continue
        issues.append(
            _warning_issue(
                row,
                column_name,
                rule_id=rule_id,
                quality_status=QualityStatus.INVALID_FORMAT,
                reason="Domestic bond field has an invalid source format.",
            )
        )
    if currency.quality_status is QualityStatus.OUT_OF_DOMAIN:
        issues.append(
            _warning_issue(
                row,
                "CURR_CD",
                rule_id="bond.currency",
                quality_status=QualityStatus.OUT_OF_DOMAIN,
                reason="Domestic bond currency is outside the supported source domain.",
            )
        )
    if credit_rating.quality_status is QualityStatus.OUT_OF_DOMAIN:
        issues.append(
            _warning_issue(
                row,
                "CRD_GRD",
                rule_id="bond.credit_rating",
                quality_status=QualityStatus.OUT_OF_DOMAIN,
                reason="Primary credit rating is outside the configured rating domain.",
            )
        )

    primary_resolution = rating_registry.resolve(credit_rating.raw_value)
    agency_resolutions = rating_registry.resolve_agencies(credit_rating_agencies_raw.raw_value)
    if any(
        resolution.quality_status is QualityStatus.OUT_OF_DOMAIN
        for resolution in agency_resolutions
    ):
        issues.append(
            _warning_issue(
                row,
                "PD_EVCO_CRD_GRD",
                rule_id="bond.agency_rating_out_of_domain",
                quality_status=QualityStatus.OUT_OF_DOMAIN,
                reason="Agency credit rating is outside the configured rating domain.",
            )
        )
    agency_ordinals = tuple(
        resolution.ordinal for resolution in agency_resolutions if resolution.ordinal is not None
    )
    rating_disagreement = len(set(agency_ordinals)) > 1 or (
        primary_resolution.ordinal is not None
        and any(ordinal != primary_resolution.ordinal for ordinal in agency_ordinals)
    )
    if rating_disagreement:
        issues.append(
            _warning_issue(
                row,
                "PD_EVCO_CRD_GRD",
                rule_id="bond.rating_disagreement",
                quality_status=QualityStatus.MIXED_SOURCE_VALUES,
                reason="Comparable credit-rating sources disagree.",
            )
        )

    remaining_days_at_as_of, is_matured_at_as_of = _derive_maturity(
        maturity_date,
        as_of,
    )
    has_positive_buyable_quantity = _derive_positive_quantity(
        buyable_quantity,
        as_of,
    )
    is_buyable_validated_at_as_of = _derive_buyability(
        buyable_quantity,
        maturity_date,
        as_of,
    )
    if (
        buyable_quantity.normalized_value is not None
        and buyable_quantity.normalized_value > 0
        and maturity_date.normalized_value is not None
        and maturity_date.normalized_value < as_of
    ):
        issues.append(
            _warning_issue(
                row,
                "BUYABLE_QUANTITY",
                rule_id="bond.matured_positive_quantity",
                quality_status=QualityStatus.MIXED_SOURCE_VALUES,
                reason="Positive source quantity conflicts with derived matured state.",
            )
        )

    record = BondInstrument(
        product_id=product_id,
        name=name,
        short_name=short_name,
        currency=currency,
        bond_kind_raw=bond_kind_raw,
        issue_date=issue_date,
        maturity_date=maturity_date,
        source_update_date=source_update_date,
        coupon_rate=coupon_rate,
        buy_yield=buy_yield,
        buyable_quantity=buyable_quantity,
        source_remaining_days=source_remaining_days,
        credit_rating=credit_rating,
        credit_rating_agencies_raw=credit_rating_agencies_raw,
        credit_rating_date=credit_rating_date,
        duration=duration,
        evaluation_price=evaluation_price,
        remaining_days_at_as_of=remaining_days_at_as_of,
        is_matured_at_as_of=is_matured_at_as_of,
        has_positive_buyable_quantity=has_positive_buyable_quantity,
        is_buyable_validated_at_as_of=is_buyable_validated_at_as_of,
    )
    return NormalizationResult[BondInstrument](record=record, issues=tuple(issues))


def _text(row: SourceRow, column_name: str, rule_id: str) -> NormalizedValue[str]:
    return parse_text(
        row,
        column_name,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _currency(row: SourceRow) -> NormalizedValue[str]:
    raw_value = row.cell("CURR_CD").raw_value
    if not raw_value.strip():
        return _text(row, "CURR_CD", "bond.currency")
    normalized_value = raw_value if re.fullmatch(r"[A-Z]{3}", raw_value, re.ASCII) else None
    return make_normalized_value(
        row,
        "CURR_CD",
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.VALID if normalized_value is not None else QualityStatus.OUT_OF_DOMAIN
        ),
        rule_id="bond.currency",
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


def _decimal(
    row: SourceRow,
    column_name: str,
    rule_id: str,
) -> NormalizedValue[Decimal]:
    return parse_decimal(
        row,
        column_name,
        zero_status=_ZERO_STATUS,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _rating(row: SourceRow, registry: RatingRegistry) -> NormalizedValue[str]:
    resolution = registry.resolve(row.cell("CRD_GRD").raw_value)
    return make_normalized_value(
        row,
        "CRD_GRD",
        normalized_value=resolution.normalized_value,
        quality_status=resolution.quality_status,
        rule_id="bond.credit_rating",
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


def _derive_maturity(
    maturity_date: NormalizedValue[date],
    as_of: date,
) -> tuple[DerivedValue[int], DerivedValue[bool]]:
    maturity = maturity_date.normalized_value
    if maturity is None:
        remaining_days = None
        matured = None
        status = maturity_date.quality_status
    else:
        remaining_days = (maturity - as_of).days
        matured = remaining_days < 0
        status = QualityStatus.VALID
    inputs = (maturity_date.source,)
    return (
        DerivedValue[int](
            value=remaining_days,
            quality_status=status,
            rule_id="bond.remaining_days_at_as_of",
            rule_version=_RULE_VERSION,
            as_of_date=as_of,
            inputs=inputs,
        ),
        DerivedValue[bool](
            value=matured,
            quality_status=status,
            rule_id="bond.is_matured_at_as_of",
            rule_version=_RULE_VERSION,
            as_of_date=as_of,
            inputs=inputs,
        ),
    )


def _derive_positive_quantity(
    quantity: NormalizedValue[Decimal],
    as_of: date,
) -> DerivedValue[bool]:
    value = quantity.normalized_value
    return DerivedValue[bool](
        value=None if value is None else value > 0,
        quality_status=(quantity.quality_status if value is None else QualityStatus.VALID),
        rule_id="bond.has_positive_buyable_quantity",
        rule_version=_RULE_VERSION,
        as_of_date=as_of,
        inputs=(quantity.source,),
    )


def _derive_buyability(
    quantity: NormalizedValue[Decimal],
    maturity_date: NormalizedValue[date],
    as_of: date,
) -> DerivedValue[bool]:
    quantity_value = quantity.normalized_value
    maturity_value = maturity_date.normalized_value
    is_matured = maturity_value is not None and maturity_value < as_of
    is_nonpositive = quantity_value is not None and quantity_value <= 0
    if is_matured or is_nonpositive:
        value = False
        status = QualityStatus.VALID
    elif quantity_value is None:
        value = None
        status = quantity.quality_status
    elif maturity_value is None:
        value = None
        status = maturity_date.quality_status
    else:
        value = True
        status = QualityStatus.VALID
    return DerivedValue[bool](
        value=value,
        quality_status=status,
        rule_id="bond.is_buyable_validated_at_as_of",
        rule_version=_RULE_VERSION,
        as_of_date=as_of,
        inputs=(quantity.source, maturity_date.source),
    )
