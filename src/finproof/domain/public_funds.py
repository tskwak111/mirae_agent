"""Immutable public-fund domain contracts."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Final, Literal, NoReturn, Self

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import DataQualityIssue
from finproof.domain.source import SourceRow
from finproof.domain.values import NormalizedValue

_SOURCE_ROW_JSON_KEYS = frozenset(
    {
        "source_table",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_checksum",
        "source_snapshot_date",
        "raw_payload",
        "cells",
    }
)
_SOURCE_CELL_JSON_KEYS = frozenset(
    {
        "column_name",
        "excel_column_number",
        "excel_column_letter",
        "raw_value",
        "applicable_date",
    }
)

FUND_ATTRIBUTE_FIELD_COLUMNS: Final[Mapping[str, str]] = MappingProxyType(
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
FUND_ITEM_FIELD_COLUMNS: Final[Mapping[str, str]] = MappingProxyType(
    {
        field_name: column_name
        for field_name, column_name in FUND_ATTRIBUTE_FIELD_COLUMNS.items()
        if field_name != "attribute_code"
    }
)

PUBLIC_FUND_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "bmrk_eng_nm",
    "bmrk_nm",
    "bns_bpr",
    "curr_cd",
    "exchdg_yn",
    "fd_daily_bas_dt",
    "fd_estb_ctry_cd",
    "fd_ivst_rgn_desc",
    "fd_last_dstb_actg_bss_dt",
    "fd_last_dstb_actg_eot_dt",
    "fd_last_dstb_r",
    "fd_mm18_ern_r",
    "fd_mm1_ern_r",
    "fd_mm3_ern_r",
    "fd_mm6_ern_r",
    "fd_nast_suma",
    "fd_price_bas_dt",
    "fd_prsv_r",
    "fd_sbpr",
    "fd_set_pcd",
    "fd_wk1_ern_r",
    "fd_yr1_ern_r",
    "fd_yr2_ern_r",
    "fd_yr3_ern_r",
    "fd_yr5_ern_r",
    "frc_bpr_itm_yn",
    "fss_itm_no",
    "han_clas_fee_type",
    "han_clas_nm",
    "han_clas_policies",
    "han_clas_sales_channel",
    "hdge_fd_yn",
    "int_dvd_desc",
    "itm_abrv_nm",
    "itm_eabrv_nm",
    "itm_eng_nm",
    "itm_nm",
    "itm_no",
    "kofia_fd_ccd",
    "ksd_itm_no",
    "mtco_itm_no",
    "ofsfd_yn",
    "ofwk_trus_rwrd_r",
    "or_attr_desc",
    "or_co_rwrd_r",
    "or_co_xtn_itt_cd",
    "ovrs_fd_desc",
    "pers_corp_desc",
    "pfiv_sale_cntl_tcd",
    "prfd_attr_cds",
    "prfd_attr_cnt",
    "prfd_attr_search_text",
    "prvo_fd_desc",
    "prvo_pbff_desc",
    "rptt_ksd_itm_no",
    "sale_co_rwrd_r",
    "sale_yn",
    "std_itm_no",
    "thco_sale_yn",
    "trusc_rwrd_r",
    "trusc_xtn_itt_cd",
    "zrin_attr_nms",
    "zrin_btyp_cd",
    "zrin_btyp_nm",
    "zrin_dmst_bd_cmst_rt",
    "zrin_dmst_stk_cmst_rt",
    "zrin_etc_ast_cmst_rt",
    "zrin_fd_cmst_rt",
    "zrin_fd_ivst_risk_gcd",
    "zrin_fd_ivst_risk_grd_nm",
    "zrin_liqt_cmst_rt",
    "zrin_ovrs_bd_cmst_rt",
    "zrin_ovrs_stk_cmst_rt",
    "zrin_pcd",
    "zrin_ptn_nm",
)
PUBLIC_FUND_FIELD_COLUMNS: Final[Mapping[str, str]] = MappingProxyType(
    {
        **FUND_ITEM_FIELD_COLUMNS,
        "attribute_count": "prfd_attr_cnt",
        "attribute_search_text": "prfd_attr_search_text",
    }
)


class PublicFundItem(BaseModel):
    """One refreshed public-fund source row at the item grain."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["fund_item"] = "fund_item"
    source_row: SourceRow
    benchmark_english_name: NormalizedValue[str]
    benchmark_name: NormalizedValue[str]
    currency: NormalizedValue[str]
    exchange_traded_flag_raw: NormalizedValue[str]
    establishment_country_code: NormalizedValue[str]
    region_description: NormalizedValue[str]
    return_18m: NormalizedValue[Decimal]
    return_1m: NormalizedValue[Decimal]
    return_3m: NormalizedValue[Decimal]
    return_6m: NormalizedValue[Decimal]
    net_assets: NormalizedValue[Decimal]
    establishment_type_code: NormalizedValue[str]
    return_1w: NormalizedValue[Decimal]
    return_1y: NormalizedValue[Decimal]
    return_2y: NormalizedValue[Decimal]
    return_3y: NormalizedValue[Decimal]
    return_5y: NormalizedValue[Decimal]
    foreign_base_price_flag_raw: NormalizedValue[str]
    fss_item_id: NormalizedValue[str]
    hedge_fund_flag_raw: NormalizedValue[str]
    interest_dividend_description: NormalizedValue[str]
    short_name: NormalizedValue[str]
    english_short_name: NormalizedValue[str]
    english_name: NormalizedValue[str]
    name: NormalizedValue[str]
    fund_item_id: NormalizedValue[str]
    kofia_classification_code: NormalizedValue[str]
    ksd_id: NormalizedValue[str]
    manager_item_id: NormalizedValue[str]
    offshore_fund_flag_raw: NormalizedValue[str]
    fund_type_raw: NormalizedValue[str]
    manager_external_code: NormalizedValue[str]
    overseas_fund_description: NormalizedValue[str]
    investor_type_description: NormalizedValue[str]
    professional_sale_control_code: NormalizedValue[str]
    attribute_codes: tuple[str, ...]
    attribute_count: NormalizedValue[int]
    attribute_search_text: NormalizedValue[str]
    private_fund_description: NormalizedValue[str]
    offering_type_description: NormalizedValue[str]
    family_candidate_key: NormalizedValue[str]
    sale_status_raw: NormalizedValue[str]
    standard_item_id: NormalizedValue[str]
    mirae_sale_flag_raw: NormalizedValue[str]
    trustee_external_code: NormalizedValue[str]
    risk_code: NormalizedValue[str]
    risk_name: NormalizedValue[str]

    @field_validator("source_row", mode="before")
    @classmethod
    def validate_source_row_boundary(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> object:
        if info.mode == "python":
            if type(value) is not SourceRow:
                raise ValueError("source_row must be an exact SourceRow instance")
        else:
            _validate_source_row_json(value, PUBLIC_FUND_SOURCE_COLUMNS)
        return value

    @model_validator(mode="after")
    def validate_complete_source_lineage(self) -> Self:
        row = self.source_row
        if row.source_table != "PRFD01N001":
            raise ValueError("public-fund source row must name PRFD01N001")
        if tuple(cell.column_name for cell in row.cells) != PUBLIC_FUND_SOURCE_COLUMNS:
            raise ValueError("public-fund source row must use canonical column order")
        expected_codes = (
            ()
            if row.cell("prfd_attr_cds").raw_value == ""
            else tuple(row.cell("prfd_attr_cds").raw_value.split(","))
        )
        if self.attribute_codes != expected_codes:
            raise ValueError("attribute_codes must preserve the exact comma split")
        for field_name, column_name in PUBLIC_FUND_FIELD_COLUMNS.items():
            wrapped = getattr(self, field_name)
            if wrapped.raw_value != row.cell(column_name).raw_value:
                raise ValueError("public-fund wrapper raw value does not match source row")
            if wrapped.source != SourceCellLocator.from_row(row, column_name):
                raise ValueError("public-fund wrapper locator does not match source row")
        return self


class FundAttributeRow(BaseModel):
    """One normalized public-fund source row at its attribute grain."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_row: SourceRow
    benchmark_english_name: NormalizedValue[str]
    benchmark_name: NormalizedValue[str]
    currency: NormalizedValue[str]
    exchange_traded_flag_raw: NormalizedValue[str]
    establishment_country_code: NormalizedValue[str]
    region_description: NormalizedValue[str]
    return_18m: NormalizedValue[Decimal]
    return_1m: NormalizedValue[Decimal]
    return_3m: NormalizedValue[Decimal]
    return_6m: NormalizedValue[Decimal]
    net_assets: NormalizedValue[Decimal]
    establishment_type_code: NormalizedValue[str]
    return_1w: NormalizedValue[Decimal]
    return_1y: NormalizedValue[Decimal]
    return_2y: NormalizedValue[Decimal]
    return_3y: NormalizedValue[Decimal]
    return_5y: NormalizedValue[Decimal]
    foreign_base_price_flag_raw: NormalizedValue[str]
    fss_item_id: NormalizedValue[str]
    hedge_fund_flag_raw: NormalizedValue[str]
    interest_dividend_description: NormalizedValue[str]
    short_name: NormalizedValue[str]
    english_short_name: NormalizedValue[str]
    english_name: NormalizedValue[str]
    name: NormalizedValue[str]
    fund_item_id: NormalizedValue[str]
    kofia_classification_code: NormalizedValue[str]
    ksd_id: NormalizedValue[str]
    manager_item_id: NormalizedValue[str]
    offshore_fund_flag_raw: NormalizedValue[str]
    fund_type_raw: NormalizedValue[str]
    manager_external_code: NormalizedValue[str]
    overseas_fund_description: NormalizedValue[str]
    investor_type_description: NormalizedValue[str]
    professional_sale_control_code: NormalizedValue[str]
    attribute_code: NormalizedValue[str]
    private_fund_description: NormalizedValue[str]
    offering_type_description: NormalizedValue[str]
    family_candidate_key: NormalizedValue[str]
    sale_status_raw: NormalizedValue[str]
    standard_item_id: NormalizedValue[str]
    mirae_sale_flag_raw: NormalizedValue[str]
    trustee_external_code: NormalizedValue[str]
    risk_code: NormalizedValue[str]
    risk_name: NormalizedValue[str]

    @field_validator("source_row", mode="before")
    @classmethod
    def validate_source_row_boundary(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> object:
        """Separate exact Python object validation from structural JSON parsing."""
        if info.mode == "python":
            if type(value) is not SourceRow:
                raise ValueError("source_row must be an exact SourceRow instance")
        else:
            validate_public_fund_source_row_json(value)
        return value

    @model_validator(mode="after")
    def validate_complete_source_lineage(self) -> Self:
        """Cross-check all 45 wrappers against one canonical public-fund row."""
        row = self.source_row
        if row.source_table != "PRFD01N001":
            raise ValueError("public-fund source row must name PRFD01N001")
        if tuple(cell.column_name for cell in row.cells) != tuple(
            FUND_ATTRIBUTE_FIELD_COLUMNS.values()
        ):
            raise ValueError("public-fund source row must use canonical column order")
        for field_name, column_name in FUND_ATTRIBUTE_FIELD_COLUMNS.items():
            wrapped = getattr(self, field_name)
            if wrapped.raw_value != row.cell(column_name).raw_value:
                raise ValueError("public-fund wrapper raw value does not match source row")
            if wrapped.source != SourceCellLocator.from_row(row, column_name):
                raise ValueError("public-fund wrapper locator does not match source row")
        return self


def validate_public_fund_source_row_json(value: object) -> None:
    """Reject noncanonical serialized SourceRow shapes before model coercion."""
    _validate_source_row_json(value, tuple(FUND_ATTRIBUTE_FIELD_COLUMNS.values()))


def _validate_source_row_json(value: object, columns: tuple[str, ...]) -> None:
    if not isinstance(value, dict) or set(value) != _SOURCE_ROW_JSON_KEYS:
        _raise_noncanonical_source_row_json()

    for field_name in (
        "source_table",
        "source_file",
        "source_sheet",
        "source_checksum",
    ):
        field_value = value[field_name]
        if type(field_value) is not str or not field_value:
            _raise_noncanonical_source_row_json()

    source_file = value["source_file"]
    if type(source_file) is not str:
        _raise_noncanonical_source_row_json()
    source_path = PurePosixPath(source_file)
    if (
        source_path.is_absolute()
        or ".." in source_path.parts
        or source_path.as_posix() != source_file
    ):
        _raise_noncanonical_source_row_json()

    row_number = value["source_row_number"]
    if type(row_number) is not int or row_number < 1:
        _raise_noncanonical_source_row_json()
    if not _is_canonical_date(value["source_snapshot_date"]):
        _raise_noncanonical_source_row_json()

    raw_payload = value["raw_payload"]
    cells = value["cells"]
    if not isinstance(raw_payload, list) or not all(
        type(raw_value) is str for raw_value in raw_payload
    ):
        _raise_noncanonical_source_row_json()
    if not isinstance(cells, list) or len(cells) != len(columns):
        _raise_noncanonical_source_row_json()

    for column_number, (cell, expected_column_name) in enumerate(
        zip(cells, columns, strict=True),
        start=1,
    ):
        if not isinstance(cell, dict) or set(cell) != _SOURCE_CELL_JSON_KEYS:
            _raise_noncanonical_source_row_json()
        if (
            type(cell["column_name"]) is not str
            or cell["column_name"] != expected_column_name
            or type(cell["excel_column_letter"]) is not str
            or type(cell["raw_value"]) is not str
            or type(cell["excel_column_number"]) is not int
            or cell["excel_column_number"] != column_number
        ):
            _raise_noncanonical_source_row_json()
        applicable_date = cell["applicable_date"]
        if applicable_date is not None and not _is_canonical_date(applicable_date):
            _raise_noncanonical_source_row_json()

    if raw_payload != [cell["raw_value"] for cell in cells]:
        _raise_noncanonical_source_row_json()


def _is_canonical_date(value: object) -> bool:
    if type(value) is not str or len(value) != 10:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _raise_noncanonical_source_row_json() -> NoReturn:
    raise ValueError("canonical SourceRow JSON shape is required")


class FundItemValue[ValueT](BaseModel):
    """One representative item value with every equivalent source-cell locator."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    representative: NormalizedValue[ValueT]
    equivalent_sources: tuple[SourceCellLocator, ...]

    @model_validator(mode="after")
    def validate_equivalent_sources(self) -> Self:
        """Require complete, deterministic, same-column source lineage."""
        sources = self.equivalent_sources
        if not sources:
            raise ValueError("equivalent_sources must not be empty")
        if sources[0] != self.representative.source:
            raise ValueError("representative source must be first")

        positions = tuple(
            (source.source_row_number, source.source_column_number) for source in sources
        )
        if len(set(positions)) != len(positions):
            raise ValueError("equivalent source positions must be unique")
        if positions != tuple(sorted(positions)):
            raise ValueError("equivalent_sources must be sorted by row and column")

        representative_source = self.representative.source
        representative_lineage = (
            representative_source.source_table,
            representative_source.source_file,
            representative_source.source_sheet,
            representative_source.source_column_name,
            representative_source.source_column_number,
            representative_source.source_column_letter,
            representative_source.source_checksum,
            representative_source.source_snapshot_date,
        )
        for source in sources:
            source_lineage = (
                source.source_table,
                source.source_file,
                source.source_sheet,
                source.source_column_name,
                source.source_column_number,
                source.source_column_letter,
                source.source_checksum,
                source.source_snapshot_date,
            )
            if source_lineage != representative_lineage:
                raise ValueError("equivalent_sources must share representative source lineage")
        return self


class FundItemAttribute(BaseModel):
    """One many-valued public-fund attribute with source-backed identity."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["fund_attribute"] = "fund_attribute"
    fund_item_id: NormalizedValue[str]
    attribute_code: NormalizedValue[str]


class _RetiredFundItem(BaseModel):
    """One public fund at the frozen item grain with repeated cell evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grain: Literal["fund_item"] = "fund_item"
    contributing_rows: tuple[SourceRow, ...]
    benchmark_english_name: FundItemValue[str]
    benchmark_name: FundItemValue[str]
    currency: FundItemValue[str]
    exchange_traded_flag_raw: FundItemValue[str]
    establishment_country_code: FundItemValue[str]
    region_description: FundItemValue[str]
    return_18m: FundItemValue[Decimal]
    return_1m: FundItemValue[Decimal]
    return_3m: FundItemValue[Decimal]
    return_6m: FundItemValue[Decimal]
    net_assets: FundItemValue[Decimal]
    establishment_type_code: FundItemValue[str]
    return_1w: FundItemValue[Decimal]
    return_1y: FundItemValue[Decimal]
    return_2y: FundItemValue[Decimal]
    return_3y: FundItemValue[Decimal]
    return_5y: FundItemValue[Decimal]
    foreign_base_price_flag_raw: FundItemValue[str]
    fss_item_id: FundItemValue[str]
    hedge_fund_flag_raw: FundItemValue[str]
    interest_dividend_description: FundItemValue[str]
    short_name: FundItemValue[str]
    english_short_name: FundItemValue[str]
    english_name: FundItemValue[str]
    name: FundItemValue[str]
    fund_item_id: FundItemValue[str]
    kofia_classification_code: FundItemValue[str]
    ksd_id: FundItemValue[str]
    manager_item_id: FundItemValue[str]
    offshore_fund_flag_raw: FundItemValue[str]
    fund_type_raw: FundItemValue[str]
    manager_external_code: FundItemValue[str]
    overseas_fund_description: FundItemValue[str]
    investor_type_description: FundItemValue[str]
    professional_sale_control_code: FundItemValue[str]
    private_fund_description: FundItemValue[str]
    offering_type_description: FundItemValue[str]
    family_candidate_key: FundItemValue[str]
    sale_status_raw: FundItemValue[str]
    standard_item_id: FundItemValue[str]
    mirae_sale_flag_raw: FundItemValue[str]
    trustee_external_code: FundItemValue[str]
    risk_code: FundItemValue[str]
    risk_name: FundItemValue[str]

    @field_validator("contributing_rows", mode="before")
    @classmethod
    def validate_contributing_row_boundary(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> object:
        """Separate exact Python SourceRows from canonical structural JSON."""
        if info.mode == "python":
            if not isinstance(value, tuple) or any(type(row) is not SourceRow for row in value):
                raise ValueError("contributing_rows must contain exact SourceRow instances")
        else:
            if not isinstance(value, list):
                _raise_noncanonical_source_row_json()
            for row in value:
                validate_public_fund_source_row_json(row)
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_complete_item_lineage(self) -> Self:
        """Prove every item value against every contributing raw source row."""
        rows = self.contributing_rows
        if not rows:
            raise ValueError("contributing_rows must not be empty")
        expected_columns = tuple(FUND_ATTRIBUTE_FIELD_COLUMNS.values())
        representative = rows[0]
        row_numbers = tuple(row.source_row_number for row in rows)
        if row_numbers != tuple(sorted(set(row_numbers))):
            raise ValueError("contributing_rows must use unique increasing row numbers")
        for row in rows:
            if row.source_table != "PRFD01N001":
                raise ValueError("contributing row must name PRFD01N001")
            if tuple(cell.column_name for cell in row.cells) != expected_columns:
                raise ValueError("contributing row must use canonical column order")

        representative_identity = (
            representative.source_file,
            representative.source_sheet,
            representative.source_checksum,
            representative.source_snapshot_date,
            representative.cell("itm_no").raw_value,
        )
        for row in rows:
            identity = (
                row.source_file,
                row.source_sheet,
                row.source_checksum,
                row.source_snapshot_date,
                row.cell("itm_no").raw_value,
            )
            if identity != representative_identity:
                raise ValueError("contributing rows must share item source identity")

        for field_name, column_name in FUND_ITEM_FIELD_COLUMNS.items():
            value = getattr(self, field_name)
            expected_sources = tuple(SourceCellLocator.from_row(row, column_name) for row in rows)
            if value.equivalent_sources != expected_sources:
                raise ValueError("item value must preserve every contributing locator")
            if value.representative.source != expected_sources[0]:
                raise ValueError("item representative must come from the lowest row")
            expected_raw = representative.cell(column_name).raw_value
            if value.representative.raw_value != expected_raw:
                raise ValueError("item representative raw value must match source row")
            if any(row.cell(column_name).raw_value != expected_raw for row in rows[1:]):
                raise ValueError("non-attribute raw values must agree within an item")
        return self


class FundCollapseResult(BaseModel):
    """Deterministic item, attribute, and quality output for public funds."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    items: tuple[_RetiredFundItem, ...]
    attributes: tuple[FundItemAttribute, ...]
    issues: tuple[DataQualityIssue, ...]

    @model_validator(mode="after")
    def validate_complete_relations(self) -> Self:
        """Require stable ordering and exact item-to-attribute row coverage."""
        item_keys = tuple(
            item.fund_item_id.representative.normalized_value or "" for item in self.items
        )
        if item_keys != tuple(sorted(item_keys)) or len(set(item_keys)) != len(item_keys):
            raise ValueError("items must have unique normalized IDs in sorted order")

        attribute_keys = tuple(_fund_attribute_order_key(value) for value in self.attributes)
        if attribute_keys != tuple(sorted(attribute_keys)):
            raise ValueError("attributes must use deterministic sorted order")

        expected_rows: dict[tuple[object, ...], SourceRow] = {}
        for item in self.items:
            for row in item.contributing_rows:
                identity = _source_row_identity(row)
                if identity in expected_rows:
                    raise ValueError("contributing source rows must be unique across items")
                expected_rows[identity] = row

        seen_rows: set[tuple[object, ...]] = set()
        for attribute in self.attributes:
            identity = (
                attribute.fund_item_id.source.source_file,
                attribute.fund_item_id.source.source_sheet,
                attribute.fund_item_id.source.source_row_number,
            )
            expected_row = expected_rows.get(identity)
            if expected_row is None or identity in seen_rows:
                raise ValueError("attributes must map once to an emitted item row")
            if attribute.fund_item_id.source != SourceCellLocator.from_row(expected_row, "itm_no"):
                raise ValueError("attribute item locator must match contributing row")
            if attribute.attribute_code.source != SourceCellLocator.from_row(
                expected_row, "prfd_attr_cd"
            ):
                raise ValueError("attribute code locator must match contributing row")
            if attribute.fund_item_id.raw_value != expected_row.cell("itm_no").raw_value:
                raise ValueError("attribute item raw value must match contributing row")
            if attribute.attribute_code.raw_value != expected_row.cell("prfd_attr_cd").raw_value:
                raise ValueError("attribute code raw value must match contributing row")
            seen_rows.add(identity)
        if seen_rows != set(expected_rows):
            raise ValueError("attributes must cover every contributing row exactly once")

        issue_ids = tuple(issue.issue_id for issue in self.issues)
        if len(set(issue_ids)) != len(issue_ids):
            raise ValueError("quality issue IDs must be unique")
        return self


def _source_row_identity(row: SourceRow) -> tuple[object, ...]:
    return (row.source_file, row.source_sheet, row.source_row_number)


def _fund_attribute_order_key(
    attribute: FundItemAttribute,
) -> tuple[str, str, str, int]:
    return (
        attribute.fund_item_id.normalized_value or "",
        attribute.attribute_code.normalized_value or "",
        attribute.attribute_code.raw_value,
        attribute.attribute_code.source.source_row_number,
    )


FundItem = PublicFundItem
