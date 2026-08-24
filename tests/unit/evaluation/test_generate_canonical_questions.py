import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import SecretStr
from tools import generate_canonical_questions as generator
from tools.generate_canonical_questions import (
    generate_review_packet,
    write_review_packet,
)

from finproof.planner.models import HcxRequest

_CATEGORIES = (
    *("lookup" for _ in range(4)),
    *("screen" for _ in range(5)),
    *("rank" for _ in range(4)),
    *("compare" for _ in range(3)),
    *("aggregate" for _ in range(2)),
    *("cross_product" for _ in range(2)),
    "clarification",
    *("quality" for _ in range(3)),
)


def _content(*, categories: tuple[str, ...] = _CATEGORIES) -> str:
    return json.dumps(
        {
            "candidates": [
                {
                    "category": category,
                    "question": f"검토용 한국어 금융상품 질문 {index}은 무엇인가요?",
                }
                for index, category in enumerate(categories, 1)
            ]
        },
        ensure_ascii=False,
    )


class _Response:
    def __init__(self, message_content: str) -> None:
        self.message_content = message_content


class _Client:
    def __init__(self, content: str) -> None:
        self._content = content
        self.requests: list[tuple[HcxRequest, str]] = []

    async def generate(self, request: HcxRequest, request_id: str) -> _Response:
        self.requests.append((request, request_id))
        return _Response(self._content)


@pytest.mark.asyncio
async def test_hcx_generation_builds_exact_pending_review_packet() -> None:
    client = _Client(_content())

    packet = await generate_review_packet(
        client,
        model_name="HCX-007",
        generated_at=datetime(2026, 8, 24, 12, 30, tzinfo=UTC),
    )

    assert packet["batch_id"] == "001"
    assert packet["provider"] == "naver-hyperclova-x"
    assert packet["model"] == "HCX-007"
    assert packet["seed"] == 17
    assert packet["prompt_version"] == "canonical-question-candidates-v1"
    prompt_sha256 = packet["prompt_sha256"]
    assert isinstance(prompt_sha256, str)
    assert len(prompt_sha256) == 64
    assert packet["generated_at"] == "2026-08-24T12:30:00Z"
    assert packet["review_status"] == "pending_human_review"
    assert packet["reviewer"] == "곽태성"
    assert packet["target_distribution"] == {
        "lookup": 4,
        "screen": 5,
        "rank": 4,
        "compare": 3,
        "aggregate": 2,
        "cross_product": 2,
        "clarification": 1,
        "quality": 3,
    }
    candidates = cast(list[dict[str, str]], packet["candidates"])
    assert len(candidates) == 24
    assert candidates[0]["candidate_id"] == "CQ-001-LOOKUP-001"
    assert candidates[-1]["candidate_id"] == "CQ-001-QUALITY-003"
    assert all(
        set(candidate) == {"candidate_id", "category", "question"} for candidate in candidates
    )

    request, request_id = client.requests[0]
    assert request_id == "finproof-canonical-question-candidates-001"
    assert request.model_name == "HCX-007"
    assert request.seed == 17
    assert request.max_completion_tokens >= 8_192
    assert request.response_schema_json is None
    assert "responseFormat" not in request.to_payload()
    assert "thinking" not in request.to_payload()
    prompt = "\n".join(message.content for message in request.messages)
    assert all(
        phrase in prompt
        for phrase in (
            "정답 데이터가 아니다",
            "국내채권",
            "국내 ETF/ETN",
            "해외 ETF/ETN",
            "공모펀드",
            "일반적인 ETF 질문은 ETN을 제외",
            "미래 수익률 예측",
            "단정적인 투자 추천",
            "expected answer/result",
        )
    )


def _invalid_contents() -> tuple[str, ...]:
    wrong_distribution = json.loads(_content())
    wrong_distribution["candidates"][-1]["category"] = "lookup"
    duplicate = json.loads(_content())
    duplicate["candidates"][-1]["question"] = duplicate["candidates"][0]["question"]
    extra_candidate_field = json.loads(_content())
    extra_candidate_field["candidates"][0]["expected_result"] = {"product_id": "unsafe"}
    extra_root_field = json.loads(_content())
    extra_root_field["expected_answer"] = "unsafe"
    missing_candidate = json.loads(_content())
    missing_candidate["candidates"].pop()
    oversized_question = json.loads(_content())
    oversized_question["candidates"][0]["question"] = "가" * 4_001
    return tuple(
        json.dumps(value, ensure_ascii=False)
        for value in (
            wrong_distribution,
            duplicate,
            extra_candidate_field,
            extra_root_field,
            missing_candidate,
            oversized_question,
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("content", _invalid_contents())
async def test_generation_rejects_malformed_or_inexact_candidate_content(
    content: str,
) -> None:
    with pytest.raises(ValueError, match="candidate"):
        await generate_review_packet(
            _Client(content),
            generated_at=datetime(2026, 8, 24, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_generation_rejects_non_hcx_007_before_request() -> None:
    client = _Client(_content())

    with pytest.raises(ValueError, match="HCX-007"):
        await generate_review_packet(
            client,
            model_name="HCX-999",
            generated_at=datetime(2026, 8, 24, tzinfo=UTC),
        )

    assert client.requests == []


@pytest.mark.asyncio
async def test_packet_writer_validates_then_atomically_refuses_unsafe_targets(
    tmp_path: Path,
) -> None:
    packet = await generate_review_packet(
        _Client(_content()),
        generated_at=datetime(2026, 8, 24, tzinfo=UTC),
    )
    repository_root = tmp_path / "repository"
    output = repository_root / "review" / "batch-001.json"

    write_review_packet(output, packet, repository_root=repository_root)

    assert json.loads(output.read_text(encoding="utf-8")) == packet
    assert list(output.parent.glob(f".{output.name}.*.tmp")) == []
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        write_review_packet(output, packet, repository_root=repository_root)
    assert output.read_bytes() == original

    canonical_output = repository_root / "evaluation" / "canonical" / "batch.json"
    with pytest.raises(ValueError, match="canonical"):
        write_review_packet(canonical_output, packet, repository_root=repository_root)
    assert not canonical_output.exists()

    invalid_packet = deepcopy(packet)
    invalid_candidates = cast(list[dict[str, str]], invalid_packet["candidates"])
    invalid_candidates[0]["question"] = ""
    invalid_output = repository_root / "review" / "invalid.json"
    with pytest.raises(ValueError, match="question"):
        write_review_packet(invalid_output, invalid_packet, repository_root=repository_root)
    assert not invalid_output.exists()


@pytest.mark.asyncio
async def test_packet_writer_rejects_non_hcx_007_model(tmp_path: Path) -> None:
    packet = await generate_review_packet(
        _Client(_content()),
        generated_at=datetime(2026, 8, 24, tzinfo=UTC),
    )
    packet["model"] = "HCX-999"
    output = tmp_path / "review" / "batch.json"

    with pytest.raises(ValueError, match="HCX-007"):
        write_review_packet(output, packet, repository_root=tmp_path)

    assert not output.exists()


def test_cli_loads_hcx_secret_without_printing_or_persisting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    packet = asyncio.run(
        generate_review_packet(
            _Client(_content()),
            generated_at=datetime(2026, 8, 24, tzinfo=UTC),
        )
    )
    secret = "super-secret-hcx-key"  # noqa: S105 - sentinel verifies redaction.
    observed: dict[str, object] = {}

    async def fake_request(api_key: SecretStr) -> dict[str, object]:
        observed["api_key"] = api_key
        return packet

    monkeypatch.setattr(generator, "_request_with_hcx", fake_request)
    output = tmp_path / "review" / "batch.json"

    assert (
        generator.main(
            ["--output", str(output)],
            environ={"FINPROOF_HCX_API_KEY": secret},
            repository_root=tmp_path,
        )
        == 0
    )

    assert isinstance(observed["api_key"], SecretStr)
    assert json.loads(output.read_text(encoding="utf-8"))["model"] == "HCX-007"
    assert secret not in output.read_text(encoding="utf-8")
    assert secret not in capsys.readouterr().out

    with pytest.raises(SystemExit, match="FINPROOF_HCX_API_KEY"):
        generator.main(
            ["--output", str(tmp_path / "missing.json")],
            environ={},
            repository_root=tmp_path,
        )


def test_cli_rejects_model_override_before_hcx_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = False

    async def fake_request(api_key: SecretStr) -> dict[str, object]:
        nonlocal requested
        requested = True
        raise AssertionError("HCX must not be requested")

    monkeypatch.setattr(generator, "_request_with_hcx", fake_request)
    output = tmp_path / "review" / "batch.json"

    with pytest.raises(SystemExit):
        generator.main(
            ["--output", str(output), "--model", "HCX-999"],
            environ={"FINPROOF_HCX_API_KEY": "not-a-real-key"},
            repository_root=tmp_path,
        )

    assert requested is False
    assert not output.exists()
