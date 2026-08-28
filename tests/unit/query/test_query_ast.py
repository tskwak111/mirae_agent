"""Refreshed bond AST state-input boundaries."""

import pytest

from finproof.domain.execution import ExecutionSegment
from finproof.domain.query_plan import FilterClause, FilterOperator, ProductType, ResultGrain
from finproof.query import FieldRegistry, QueryAst
from finproof.registry.loader import RegistryBundle


def _segment(*, filters: tuple[FilterClause, ...] = ()) -> ExecutionSegment:
    return ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=filters,
        metrics=("buy_yield",),
        sort=(),
        aggregation=None,
        top_k=5,
    )


def test_bond_ast_adds_only_issue_and_maturity_state_inputs() -> None:
    ast = QueryAst.from_segment(
        _segment(), fields=FieldRegistry.from_bundle(RegistryBundle.from_package())
    )

    assert tuple(item.field_id for item in ast.projections) == (
        "product_id",
        "buy_yield",
        "issue_date",
        "maturity_date",
    )
    assert "buyable_quantity" not in tuple(item.field_id for item in ast.projections)


def test_bond_ast_rejects_removed_buyable_quantity_even_if_forged_in_segment() -> None:
    segment = _segment(
        filters=(FilterClause(field="buyable_quantity", operator=FilterOperator.GT, value=0),)
    )

    with pytest.raises(ValueError, match="not registered"):
        QueryAst.from_segment(
            segment, fields=FieldRegistry.from_bundle(RegistryBundle.from_package())
        )
