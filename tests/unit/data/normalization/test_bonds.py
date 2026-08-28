"""Focused refreshed domestic-bond lot and parent projection contracts."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.bonds import normalize_bond_lot, project_bond_instrument
from finproof.domain.bonds import BOND_LOT_FIELD_COLUMNS, BondInstrument, BondSaleLot
from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import IssueSeverity, QualityStatus
from finproof.registry.rating import RatingRegistry
from tests.helpers.source_rows import source_row

AS_OF = date(2026, 8, 22)
ROOT = Path(__file__).resolve().parents[4]
RATING_REGISTRY = RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")


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
        ),
        RATING_REGISTRY,
    )
    assert result.record is not None
    return result.record


def test_bond_lot_rejects_wrong_source_table() -> None:
    with pytest.raises(NormalizationContractError, match="PRBD01N001"):
        normalize_bond_lot(source_row("PREF01N001"), RATING_REGISTRY)


@pytest.mark.parametrize(
    ("raw", "normalized", "status", "warned"),
    [
        ("C0", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("AA０", "AA0", QualityStatus.VALID, False),  # noqa: RUF001 -- exact alias
        ("AA-", "AA-", QualityStatus.VALID, False),
        ("NR", None, QualityStatus.MISSING_LITERAL_NULL, False),
    ],
)
def test_bond_lot_resolves_primary_rating_through_registry(
    raw: str,
    normalized: str | None,
    status: QualityStatus,
    warned: bool,
) -> None:
    result = normalize_bond_lot(
        source_row("PRBD01N001", {"crd_grd": raw}),
        RATING_REGISTRY,
    )

    assert result.record is not None
    assert result.record.credit_rating.raw_value == raw
    assert result.record.credit_rating.normalized_value == normalized
    assert result.record.credit_rating.quality_status is status
    assert (
        any(
            issue.rule_id == "bond.credit_rating"
            and issue.source.source_column_name == "crd_grd"
            and issue.severity is IssueSeverity.WARNING
            and not issue.quarantined
            for issue in result.issues
        )
        is warned
    )


@pytest.mark.parametrize(
    ("values", "column"),
    [
        ({"pd_no": "KR"}, "pd_no"),
        ({"pd_no": " KR0000000001"}, "pd_no"),
        ({"pd_exg_mkt": ""}, "pd_exg_mkt"),
        ({"info_base_dt": "20260230"}, "info_base_dt"),
        ({"info_seq": "0"}, "info_seq"),
        ({"info_seq": "1.5"}, "info_seq"),
    ],
)
def test_malformed_bond_lot_identity_quarantines_with_safe_blocker(
    values: dict[str, str],
    column: str,
) -> None:
    result = normalize_bond_lot(
        source_row("PRBD01N001", values, excel_row=77),
        RATING_REGISTRY,
    )

    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.quarantined is True
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.source.source_row_number == 77
    assert issue.source.source_column_name == column
    assert all(raw not in issue.reason for raw in values.values() if raw)


def test_valid_bond_lot_maps_every_declared_source_cell_exactly() -> None:
    values = {
        "pd_no": "XS0000000001",
        "pd_exg_mkt": "장외",
        "info_base_dt": "20260822",
        "info_seq": "7",
        "pd_nm": "채권명",
        "pd_abrv_nm": "단축명",
        "curr_cd": "USD",
        "bd_knd": "회사채",
        "isu_dt": "20200101",
        "mat_dt": "20270822",
        "pd_std_info_update": "20260821",
        "srfc_irt": "1.1",
        "buy_yield": "2.2",
        "buyable_quantity": "3",
        "remaining_days": "365",
        "crd_grd": "AA０",  # noqa: RUF001 -- exact source alias
        "crd_grd_dt": "20260820",
        "dur": "4.4",
        "eval_price": "10000",
        "trade_price": "9990",
    }
    row = source_row("PRBD01N001", values, excel_row=42)
    result = normalize_bond_lot(row, RATING_REGISTRY)

    assert result.record is not None
    lot = result.record
    for field_name, column_name in BOND_LOT_FIELD_COLUMNS.items():
        wrapped = getattr(lot, field_name)
        assert wrapped.raw_value == row.cell(column_name).raw_value
        assert wrapped.source == SourceCellLocator.from_row(row, column_name)
    assert lot.product_id.normalized_value == "XS0000000001"
    assert lot.credit_rating.normalized_value == "AA0"


@pytest.mark.parametrize(
    ("raw", "status", "warned"),
    [
        ("", QualityStatus.MISSING_BLANK, False),
        ("0", QualityStatus.SENTINEL_ZERO, False),
        ("00000000", QualityStatus.SENTINEL_ZERO, False),
        ("99991231", QualityStatus.SENTINEL_MAX_DATE, False),
        ("20260230", QualityStatus.INVALID_FORMAT, True),
    ],
)
def test_bond_maturity_quality_and_warning_remain_source_faithful(
    raw: str,
    status: QualityStatus,
    warned: bool,
) -> None:
    result = normalize_bond_lot(
        source_row("PRBD01N001", {"mat_dt": raw}),
        RATING_REGISTRY,
    )

    assert result.record is not None
    assert result.record.maturity_date.raw_value == raw
    assert result.record.maturity_date.normalized_value is None
    assert result.record.maturity_date.quality_status is status
    assert (
        any(
            issue.source.source_column_name == "mat_dt"
            and issue.quality_status is QualityStatus.INVALID_FORMAT
            for issue in result.issues
        )
        is warned
    )


def test_bond_projection_recalculates_remaining_days_without_overwriting_source() -> None:
    row = source_row(
        "PRBD01N001",
        {"mat_dt": "20260831", "remaining_days": "999"},
        applicable_dates={"mat_dt": date(2026, 8, 21)},
    )
    lot_result = normalize_bond_lot(row, RATING_REGISTRY)
    assert lot_result.record is not None
    result = project_bond_instrument((lot_result.record,), as_of=AS_OF)

    assert result.record is not None
    assert result.record.source_remaining_days.raw_value == "999"
    assert result.record.source_remaining_days.normalized_value == 999
    assert result.record.remaining_days_at_as_of.value == 9
    assert result.record.remaining_days_at_as_of.inputs == (lot_result.record.maturity_date.source,)
    assert result.record.maturity_date.source.source_applicable_date == date(2026, 8, 21)


@pytest.mark.parametrize(
    ("column", "field_name"),
    [
        ("srfc_irt", "coupon_rate"),
        ("buy_yield", "buy_yield"),
        ("buyable_quantity", "buyable_quantity"),
        ("dur", "duration"),
        ("eval_price", "evaluation_price"),
        ("trade_price", "trade_price"),
    ],
)
def test_bond_lot_numeric_zero_remains_recorded_zero(
    column: str,
    field_name: str,
) -> None:
    result = normalize_bond_lot(
        source_row("PRBD01N001", {column: "0"}),
        RATING_REGISTRY,
    )

    assert result.record is not None
    wrapped = getattr(result.record, field_name)
    assert wrapped.normalized_value == 0
    assert wrapped.quality_status is QualityStatus.RECORDED_ZERO


def test_invalid_optional_numeric_is_preserved_and_warned() -> None:
    result = normalize_bond_lot(
        source_row("PRBD01N001", {"dur": "not-a-number"}),
        RATING_REGISTRY,
    )

    assert result.record is not None
    assert result.record.duration.raw_value == "not-a-number"
    assert result.record.duration.normalized_value is None
    assert result.record.duration.quality_status is QualityStatus.INVALID_FORMAT
    assert any(
        issue.source.source_column_name == "dur"
        and issue.quality_status is QualityStatus.INVALID_FORMAT
        and issue.severity is IssueSeverity.WARNING
        and not issue.quarantined
        for issue in result.issues
    )


@pytest.mark.parametrize(
    ("raw", "normalized", "status", "warned"),
    [
        ("KRW", "KRW", QualityStatus.VALID, False),
        ("USD", "USD", QualityStatus.VALID, False),
        ("000", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("krw", None, QualityStatus.OUT_OF_DOMAIN, True),
        ("", None, QualityStatus.MISSING_BLANK, False),
    ],
)
def test_bond_currency_requires_exact_uppercase_three_letter_code(
    raw: str,
    normalized: str | None,
    status: QualityStatus,
    warned: bool,
) -> None:
    result = normalize_bond_lot(
        source_row("PRBD01N001", {"curr_cd": raw}),
        RATING_REGISTRY,
    )

    assert result.record is not None
    assert result.record.currency.raw_value == raw
    assert result.record.currency.normalized_value == normalized
    assert result.record.currency.quality_status is status
    assert (
        any(
            issue.source.source_column_name == "curr_cd"
            and issue.quality_status is QualityStatus.OUT_OF_DOMAIN
            for issue in result.issues
        )
        is warned
    )


def test_bond_models_are_strict_frozen_and_quantity_lives_only_on_lot() -> None:
    assert BondSaleLot.model_config["frozen"] is True
    assert BondInstrument.model_config["frozen"] is True
    assert BondSaleLot.model_config["extra"] == "forbid"
    assert BondSaleLot.model_config["strict"] is True
    assert BondInstrument.model_config["extra"] == "forbid"
    assert BondInstrument.model_config["strict"] is True
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
