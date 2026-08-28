"""Official refreshed domestic normalization acceptance checks."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from finproof.data.normalization.bonds import normalize_bond_lot, project_bond_instrument
from finproof.data.source_manifest import SourceFileManifest
from finproof.data.xlsx_stream import iter_xlsx_rows
from finproof.domain.bonds import BOND_LOT_FIELD_COLUMNS, BondSaleLot
from finproof.domain.locators import SourceCellLocator

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SNAPSHOT = date(2026, 8, 24)
BOND_BOUNDARY = date(2026, 8, 22)
pytestmark = [pytest.mark.source_contract, pytest.mark.slow]


def test_official_bond_lots_project_to_unique_quantity_independent_parents() -> None:
    manifest = SourceFileManifest.load(
        ROOT / "source_material/input_manifest.json",
        ROOT / "source_material/schema_catalog.json",
    )
    verified = manifest.verify(ROOT / "source_material")
    lots_by_product: defaultdict[str, list[BondSaleLot]] = defaultdict(list)
    key_counts: Counter[tuple[str, str, str, str, int]] = Counter()

    for row in iter_xlsx_rows(verified.data_file("PRBD01N001")):
        assert row.source_snapshot_date == SOURCE_SNAPSHOT
        result = normalize_bond_lot(row)
        assert result.record is not None
        lot = result.record
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
