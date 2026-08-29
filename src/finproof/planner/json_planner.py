"""Strict-JSON HyperCLOVA X planner adapter."""

from time import monotonic

from finproof.planner.models import HcxMessage, HcxRequest
from finproof.planner.prompts import build_system_prompt
from finproof.planner.provider_schema import ProviderPlanError, parse_provider_plan
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
from finproof.registry.loader import RegistryBundle
from finproof.service.limits import RequestDeadline


class StrictJsonPlanner:
    """One-call strict JSON adapter; retry policy remains in PlannerService."""

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
        messages = [HcxMessage(role="system", content=prompt.text)]
        messages.append(HcxMessage(role="user", content=request.question))
        if invalid_content is not None:
            messages.extend(
                (
                    HcxMessage(role="assistant", content=invalid_content),
                    HcxMessage(
                        role="user",
                        content="Correct only the JSON/schema error. Return JSON only.",
                    ),
                )
            )
        try:
            provider_request = HcxRequest.strict_json(
                model_name=self._model_name,
                messages=tuple(messages),
                max_completion_tokens=2_048,
                temperature=0.0,
                seed=17,
            )
        except ValueError:
            raise PlannerOutputError(invalid_content or "") from None
        attempt_name = "repair" if invalid_content is not None else "plan"
        response = await self._generator.generate(
            provider_request,
            request_id=f"{request.request_id}-{attempt_name}",
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
            raise PlannerSemanticError(semantic_reason_code(error)) from None
        return PlannedQuery(
            plan=plan,
            validated_plan=validated,
            attempts=PlannerAttemptSummary(
                hcx_calls=1,
                repair_calls=int(invalid_content is not None),
                parse_failures=0,
                semantic_failures=0,
                transport_failures=0,
                fallback_used=False,
            ),
            latency_ms=max(0, int((monotonic() - started) * 1000)),
            fallback_path=("repair" if invalid_content is not None else "strict_json",),
            safe_assumptions=(f"snapshot_date={request.as_of_date.isoformat()}",),
            request_deadline_at=deadline.work_cutoff_at,
        )
