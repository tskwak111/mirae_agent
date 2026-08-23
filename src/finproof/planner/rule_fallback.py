"""Conservative deterministic parser for reviewed high-confidence patterns."""

import re
from datetime import date
from decimal import Decimal
from time import monotonic

from finproof.domain.query_plan import (
    AggregationFunction,
    AggregationSpec,
    EntityIdentifierType,
    EntityMention,
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
from finproof.planner.service import (
    LocalPlanValidator,
    PlannedQuery,
    PlannerAttemptSummary,
    PlanningRequest,
)

_ALL_REVIEWED_PRODUCTS = (
    ProductType.DOMESTIC_BOND,
    ProductType.DOMESTIC_ETF,
    ProductType.OVERSEAS_ETF,
    ProductType.PUBLIC_FUND,
)
_NATIVE_GRAIN = {
    ProductType.DOMESTIC_BOND: ResultGrain.INSTRUMENT,
    ProductType.DOMESTIC_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.DOMESTIC_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETF: ResultGrain.LISTED_PRODUCT,
    ProductType.OVERSEAS_ETN: ResultGrain.LISTED_PRODUCT,
    ProductType.PUBLIC_FUND: ResultGrain.FUND_ITEM,
}
_METRIC_ALIASES = (
    ("tracking_error", ("추적오차",)),
    ("total_fee", ("총보수", "운용보수")),
    ("return_1d", ("1일 수익률",)),
    ("return_1y", ("1년 수익률",)),
    ("aum", ("AUM", "운용규모", "순자산")),
    ("risk_grade", ("위험등급",)),
    ("credit_rating", ("신용등급",)),
    ("product_name", ("상품명",)),
)
_RANK_FIELD_PATTERN = re.compile(
    r"([A-Za-z가-힣0-9_]+?)(?:이|가|을|를)?\s*"
    r"(?:가장\s*)?(?:높은|낮은|큰|작은|많은|상위|하위)"
)
_PERCENT_FILTER_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(이하|미만|이상|초과)")
_NUMERIC_COMPARISON_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|원|달러|억원|만)?\s*(?:이하|미만|이상|초과)"
)
_EXPLICIT_DATE_PATTERN = re.compile(
    r"(?<!\d)(?:19|20)\d{2}(?:[./-]\d{1,2}(?:[./-]\d{1,2})?|년(?:\s*\d{1,2}월(?:\s*\d{1,2}일)?)?)"
)


class RuleFallbackPlanner:
    """Fail closed outside a small set of explicit Korean query patterns."""

    def __init__(self, *, validator: LocalPlanValidator) -> None:
        self._validator = validator

    async def plan(self, request: PlanningRequest) -> PlannedQuery:
        started = monotonic()
        plan = _parse(request.question, request.as_of_date)
        try:
            validated = self._validator.validate(plan, request)
        except (TypeError, ValueError):
            reason = (
                "entity could not be resolved exactly"
                if plan.entities
                else "fallback semantics could not be validated"
            )
            plan = _terminal(
                Intent.CLARIFY,
                plan.product_types,
                request.as_of_date,
                reason,
                plan.top_k,
                plan.top_k_scope,
            )
            validated = self._validator.validate(plan, request)
        return PlannedQuery(
            plan=plan,
            validated_plan=validated,
            attempts=PlannerAttemptSummary(
                hcx_calls=0,
                repair_calls=0,
                parse_failures=0,
                semantic_failures=0,
                transport_failures=0,
                fallback_used=True,
            ),
            latency_ms=max(0, int((monotonic() - started) * 1000)),
            fallback_path=("rule_fallback",),
            safe_assumptions=(f"snapshot_date={request.as_of_date.isoformat()}",),
            request_deadline_at=request.deadline_at,
        )


def _parse(question: str, as_of_date: date) -> QueryPlan:
    normalized = " ".join(question.split())
    products = _products(normalized)
    top_k = _top_k(normalized)
    top_k_scope = TopKScope.PER_PRODUCT_TYPE if "각각" in normalized else TopKScope.GLOBAL

    if any(term in normalized for term in ("무조건", "추천", "사야")):
        terminal_products = _ALL_REVIEWED_PRODUCTS if "상품" in normalized else products
        terminal_products = terminal_products or _ALL_REVIEWED_PRODUCTS
        return _terminal(
            Intent.UNSUPPORTED,
            terminal_products,
            as_of_date,
            "unsupported advice",
            top_k,
            TopKScope.PER_PRODUCT_TYPE if "상품" in normalized else top_k_scope,
        )
    if any(term in normalized for term in ("미래", "예측")):
        terminal_products = products or _ALL_REVIEWED_PRODUCTS
        return _terminal(
            Intent.UNSUPPORTED,
            terminal_products,
            as_of_date,
            "unsupported forecast",
            top_k,
            TopKScope.PER_PRODUCT_TYPE if not products else top_k_scope,
        )

    metric = _metric(normalized)
    filter_metric = _bound_percentage_filter_metric(normalized)
    if _has_unreviewed_comparison_or_date(normalized, metric, filter_metric):
        return _terminal(
            Intent.CLARIFY,
            products or _ALL_REVIEWED_PRODUCTS,
            as_of_date,
            "comparison or as-of syntax is outside the reviewed fallback grammar",
            top_k,
            top_k_scope if products else TopKScope.PER_PRODUCT_TYPE,
        )
    if "수익률" in normalized and metric is None:
        return _terminal(
            Intent.CLARIFY,
            _ALL_REVIEWED_PRODUCTS,
            as_of_date,
            "product type and return/yield period or definition are unresolved",
            top_k,
            TopKScope.PER_PRODUCT_TYPE,
        )
    if (
        metric == "aum"
        and {
            ProductType.DOMESTIC_ETF,
            ProductType.OVERSEAS_ETF,
        }
        <= set(products)
        and "합쳐서" in normalized
    ):
        return _terminal(
            Intent.CLARIFY,
            products,
            as_of_date,
            "AUM currencies differ and no fixed FX basis was supplied",
            top_k,
            top_k_scope,
        )
    if _has_unknown_rank_field(normalized) or (
        metric is None
        and any(term in normalized for term in ("높은", "낮은", "상위", "하위", "가장"))
    ):
        return _terminal(
            Intent.CLARIFY,
            products or _ALL_REVIEWED_PRODUCTS,
            as_of_date,
            "requested field is not registered",
            top_k,
            top_k_scope if products else TopKScope.PER_PRODUCT_TYPE,
        )
    if not products:
        return _terminal(
            Intent.CLARIFY,
            _ALL_REVIEWED_PRODUCTS,
            as_of_date,
            "product type is unresolved",
            top_k,
            TopKScope.PER_PRODUCT_TYPE,
        )

    filters = _filters(normalized, filter_metric or metric, as_of_date)
    ticker = _ticker(normalized)
    entities = (
        (
            EntityMention(
                text=ticker,
                identifier_type=EntityIdentifierType.TICKER,
            ),
        )
        if ticker is not None
        else ()
    )
    aggregate = "개수" in normalized or "몇 개" in normalized
    direction = _direction(normalized)
    sort = (SortSpec(field=metric, direction=direction),) if metric and direction else ()
    intent = (
        Intent.AGGREGATE
        if aggregate
        else Intent.LOOKUP
        if entities
        else Intent.SCREEN_RANK
        if sort
        else Intent.SCREEN
    )
    return QueryPlan(
        intent=intent,
        product_types=products,
        entities=entities,
        as_of_date=as_of_date,
        result_grain=_grain(products),
        filters=filters,
        metrics=(metric,) if metric is not None else (),
        sort=sort,
        aggregation=(
            AggregationSpec(
                function=AggregationFunction.COUNT,
                field=None,
                group_by=(),
            )
            if aggregate
            else None
        ),
        top_k=top_k,
        top_k_scope=top_k_scope,
        needs_clarification=False,
        clarification_reason="",
    )


def _products(question: str) -> tuple[ProductType, ...]:
    selected: list[ProductType] = []
    pairs = (
        (ProductType.DOMESTIC_BOND, ("국내채권", "국내 채권")),
        (ProductType.DOMESTIC_ETF, ("국내 ETF", "한국 ETF")),
        (ProductType.DOMESTIC_ETN, ("국내 ETN", "한국 ETN")),
        (ProductType.OVERSEAS_ETF, ("해외 ETF", "미국 ETF")),
        (ProductType.OVERSEAS_ETN, ("해외 ETN",)),
        (ProductType.PUBLIC_FUND, ("공모펀드",)),
    )
    for product, aliases in pairs:
        if any(alias in question for alias in aliases):
            selected.append(product)
    if not selected and _ticker(question) is not None:
        selected.append(ProductType.OVERSEAS_ETF)
    if not selected and "ETF" in question:
        selected.extend((ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF))
    if not selected and "펀드" in question:
        selected.append(ProductType.PUBLIC_FUND)
    if not selected and "상품" in question:
        selected.extend(_ALL_REVIEWED_PRODUCTS)
    return tuple(selected)


def _metric(question: str) -> str | None:
    return next(
        (field for field, names in _METRIC_ALIASES if any(name in question for name in names)),
        None,
    )


def _has_unknown_rank_field(question: str) -> bool:
    known = {alias.split()[-1] for _, aliases in _METRIC_ALIASES for alias in aliases}
    return any(match.group(1) not in known for match in _RANK_FIELD_PATTERN.finditer(question))


def _bound_percentage_filter_metric(question: str) -> str | None:
    matches = [
        field
        for field, aliases in _METRIC_ALIASES
        for alias in aliases
        if re.search(
            rf"{re.escape(alias)}(?:이|가|은|는|도|을|를)?\s*{_PERCENT_FILTER_PATTERN.pattern}",
            question,
        )
        is not None
    ]
    return matches[0] if len(matches) == 1 else None


def _has_unreviewed_comparison_or_date(
    question: str,
    metric: str | None,
    filter_metric: str | None,
) -> bool:
    if _EXPLICIT_DATE_PATTERN.search(question) is not None:
        return True
    comparisons = tuple(_NUMERIC_COMPARISON_PATTERN.finditer(question))
    if not comparisons:
        return False
    reviewed = tuple(_PERCENT_FILTER_PATTERN.finditer(question))
    return (
        metric is None
        or filter_metric != metric
        or len(comparisons) != 1
        or len(reviewed) != 1
        or comparisons[0].span() != reviewed[0].span()
    )


def _filters(question: str, metric: str | None, as_of_date: date) -> tuple[FilterClause, ...]:
    filters: list[FilterClause] = []
    if "매수 가능" in question or "매수가능" in question:
        filters.extend(
            (
                FilterClause(
                    field="buyable_quantity", operator=FilterOperator.GT, value=Decimal(0)
                ),
                FilterClause(
                    field="maturity_date",
                    operator=FilterOperator.GTE,
                    value=as_of_date.isoformat(),
                ),
            )
        )
    rating = re.search(r"([A-Z]{1,3}[+-]?)\s*이상", question)
    if rating is not None:
        filters.append(
            FilterClause(
                field="credit_rating",
                operator=FilterOperator.GTE,
                value=rating.group(1),
            )
        )
    if metric == "risk_grade" and "없는" in question:
        filters.append(FilterClause(field="risk_grade", operator=FilterOperator.IS_MISSING))
    numeric = _PERCENT_FILTER_PATTERN.search(question)
    if metric is not None and numeric is not None:
        operator = {
            "이하": FilterOperator.LTE,
            "미만": FilterOperator.LT,
            "이상": FilterOperator.GTE,
            "초과": FilterOperator.GT,
        }[numeric.group(2)]
        filters.append(
            FilterClause(field=metric, operator=operator, value=Decimal(numeric.group(1)))
        )
    return tuple(filters)


def _direction(question: str) -> SortDirection | None:
    if any(term in question for term in ("낮은", "작은", "오름차순", "가나다순")):
        return SortDirection.ASC
    if any(term in question for term in ("높은", "큰", "많은", "상위", "내림차순")):
        return SortDirection.DESC
    return None


def _top_k(question: str) -> int:
    match = re.search(r"(\d+)\s*개", question)
    return min(int(match.group(1)), 50) if match is not None else 5


def _grain(products: tuple[ProductType, ...]) -> ResultGrain:
    return _NATIVE_GRAIN[products[0]] if len(products) == 1 else ResultGrain.PRODUCT


def _ticker(question: str) -> str | None:
    return next(
        (
            match.group(0)
            for match in re.finditer(r"\b[A-Z]{1,5}\b", question)
            if match.group(0) not in {"ETF", "ETN", "AUM", "YTD"}
            and re.match(r"[+-]?\s*(이상|이하)", question[match.end() :]) is None
        ),
        None,
    )


def _terminal(
    intent: Intent,
    products: tuple[ProductType, ...],
    as_of_date: date,
    reason: str,
    top_k: int,
    top_k_scope: TopKScope,
) -> QueryPlan:
    return QueryPlan(
        intent=intent,
        product_types=products,
        entities=(),
        as_of_date=as_of_date,
        result_grain=_grain(products),
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=top_k,
        top_k_scope=top_k_scope,
        needs_clarification=intent is Intent.CLARIFY,
        clarification_reason=reason,
    )
