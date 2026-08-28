"""Focused deterministic policy-pipeline ordering."""

from datetime import date
from decimal import Decimal

from finproof.domain.query_plan import ProductType
from finproof.storage import RawProductRow


def test_bond_prepolicy_projection_includes_maturity_for_validated_state() -> None:
    from finproof.domain.execution import ExecutionSegment
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import FieldRegistry, QueryAst
    from finproof.registry.loader import RegistryBundle

    ast = QueryAst.from_segment(
        ExecutionSegment(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            filters=(),
            metrics=(),
            sort=(),
            aggregation=None,
            top_k=5,
        ),
        fields=FieldRegistry.from_bundle(RegistryBundle.from_package()),
    )

    assert tuple(projection.field_id for projection in ast.projections) == (
        "product_id",
        "issue_date",
        "maturity_date",
    )


def test_bond_prepolicy_projection_excludes_invalid_buyable_quantity() -> None:
    from finproof.domain.execution import ExecutionSegment
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import FieldRegistry, QueryAst
    from finproof.registry.loader import RegistryBundle

    ast = QueryAst.from_segment(
        ExecutionSegment(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            filters=(),
            metrics=(),
            sort=(),
            aggregation=None,
            top_k=5,
        ),
        fields=FieldRegistry.from_bundle(RegistryBundle.from_package()),
    )

    assert "buyable_quantity" not in tuple(projection.field_id for projection in ast.projections)


def test_domestic_listed_prepolicy_projection_includes_state_inputs() -> None:
    from finproof.domain.execution import ExecutionSegment
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import FieldRegistry, QueryAst
    from finproof.registry.loader import RegistryBundle

    ast = QueryAst.from_segment(
        ExecutionSegment(
            product_type=ProductType.DOMESTIC_ETF,
            native_result_grain=ResultGrain.LISTED_PRODUCT,
            filters=(),
            metrics=("tracking_error",),
            sort=(),
            aggregation=None,
            top_k=5,
        ),
        fields=FieldRegistry.from_bundle(RegistryBundle.from_package()),
    )

    assert tuple(projection.field_id for projection in ast.projections) == (
        "product_id",
        "tracking_error",
        "saleable",
        "suspension_flag",
        "listing_date",
        "listing_end_date",
    )


def test_domestic_listed_prepolicy_projection_includes_listing_period_inputs() -> None:
    from finproof.domain.execution import ExecutionSegment
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import FieldRegistry, QueryAst
    from finproof.registry.loader import RegistryBundle

    ast = QueryAst.from_segment(
        ExecutionSegment(
            product_type=ProductType.DOMESTIC_ETN,
            native_result_grain=ResultGrain.LISTED_PRODUCT,
            filters=(),
            metrics=(),
            sort=(),
            aggregation=None,
            top_k=5,
        ),
        fields=FieldRegistry.from_bundle(RegistryBundle.from_package()),
    )

    projected = tuple(projection.field_id for projection in ast.projections)
    assert "listing_date" in projected
    assert "listing_end_date" in projected


def test_aum_prepolicy_projection_includes_dynamic_currency_input() -> None:
    from finproof.domain.execution import ExecutionSegment
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.query import FieldRegistry, QueryAst
    from finproof.registry.loader import RegistryBundle

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    for product_type, grain in (
        (ProductType.DOMESTIC_ETF, ResultGrain.LISTED_PRODUCT),
        (ProductType.OVERSEAS_ETF, ResultGrain.LISTED_PRODUCT),
        (ProductType.PUBLIC_FUND, ResultGrain.FUND_ITEM),
    ):
        ast = QueryAst.from_segment(
            ExecutionSegment(
                product_type=product_type,
                native_result_grain=grain,
                filters=(),
                metrics=("aum",),
                sort=(),
                aggregation=None,
                top_k=5,
            ),
            fields=fields,
        )

        assert "currency" in tuple(projection.field_id for projection in ast.projections)


def test_pipeline_applies_state_and_metric_eligibility_without_invalid_quantity() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawSegmentResult,
    )

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(filters=()).model_copy(update={"metrics": ()})
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _bond(product_id, quantity, maturity)
        for product_id, quantity, maturity in (
            ("filtered", "0", date(2030, 1, 1)),
            ("matured", "10", date(2026, 7, 10)),
            ("included", "10", date(2030, 1, 1)),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=rows,
                candidate_count=3,
                max_batch_rows=3,
            ),
        ),
        candidate_count=3,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(row.raw.product_id for row in result.included_rows) == (
        "filtered",
        "included",
    )
    assert result.excluded_filter_count == 0
    assert result.excluded_state_count == 1


def test_pipeline_uses_the_frozen_rating_scale_for_aa_minus_or_higher() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import FilterClause, FilterOperator, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        filters=(
            FilterClause(
                field="credit_rating",
                operator=FilterOperator.GTE,
                value="AA-",
            ),
        )
    ).model_copy(update={"metrics": ()})
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _bond(product_id, "10", date(2030, 1, 1)).model_copy(
            update={
                "values": (
                    *_bond(product_id, "10", date(2030, 1, 1)).values,
                    RawFieldValue(
                        field_id="credit_rating",
                        value=rating,
                        quality_status="valid",
                    ),
                )
            }
        )
        for product_id, rating in (("strong", "AA"), ("weak", "BBB"))
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(row.raw.product_id for row in result.included_rows) == ("strong",)
    assert result.excluded_filter_count == 1


def test_pipeline_ranks_credit_ratings_by_registry_order_and_preserves_labels() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ResultGrain, SortDirection, SortSpec
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("credit_rating",),
            "sort": (SortSpec(field="credit_rating", direction=SortDirection.DESC),),
            "top_k": 3,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _bond(product_id, "10", date(2030, 1, 1)).model_copy(
            update={
                "values": (
                    *_bond(product_id, "10", date(2030, 1, 1)).values,
                    RawFieldValue(
                        field_id="credit_rating",
                        value=rating,
                        quality_status="valid",
                    ),
                )
            }
        )
        for product_id, rating in (
            ("AA-plus", "AA+"),
            ("AAA-two", "AAA"),
            ("not-rated", "NR"),
            ("AAA-one", "AAA"),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=rows,
                candidate_count=4,
                max_batch_rows=4,
            ),
        ),
        candidate_count=4,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(
        (rank.value.product_id, rank.value.value, rank.rank, rank.tie_count)
        for rank in result.ranks
    ) == (
        ("AAA-one", "AAA", 1, 2),
        ("AAA-two", "AAA", 1, 2),
        ("AA-plus", "AA+", 3, 1),
    )
    assert result.excluded_metric_count == 1


def test_pipeline_compares_iso_date_filter_values_as_dates() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import FilterClause, FilterOperator, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        filters=(
            FilterClause(
                field="maturity_date",
                operator=FilterOperator.GTE,
                value="2026-07-11",
            ),
        )
    ).model_copy(update={"metrics": ()})
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=(
                    _bond("expired", "10", date(2026, 7, 10)),
                    _bond("active", "10", date(2030, 1, 1)),
                ),
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(row.raw.product_id for row in result.included_rows) == ("active",)
    assert result.excluded_filter_count == 1


def test_pipeline_ranks_integer_derived_metric_values() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ResultGrain, SortDirection, SortSpec
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("remaining_days_at_as_of",),
            "sort": (
                SortSpec(
                    field="remaining_days_at_as_of",
                    direction=SortDirection.ASC,
                ),
            ),
            "top_k": 2,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _bond(product_id, "10", maturity).model_copy(
            update={
                "values": (
                    *_bond(product_id, "10", maturity).values,
                    RawFieldValue(
                        field_id="remaining_days_at_as_of",
                        value=remaining_days,
                        quality_status="valid",
                    ),
                )
            }
        )
        for product_id, maturity, remaining_days in (
            ("near", date(2026, 7, 21), 10),
            ("far", date(2026, 8, 10), 30),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple((rank.value.product_id, rank.rank, rank.value.value) for rank in result.ranks) == (
        ("near", 1, Decimal(10)),
        ("far", 2, Decimal(30)),
    )


def test_pipeline_preserves_integer_metric_values_for_decimal_aggregation() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import AggregationFunction, AggregationSpec, Intent, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.AVG,
                field="remaining_days_at_as_of",
                group_by=(),
            ),
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _bond(product_id, "10", maturity).model_copy(
            update={
                "values": (
                    *_bond(product_id, "10", maturity).values,
                    RawFieldValue(
                        field_id="remaining_days_at_as_of",
                        value=remaining_days,
                        quality_status="valid",
                    ),
                )
            }
        )
        for product_id, maturity, remaining_days in (
            ("near", date(2026, 7, 21), 10),
            ("far", date(2026, 8, 10), 30),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    aggregate = PolicyEngine().apply(raw, bundle=bundle).aggregates[0]

    assert aggregate.value == Decimal(20)
    assert aggregate.included_count == 2


def test_pipeline_partitions_before_aggregate_or_rank_tie() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("aum",),
            "sort": (SortSpec(field="aum", direction=SortDirection.DESC),),
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    domestic = _listed("K1", ProductType.DOMESTIC_ETF, "KRW", "100")
    overseas = _listed("U1", ProductType.OVERSEAS_ETF, "USD", "200")
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=(domestic,),
                candidate_count=1,
                max_batch_rows=1,
            ),
            RawSegmentResult(
                product_type=ProductType.OVERSEAS_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=(overseas,),
                candidate_count=1,
                max_batch_rows=1,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(partition.currency for partition in result.partitions) == ("KRW", "USD")
    assert tuple(
        item.product_id for partition in result.partitions for item in partition.values
    ) == (
        "K1",
        "U1",
    )


def test_lookup_allows_multiple_metric_partitions_for_the_same_selected_product() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawProductRow, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.LOOKUP,
            "metrics": ("total_fee", "aum"),
        }
    )
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    row = RawProductRow(
        product_type=ProductType.DOMESTIC_ETF,
        native_result_grain=ResultGrain.LISTED_PRODUCT,
        product_id="K1",
        values=(
            RawFieldValue(field_id="product_id", value="K1", quality_status="valid"),
            RawFieldValue(field_id="total_fee", value=Decimal("0.1"), quality_status="valid"),
            RawFieldValue(field_id="aum", value=Decimal("100"), quality_status="valid"),
            RawFieldValue(field_id="currency", value="KRW", quality_status="valid"),
            RawFieldValue(field_id="saleable", value=True, quality_status="valid"),
            RawFieldValue(field_id="suspension_flag", value=False, quality_status="valid"),
            RawFieldValue(
                field_id="listing_date",
                value=date(2020, 1, 1),
                quality_status="valid",
            ),
            RawFieldValue(
                field_id="listing_end_date",
                value=None,
                quality_status="sentinel_max_date",
            ),
        ),
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=(row,),
                candidate_count=1,
                max_batch_rows=1,
            ),
        ),
        candidate_count=1,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert len(result.partitions) == 2
    assert {
        value.product_id for partition in result.partitions for value in partition.selected_values
    } == {"K1"}


def test_display_lookup_preserves_mixed_nonnumeric_metric_rows_without_a_partition() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={
            "intent": Intent.LOOKUP,
            "metrics": ("credit_rating", "maturity_date"),
            "top_k": 1,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    bond = _bond("B1", "10", date(2031, 7, 21))
    row = bond.model_copy(
        update={
            "values": (
                *bond.values,
                RawFieldValue(field_id="credit_rating", value="AAA", quality_status="valid"),
            )
        }
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=(row,),
                candidate_count=1,
                max_batch_rows=1,
            ),
        ),
        candidate_count=1,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert result.partitions == ()
    assert tuple(item.raw.product_id for item in result.selected_rows) == ("B1",)


def test_display_compare_preserves_ordinal_rating_rows_without_a_partition() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={"intent": Intent.COMPARE, "metrics": ("credit_rating",), "top_k": 2}
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        bond.model_copy(
            update={
                "values": (
                    *bond.values,
                    RawFieldValue(field_id="credit_rating", value="AAA", quality_status="valid"),
                )
            }
        )
        for bond in (
            _bond("B1", "10", date(2030, 1, 1)),
            _bond("B2", "10", date(2031, 1, 1)),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert result.partitions == ()
    assert tuple(item.raw.product_id for item in result.selected_rows) == ("B1", "B2")


def test_display_compare_keeps_all_missing_numeric_rows_selected_for_null_evidence() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.PUBLIC_FUND,),
        result_grain=ResultGrain.FUND_ITEM,
    ).model_copy(update={"intent": Intent.COMPARE, "metrics": ("return_3m",), "top_k": 2})
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        RawProductRow(
            product_type=ProductType.PUBLIC_FUND,
            native_result_grain=ResultGrain.FUND_ITEM,
            product_id=product_id,
            values=(
                RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                RawFieldValue(field_id="return_3m", value=None, quality_status="missing_blank"),
            ),
        )
        for product_id in ("F1", "F2")
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.PUBLIC_FUND,
                native_result_grain=ResultGrain.FUND_ITEM,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert result.partitions == ()
    assert tuple(item.raw.product_id for item in result.selected_rows) == ("F1", "F2")


def test_screen_numeric_filters_do_not_create_extra_metric_partition_identities() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        FilterClause,
        FilterOperator,
        ProductType,
        ResultGrain,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.OVERSEAS_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
        filters=(
            FilterClause(field="aum", operator=FilterOperator.GTE, value=Decimal("0")),
            FilterClause(field="total_fee", operator=FilterOperator.LTE, value=Decimal("1")),
        ),
    ).model_copy(update={"metrics": (), "top_k": 2})
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _listed(product_id, ProductType.OVERSEAS_ETF, "USD", aum).model_copy(
            update={
                "values": (
                    *_listed(product_id, ProductType.OVERSEAS_ETF, "USD", aum).values,
                    RawFieldValue(field_id="total_fee", value=Decimal(fee), quality_status="valid"),
                )
            }
        )
        for product_id, aum, fee in (
            ("A", "100", "0.4"),
            ("B", "200", "0.3"),
            ("C", "1", "0.2"),
            ("D", "2", "0.1"),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.OVERSEAS_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=rows,
                candidate_count=4,
                max_batch_rows=4,
            ),
        ),
        candidate_count=4,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)
    selected = {
        *(row.raw.product_id for row in result.selected_rows),
        *(
            value.product_id
            for partition in result.partitions
            for value in partition.selected_values
        ),
    }

    assert result.partitions == ()
    assert selected == {"A", "B"}


def test_pipeline_retains_post_filter_pre_state_rows_without_bypassing_eligibility() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={"intent": Intent.COMPARE, "metrics": ("maturity_date",), "top_k": 2}
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=(
                    _bond("MATURED", "10", date(2025, 1, 1)),
                    _bond("ELIGIBLE", "10", date(2030, 1, 1)),
                ),
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(row.raw.product_id for row in result.source_rows) == ("MATURED", "ELIGIBLE")
    assert tuple(row.raw.product_id for row in result.included_rows) == ("ELIGIBLE",)
    assert result.excluded_state_count == 1


def test_pipeline_applies_top_k_only_after_each_final_partition() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("aum",),
            "sort": (SortSpec(field="aum", direction=SortDirection.DESC),),
            "top_k": 1,
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    domestic = tuple(
        _listed(product_id, ProductType.DOMESTIC_ETF, "KRW", aum)
        for product_id, aum in (("K1", "100"), ("K2", "200"))
    )
    overseas = tuple(
        _listed(product_id, ProductType.OVERSEAS_ETF, "USD", aum)
        for product_id, aum in (("U1", "100"), ("U2", "300"))
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=domestic,
                candidate_count=2,
                max_batch_rows=2,
            ),
            RawSegmentResult(
                product_type=ProductType.OVERSEAS_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=overseas,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=4,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(len(partition.values) for partition in result.partitions) == (2, 2)
    assert tuple(
        tuple(value.product_id for value in partition.selected_values)
        for partition in result.partitions
    ) == (("K2",), ("U2",))


def test_per_product_type_top_k_keeps_same_currency_types_independent() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF, ProductType.DOMESTIC_ETN),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("tracking_error",),
            "sort": (SortSpec(field="tracking_error", direction=SortDirection.ASC),),
            "top_k": 1,
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())

    def rows(product_type: ProductType, prefix: str):  # type: ignore[no-untyped-def]
        return tuple(
            _listed(f"{prefix}{value}", product_type, "KRW", "100").model_copy(
                update={
                    "values": (
                        *_listed(f"{prefix}{value}", product_type, "KRW", "100").values,
                        RawFieldValue(
                            field_id="tracking_error",
                            value=Decimal(value),
                            quality_status="valid",
                        ),
                    )
                }
            )
            for value in ("1", "2")
        )

    raw = RawExecutionResult(
        segments=tuple(
            RawSegmentResult(
                product_type=product_type,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=rows(product_type, prefix),
                candidate_count=2,
                max_batch_rows=2,
            )
            for product_type, prefix in (
                (ProductType.DOMESTIC_ETF, "E"),
                (ProductType.DOMESTIC_ETN, "N"),
            )
        ),
        candidate_count=4,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(
        tuple(value.product_id for value in partition.selected_values)
        for partition in result.partitions
    ) == (("E1",), ("N1",))


def test_pipeline_applies_field_sort_top_k_per_product_type_without_metric_coercion() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.OVERSEAS_ETF, ProductType.PUBLIC_FUND),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("product_name",),
            "sort": (SortSpec(field="product_name", direction=SortDirection.ASC),),
            "top_k": 1,
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    raw = RawExecutionResult(
        segments=tuple(
            RawSegmentResult(
                product_type=product_type,
                native_result_grain=grain,
                rows=tuple(
                    RawProductRow(
                        product_type=product_type,
                        native_result_grain=grain,
                        product_id=f"{prefix}{name}",
                        values=(
                            RawFieldValue(
                                field_id="product_id",
                                value=f"{prefix}{name}",
                                quality_status="valid",
                            ),
                            RawFieldValue(
                                field_id="product_name",
                                value=name,
                                quality_status="valid",
                            ),
                        ),
                    )
                    for name in ("나", "가")
                ),
                candidate_count=2,
                max_batch_rows=2,
            )
            for product_type, grain, prefix in (
                (ProductType.OVERSEAS_ETF, ResultGrain.LISTED_PRODUCT, "E"),
                (ProductType.PUBLIC_FUND, ResultGrain.FUND_ITEM, "F"),
            )
        ),
        candidate_count=4,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(row.raw.product_id for row in result.selected_rows) == ("E가", "F가")
    assert result.metric_policy.recorded_values == ()


def test_global_scope_rejects_more_than_one_final_partition() -> None:
    import pytest
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(update={"intent": Intent.SCREEN_RANK, "metrics": ("aum",)})
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = (
        _listed("K1", ProductType.DOMESTIC_ETF, "KRW", "100"),
        _listed("U1", ProductType.DOMESTIC_ETF, "USD", "200"),
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    with pytest.raises(ValueError, match="global"):
        PolicyEngine().apply(raw, bundle=bundle)


def test_display_infers_return_period_after_another_requested_metric_is_missing() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETN,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(update={"metrics": ("total_fee", "return_1y")})
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    row = _listed("KRG500000614", ProductType.DOMESTIC_ETN, "KRW", "1")
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETN,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=(
                    row.model_copy(
                        update={
                            "values": (
                                *row.values,
                                RawFieldValue(
                                    field_id="total_fee",
                                    value=None,
                                    quality_status="missing_blank",
                                ),
                                RawFieldValue(
                                    field_id="return_1y",
                                    value=Decimal("-76.03"),
                                    quality_status="valid",
                                ),
                            )
                        }
                    ),
                ),
                candidate_count=1,
                max_batch_rows=1,
            ),
        ),
        candidate_count=1,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple(partition.period for partition in result.partitions) == ("1y",)
    assert tuple(value.metric_id for value in result.partitions[0].values) == (
        "domestic_etf.return_1y",
    )


def test_aggregate_functions_return_typed_value_counts_policy_and_evidence_requirements() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        ResultGrain,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.AVG,
                field="buy_yield",
                group_by=(),
            ),
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = (
        _bond("B1", "10", date(2030, 1, 1), yield_value="2"),
        _bond("B2", "10", date(2030, 1, 1), yield_value="4"),
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    aggregate = PolicyEngine().apply(raw, bundle=bundle).aggregates[0]

    assert aggregate.value == Decimal("3")
    assert aggregate.product_type is ProductType.DOMESTIC_BOND
    assert aggregate.native_result_grain is ResultGrain.INSTRUMENT
    assert aggregate.partition_key == (
        "bond_buy_yield:None:yield_to_maturity_like_source_field:"
        "not_equal_to_historical_period_return"
    )
    assert (aggregate.included_count, aggregate.excluded_count) == (2, 0)
    assert aggregate.policy_id == "bond.buy_yield:avg"
    assert aggregate.evidence_requirements == ("value", "quality", "count")


def test_rank_output_retains_tie_counts_policy_and_evidence_requirements() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain, SortDirection, SortSpec
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("tracking_error",),
            "sort": (SortSpec(field="tracking_error", direction=SortDirection.ASC),),
            "top_k": 1,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _listed(product_id, ProductType.DOMESTIC_ETF, "KRW", "100").model_copy(
            update={
                "values": (
                    *(_listed(product_id, ProductType.DOMESTIC_ETF, "KRW", "100").values),
                    RawFieldValue(
                        field_id="tracking_error",
                        value=Decimal("0"),
                        quality_status="valid",
                    ),
                )
            }
        )
        for product_id in ("E2", "E1", "E3")
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=rows,
                candidate_count=3,
                max_batch_rows=3,
            ),
        ),
        candidate_count=3,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple((rank.rank, rank.tie_count) for rank in result.ranks) == (
        (1, 3),
        (1, 3),
        (1, 3),
    )
    assert all(rank.native_result_grain is ResultGrain.LISTED_PRODUCT for rank in result.ranks)
    assert all(
        rank.partition_key == "tracking_error:KRW:source_convention:same_metric_only"
        for rank in result.ranks
    )
    assert all(rank.policy_id == "domestic_etf.tracking_error:rank" for rank in result.ranks)
    assert result.ranks[0].evidence_requirements == ("value", "quality", "tie")


def test_rank_metric_policy_drops_missing_and_preserves_recorded_zero_tie() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("tracking_error",),
            "sort": (SortSpec(field="tracking_error", direction=SortDirection.ASC),),
            "top_k": 1,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        _listed(product_id, ProductType.DOMESTIC_ETF, "KRW", "100").model_copy(
            update={
                "values": (
                    *_listed(product_id, ProductType.DOMESTIC_ETF, "KRW", "100").values,
                    RawFieldValue(
                        field_id="tracking_error",
                        value=value,
                        quality_status=quality,
                    ),
                )
            }
        )
        for product_id, value, quality in (
            ("E2", Decimal("0"), "recorded_zero"),
            ("E1", Decimal("0"), "recorded_zero"),
            ("missing", None, "missing_blank"),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=rows,
                candidate_count=3,
                max_batch_rows=3,
            ),
        ),
        candidate_count=3,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert tuple((rank.rank, rank.tie_count) for rank in result.ranks) == (
        (1, 2),
        (1, 2),
    )
    assert result.excluded_metric_count == 1


def test_pipeline_retains_recorded_and_comparison_valid_metric_views() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.OVERSEAS_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("total_fee",),
            "sort": (SortSpec(field="total_fee", direction=SortDirection.ASC),),
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.OVERSEAS_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=(
                    RawProductRow(
                        product_type=ProductType.OVERSEAS_ETF,
                        native_result_grain=ResultGrain.LISTED_PRODUCT,
                        product_id="O1",
                        values=(
                            RawFieldValue(
                                field_id="product_id",
                                value="O1",
                                quality_status="valid",
                            ),
                            RawFieldValue(
                                field_id="total_fee",
                                value=Decimal("0"),
                                quality_status="recorded_zero_unverified",
                            ),
                        ),
                    ),
                ),
                candidate_count=1,
                max_batch_rows=1,
            ),
        ),
        candidate_count=1,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)

    assert len(result.metric_policy.recorded_values) == 1
    assert result.metric_policy.comparison_valid_values == ()
    assert result.dual_lens_labels == ("recorded", "comparison_valid")


def test_aggregate_metric_policy_excludes_out_of_domain_value_with_count() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        ResultGrain,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.PUBLIC_FUND,),
        result_grain=ResultGrain.FUND_ITEM,
    ).model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.AVG,
                field="return_3y",
                group_by=(),
            ),
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        RawProductRow(
            product_type=ProductType.PUBLIC_FUND,
            native_result_grain=ResultGrain.FUND_ITEM,
            product_id=product_id,
            values=(
                RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                RawFieldValue(field_id="return_3y", value=value, quality_status=quality),
            ),
        )
        for product_id, value, quality in (
            ("valid", Decimal("10"), "valid"),
            ("invalid", Decimal("-120"), "out_of_domain"),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.PUBLIC_FUND,
                native_result_grain=ResultGrain.FUND_ITEM,
                rows=rows,
                candidate_count=2,
                max_batch_rows=2,
            ),
        ),
        candidate_count=2,
    )

    result = PolicyEngine().apply(raw, bundle=bundle)
    aggregate = result.aggregates[0]

    assert aggregate.value == Decimal("10")
    assert (aggregate.included_count, aggregate.excluded_count) == (1, 1)
    assert "metric values excluded from comparison" in result.warnings


def test_aggregate_group_by_preserves_typed_keys_values_and_group_counts() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.PUBLIC_FUND,),
        result_grain=ResultGrain.FUND_ITEM,
    ).model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.SUM,
                field="aum",
                group_by=("currency",),
            ),
            "sort": (SortSpec(field="aum", direction=SortDirection.DESC),),
            "top_k": 1,
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    rows = tuple(
        RawProductRow(
            product_type=ProductType.PUBLIC_FUND,
            native_result_grain=ResultGrain.FUND_ITEM,
            product_id=product_id,
            values=(
                RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                RawFieldValue(field_id="currency", value=currency, quality_status="valid"),
                RawFieldValue(field_id="aum", value=value, quality_status=quality),
            ),
        )
        for product_id, currency, value, quality in (
            ("K1", "KRW", Decimal("10"), "valid"),
            ("K2", "KRW", Decimal("20"), "valid"),
            ("K3", "KRW", None, "missing_blank"),
            ("U1", "USD", Decimal("5"), "valid"),
        )
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.PUBLIC_FUND,
                native_result_grain=ResultGrain.FUND_ITEM,
                rows=rows,
                candidate_count=4,
                max_batch_rows=4,
            ),
        ),
        candidate_count=4,
    )

    aggregates = PolicyEngine().apply(raw, bundle=bundle).aggregates

    assert tuple(
        (
            aggregate.group_values[0].value,
            aggregate.value,
            aggregate.included_count,
            aggregate.excluded_count,
        )
        for aggregate in aggregates
    ) == (
        ("KRW", Decimal("30"), 2, 1),
        ("USD", Decimal("5"), 1, 0),
    )
    assert len({aggregate.partition_key for aggregate in aggregates}) == 2


def test_display_partitions_do_not_expand_the_primary_top_k_identity_set() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.LOOKUP,
            "metrics": ("total_fee", "aum"),
            "sort": (),
            "top_k": 2,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())

    def row(
        product_id: str,
        *,
        fee: Decimal | None,
        aum: Decimal | None,
    ) -> RawProductRow:
        base = _listed(product_id, ProductType.DOMESTIC_ETF, "KRW", "100")
        return base.model_copy(
            update={
                "values": (
                    *(item for item in base.values if item.field_id != "aum"),
                    RawFieldValue(
                        field_id="aum",
                        value=aum,
                        quality_status="valid" if aum is not None else "missing_blank",
                    ),
                    RawFieldValue(
                        field_id="total_fee",
                        value=fee,
                        quality_status="valid" if fee is not None else "missing_blank",
                    ),
                )
            }
        )

    rows = (
        row("A", fee=Decimal("0.1"), aum=None),
        row("B", fee=Decimal("0.2"), aum=None),
        row("C", fee=None, aum=Decimal("100")),
        row("D", fee=None, aum=Decimal("200")),
    )
    result = PolicyEngine().apply(
        RawExecutionResult(
            segments=(
                RawSegmentResult(
                    product_type=ProductType.DOMESTIC_ETF,
                    native_result_grain=ResultGrain.LISTED_PRODUCT,
                    rows=rows,
                    candidate_count=4,
                    max_batch_rows=4,
                ),
            ),
            candidate_count=4,
        ),
        bundle=bundle,
    )

    primary = {row.raw.product_id for row in result.selected_rows}
    partition_selected = {
        value.product_id for partition in result.partitions for value in partition.selected_values
    }
    assert primary == {"A", "B"}
    assert partition_selected == primary


def test_ungrouped_cross_product_aggregate_exclusions_are_segment_scoped() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        ResultGrain,
        TopKScope,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_ETF, ProductType.PUBLIC_FUND),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.AVG,
                field="return_1m",
                group_by=(),
            ),
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())

    def etf(product_id: str, *, saleable: bool) -> RawProductRow:
        base = _listed(product_id, ProductType.DOMESTIC_ETF, "KRW", "100")
        return base.model_copy(
            update={
                "values": (
                    *(item for item in base.values if item.field_id != "saleable"),
                    RawFieldValue(field_id="saleable", value=saleable, quality_status="valid"),
                    RawFieldValue(
                        field_id="return_1m",
                        value=Decimal("1"),
                        quality_status="valid",
                    ),
                )
            }
        )

    funds = tuple(
        RawProductRow(
            product_type=ProductType.PUBLIC_FUND,
            native_result_grain=ResultGrain.FUND_ITEM,
            product_id=product_id,
            values=(
                RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                RawFieldValue(
                    field_id="return_1m",
                    value=value,
                    quality_status="valid" if value is not None else "missing_blank",
                ),
            ),
        )
        for product_id, value in (("F-VALID", Decimal("2")), ("F-MISSING", None))
    )
    result = PolicyEngine().apply(
        RawExecutionResult(
            segments=(
                RawSegmentResult(
                    product_type=ProductType.DOMESTIC_ETF,
                    native_result_grain=ResultGrain.LISTED_PRODUCT,
                    rows=(etf("E-VALID", saleable=True), etf("E-EXCLUDED", saleable=False)),
                    candidate_count=2,
                    max_batch_rows=2,
                ),
                RawSegmentResult(
                    product_type=ProductType.PUBLIC_FUND,
                    native_result_grain=ResultGrain.FUND_ITEM,
                    rows=funds,
                    candidate_count=2,
                    max_batch_rows=2,
                ),
            ),
            candidate_count=4,
        ),
        bundle=bundle,
    )

    by_type = {aggregate.product_type: aggregate for aggregate in result.aggregates}
    assert by_type[ProductType.DOMESTIC_ETF].excluded_count == 1
    assert by_type[ProductType.PUBLIC_FUND].excluded_count == 1


def _bond(
    product_id: str,
    quantity: str,
    maturity: date,
    *,
    yield_value: str = "3",
) -> RawProductRow:
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.storage import RawFieldValue, RawProductRow

    return RawProductRow(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        product_id=product_id,
        values=(
            RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
            RawFieldValue(
                field_id="buyable_quantity",
                value=Decimal(quantity),
                quality_status="valid",
            ),
            RawFieldValue(field_id="maturity_date", value=maturity, quality_status="valid"),
            RawFieldValue(
                field_id="buy_yield",
                value=Decimal(yield_value),
                quality_status="valid",
            ),
        ),
    )


def _listed(
    product_id: str,
    product_type: ProductType,
    currency: str,
    aum: str,
) -> RawProductRow:
    from finproof.domain.query_plan import ResultGrain
    from finproof.storage import RawFieldValue, RawProductRow

    return RawProductRow(
        product_type=product_type,
        native_result_grain=ResultGrain.LISTED_PRODUCT,
        product_id=product_id,
        values=(
            RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
            RawFieldValue(field_id="aum", value=Decimal(aum), quality_status="valid"),
            RawFieldValue(field_id="currency", value=currency, quality_status="valid"),
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
