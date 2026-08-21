"""Metamorphic invariants for bounded raw queries."""

from decimal import Decimal

import pytest

from finproof.domain.query_plan import FilterClause, FilterOperator, ProductType, ResultGrain
from finproof.storage import RawFieldValue


@pytest.mark.parametrize("threshold", ["1", "2", "3", "4"])
def test_more_restrictive_literal_filter_cannot_increase_raw_candidate_count(
    threshold: str,
) -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ReferenceExecutor,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.query.reference import FixtureRow
    from finproof.registry.loader import RegistryBundle

    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    validator = SemanticValidator(fields)
    rows = tuple(
        FixtureRow(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            product_id=f"B{value}",
            values=(
                RawFieldValue(field_id="product_id", value=f"B{value}", quality_status="valid"),
                RawFieldValue(
                    field_id="buy_yield",
                    value=Decimal(value),
                    quality_status="valid",
                ),
            ),
        )
        for value in range(1, 6)
    )

    counts = []
    for minimum in (Decimal("0"), Decimal(threshold)):
        plan = _plan(
            filters=(
                FilterClause(
                    field="buy_yield",
                    operator=FilterOperator.GT,
                    value=minimum,
                ),
            )
        )
        validated = validator.validate(
            plan,
            resolutions=ResolutionBundle(results=()),
            context=_context(),
        )
        bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
        counts.append(ReferenceExecutor().execute(rows, bundle).candidate_count)

    assert counts[1] <= counts[0]
