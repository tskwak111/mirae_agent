"""Focused product-state policy tests."""

from datetime import date

import pytest

from finproof.domain.query_plan import ProductType


def test_quality_policy_skeleton_exposes_exact_interfaces() -> None:
    from finproof.quality import (
        MetricPolicy,
        PolicyEngine,
        PolicyExecutionResult,
        StateEvaluation,
        StatePolicy,
    )

    assert all(
        isinstance(value, type)
        for value in (
            MetricPolicy,
            PolicyEngine,
            PolicyExecutionResult,
            StateEvaluation,
            StatePolicy,
        )
    )


def test_domestic_listed_zero_suspension_flag_is_not_suspended() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import PolicyProduct, StatePolicy
    from finproof.storage import RawFieldValue

    product = PolicyProduct(
        product_type=ProductType.DOMESTIC_ETF,
        product_id="ETF1",
        values=(
            RawFieldValue(field_id="suspension_flag", value=False, quality_status="valid"),
            RawFieldValue(field_id="saleable", value=True, quality_status="valid"),
            RawFieldValue(field_id="listing_date", value=date(2020, 1, 1), quality_status="valid"),
            RawFieldValue(
                field_id="listing_end_date",
                value=None,
                quality_status="sentinel_max_date",
            ),
        ),
    )

    result = StatePolicy().evaluate(product, as_of=date(2026, 7, 11))

    assert result.eligible is True
    assert "suspended" not in result.state_ids


@pytest.mark.parametrize(
    ("listing_date", "listing_end_date", "end_quality", "expected"),
    [
        (date(2026, 7, 12), None, "sentinel_max_date", False),
        (date(2020, 1, 1), date(2026, 7, 10), "valid", False),
        (date(2020, 1, 1), None, "sentinel_max_date", True),
    ],
)
def test_domestic_listed_state_honors_listing_period_and_open_end(
    listing_date: date,
    listing_end_date: date | None,
    end_quality: str,
    expected: bool,
) -> None:
    from finproof.quality import PolicyProduct, StatePolicy
    from finproof.storage import RawFieldValue

    product = PolicyProduct(
        product_type=ProductType.DOMESTIC_ETF,
        product_id="ETF1",
        values=(
            RawFieldValue(field_id="suspension_flag", value=False, quality_status="valid"),
            RawFieldValue(field_id="saleable", value=True, quality_status="valid"),
            RawFieldValue(field_id="listing_date", value=listing_date, quality_status="valid"),
            RawFieldValue(
                field_id="listing_end_date",
                value=listing_end_date,
                quality_status=end_quality,
            ),
        ),
    )

    assert StatePolicy().evaluate(product, as_of=date(2026, 7, 11)).eligible is expected


def test_ended_bond_is_not_purchasable_even_with_irrelevant_positive_quantity() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import PolicyProduct, StatePolicy
    from finproof.storage import RawFieldValue

    product = PolicyProduct(
        product_type=ProductType.DOMESTIC_BOND,
        product_id="B1",
        values=(
            RawFieldValue(
                field_id="buyable_quantity",
                value=10,
                quality_status="valid",
            ),
            RawFieldValue(
                field_id="issue_date",
                value=date(2020, 1, 1),
                quality_status="valid",
            ),
            RawFieldValue(
                field_id="maturity_date",
                value=date(2026, 7, 10),
                quality_status="valid",
            ),
        ),
    )

    result = StatePolicy().evaluate(product, as_of=date(2026, 7, 11))

    assert result.eligible is False
    assert result.state_ids == ("ended",)


def test_bond_maturing_on_as_of_date_remains_purchasable() -> None:
    from finproof.quality import PolicyProduct, StatePolicy
    from finproof.storage import RawFieldValue

    product = PolicyProduct(
        product_type=ProductType.DOMESTIC_BOND,
        product_id="B1",
        values=(
            RawFieldValue(field_id="issue_date", value=date(2020, 1, 1), quality_status="valid"),
            RawFieldValue(
                field_id="maturity_date",
                value=date(2026, 7, 11),
                quality_status="valid",
            ),
        ),
    )

    result = StatePolicy().evaluate(product, as_of=date(2026, 7, 11))

    assert result.eligible is True
    assert result.state_ids == ("purchasable_assumed",)


@pytest.mark.parametrize("quantity", [None, 0, 10])
def test_bond_with_missing_maturity_uses_assumption_and_quantity_never_changes_result(
    quantity: int | None,
) -> None:
    from finproof.quality import PolicyProduct, StatePolicy
    from finproof.storage import RawFieldValue

    result = StatePolicy().evaluate(
        PolicyProduct(
            product_type=ProductType.DOMESTIC_BOND,
            product_id="B1",
            values=(
                RawFieldValue(
                    field_id="buyable_quantity",
                    value=quantity,
                    quality_status="valid",
                ),
                RawFieldValue(
                    field_id="issue_date",
                    value=date(2020, 1, 1),
                    quality_status="valid",
                ),
                RawFieldValue(
                    field_id="maturity_date",
                    value=None,
                    quality_status="missing_blank",
                ),
            ),
        ),
        as_of=date(2026, 7, 11),
    )

    assert result.eligible is True
    assert result.state_ids == ("unknown_maturity", "purchasable_assumed")
    assert result.warnings == ("bond end state is not source-verifiable",)


def test_future_issue_date_excludes_bond_under_organizer_assumption() -> None:
    from finproof.quality import PolicyProduct, StatePolicy
    from finproof.storage import RawFieldValue

    result = StatePolicy().evaluate(
        PolicyProduct(
            product_type=ProductType.DOMESTIC_BOND,
            product_id="B1",
            values=(
                RawFieldValue(
                    field_id="issue_date", value=date(2026, 7, 12), quality_status="valid"
                ),
                RawFieldValue(
                    field_id="maturity_date",
                    value=date(2027, 7, 11),
                    quality_status="valid",
                ),
            ),
        ),
        as_of=date(2026, 7, 11),
    )

    assert result.eligible is False
    assert result.state_ids == ("not_yet_issued",)


@pytest.mark.parametrize(
    "product_type",
    [ProductType.OVERSEAS_ETF, ProductType.OVERSEAS_ETN, ProductType.PUBLIC_FUND],
)
def test_unsupported_overseas_and_public_fund_validated_eligibility_fails_closed(
    product_type: ProductType,
) -> None:
    from finproof.quality import PolicyProduct, StatePolicy

    with pytest.raises(ValueError, match="not implemented"):
        StatePolicy().evaluate(
            PolicyProduct(product_type=product_type, product_id="P1", values=()),
            as_of=date(2026, 7, 11),
        )
