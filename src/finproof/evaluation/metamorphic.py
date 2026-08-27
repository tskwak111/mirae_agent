"""Typed checks for the frozen evaluation metamorphic relations."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from finproof.domain.query_plan import ResultGrain


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class MetamorphicKind(StrEnum):
    FILTER_MONOTONICITY = "filter_monotonicity"
    SORT_REVERSAL = "sort_reversal"
    COMPARISON_SIGN = "comparison_sign"
    UNIT_DISPLAY_INVARIANCE = "unit_display_invariance"
    IDENTITY_ALIAS_INVARIANCE = "identity_alias_invariance"
    TIE_PRESERVATION = "tie_preservation"
    FUND_ITEM_NON_DUPLICATION = "fund_item_non_duplication"


class MetamorphicObservation(_FrozenModel):
    total: int = Field(default=0, ge=0)
    product_ids: tuple[str, ...] = ()
    primary_values: tuple[Decimal, ...] = ()
    comparison_value: Decimal | None = None
    ranks: tuple[int, ...] = ()
    result_grain: ResultGrain | None = None


class RelationResult(_FrozenModel):
    kind: MetamorphicKind
    passed: bool
    failure: str | None = None


class MetamorphicRelation(_FrozenModel):
    kind: MetamorphicKind

    def check(
        self,
        base: MetamorphicObservation,
        transformed: MetamorphicObservation,
    ) -> RelationResult:
        passed = self._holds(base, transformed)
        return RelationResult(
            kind=self.kind,
            passed=passed,
            failure=None if passed else f"{self.kind.value} relation failed",
        )

    def _holds(
        self,
        base: MetamorphicObservation,
        transformed: MetamorphicObservation,
    ) -> bool:
        if self.kind is MetamorphicKind.FILTER_MONOTONICITY:
            return transformed.total <= base.total
        if self.kind is MetamorphicKind.SORT_REVERSAL:
            return len(set(base.primary_values)) == len(
                base.primary_values
            ) and transformed.primary_values == tuple(reversed(base.primary_values))
        if self.kind is MetamorphicKind.COMPARISON_SIGN:
            return (
                base.comparison_value is not None
                and transformed.comparison_value == -base.comparison_value
            )
        if self.kind in {
            MetamorphicKind.UNIT_DISPLAY_INVARIANCE,
            MetamorphicKind.IDENTITY_ALIAS_INVARIANCE,
        }:
            return transformed.product_ids == base.product_ids
        if self.kind is MetamorphicKind.TIE_PRESERVATION:
            return _ties_preserved(base, transformed)
        return (
            transformed.result_grain is ResultGrain.FUND_ITEM
            and transformed.total == len(transformed.product_ids)
            and len(set(transformed.product_ids)) == len(transformed.product_ids)
        )


def _ties_preserved(
    base: MetamorphicObservation,
    transformed: MetamorphicObservation,
) -> bool:
    size = len(transformed.product_ids)
    if (
        size == 0
        or len(transformed.primary_values) != size
        or len(transformed.ranks) != size
        or set(transformed.product_ids) != set(base.product_ids)
    ):
        return False
    ranks_by_value: dict[Decimal, set[int]] = {}
    for value, rank in zip(transformed.primary_values, transformed.ranks, strict=True):
        ranks_by_value.setdefault(value, set()).add(rank)
    return all(len(ranks) == 1 for ranks in ranks_by_value.values())
