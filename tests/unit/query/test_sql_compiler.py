"""Focused closed-AST and SQL compiler tests."""

from decimal import Decimal

import pytest

from finproof.domain.execution import ExecutionSegment
from finproof.domain.query_plan import (
    AggregationFunction,
    AggregationSpec,
    FilterClause,
    FilterOperator,
    ProductType,
    ResultGrain,
    SortDirection,
    SortSpec,
)
from finproof.query import FieldRegistry, QueryAst, SqlCompiler
from finproof.registry.loader import RegistryBundle


def test_query_ast_accepts_one_native_segment_and_rejects_product_envelope() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=("buy_yield",),
        sort=(),
        aggregation=None,
        top_k=5,
    )

    ast = QueryAst.from_segment(segment, fields=fields)

    assert ast.segment is segment
    assert ast.table_name == "silver_bond_instrument"
    assert tuple(item.field_id for item in ast.projections) == (
        "product_id",
        "buy_yield",
    )

    with pytest.raises(ValueError, match="native"):
        QueryAst.from_segment(
            segment.model_copy(update={"native_result_grain": ResultGrain.PRODUCT}),
            fields=fields,
        )


def test_sql_compiler_parameterizes_every_value_and_uses_closed_identifiers() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=(
            FilterClause(
                field="buy_yield",
                operator=FilterOperator.GT,
                value=Decimal("1.5"),
            ),
            FilterClause(
                field="product_name",
                operator=FilterOperator.EQ,
                value="Bond One",
            ),
        ),
        metrics=("buy_yield",),
        sort=(),
        aggregation=None,
        top_k=5,
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert compiled.product_type is ProductType.DOMESTIC_BOND
    assert compiled.parameters == (Decimal("1.5"), "Bond One")
    assert 'FROM "silver_bond_instrument"' in compiled.sql
    assert '"buy_yield" > ?' in compiled.sql
    assert '"name" = ?' in compiled.sql
    assert "1.5" not in compiled.sql
    assert "Bond One" not in compiled.sql


def test_contains_and_starts_with_treat_wildcards_controls_and_unicode_as_literal_data() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    values = ("%_\\\x00한글", "시작%_")
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=(
            FilterClause(
                field="product_name",
                operator=FilterOperator.CONTAINS,
                value=values[0],
            ),
            FilterClause(
                field="product_name",
                operator=FilterOperator.STARTS_WITH,
                value=values[1],
            ),
        ),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert compiled.parameters == values
    assert "strpos" in compiled.sql
    assert "starts_with" in compiled.sql
    assert "LIKE" not in compiled.sql
    assert all(value not in compiled.sql for value in values)


def test_compiler_projects_aggregate_inputs_without_prepolicy_aggregation_or_top_k() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=AggregationSpec(
            function=AggregationFunction.AVG,
            field="buy_yield",
            group_by=("currency",),
        ),
        top_k=3,
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert compiled.projected_fields == ("product_id", "currency", "buy_yield")
    assert '"currency"' in compiled.sql
    assert '"buy_yield"' in compiled.sql
    assert "AVG(" not in compiled.sql
    assert "GROUP BY" not in compiled.sql
    assert "LIMIT" not in compiled.sql


def test_compiler_uses_deterministic_null_and_product_id_ordering_only_as_display_stability() -> (
    None
):
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=("buy_yield",),
        sort=(SortSpec(field="buy_yield", direction=SortDirection.DESC),),
        aggregation=None,
        top_k=1,
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert compiled.sql.endswith(
        'ORDER BY "buy_yield" DESC NULLS LAST, "product_id" ASC NULLS LAST'
    )
    assert "LIMIT" not in compiled.sql
