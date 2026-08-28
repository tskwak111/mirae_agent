"""Direct public-fund item normalization tests for the refreshed source."""

from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import cast

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.public_funds import normalize_public_fund_item
from finproof.domain.locators import SourceCellLocator
from finproof.domain.public_funds import (
    PUBLIC_FUND_FIELD_COLUMNS,
    PUBLIC_FUND_SOURCE_COLUMNS,
    PublicFundItem,
)
from finproof.domain.quality import IssueSeverity, QualityStatus
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import PUBLIC_FUND_COLUMNS, source_row

EXPECTED_PUBLIC_FUND_FIELD_COLUMNS = MappingProxyType(
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
        "attribute_count": "prfd_attr_cnt",
        "attribute_search_text": "prfd_attr_search_text",
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


def test_public_fund_attributes_are_item_properties() -> None:
    result = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {"prfd_attr_cds": "C101,V101,D102", "prfd_attr_cnt": "3"},
        )
    )

    assert result.record is not None
    assert result.record.attribute_codes == ("C101", "V101", "D102")
    assert result.record.attribute_count.normalized_value == 3


def test_empty_attribute_list_and_zero_count_are_valid() -> None:
    result = normalize_public_fund_item(
        source_row("PRFD01N001", {"prfd_attr_cds": "", "prfd_attr_cnt": "0"})
    )

    assert result.record is not None
    assert result.record.attribute_codes == ()
    assert result.record.attribute_count.normalized_value == 0
    assert result.issues == ()


def test_attribute_codes_are_opaque_and_never_inferred() -> None:
    result = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {"prfd_attr_cds": "opaque,opaque,X?", "prfd_attr_cnt": "3"},
        )
    )

    assert result.record is not None
    assert result.record.attribute_codes == ("opaque", "opaque", "X?")
    assert "attribute_meanings" not in PublicFundItem.model_fields


def test_attribute_count_mismatch_is_evidence_linked_without_dropping_item() -> None:
    row = source_row(
        "PRFD01N001",
        {"prfd_attr_cds": "C101,V101,D102", "prfd_attr_cnt": "2"},
        excel_row=41,
    )

    result = normalize_public_fund_item(row)

    assert result.record is not None
    assert result.record.attribute_codes == ("C101", "V101", "D102")
    assert result.record.attribute_count.normalized_value == 2
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.rule_id == "public_fund.attribute_count_mismatch"
    assert issue.source == SourceCellLocator.from_row(row, "prfd_attr_cnt")
    assert issue.quarantined is False


def test_duplicate_attribute_tokens_do_not_create_duplicate_items() -> None:
    results = tuple(
        normalize_public_fund_item(
            source_row(
                "PRFD01N001",
                {
                    "itm_no": item_id,
                    "prfd_attr_cds": "opaque,opaque",
                    "prfd_attr_cnt": "2",
                },
                excel_row=row_number,
            )
        )
        for item_id, row_number in (("KR5114601001", 2), ("KR5114601002", 3))
    )

    records = tuple(result.record for result in results)
    assert all(record is not None for record in records)
    assert [record.fund_item_id.normalized_value for record in records if record] == [
        "KR5114601001",
        "KR5114601002",
    ]
    assert all(record.attribute_codes == ("opaque", "opaque") for record in records if record)


def test_attribute_search_text_preserves_exact_raw_lineage() -> None:
    row = source_row(
        "PRFD01N001",
        {"prfd_attr_search_text": " C101 상품속성 "},
        excel_row=23,
    )

    record = normalize_public_fund_item(row).record

    assert record is not None
    assert record.attribute_search_text.raw_value == " C101 상품속성 "
    assert record.attribute_search_text.normalized_value == "C101 상품속성"
    assert record.attribute_search_text.source == SourceCellLocator.from_row(
        row, "prfd_attr_search_text"
    )


def test_fund_normalizer_rejects_wrong_table() -> None:
    with pytest.raises(NormalizationContractError, match="PRFD01N001"):
        normalize_public_fund_item(source_row("PREF02N001"))


def test_malformed_item_quarantines_before_payload_is_parsed() -> None:
    result = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {
                "itm_no": '"',
                "curr_cd": "",
                "fd_nast_suma": "not-a-number",
                "or_attr_desc": "06",
            },
            excel_row=84563,
        )
    )

    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.rule_id == "public_fund.malformed_item"
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quarantined is True
    assert issue.source.source_column_name == "itm_no"


def test_malformed_item_quarantines_before_shifted_payload_is_parsed() -> None:
    result = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {"itm_no": '"', "fd_nast_suma": "not-a-number"},
            excel_row=84_563,
        )
    )

    assert result.record is None
    assert [issue.rule_id for issue in result.issues] == ["public_fund.malformed_item"]


def test_malformed_item_returns_before_later_cell_lookup() -> None:
    complete = source_row("PRFD01N001", {"itm_no": '"'}, excel_row=84_563)
    item_cell = complete.cell("itm_no").model_copy(
        update={"excel_column_number": 1, "excel_column_letter": "A"}
    )
    identity_only = SourceRow(
        source_table=complete.source_table,
        source_file=complete.source_file,
        source_sheet=complete.source_sheet,
        source_row_number=complete.source_row_number,
        source_checksum=complete.source_checksum,
        source_snapshot_date=complete.source_snapshot_date,
        raw_payload=('"',),
        cells=(item_cell,),
    )

    result = normalize_public_fund_item(identity_only)

    assert result.record is None
    assert [issue.rule_id for issue in result.issues] == ["public_fund.malformed_item"]


def test_valid_item_preserves_all_wrappers_and_the_exact_75_cell_row() -> None:
    row = source_row("PRFD01N001", excel_row=28)

    record = normalize_public_fund_item(row).record

    assert record is not None
    assert record.source_row is row
    assert tuple(cell.column_name for cell in row.cells) == PUBLIC_FUND_SOURCE_COLUMNS
    for field_name, column_name in EXPECTED_PUBLIC_FUND_FIELD_COLUMNS.items():
        wrapped = getattr(record, field_name)
        assert wrapped.raw_value == row.cell(column_name).raw_value
        assert wrapped.source == SourceCellLocator.from_row(row, column_name)


def test_public_fund_field_maps_are_complete_exact_and_immutable() -> None:
    assert PUBLIC_FUND_SOURCE_COLUMNS == PUBLIC_FUND_COLUMNS
    assert dict(PUBLIC_FUND_FIELD_COLUMNS) == dict(EXPECTED_PUBLIC_FUND_FIELD_COLUMNS)
    assert len(PUBLIC_FUND_SOURCE_COLUMNS) == len(set(PUBLIC_FUND_SOURCE_COLUMNS)) == 75
    with pytest.raises(TypeError):
        cast(dict[str, str], PUBLIC_FUND_FIELD_COLUMNS)["name"] = "other"


def test_fund_currency_zero_risk_and_unmapped_type_policies_are_field_specific() -> None:
    result = normalize_public_fund_item(
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
    assert record.risk_code.quality_status is QualityStatus.MISSING_LITERAL_NULL
    assert record.risk_name.quality_status is QualityStatus.MISSING_BLANK
    assert record.fund_type_raw.quality_status is QualityStatus.MIXED_SOURCE_VALUES
    assert record.name.normalized_value == "NULL ETF 상장지수"
    assert [issue.rule_id for issue in result.issues] == ["public_fund.fund_type_unmapped_code"]


@pytest.mark.parametrize(
    "column",
    ["fd_mm18_ern_r", "fd_yr2_ern_r", "fd_yr3_ern_r", "fd_yr5_ern_r"],
)
def test_declared_return_periods_warn_below_minus_100(column: str) -> None:
    result = normalize_public_fund_item(source_row("PRFD01N001", {column: "-100.01"}))

    assert result.record is not None
    wrapped = next(
        getattr(result.record, field_name)
        for field_name, source_column in PUBLIC_FUND_FIELD_COLUMNS.items()
        if source_column == column
    )
    assert wrapped.normalized_value == Decimal("-100.01")
    assert wrapped.quality_status is QualityStatus.OUT_OF_DOMAIN
    assert [issue.source.source_column_name for issue in result.issues] == [column]


def test_invalid_currency_numeric_and_count_emit_cell_located_warnings() -> None:
    result = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {
                "curr_cd": "EUR",
                "fd_mm1_ern_r": "not-a-number",
                "prfd_attr_cnt": "not-a-number",
            },
            excel_row=44,
        )
    )

    assert result.record is not None
    assert [issue.source.source_column_name for issue in result.issues] == [
        "curr_cd",
        "fd_mm1_ern_r",
        "prfd_attr_cnt",
    ]
    assert all(issue.quarantined is False for issue in result.issues)
    assert all(issue.severity is IssueSeverity.WARNING for issue in result.issues)


def test_fund_flags_family_private_markers_and_optional_ids_remain_raw_data() -> None:
    record = normalize_public_fund_item(
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
    assert record.name.normalized_value == "ETF 상장지수 펀드"
    assert {"saleable", "mirae_saleable", "family", "product_type"}.isdisjoint(
        PublicFundItem.model_fields
    )


def test_literal_null_is_special_only_for_risk_fields() -> None:
    record = normalize_public_fund_item(
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


def test_fund_locators_keep_only_each_cells_explicit_applicable_date() -> None:
    explicit_date = date(2026, 6, 30)
    record = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            applicable_dates={"fd_nast_suma": explicit_date},
        )
    ).record

    assert record is not None
    assert record.net_assets.source.source_applicable_date == explicit_date
    for field_name, column_name in PUBLIC_FUND_FIELD_COLUMNS.items():
        if column_name != "fd_nast_suma":
            assert getattr(record, field_name).source.source_applicable_date is None
