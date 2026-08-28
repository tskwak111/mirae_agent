"""Official refreshed domestic normalization acceptance checks."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from finproof.data.normalization.bonds import normalize_bond_lot, project_bond_instrument
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.data.source_manifest import SourceFileManifest
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.bonds import BOND_LOT_FIELD_COLUMNS, BondSaleLot
from finproof.domain.domestic_listed import (
    DOMESTIC_FIELD_COLUMNS,
    ListedProduct,
    ListedProductType,
)
from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import DataQualityIssue, QualityStatus
from finproof.domain.source import SourceRow
from finproof.domain.values import DerivedValue, NormalizedValue
from finproof.registry.rating import RatingRegistry

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SNAPSHOT = date(2026, 8, 24)
BOND_BOUNDARY = date(2026, 8, 22)
RATING_REGISTRY = RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")
pytestmark = [pytest.mark.source_contract, pytest.mark.slow]


def test_official_bond_lots_project_to_unique_quantity_independent_parents() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")
    lots_by_product: defaultdict[str, list[BondSaleLot]] = defaultdict(list)
    key_counts: Counter[tuple[str, str, str, str, int]] = Counter()
    out_of_domain_ratings = 0

    for row in iter_xlsx_rows(verified.data_file("PRBD01N001")):
        assert row.source_snapshot_date == SOURCE_SNAPSHOT
        result = normalize_bond_lot(row, RATING_REGISTRY)
        assert result.record is not None
        lot = result.record
        if lot.credit_rating.quality_status is QualityStatus.OUT_OF_DOMAIN:
            out_of_domain_ratings += 1
            assert lot.credit_rating.normalized_value is None
            assert any(issue.rule_id == "bond.credit_rating" for issue in result.issues)
        product_id = lot.product_id.normalized_value
        assert product_id is not None
        lots_by_product[product_id].append(lot)
        key_counts[
            (
                lot.source_key.product_id,
                lot.source_key.exchange_market,
                lot.source_key.info_base_date,
                lot.source_key.info_seq,
                lot.source_key.source_row_number,
            )
        ] += 1
        for field_name, column_name in BOND_LOT_FIELD_COLUMNS.items():
            wrapped = getattr(lot, field_name)
            assert wrapped.raw_value == row.cell(column_name).raw_value
            assert wrapped.source == SourceCellLocator.from_row(row, column_name)

    assert sum(map(len, lots_by_product.values())) == 21_882
    assert len(key_counts) == 21_882
    assert set(key_counts.values()) == {1}
    assert len(lots_by_product) == 20_497
    assert sum(len(lots) > 1 for lots in lots_by_product.values()) == 1_078
    assert out_of_domain_ratings == 103

    for lots in lots_by_product.values():
        projection = project_bond_instrument(lots, as_of=BOND_BOUNDARY)
        assert projection.record is not None
        parent = projection.record
        assert parent.product_id.normalized_value == lots[0].product_id.normalized_value

        quantity_mutants = tuple(
            lot.model_copy(
                update={
                    "buyable_quantity": lot.buyable_quantity.model_copy(
                        update={
                            "raw_value": f"ignored-{index}",
                            "normalized_value": Decimal(index),
                        }
                    )
                }
            )
            for index, lot in enumerate(lots, start=1)
        )
        quantity_independent = project_bond_instrument(
            quantity_mutants,
            as_of=BOND_BOUNDARY,
        )
        assert quantity_independent.record == parent


def test_official_domestic_listed_preserves_existing_mapped_source_contract() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")
    source = verified.data_file("PREF01N001")
    assert len(DOMESTIC_FIELD_COLUMNS) == 98
    assert tuple(DOMESTIC_FIELD_COLUMNS.values()) == source.expected_headers
    source_groups: Counter[str] = Counter()
    produced_groups: Counter[ListedProductType] = Counter()
    metric_quality: dict[str, Counter[QualityStatus]] = {
        field_name: Counter() for field_name in ("total_fee", "tracking_error", "return_1y")
    }
    admitted_blank_suspensions: list[ListedProduct] = []
    product_ids: set[str] = set()
    quarantined: list[tuple[int, str, tuple[DataQualityIssue, ...]]] = []
    source_rows = records = 0

    for row in iter_xlsx_rows(source):
        source_rows += 1
        assert row.source_snapshot_date == SOURCE_SNAPSHOT
        source_groups[row.cell("pd_grp_no").raw_value] += 1
        result = normalize_domestic_listed(row, BOND_BOUNDARY)
        if result.record is None:
            quarantined.append(
                (
                    row.source_row_number,
                    row.cell("pd_itm_no").raw_value,
                    result.issues,
                )
            )
            continue
        records += 1
        record = result.record
        product_id = record.product_id.normalized_value
        product_type = record.product_type.normalized_value
        assert product_id is not None
        assert product_type is not None
        assert product_id not in product_ids
        product_ids.add(product_id)
        produced_groups[product_type] += 1
        for field_name, counter in metric_quality.items():
            counter[getattr(record, field_name).quality_status] += 1
        if record.suspension_flag.raw_value == "":
            admitted_blank_suspensions.append(record)
        _assert_listed_source_fidelity(record, row)

    assert source_rows == 1_780
    assert records == 1_779
    assert len(product_ids) == 1_779
    assert source_groups == Counter({"ETF": 1_235, "ETN": 545})
    assert produced_groups == Counter({ListedProductType.ETF: 1_234, ListedProductType.ETN: 545})
    assert len(admitted_blank_suspensions) == 2
    assert all(
        record.suspension_flag.normalized_value is None
        and record.suspension_flag.quality_status is QualityStatus.MISSING_BLANK
        for record in admitted_blank_suspensions
    )
    assert metric_quality == {
        "total_fee": Counter(
            {
                QualityStatus.MISSING_BLANK: 1_562,
                QualityStatus.RECORDED_ZERO: 150,
                QualityStatus.VALID: 67,
            }
        ),
        "tracking_error": Counter(
            {
                QualityStatus.VALID: 1_160,
                QualityStatus.RECORDED_ZERO: 438,
                QualityStatus.MISSING_BLANK: 181,
            }
        ),
        "return_1y": Counter(
            {
                QualityStatus.VALID: 1_396,
                QualityStatus.MISSING_BLANK: 363,
                QualityStatus.RECORDED_ZERO: 20,
            }
        ),
    }
    assert len(quarantined) == 1
    excel_row, raw_product_id, issues = quarantined[0]
    assert (excel_row, raw_product_id) == (224, "KR")
    assert any(
        issue.quarantined
        and issue.source.source_row_number == 224
        and issue.source.source_column_name == "pd_itm_no"
        for issue in issues
    )


def _assert_listed_source_fidelity(record: ListedProduct, row: SourceRow) -> None:
    for field_name, column_name in DOMESTIC_FIELD_COLUMNS.items():
        wrapped = getattr(record, field_name)
        assert isinstance(wrapped, NormalizedValue)
        assert wrapped.raw_value == row.cell(column_name).raw_value
        assert wrapped.source == SourceCellLocator.from_row(row, column_name)
    eligibility = record.is_eligible_at_as_of
    assert isinstance(eligibility, DerivedValue)
    assert eligibility.as_of_date == BOND_BOUNDARY
    assert tuple(source.source_column_name for source in eligibility.inputs) == (
        "pd_sale_yn",
        "pd_tr_yn",
        "pd_lstg_dt",
        "pd_lste_dt",
    )
