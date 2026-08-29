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
    MetricTarget,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.entity import HoldingResolutionResult
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


def test_semantic_validator_rejects_unregistered_metric_target_pairs() -> None:
    plan = _plan(
        product_types=(ProductType.DOMESTIC_BOND, ProductType.PUBLIC_FUND),
        result_grain=ResultGrain.PRODUCT,
    ).model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "metrics": ("buy_yield", "return_1y"),
            "metric_targets": (
                MetricTarget(
                    product_type=ProductType.DOMESTIC_BOND,
                    metrics=("return_1y",),
                ),
                MetricTarget(
                    product_type=ProductType.PUBLIC_FUND,
                    metrics=("buy_yield",),
                ),
            ),
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )

    with pytest.raises(ValueError, match="metric target"):
        _validator().validate(
            plan,
            resolutions=ResolutionBundle(results=()),
            context=_context(),
        )


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


def _holding_plan(
    product_types: tuple[ProductType, ...] = (ProductType.DOMESTIC_ETF,),
    *,
    filters: tuple[FilterClause, ...] | None = None,
) -> QueryPlan:
    return QueryPlan(
        intent=Intent.SCREEN,
        product_types=product_types,
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=(
            ResultGrain.LISTED_PRODUCT if len(product_types) == 1 else ResultGrain.PRODUCT
        ),
        filters=filters
        if filters is not None
        else (
            FilterClause(
                field="holding_constituent",
                operator=FilterOperator.EQ,
                value="삼성전자",
            ),
        ),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )


def _holding_resolution(*, selected: bool = True) -> HoldingResolutionResult:
    from finproof.entity import HoldingResolutionCandidate

    candidate = HoldingResolutionCandidate(
        constituent_identifier="KR7005930003",
        constituent_identifier_type="ISIN",
        display_name="삼성전자",
    )
    return HoldingResolutionResult(
        selected=candidate if selected else None,
        candidates=(candidate,),
    )


def test_holding_semantics_require_one_resolved_filter_and_reject_bonds_whole_plan() -> None:
    resolution = _holding_resolution()
    allowed = (
        ProductType.DOMESTIC_ETF,
        ProductType.DOMESTIC_ETN,
        ProductType.OVERSEAS_ETF,
        ProductType.OVERSEAS_ETN,
        ProductType.PUBLIC_FUND,
    )
    for product_type in allowed:
        plan = _holding_plan((product_type,))
        if product_type is ProductType.PUBLIC_FUND:
            plan = plan.model_copy(update={"result_grain": ResultGrain.FUND_ITEM})
        assert (
            _validator()
            .validate(
                plan,
                resolutions=ResolutionBundle(results=(), holding_constituent=resolution),
                context=_context(),
            )
            .plan
            is plan
        )

    duplicate = _holding_plan().filters * 2
    for plan in (
        _holding_plan(filters=duplicate),
        _holding_plan((ProductType.DOMESTIC_BOND, ProductType.DOMESTIC_ETF)),
    ):
        with pytest.raises(ValueError, match=r"holding|bond"):
            _validator().validate(
                plan,
                resolutions=ResolutionBundle(results=(), holding_constituent=resolution),
                context=_context(),
            )


def test_holding_semantics_reject_missing_unresolved_and_malformed_resolution() -> None:
    from finproof.entity import HoldingResolutionResult

    plan = _holding_plan()
    invalid = (
        None,
        HoldingResolutionResult(selected=None, candidates=()),
        _holding_resolution(selected=False),
    )
    for resolution in invalid:
        with pytest.raises(ValueError, match="holding resolution"):
            _validator().validate(
                plan,
                resolutions=ResolutionBundle(results=(), holding_constituent=resolution),
                context=_context(),
            )


def test_unrelated_semantics_keep_default_none_holding_resolution() -> None:
    plan = _holding_plan(filters=())
    resolutions = ResolutionBundle(results=())

    validated = _validator().validate(plan, resolutions=resolutions, context=_context())

    assert validated.resolutions is resolutions
    assert resolutions.holding_constituent is None
