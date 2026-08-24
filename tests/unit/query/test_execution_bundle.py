"""Focused native execution-bundle segmentation tests."""

from decimal import Decimal

import pytest
from tests.unit.query.test_semantic_validator import _context, _plan

from finproof.domain.query_plan import (
    AggregationFunction,
    AggregationSpec,
    EntityMention,
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    ResultGrain,
    SortDirection,
    SortSpec,
    TopKScope,
)
from finproof.entity import ResolutionCandidate, ResolutionMatchKind, ResolutionResult
from finproof.query import (
    ExecutionBundleBuilder,
    FieldRegistry,
    ResolutionBundle,
    SemanticValidator,
)
from finproof.registry.loader import RegistryBundle


def test_exact_entity_resolutions_become_closed_product_id_filters() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    mentions = (EntityMention(text="KR0000000001"), EntityMention(text="KR0000000002"))
    candidates = tuple(
        ResolutionCandidate(
            product_id=mention.text,
            product_type=ProductType.DOMESTIC_BOND,
            name=f"채권 {index}",
            match_kind=ResolutionMatchKind.EXACT_PRODUCT_ID,
            score=10_000,
        )
        for index, mention in enumerate(mentions, 1)
    )
    plan = _plan(entities=mentions).model_copy(update={"intent": Intent.COMPARE})
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(
            results=tuple(
                ResolutionResult(selected=candidate, candidates=(candidate,))
                for candidate in candidates
            )
        ),
        context=_context(),
    )

    segment = (
        ExecutionBundleBuilder(fields)
        .build(
            validated,
            context=_context(),
        )
        .segments[0]
    )

    assert segment.filters == (
        FilterClause(
            field="product_id",
            operator=FilterOperator.IN,
            value=("KR0000000001", "KR0000000002"),
        ),
    )


def test_heterogeneous_product_envelope_builds_ordered_native_segments() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.PUBLIC_FUND, ProductType.DOMESTIC_BOND),
        result_grain=ResultGrain.PRODUCT,
    )
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())

    assert bundle.validated_plan is validated
    assert bundle.response_grain is ResultGrain.PRODUCT
    assert tuple(segment.product_type for segment in bundle.segments) == (
        ProductType.DOMESTIC_BOND,
        ProductType.PUBLIC_FUND,
    )
    assert tuple(segment.native_result_grain for segment in bundle.segments) == (
        ResultGrain.INSTRUMENT,
        ResultGrain.FUND_ITEM,
    )


def test_clause_distribution_targets_only_registered_product_types_and_zero_targets_fail() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    validator = SemanticValidator(fields)
    plan = _plan(
        filters=(
            FilterClause(
                field="buy_yield",
                operator=FilterOperator.GT,
                value=Decimal("1"),
            ),
            FilterClause(field="region", operator=FilterOperator.EQ, value="Korea"),
        ),
        product_types=(ProductType.PUBLIC_FUND, ProductType.DOMESTIC_BOND),
        result_grain=ResultGrain.PRODUCT,
    )
    validated = validator.validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    segments = ExecutionBundleBuilder(fields).build(validated, context=_context()).segments
    assert tuple(clause.field for clause in segments[0].filters) == ("buy_yield",)
    assert tuple(clause.field for clause in segments[1].filters) == ("region",)

    with pytest.raises(ValueError, match="target"):
        validator.validate(
            plan.model_copy(
                update={
                    "filters": (
                        FilterClause(
                            field="tracking_error",
                            operator=FilterOperator.GT,
                            value=Decimal("0"),
                        ),
                    )
                }
            ),
            resolutions=ResolutionBundle(results=()),
            context=_context(),
        )


def test_global_scope_requires_one_compatible_partition_for_rank_and_aggregate() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    validator = SemanticValidator(fields)
    compatible = _plan(
        product_types=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("total_fee",),
            "sort": (SortSpec(field="total_fee", direction=SortDirection.ASC),),
        }
    )
    validated = validator.validate(
        compatible,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    assert len(bundle.comparison_partitions) == 1
    assert bundle.comparison_partitions[0].product_types == (
        ProductType.DOMESTIC_ETF,
        ProductType.OVERSEAS_ETF,
    )

    incompatible = _plan(
        product_types=(ProductType.DOMESTIC_BOND, ProductType.PUBLIC_FUND),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("buy_yield", "return_1m"),
            "sort": (
                SortSpec(field="buy_yield", direction=SortDirection.DESC),
                SortSpec(field="return_1m", direction=SortDirection.DESC),
            ),
        }
    )
    invalid = validator.validate(
        incompatible,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    with pytest.raises(ValueError, match="global"):
        ExecutionBundleBuilder(fields).build(invalid, context=_context())


def test_global_targetless_count_has_one_native_grain_partition() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.COUNT,
                field=None,
                group_by=(),
            ),
        }
    )
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )

    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())

    assert len(bundle.comparison_partitions) == 1
    assert bundle.comparison_partitions[0].product_types == (ProductType.DOMESTIC_BOND,)


def test_per_product_type_scope_records_each_required_compatibility_split() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan(
        product_types=(ProductType.DOMESTIC_BOND, ProductType.PUBLIC_FUND),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("buy_yield", "return_1m"),
            "sort": (
                SortSpec(field="buy_yield", direction=SortDirection.DESC),
                SortSpec(field="return_1m", direction=SortDirection.DESC),
            ),
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )

    partitions = (
        ExecutionBundleBuilder(fields).build(validated, context=_context()).comparison_partitions
    )

    assert tuple(partition.product_types for partition in partitions) == (
        (ProductType.DOMESTIC_BOND,),
        (ProductType.PUBLIC_FUND,),
    )
