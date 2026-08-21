"""Focused fail-closed semantic validation tests."""

from datetime import date
from decimal import Decimal

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import (
    AggregationFunction,
    AggregationSpec,
    EntityMention,
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.query import FieldRegistry, ResolutionBundle, SemanticValidator, ValidationContext
from finproof.registry.loader import RegistryBundle


def _plan(
    *,
    filters: tuple[FilterClause, ...] = (),
    entities: tuple[EntityMention, ...] = (),
    product_types: tuple[ProductType, ...] = (ProductType.DOMESTIC_BOND,),
    result_grain: ResultGrain = ResultGrain.INSTRUMENT,
) -> QueryPlan:
    return QueryPlan(
        intent=Intent.SCREEN,
        product_types=product_types,
        entities=entities,
        as_of_date=date(2026, 7, 11),
        result_grain=result_grain,
        filters=filters,
        metrics=("buy_yield",),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )


def _validator() -> SemanticValidator:
    return SemanticValidator(FieldRegistry.from_bundle(RegistryBundle.from_package()))


def _context() -> ValidationContext:
    return ValidationContext(
        as_of_date=date(2026, 7, 11),
        execution_mode=ExecutionMode.EVALUATION,
    )


def test_semantic_validator_rejects_unknown_field_operator_and_value_type_family() -> None:
    invalid = (
        FilterClause(field="unknown", operator=FilterOperator.EQ, value="x"),
        FilterClause(field="buy_yield", operator=FilterOperator.CONTAINS, value="1"),
        FilterClause(field="buy_yield", operator=FilterOperator.GT, value="high"),
    )
    for clause in invalid:
        with pytest.raises(ValueError, match="filter"):
            _validator().validate(
                _plan(filters=(clause,)),
                resolutions=ResolutionBundle(results=()),
                context=_context(),
            )

    validated = _validator().validate(
        _plan(
            filters=(
                FilterClause(
                    field="buy_yield",
                    operator=FilterOperator.GT,
                    value=Decimal("1.5"),
                ),
            )
        ),
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    assert validated.plan.filters[0].value == Decimal("1.5")


def test_resolutions_are_retained_by_identity_and_candidate_or_ambiguous_status_fails_closed() -> (
    None
):
    from finproof.entity import ResolutionCandidate, ResolutionMatchKind, ResolutionResult

    mention = EntityMention(text="B1")
    selected = ResolutionCandidate(
        product_id="B1",
        product_type=ProductType.DOMESTIC_BOND,
        name="Bond One",
        match_kind=ResolutionMatchKind.EXACT_PRODUCT_ID,
        score=10_000,
    )
    result = ResolutionResult(selected=selected, candidates=(selected,))
    resolutions = ResolutionBundle(results=(result,))
    validated = _validator().validate(
        _plan(entities=(mention,)),
        resolutions=resolutions,
        context=_context(),
    )
    assert validated.resolutions is resolutions
    assert resolutions.results[0] is result

    unresolved = (
        ResolutionResult(
            selected=None,
            candidates=(
                selected.model_copy(
                    update={"match_kind": ResolutionMatchKind.FUZZY_CANDIDATE, "score": 8000}
                ),
            ),
        ),
        ResolutionResult(
            selected=None,
            candidates=(
                selected.model_copy(update={"match_kind": ResolutionMatchKind.EXACT_NAME}),
                selected.model_copy(update={"product_id": "B2"}),
            ),
        ),
    )
    for resolution in unresolved:
        with pytest.raises(ValueError, match="resolution"):
            _validator().validate(
                _plan(entities=(mention,)),
                resolutions=ResolutionBundle(results=(resolution,)),
                context=_context(),
            )


def test_product_type_and_native_grain_contract_is_exact() -> None:
    valid = (
        (ProductType.DOMESTIC_BOND, ResultGrain.INSTRUMENT),
        (ProductType.DOMESTIC_ETF, ResultGrain.LISTED_PRODUCT),
        (ProductType.DOMESTIC_ETN, ResultGrain.LISTED_PRODUCT),
        (ProductType.OVERSEAS_ETF, ResultGrain.LISTED_PRODUCT),
        (ProductType.OVERSEAS_ETN, ResultGrain.LISTED_PRODUCT),
        (ProductType.PUBLIC_FUND, ResultGrain.FUND_ITEM),
    )
    for product_type, grain in valid:
        plan = _plan(product_types=(product_type,), result_grain=grain)
        if product_type is not ProductType.DOMESTIC_BOND:
            plan = plan.model_copy(update={"metrics": ()})
        assert (
            _validator()
            .validate(
                plan,
                resolutions=ResolutionBundle(results=()),
                context=_context(),
            )
            .plan
            is plan
        )

        with pytest.raises(ValueError, match="grain"):
            _validator().validate(
                plan.model_copy(
                    update={
                        "result_grain": (
                            ResultGrain.FUND_ITEM
                            if grain is not ResultGrain.FUND_ITEM
                            else ResultGrain.INSTRUMENT
                        )
                    }
                ),
                resolutions=ResolutionBundle(results=()),
                context=_context(),
            )


def test_overseas_and_public_fund_validated_eligibility_requests_fail_closed() -> None:
    eligibility = FilterClause(field="saleable", operator=FilterOperator.EQ, value=True)
    for product_type, grain in (
        (ProductType.OVERSEAS_ETF, ResultGrain.LISTED_PRODUCT),
        (ProductType.OVERSEAS_ETN, ResultGrain.LISTED_PRODUCT),
        (ProductType.PUBLIC_FUND, ResultGrain.FUND_ITEM),
    ):
        with pytest.raises(ValueError, match="eligibility"):
            _validator().validate(
                _plan(
                    filters=(eligibility,),
                    product_types=(product_type,),
                    result_grain=grain,
                ).model_copy(update={"metrics": ()}),
                resolutions=ResolutionBundle(results=()),
                context=_context(),
            )

    domestic = _plan(
        filters=(eligibility,),
        product_types=(ProductType.DOMESTIC_ETF,),
        result_grain=ResultGrain.LISTED_PRODUCT,
    ).model_copy(update={"metrics": ()})
    assert (
        _validator()
        .validate(
            domestic,
            resolutions=ResolutionBundle(results=()),
            context=_context(),
        )
        .plan
        is domestic
    )


def test_aggregation_target_group_and_operation_are_registry_authorized() -> None:
    count = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "aggregation": AggregationSpec(
                function=AggregationFunction.COUNT,
                field=None,
                group_by=("currency",),
            ),
        }
    )
    assert (
        _validator()
        .validate(
            count,
            resolutions=ResolutionBundle(results=()),
            context=_context(),
        )
        .plan
        is count
    )

    invalid = (
        AggregationSpec(
            function=AggregationFunction.SUM,
            field="buy_yield",
            group_by=(),
        ),
        AggregationSpec(
            function=AggregationFunction.AVG,
            field="product_name",
            group_by=(),
        ),
        AggregationSpec(
            function=AggregationFunction.AVG,
            field="buy_yield",
            group_by=("asset_type",),
        ),
    )
    for aggregation in invalid:
        plan = _plan().model_copy(update={"intent": Intent.AGGREGATE, "aggregation": aggregation})
        with pytest.raises(ValueError, match="aggregation"):
            _validator().validate(
                plan,
                resolutions=ResolutionBundle(results=()),
                context=_context(),
            )
