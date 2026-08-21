"""Independent in-memory raw query reference."""

from finproof.domain.execution import ExecutionBundle
from finproof.domain.query_plan import FilterClause, FilterOperator
from finproof.storage.repositories.products import (
    RawExecutionResult,
    RawProductRow,
    RawSegmentResult,
)


class FixtureRow(RawProductRow):
    pass


class ReferenceExecutor:
    def execute(
        self,
        rows: tuple[FixtureRow, ...],
        bundle: ExecutionBundle,
    ) -> RawExecutionResult:
        if type(rows) is not tuple or type(bundle) is not ExecutionBundle:
            raise TypeError("reference executor inputs differ")
        segments: list[RawSegmentResult] = []
        for segment in bundle.segments:
            selected = tuple(
                RawProductRow.model_validate(row.model_dump(), strict=True)
                for row in rows
                if type(row) is FixtureRow
                and row.product_type is segment.product_type
                and all(_matches(row, clause) for clause in segment.filters)
            )
            segments.append(
                RawSegmentResult(
                    product_type=segment.product_type,
                    native_result_grain=segment.native_result_grain,
                    rows=selected,
                    candidate_count=len(selected),
                    max_batch_rows=len(selected),
                )
            )
        return RawExecutionResult(
            segments=tuple(segments),
            candidate_count=sum(segment.candidate_count for segment in segments),
        )


def _matches(row: FixtureRow, clause: FilterClause) -> bool:
    values = {item.field_id: item.value for item in row.values}
    value = values.get(clause.field)
    target = clause.value
    if clause.operator is FilterOperator.IS_MISSING:
        return value is None
    if clause.operator is FilterOperator.IS_NOT_MISSING:
        return value is not None
    if value is None:
        return False
    if clause.operator is FilterOperator.EQ:
        return value == target
    if clause.operator is FilterOperator.NE:
        return value != target
    if clause.operator is FilterOperator.IN:
        return isinstance(target, tuple) and value in target
    if clause.operator is FilterOperator.NOT_IN:
        return isinstance(target, tuple) and value not in target
    if clause.operator is FilterOperator.BETWEEN:
        return isinstance(target, tuple) and target[0] <= value <= target[1]  # type: ignore[operator]
    if clause.operator is FilterOperator.CONTAINS:
        return type(value) is str and type(target) is str and target in value
    if clause.operator is FilterOperator.STARTS_WITH:
        return type(value) is str and type(target) is str and value.startswith(target)
    if clause.operator is FilterOperator.GT:
        return value > target  # type: ignore[operator]
    if clause.operator is FilterOperator.GTE:
        return value >= target  # type: ignore[operator]
    if clause.operator is FilterOperator.LT:
        return value < target  # type: ignore[operator]
    if clause.operator is FilterOperator.LTE:
        return value <= target  # type: ignore[operator]
    raise ValueError("reference filter operator differs")
