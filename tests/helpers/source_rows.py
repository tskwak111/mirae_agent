"""Complete synthetic rows with safe, fixed source lineage for unit tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import PurePosixPath
from typing import Literal

from finproof.domain.source import SourceCell, SourceRow

SNAPSHOT_DATE = date(2026, 7, 11)

BOND_COLUMNS = (
    "PD_NO",
    "PD_EXG_MKT",
    "PD_NM",
    "PD_ABRV_NM",
    "PD_ENG_NM",
    "PD_ABRV_ENG_NM",
    "PD_CTRY_CD",
    "PD_PBCM",
    "STD_PD_MCLS_NM",
    "STD_PD_SCLS_NM",
    "BD_KND",
    "CURR_CD",
    "ISU_BAL_AMT",
    "ISU_DT",
    "MAT_DT",
    "SRFC_IRT",
    "PD_EVCO_CRD_GRD",
    "PD_RISK_GCD",
    "PD_STD_INFO_UPDATE",
    "BUY_YIELD",
    "CORP_PRETAX_YIELD",
    "CORP_AFTER_TAX_YIELD",
    "AFTER_TAX_YIELD",
    "PREF_TAX_YIELD",
    "AVG_ANNUAL_TAX_YIELD",
    "DEPO_EQUIV_YIELD_154",
    "BUYABLE_QUANTITY",
    "REMAINING_DAYS",
    "DUR",
    "COV",
    "NDY_DUR",
    "NDY_COV",
    "EVAL_PRICE",
    "APPLIED_YIELD",
    "DIRTY",
    "NDY_EVAL_PRICE",
    "NDY_APPLIED_YIELD",
    "NDY_DIRTY",
    "CRD_GRD",
    "CRD_GRD_DT",
)

DOMESTIC_LISTED_COLUMNS = (
    "cu_base_index",
    "cu_charge_etc_rt",
    "cu_charge_rt",
    "cu_fund_mgmt_co",
    "cu_lev_fector",
    "cu_strtegy",
    "cu_upt_dt",
    "du_bpr",
    "du_chas_errt",
    "du_clpr",
    "du_diff_rt",
    "du_er_1d",
    "du_er_1m",
    "du_er_1y",
    "du_er_3m",
    "du_er_6m",
    "du_er_ytd",
    "du_hpr",
    "du_last_aum",
    "du_last_nav",
    "du_lpr",
    "du_nav_rnf_amt",
    "du_nav_yday",
    "du_upt_dt",
    "du_val_1d",
    "du_val_1m",
    "du_val_5d",
    "du_vol_1d",
    "du_vol_avg_1m",
    "du_vol_avg_5d",
    "nru_mkt_diff_rt",
    "nru_mkt_inav",
    "pd_abrv_nm",
    "pd_circ_net_tamt",
    "pd_circ_stk_cnt",
    "pd_curr_cd",
    "pd_curr_nm",
    "pd_divd_amt_pshr",
    "pd_dvid_cycl",
    "pd_dvid_yield",
    "pd_exg_mkt_cd",
    "pd_exg_mkt_nm",
    "pd_grp_no",
    "pd_itm_no",
    "pd_itm_no_ma",
    "pd_lst_price",
    "pd_lst_stk_cnt",
    "pd_lste_dt",
    "pd_lstg_dt",
    "pd_mkt_id",
    "pd_mkt_nm",
    "pd_nav_pshr",
    "pd_net_ast_pshr",
    "pd_net_prft_pshr",
    "pd_net_rt_ast_pshr",
    "pd_net_tamt",
    "pd_nm",
    "pd_pen_risk_nm",
    "pd_pen_tr_yn",
    "pd_risk_cd",
    "pd_risk_nm",
    "pd_sale_yn",
    "pd_sect_cd",
    "pd_sect_nm",
    "pd_spac_yn",
    "pd_stk_cnt",
    "pd_tr_yn",
    "ru_mkt_price",
    "ru_mkt_volume",
    "wu_core_yn",
    "wu_inv_ast_type",
    "wu_inv_rgn",
    "wu_upt_dt",
)

TableId = Literal["PRBD01N001", "PREF01N001"]


def _excel_column_letter(number: int) -> str:
    letters: list[str] = []
    remaining = number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def source_row(
    table_id: TableId,
    values: Mapping[str, str] | None = None,
    *,
    excel_row: int = 2,
    applicable_dates: Mapping[str, date | None] | None = None,
) -> SourceRow:
    """Return a complete source row with only safe, fixed fixture lineage."""
    columns = BOND_COLUMNS if table_id == "PRBD01N001" else DOMESTIC_LISTED_COLUMNS
    defaults = (
        {
            "PD_NO": "KR0000000001",
            "PD_NM": "테스트 채권",
            "PD_ABRV_NM": "채권",
            "CURR_CD": "KRW",
            "BD_KND": "회사채",
            "ISU_DT": "20200101",
            "MAT_DT": "20270711",
            "BUYABLE_QUANTITY": "1",
            "REMAINING_DAYS": "365",
        }
        if table_id == "PRBD01N001"
        else {
            "pd_itm_no": "KR7000000001",
            "pd_itm_no_ma": "A000001",
            "pd_grp_no": "ETF",
            "pd_nm": "테스트 ETF",
            "pd_abrv_nm": "테스트",
            "pd_curr_cd": "CURR_CD_KRW",
            "pd_sale_yn": "1",
            "pd_tr_yn": "0",
            "pd_lstg_dt": "20200101",
            "pd_lste_dt": "99991231",
        }
    )
    supplied = dict(values or {})
    unknown = set(supplied) - set(columns)
    if unknown:
        raise KeyError(f"unknown source columns: {sorted(unknown)}")
    dates = dict(applicable_dates or {})
    unknown_dates = set(dates) - set(columns)
    if unknown_dates:
        raise KeyError(f"unknown applicable-date columns: {sorted(unknown_dates)}")
    raw = dict.fromkeys(columns, "") | defaults | supplied
    cells = tuple(
        SourceCell(
            column_name=column,
            excel_column_number=number,
            excel_column_letter=_excel_column_letter(number),
            raw_value=raw[column],
            applicable_date=dates.get(column),
        )
        for number, column in enumerate(columns, start=1)
    )
    return SourceRow(
        source_table=table_id,
        source_file=PurePosixPath(f"data/{table_id}_fixture.xlsx"),
        source_sheet="datarows",
        source_row_number=excel_row,
        source_checksum="a" * 64,
        source_snapshot_date=SNAPSHOT_DATE,
        raw_payload=tuple(cell.raw_value for cell in cells),
        cells=cells,
    )
