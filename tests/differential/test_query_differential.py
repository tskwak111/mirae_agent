"""Independent reference versus DuckDB raw projections."""

from datetime import date
from decimal import Decimal

import duckdb
import pytest

from finproof.domain.query_plan import FilterClause, FilterOperator, ProductType, ResultGrain
from finproof.storage import RawFieldValue


def test_reference_executor_is_independent_of_production_sql_and_compiler_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    import finproof.query.compiler as compiler_module
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ReferenceExecutor,
        ResolutionBundle,
        SemanticValidator,
        SqlCompiler,
    )
    from finproof.query.reference import FixtureRow
    from finproof.registry.loader import RegistryBundle

    monkeypatch.setattr(
        SqlCompiler,
        "compile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("compiler used")),
    )
    monkeypatch.setattr(
        compiler_module,
        "_predicate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("SQL helper used")),
    )
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        filters=(
            FilterClause(
                field="buy_yield",
                operator=FilterOperator.GT,
                value=Decimal("2"),
            ),
        )
    )
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = (
        FixtureRow(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            product_id="B1",
            values=(
                RawFieldValue(field_id="product_id", value="B1", quality_status="valid"),
                RawFieldValue(field_id="buy_yield", value=Decimal("3"), quality_status="valid"),
            ),
        ),
    )

    result = ReferenceExecutor().execute(rows, bundle)

    assert result.candidate_count == 1
    assert result.segments[0].rows[0].product_id == "B1"


def test_duckdb_and_reference_raw_projections_are_equal() -> None:
    from tests.integration.query.test_executor import _session
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        QueryExecutor,
        ReferenceExecutor,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.query.reference import FixtureRow
    from finproof.registry.loader import RegistryBundle

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        filters=(
            FilterClause(
                field="buy_yield",
                operator=FilterOperator.GT,
                value=Decimal("2"),
            ),
        )
    )
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    fixture_rows = tuple(
        FixtureRow(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            product_id=product_id,
            values=(
                RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                RawFieldValue(field_id="buy_yield", value=value, quality_status="valid"),
                RawFieldValue(
                    field_id="issue_date",
                    value=date(2020, 1, 1),
                    quality_status="valid",
                ),
                RawFieldValue(
                    field_id="maturity_date",
                    value=date(2027, 7, 11),
                    quality_status="valid",
                ),
            ),
        )
        for product_id, value in (("B1", Decimal("3")), ("B2", Decimal("1")))
    )
    connection = duckdb.connect(":memory:")
    connection.execute(
        "CREATE TABLE silver_bond_instrument ("
        "product_id VARCHAR, product_id__quality_status VARCHAR, "
        "buy_yield DECIMAL(38, 18), buy_yield__quality_status VARCHAR, "
        "issue_date DATE, issue_date__quality_status VARCHAR, "
        "maturity_date DATE, maturity_date__quality_status VARCHAR)"
    )
    connection.executemany(
        "INSERT INTO silver_bond_instrument VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(
            (
                row.product_id,
                "valid",
                next(value.value for value in row.values if value.field_id == "buy_yield"),
                "valid",
                date(2020, 1, 1),
                "valid",
                date(2027, 7, 11),
                "valid",
            )
            for row in fixture_rows
        ),
    )
    session = _session(connection)  # type: ignore[arg-type]

    actual = QueryExecutor(session).execute(bundle)
    expected = ReferenceExecutor().execute(fixture_rows, bundle)

    assert actual == expected
    session._close()
