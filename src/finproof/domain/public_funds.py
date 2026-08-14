"""Immutable public-fund domain contracts."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Final, NoReturn, Self

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from finproof.domain.locators import SourceCellLocator
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
    if not isinstance(cells, list) or len(cells) != len(FUND_ATTRIBUTE_FIELD_COLUMNS):
        _raise_noncanonical_source_row_json()

    for column_number, (cell, expected_column_name) in enumerate(
        zip(cells, FUND_ATTRIBUTE_FIELD_COLUMNS.values(), strict=True),
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
