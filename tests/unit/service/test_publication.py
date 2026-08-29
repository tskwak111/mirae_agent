"""Single organizer response publication boundary."""

import json
from datetime import date

from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.answers import AnswerRequest
from finproof.service.limits import RequestDeadline
from finproof.service.publication import build_safe_publication


def test_safe_publication_owns_exact_result_envelope_and_bytes() -> None:
    deadline = RequestDeadline.start(clock=lambda: 100.0)
    request = AnswerRequest(question_id="Q-1", question="질문")

    publication = build_safe_publication(
        request,
        correlation_id="corr-1",
        snapshot_date=date(2026, 8, 24),
        deadline=deadline,
    )

    expected = publication.response.model_dump(mode="json")
    assert set(expected) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert publication.body == canonical_json_bytes(expected, terminal_newline=False)
    assert json.loads(publication.body) == expected
    assert publication.result.answer.text == "요청을 처리할 수 없습니다."
    assert publication.result.retrieved_context == "{}"
    forbidden = ("api-key", "Authorization", "/Users/", "SELECT ", "prompt", "Traceback")
    assert all(value.encode() not in publication.body for value in forbidden)
