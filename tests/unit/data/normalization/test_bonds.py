from datetime import date
from pathlib import Path

import pytest

from finproof.core.errors import NormalizationContractError
from finproof.data.normalization.bonds import normalize_bond
from finproof.domain.bonds import BondInstrument
from finproof.domain.quality import IssueSeverity, QualityStatus
from finproof.registry.rating import RatingRegistry
from tests.helpers.source_rows import source_row

ROOT = Path(__file__).resolve().parents[4]
AS_OF = date(2026, 7, 11)


@pytest.fixture(scope="module")
def rating_registry() -> RatingRegistry:
    return RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")


def test_bond_rejects_wrong_source_table_as_programmer_error(
    rating_registry: RatingRegistry,
) -> None:
    row = source_row("PREF01N001")
    with pytest.raises(NormalizationContractError, match="PRBD01N001"):
        normalize_bond(row, AS_OF, rating_registry)


def test_bond_model_is_explicitly_frozen_forbid_and_strict() -> None:
    assert BondInstrument.model_config["frozen"] is True
    assert BondInstrument.model_config["extra"] == "forbid"
    assert BondInstrument.model_config["strict"] is True


@pytest.mark.parametrize("product_id", ["KR0000000001", "XS0000000001"])
def test_bond_accepts_observed_kr_and_xs_identifier_shapes(
    product_id: str, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(source_row("PRBD01N001", {"PD_NO": product_id}), AS_OF, rating_registry)
    assert result.record is not None
    assert result.record.grain == "instrument"
    assert result.record.product_id.normalized_value == product_id
    assert not any(issue.quarantined for issue in result.issues)


def test_valid_bond_maps_every_declared_source_column(
    rating_registry: RatingRegistry,
) -> None:
    values = {
        "PD_NO": "KR0000000001",
        "PD_NM": "채권명",
        "PD_ABRV_NM": "단축명",
        "CURR_CD": "KRW",
        "BD_KND": "회사채",
        "ISU_DT": "20200101",
        "MAT_DT": "20270711",
        "PD_STD_INFO_UPDATE": "20260710",
        "SRFC_IRT": "1.1",
        "BUY_YIELD": "2.2",
        "BUYABLE_QUANTITY": "3",
        "REMAINING_DAYS": "365",
        "CRD_GRD": "AA0",
        "PD_EVCO_CRD_GRD": "AA",
        "CRD_GRD_DT": "20260709",
        "DUR": "4.4",
        "EVAL_PRICE": "10000",
    }
    columns = {
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
    row = source_row("PRBD01N001", values)
    record = normalize_bond(row, AS_OF, rating_registry).record
    assert record is not None
    for attribute, column in columns.items():
        wrapped = getattr(record, attribute)
        assert wrapped.raw_value == values[column]
        assert wrapped.source.source_column_name == column
    assert record.currency.normalized_value == "KRW"
    assert record.credit_rating.normalized_value == "AA0"
    assert record.remaining_days_at_as_of.value == 365
    assert record.remaining_days_at_as_of.quality_status is QualityStatus.VALID
    assert record.is_matured_at_as_of.value is False
    assert record.is_matured_at_as_of.quality_status is QualityStatus.VALID
    assert record.has_positive_buyable_quantity.value is True
    assert record.has_positive_buyable_quantity.quality_status is QualityStatus.VALID
    assert record.is_buyable_validated_at_as_of.value is True
    assert record.is_buyable_validated_at_as_of.quality_status is QualityStatus.VALID
    assert tuple(
        locator.source_column_name for locator in record.is_buyable_validated_at_as_of.inputs
    ) == ("BUYABLE_QUANTITY", "MAT_DT")


@pytest.mark.parametrize("product_id", ["", "KR", " kr0000000001", "KR0000000001 "])
def test_malformed_bond_identifier_quarantines_with_safe_blocker(
    product_id: str, rating_registry: RatingRegistry
) -> None:
    row = source_row("PRBD01N001", {"PD_NO": product_id}, excel_row=77)
    result = normalize_bond(row, AS_OF, rating_registry)
    assert result.record is None
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.quarantined is True
    assert issue.severity is IssueSeverity.BLOCKER
    assert issue.quality_status is QualityStatus.MALFORMED_SOURCE_ROW
    assert issue.source.source_row_number == 77
    assert issue.source.source_column_name == "PD_NO"
    if product_id:
        assert product_id not in issue.reason


@pytest.mark.parametrize(
    ("raw", "status"),
    [
        ("", QualityStatus.MISSING_BLANK),
        ("0", QualityStatus.SENTINEL_ZERO),
        ("00000000", QualityStatus.SENTINEL_ZERO),
        ("99991231", QualityStatus.SENTINEL_MAX_DATE),
        ("20260230", QualityStatus.INVALID_FORMAT),
    ],
)
def test_bond_maturity_states_never_become_derived_dates(
    raw: str, status: QualityStatus, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(source_row("PRBD01N001", {"MAT_DT": raw}), AS_OF, rating_registry)
    assert result.record is not None
    assert result.record.maturity_date.raw_value == raw
    assert result.record.maturity_date.normalized_value is None
    assert result.record.maturity_date.quality_status is status
    assert result.record.remaining_days_at_as_of.value is None
    assert result.record.is_matured_at_as_of.value is None
    assert result.record.remaining_days_at_as_of.quality_status is status
    assert result.record.is_matured_at_as_of.quality_status is status
    assert any(issue.source.source_column_name == "MAT_DT" for issue in result.issues) is (
        status is QualityStatus.INVALID_FORMAT
    )


def test_bond_recalculates_remaining_days_without_overwriting_source_value(
    rating_registry: RatingRegistry,
) -> None:
    row = source_row(
        "PRBD01N001",
        {"MAT_DT": "20260720", "REMAINING_DAYS": "999"},
        applicable_dates={"MAT_DT": date(2026, 7, 10)},
    )
    record = normalize_bond(row, AS_OF, rating_registry).record
    assert record is not None
    assert record.source_remaining_days.raw_value == "999"
    assert record.source_remaining_days.normalized_value == 999
    assert record.remaining_days_at_as_of.value == 9
    assert record.remaining_days_at_as_of.as_of_date == AS_OF
    assert record.remaining_days_at_as_of.inputs == (record.maturity_date.source,)
    assert record.maturity_date.source.source_applicable_date == date(2026, 7, 10)


@pytest.mark.parametrize(
    ("maturity", "remaining", "matured"),
    [
        ("20260710", -1, True),
        ("20260711", 0, False),
        ("20260712", 1, False),
    ],
)
def test_bond_maturity_is_strictly_before_as_of(
    maturity: str, remaining: int, matured: bool, rating_registry: RatingRegistry
) -> None:
    record = normalize_bond(
        source_row("PRBD01N001", {"MAT_DT": maturity}), AS_OF, rating_registry
    ).record
    assert record is not None
    assert record.remaining_days_at_as_of.value == remaining
    assert record.remaining_days_at_as_of.quality_status is QualityStatus.VALID
    assert record.is_matured_at_as_of.value is matured
    assert record.is_matured_at_as_of.quality_status is QualityStatus.VALID


def test_update_date_is_preserved_without_inferred_applicable_date(
    rating_registry: RatingRegistry,
) -> None:
    row = source_row("PRBD01N001", {"PD_STD_INFO_UPDATE": "20260224", "MAT_DT": "20260720"})
    record = normalize_bond(row, AS_OF, rating_registry).record
    assert record is not None
    assert record.source_update_date.normalized_value == date(2026, 2, 24)
    assert record.source_update_date.source.source_applicable_date is None
    assert record.maturity_date.source.source_applicable_date is None


def test_max_date_sentinel_is_enabled_only_for_bond_maturity(
    rating_registry: RatingRegistry,
) -> None:
    record = normalize_bond(
        source_row(
            "PRBD01N001",
            {
                "ISU_DT": "99991231",
                "MAT_DT": "99991231",
                "PD_STD_INFO_UPDATE": "99991231",
                "CRD_GRD_DT": "99991231",
            },
        ),
        AS_OF,
        rating_registry,
    ).record
    assert record is not None
    assert record.maturity_date.normalized_value is None
    assert record.maturity_date.quality_status is QualityStatus.SENTINEL_MAX_DATE
    assert record.issue_date.normalized_value == date(9999, 12, 31)
    assert record.source_update_date.normalized_value == date(9999, 12, 31)
    assert record.credit_rating_date.normalized_value == date(9999, 12, 31)


@pytest.mark.parametrize(
    (
        "quantity",
        "maturity",
        "positive",
        "positive_status",
        "buyable",
        "buyable_status",
    ),
    [
        ("1", "20260712", True, QualityStatus.VALID, True, QualityStatus.VALID),
        ("0", "20260712", False, QualityStatus.VALID, False, QualityStatus.VALID),
        ("-1", "20260712", False, QualityStatus.VALID, False, QualityStatus.VALID),
        (
            "",
            "20260712",
            None,
            QualityStatus.MISSING_BLANK,
            None,
            QualityStatus.MISSING_BLANK,
        ),
        (
            "bad",
            "20260712",
            None,
            QualityStatus.INVALID_FORMAT,
            None,
            QualityStatus.INVALID_FORMAT,
        ),
        ("1", "20260710", True, QualityStatus.VALID, False, QualityStatus.VALID),
        ("", "20260710", None, QualityStatus.MISSING_BLANK, False, QualityStatus.VALID),
        ("0", "", False, QualityStatus.VALID, False, QualityStatus.VALID),
        ("1", "", True, QualityStatus.VALID, None, QualityStatus.MISSING_BLANK),
    ],
)
def test_bond_buyability_uses_explicit_false_before_unknown(
    quantity: str,
    maturity: str,
    positive: bool | None,
    positive_status: QualityStatus,
    buyable: bool | None,
    buyable_status: QualityStatus,
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"BUYABLE_QUANTITY": quantity, "MAT_DT": maturity}),
        AS_OF,
        rating_registry,
    )
    assert result.record is not None
    assert result.record.has_positive_buyable_quantity.value is positive
    assert result.record.has_positive_buyable_quantity.quality_status is positive_status
    assert result.record.is_buyable_validated_at_as_of.value is buyable
    assert result.record.is_buyable_validated_at_as_of.quality_status is buyable_status
    assert result.record.is_buyable_validated_at_as_of.inputs == (
        result.record.buyable_quantity.source,
        result.record.maturity_date.source,
    )


def test_positive_quantity_on_matured_bond_is_preserved_and_warned(
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"BUYABLE_QUANTITY": "7", "MAT_DT": "20260710"}),
        AS_OF,
        rating_registry,
    )
    assert result.record is not None
    assert result.record.buyable_quantity.normalized_value == 7
    assert result.record.is_buyable_validated_at_as_of.value is False
    assert result.record.is_buyable_validated_at_as_of.quality_status is QualityStatus.VALID
    assert any(
        issue.rule_id == "bond.matured_positive_quantity"
        and issue.severity is IssueSeverity.WARNING
        and issue.quality_status is QualityStatus.MIXED_SOURCE_VALUES
        and not issue.quarantined
        for issue in result.issues
    )


@pytest.mark.parametrize(
    ("column", "attribute"),
    [
        ("SRFC_IRT", "coupon_rate"),
        ("BUY_YIELD", "buy_yield"),
        ("BUYABLE_QUANTITY", "buyable_quantity"),
        ("DUR", "duration"),
        ("EVAL_PRICE", "evaluation_price"),
    ],
)
def test_ordinary_bond_numeric_zero_is_recorded_zero(
    column: str, attribute: str, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(source_row("PRBD01N001", {column: "0"}), AS_OF, rating_registry)
    assert result.record is not None
    wrapped = getattr(result.record, attribute)
    assert wrapped.normalized_value == 0
    assert wrapped.quality_status is QualityStatus.RECORDED_ZERO


def test_invalid_optional_numeric_is_preserved_and_warned(
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"DUR": "not-a-number"}), AS_OF, rating_registry
    )
    assert result.record is not None
    assert result.record.duration.raw_value == "not-a-number"
    assert result.record.duration.normalized_value is None
    assert result.record.duration.quality_status is QualityStatus.INVALID_FORMAT
    assert any(
        issue.source.source_column_name == "DUR"
        and issue.quality_status is QualityStatus.INVALID_FORMAT
        and issue.severity is IssueSeverity.WARNING
        and not issue.quarantined
        for issue in result.issues
    )


@pytest.mark.parametrize(
    ("raw", "value", "status", "has_warning"),
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
    value: str | None,
    status: QualityStatus,
    has_warning: bool,
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(source_row("PRBD01N001", {"CURR_CD": raw}), AS_OF, rating_registry)
    assert result.record is not None
    assert result.record.currency.raw_value == raw
    assert result.record.currency.normalized_value == value
    assert result.record.currency.quality_status is status
    assert (
        any(issue.source.source_column_name == "CURR_CD" for issue in result.issues) is has_warning
    )


@pytest.mark.parametrize(
    ("primary", "status"),
    [
        ("", QualityStatus.MISSING_BLANK),
        ("NR", QualityStatus.MISSING_LITERAL_NULL),
        ("C0", QualityStatus.OUT_OF_DOMAIN),
        ("CC0", QualityStatus.OUT_OF_DOMAIN),
    ],
)
def test_missing_and_unregistered_primary_ratings_remain_unavailable(
    primary: str, status: QualityStatus, rating_registry: RatingRegistry
) -> None:
    result = normalize_bond(source_row("PRBD01N001", {"CRD_GRD": primary}), AS_OF, rating_registry)
    assert result.record is not None
    assert result.record.credit_rating.normalized_value is None
    assert result.record.credit_rating.quality_status is status
    assert any(issue.source.source_column_name == "CRD_GRD" for issue in result.issues) is (
        status is QualityStatus.OUT_OF_DOMAIN
    )


def test_agency_rating_never_backfills_missing_primary(
    rating_registry: RatingRegistry,
) -> None:
    record = normalize_bond(
        source_row("PRBD01N001", {"CRD_GRD": "", "PD_EVCO_CRD_GRD": "AAA"}),
        AS_OF,
        rating_registry,
    ).record
    assert record is not None
    assert record.credit_rating.normalized_value is None
    assert record.credit_rating_agencies_raw.raw_value == "AAA"
    assert record.credit_rating_agencies_raw.normalized_value == "AAA"


@pytest.mark.parametrize(
    ("primary", "agencies", "mixed"),
    [
        ("AA", "AA0, AA", False),
        ("AA", "AA, AA-", True),
        ("AA-", "AA", True),
        ("", "AA, AA-", True),
        ("", "AA, AA0", False),
    ],
)
def test_agency_disagreement_uses_ordinals_and_preserves_primary(
    primary: str,
    agencies: str,
    mixed: bool,
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row("PRBD01N001", {"CRD_GRD": primary, "PD_EVCO_CRD_GRD": agencies}),
        AS_OF,
        rating_registry,
    )
    assert result.record is not None
    assert result.record.credit_rating.raw_value == primary
    assert any(issue.rule_id == "bond.rating_disagreement" for issue in result.issues) is mixed


def test_unregistered_agency_rating_warns_without_altering_primary(
    rating_registry: RatingRegistry,
) -> None:
    result = normalize_bond(
        source_row(
            "PRBD01N001",
            {"CRD_GRD": "AA", "PD_EVCO_CRD_GRD": "AA, UNREGISTERED"},
        ),
        AS_OF,
        rating_registry,
    )
    assert result.record is not None
    assert result.record.credit_rating.normalized_value == "AA"
    assert result.record.credit_rating_agencies_raw.normalized_value == "AA, UNREGISTERED"
    assert any(
        issue.rule_id == "bond.agency_rating_out_of_domain"
        and issue.source.source_column_name == "PD_EVCO_CRD_GRD"
        and issue.quality_status is QualityStatus.OUT_OF_DOMAIN
        for issue in result.issues
    )
