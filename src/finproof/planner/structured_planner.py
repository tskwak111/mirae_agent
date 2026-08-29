"""HCX-007 Structured Outputs planner adapter."""

from time import monotonic

from finproof.domain.query_plan import QueryPlan
from finproof.planner.models import HcxMessage, HcxRequest
from finproof.planner.prompts import build_system_prompt
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
        deadline: RequestDeadline,
    ) -> PlannedQuery:
        return await self._attempt(request, invalid_content=invalid_content, deadline=deadline)

    async def _attempt(
        self,
        request: PlanningRequest,
        *,
        invalid_content: str | None,
        deadline: RequestDeadline,
    ) -> PlannedQuery:
        started = monotonic()
        prompt = build_system_prompt(self._registries, snapshot_date=request.as_of_date)
        messages = [
            HcxMessage(role="system", content=prompt.text),
            HcxMessage(role="user", content=request.question),
        ]
        if invalid_content is not None:
            messages.extend(
                (
                    HcxMessage(role="assistant", content=invalid_content),
                    HcxMessage(
                        role="user",
                        content=(
                            "Correct only the JSON/schema error. One product_type must use "
                            "its native result_grain: domestic_bond=instrument; "
                            "domestic_etf|domestic_etn|overseas_etf|overseas_etn="
                            "listed_product; public_fund=fund_item. Use result_grain=product "
                            "only for heterogeneous native grains. 낮은/높은 with top-k "
                            "define sort direction, not a filter. Without an explicit literal "
                            "value, set, range, or missing-state condition, emit filters=[]; "
                            "never invent a threshold. Return JSON only."
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
        response = await self._generator.generate(
            provider_request,
            request_id=(
                f"{request.request_id}-structured-repair"
                if invalid_content is not None
                else f"{request.request_id}-structured"
            ),
            deadline=deadline,
        )
        try:
            plan = parse_provider_plan(response.message_content)
        except ProviderPlanError as error:
            raise PlannerOutputError(
                response.message_content,
                validation_stage=error.stage.value,
                canonical_substage=error.canonical_substage,
                canonical_path=error.canonical_path,
                canonical_keyword=error.canonical_keyword,
                filter_shape_category=error.filter_shape_category,
            ) from None
        try:
            validated = self._validator.validate(plan, request)
        except (TypeError, ValueError) as error:
            reason_code = semantic_reason_code(error)
            detail, registry_field_id = _semantic_detail(reason_code, plan, self._registries)
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


def _semantic_detail(
    reason_code: str,
    plan: QueryPlan,
    registries: RegistryBundle,
) -> tuple[str | None, str | None]:
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
