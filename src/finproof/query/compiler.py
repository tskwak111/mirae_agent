"""Compiler for the closed native query AST."""

from decimal import Decimal

from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.domain.query_plan import FilterOperator, ProductType
from finproof.query.ast import CompiledQuery, QueryAst


class SqlCompiler:
    def compile(self, ast: QueryAst) -> CompiledQuery:
        if type(ast) is not QueryAst:
            raise TypeError("SQL compiler requires one exact query AST")
        try:
            spec = TABLE_SPEC_BY_NAME[ast.table_name]
        except KeyError as exc:
            raise ValueError("query AST table is not registered") from exc
        columns = {column.name for column in spec.columns}
        if any(
            projection.table_name != ast.table_name
            or projection.column_name not in columns
            or projection.quality_column_name not in columns
            for projection in ast.projections
        ):
            raise ValueError("query AST projection is not registered")
        by_field = {projection.field_id: projection for projection in ast.projections}
        selected = tuple(
            dict.fromkeys(
                column
                for projection in ast.projections
                for column in (
                    projection.column_name,
                    projection.quality_column_name,
                )
            )
        )
        predicates: list[str] = []
        parameters: list[str | int | Decimal | bool] = []
        if ast.segment.product_type in _SHARED_LISTED_TYPES:
            if "product_type" not in columns:
                raise ValueError("listed product discriminator is not registered")
            predicates.append('"product_type" = ?')
            parameters.append(_LISTED_DISCRIMINATOR[ast.segment.product_type])
        for clause in ast.segment.filters:
            projection = by_field[clause.field]
            if projection.value_type == "ordinal_rating" and clause.operator in {
                FilterOperator.GTE,
                FilterOperator.LTE,
            }:
                continue
            predicate, values = _predicate(projection.column_name, clause.operator, clause.value)
            predicates.append(predicate)
            parameters.extend(values)
        holding_filter = ast.segment.holding_constituent_filter
        if holding_filter is not None:
            holding_spec = TABLE_SPEC_BY_NAME["silver_product_holding"]
            holding_columns = {column.name for column in holding_spec.columns}
            required = {
                "owner_product_type",
                "owner_product_id",
                "constituent_identifier",
                "constituent_identifier_type",
            }
            if not required <= holding_columns:
                raise ValueError("holding relation columns are not registered")
            outer_product_id = by_field["product_id"].column_name
            predicates.append(
                'EXISTS (SELECT 1 FROM "silver_product_holding" AS "holding" WHERE '  # noqa: S608 -- closed registry identifier
                '"holding"."owner_product_type" = ? AND '
                f'"holding"."owner_product_id" = "owner".{_quote(outer_product_id)} AND '
                '"holding"."constituent_identifier" = ? AND '
                '"holding"."constituent_identifier_type" = ?)'
            )
            parameters.extend(
                (
                    ast.segment.product_type.value,
                    holding_filter.constituent_identifier,
                    holding_filter.constituent_identifier_type,
                )
            )
        selected_sql = ", ".join(_quote(column) for column in selected)
        sql = f'SELECT {selected_sql} FROM {_quote(ast.table_name)} AS "owner"'  # noqa: S608 -- closed registry identifiers
        if predicates:
            sql += " WHERE " + " AND ".join(predicates)
        order = [
            f"{_quote(by_field[item.field].column_name)} {item.direction.value.upper()} NULLS LAST"
            for item in ast.segment.sort
        ]
        product_id = _quote(by_field["product_id"].column_name)
        if all(by_field[item.field].field_id != "product_id" for item in ast.segment.sort):
            order.append(f"{product_id} ASC NULLS LAST")
        sql += " ORDER BY " + ", ".join(order)
        return CompiledQuery(
            product_type=ast.segment.product_type,
            native_result_grain=ast.segment.native_result_grain,
            table_name=ast.table_name,
            projected_fields=tuple(projection.field_id for projection in ast.projections),
            sql=sql,
            parameters=tuple(parameters),
        )


_SHARED_LISTED_TYPES = {
    ProductType.DOMESTIC_ETF,
    ProductType.DOMESTIC_ETN,
    ProductType.OVERSEAS_ETF,
    ProductType.OVERSEAS_ETN,
}

_LISTED_DISCRIMINATOR = {
    ProductType.DOMESTIC_ETF: "ETF",
    ProductType.DOMESTIC_ETN: "ETN",
    ProductType.OVERSEAS_ETF: "ETF",
    ProductType.OVERSEAS_ETN: "ETN",
}


def _quote(identifier: str) -> str:
    return f'"{identifier}"'


def _predicate(
    column: str,
    operator: FilterOperator,
    value: str | int | Decimal | bool | tuple[str | int | Decimal | bool, ...] | None,
) -> tuple[str, tuple[str | int | Decimal | bool, ...]]:
    quoted = _quote(column)
    binary = {
        FilterOperator.EQ: "=",
        FilterOperator.NE: "!=",
        FilterOperator.GT: ">",
        FilterOperator.GTE: ">=",
        FilterOperator.LT: "<",
        FilterOperator.LTE: "<=",
    }
    if operator in binary:
        if value is None or isinstance(value, tuple):
            raise ValueError("filter operator requires one scalar")
        return f"{quoted} {binary[operator]} ?", (value,)
    if operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
        assert isinstance(value, tuple)
        keyword = "IN" if operator is FilterOperator.IN else "NOT IN"
        return f"{quoted} {keyword} ({', '.join('?' for _ in value)})", value
    if operator is FilterOperator.BETWEEN:
        assert isinstance(value, tuple)
        return f"{quoted} BETWEEN ? AND ?", value
    if operator is FilterOperator.CONTAINS:
        if type(value) is not str:
            raise ValueError("contains requires one string")
        return f"strpos({quoted}, ?) > 0", (value,)
    if operator is FilterOperator.STARTS_WITH:
        if type(value) is not str:
            raise ValueError("starts-with requires one string")
        return f"starts_with({quoted}, ?)", (value,)
    if operator is FilterOperator.IS_MISSING:
        return f"{quoted} IS NULL", ()
    if operator is FilterOperator.IS_NOT_MISSING:
        return f"{quoted} IS NOT NULL", ()
    raise ValueError("filter operator is not registered")
