from decimal import Decimal

import pytest

from finproof.domain.query_plan import ResultGrain
from finproof.evaluation.metamorphic import (
    MetamorphicKind,
    MetamorphicObservation,
    MetamorphicRelation,
)


@pytest.mark.parametrize(
    ("kind", "base", "transformed"),
    [
        (
            MetamorphicKind.FILTER_MONOTONICITY,
            MetamorphicObservation(total=8),
            MetamorphicObservation(total=3),
        ),
        (
            MetamorphicKind.SORT_REVERSAL,
            MetamorphicObservation(primary_values=(Decimal("1"), Decimal("2"), Decimal("3"))),
            MetamorphicObservation(primary_values=(Decimal("3"), Decimal("2"), Decimal("1"))),
        ),
        (
            MetamorphicKind.COMPARISON_SIGN,
            MetamorphicObservation(comparison_value=Decimal("-2.5")),
            MetamorphicObservation(comparison_value=Decimal("2.5")),
        ),
        (
            MetamorphicKind.UNIT_DISPLAY_INVARIANCE,
            MetamorphicObservation(product_ids=("A", "B")),
            MetamorphicObservation(product_ids=("A", "B")),
        ),
        (
            MetamorphicKind.IDENTITY_ALIAS_INVARIANCE,
            MetamorphicObservation(product_ids=("O-SPY",)),
            MetamorphicObservation(product_ids=("O-SPY",)),
        ),
        (
            MetamorphicKind.TIE_PRESERVATION,
            MetamorphicObservation(
                product_ids=("A", "B", "C"),
                primary_values=(Decimal("0"), Decimal("0"), Decimal("1")),
                ranks=(1, 1, 3),
            ),
            MetamorphicObservation(
                product_ids=("B", "A", "C"),
                primary_values=(Decimal("0"), Decimal("0"), Decimal("1")),
                ranks=(1, 1, 3),
            ),
        ),
        (
            MetamorphicKind.FUND_ITEM_NON_DUPLICATION,
            MetamorphicObservation(total=3),
            MetamorphicObservation(
                total=3,
                product_ids=("F1", "F2", "F3"),
                result_grain=ResultGrain.FUND_ITEM,
            ),
        ),
    ],
)
def test_required_metamorphic_relations_accept_valid_transformations(
    kind: MetamorphicKind,
    base: MetamorphicObservation,
    transformed: MetamorphicObservation,
) -> None:
    result = MetamorphicRelation(kind=kind).check(base, transformed)

    assert result.passed is True
    assert result.failure is None


@pytest.mark.parametrize(
    ("kind", "base", "transformed"),
    [
        (
            MetamorphicKind.FILTER_MONOTONICITY,
            MetamorphicObservation(total=2),
            MetamorphicObservation(total=3),
        ),
        (
            MetamorphicKind.SORT_REVERSAL,
            MetamorphicObservation(primary_values=(Decimal("1"), Decimal("2"))),
            MetamorphicObservation(primary_values=(Decimal("1"), Decimal("2"))),
        ),
        (
            MetamorphicKind.COMPARISON_SIGN,
            MetamorphicObservation(comparison_value=Decimal("2")),
            MetamorphicObservation(comparison_value=Decimal("2")),
        ),
        (
            MetamorphicKind.UNIT_DISPLAY_INVARIANCE,
            MetamorphicObservation(product_ids=("A", "B")),
            MetamorphicObservation(product_ids=("B", "A")),
        ),
        (
            MetamorphicKind.IDENTITY_ALIAS_INVARIANCE,
            MetamorphicObservation(product_ids=("O-SPY",)),
            MetamorphicObservation(product_ids=("O-IVV",)),
        ),
        (
            MetamorphicKind.TIE_PRESERVATION,
            MetamorphicObservation(),
            MetamorphicObservation(
                product_ids=("A", "B"),
                primary_values=(Decimal("0"), Decimal("0")),
                ranks=(1, 2),
            ),
        ),
        (
            MetamorphicKind.FUND_ITEM_NON_DUPLICATION,
            MetamorphicObservation(),
            MetamorphicObservation(
                total=2,
                product_ids=("F1", "F1"),
                result_grain=ResultGrain.FUND_ITEM,
            ),
        ),
    ],
)
def test_required_metamorphic_relations_report_contract_breaks(
    kind: MetamorphicKind,
    base: MetamorphicObservation,
    transformed: MetamorphicObservation,
) -> None:
    result = MetamorphicRelation(kind=kind).check(base, transformed)

    assert result.passed is False
    assert result.failure
