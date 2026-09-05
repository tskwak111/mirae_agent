"""HCX-007 Structured Outputs planner adapter."""

from time import monotonic

from finproof.core.logging import log_hcx_output_invalid
from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
from finproof.planner.models import HcxMessage, HcxRequest
from finproof.planner.prompts import build_system_prompt, build_user_prompt
from finproof.planner.provider_schema import (
    ProviderPlanError,
    build_hcx_query_plan_schema,
    parse_provider_plan,
)
from finproof.planner.service import (
    HcxGenerator,
    LocalPlanValidator,
    PlannedQuery,
    PlannerAttemptSummary,
    PlannerOutputError,
    PlannerSemanticError,
    PlanningRequest,
    semantic_reason_code,
)
from finproof.query.fields import FieldRegistry
from finproof.registry.loader import RegistryBundle
from finproof.service.limits import RequestDeadline


class StructuredOutputPlanner:
    """One-call structured adapter; retry policy remains in PlannerService."""

    def __init__(
        self,
        *,
        generator: HcxGenerator,
        validator: LocalPlanValidator,
        registries: RegistryBundle,
        model_name: str,
    ) -> None:
        self._generator = generator
        self._validator = validator
        self._registries = registries
        self._model_name = model_name

    async def plan(self, request: PlanningRequest, *, deadline: RequestDeadline) -> PlannedQuery:
        return await self._attempt(request, invalid_content=None, deadline=deadline)

    async def repair(
        self,
        request: PlanningRequest,
        invalid_content: str,
        *,
        validation_stage: str | None = None,
        canonical_path: str | None = None,
        canonical_keyword: str | None = None,
        deadline: RequestDeadline,
    ) -> PlannedQuery:
        return await self._attempt(
            request,
            invalid_content=invalid_content,
            validation_stage=validation_stage,
            canonical_path=canonical_path,
            canonical_keyword=canonical_keyword,
            deadline=deadline,
        )

    async def _attempt(
        self,
        request: PlanningRequest,
        *,
        invalid_content: str | None,
        validation_stage: str | None = None,
        canonical_path: str | None = None,
        canonical_keyword: str | None = None,
        deadline: RequestDeadline,
    ) -> PlannedQuery:
        started = monotonic()
        prompt = build_system_prompt(self._registries, snapshot_date=request.as_of_date)
        messages = [
            HcxMessage(role="system", content=prompt.text),
            HcxMessage(role="user", content=build_user_prompt(request.question)),
        ]
        if invalid_content is not None:
            messages.extend(
                (
                    HcxMessage(role="assistant", content=invalid_content),
                    HcxMessage(
                        role="user",
                        content=(
                            "Correct only the JSON/schema error. Local validation metadata: "
                            f"validation_stage={validation_stage or 'unknown'}; "
                            f"canonical_path={canonical_path or 'unknown'}; "
                            f"canonical_keyword={canonical_keyword or 'unknown'}. "
                            "One product_type must use "
                            "its native result_grain: domestic_bond=instrument; "
                            "domestic_etf|domestic_etn|overseas_etf|overseas_etn="
                            "listed_product; public_fund=fund_item. Use result_grain=product "
                            "only for heterogeneous native grains. 낮은/높은 with top-k "
                            "define sort direction, not a filter. Without an explicit literal "
                            "value, set, range, or missing-state condition, emit filters=[]; "
                            "never invent a threshold. Unless intent=aggregate, emit exactly "
                            'aggregation={"function":"none","field":"","group_by":[]} '
                            "with exactly these three keys. For explicitly different metrics, "
                            "use intent=screen_rank, top_k_scope=per_product_type, and one "
                            "target per product_type in product_types order; the target metric "
                            "union must exactly equal metrics and preserve metrics order; "
                            "otherwise metric_targets=[]. Return JSON only."
                        ),
                    ),
                )
            )
        provider_request = HcxRequest.structured(
            model_name=self._model_name,
            messages=tuple(messages),
            schema=build_hcx_query_plan_schema(),
            max_completion_tokens=2_048,
            temperature=0.0,
            seed=17,
        )
        provider_request_id = (
            f"{request.request_id}-structured-repair"
            if invalid_content is not None
            else f"{request.request_id}-structured"
        )
        response = await self._generator.generate(
            provider_request,
            request_id=provider_request_id,
            deadline=deadline,
        )
        try:
            plan = parse_provider_plan(
                response.message_content,
                local_terminal_intent=(
                    Intent.UNSUPPORTED
                    if _requires_unavailable_relationship(" ".join(request.question.split()))
                    else None
                ),
            )
        except ProviderPlanError as error:
            log_hcx_output_invalid(
                provider_request_id=provider_request_id,
                validation_stage=error.stage.value,
                canonical_substage=error.canonical_substage,
                canonical_path=error.canonical_path,
                canonical_keyword=error.canonical_keyword,
            )
            raise PlannerOutputError(
                response.message_content,
                validation_stage=error.stage.value,
                canonical_substage=error.canonical_substage,
                canonical_path=error.canonical_path,
                canonical_keyword=error.canonical_keyword,
                filter_shape_category=error.filter_shape_category,
            ) from None
        plan = _canonical_terminal_plan(plan, request)
        normalized_question = " ".join(request.question.split())
        if (
            len(plan.product_types) > 1
            and plan.top_k_scope is TopKScope.GLOBAL
            and "개씩" in normalized_question
            and any(term in normalized_question for term in ("유형별", "각각"))
        ):
            plan = plan.model_copy(update={"top_k_scope": TopKScope.PER_PRODUCT_TYPE})
        if (
            len(plan.product_types) > 1
            and "현재 구매 가능한" in normalized_question
            and any(clause.field in {"saleable", "mirae_saleable"} for clause in plan.filters)
        ):
            plan = plan.model_copy(
                update={
                    "filters": tuple(
                        clause
                        for clause in plan.filters
                        if clause.field not in {"saleable", "mirae_saleable"}
                    )
                }
            )
        try:
            validated = self._validator.validate(plan, request)
        except (TypeError, ValueError) as error:
            reason_code = semantic_reason_code(error)
            detail, registry_field_id = _semantic_detail(reason_code, plan, self._registries)
            log_hcx_output_invalid(
                provider_request_id=provider_request_id,
                validation_stage="semantic",
                semantic_reason_code=reason_code,
                semantic_detail=detail,
                registry_field_id=registry_field_id,
            )
            if reason_code == "entity_resolution_not_unique":
                plan = _canonical_terminal_plan(
                    plan.model_copy(update={"intent": Intent.CLARIFY}), request
                )
                validated = self._validator.validate(plan, request)
            else:
                raise PlannerSemanticError(
                    reason_code,
                    detail=detail,
                    registry_field_id=registry_field_id,
                ) from None
        return PlannedQuery(
            plan=plan,
            validated_plan=validated,
            attempts=PlannerAttemptSummary(
                hcx_calls=1,
                repair_calls=0,
                parse_failures=0,
                semantic_failures=0,
                transport_failures=0,
                fallback_used=False,
            ),
            latency_ms=max(0, int((monotonic() - started) * 1000)),
            fallback_path=("structured_repair" if invalid_content is not None else "structured",),
            safe_assumptions=(f"snapshot_date={request.as_of_date.isoformat()}",),
            request_deadline_at=deadline.work_cutoff_at,
        )


def _canonical_terminal_plan(plan: QueryPlan, request: PlanningRequest) -> QueryPlan:
    question = " ".join(request.question.split())
    if plan.intent not in {Intent.CLARIFY, Intent.UNSUPPORTED} and (
        _requires_unavailable_relationship(question)
        or any(clause.field == "holding_constituent" for clause in plan.filters)
    ):
        plan = plan.model_copy(update={"intent": Intent.UNSUPPORTED})
    if plan.intent not in {Intent.CLARIFY, Intent.UNSUPPORTED}:
        return plan
    if plan.intent is Intent.CLARIFY:
        reason = (
            "상품 유형과 수익률 기간을 지정해 주세요."
            if "수익률" in question
            else "요청 조건을 더 구체적으로 지정해 주세요."
        )
    elif "코드" in question and any(
        term in question for term in ("의미", "명칭", "코드명", "매핑", "테이블")
    ):
        reason = (
            "공식 코드 값 테이블이 제공되지 않아 코드의 의미를 추정하거나 공식 명칭으로 "
            "매핑할 수 없습니다."
        )
    elif "실시간" in question or "지금 이 순간" in question:
        reason = (
            f"평가 모드는 {request.as_of_date.isoformat()} 공식 스냅샷만 사용하므로 "
            "실시간 값은 제공할 수 없습니다."
        )
    elif any(term in question for term in ("예측", "전망", "미래", "앞으로")):
        reason = "제공 데이터는 미래 수익률 예측이나 확정적 전망을 뒷받침하지 않습니다."
    elif any(term in question for term in ("추천", "무손실", "보장", "반드시")):
        reason = "무손실 보장이나 확정적 투자 추천은 제공 데이터로 검증할 수 없습니다."
    else:
        reason = "요청한 내용은 제공 데이터로 검증할 수 없습니다."
    return QueryPlan(
        intent=plan.intent,
        product_types=(),
        entities=(),
        as_of_date=plan.as_of_date,
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=(),
        metric_targets=(),
        sort=(),
        aggregation=None,
        top_k=plan.top_k,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=plan.intent is Intent.CLARIFY,
        clarification_reason=reason,
    )


def _requires_unavailable_relationship(question: str) -> bool:
    return any(
        term in question
        for term in ("구성종목", "보유종목", "보유한", "편입종목", "섹터", "산업군", "노출")
    )


def _semantic_detail(
    reason_code: str,
    plan: QueryPlan,
    registries: RegistryBundle,
) -> tuple[str | None, str | None]:
    if reason_code == "eligibility_unsupported":
        eligibility_fields = {"saleable", "mirae_saleable"}
        for clause in plan.filters:
            if clause.field in eligibility_fields:
                return "filter", clause.field
        for field in plan.metrics:
            if field in eligibility_fields:
                return "metric", field
        for sort in plan.sort:
            if sort.field in eligibility_fields:
                return "sort", sort.field
        if plan.aggregation is not None:
            if plan.aggregation.field in eligibility_fields:
                return "aggregation_field", plan.aggregation.field
            for field in plan.aggregation.group_by:
                if field in eligibility_fields:
                    return "aggregation_group_by", field
        return None, None
    if reason_code != "filter_field_unavailable":
        return None, None
    projections = FieldRegistry.from_bundle(registries).projections
    for clause in plan.filters:
        if clause.field == "holding_constituent":
            continue
        if clause.field not in registries.fields.entries:
            return "unregistered", None
        if not any((clause.field, product) in projections for product in plan.product_types):
            return "product_inapplicable", clause.field
    return None, None
