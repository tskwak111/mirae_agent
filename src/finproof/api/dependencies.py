"""Minimal composition seam for the HTTP adapter."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from finproof.core.settings import Settings
from finproof.domain.answers import AnswerRequest, AnswerResult
from finproof.runtime import open_runtime_artifact_session


@runtime_checkable
class AnswerOrchestrator(Protocol):
    """The one application operation exposed by the evaluation transport."""

    def answer(self, request: AnswerRequest) -> Awaitable[AnswerResult]: ...


class ApiDependencies:
    """Small injectable runtime boundary; orchestration remains a later task."""

    def __init__(
        self,
        *,
        open_session: Callable[
            [Settings], AbstractContextManager[object]
        ] = open_runtime_artifact_session,
        create_orchestrator: Callable[[object], AnswerOrchestrator] | None = None,
    ) -> None:
        self.open_session = open_session
        self.create_orchestrator = create_orchestrator or _unconfigured_orchestrator


def _unconfigured_orchestrator(_: object) -> AnswerOrchestrator:
    raise RuntimeError("evaluation orchestrator is not configured")
