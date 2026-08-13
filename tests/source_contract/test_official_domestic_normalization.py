from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from finproof.data.normalization.bonds import normalize_bond
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.data.source_manifest import SourceFileManifest
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.bonds import BondInstrument
from finproof.domain.domestic_listed import ListedProduct, ListedProductType
from finproof.domain.quality import DataQualityIssue
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue
from finproof.registry.rating import RatingRegistry

ROOT = Path(__file__).resolve().parents[2]
AS_OF = date(2026, 7, 11)
pytestmark = [pytest.mark.source_contract, pytest.mark.slow]

BOND_COLUMNS = {
    "product_id": "PD_NO",
    "name": "PD_NM",
    "short_name": "PD_ABRV_NM",
    "currency": "CURR_CD",
    "bond_kind_raw": "BD_KND",
    "issue_date": "ISU_DT",
    "maturity_date": "MAT_DT",
    "source_update_date": "PD_STD_INFO_UPDATE",
    "coupon_rate": "SRFC_IRT",
    "buy_yield": "BUY_YIELD",
    "buyable_quantity": "BUYABLE_QUANTITY",
    "source_remaining_days": "REMAINING_DAYS",
    "credit_rating": "CRD_GRD",
    "credit_rating_agencies_raw": "PD_EVCO_CRD_GRD",
    "credit_rating_date": "CRD_GRD_DT",
    "duration": "DUR",
    "evaluation_price": "EVAL_PRICE",
}

LISTED_COLUMNS = {
    "product_id": "pd_itm_no",
    "market_identifier": "pd_itm_no_ma",
    "product_type": "pd_grp_no",
    "name": "pd_nm",
    "short_name": "pd_abrv_nm",
    "currency": "pd_curr_cd",
    "listing_date": "pd_lstg_dt",
    "listing_end_date": "pd_lste_dt",
    "sale_flag": "pd_sale_yn",
    "suspension_flag": "pd_tr_yn",
    "aum_primary": "pd_net_tamt",
    "aum_secondary": "du_last_aum",
    "total_fee": "cu_charge_rt",
    "tracking_error": "du_chas_errt",
    "difference_rate": "du_diff_rt",
    "return_1d": "du_er_1d",
    "return_1m": "du_er_1m",
    "return_3m": "du_er_3m",
    "return_6m": "du_er_6m",
    "return_1y": "du_er_1y",
    "return_ytd": "du_er_ytd",
    "risk_code": "pd_risk_cd",
    "risk_name": "pd_risk_nm",
    "base_index": "cu_base_index",
    "manager": "cu_fund_mgmt_co",
    "asset_type": "wu_inv_ast_type",
    "region": "wu_inv_rgn",
    "custom_update_date": "cu_upt_dt",
    "daily_update_at": "du_upt_dt",
    "weekly_update_date": "wu_upt_dt",
}


def _assert_wrapped_source_fidelity(
    record: BondInstrument | ListedProduct,
    row: SourceRow,
    field_columns: dict[str, str],
) -> None:
    for field_name, column_name in field_columns.items():
        wrapped = getattr(record, field_name)
        assert isinstance(wrapped, NormalizedValue)
        cell = row.cell(column_name)
        assert wrapped.raw_value == cell.raw_value
        assert wrapped.source.source_table == row.source_table
        assert wrapped.source.source_file == row.source_file
        assert wrapped.source.source_sheet == row.source_sheet
        assert wrapped.source.source_row_number == row.source_row_number
        assert wrapped.source.source_column_name == cell.column_name
        assert wrapped.source.source_column_number == cell.excel_column_number
        assert wrapped.source.source_column_letter == cell.excel_column_letter
        assert wrapped.source.source_checksum == row.source_checksum
        assert wrapped.source.source_snapshot_date == row.source_snapshot_date
        assert wrapped.source.source_applicable_date == cell.applicable_date


def _assert_derived_inputs(
    record: BondInstrument | ListedProduct,
    row: SourceRow,
) -> None:
    derived_columns = (
        {
            "remaining_days_at_as_of": ("MAT_DT",),
            "is_matured_at_as_of": ("MAT_DT",),
            "has_positive_buyable_quantity": ("BUYABLE_QUANTITY",),
            "is_buyable_validated_at_as_of": ("BUYABLE_QUANTITY", "MAT_DT"),
        }
        if isinstance(record, BondInstrument)
        else {
            "is_eligible_at_as_of": (
                "pd_sale_yn",
                "pd_tr_yn",
                "pd_lstg_dt",
                "pd_lste_dt",
            )
        }
    )
    for field_name, expected_columns in derived_columns.items():
        derived = getattr(record, field_name)
        assert isinstance(derived, DerivedValue)
        assert derived.as_of_date == AS_OF
        assert tuple(locator.source_column_name for locator in derived.inputs) == expected_columns
        for locator, column_name in zip(derived.inputs, expected_columns, strict=True):
            cell = row.cell(column_name)
            assert locator.source_table == row.source_table
            assert locator.source_file == row.source_file
            assert locator.source_sheet == row.source_sheet
            assert locator.source_row_number == row.source_row_number
            assert locator.source_column_name == cell.column_name
            assert locator.source_column_number == cell.excel_column_number
            assert locator.source_column_letter == cell.excel_column_letter
            assert locator.source_checksum == row.source_checksum
            assert locator.source_snapshot_date == row.source_snapshot_date
            assert locator.source_applicable_date == cell.applicable_date


def test_official_domestic_normalization_exhausts_all_rows_with_exact_counts_and_fidelity() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")
    rating_registry = RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")

    bond_ids: set[str] = set()
    bond_source_rows = bond_records = bond_quarantined = 0
    for row in iter_xlsx_rows(verified.data_file("PRBD01N001")):
        bond_source_rows += 1
        assert row.source_snapshot_date == AS_OF
        bond_result = normalize_bond(row, AS_OF, rating_registry)
        bond_quarantined += bond_result.record is None
        assert bond_result.record is not None
        bond_records += 1
        product_id = bond_result.record.product_id.normalized_value
        assert product_id is not None
        assert bond_result.record.product_id.source.source_snapshot_date == AS_OF
        assert product_id not in bond_ids
        bond_ids.add(product_id)
        _assert_wrapped_source_fidelity(bond_result.record, row, BOND_COLUMNS)
        _assert_derived_inputs(bond_result.record, row)

    listed_ids: set[str] = set()
    listed_source_rows = listed_records = listed_quarantined = 0
    source_groups: Counter[str] = Counter()
    produced_groups: Counter[ListedProductType] = Counter()
    quarantined_rows: list[tuple[int, str, tuple[DataQualityIssue, ...]]] = []
    for row in iter_xlsx_rows(verified.data_file("PREF01N001")):
        listed_source_rows += 1
        assert row.source_snapshot_date == AS_OF
        source_groups[row.cell("pd_grp_no").raw_value] += 1
        listed_result = normalize_domestic_listed(row, AS_OF)
        if listed_result.record is None:
            listed_quarantined += 1
            quarantined_rows.append(
                (
                    row.source_row_number,
                    row.cell("pd_itm_no").raw_value,
                    listed_result.issues,
                )
            )
            continue
        listed_records += 1
        product_id = listed_result.record.product_id.normalized_value
        assert product_id is not None
        assert listed_result.record.product_id.source.source_snapshot_date == AS_OF
        assert product_id not in listed_ids
        listed_ids.add(product_id)
        product_type = listed_result.record.product_type.normalized_value
        assert product_type is not None
        produced_groups[product_type] += 1
        _assert_wrapped_source_fidelity(listed_result.record, row, LISTED_COLUMNS)
        _assert_derived_inputs(listed_result.record, row)

    assert bond_source_rows == 42_394
    assert bond_records == 42_394
    assert bond_quarantined == 0
    assert len(bond_ids) == 42_394
    assert listed_source_rows == 1_734
    assert listed_records == 1_733
    assert listed_quarantined == 1
    assert len(listed_ids) == 1_733
    assert source_groups == Counter({"ETF": 1_202, "ETN": 532})
    assert produced_groups == Counter({ListedProductType.ETF: 1_201, ListedProductType.ETN: 532})
    assert bond_source_rows + listed_source_rows == 44_128
    assert len(quarantined_rows) == 1
    excel_row, raw_product_id, issues = quarantined_rows[0]
    assert excel_row == 1_155
    assert raw_product_id == "KR"
    assert any(
        issue.quarantined
        and issue.source.source_row_number == 1_155
        and issue.source.source_column_name == "pd_itm_no"
        for issue in issues
    )
