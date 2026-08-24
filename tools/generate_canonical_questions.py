"""Generate one HCX-only packet of noncanonical question candidates."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from pydantic import SecretStr

from finproof.planner.hcx_client import HcxClient, create_hcx_http_client
from finproof.planner.models import HcxMessage, HcxRequest

BATCH_ID = "001"
PROVIDER = "naver-hyperclova-x"
DEFAULT_MODEL = "HCX-007"
SEED = 17
PROMPT_VERSION = "canonical-question-candidates-v1"
MAX_COMPLETION_TOKENS = 12_000
MAX_RESPONSE_BYTES = 128_000
TARGET_DISTRIBUTION = {
    "lookup": 4,
    "screen": 5,
    "rank": 4,
    "compare": 3,
    "aggregate": 2,
    "cross_product": 2,
    "clarification": 1,
    "quality": 3,
}
_PACKET_KEYS = {
    "batch_id",
    "provider",
    "model",
    "seed",
    "prompt_version",
    "prompt_sha256",
    "generated_at",
    "review_status",
    "reviewer",
    "target_distribution",
    "candidates",
}

_PROMPT = """당신은 FinProof 평가 질문 후보 작성자입니다.
생성물은 사람 검토 전의 질문 후보이며 정답 데이터가 아니다. ground truth로 취급하지 마십시오.
공식 2026-07-11 스냅샷의 네 데이터 계열인 국내채권, 국내 ETF/ETN, 해외 ETF/ETN,
공모펀드를 대상으로 자연스러운 한국어 질문을 작성하십시오.
공식 데이터와 FinProof 계약으로 지원 가능한 필드, 상태, 지표, 기간, 통화, 집계만 질문하십시오.
일반적인 ETF 질문은 ETN을 제외합니다.
미래 수익률 예측이나 단정적인 투자 추천을 요구하지 마십시오.
명확화 필요성과 데이터 품질 한계를 의도적으로 시험하는 질문은 해당 범주에 포함할 수 있습니다.
expected plan, expected answer/result, 상품 ID, 수치, 개수 또는 정답을 사실로 출력하지 마십시오.
응답은 JSON 객체 하나만 반환하고 다른 텍스트나 마크다운을 포함하지 마십시오.
루트 키는 candidates 하나뿐이며 각 항목의 키는 category와 question 두 개뿐입니다.
정확히 24개를 만들고 범주별 개수는 다음과 같습니다:
lookup 4, screen 5, rank 4, compare 3, aggregate 2, cross_product 2,
clarification 1, quality 3.
"""


class _Response(Protocol):
    message_content: str


class _Client(Protocol):
    async def generate(self, request: HcxRequest, request_id: str) -> _Response: ...


async def generate_review_packet(
    client: _Client,
    *,
    model_name: str = DEFAULT_MODEL,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Request, validate, and label one pending human-review packet."""
    if model_name != DEFAULT_MODEL:
        raise ValueError(f"model_name must be exactly {DEFAULT_MODEL}")
    request = HcxRequest.strict_json(
        model_name=model_name,
        messages=(
            HcxMessage(role="system", content=_PROMPT),
            HcxMessage(
                role="user",
                content="지정된 분포대로 한국어 질문 후보 24개를 JSON으로 생성하십시오.",
            ),
        ),
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        temperature=0.0,
        seed=SEED,
    )
    response = await client.generate(
        request,
        request_id="finproof-canonical-question-candidates-001",
    )
    candidates = _validate_candidates(response.message_content)
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("generated timestamp must be timezone-aware")
    return {
        "batch_id": BATCH_ID,
        "provider": PROVIDER,
        "model": model_name,
        "seed": SEED,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": sha256(_PROMPT.encode("utf-8")).hexdigest(),
        "generated_at": timestamp.astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "review_status": "pending_human_review",
        "reviewer": "곽태성",
        "target_distribution": dict(TARGET_DISTRIBUTION),
        "candidates": candidates,
    }


def _validate_candidates(content: str) -> list[dict[str, str]]:
    if not content or len(content.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("HCX candidate response is empty or oversized")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("HCX candidate response is not valid JSON") from exc
    if type(payload) is not dict or set(payload) != {"candidates"}:
        raise ValueError("HCX candidate response has an invalid root shape")
    raw_candidates = payload["candidates"]
    if type(raw_candidates) is not list or len(raw_candidates) != sum(TARGET_DISTRIBUTION.values()):
        raise ValueError("HCX candidate response has an invalid candidate count")

    grouped: dict[str, list[str]] = {category: [] for category in TARGET_DISTRIBUTION}
    seen_questions: set[str] = set()
    for raw in raw_candidates:
        if type(raw) is not dict or set(raw) != {"category", "question"}:
            raise ValueError("HCX candidate has an invalid shape")
        category = raw["category"]
        question = raw["question"]
        if type(category) is not str or category not in TARGET_DISTRIBUTION:
            raise ValueError("HCX candidate has an invalid category")
        if (
            type(question) is not str
            or question != question.strip()
            or not 1 <= len(question) <= 4_000
            or not any("가" <= character <= "힣" for character in question)
            or question in seen_questions
        ):
            raise ValueError("HCX candidate has an invalid or duplicate question")
        seen_questions.add(question)
        grouped[category].append(question)
    if {category: len(questions) for category, questions in grouped.items()} != (
        TARGET_DISTRIBUTION
    ):
        raise ValueError("HCX candidate distribution does not match the target")
    return [
        {
            "candidate_id": f"CQ-001-{category.upper()}-{index:03d}",
            "category": category,
            "question": question,
        }
        for category, category_questions in grouped.items()
        for index, question in enumerate(category_questions, 1)
    ]


def write_review_packet(
    output: Path,
    packet: dict[str, object],
    *,
    repository_root: Path,
) -> None:
    """Validate and atomically install one new noncanonical review packet."""
    _validate_packet(packet)
    _validate_output_path(output, repository_root=repository_root)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.pending.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(packet, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        output.hardlink_to(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_output_path(output: Path, *, repository_root: Path) -> None:
    resolved_output = output.resolve()
    canonical_root = (repository_root / "evaluation" / "canonical").resolve()
    if resolved_output.is_relative_to(canonical_root):
        raise ValueError("question candidates must not be written under canonical data")
    if output.suffix != ".json":
        raise ValueError("review packet output must use a .json suffix")
    if output.exists():
        raise FileExistsError(output)


def _validate_packet(packet: dict[str, object]) -> None:
    if type(packet) is not dict or set(packet) != _PACKET_KEYS:
        raise ValueError("review packet has an invalid shape")
    if packet["model"] != DEFAULT_MODEL:
        raise ValueError(f"review packet model must be exactly {DEFAULT_MODEL}")
    if (
        packet["batch_id"] != BATCH_ID
        or packet["provider"] != PROVIDER
        or packet["seed"] != SEED
        or packet["prompt_version"] != PROMPT_VERSION
        or packet["prompt_sha256"] != sha256(_PROMPT.encode("utf-8")).hexdigest()
        or packet["review_status"] != "pending_human_review"
        or packet["reviewer"] != "곽태성"
        or packet["target_distribution"] != TARGET_DISTRIBUTION
    ):
        raise ValueError("review packet metadata does not match the authoring contract")
    generated_at = packet["generated_at"]
    if type(generated_at) is not str or not generated_at.endswith("Z"):
        raise ValueError("review packet timestamp must be UTC")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("review packet timestamp is invalid") from exc

    candidates = packet["candidates"]
    if type(candidates) is not list:
        raise ValueError("review packet candidates must be a list")
    raw_candidates: list[dict[str, object]] = []
    for candidate in candidates:
        if type(candidate) is not dict or set(candidate) != {
            "candidate_id",
            "category",
            "question",
        }:
            raise ValueError("review packet candidate has an invalid shape")
        raw_candidates.append(
            {
                "category": candidate["category"],
                "question": candidate["question"],
            }
        )
    expected = _validate_candidates(json.dumps({"candidates": raw_candidates}, ensure_ascii=False))
    if candidates != expected:
        raise ValueError("review packet candidate IDs or ordering are invalid")


async def _request_with_hcx(
    api_key: SecretStr,
) -> dict[str, object]:
    async with create_hcx_http_client() as http_client:
        client = HcxClient(http_client=http_client, api_key=api_key)
        return await generate_review_packet(client)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
) -> int:
    """Generate a single pending-review packet at an explicit safe path."""
    parser = argparse.ArgumentParser(
        description="Generate HCX-only noncanonical question candidates."
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    root = repository_root or Path.cwd()
    _validate_output_path(args.output, repository_root=root)
    environment = os.environ if environ is None else environ
    raw_api_key = environment.get("FINPROOF_HCX_API_KEY")
    if raw_api_key is None or not raw_api_key.strip():
        raise SystemExit("FINPROOF_HCX_API_KEY is required")

    packet = asyncio.run(_request_with_hcx(SecretStr(raw_api_key)))
    write_review_packet(args.output, packet, repository_root=root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
