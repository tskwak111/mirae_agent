"""Official registry semantic-validation integration."""

from datetime import date

import pytest

from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import (
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    SortDirection,
    SortSpec,
    TopKScope,
)
from finproof.query import (
    ExecutionBundleBuilder,
    FieldRegistry,
    ResolutionBundle,
    SemanticValidator,
    ValidationContext,
)
from finproof.registry.loader import RegistryBundle


def test_official_registry_validates_supported_plan_and_fail_closed_eligibility_plan() -> None:
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    validator = SemanticValidator(fields)
    context = ValidationContext(
        as_of_date=date(2026, 7, 11),
        execution_mode=ExecutionMode.EVALUATION,
    )
    supported = QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=("total_fee",),
        sort=(SortSpec(field="total_fee", direction=SortDirection.ASC),),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )
    validated = validator.validate(
        supported,
        resolutions=ResolutionBundle(results=()),
        context=context,
    )
    assert len(ExecutionBundleBuilder(fields).build(validated, context=context).segments) == 2

    unsupported = supported.model_copy(
        update={
            "product_types": (ProductType.PUBLIC_FUND,),
            "result_grain": ResultGrain.FUND_ITEM,
            "filters": (
                FilterClause(
                    field="mirae_saleable",
                    operator=FilterOperator.EQ,
                    value=True,
                ),
            ),
            "metrics": (),
            "sort": (),
        }
    )
    with pytest.raises(ValueError, match="eligibility"):
        validator.validate(
            unsupported,
            resolutions=ResolutionBundle(results=()),
            context=context,
        )
