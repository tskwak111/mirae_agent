"""Pure public-fund attribute-row normalization tests."""

from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import cast

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.public_funds import normalize_fund_attribute
from finproof.domain.locators import SourceCellLocator
from finproof.domain.public_funds import (
    FUND_ATTRIBUTE_FIELD_COLUMNS,
    FUND_ITEM_FIELD_COLUMNS,
)
from finproof.domain.quality import IssueSeverity, QualityStatus
from tests.helpers.source_rows import source_row

EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS = MappingProxyType(
    {
        "benchmark_english_name": "bmrk_eng_nm",
        "benchmark_name": "bmrk_nm",
        "currency": "curr_cd",
        "exchange_traded_flag_raw": "exchdg_yn",
        "establishment_country_code": "fd_estb_ctry_cd",
        "region_description": "fd_ivst_rgn_desc",
        "return_18m": "fd_mm18_ern_r",
        "return_1m": "fd_mm1_ern_r",
        "return_3m": "fd_mm3_ern_r",
        "return_6m": "fd_mm6_ern_r",
        "net_assets": "fd_nast_suma",
        "establishment_type_code": "fd_set_pcd",
        "return_1w": "fd_wk1_ern_r",
        "return_1y": "fd_yr1_ern_r",
        "return_2y": "fd_yr2_ern_r",
        "return_3y": "fd_yr3_ern_r",
        "return_5y": "fd_yr5_ern_r",
        "foreign_base_price_flag_raw": "frc_bpr_itm_yn",
        "fss_item_id": "fss_itm_no",
        "hedge_fund_flag_raw": "hdge_fd_yn",
        "interest_dividend_description": "int_dvd_desc",
        "short_name": "itm_abrv_nm",
        "english_short_name": "itm_eabrv_nm",
        "english_name": "itm_eng_nm",
        "name": "itm_nm",
        "fund_item_id": "itm_no",
        "kofia_classification_code": "kofia_fd_ccd",
        "ksd_id": "ksd_itm_no",
        "manager_item_id": "mtco_itm_no",
        "offshore_fund_flag_raw": "ofsfd_yn",
        "fund_type_raw": "or_attr_desc",
        "manager_external_code": "or_co_xtn_itt_cd",
        "overseas_fund_description": "ovrs_fd_desc",
        "investor_type_description": "pers_corp_desc",
        "professional_sale_control_code": "pfiv_sale_cntl_tcd",
        "attribute_code": "prfd_attr_cd",
        "private_fund_description": "prvo_fd_desc",
        "offering_type_description": "prvo_pbff_desc",
        "family_candidate_key": "rptt_ksd_itm_no",
        "sale_status_raw": "sale_yn",
        "standard_item_id": "std_itm_no",
        "mirae_sale_flag_raw": "thco_sale_yn",
        "trustee_external_code": "trusc_xtn_itt_cd",
        "risk_code": "zrin_fd_ivst_risk_gcd",
        "risk_name": "zrin_fd_ivst_risk_grd_nm",
    }
)


def test_fund_normalizer_rejects_wrong_table() -> None:
    """A source row from any other table must fail at the typed boundary."""
    with pytest.raises(NormalizationContractError, match="PRFD01N001"):
        normalize_fund_attribute(source_row("PREF02N001"))


def test_malformed_item_quarantines_before_shifted_payload_is_parsed() -> None:
    """A shifted row emits only its item blocker, never misleading payload issues."""
    row = source_row(
        "PRFD01N001",
        {
            "itm_no": '"',
            "prfd_attr_cd": "해외",
            "curr_cd": "",
            "fd_nast_suma": "not-a-number",
            "or_attr_desc": "06",
            "zrin_fd_ivst_risk_gcd": "00020054",
        },
        excel_row=84563,
    )

    result = normalize_fund_attribute(row)

    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.rule_id == "public_fund.malformed_item"
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quarantined is True
    assert issue.source.source_column_name == "itm_no"
    assert issue.source.source_row_number == 84563
    assert '"' not in issue.reason


@pytest.mark.parametrize("raw", ["", " ", "\t"])
def test_blank_attribute_key_quarantines_at_attribute_cell(raw: str) -> None:
    """A blank member of the source primary key blocks the row at that cell."""
    result = normalize_fund_attribute(source_row("PRFD01N001", {"prfd_attr_cd": raw}, excel_row=17))

    assert result.record is None
    assert len(result.issues) == 1
    assert result.issues[0].source.source_column_name == "prfd_attr_cd"
    assert result.issues[0].quarantined is True


def test_valid_fund_row_preserves_padded_attribute_and_all_45_source_cells() -> None:
    """Every source column maps once while padded attribute raw text survives."""
    row = source_row("PRFD01N001", {"prfd_attr_cd": "USA "}, excel_row=28)

    record = normalize_fund_attribute(row).record

    assert record is not None
    assert record.source_row is row
    assert record.fund_item_id.normalized_value == "KR5114601001"
    assert record.attribute_code.raw_value == "USA "
    assert record.attribute_code.normalized_value == "USA"
    for field_name, column_name in EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS.items():
        wrapped = getattr(record, field_name)
        cell = row.cell(column_name)
        assert wrapped.raw_value == cell.raw_value
        assert wrapped.source == SourceCellLocator.from_row(row, column_name)


def test_public_fund_field_maps_are_complete_exact_and_immutable() -> None:
    """Mapping drift cannot omit, duplicate, or dynamically rewrite source fields."""
    assert dict(FUND_ATTRIBUTE_FIELD_COLUMNS) == dict(EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS)
    assert dict(FUND_ITEM_FIELD_COLUMNS) == {
        field_name: column_name
        for field_name, column_name in EXPECTED_FUND_ATTRIBUTE_FIELD_COLUMNS.items()
        if field_name != "attribute_code"
    }
    assert len(set(FUND_ATTRIBUTE_FIELD_COLUMNS.values())) == 45
    with pytest.raises(TypeError):
        cast(dict[str, str], FUND_ATTRIBUTE_FIELD_COLUMNS)["name"] = "other"
    with pytest.raises(TypeError):
        cast(dict[str, str], FUND_ITEM_FIELD_COLUMNS)["name"] = "other"


def test_fund_currency_zero_risk_and_unmapped_type_policies_are_field_specific() -> None:
    """Field-specific missing and anomaly semantics must not leak into free text."""
    result = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            {
                "curr_cd": "USD",
                "fd_nast_suma": "0.0000",
                "fd_wk1_ern_r": "0",
                "zrin_fd_ivst_risk_gcd": "NULL",
                "zrin_fd_ivst_risk_grd_nm": "",
                "or_attr_desc": "06",
                "itm_nm": "NULL ETF 상장지수",
            },
        )
    )

    record = result.record
    assert record is not None
    assert record.currency.normalized_value == "USD"
    assert record.net_assets.quality_status is QualityStatus.RECORDED_ZERO
    assert record.return_1w.quality_status is QualityStatus.RECORDED_ZERO
    assert (record.risk_code.normalized_value, record.risk_code.quality_status) == (
        None,
        QualityStatus.MISSING_LITERAL_NULL,
    )
    assert (record.risk_name.normalized_value, record.risk_name.quality_status) == (
        None,
        QualityStatus.MISSING_BLANK,
    )
    assert record.fund_type_raw.normalized_value == "06"
    assert record.fund_type_raw.quality_status is QualityStatus.MIXED_SOURCE_VALUES
    assert record.name.normalized_value == "NULL ETF 상장지수"
    assert [issue.rule_id for issue in result.issues] == ["public_fund.fund_type_unmapped_code"]


@pytest.mark.parametrize(
    "column",
    ["fd_mm18_ern_r", "fd_yr2_ern_r", "fd_yr3_ern_r", "fd_yr5_ern_r"],
)
def test_only_declared_return_periods_warn_below_minus_100(column: str) -> None:
    """Only four frozen comparison periods reject values below minus 100%."""
    result = normalize_fund_attribute(source_row("PRFD01N001", {column: "-100.01"}))

    assert result.record is not None
    wrapped = next(
        getattr(result.record, field_name)
        for field_name, source_column in FUND_ATTRIBUTE_FIELD_COLUMNS.items()
        if source_column == column
    )
    assert wrapped.normalized_value == Decimal("-100.01")
    assert wrapped.quality_status is QualityStatus.OUT_OF_DOMAIN
    assert len(result.issues) == 1
    assert result.issues[0].source.source_column_name == column
    assert result.issues[0].reason == (
        "Public-fund return is below the registered comparison domain."
    )
    assert result.issues[0].quarantined is False


@pytest.mark.parametrize(
    "column",
    [
        "fd_wk1_ern_r",
        "fd_mm1_ern_r",
        "fd_mm3_ern_r",
        "fd_mm6_ern_r",
        "fd_yr1_ern_r",
    ],
)
def test_unregistered_return_periods_do_not_apply_below_minus_100_rule(
    column: str,
) -> None:
    """Unregistered periods remain exact numeric source data without the warning."""
    result = normalize_fund_attribute(source_row("PRFD01N001", {column: "-100.01"}))

    assert result.record is not None
    assert not any(issue.source.source_column_name == column for issue in result.issues)


def test_invalid_currency_and_numeric_emit_fixed_nonquarantine_warnings() -> None:
    """Invalid optional fields survive with safe, cell-located warning issues."""
    result = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            {"curr_cd": "EUR", "fd_mm1_ern_r": "not-a-number"},
            excel_row=44,
        )
    )

    assert result.record is not None
    assert result.record.currency.quality_status is QualityStatus.OUT_OF_DOMAIN
    assert result.record.return_1m.quality_status is QualityStatus.INVALID_FORMAT
    assert [
        (issue.source.source_column_name, issue.reason, issue.quarantined)
        for issue in result.issues
    ] == [
        ("curr_cd", "Public-fund currency is invalid.", False),
        ("fd_mm1_ern_r", "Public-fund numeric value is invalid.", False),
    ]
    assert all(issue.severity is IssueSeverity.WARNING for issue in result.issues)
    assert all(issue.rule_version == "1.0.0" for issue in result.issues)
    assert all(issue.first_detected_at is None for issue in result.issues)
    assert all("EUR" not in issue.reason for issue in result.issues)
    assert all("not-a-number" not in issue.reason for issue in result.issues)


@pytest.mark.parametrize("raw", [" KRW", "KRW ", "krw", "EUR"])
def test_fund_currency_accepts_only_exact_krw_or_usd(raw: str) -> None:
    """Currency cannot be silently trimmed, case-folded, or expanded."""
    result = normalize_fund_attribute(source_row("PRFD01N001", {"curr_cd": raw}))

    assert result.record is not None
    assert result.record.currency.normalized_value is None
    assert result.record.currency.quality_status is QualityStatus.OUT_OF_DOMAIN
    assert [issue.reason for issue in result.issues] == ["Public-fund currency is invalid."]


def test_blank_currency_remains_missing_without_warning() -> None:
    """A genuinely absent optional currency is not misclassified as invalid."""
    result = normalize_fund_attribute(source_row("PRFD01N001", {"curr_cd": ""}))

    assert result.record is not None
    assert result.record.currency.quality_status is QualityStatus.MISSING_BLANK
    assert result.issues == ()


@pytest.mark.parametrize(
    "column",
    [
        "fd_mm18_ern_r",
        "fd_mm1_ern_r",
        "fd_mm3_ern_r",
        "fd_mm6_ern_r",
        "fd_nast_suma",
        "fd_wk1_ern_r",
        "fd_yr1_ern_r",
        "fd_yr2_ern_r",
        "fd_yr3_ern_r",
        "fd_yr5_ern_r",
    ],
)
def test_each_declared_fund_numeric_emits_its_own_invalid_warning(column: str) -> None:
    """No numeric source field can lose its invalid-format issue coverage."""
    result = normalize_fund_attribute(source_row("PRFD01N001", {column: "not-a-number"}))

    assert result.record is not None
    assert [issue.source.source_column_name for issue in result.issues] == [column]
    assert result.issues[0].quality_status is QualityStatus.INVALID_FORMAT


@pytest.mark.parametrize("raw", ["-100", "-99.999"])
def test_registered_return_domain_includes_minus_100_boundary(raw: str) -> None:
    """The frozen comparison rule is strictly below, not at, minus 100%."""
    result = normalize_fund_attribute(source_row("PRFD01N001", {"fd_mm18_ern_r": raw}))

    assert result.record is not None
    assert result.record.return_18m.quality_status is QualityStatus.VALID
    assert result.issues == ()


def test_fund_flags_family_private_markers_and_optional_ids_remain_raw_data() -> None:
    """Task 4 must not infer eligibility, grouping, links, or listed-product type."""
    record = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            {
                "sale_yn": "판매중",
                "thco_sale_yn": "Y",
                "rptt_ksd_itm_no": "000000000000",
                "prvo_fd_desc": "사모",
                "std_itm_no": " 000000000000 ",
                "itm_nm": "ETF 상장지수 펀드",
            },
        )
    ).record

    assert record is not None
    assert record.sale_status_raw.normalized_value == "판매중"
    assert record.mirae_sale_flag_raw.normalized_value == "Y"
    assert record.family_candidate_key.normalized_value == "000000000000"
    assert record.private_fund_description.normalized_value == "사모"
    assert record.standard_item_id.raw_value == " 000000000000 "
    assert record.standard_item_id.normalized_value == "000000000000"
    assert record.name.normalized_value == "ETF 상장지수 펀드"
    assert "saleable" not in type(record).model_fields
    assert "mirae_saleable" not in type(record).model_fields
    assert "family" not in type(record).model_fields
    assert "product_type" not in type(record).model_fields


def test_literal_null_is_special_only_for_risk_fields() -> None:
    """Exact NULL remains ordinary text everywhere outside the two risk cells."""
    record = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            {
                "zrin_fd_ivst_risk_gcd": "NULL",
                "zrin_fd_ivst_risk_grd_nm": "NULL",
                "itm_eng_nm": "NULL",
            },
        )
    ).record

    assert record is not None
    assert record.risk_code.quality_status is QualityStatus.MISSING_LITERAL_NULL
    assert record.risk_name.quality_status is QualityStatus.MISSING_LITERAL_NULL
    assert record.english_name.normalized_value == "NULL"
    assert record.english_name.quality_status is QualityStatus.VALID


@pytest.mark.parametrize("raw", ["null", " NULL "])
def test_risk_literal_null_token_is_exact_and_case_sensitive(raw: str) -> None:
    """Only the exact uppercase unpadded token has special missing semantics."""
    record = normalize_fund_attribute(
        source_row("PRFD01N001", {"zrin_fd_ivst_risk_gcd": raw})
    ).record

    assert record is not None
    assert record.risk_code.normalized_value == raw.strip()
    assert record.risk_code.quality_status is QualityStatus.VALID


def test_fund_locators_keep_only_each_cells_explicit_applicable_date() -> None:
    """No neighboring date may be inferred for public-fund source cells."""
    explicit_date = date(2026, 6, 30)
    record = normalize_fund_attribute(
        source_row(
            "PRFD01N001",
            applicable_dates={"fd_nast_suma": explicit_date},
        )
    ).record

    assert record is not None
    assert record.net_assets.source.source_applicable_date == explicit_date
    for field_name, column_name in FUND_ATTRIBUTE_FIELD_COLUMNS.items():
        if column_name != "fd_nast_suma":
            assert getattr(record, field_name).source.source_applicable_date is None
