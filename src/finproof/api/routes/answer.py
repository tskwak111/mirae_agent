"""The sole public evaluation route."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from finproof.api.dependencies import AnswerOrchestrator
from finproof.api.models import EvaluationResponse
from finproof.core.correlation import bind_correlation_id
from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.answers import AnswerRequest

router = APIRouter()


@router.get("/answer", response_model=EvaluationResponse)
async def answer(
    request: Request,
    question_id: Annotated[str, Query(min_length=1, max_length=200)],
    question: Annotated[str, Query(min_length=1, max_length=4_000)],
) -> EvaluationResponse:
    """Adapt one verified answer to the exact organizer envelope."""
    orchestrator = request.app.state.answer_orchestrator
    if not isinstance(orchestrator, AnswerOrchestrator):
        raise RuntimeError("evaluation orchestrator differs")
    with bind_correlation_id() as correlation_id:
        request.state.correlation_id = correlation_id
        result = await orchestrator.answer(
            AnswerRequest(question_id=question_id, question=question)
        )
    trace = result.trace.model_copy(update={"correlation_id": correlation_id})
    return EvaluationResponse(
        question_id=question_id,
        question=question,
        retrieved_context=result.retrieved_context,
        think_trace=canonical_json_bytes(
            trace.model_dump(mode="json"), terminal_newline=False
        ).decode(),
        answer=result.answer.text,
    )
