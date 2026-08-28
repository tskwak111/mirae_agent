"""Bounded planner orchestration and local semantic validation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from time import monotonic
from typing import Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field

from finproof.core.settings import ExecutionMode
from finproof.domain.execution import ValidatedQueryPlan
from finproof.domain.query_plan import QueryPlan
from finproof.entity import EntityResolver, HoldingResolver
from finproof.planner.hcx_client import (
    HcxClientError,
    HcxMalformedResponseError,
    HcxNoContentError,
    HcxRateLimitError,
    HcxTransportError,
)
from finproof.planner.models import HcxRequest, HcxResponse
from finproof.query import ResolutionBundle, SemanticValidator, ValidationContext


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class PlanningRequest(_FrozenModel):
    """Transport-independent planner input with one absolute deadline."""

    question: str = Field(min_length=1, max_length=4_000)
    request_id: str = Field(min_length=1, max_length=200)
    as_of_date: date
    execution_mode: ExecutionMode
    deadline_at: float

    @classmethod
    def start(
        cls,
        *,
        question: str,
        request_id: str,
        as_of_date: date,
        execution_mode: ExecutionMode,
        deadline_seconds: float,
    ) -> Self:
        if deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")
        return cls(
            question=question,
            request_id=request_id,
            as_of_date=as_of_date,
            execution_mode=execution_mode,
            deadline_at=monotonic() + deadline_seconds,
        )


class PlannerAttemptSummary(_FrozenModel):
    hcx_calls: int = Field(ge=0, le=2)
    repair_calls: int = Field(ge=0, le=1)
    parse_failures: int = Field(ge=0, le=2)
    semantic_failures: int = Field(ge=0, le=2)
    transport_failures: int = Field(ge=0, le=2)
    fallback_used: bool


class PlannedQuery(_FrozenModel):
    plan: QueryPlan
    validated_plan: ValidatedQueryPlan
    attempts: PlannerAttemptSummary
    latency_ms: int = Field(ge=0)
    fallback_path: tuple[str, ...]
    safe_assumptions: tuple[str, ...]
    request_deadline_at: float


class PlannerOutputError(ValueError):
    """Model content failed local JSON/schema validation and may be repaired once."""

    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__("planner output validation failed")


class PlannerSemanticError(ValueError):
    """A parsed plan failed domain validation and must never execute."""


class HcxGenerator(Protocol):
    async def generate(self, request: HcxRequest, request_id: str) -> HcxResponse: ...


class PlannerProtocol(Protocol):
    async def plan(self, request: PlanningRequest) -> PlannedQuery: ...


class _RepairablePlanner(PlannerProtocol, Protocol):
    async def repair(self, request: PlanningRequest, invalid_content: str) -> PlannedQuery: ...


class LocalPlanValidator:
    """Resolve exact entities and enter the existing semantic-validation boundary."""

    def __init__(
        self,
        semantic_validator: SemanticValidator,
        *,
        entity_resolver: EntityResolver | None = None,
        holding_resolver: HoldingResolver | None = None,
    ) -> None:
        self._semantic_validator = semantic_validator
        self._entity_resolver = entity_resolver
        self._holding_resolver = holding_resolver

    def validate(self, plan: QueryPlan, request: PlanningRequest) -> ValidatedQueryPlan:
        if plan.entities and self._entity_resolver is None:
            raise ValueError("entity resolver is required for entity mentions")
        holding_filters = tuple(
            clause for clause in plan.filters if clause.field == "holding_constituent"
        )
        if holding_filters and self._holding_resolver is None:
            raise ValueError("holding resolver is required for constituent filters")
        resolutions = ResolutionBundle(
            results=tuple(
                self._entity_resolver.resolve(mention, product_types=plan.product_types)
                for mention in plan.entities
            )
            if self._entity_resolver is not None
            else (),
            holding_constituent=(
                self._holding_resolver.resolve(cast(str, holding_filters[0].value))
                if holding_filters and self._holding_resolver is not None
                else None
            ),
        )
        return self._semantic_validator.validate(
            plan,
            resolutions=resolutions,
            context=ValidationContext(
                as_of_date=request.as_of_date,
                execution_mode=request.execution_mode,
            ),
        )


class PlannerService:
    """Runtime strict-JSON planner with one retry/repair and deterministic fallback."""

    def __init__(
        self,
        *,
        strict_json_planner: _RepairablePlanner,
        rule_fallback: PlannerProtocol,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if not callable(getattr(strict_json_planner, "repair", None)):
            raise TypeError("strict_json_planner must support strict JSON repair")
        self._strict = strict_json_planner
        self._fallback = rule_fallback
        self._sleep = sleep
        self._clock = clock

    async def plan(self, request: PlanningRequest) -> PlannedQuery:
        started = self._clock()
        path = ["strict_json"]
        hcx_calls = 1
        repair_calls = 0
        parse_failures = 0
        semantic_failures = 0
        transport_failures = 0
        try:
            result = await self._within_deadline(self._strict.plan(request), request)
            return self._finalize(
                result,
                request=request,
                started=started,
                path=path,
                hcx_calls=hcx_calls,
                repair_calls=repair_calls,
                parse_failures=parse_failures,
                semantic_failures=semantic_failures,
                transport_failures=transport_failures,
            )
        except PlannerOutputError as error:
            parse_failures += 1
            if self._remaining(request) > 0:
                path.append("repair")
                repair_calls = 1
                hcx_calls = 2
                try:
                    result = await self._within_deadline(
                        self._strict.repair(request, error.content), request
                    )
                    return self._finalize(
                        result,
                        request=request,
                        started=started,
                        path=path,
                        hcx_calls=hcx_calls,
                        repair_calls=repair_calls,
                        parse_failures=parse_failures,
                        semantic_failures=semantic_failures,
                        transport_failures=transport_failures,
                    )
                except PlannerOutputError:
                    parse_failures += 1
                except PlannerSemanticError:
                    semantic_failures += 1
                except (HcxClientError, TimeoutError):
                    transport_failures += 1
        except PlannerSemanticError:
            semantic_failures += 1
        except (
            HcxNoContentError,
            HcxTransportError,
            HcxMalformedResponseError,
            HcxRateLimitError,
        ) as error:
            transport_failures += 1
            try:
                may_retry = await self._may_retry(error, request)
            except TimeoutError:
                transport_failures += 1
                may_retry = False
            if may_retry:
                path.append("retry")
                hcx_calls = 2
                try:
                    result = await self._within_deadline(self._strict.plan(request), request)
                    return self._finalize(
                        result,
                        request=request,
                        started=started,
                        path=path,
                        hcx_calls=hcx_calls,
                        repair_calls=repair_calls,
                        parse_failures=parse_failures,
                        semantic_failures=semantic_failures,
                        transport_failures=transport_failures,
                    )
                except PlannerOutputError:
                    parse_failures += 1
                except PlannerSemanticError:
                    semantic_failures += 1
                except (HcxClientError, TimeoutError):
                    transport_failures += 1
        except (HcxClientError, TimeoutError):
            transport_failures += 1

        fallback = await self._fallback.plan(request)
        path.append("rule_fallback")
        return self._finalize(
            fallback,
            request=request,
            started=started,
            path=path,
            hcx_calls=hcx_calls,
            repair_calls=repair_calls,
            parse_failures=parse_failures,
            semantic_failures=semantic_failures,
            transport_failures=transport_failures,
            fallback_used=True,
        )

    async def _within_deadline(
        self, operation: Awaitable[PlannedQuery], request: PlanningRequest
    ) -> PlannedQuery:
        remaining = self._remaining(request)
        if remaining <= 0:
            if hasattr(operation, "close"):
                operation.close()
            raise TimeoutError
        return await asyncio.wait_for(operation, timeout=remaining)

    async def _may_retry(
        self,
        error: HcxClientError,
        request: PlanningRequest,
    ) -> bool:
        if isinstance(error, HcxRateLimitError):
            delay = error.rate_limits.reset_requests_seconds
            if delay is None or delay >= self._remaining(request):
                return False
            await asyncio.wait_for(self._sleep(delay), timeout=self._remaining(request))
        return self._remaining(request) > 0

    def _remaining(self, request: PlanningRequest) -> float:
        return max(0.0, request.deadline_at - self._clock())

    def _finalize(
        self,
        result: PlannedQuery,
        *,
        request: PlanningRequest,
        started: float,
        path: list[str],
        hcx_calls: int,
        repair_calls: int,
        parse_failures: int,
        semantic_failures: int,
        transport_failures: int,
        fallback_used: bool = False,
    ) -> PlannedQuery:
        return result.model_copy(
            update={
                "attempts": PlannerAttemptSummary(
                    hcx_calls=hcx_calls,
                    repair_calls=repair_calls,
                    parse_failures=parse_failures,
                    semantic_failures=semantic_failures,
                    transport_failures=transport_failures,
                    fallback_used=fallback_used,
                ),
                "latency_ms": max(0, int((self._clock() - started) * 1000)),
                "fallback_path": tuple(path),
                "request_deadline_at": request.deadline_at,
            }
        )
