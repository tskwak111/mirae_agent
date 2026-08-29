"""The sole organizer result, envelope, and canonical-byte publication boundary."""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.answers import AnswerRequest, AnswerResult, VerifiedAnswer
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import Intent, ResultGrain, TopKScope
from finproof.service.limits import RequestDeadline

if TYPE_CHECKING:
    from finproof.api.models import EvaluationResponse


@dataclass(frozen=True, slots=True)
class EvaluationPublication:
    result: AnswerResult
    response: "EvaluationResponse"
    body: bytes


def build_safe_publication(
    request: AnswerRequest,
    *,
    correlation_id: str,
    snapshot_date: date,
    deadline: RequestDeadline,
) -> EvaluationPublication:
    """Prebuild the fixed safe result and its exact public bytes."""
    return publish_result(
        request,
        AnswerResult(
            answer=VerifiedAnswer(text="요청을 처리할 수 없습니다.", claims=()),
            retrieved_context="{}",
            trace=ExecutionTrace(
                correlation_id=correlation_id,
                intent=Intent.CLARIFY,
                product_types=(),
                as_of_date=snapshot_date,
                result_grain=ResultGrain.PRODUCT,
                top_k_scope=TopKScope.GLOBAL,
                segments=(),
                candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
                tools=("safe_failure",),
                policy_ids=(),
                validation=TraceValidation.SAFE_FAILURE,
                versions={},
                latency_ms={},
            ),
        ),
        correlation_id=correlation_id,
        deadline=deadline,
    )


def publish_result(
    request: AnswerRequest,
    result: AnswerResult,
    *,
    correlation_id: str,
    deadline: RequestDeadline,
) -> EvaluationPublication:
    """Construct the only public envelope and canonical serialization."""
    from finproof.api.models import EvaluationResponse

    if deadline.remaining_outer_seconds() <= 0:
        raise TimeoutError("publication deadline exceeded")
    trace = result.trace.model_copy(update={"correlation_id": correlation_id})
    response = EvaluationResponse(
        question_id=request.question_id,
        question=request.question,
        retrieved_context=result.retrieved_context,
        think_trace=canonical_json_bytes(
            trace.model_dump(mode="json"), terminal_newline=False
        ).decode(),
        answer=result.answer.text,
    )
    return EvaluationPublication(
        result=result,
        response=response,
        body=canonical_json_bytes(response.model_dump(mode="json"), terminal_newline=False),
    )
