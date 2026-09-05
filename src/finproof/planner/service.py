"""Bounded planner orchestration and local semantic validation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from time import monotonic
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from finproof.core.settings import ExecutionMode
from finproof.domain.execution import ValidatedQueryPlan
from finproof.domain.query_plan import QueryPlan
from finproof.entity import EntityResolver, HoldingResolver
from finproof.planner.hcx_client import (
    HcxClientError,
    HcxHttpError,
    HcxRateLimitError,
    HcxTransportError,
)
from finproof.planner.models import HcxRequest, HcxResponse
from finproof.query import ResolutionBundle, SemanticValidator, ValidationContext
from finproof.service.limits import RequestDeadline


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class PlanningRequest(_FrozenModel):
    """Transport-independent planner input; the application owns its deadline."""

    question: str = Field(min_length=1, max_length=4_000)
    request_id: str = Field(min_length=1, max_length=200)
    as_of_date: date
    execution_mode: ExecutionMode


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

    def __init__(
        self,
        content: str,
        *,
        validation_stage: str | None = None,
        canonical_substage: str | None = None,
        canonical_path: str | None = None,
        canonical_keyword: str | None = None,
        filter_shape_category: str | None = None,
    ) -> None:
        self.content = content
        self.validation_stage = validation_stage
        self.canonical_substage = canonical_substage
        self.canonical_path = canonical_path
        self.canonical_keyword = canonical_keyword
        self.filter_shape_category = filter_shape_category
        super().__init__("planner output validation failed")


class PlannerSemanticError(ValueError):
    """A parsed plan failed domain validation and must never execute."""

    def __init__(
        self,
        reason_code: str,
        *,
        detail: str | None = None,
        registry_field_id: str | None = None,
    ) -> None:
        self.reason_code = reason_code
        self.detail = detail
        self.registry_field_id = registry_field_id
        super().__init__("planner semantic validation failed")


_SEMANTIC_REASON_CODES = {
    "entity resolver is required for entity mentions": "entity_resolver_required",
    "holding resolver is required for constituent filters": "holding_resolver_required",
    "semantic validation inputs differ": "validation_inputs_mismatch",
    "validation as-of date differs": "as_of_date_mismatch",
    "product type and result grain differ": "result_grain_mismatch",
    "validated eligibility is unsupported for product type": "eligibility_unsupported",
    "entity resolution count differs": "entity_resolution_count_mismatch",
    "entity resolution is not uniquely selected": "entity_resolution_not_unique",
    "holding constituent filter cardinality differs": "holding_filter_cardinality",
    "holding constituent cannot be combined with domestic bond": "holding_with_bond",
    "holding resolution is not uniquely selected": "holding_resolution_not_unique",
    "holding resolution lacks a relation filter": "holding_resolution_without_filter",
    "holding filter differs": "holding_filter_mismatch",
    "filter field has no selected product target": "filter_field_unavailable",
    "filter operator is not registered": "filter_operator_unregistered",
    "filter value type differs": "filter_value_type_mismatch",
    "metric has no selected product target": "metric_unavailable",
    "sort field is not registered": "sort_field_unregistered",
    "aggregation operation is not registered": "aggregation_operation_unregistered",
    "aggregation target is not registered": "aggregation_target_unregistered",
    "aggregation group is not registered": "aggregation_group_unregistered",
}


def semantic_reason_code(error: Exception) -> str:
    """Map only local fixed validation messages to non-content reason codes."""
    return _SEMANTIC_REASON_CODES.get(str(error), "unknown")


class PlannerTerminalError(ValueError):
    """Bounded terminal planner category without provider content."""

    def __init__(self, category: str, attempts: PlannerAttemptSummary) -> None:
        self.category = category
        self.attempts = attempts
        super().__init__(f"planner terminal failure: {category}")


class HcxGenerator(Protocol):
    async def generate(
        self, request: HcxRequest, request_id: str, *, deadline: RequestDeadline
    ) -> HcxResponse: ...


class PlannerProtocol(Protocol):
    async def plan(
        self, request: PlanningRequest, *, deadline: RequestDeadline
    ) -> PlannedQuery: ...


class _RepairablePlanner(PlannerProtocol, Protocol):
    async def repair(
        self,
        request: PlanningRequest,
        invalid_content: str,
        *,
        validation_stage: str | None = None,
        canonical_path: str | None = None,
        canonical_keyword: str | None = None,
        deadline: RequestDeadline,
    ) -> PlannedQuery: ...


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
    """Evaluation strict-JSON planner with one mutually exclusive retry or repair."""

    def __init__(
        self,
        *,
        strict_json_planner: _RepairablePlanner,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if not callable(getattr(strict_json_planner, "repair", None)):
            raise TypeError("planner must support invalid-output repair")
        self._strict = strict_json_planner
        self._sleep = sleep
        self._clock = clock

    async def plan(self, request: PlanningRequest, *, deadline: RequestDeadline) -> PlannedQuery:
        started = self._clock()
        path = ["structured"]
        hcx_calls = 1
        repair_calls = 0
        parse_failures = 0
        semantic_failures = 0
        transport_failures = 0
        try:
            result = await self._within_deadline(
                self._strict.plan(request, deadline=deadline), deadline
            )
            return self._finalize(
                result,
                deadline=deadline,
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
            if deadline.remaining_work_seconds() > 0:
                path.append("repair")
                repair_calls = 1
                hcx_calls = 2
                try:
                    result = await self._within_deadline(
                        self._strict.repair(
                            request,
                            error.content,
                            validation_stage=error.validation_stage,
                            canonical_path=error.canonical_path,
                            canonical_keyword=error.canonical_keyword,
                            deadline=deadline,
                        ),
                        deadline,
                    )
                    return self._finalize(
                        result,
                        deadline=deadline,
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
                    category = "repair_output_invalid"
                except PlannerSemanticError:
                    semantic_failures += 1
                    category = "repair_semantic_invalid"
                except (HcxClientError, TimeoutError):
                    transport_failures += 1
                    category = "repair_provider_failure"
                raise self._terminal(
                    category,
                    hcx_calls=hcx_calls,
                    repair_calls=repair_calls,
                    parse_failures=parse_failures,
                    semantic_failures=semantic_failures,
                    transport_failures=transport_failures,
                ) from None
            raise self._terminal(
                "work_cutoff",
                hcx_calls=hcx_calls,
                repair_calls=repair_calls,
                parse_failures=parse_failures,
                semantic_failures=semantic_failures,
                transport_failures=transport_failures,
            ) from None
        except PlannerSemanticError:
            semantic_failures += 1
            raise self._terminal(
                "semantic_invalid",
                hcx_calls=hcx_calls,
                repair_calls=repair_calls,
                parse_failures=parse_failures,
                semantic_failures=semantic_failures,
                transport_failures=transport_failures,
            ) from None
        except (HcxTransportError, HcxRateLimitError, HcxHttpError) as error:
            transport_failures += 1
            try:
                may_retry = await self._may_retry(error, deadline)
            except TimeoutError:
                transport_failures += 1
                may_retry = False
            if may_retry:
                path.append("retry")
                hcx_calls = 2
                try:
                    result = await self._within_deadline(
                        self._strict.plan(request, deadline=deadline), deadline
                    )
                    return self._finalize(
                        result,
                        deadline=deadline,
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
                    category = "retry_output_invalid"
                except PlannerSemanticError:
                    semantic_failures += 1
                    category = "retry_semantic_invalid"
                except (HcxClientError, TimeoutError):
                    transport_failures += 1
                    category = "retry_provider_failure"
                raise self._terminal(
                    category,
                    hcx_calls=hcx_calls,
                    repair_calls=repair_calls,
                    parse_failures=parse_failures,
                    semantic_failures=semantic_failures,
                    transport_failures=transport_failures,
                ) from None
            raise self._terminal(
                "provider_failure",
                hcx_calls=hcx_calls,
                repair_calls=repair_calls,
                parse_failures=parse_failures,
                semantic_failures=semantic_failures,
                transport_failures=transport_failures,
            ) from None
        except (HcxClientError, TimeoutError):
            transport_failures += 1
            raise self._terminal(
                "provider_failure",
                hcx_calls=hcx_calls,
                repair_calls=repair_calls,
                parse_failures=parse_failures,
                semantic_failures=semantic_failures,
                transport_failures=transport_failures,
            ) from None

    async def _within_deadline(
        self, operation: Awaitable[PlannedQuery], deadline: RequestDeadline
    ) -> PlannedQuery:
        remaining = deadline.remaining_work_seconds()
        if remaining <= 0:
            if hasattr(operation, "close"):
                operation.close()
            raise TimeoutError
        return await asyncio.wait_for(operation, timeout=remaining)

    async def _may_retry(
        self,
        error: HcxClientError,
        deadline: RequestDeadline,
    ) -> bool:
        if isinstance(error, HcxHttpError) and error.http_status < 500:
            return False
        if isinstance(error, HcxRateLimitError):
            delay = error.rate_limits.reset_requests_seconds
            if delay is None or delay >= deadline.remaining_work_seconds():
                return False
            await asyncio.wait_for(self._sleep(delay), timeout=deadline.remaining_work_seconds())
        return deadline.remaining_work_seconds() > 0

    def _finalize(
        self,
        result: PlannedQuery,
        *,
        deadline: RequestDeadline,
        started: float,
        path: list[str],
        hcx_calls: int,
        repair_calls: int,
        parse_failures: int,
        semantic_failures: int,
        transport_failures: int,
    ) -> PlannedQuery:
        return result.model_copy(
            update={
                "attempts": PlannerAttemptSummary(
                    hcx_calls=hcx_calls,
                    repair_calls=repair_calls,
                    parse_failures=parse_failures,
                    semantic_failures=semantic_failures,
                    transport_failures=transport_failures,
                    fallback_used=False,
                ),
                "latency_ms": max(0, int((self._clock() - started) * 1000)),
                "fallback_path": tuple(path),
                "request_deadline_at": deadline.work_cutoff_at,
            }
        )

    @staticmethod
    def _terminal(
        category: str,
        *,
        hcx_calls: int,
        repair_calls: int,
        parse_failures: int,
        semantic_failures: int,
        transport_failures: int,
    ) -> PlannerTerminalError:
        return PlannerTerminalError(
            category,
            PlannerAttemptSummary(
                hcx_calls=hcx_calls,
                repair_calls=repair_calls,
                parse_failures=parse_failures,
                semantic_failures=semantic_failures,
                transport_failures=transport_failures,
                fallback_used=False,
            ),
        )
