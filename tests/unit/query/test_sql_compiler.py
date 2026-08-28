"""Focused closed-AST and SQL compiler tests."""

from decimal import Decimal

import pytest

from finproof.domain.execution import ExecutionSegment, HoldingConstituentFilter
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
        "issue_date",
        "maturity_date",
    )

    with pytest.raises(ValueError, match="native"):
        QueryAst.from_segment(
            segment.model_copy(update={"native_result_grain": ResultGrain.PRODUCT}),
            fields=fields,
        )


@pytest.mark.parametrize(
    ("product_type", "expected_discriminator"),
    [
        (ProductType.DOMESTIC_ETF, "ETF"),
        (ProductType.DOMESTIC_ETN, "ETN"),
        (ProductType.OVERSEAS_ETF, "ETF"),
        (ProductType.OVERSEAS_ETN, "ETN"),
    ],
)
def test_shared_listed_compiler_uses_frozen_physical_product_discriminator(
    product_type: ProductType,
    expected_discriminator: str,
) -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=product_type,
        native_result_grain=ResultGrain.LISTED_PRODUCT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert compiled.parameters == (expected_discriminator,)
    assert '"product_type" = ?' in compiled.sql


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


def test_sql_compiler_defers_ordinal_rating_order_to_the_domain_policy() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        filters=(
            FilterClause(
                field="credit_rating",
                operator=FilterOperator.GTE,
                value="AA-",
            ),
        ),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert '"credit_rating"' in compiled.sql
    assert '"credit_rating" >= ?' not in compiled.sql
    assert compiled.parameters == ()


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

    assert compiled.projected_fields == (
        "product_id",
        "currency",
        "buy_yield",
        "issue_date",
        "maturity_date",
    )
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


@pytest.mark.parametrize(
    "product_type",
    [
        ProductType.DOMESTIC_ETF,
        ProductType.DOMESTIC_ETN,
        ProductType.OVERSEAS_ETF,
        ProductType.OVERSEAS_ETN,
        ProductType.PUBLIC_FUND,
    ],
)
def test_holding_filter_compiles_parameterized_four_part_exists(
    product_type: ProductType,
) -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    segment = ExecutionSegment(
        product_type=product_type,
        native_result_grain=(
            ResultGrain.FUND_ITEM
            if product_type is ProductType.PUBLIC_FUND
            else ResultGrain.LISTED_PRODUCT
        ),
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        holding_constituent_filter=HoldingConstituentFilter(
            constituent_identifier="KR7005930003",
            constituent_identifier_type="ISIN",
        ),
    )

    compiled = SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))

    assert "EXISTS" in compiled.sql
    assert 'FROM "silver_product_holding" AS "holding"' in compiled.sql
    assert '"holding"."owner_product_type" = ?' in compiled.sql
    assert '"holding"."owner_product_id" = "owner".' in compiled.sql
    assert '"holding"."constituent_identifier" = ?' in compiled.sql
    assert '"holding"."constituent_identifier_type" = ?' in compiled.sql
    assert "KR7005930003" not in compiled.sql
    assert compiled.parameters[-3:] == (product_type.value, "KR7005930003", "ISIN")
    assert "UNION" not in compiled.sql
