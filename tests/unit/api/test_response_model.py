"""Exact organizer response contract."""

import pytest
from pydantic import ValidationError

from finproof.api.models import EvaluationResponse
from finproof.data.artifacts.hashing import canonical_json_bytes


def _response(**changes: object) -> EvaluationResponse:
    values: dict[str, object] = {
        "question_id": "Q1",
        "question": "질문",
        "retrieved_context": "{}",
        "think_trace": "validation=passed",
        "answer": "답변",
    }
    values.update(changes)
    return EvaluationResponse.model_validate(values)


def test_evaluation_response_has_exact_five_string_fields() -> None:
    response = _response()

    assert response.model_dump() == {
        "question_id": "Q1",
        "question": "질문",
        "retrieved_context": "{}",
        "think_trace": "validation=passed",
        "answer": "답변",
    }
    assert canonical_json_bytes(response.model_dump(mode="json"), terminal_newline=False) == (
        b'{"answer":"\xeb\x8b\xb5\xeb\xb3\x80","question":"\xec\xa7\x88\xeb\xac\xb8",'
        b'"question_id":"Q1","retrieved_context":"{}",'
        b'"think_trace":"validation=passed"}'
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"extra": "no"},
        {"question_id": 1},
        {"question": 1},
        {"retrieved_context": 1},
        {"think_trace": 1},
        {"answer": 1},
        {"question_id": "q" * 201},
        {"question": "q" * 4_001},
        {"retrieved_context": "가" * 8_001},
        {"think_trace": "가" * 5_334},
        {"answer": "a" * 12_001},
    ],
)
def test_evaluation_response_rejects_invalid_or_oversized_fields(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _response(**changes)


def test_evaluation_response_rejects_oversized_canonical_json() -> None:
    with pytest.raises(ValidationError, match="response exceeds configured bound"):
        _response(
            question_id="😀" * 200,
            question="😀" * 4_000,
            retrieved_context="가" * 8_000,
            think_trace="가" * 5_333,
            answer="😀" * 12_000,
        )
