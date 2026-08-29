"""Minimal production composition seam for the HTTP adapter."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractContextManager, asynccontextmanager
from time import monotonic
from typing import Protocol, runtime_checkable

from finproof.answer.hcx_verbalizer import HcxVerbalizer
from finproof.core.settings import ExecutionMode, Settings
from finproof.domain.answers import AnswerRequest, AnswerResult, FactPack, ProviderWording
from finproof.entity import EntityIndex, EntityResolver, HoldingResolver
from finproof.planner.hcx_client import HcxClient, HcxHttpClientFactory, create_hcx_http_client
from finproof.planner.rule_fallback import RuleFallbackPlanner
from finproof.planner.service import LocalPlanValidator, PlannerProtocol, PlannerService
from finproof.planner.structured_planner import StructuredOutputPlanner
from finproof.query import FieldRegistry, SemanticValidator
from finproof.runtime import open_runtime_artifact_session
from finproof.runtime.session import RuntimeArtifactSession
from finproof.service import AnswerService
from finproof.service.limits import RequestDeadline
from finproof.service.orchestrator import EvaluationOrchestrator, WordingService


@runtime_checkable
class AnswerOrchestrator(Protocol):
    """The one application operation exposed by the evaluation transport."""

    def answer(
        self,
        request: AnswerRequest,
        *,
        deadline: RequestDeadline,
        safe_result: AnswerResult,
    ) -> Awaitable[AnswerResult]: ...


class ApiDependencies:
    """Small injectable boundary around the production dependency graph."""

    def __init__(
        self,
        *,
        open_session: Callable[
            [Settings], AbstractContextManager[object]
        ] = open_runtime_artifact_session,
        create_orchestrator: Callable[[object], AnswerOrchestrator] | None = None,
        http_client_factory: HcxHttpClientFactory = create_hcx_http_client,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.open_session = open_session
        self.create_orchestrator = create_orchestrator
        self._http_client_factory = http_client_factory
        self.clock = clock

    @asynccontextmanager
    async def open_orchestrator(
        self, session: object, settings: Settings
    ) -> AsyncIterator[AnswerOrchestrator]:
        if self.create_orchestrator is not None:
            if settings.execution_mode is ExecutionMode.EVALUATION:
                raise RuntimeError("evaluation graph cannot be overridden")
            yield self.create_orchestrator(session)
            return
        if (
            settings.execution_mode is ExecutionMode.EVALUATION
            and settings.hcx_model_name != "HCX-007"
        ):
            raise RuntimeError("evaluation requires exact HCX-007 Structured Outputs")
        if type(session) is not RuntimeArtifactSession:
            raise TypeError("production graph requires exact runtime session")
        runtime_session = session
        fields = FieldRegistry.from_bundle(runtime_session.registries)
        validator = LocalPlanValidator(
            SemanticValidator(fields),
            entity_resolver=EntityResolver(EntityIndex.from_session(runtime_session)),
            holding_resolver=HoldingResolver.from_session(runtime_session),
        )
        fallback = RuleFallbackPlanner(validator=validator)
        if not settings.hcx_enabled:
            if settings.execution_mode is ExecutionMode.EVALUATION:
                raise RuntimeError("evaluation requires HCX")
            orchestrator = _orchestrator(
                runtime_session, fallback, _DeterministicDemoWording(), settings
            )
            try:
                yield orchestrator
            finally:
                await orchestrator.aclose()
            return
        if settings.hcx_api_key is None:
            raise RuntimeError("validated HCX settings lost the API key")
        async with self._http_client_factory() as http_client:
            hcx_client = HcxClient(http_client=http_client, api_key=settings.hcx_api_key)
            structured = StructuredOutputPlanner(
                generator=hcx_client,
                validator=validator,
                registries=runtime_session.registries,
                model_name=settings.hcx_model_name,
            )
            verbalizer = HcxVerbalizer(generator=hcx_client, model_name=settings.hcx_model_name)
            orchestrator = _orchestrator(
                runtime_session,
                PlannerService(strict_json_planner=structured),
                verbalizer,
                settings,
            )
            try:
                yield orchestrator
            finally:
                await orchestrator.aclose()


def _orchestrator(
    session: RuntimeArtifactSession,
    planner: PlannerProtocol,
    verbalizer: WordingService,
    settings: Settings,
) -> EvaluationOrchestrator:
    return EvaluationOrchestrator(
        planner=planner,
        answer_service=AnswerService(session),
        verbalizer=verbalizer,
        execution_mode=settings.execution_mode,
        snapshot_date=settings.dataset_snapshot_date,
    )


class _DeterministicDemoWording:
    """Explicit non-evaluation compatibility wording."""

    async def verbalize(
        self,
        fact_pack: FactPack,
        *,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording:
        del request_id, deadline
        return _wording(fact_pack)

    async def repair(
        self,
        fact_pack: FactPack,
        *,
        invalid_content: str,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording:
        del invalid_content, request_id, deadline
        return _wording(fact_pack)


def _wording(fact_pack: FactPack) -> ProviderWording:
    return ProviderWording(
        answer="".join(part.text for part in fact_pack.surface_parts),
        surface_part_ids=tuple(part.part_id for part in fact_pack.surface_parts),
        claim_ids=fact_pack.required_claim_ids,
        limitation_codes=fact_pack.required_limitation_codes,
    )
