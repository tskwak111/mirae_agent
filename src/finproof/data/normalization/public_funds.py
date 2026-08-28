"""Pure refreshed public-fund item normalization with exact source lineage."""

from decimal import Decimal
from typing import NoReturn

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.numeric import parse_decimal, parse_integer
from finproof.data.normalization.text import (
    parse_identifier,
    parse_literal_null_text,
    parse_text,
)
from finproof.data.normalization.value_factory import make_normalized_value
from finproof.domain.normalization import NormalizationResult
from finproof.domain.public_funds import PUBLIC_FUND_SOURCE_COLUMNS, PublicFundItem
from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

_TABLE = "PRFD01N001"
_RULE_VERSION = "1.0.0"
_RETIRED_PATH_MESSAGE = "public-fund source-row grouping/collapse path is retired"


def classify_public_fund_row(row: SourceRow) -> NoReturn:
    del row
    raise RuntimeError(_RETIRED_PATH_MESSAGE)


def normalize_fund_attribute(row: object) -> NoReturn:
    del row
    raise RuntimeError(_RETIRED_PATH_MESSAGE)


def collapse_fund_items(rows: object) -> NoReturn:
    del rows
    raise RuntimeError(_RETIRED_PATH_MESSAGE)


def normalize_public_funds(rows: object) -> NoReturn:
    del rows
    raise RuntimeError(_RETIRED_PATH_MESSAGE)


def normalize_public_fund_item_group(rows: object) -> NoReturn:
    del rows
    raise RuntimeError(_RETIRED_PATH_MESSAGE)


def normalize_public_fund_item(
    row: SourceRow,
) -> NormalizationResult[PublicFundItem]:
    """Normalize one refreshed public-fund source row directly to item grain."""
    fund_item_id = _validate_item_key(row)
    if fund_item_id.normalized_value is None:
        return NormalizationResult[PublicFundItem](
            record=None,
            issues=(
                _quarantined_key_issue(
                    row,
                    "itm_no",
                    rule_id="public_fund.malformed_item",
                    reason="Public-fund item identifier has an invalid source format.",
                ),
            ),
        )

    raw_attribute_codes = row.cell("prfd_attr_cds").raw_value
    attribute_codes = () if raw_attribute_codes == "" else tuple(raw_attribute_codes.split(","))
    attribute_count = parse_integer(
        row,
        "prfd_attr_cnt",
        zero_status=QualityStatus.RECORDED_ZERO,
        rule_id="public_fund.attribute_count",
        rule_version=_RULE_VERSION,
    )
    record = PublicFundItem(
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
        attribute_codes=attribute_codes,
        attribute_count=attribute_count,
        attribute_search_text=_text(row, "prfd_attr_search_text", "attribute_search_text"),
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
    if attribute_count.quality_status is QualityStatus.INVALID_FORMAT:
        issues.append(
            _warning_issue(
                row,
                "prfd_attr_cnt",
                rule_id=attribute_count.rule_id,
                quality_status=QualityStatus.INVALID_FORMAT,
                reason="Public-fund attribute count is invalid.",
            )
        )
    elif attribute_count.normalized_value != len(attribute_codes):
        issues.append(
            _warning_issue(
                row,
                "prfd_attr_cnt",
                rule_id="public_fund.attribute_count_mismatch",
                quality_status=QualityStatus.MIXED_SOURCE_VALUES,
                reason="Public-fund attribute count differs from the comma-split list.",
            )
        )
    return NormalizationResult[PublicFundItem](
        record=record,
        issues=tuple(sorted(issues, key=_issue_sort_key)),
    )


def _validate_item_key(row: SourceRow) -> NormalizedValue[str]:
    if row.source_table != _TABLE:
        raise NormalizationContractError(
            expected_table=_TABLE,
            actual_table=row.source_table,
        )
    return parse_identifier(
        row,
        "itm_no",
        rule_id="public_fund.fund_item_id",
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
    if column_name not in PUBLIC_FUND_SOURCE_COLUMNS:
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
