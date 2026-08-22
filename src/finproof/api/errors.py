"""Safe evaluation error rendering."""

from uuid import uuid4

from finproof.api.models import EvaluationResponse
from finproof.data.artifacts.hashing import canonical_json_bytes


def safe_failure(
    *, question_id: str, question: str, correlation_id: str | None = None
) -> EvaluationResponse:
    """Return the organizer envelope without exposing an internal exception."""
    request_id = correlation_id or uuid4().hex
    return EvaluationResponse(
        question_id=question_id,
        question=question,
        retrieved_context="{}",
        think_trace=canonical_json_bytes(
            {"correlation_id": request_id, "stages": ["safe_failure"]},
            terminal_newline=False,
        ).decode(),
        answer="요청을 처리할 수 없습니다.",
    )
