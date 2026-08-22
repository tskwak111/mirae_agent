"""Focused bounded raw query execution tests."""

from datetime import date
from decimal import Decimal

import pytest


def test_repository_and_executor_skeleton_exposes_exact_interfaces() -> None:
    from finproof.query import QueryExecutor, ReferenceExecutor
    from finproof.storage import ProductRepository, RawExecutionResult, RawSegmentResult

    assert all(
        isinstance(value, type)
        for value in (
            ProductRepository,
            QueryExecutor,
            ReferenceExecutor,
            RawExecutionResult,
            RawSegmentResult,
        )
    )


def test_repository_accepts_live_runtime_session_only() -> None:
    from finproof.storage import ProductRepository

    session = _session(Connection())
    repository = ProductRepository(session)
    assert not {"connection", "cursor", "path", "sql"} & {
        name for name in dir(repository) if not name.startswith("_")
    }

    with pytest.raises(TypeError, match="session"):
        ProductRepository(object())  # type: ignore[arg-type]

    session._close()
    with pytest.raises(RuntimeError, match="closed"):
        ProductRepository(session)


def test_lookup_and_screen_return_typed_decimal_date_and_quality_values() -> None:
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import CompiledQuery
    from finproof.storage import ProductRepository

    connection = ScriptedConnection(
        rows=(
            (
                "B1",
                "valid",
                Decimal("3.25"),
                "valid",
                date(2030, 1, 2),
                "valid",
            ),
        )
    )
    session = _session(connection)
    result = ProductRepository(session).execute(
        CompiledQuery(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            table_name="silver_bond_instrument",
            projected_fields=("product_id", "buy_yield", "maturity_date"),
            sql="SELECT closed_projection",
            parameters=(),
        )
    )

    assert result.candidate_count == 1
    assert result.rows[0].product_id == "B1"
    assert tuple(
        (item.field_id, item.value, item.quality_status) for item in result.rows[0].values
    ) == (
        ("product_id", "B1", "valid"),
        ("buy_yield", Decimal("3.25"), "valid"),
        ("maturity_date", date(2030, 1, 2), "valid"),
    )
    session._close()


def test_raw_executor_does_not_apply_final_top_k_rank_tie_or_aggregate() -> None:
    from finproof.storage import RawExecutionResult, RawProductRow, RawSegmentResult

    assert set(RawProductRow.model_fields) == {
        "product_type",
        "native_result_grain",
        "product_id",
        "values",
    }
    assert set(RawSegmentResult.model_fields) == {
        "product_type",
        "native_result_grain",
        "rows",
        "candidate_count",
        "max_batch_rows",
    }
    assert set(RawExecutionResult.model_fields) == {"segments", "candidate_count"}
    assert not {
        "aggregate",
        "partition",
        "rank",
        "tie",
        "top_k",
    } & set(RawSegmentResult.model_fields)


def test_candidate_counts_are_explicit_and_not_inferred_from_sql_text() -> None:
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import CompiledQuery
    from finproof.storage import ProductRepository

    session = _session(ScriptedConnection(rows=(("B1", "valid"), ("B2", "valid"))))
    result = ProductRepository(session).execute(
        CompiledQuery(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            table_name="silver_bond_instrument",
            projected_fields=("product_id",),
            sql="SELECT product_id, product_id__quality_status /* COUNT(*) = 999 */",
            parameters=(),
        )
    )
    assert result.candidate_count == 2
    assert result.max_batch_rows == 2
    session._close()


def test_no_result_returns_empty_typed_segment_without_error() -> None:
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import CompiledQuery
    from finproof.storage import ProductRepository, RawSegmentResult

    session = _session(ScriptedConnection(rows=()))
    result = ProductRepository(session).execute(
        CompiledQuery(
            product_type=ProductType.PUBLIC_FUND,
            native_result_grain=ResultGrain.FUND_ITEM,
            table_name="silver_fund_item",
            projected_fields=("product_id",),
            sql="SELECT empty_projection",
            parameters=(),
        )
    )
    assert type(result) is RawSegmentResult
    assert result.rows == ()
    assert result.candidate_count == result.max_batch_rows == 0
    session._close()


def test_native_segments_execute_once_in_frozen_product_type_order() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        QueryExecutor,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    validated = SemanticValidator(fields).validate(
        _plan(
            product_types=(ProductType.PUBLIC_FUND, ProductType.DOMESTIC_BOND),
            result_grain=ResultGrain.PRODUCT,
        ).model_copy(update={"metrics": ()}),
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    connection = QueueConnection(
        batches=(
            (
                (
                    "B1",
                    "valid",
                    Decimal("10"),
                    "valid",
                    date(2027, 7, 11),
                    "valid",
                ),
            ),
            (("F1", "valid"),),
        )
    )
    session = _session(connection)

    raw = QueryExecutor(session).execute(bundle)

    assert tuple(segment.product_type for segment in raw.segments) == (
        ProductType.DOMESTIC_BOND,
        ProductType.PUBLIC_FUND,
    )
    assert raw.candidate_count == 2
    assert len(connection.sql) == 2
    assert "silver_bond_instrument" in connection.sql[0]
    assert "silver_fund_item" in connection.sql[1]
    session._close()


def test_same_grain_multi_type_rows_preserve_product_type_and_native_identity() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        QueryExecutor,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETN, ProductType.DOMESTIC_ETF),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(update={"metrics": ()})
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    session = _session(
        QueueConnection(
            batches=(
                (
                    (
                        "ETF1",
                        "valid",
                        True,
                        "valid",
                        False,
                        "valid",
                        date(2020, 1, 1),
                        "valid",
                        None,
                        "missing",
                    ),
                ),
                (
                    (
                        "ETN1",
                        "valid",
                        True,
                        "valid",
                        False,
                        "valid",
                        date(2020, 1, 1),
                        "valid",
                        None,
                        "missing",
                    ),
                ),
            )
        )
    )

    raw = QueryExecutor(session).execute(bundle)

    assert tuple(
        (segment.product_type, segment.native_result_grain, segment.rows[0].product_id)
        for segment in raw.segments
    ) == (
        (ProductType.DOMESTIC_ETF, ResultGrain.LISTED_PRODUCT, "ETF1"),
        (ProductType.DOMESTIC_ETN, ResultGrain.LISTED_PRODUCT, "ETN1"),
    )
    session._close()


class Connection:
    def close(self) -> None:
        pass


class Cursor:
    def __init__(self, rows: tuple[tuple[object, ...], ...]) -> None:
        self._rows = rows

    def fetchmany(self, _size: int) -> list[tuple[object, ...]]:
        rows, self._rows = self._rows, ()
        return list(rows)


class ScriptedConnection(Connection):
    def __init__(self, *, rows: tuple[tuple[object, ...], ...]) -> None:
        self._rows = rows

    def execute(self, _sql: str, _parameters: object) -> Cursor:
        return Cursor(self._rows)


class QueueConnection(Connection):
    def __init__(self, *, batches: tuple[tuple[tuple[object, ...], ...], ...]) -> None:
        self._batches = list(batches)
        self.sql: list[str] = []

    def execute(self, sql: str, _parameters: object) -> Cursor:
        self.sql.append(sql)
        return Cursor(self._batches.pop(0))


def _session(connection: Connection):  # type: ignore[no-untyped-def]
    from tests.helpers.query_runtime import verified_artifacts

    from finproof.core.settings import ExecutionMode
    from finproof.core.versions import VersionBundle
    from finproof.registry.loader import RegistryBundle
    from finproof.runtime.session import RuntimeArtifactSession

    verified = verified_artifacts()
    registries = RegistryBundle.from_package()
    return RuntimeArtifactSession._issue(
        connection=connection,
        verified=verified,
        registries=registries,
        versions=VersionBundle.from_runtime(
            verified=verified,
            registries=registries,
            execution_mode=ExecutionMode.EVALUATION,
        ),
    )
