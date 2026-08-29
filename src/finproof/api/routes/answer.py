"""The sole public evaluation route."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from finproof.api.dependencies import AnswerOrchestrator
from finproof.core.correlation import bind_correlation_id
from finproof.domain.answers import AnswerRequest
from finproof.service.limits import RequestDeadline
from finproof.service.publication import build_safe_publication, publish_result

router = APIRouter()


@router.get("/answer")
async def answer(
    request: Request,
    question_id: Annotated[str, Query(min_length=1, max_length=200)],
    question: Annotated[str, Query(min_length=1, max_length=4_000)],
) -> Response:
    """Adapt one verified answer to the exact organizer envelope."""
    with bind_correlation_id() as correlation_id:
        request.state.correlation_id = correlation_id
        deadline = request.state.deadline
        if type(deadline) is not RequestDeadline:
            raise RuntimeError("evaluation deadline differs")
        answer_request = AnswerRequest(question_id=question_id, question=question)
        safe_publication = build_safe_publication(
            answer_request,
            correlation_id=correlation_id,
            snapshot_date=request.app.state.settings.dataset_snapshot_date,
            deadline=deadline,
        )
        request.state.safe_publication = safe_publication
        orchestrator = request.app.state.answer_orchestrator
        if not isinstance(orchestrator, AnswerOrchestrator):
            raise RuntimeError("evaluation orchestrator differs")
        result = await orchestrator.answer(
            answer_request,
            deadline=deadline,
            safe_result=safe_publication.result,
        )
        publication = (
            safe_publication
            if result is safe_publication.result
            else publish_result(
                answer_request,
                result,
                correlation_id=correlation_id,
                deadline=deadline,
            )
        )
    return Response(
        content=publication.body,
        media_type="application/json",
        status_code=200,
    )
