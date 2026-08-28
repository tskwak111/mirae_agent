"""Synthetic executor coverage for fail-closed holding predicates."""

from tests.integration.query.test_executor import _session


def test_unavailable_etn_relation_returns_zero_instead_of_unfiltered_rows() -> None:
    import duckdb
    from tests.unit.query.test_semantic_validator import (
        _context,
        _holding_plan,
        _holding_resolution,
    )

    from finproof.domain.execution import (
        ExecutionBundle,
        ExecutionSegment,
        HoldingConstituentFilter,
    )
    from finproof.domain.query_plan import ProductType, ResultGrain, TopKScope
    from finproof.query import FieldRegistry, QueryExecutor, ResolutionBundle, SemanticValidator
    from finproof.registry.loader import RegistryBundle

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    validated = SemanticValidator(fields).validate(
        _holding_plan((ProductType.DOMESTIC_ETN,)),
        resolutions=ResolutionBundle(results=(), holding_constituent=_holding_resolution()),
        context=_context(),
    )
    relation = HoldingConstituentFilter(
        constituent_identifier="KR7005930003",
        constituent_identifier_type="ISIN",
    )
    segment = ExecutionSegment(
        product_type=ProductType.DOMESTIC_ETN,
        native_result_grain=ResultGrain.LISTED_PRODUCT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        holding_constituent_filter=relation,
    )
    bundle = ExecutionBundle(
        validated_plan=validated,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        segments=(segment,),
        comparison_partitions=(),
        response_grain=ResultGrain.LISTED_PRODUCT,
    )
    connection = duckdb.connect(":memory:")
    connection.execute(
        "CREATE TABLE silver_domestic_listed_product ("
        "product_id VARCHAR, product_id__quality_status VARCHAR, product_type VARCHAR, "
        "sale_flag BOOLEAN, sale_flag__quality_status VARCHAR, "
        "suspension_flag BOOLEAN, suspension_flag__quality_status VARCHAR, "
        "listing_date DATE, listing_date__quality_status VARCHAR, "
        "listing_end_date DATE, listing_end_date__quality_status VARCHAR)"
    )
    connection.execute(
        "INSERT INTO silver_domestic_listed_product VALUES "
        "('ETN-1','valid','ETN',true,'valid',false,'valid',"
        "DATE '2020-01-01','valid',NULL,'missing')"
    )
    connection.execute(
        "CREATE TABLE silver_product_holding ("
        "owner_product_type VARCHAR, owner_product_id VARCHAR, "
        "constituent_identifier VARCHAR, constituent_identifier_type VARCHAR)"
    )
    session = _session(connection)  # type: ignore[arg-type]
    try:
        result = QueryExecutor(session).execute(bundle)
    finally:
        session._close()

    assert result.candidate_count == 0
    assert result.segments[0].rows == ()
