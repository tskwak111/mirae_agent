"""Pure domestic-bond lot normalization and deterministic parent projection."""

import re
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.numeric import NumericZeroStatus, parse_decimal, parse_integer
from finproof.data.normalization.temporal import parse_yyyymmdd
from finproof.data.normalization.text import parse_identifier, parse_text
from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.bonds import (
    BondFieldSources,
    BondInstrument,
    BondSaleLot,
    BondSaleLotKey,
)
from finproof.domain.locators import SourceCellLocator
from finproof.domain.normalization import NormalizationResult
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue
from finproof.registry.rating import RatingRegistry

_TABLE = "PRBD01N001"
_RULE_VERSION = "2.0.0"
_ZERO_STATUS: NumericZeroStatus = QualityStatus.RECORDED_ZERO
_PARENT_FIELDS = (
    "name",
    "short_name",
    "currency",
    "bond_kind_raw",
    "issue_date",
    "maturity_date",
    "source_update_date",
    "coupon_rate",
    "credit_rating",
    "credit_rating_date",
)


def normalize_bond_lot(row: SourceRow) -> NormalizationResult[BondSaleLot]:
    """Normalize one verified PRBD row into one recoverable sale lot."""
    if row.source_table != _TABLE:
        raise NormalizationContractError(expected_table=_TABLE, actual_table=row.source_table)

    product_id = parse_identifier(
        row, "pd_no", rule_id="bond.product_id", rule_version=_RULE_VERSION
    )
    exchange_market = _text(row, "pd_exg_mkt", "bond.exchange_market")
    info_base_date = _date(row, "info_base_dt", "bond.info_base_date")
    info_sequence = parse_integer(
        row,
        "info_seq",
        zero_status=_ZERO_STATUS,
        rule_id="bond.info_sequence",
        rule_version=_RULE_VERSION,
    )
    invalid_key = next(
        (
            (column, rule_id)
            for column, rule_id, valid in (
                ("pd_no", "bond.product_id", product_id.normalized_value is not None),
                (
                    "pd_exg_mkt",
                    "bond.exchange_market",
                    exchange_market.normalized_value is not None,
                ),
                (
                    "info_base_dt",
                    "bond.info_base_date",
                    info_base_date.normalized_value is not None,
                ),
                (
                    "info_seq",
                    "bond.info_sequence",
                    info_sequence.normalized_value is not None
                    and info_sequence.normalized_value > 0,
                ),
            )
            if not valid
        ),
        None,
    )
    if invalid_key is not None:
        column, rule_id = invalid_key
        return NormalizationResult[BondSaleLot](
            record=None,
            issues=(
                DataQualityIssue.from_row(
                    row,
                    column,
                    rule_id=rule_id,
                    rule_version=_RULE_VERSION,
                    severity=IssueSeverity.BLOCKER,
                    quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
                    reason="Domestic bond sale-lot identity is invalid.",
                    quarantined=True,
                ),
            ),
        )

    name = _text(row, "pd_nm", "bond.name")
    short_name = _text(row, "pd_abrv_nm", "bond.short_name")
    currency = _currency(row)
    bond_kind_raw = _text(row, "bd_knd", "bond.bond_kind_raw")
    issue_date = _date(row, "isu_dt", "bond.issue_date")
    maturity_date = _date(row, "mat_dt", "bond.maturity_date", allow_max_sentinel=True)
    source_update_date = _date(row, "pd_std_info_update", "bond.source_update_date")
    coupon_rate = _decimal(row, "srfc_irt", "bond.coupon_rate")
    buy_yield = _decimal(row, "buy_yield", "bond.buy_yield")
    buyable_quantity = _decimal(row, "buyable_quantity", "bond.buyable_quantity.raw_only")
    source_remaining_days = parse_integer(
        row,
        "remaining_days",
        zero_status=_ZERO_STATUS,
        rule_id="bond.source_remaining_days",
        rule_version=_RULE_VERSION,
    )
    credit_rating = _text(row, "crd_grd", "bond.credit_rating")
    credit_rating_date = _date(row, "crd_grd_dt", "bond.credit_rating_date")
    duration = _decimal(row, "dur", "bond.duration")
    evaluation_price = _decimal(row, "eval_price", "bond.evaluation_price")
    trade_price = _decimal(row, "trade_price", "bond.trade_price")

    issues: list[DataQualityIssue] = []
    for wrapped, column_name, rule_id in (
        (issue_date, "isu_dt", "bond.issue_date"),
        (maturity_date, "mat_dt", "bond.maturity_date"),
        (source_update_date, "pd_std_info_update", "bond.source_update_date"),
        (coupon_rate, "srfc_irt", "bond.coupon_rate"),
        (buy_yield, "buy_yield", "bond.buy_yield"),
        (buyable_quantity, "buyable_quantity", "bond.buyable_quantity.raw_only"),
        (source_remaining_days, "remaining_days", "bond.source_remaining_days"),
        (credit_rating_date, "crd_grd_dt", "bond.credit_rating_date"),
        (duration, "dur", "bond.duration"),
        (evaluation_price, "eval_price", "bond.evaluation_price"),
        (trade_price, "trade_price", "bond.trade_price"),
    ):
        if wrapped.quality_status is QualityStatus.INVALID_FORMAT:
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
                "curr_cd",
                rule_id="bond.currency",
                quality_status=QualityStatus.OUT_OF_DOMAIN,
                reason="Domestic bond currency is outside the source domain.",
            )
        )

    lot = BondSaleLot(
        source_row=row,
        source_key=BondSaleLotKey(
            product_id=product_id.raw_value,
            exchange_market=exchange_market.raw_value,
            info_base_date=info_base_date.raw_value,
            info_seq=info_sequence.raw_value,
            source_row_number=row.source_row_number,
        ),
        product_id=product_id,
        exchange_market=exchange_market,
        info_base_date=info_base_date,
        info_sequence=info_sequence,
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
        credit_rating_date=credit_rating_date,
        duration=duration,
        evaluation_price=evaluation_price,
        trade_price=trade_price,
    )
    return NormalizationResult[BondSaleLot](record=lot, issues=tuple(issues))


def project_bond_instrument(
    lots: Sequence[BondSaleLot], *, as_of: date
) -> NormalizationResult[BondInstrument]:
    """Collapse one instrument's lots with a deterministic same-lot quote."""
    materialized = tuple(lots)
    if not materialized or any(type(lot) is not BondSaleLot for lot in materialized):
        raise TypeError("bond projection requires sale lots")
    if type(as_of) is not date:
        raise TypeError("bond projection requires an exact date")
    product_ids = {lot.product_id.normalized_value for lot in materialized}
    if len(product_ids) != 1 or None in product_ids:
        raise ValueError("bond projection requires one product")
    source_keys = tuple(lot.source_key for lot in materialized)
    if len(set(source_keys)) != len(source_keys):
        raise ValueError("bond projection requires unique source keys")

    ordered = tuple(sorted(materialized, key=_lot_order_key))
    valid_yields = tuple(lot for lot in ordered if lot.buy_yield.normalized_value is not None)
    selected = (
        min(
            valid_yields,
            key=lambda lot: (-_required_decimal(lot.buy_yield), _lot_order_key(lot)),
        )
        if valid_yields
        else ordered[0]
    )
    issues: list[DataQualityIssue] = []
    parent_values: dict[str, NormalizedValue[Any]] = {}
    field_sources: list[BondFieldSources] = []
    for field_name in _PARENT_FIELDS:
        projected, sources, conflict = _project_parent_value(ordered, field_name)
        parent_values[field_name] = projected
        field_sources.append(BondFieldSources(field_name=field_name, sources=sources))
        if conflict:
            column_name = sources[0].source_column_name
            issues.append(
                _warning_issue(
                    ordered[0].source_row,
                    column_name,
                    rule_id=f"bond.parent_field_conflict.{field_name}",
                    quality_status=QualityStatus.MIXED_SOURCE_VALUES,
                    reason="Bond sale lots disagree on a parent-level field.",
                )
            )

    maturity = parent_values["maturity_date"]
    issue = parent_values["issue_date"]
    remaining_days, matured = _derive_maturity(maturity, as_of)
    purchasable = _derive_purchaseability(issue, maturity, as_of)
    if maturity.normalized_value is None:
        issues.append(
            _warning_issue(
                ordered[0].source_row,
                "mat_dt",
                rule_id="bond.purchaseability_unverifiable_end",
                quality_status=maturity.quality_status,
                reason=(
                    "Bond end state is not source-verifiable; purchaseability uses the "
                    "organizer assumption."
                ),
            )
        )
    yield_values = tuple(_required_decimal(lot.buy_yield) for lot in valid_yields)
    yield_sources = tuple(lot.buy_yield.source for lot in valid_yields)
    yield_range = DerivedValue[tuple[Decimal, Decimal]](
        value=(min(yield_values), max(yield_values)) if yield_values else None,
        quality_status=(QualityStatus.VALID if yield_values else selected.buy_yield.quality_status),
        rule_id="bond.buy_yield_range",
        rule_version=_RULE_VERSION,
        as_of_date=as_of,
        inputs=yield_sources or (selected.buy_yield.source,),
    )
    record = BondInstrument(
        selected_lot_key=selected.source_key,
        field_sources=tuple(field_sources),
        product_id=ordered[0].product_id,
        name=parent_values["name"],
        short_name=parent_values["short_name"],
        currency=parent_values["currency"],
        bond_kind_raw=parent_values["bond_kind_raw"],
        issue_date=issue,
        maturity_date=maturity,
        source_update_date=parent_values["source_update_date"],
        coupon_rate=parent_values["coupon_rate"],
        buy_yield=selected.buy_yield,
        source_remaining_days=selected.source_remaining_days,
        credit_rating=parent_values["credit_rating"],
        credit_rating_date=parent_values["credit_rating_date"],
        duration=selected.duration,
        evaluation_price=selected.evaluation_price,
        trade_price=selected.trade_price,
        remaining_days_at_as_of=remaining_days,
        is_matured_at_as_of=matured,
        is_purchasable_at_as_of=purchasable,
        buy_yield_range=yield_range,
    )
    return NormalizationResult[BondInstrument](record=record, issues=tuple(issues))


def normalize_bond(
    row: SourceRow,
    as_of: date,
    _rating_registry: RatingRegistry,
) -> NormalizationResult[BondInstrument]:
    """Compatibility wrapper for one-row callers until grouped artifact staging migrates."""
    lot_result = normalize_bond_lot(row)
    if lot_result.record is None:
        return NormalizationResult[BondInstrument](record=None, issues=lot_result.issues)
    projection = project_bond_instrument((lot_result.record,), as_of=as_of)
    return NormalizationResult[BondInstrument](
        record=projection.record,
        issues=tuple(dict.fromkeys((*lot_result.issues, *projection.issues))),
    )


def _project_parent_value(
    lots: tuple[BondSaleLot, ...], field_name: str
) -> tuple[NormalizedValue[Any], tuple[SourceCellLocator, ...], bool]:
    values = tuple(
        sorted(
            (getattr(lot, field_name) for lot in lots),
            key=lambda value: (
                value.source.source_row_number,
                value.source.source_column_number,
            ),
        )
    )
    representative = values[0]
    sources = tuple(value.source for value in values)
    raw_values = {value.raw_value for value in values}
    if len(raw_values) == 1:
        return representative, sources, False
    return (
        NormalizedValue[Any](
            raw_value=representative.raw_value,
            normalized_value=None,
            quality_status=QualityStatus.MIXED_SOURCE_VALUES,
            rule_id=f"bond.parent_field_conflict.{field_name}",
            rule_version=_RULE_VERSION,
            source=representative.source,
        ),
        sources,
        True,
    )


def _lot_order_key(lot: BondSaleLot) -> tuple[str, str, str, int, int]:
    sequence = lot.info_sequence.normalized_value
    if sequence is None:
        raise ValueError("bond lot sequence differs")
    return (
        lot.source_key.product_id,
        lot.source_key.exchange_market,
        lot.source_key.info_base_date,
        sequence,
        lot.source_key.source_row_number,
    )


def _required_decimal(value: NormalizedValue[Decimal]) -> Decimal:
    if value.normalized_value is None:
        raise ValueError("bond decimal differs")
    return value.normalized_value


def _derive_maturity(
    maturity_date: NormalizedValue[Any], as_of: date
) -> tuple[DerivedValue[int], DerivedValue[bool]]:
    maturity = maturity_date.normalized_value
    if type(maturity) is date:
        remaining = (maturity - as_of).days
        status = QualityStatus.VALID
    else:
        remaining = None
        status = maturity_date.quality_status
    inputs = (maturity_date.source,)
    return (
        DerivedValue[int](
            value=remaining,
            quality_status=status,
            rule_id="bond.remaining_days_at_as_of",
            rule_version=_RULE_VERSION,
            as_of_date=as_of,
            inputs=inputs,
        ),
        DerivedValue[bool](
            value=None if remaining is None else remaining < 0,
            quality_status=status,
            rule_id="bond.is_matured_at_as_of",
            rule_version=_RULE_VERSION,
            as_of_date=as_of,
            inputs=inputs,
        ),
    )


def _derive_purchaseability(
    issue_date: NormalizedValue[Any],
    maturity_date: NormalizedValue[Any],
    as_of: date,
) -> DerivedValue[bool]:
    issue = issue_date.normalized_value
    maturity = maturity_date.normalized_value
    not_yet_issued = type(issue) is date and issue > as_of
    ended = type(maturity) is date and maturity < as_of
    return DerivedValue[bool](
        value=not (not_yet_issued or ended),
        quality_status=QualityStatus.VALID,
        rule_id="bond.is_purchasable_at_as_of.organizer_override",
        rule_version=_RULE_VERSION,
        as_of_date=as_of,
        inputs=(issue_date.source, maturity_date.source),
    )


def _text(row: SourceRow, column_name: str, rule_id: str) -> NormalizedValue[str]:
    return parse_text(row, column_name, rule_id=rule_id, rule_version=_RULE_VERSION)


def _currency(row: SourceRow) -> NormalizedValue[str]:
    raw_value = row.cell("curr_cd").raw_value
    if not raw_value.strip():
        return _text(row, "curr_cd", "bond.currency")
    normalized = raw_value if re.fullmatch(r"[A-Z]{3}", raw_value, re.ASCII) else None
    return make_normalized_value(
        row,
        "curr_cd",
        normalized_value=normalized,
        quality_status=(
            QualityStatus.VALID if normalized is not None else QualityStatus.OUT_OF_DOMAIN
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


def _decimal(row: SourceRow, column_name: str, rule_id: str) -> NormalizedValue[Decimal]:
    return parse_decimal(
        row,
        column_name,
        zero_status=_ZERO_STATUS,
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
