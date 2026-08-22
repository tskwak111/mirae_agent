"""Dormant HCX-007 Structured Outputs adapter."""

from time import monotonic

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
)
from finproof.registry.loader import RegistryBundle


class StructuredOutputPlanner:
    """Fixture-testable adapter with no Phase 3 runtime composition path."""

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

    async def plan(self, request: PlanningRequest) -> PlannedQuery:
        started = monotonic()
        prompt = build_system_prompt(self._registries, snapshot_date=request.as_of_date)
        provider_request = HcxRequest.structured(
            model_name=self._model_name,
            messages=(
                HcxMessage(role="system", content=prompt.text),
                HcxMessage(role="user", content=request.question),
            ),
            schema=build_hcx_query_plan_schema(),
            max_completion_tokens=2_048,
            temperature=0.0,
            seed=17,
        )
        response = await self._generator.generate(
            provider_request, request_id=f"{request.request_id}-structured"
        )
        try:
            plan = parse_provider_plan(response.message_content)
        except ProviderPlanError:
            raise PlannerOutputError(response.message_content) from None
        try:
            validated = self._validator.validate(plan, request)
        except (TypeError, ValueError):
            raise PlannerSemanticError("planner semantic validation failed") from None
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
            fallback_path=("structured",),
            safe_assumptions=(f"snapshot_date={request.as_of_date.isoformat()}",),
            request_deadline_at=request.deadline_at,
        )
