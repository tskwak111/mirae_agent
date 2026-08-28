"""Focused refreshed domestic-bond lot and parent projection contracts."""

from datetime import date
from decimal import Decimal

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.bonds import normalize_bond_lot, project_bond_instrument
from finproof.domain.bonds import BondInstrument, BondSaleLot
from finproof.domain.quality import QualityStatus
from tests.helpers.source_rows import source_row

AS_OF = date(2026, 8, 22)


def _lot(
    *,
    row_number: int = 2,
    product_id: str = "KR0000000001",
    market: str = "장외",
    sequence: str = "1",
    yield_: str = "3.1",
    price: str = "99",
    trade_price: str = "100",
    quantity: str = "0",
    issue_date: str = "20200101",
    maturity_date: str = "20270822",
    name: str = "테스트 채권",
) -> BondSaleLot:
    result = normalize_bond_lot(
        source_row(
            "PRBD01N001",
            {
                "pd_no": product_id,
                "pd_exg_mkt": market,
                "info_base_dt": "20260822",
                "info_seq": sequence,
                "pd_nm": name,
                "buy_yield": yield_,
                "eval_price": price,
                "trade_price": trade_price,
                "buyable_quantity": quantity,
                "isu_dt": issue_date,
                "mat_dt": maturity_date,
            },
            excel_row=row_number,
        )
    )
    assert result.record is not None
    return result.record


def test_bond_lot_rejects_wrong_source_table() -> None:
    with pytest.raises(NormalizationContractError, match="PRBD01N001"):
        normalize_bond_lot(source_row("PREF01N001"))


def test_bond_models_are_strict_frozen_and_quantity_lives_only_on_lot() -> None:
    assert BondSaleLot.model_config["frozen"] is True
    assert BondInstrument.model_config["frozen"] is True
    assert "buyable_quantity" in BondSaleLot.model_fields
    assert "buyable_quantity" not in BondInstrument.model_fields
    assert "has_positive_buyable_quantity" not in BondInstrument.model_fields
    assert "is_buyable_validated_at_as_of" not in BondInstrument.model_fields


def test_bond_lot_preserves_exact_source_key_quote_quantity_and_row_lineage() -> None:
    lot = _lot(sequence="2", yield_="4.2", price="97", trade_price="98", quantity="999")

    assert lot.source_key.product_id == "KR0000000001"
    assert lot.source_key.exchange_market == "장외"
    assert lot.source_key.info_base_date == "20260822"
    assert lot.source_key.info_seq == "2"
    assert lot.buy_yield.normalized_value == Decimal("4.2")
    assert lot.evaluation_price.normalized_value == Decimal("97")
    assert lot.trade_price.normalized_value == Decimal("98")
    assert lot.buyable_quantity.raw_value == "999"
    assert lot.buyable_quantity.source.source_column_name == "buyable_quantity"
    assert lot.source_row.source_row_number == 2


def test_bond_projection_selects_max_yield_and_same_lot_quote() -> None:
    result = project_bond_instrument(
        (
            _lot(row_number=2, sequence="1", yield_="3.1", price="99", trade_price="100"),
            _lot(row_number=3, sequence="2", yield_="4.2", price="97", trade_price="98"),
        ),
        as_of=AS_OF,
    )

    assert result.record is not None
    assert result.record.buy_yield.normalized_value == Decimal("4.2")
    assert result.record.evaluation_price.normalized_value == Decimal("97")
    assert result.record.trade_price.normalized_value == Decimal("98")
    assert result.record.selected_lot_key.info_seq == "2"
    assert result.record.buy_yield_range.value == (Decimal("3.1"), Decimal("4.2"))


def test_equal_yield_uses_canonical_source_key_not_quantity() -> None:
    result = project_bond_instrument(
        (
            _lot(row_number=3, sequence="2", yield_="4.2", quantity="999"),
            _lot(row_number=2, sequence="1", yield_="4.2", quantity="0"),
        ),
        as_of=AS_OF,
    )

    assert result.record is not None
    assert result.record.selected_lot_key.info_seq == "1"
    assert result.record.selected_lot_key.source_row_number == 2


def test_projection_rejects_mixed_parent_identity_and_duplicate_source_keys() -> None:
    with pytest.raises(ValueError, match="one product"):
        project_bond_instrument(
            (_lot(product_id="KR0000000001"), _lot(product_id="KR0000000002")),
            as_of=AS_OF,
        )
    lot = _lot()
    with pytest.raises(ValueError, match="source key"):
        project_bond_instrument((lot, lot), as_of=AS_OF)


def test_equal_parent_fields_retain_every_equivalent_locator() -> None:
    result = project_bond_instrument(
        (_lot(row_number=9, sequence="1"), _lot(row_number=2, sequence="2")),
        as_of=AS_OF,
    )

    assert result.record is not None
    name_sources = next(item for item in result.record.field_sources if item.field_name == "name")
    assert tuple(source.source_row_number for source in name_sources.sources) == (2, 9)
    assert result.record.name.source == name_sources.sources[0]


def test_conflicting_parent_field_is_unavailable_and_warned_without_losing_lots() -> None:
    result = project_bond_instrument(
        (
            _lot(row_number=2, sequence="1", name="이름 A"),
            _lot(row_number=3, sequence="2", name="이름 B"),
        ),
        as_of=AS_OF,
    )

    assert result.record is not None
    assert result.record.name.normalized_value is None
    assert result.record.name.quality_status is QualityStatus.MIXED_SOURCE_VALUES
    assert any(issue.rule_id == "bond.parent_field_conflict.name" for issue in result.issues)
    name_sources = next(item for item in result.record.field_sources if item.field_name == "name")
    assert len(name_sources.sources) == 2


@pytest.mark.parametrize(
    ("issue_date", "maturity_date", "purchasable", "warning"),
    [
        ("20260823", "20270822", False, None),
        ("20200101", "20260821", False, None),
        ("20200101", "", True, "not source-verifiable"),
        ("20200101", "99991231", True, "not source-verifiable"),
        ("20200101", "20270822", True, None),
    ],
)
def test_purchaseability_uses_issue_end_evidence_never_quantity(
    issue_date: str,
    maturity_date: str,
    purchasable: bool,
    warning: str | None,
) -> None:
    for quantity in ("", "0", "999999"):
        result = project_bond_instrument(
            (
                _lot(
                    issue_date=issue_date,
                    maturity_date=maturity_date,
                    quantity=quantity,
                ),
            ),
            as_of=AS_OF,
        )
        assert result.record is not None
        assert result.record.is_purchasable_at_as_of.value is purchasable
        reasons = tuple(issue.reason for issue in result.issues)
        assert any(warning in reason for reason in reasons) if warning else True


def test_missing_or_invalid_yield_uses_canonical_lot_without_quantity_tie_break() -> None:
    result = project_bond_instrument(
        (
            _lot(row_number=3, sequence="2", yield_="", quantity="999"),
            _lot(row_number=2, sequence="1", yield_="bad", quantity="0"),
        ),
        as_of=AS_OF,
    )

    assert result.record is not None
    assert result.record.selected_lot_key.info_seq == "1"
    assert result.record.buy_yield.normalized_value is None
    assert result.record.buy_yield_range.value is None
