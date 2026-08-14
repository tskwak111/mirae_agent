"""Pure public-fund attribute-row normalization with exact source lineage."""

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.numeric import parse_decimal
from finproof.data.normalization.text import (
    parse_identifier,
    parse_literal_null_text,
    parse_text,
)
from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.locators import SourceCellLocator
from finproof.domain.normalization import NormalizationResult
from finproof.domain.public_funds import (
    FUND_ATTRIBUTE_FIELD_COLUMNS,
    FUND_ITEM_FIELD_COLUMNS,
    FundAttributeRow,
    FundCollapseResult,
    FundItem,
    FundItemAttribute,
    FundItemValue,
)
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

_TABLE = "PRFD01N001"
_RULE_VERSION = "1.0.0"
_COLLAPSE_ISSUE_REASONS = {
    "public_fund.attribute_key.raw_duplicate": (
        "Public-fund raw item-attribute key is duplicated."
    ),
    "public_fund.attribute_key.normalized_collision": (
        "Public-fund attribute values collide after normalization."
    ),
    "public_fund.item.non_attribute_disagreement": (
        "Public-fund non-attribute source values disagree within one item."
    ),
}


def normalize_fund_attribute(
    row: SourceRow,
) -> NormalizationResult[FundAttributeRow]:
    """Normalize one verified public-fund source row without performing I/O."""
    fund_item_id, attribute_code, key_issue = _validate_fund_keys(row)
    if key_issue is not None:
        return NormalizationResult[FundAttributeRow](record=None, issues=(key_issue,))
    if attribute_code is None:
        raise RuntimeError("validated public-fund attribute key is unexpectedly missing")

    record = FundAttributeRow(
        source_row=row,
        benchmark_english_name=_text(row, "bmrk_eng_nm", "benchmark_english_name"),
        benchmark_name=_text(row, "bmrk_nm", "benchmark_name"),
        currency=_currency(row),
        exchange_traded_flag_raw=_text(row, "exchdg_yn", "exchange_traded_flag_raw"),
        establishment_country_code=_text(row, "fd_estb_ctry_cd", "establishment_country_code"),
        region_description=_text(row, "fd_ivst_rgn_desc", "region_description"),
        return_18m=_registered_return(row, "fd_mm18_ern_r", "return_18m"),
        return_1m=_decimal(row, "fd_mm1_ern_r", "return_1m"),
        return_3m=_decimal(row, "fd_mm3_ern_r", "return_3m"),
        return_6m=_decimal(row, "fd_mm6_ern_r", "return_6m"),
        net_assets=_decimal(row, "fd_nast_suma", "net_assets"),
        establishment_type_code=_text(row, "fd_set_pcd", "establishment_type_code"),
        return_1w=_decimal(row, "fd_wk1_ern_r", "return_1w"),
        return_1y=_decimal(row, "fd_yr1_ern_r", "return_1y"),
        return_2y=_registered_return(row, "fd_yr2_ern_r", "return_2y"),
        return_3y=_registered_return(row, "fd_yr3_ern_r", "return_3y"),
        return_5y=_registered_return(row, "fd_yr5_ern_r", "return_5y"),
        foreign_base_price_flag_raw=_text(row, "frc_bpr_itm_yn", "foreign_base_price_flag_raw"),
        fss_item_id=_text(row, "fss_itm_no", "fss_item_id"),
        hedge_fund_flag_raw=_text(row, "hdge_fd_yn", "hedge_fund_flag_raw"),
        interest_dividend_description=_text(row, "int_dvd_desc", "interest_dividend_description"),
        short_name=_text(row, "itm_abrv_nm", "short_name"),
        english_short_name=_text(row, "itm_eabrv_nm", "english_short_name"),
        english_name=_text(row, "itm_eng_nm", "english_name"),
        name=_text(row, "itm_nm", "name"),
        fund_item_id=fund_item_id,
        kofia_classification_code=_text(row, "kofia_fd_ccd", "kofia_classification_code"),
        ksd_id=_text(row, "ksd_itm_no", "ksd_id"),
        manager_item_id=_text(row, "mtco_itm_no", "manager_item_id"),
        offshore_fund_flag_raw=_text(row, "ofsfd_yn", "offshore_fund_flag_raw"),
        fund_type_raw=_fund_type(row),
        manager_external_code=_text(row, "or_co_xtn_itt_cd", "manager_external_code"),
        overseas_fund_description=_text(row, "ovrs_fd_desc", "overseas_fund_description"),
        investor_type_description=_text(row, "pers_corp_desc", "investor_type_description"),
        professional_sale_control_code=_text(
            row, "pfiv_sale_cntl_tcd", "professional_sale_control_code"
        ),
        attribute_code=attribute_code,
        private_fund_description=_text(row, "prvo_fd_desc", "private_fund_description"),
        offering_type_description=_text(row, "prvo_pbff_desc", "offering_type_description"),
        family_candidate_key=_text(row, "rptt_ksd_itm_no", "family_candidate_key"),
        sale_status_raw=_text(row, "sale_yn", "sale_status_raw"),
        standard_item_id=_text(row, "std_itm_no", "standard_item_id"),
        mirae_sale_flag_raw=_text(row, "thco_sale_yn", "mirae_sale_flag_raw"),
        trustee_external_code=_text(row, "trusc_xtn_itt_cd", "trustee_external_code"),
        risk_code=_risk_text(row, "zrin_fd_ivst_risk_gcd", "risk_code"),
        risk_name=_risk_text(row, "zrin_fd_ivst_risk_grd_nm", "risk_name"),
    )
    numeric_fields = (
        record.return_18m,
        record.return_1m,
        record.return_3m,
        record.return_6m,
        record.net_assets,
        record.return_1w,
        record.return_1y,
        record.return_2y,
        record.return_3y,
        record.return_5y,
    )
    issues = [
        _warning_issue(
            row,
            wrapped.source.source_column_name,
            rule_id=wrapped.rule_id,
            quality_status=QualityStatus.INVALID_FORMAT,
            reason="Public-fund numeric value is invalid.",
        )
        for wrapped in numeric_fields
        if wrapped.quality_status is QualityStatus.INVALID_FORMAT
    ]
    issues.extend(
        _warning_issue(
            row,
            wrapped.source.source_column_name,
            rule_id=wrapped.rule_id,
            quality_status=QualityStatus.OUT_OF_DOMAIN,
            reason="Public-fund return is below the registered comparison domain.",
        )
        for wrapped in numeric_fields
        if wrapped.quality_status is QualityStatus.OUT_OF_DOMAIN
    )
    if record.currency.quality_status is QualityStatus.OUT_OF_DOMAIN:
        issues.append(
            _warning_issue(
                row,
                "curr_cd",
                rule_id=record.currency.rule_id,
                quality_status=QualityStatus.OUT_OF_DOMAIN,
                reason="Public-fund currency is invalid.",
            )
        )
    if record.fund_type_raw.quality_status is QualityStatus.MIXED_SOURCE_VALUES:
        issues.append(
            _warning_issue(
                row,
                "or_attr_desc",
                rule_id=record.fund_type_raw.rule_id,
                quality_status=QualityStatus.MIXED_SOURCE_VALUES,
                reason="Public-fund type code has mixed source semantics.",
            )
        )
    return NormalizationResult[FundAttributeRow](
        record=record,
        issues=tuple(sorted(issues, key=_issue_sort_key)),
    )


def collapse_fund_items(rows: Iterable[FundAttributeRow]) -> FundCollapseResult:
    """Collapse pre-normalized attribute rows into stable item-grain records."""
    groups: dict[str, list[FundAttributeRow]] = defaultdict(list)
    issue_order: dict[tuple[object, ...], tuple[str, str]] = {}
    for row in rows:
        item_key = row.fund_item_id.normalized_value
        if item_key is None:
            raise ValueError("normalized public-fund row must have an item key")
        groups[item_key].append(row)
        issue_order[_source_issue_identity(row.source_row)] = (item_key, "")

    items: list[FundItem] = []
    attributes: list[FundItemAttribute] = []
    issues: list[DataQualityIssue] = []
    for item_key in sorted(groups):
        group = tuple(sorted(groups[item_key], key=lambda row: row.source_row.source_row_number))
        item, group_attributes, group_issues = _collapse_one_group(group)
        if item is not None:
            items.append(item)
        attributes.extend(group_attributes)
        issues.extend(group_issues)

    attributes.sort(key=_attribute_sort_key)
    return FundCollapseResult(
        items=tuple(items),
        attributes=tuple(attributes),
        issues=_ordered_issues(issues, issue_order),
    )


def normalize_public_funds(rows: Iterable[SourceRow]) -> FundCollapseResult:
    """Normalize and collapse all rows while retaining only source rows globally."""
    source_groups: dict[str, list[SourceRow]] = defaultdict(list)
    issues: list[DataQualityIssue] = []
    issue_order: dict[tuple[object, ...], tuple[str, str]] = {}
    for row in rows:
        fund_item_id, _attribute_code_value, key_issue = _validate_fund_keys(row)
        normalized_item_key = fund_item_id.normalized_value
        issue_order[_source_issue_identity(row)] = (
            normalized_item_key or "",
            "" if normalized_item_key is not None else row.cell("itm_no").raw_value,
        )
        if key_issue is not None:
            issues.append(key_issue)
            continue
        item_key = normalized_item_key
        if item_key is None:
            raise RuntimeError("validated public-fund item key is unexpectedly missing")
        source_groups[item_key].append(row)

    items: list[FundItem] = []
    attributes: list[FundItemAttribute] = []
    for item_key in sorted(source_groups):
        item, group_attributes, group_issues = _normalize_and_collapse_source_group(
            tuple(
                sorted(
                    source_groups[item_key],
                    key=lambda source_row: source_row.source_row_number,
                )
            )
        )
        if item is not None:
            items.append(item)
        attributes.extend(group_attributes)
        issues.extend(group_issues)

    attributes.sort(key=_attribute_sort_key)
    return FundCollapseResult(
        items=tuple(items),
        attributes=tuple(attributes),
        issues=_ordered_issues(issues, issue_order),
    )


def _normalize_and_collapse_source_group(
    rows: tuple[SourceRow, ...],
) -> tuple[FundItem | None, tuple[FundItemAttribute, ...], tuple[DataQualityIssue, ...]]:
    normalized_rows: list[FundAttributeRow] = []
    issues: list[DataQualityIssue] = []
    for row in rows:
        result = normalize_fund_attribute(row)
        if result.record is None:
            raise RuntimeError("validated public-fund key failed during full normalization")
        normalized_rows.append(result.record)
        issues.extend(result.issues)
    item, attributes, collapse_issues = _collapse_one_group(tuple(normalized_rows))
    issues.extend(collapse_issues)
    return item, attributes, tuple(issues)


def _collapse_one_group(
    rows: tuple[FundAttributeRow, ...],
) -> tuple[
    FundItem | None,
    tuple[FundItemAttribute, ...],
    tuple[DataQualityIssue, ...],
]:
    if not rows:
        raise ValueError("public-fund collapse group must not be empty")
    issues = tuple(
        sorted(
            (*_attribute_key_issues(rows), *_non_attribute_disagreement_issues(rows)),
            key=_collapse_issue_local_sort_key,
        )
    )
    if issues:
        return None, (), issues
    source_rows = tuple(row.source_row for row in rows)
    item = FundItem(
        contributing_rows=source_rows,
        benchmark_english_name=_item_value(rows, "benchmark_english_name"),
        benchmark_name=_item_value(rows, "benchmark_name"),
        currency=_item_value(rows, "currency"),
        exchange_traded_flag_raw=_item_value(rows, "exchange_traded_flag_raw"),
        establishment_country_code=_item_value(rows, "establishment_country_code"),
        region_description=_item_value(rows, "region_description"),
        return_18m=_item_value(rows, "return_18m"),
        return_1m=_item_value(rows, "return_1m"),
        return_3m=_item_value(rows, "return_3m"),
        return_6m=_item_value(rows, "return_6m"),
        net_assets=_item_value(rows, "net_assets"),
        establishment_type_code=_item_value(rows, "establishment_type_code"),
        return_1w=_item_value(rows, "return_1w"),
        return_1y=_item_value(rows, "return_1y"),
        return_2y=_item_value(rows, "return_2y"),
        return_3y=_item_value(rows, "return_3y"),
        return_5y=_item_value(rows, "return_5y"),
        foreign_base_price_flag_raw=_item_value(rows, "foreign_base_price_flag_raw"),
        fss_item_id=_item_value(rows, "fss_item_id"),
        hedge_fund_flag_raw=_item_value(rows, "hedge_fund_flag_raw"),
        interest_dividend_description=_item_value(rows, "interest_dividend_description"),
        short_name=_item_value(rows, "short_name"),
        english_short_name=_item_value(rows, "english_short_name"),
        english_name=_item_value(rows, "english_name"),
        name=_item_value(rows, "name"),
        fund_item_id=_item_value(rows, "fund_item_id"),
        kofia_classification_code=_item_value(rows, "kofia_classification_code"),
        ksd_id=_item_value(rows, "ksd_id"),
        manager_item_id=_item_value(rows, "manager_item_id"),
        offshore_fund_flag_raw=_item_value(rows, "offshore_fund_flag_raw"),
        fund_type_raw=_item_value(rows, "fund_type_raw"),
        manager_external_code=_item_value(rows, "manager_external_code"),
        overseas_fund_description=_item_value(rows, "overseas_fund_description"),
        investor_type_description=_item_value(rows, "investor_type_description"),
        professional_sale_control_code=_item_value(rows, "professional_sale_control_code"),
        private_fund_description=_item_value(rows, "private_fund_description"),
        offering_type_description=_item_value(rows, "offering_type_description"),
        family_candidate_key=_item_value(rows, "family_candidate_key"),
        sale_status_raw=_item_value(rows, "sale_status_raw"),
        standard_item_id=_item_value(rows, "standard_item_id"),
        mirae_sale_flag_raw=_item_value(rows, "mirae_sale_flag_raw"),
        trustee_external_code=_item_value(rows, "trustee_external_code"),
        risk_code=_item_value(rows, "risk_code"),
        risk_name=_item_value(rows, "risk_name"),
    )
    attributes = tuple(
        sorted(
            (
                FundItemAttribute(
                    fund_item_id=row.fund_item_id,
                    attribute_code=row.attribute_code,
                )
                for row in rows
            ),
            key=_attribute_sort_key,
        )
    )
    return item, attributes, ()


def _attribute_key_issues(
    rows: tuple[FundAttributeRow, ...],
) -> tuple[DataQualityIssue, ...]:
    raw_groups: dict[str, list[FundAttributeRow]] = defaultdict(list)
    normalized_groups: dict[str, list[FundAttributeRow]] = defaultdict(list)
    for row in rows:
        normalized_code = row.attribute_code.normalized_value
        if normalized_code is None:
            raise ValueError("normalized public-fund row must have an attribute key")
        raw_groups[row.attribute_code.raw_value].append(row)
        normalized_groups[normalized_code].append(row)

    issues: list[DataQualityIssue] = []
    for participants in raw_groups.values():
        if len(participants) > 1:
            issues.extend(
                _collapse_issue(
                    row.source_row,
                    "prfd_attr_cd",
                    rule_id="public_fund.attribute_key.raw_duplicate",
                )
                for row in participants
            )
    for participants in normalized_groups.values():
        if len({row.attribute_code.raw_value for row in participants}) > 1:
            issues.extend(
                _collapse_issue(
                    row.source_row,
                    "prfd_attr_cd",
                    rule_id="public_fund.attribute_key.normalized_collision",
                )
                for row in participants
            )
    return tuple(sorted(issues, key=_collapse_issue_local_sort_key))


def _non_attribute_disagreement_issues(
    rows: tuple[FundAttributeRow, ...],
) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    for column_name in FUND_ITEM_FIELD_COLUMNS.values():
        raw_values = {row.source_row.cell(column_name).raw_value for row in rows}
        if len(raw_values) <= 1:
            continue
        issues.extend(
            _collapse_issue(
                row.source_row,
                column_name,
                rule_id="public_fund.item.non_attribute_disagreement",
            )
            for row in rows
        )
    return tuple(sorted(issues, key=_collapse_issue_local_sort_key))


def _collapse_issue(
    row: SourceRow,
    column_name: str,
    *,
    rule_id: str,
) -> DataQualityIssue:
    return DataQualityIssue.from_row(
        row,
        column_name,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        severity=IssueSeverity.HIGH,
        quality_status=QualityStatus.MIXED_SOURCE_VALUES,
        reason=_COLLAPSE_ISSUE_REASONS[rule_id],
        quarantined=True,
    )


def _collapse_issue_local_sort_key(
    issue: DataQualityIssue,
) -> tuple[int, int, str, str]:
    return (
        issue.source.source_row_number,
        issue.source.source_column_number,
        issue.rule_id,
        issue.issue_id,
    )


def _source_issue_identity(row: SourceRow) -> tuple[object, ...]:
    return (row.source_file, row.source_sheet, row.source_row_number)


def _ordered_issues(
    issues: Iterable[DataQualityIssue],
    order: dict[tuple[object, ...], tuple[str, str]],
) -> tuple[DataQualityIssue, ...]:
    materialized = tuple(issues)
    issue_ids = tuple(issue.issue_id for issue in materialized)
    if len(set(issue_ids)) != len(issue_ids):
        raise ValueError("public-fund issue IDs must be unique")

    def total_key(issue: DataQualityIssue) -> tuple[str, str, int, int, str, str]:
        identity = (
            issue.source.source_file,
            issue.source.source_sheet,
            issue.source.source_row_number,
        )
        try:
            normalized_item_key, quarantine_raw_item_key = order[identity]
        except KeyError as error:
            raise ValueError("public-fund issue source row is not registered") from error
        return (
            normalized_item_key,
            quarantine_raw_item_key,
            issue.source.source_row_number,
            issue.source.source_column_number,
            issue.rule_id,
            issue.issue_id,
        )

    return tuple(sorted(materialized, key=total_key))


def _item_value[ValueT](
    rows: tuple[FundAttributeRow, ...],
    field_name: str,
) -> FundItemValue[ValueT]:
    representative = getattr(rows[0], field_name)
    column_name = FUND_ITEM_FIELD_COLUMNS[field_name]
    return FundItemValue[ValueT](
        representative=representative,
        equivalent_sources=tuple(
            SourceCellLocator.from_row(row.source_row, column_name) for row in rows
        ),
    )


def _attribute_sort_key(attribute: FundItemAttribute) -> tuple[str, str, str, int]:
    return (
        attribute.fund_item_id.normalized_value or "",
        attribute.attribute_code.normalized_value or "",
        attribute.attribute_code.raw_value,
        attribute.attribute_code.source.source_row_number,
    )


def _validate_fund_keys(
    row: SourceRow,
) -> tuple[
    NormalizedValue[str],
    NormalizedValue[str] | None,
    DataQualityIssue | None,
]:
    if row.source_table != _TABLE:
        raise NormalizationContractError(
            expected_table=_TABLE,
            actual_table=row.source_table,
        )
    fund_item_id = parse_identifier(
        row,
        "itm_no",
        rule_id="public_fund.fund_item_id",
        rule_version=_RULE_VERSION,
    )
    if fund_item_id.normalized_value is None:
        issue = _quarantined_key_issue(
            row,
            "itm_no",
            rule_id="public_fund.malformed_item",
            reason="Public-fund item identifier has an invalid source format.",
        )
        return fund_item_id, None, issue
    attribute_code = _attribute_code(row)
    if attribute_code.normalized_value is None:
        issue = _quarantined_key_issue(
            row,
            "prfd_attr_cd",
            rule_id="public_fund.malformed_attribute",
            reason="Public-fund attribute code is blank.",
        )
        return fund_item_id, attribute_code, issue
    return fund_item_id, attribute_code, None


def _attribute_code(row: SourceRow) -> NormalizedValue[str]:
    raw_value = row.cell("prfd_attr_cd").raw_value
    normalized_value = raw_value.strip() or None
    return make_normalized_value(
        row,
        "prfd_attr_cd",
        normalized_value=normalized_value,
        quality_status=(
            QualityStatus.VALID
            if normalized_value is not None
            else QualityStatus.MALFORMED_SOURCE_ROW
        ),
        rule_id="public_fund.attribute_code",
        rule_version=_RULE_VERSION,
    )


def _text(row: SourceRow, column_name: str, field_name: str) -> NormalizedValue[str]:
    return parse_text(
        row,
        column_name,
        rule_id=f"public_fund.{field_name}",
        rule_version=_RULE_VERSION,
    )


def _decimal(
    row: SourceRow,
    column_name: str,
    field_name: str,
) -> NormalizedValue[Decimal]:
    return parse_decimal(
        row,
        column_name,
        zero_status=QualityStatus.RECORDED_ZERO,
        rule_id=f"public_fund.{field_name}",
        rule_version=_RULE_VERSION,
    )


def _registered_return(
    row: SourceRow,
    column_name: str,
    field_name: str,
) -> NormalizedValue[Decimal]:
    wrapped = _decimal(row, column_name, field_name)
    if wrapped.normalized_value is not None and wrapped.normalized_value < Decimal("-100"):
        return wrapped.model_copy(update={"quality_status": QualityStatus.OUT_OF_DOMAIN})
    return wrapped


def _currency(row: SourceRow) -> NormalizedValue[str]:
    raw_value = row.cell("curr_cd").raw_value
    if not raw_value.strip():
        return _text(row, "curr_cd", "currency")
    if raw_value in {"KRW", "USD"}:
        return make_normalized_value(
            row,
            "curr_cd",
            normalized_value=raw_value,
            quality_status=QualityStatus.VALID,
            rule_id="public_fund.currency",
            rule_version=_RULE_VERSION,
        )
    return make_normalized_value(
        row,
        "curr_cd",
        normalized_value=None,
        quality_status=QualityStatus.OUT_OF_DOMAIN,
        rule_id="public_fund.currency",
        rule_version=_RULE_VERSION,
    )


def _fund_type(row: SourceRow) -> NormalizedValue[str]:
    wrapped = _text(row, "or_attr_desc", "fund_type_raw")
    if wrapped.normalized_value != "06":
        return wrapped
    return make_normalized_value(
        row,
        "or_attr_desc",
        normalized_value="06",
        quality_status=QualityStatus.MIXED_SOURCE_VALUES,
        rule_id="public_fund.fund_type_unmapped_code",
        rule_version=_RULE_VERSION,
    )


def _risk_text(
    row: SourceRow,
    column_name: str,
    field_name: str,
) -> NormalizedValue[str]:
    return parse_literal_null_text(
        row,
        column_name,
        rule_id=f"public_fund.{field_name}",
        rule_version=_RULE_VERSION,
    )


def _issue_sort_key(issue: DataQualityIssue) -> tuple[int, int, str, str]:
    return (
        issue.source.source_row_number,
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
    if column_name not in FUND_ATTRIBUTE_FIELD_COLUMNS.values():
        raise ValueError("public-fund issue column must be declared")
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


def _quarantined_key_issue(
    row: SourceRow,
    column_name: str,
    *,
    rule_id: str,
    reason: str,
) -> DataQualityIssue:
    return DataQualityIssue.from_row(
        row,
        column_name,
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
        severity=IssueSeverity.BLOCKER,
        quality_status=QualityStatus.MALFORMED_SOURCE_ROW,
        reason=reason,
        quarantined=True,
    )
