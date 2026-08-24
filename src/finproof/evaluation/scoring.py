"""Deterministic, denominator-preserving golden-case scoring."""

from collections.abc import Sequence
from math import ceil

from pydantic import BaseModel, ConfigDict, Field

from finproof.domain.query_plan import FilterClause
from finproof.evaluation.models import (
    ExpectedAggregate,
    ExpectedValue,
    GoldenCase,
    ObservedAggregate,
    ObservedCase,
    ObservedValue,
    ProductIdentity,
    aggregate_key,
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class RatioScore(_FrozenModel):
    value: float = Field(ge=0, le=1)
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    failures: tuple[str, ...] = ()


class ProductScore(_FrozenModel):
    set_f1: float = Field(ge=0, le=1)
    set_numerator: int = Field(ge=0)
    set_denominator: int = Field(ge=0)
    order_accuracy: float = Field(ge=0, le=1)
    order_numerator: int = Field(ge=0)
    order_denominator: int = Field(ge=0)


class LatencySummary(_FrozenModel):
    count: int = Field(ge=0)
    total_ms: int = Field(ge=0)
    mean_ms: float
    p95_ms: int

    @classmethod
    def from_milliseconds(cls, samples: Sequence[int]) -> "LatencySummary":
        if not samples or any(type(sample) is not int or sample < 0 for sample in samples):
            raise ValueError("latency samples must be nonempty nonnegative integers")
        ordered = sorted(samples)
        total = sum(ordered)
        return cls(
            count=len(ordered),
            total_ms=total,
            mean_ms=total / len(ordered),
            p95_ms=ordered[ceil(len(ordered) * 0.95) - 1],
        )


class CaseScore(_FrozenModel):
    case_id: str
    plan_fields: RatioScore
    filter_slots: RatioScore
    top_k_scope: RatioScore
    segment_assignment: RatioScore
    compatibility_partitions: RatioScore
    assembled_envelope: RatioScore
    product_set: RatioScore
    product_order: RatioScore
    numeric_values: RatioScore
    aggregate_values: RatioScore
    evidence_coverage: RatioScore
    answer_semantics: RatioScore
    repeat_stability: RatioScore
    latency: LatencySummary | None
    failures: tuple[str, ...]


def _ratio(
    numerator: int,
    denominator: int,
    failures: Sequence[str] = (),
) -> RatioScore:
    return RatioScore(
        value=1.0 if denominator == 0 else numerator / denominator,
        numerator=numerator,
        denominator=denominator,
        failures=tuple(failures),
    )


def score_products(
    expected: Sequence[ProductIdentity], observed: Sequence[ProductIdentity]
) -> ProductScore:
    expected_set = set(expected)
    observed_set = set(observed)
    set_denominator = len(expected_set) + len(observed_set)
    set_numerator = 2 * len(expected_set & observed_set)
    if set_denominator == 0:
        set_numerator = set_denominator = 1
    order_denominator = max(len(expected), len(observed), 1)
    order_numerator = sum(left == right for left, right in zip(expected, observed, strict=False))
    if not expected and not observed:
        order_numerator = 1
    return ProductScore(
        set_f1=set_numerator / set_denominator,
        set_numerator=set_numerator,
        set_denominator=set_denominator,
        order_accuracy=order_numerator / order_denominator,
        order_numerator=order_numerator,
        order_denominator=order_denominator,
    )


def _filter_key(clause: FilterClause) -> str:
    return clause.model_dump_json(exclude_none=False)


def score_filters(expected: Sequence[FilterClause], observed: Sequence[FilterClause]) -> RatioScore:
    expected_set = {_filter_key(clause) for clause in expected}
    observed_set = {_filter_key(clause) for clause in observed}
    denominator = len(expected_set) + len(observed_set)
    if denominator == 0:
        return _ratio(1, 1)
    numerator = 2 * len(expected_set & observed_set)
    failures = () if numerator == denominator else ("filter slots differ",)
    return _ratio(numerator, denominator, failures)


def score_values(
    expected: Sequence[ExpectedValue], observed: Sequence[ObservedValue | ExpectedValue]
) -> RatioScore:
    observed_by_key = {(value.product_id, value.field_id): value for value in observed}
    failures: list[str] = []
    matched = 0
    for expectation in expected:
        key = (expectation.product_id, expectation.field_id)
        actual = observed_by_key.get(key)
        if actual is None or actual.value_type is not expectation.value_type:
            failures.append(f"missing or mistyped value: {key}")
            continue
        if actual.value == expectation.value:
            matched += 1
            continue
        if (
            expectation.value_type.value == "decimal"
            and abs(actual.value - expectation.value) <= expectation.display_tolerance  # type: ignore[operator]
        ):
            matched += 1
            continue
        failures.append(f"value differs: {key}")
    return _ratio(matched, len(expected), failures)


def score_aggregates(
    expected: Sequence[ExpectedAggregate], observed: Sequence[ObservedAggregate]
) -> RatioScore:
    observed_by_key: dict[tuple[object, ...], list[ObservedAggregate]] = {}
    for value in observed:
        observed_by_key.setdefault(aggregate_key(value), []).append(value)
    expected_keys = {aggregate_key(value) for value in expected}
    failures: list[str] = []
    matched = 0
    for expectation in expected:
        actual = observed_by_key.get(aggregate_key(expectation), [])
        if not actual:
            failures.append(f"aggregate missing: {expectation.partition_key}")
        elif len(actual) > 1:
            failures.append(f"duplicate aggregate observation: {expectation.partition_key}")
        elif (
            actual[0].value_type is expectation.value_type and actual[0].value == expectation.value
        ):
            matched += 1
        else:
            failures.append(f"aggregate value differs: {expectation.partition_key}")
    unexpected = [value for value in observed if aggregate_key(value) not in expected_keys]
    failures.extend(f"unexpected aggregate: {value.partition_key}" for value in unexpected)
    duplicate_count = sum(
        max(0, len(values) - 1) for key, values in observed_by_key.items() if key in expected_keys
    )
    return _ratio(
        matched,
        len(expected) + len(unexpected) + duplicate_count,
        failures,
    )


def score_evidence(expected_ids: Sequence[str], observed_ids: Sequence[str]) -> RatioScore:
    observed = set(observed_ids)
    failures = [f"missing evidence: {item}" for item in expected_ids if item not in observed]
    return _ratio(len(expected_ids) - len(failures), len(expected_ids), failures)


def score_repeated_stability(signatures: Sequence[str]) -> RatioScore:
    if len(signatures) < 2:
        return _ratio(0, 0)
    baseline = signatures[0]
    matches = sum(signature == baseline for signature in signatures[1:])
    failures = () if matches == len(signatures) - 1 else ("repeated output changed",)
    return _ratio(matches, len(signatures) - 1, failures)


def _exact_dimension(expected: object, observed: object, label: str) -> RatioScore:
    return _ratio(
        int(expected == observed),
        1,
        () if expected == observed else (f"{label} differs",),
    )


def _not_applicable() -> RatioScore:
    return _ratio(0, 0)


def score_case(case: GoldenCase, observed: ObservedCase) -> CaseScore:
    plan_expectation = case.expected_plan
    plan = observed.plan
    plan_checks: list[tuple[str, object, object]]
    if plan is None:
        expected_fields: list[tuple[str, object]] = [
            ("intent", plan_expectation.intent),
            ("product_types", plan_expectation.product_types),
            ("as_of_date", plan_expectation.as_of_date),
            ("result_grain", plan_expectation.result_grain),
        ]
        expected_fields.extend(
            (label, expected)
            for label, expected in (
                ("metrics", plan_expectation.metrics),
                ("sort", plan_expectation.sort),
                ("needs_clarification", plan_expectation.needs_clarification),
                ("top_k", plan_expectation.top_k),
                ("aggregation", plan_expectation.aggregation),
                ("clarification_reason", plan_expectation.clarification_reason),
            )
            if expected is not None
        )
        plan_checks = [(label, expected, None) for label, expected in expected_fields]
    else:
        plan_checks = [
            ("intent", plan_expectation.intent, plan.intent),
            ("product_types", plan_expectation.product_types, plan.product_types),
            ("as_of_date", plan_expectation.as_of_date, plan.as_of_date),
            ("result_grain", plan_expectation.result_grain, plan.result_grain),
        ]
        for label, expected, actual in (
            ("metrics", plan_expectation.metrics, plan.metrics),
            ("sort", plan_expectation.sort, plan.sort),
            (
                "needs_clarification",
                plan_expectation.needs_clarification,
                plan.needs_clarification,
            ),
            ("top_k", plan_expectation.top_k, plan.top_k),
            ("aggregation", plan_expectation.aggregation, plan.aggregation),
            (
                "clarification_reason",
                plan_expectation.clarification_reason,
                plan.clarification_reason,
            ),
        ):
            if expected is not None:
                plan_checks.append((label, expected, actual))
    if plan is None:
        plan_failures = ["observed plan is missing"]
        plan_fields = _ratio(0, len(plan_checks), plan_failures)
    else:
        plan_failures = [
            f"{label} differs" for label, expected, actual in plan_checks if expected != actual
        ]
        plan_fields = _ratio(len(plan_checks) - len(plan_failures), len(plan_checks), plan_failures)

    filter_slots = (
        _not_applicable()
        if plan_expectation.filters is None
        else score_filters(plan_expectation.filters, () if plan is None else plan.filters)
    )
    top_k_scope = (
        _ratio(0, 1, ("observed plan is missing",))
        if plan is None
        else _exact_dimension(plan_expectation.top_k_scope, plan.top_k_scope, "top_k_scope")
    )

    expected_segments = {
        (
            segment.product_type.value,
            segment.native_result_grain.value,
        )
        for segment in plan_expectation.native_segments
    }
    actual_segments = {
        (
            segment.product_type.value,
            segment.native_result_grain.value,
        )
        for segment in observed.segments
    }
    segment_assignment = (
        _not_applicable()
        if not expected_segments
        else _exact_dimension(expected_segments, actual_segments, "segment assignment")
    )
    expected_partitions = set(case.expected_result.required_compatibility_partitions)
    compatibility_partitions = (
        _not_applicable()
        if not expected_partitions
        else _exact_dimension(
            expected_partitions,
            set(observed.compatibility_partitions),
            "compatibility partitions",
        )
    )
    assembled_envelope = (
        _not_applicable()
        if case.expected_result.assembled_envelope is None
        else _exact_dimension(
            case.expected_result.assembled_envelope,
            observed.assembled_envelope,
            "assembled envelope",
        )
    )

    products = score_products(case.expected_result.products, observed.products)
    product_set = _ratio(
        products.set_numerator,
        products.set_denominator,
        () if products.set_f1 == 1 else ("product set differs",),
    )
    product_order = (
        _not_applicable()
        if not case.expected_result.order_matters
        else _ratio(
            products.order_numerator,
            products.order_denominator,
            () if products.order_accuracy == 1 else ("product order differs",),
        )
    )
    numeric_values = score_values(case.expected_result.values, observed.values)
    aggregate_values = score_aggregates(case.expected_result.aggregates, observed.aggregates)
    evidence_coverage = score_evidence(
        case.expected_result.required_evidence_ids, observed.evidence_ids
    )

    answer_checks: list[tuple[bool, str]] = []
    for concept in case.expected_answer.required_concepts:
        answer_checks.append(
            (concept in observed.answer_text, f"required concept missing: {concept}")
        )
    for concept in case.expected_answer.forbidden_concepts:
        answer_checks.append(
            (concept not in observed.answer_text, f"forbidden concept present: {concept}")
        )
    for expected, actual, label in (
        (
            case.expected_answer.expect_limitation,
            observed.limitation_present,
            "limitation behavior differs",
        ),
        (
            case.expected_answer.expect_clarification,
            observed.clarification_present,
            "clarification behavior differs",
        ),
    ):
        if expected is not None:
            answer_checks.append((expected == actual, label))
    answer_failures = [failure for passed, failure in answer_checks if not passed]
    answer_semantics = _ratio(
        len(answer_checks) - len(answer_failures), len(answer_checks), answer_failures
    )
    repeat_stability = score_repeated_stability(observed.repeat_signatures)
    scores = (
        plan_fields,
        filter_slots,
        top_k_scope,
        segment_assignment,
        compatibility_partitions,
        assembled_envelope,
        product_set,
        product_order,
        numeric_values,
        aggregate_values,
        evidence_coverage,
        answer_semantics,
        repeat_stability,
    )
    return CaseScore(
        case_id=case.case_id,
        plan_fields=plan_fields,
        filter_slots=filter_slots,
        top_k_scope=top_k_scope,
        segment_assignment=segment_assignment,
        compatibility_partitions=compatibility_partitions,
        assembled_envelope=assembled_envelope,
        product_set=product_set,
        product_order=product_order,
        numeric_values=numeric_values,
        aggregate_values=aggregate_values,
        evidence_coverage=evidence_coverage,
        answer_semantics=answer_semantics,
        repeat_stability=repeat_stability,
        latency=None
        if not observed.latency_ms
        else LatencySummary.from_milliseconds(observed.latency_ms),
        failures=tuple(failure for score in scores for failure in score.failures),
    )
