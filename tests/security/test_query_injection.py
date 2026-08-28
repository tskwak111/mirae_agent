"""Injection resistance for the closed query compiler."""

from datetime import date

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.execution import ExecutionSegment, HoldingConstituentFilter
from finproof.domain.query_plan import (
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.query import (
    FieldRegistry,
    QueryAst,
    ResolutionBundle,
    SemanticValidator,
    SqlCompiler,
    ValidationContext,
)
from finproof.registry.loader import RegistryBundle


def test_query_injection_family_never_reaches_identifier_expression_or_statement_surface() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    payload = "x'); DROP TABLE silver_bond_instrument; --"
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=(
            FilterClause(
                field="product_name",
                operator=FilterOperator.CONTAINS,
                value=payload,
            ),
        ),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
    )
    ast = QueryAst.from_segment(segment, fields=fields)
    compiled = SqlCompiler().compile(ast)
    assert payload not in compiled.sql
    assert compiled.parameters == (payload,)
    assert compiled.sql.count(";") == 0

    with pytest.raises(ValueError, match="table"):
        SqlCompiler().compile(
            ast.model_copy(update={"table_name": 'silver_bond_instrument"; DROP TABLE x; --'})
        )

    plan = QueryPlan(
        intent=Intent.SCREEN,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(FilterClause(field=payload, operator=FilterOperator.EQ, value="x"),),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )
    with pytest.raises(ValueError, match="field"):
        SemanticValidator(fields).validate(
            plan,
            resolutions=ResolutionBundle(results=()),
            context=ValidationContext(
                as_of_date=date(2026, 7, 11),
                execution_mode=ExecutionMode.EVALUATION,
            ),
        )


def test_holding_injection_payload_is_bound_and_never_interpolated() -> None:
    payload = "x'); DROP TABLE silver_product_holding; --"
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_ETN,
        native_result_grain=ResultGrain.LISTED_PRODUCT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        holding_constituent_filter=HoldingConstituentFilter(
            constituent_identifier=payload,
            constituent_identifier_type="LOCAL",
        ),
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert payload not in compiled.sql
    assert payload in compiled.parameters
    assert compiled.sql.count(";") == 0
    assert "EXISTS" in compiled.sql
