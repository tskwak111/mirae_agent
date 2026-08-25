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

from finproof.planner.hcx_client import HcxClient
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


def _content_with_question(index: int, question: str) -> str:
    content = json.loads(_batch_002_content())
    content["candidates"][index]["question"] = question
    return json.dumps(content, ensure_ascii=False)


def _batch_002_content() -> str:
    content = json.loads(_content())
    questions = content["candidates"]
    questions[4]["question"] = "매수가능수량이 양수인 국내채권을 찾아주세요."
    questions[20]["question"] = "수익률이 좋고 AUM이 큰 국내 ETF 5개를 알려주세요."
    questions[22]["question"] = (
        "AA- 이상 국내채권 수를 복수 신용등급과 등급 정책을 확인해 집계해주세요."
    )
    return json.dumps(content, ensure_ascii=False)


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


def test_authoring_timeout_extends_only_the_read_window() -> None:
    assert HcxClient._TIMEOUT.read == 15.0
    assert generator._AuthoringHcxClient._TIMEOUT.read == 60.0
    assert generator._AuthoringHcxClient._TIMEOUT.connect == 5.0
    assert generator._AuthoringHcxClient._TIMEOUT.write == 5.0
    assert generator._AuthoringHcxClient._TIMEOUT.pool == 5.0


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
    assert packet["prompt_version"] == "canonical-question-candidates-v4"
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
            "1~4 lookup",
            "22~24 quality",
            "출력 전 candidates 배열 길이가 24",
            "overseas_etf/overseas_etn: product_name",
            "lookup은 정확한 단일 상품 조회",
            "[검증된 상품명 또는 ID]",
            "거래량, 표면금리, 분배금, 레버리지",
            "해외 ETF/ETN 1일 수익률 전부 0",
            "슬롯별 의미, 식별자, 필드, 조건, 순서와 category를 바꾸지 마십시오",
            "1 lookup: 국내채권 KR101501DA16",
            "24 quality: 위험등급이 없는 공모펀드",
        )
    )


@pytest.mark.asyncio
async def test_hcx_generation_supports_the_frozen_batch_002_contract() -> None:
    client = _Client(_batch_002_content())

    packet = await generate_review_packet(
        client,
        batch_id="002",
        generated_at=datetime(2026, 8, 24, 12, 30, tzinfo=UTC),
    )

    assert packet["batch_id"] == "002"
    assert packet["model"] == "HCX-007"
    assert packet["seed"] == 29
    assert packet["prompt_version"] == "canonical-question-candidates-v5"
    candidates = cast(list[dict[str, str]], packet["candidates"])
    assert candidates[0]["candidate_id"] == "CQ-002-LOOKUP-001"
    assert candidates[-1]["candidate_id"] == "CQ-002-QUALITY-003"
    request, request_id = client.requests[0]
    assert request_id == "finproof-canonical-question-candidates-002"
    assert request.model_name == "HCX-007"
    assert request.seed == 29
    prompt = "\n".join(message.content for message in request.messages)
    batch_002_slots = (
        "1 lookup: 국내채권 KR350105G9C6의 신용등급과 매수가능수량 조회",
        "2 lookup: 국내 ETF KR7243880002의 연초이후 수익률과 AUM 조회",
        "3 lookup: 해외 ETF VOO의 AUM과 거래통화 조회",
        "4 lookup: 공모펀드 KR5129470010의 1년 수익률과 위험등급 조회",
        "5 screen: 매수수익률 4% 이상, 만기일이 2026-07-11 이후이고 매수가능수량이 양수인 국내채권",
        "6 screen: AUM 1조원 이상이고 판매 가능한 국내 ETF, ETN 제외",
        "7 screen: 총보수가 0% 초과 0.1% 이하인 해외 ETF",
        "8 screen: 1년 수익률 100% 이상이고 위험등급이 있는 공모펀드",
        "9 screen: 총보수 0.5% 이하이고 판매 가능한 국내 ETN(ETN 명시)",
        "10 rank: 현재 매수 가능한 국내채권 중 매수수익률 높은 5개",
        "11 rank: 국내 ETF AUM 큰 5개, ETN 제외",
        "12 rank: 거래통화 USD인 해외 ETF AUM 큰 5개",
        "13 rank: 거래통화 KRW인 공모펀드 AUM 큰 5개",
        "14 compare: 국내채권 KR350105G9C6와 KR350901G671의 매수가능수량 비교",
        "15 compare: 국내 ETF KR7243880002와 KR7494310006의 연초이후 수익률 비교",
        "16 compare: 공모펀드 KR5129470010와 KR5129470016의 1년 수익률 비교",
        "17 aggregate: 거래통화 USD인 해외 ETF 수 집계, ETN 제외",
        "18 aggregate: 국내 ETF 1년 수익률 평균, ETN 제외",
        "19 cross_product: 국내 ETF와 공모펀드의 3개월 수익률 상위 3개를 유형별 분리",
        "20 cross_product: 국내 ETF와 해외 ETF의 총보수 낮은 3개를 유형별 분리",
        (
            "21 clarification: 국내 ETF 중 수익률이 좋고 AUM이 큰 5개 요청. "
            "자연스러운 질문으로만 작성하고 추천이나 모호성 설명을 쓰지 마십시오. "
            "수익률 기간과 복합 우선순위는 질문에서 자연스럽게 생략하십시오."
        ),
        "22 quality: 국내 ETF 총보수 낮은 5개—기록된 0의 미검증 품질 경고 확인",
        "23 quality: AA- 이상 국내채권 수 집계—미평가 채권 제외, 복수 신용등급과 등급 정책 확인",
        "24 quality: 판매 가능한 해외 ETF 5개—검증된 매수 가능 여부 제한 확인",
    )
    assert [prompt.index(slot) for slot in batch_002_slots] == sorted(
        prompt.index(slot) for slot in batch_002_slots
    )

    with pytest.raises(ValueError, match="batch_id"):
        await generate_review_packet(client, batch_id="999")
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_hcx_generation_supports_the_frozen_batch_003_contract() -> None:
    client = _Client(_content())

    packet = await generate_review_packet(
        client,
        batch_id="003",
        generated_at=datetime(2026, 8, 25, 12, 30, tzinfo=UTC),
    )

    assert packet["batch_id"] == "003"
    assert packet["model"] == "HCX-007"
    assert packet["seed"] == 41
    assert packet["prompt_version"] == "canonical-question-candidates-v6"
    assert packet["review_status"] == "pending_human_review"
    assert packet["reviewer"] == "곽태성"
    candidates = cast(list[dict[str, str]], packet["candidates"])
    assert [candidate["candidate_id"] for candidate in candidates] == [
        f"CQ-003-{index:03d}" for index in range(1, 25)
    ]
    request, request_id = client.requests[0]
    assert request_id == "finproof-canonical-question-candidates-003"
    assert request.model_name == "HCX-007"
    assert request.seed == 41
    prompt = request.messages[0].content
    batch_003_slots = (
        "1 lookup: 국내채권 KR353601DE34의 매수수익률과 잔존일수 조회",
        "2 lookup: 국내 ETN KRG520000826의 3개월 수익률과 연초이후 수익률 조회",
        "3 lookup: 해외 ETN NRGD.K의 총보수와 AUM 조회",
        "4 lookup: 공모펀드 KR5174430032의 3년 수익률과 위험등급 조회",
        (
            "5 screen: 매수수익률 3% 이상, 만기일이 2026-07-11 이후이고 "
            "매수가능수량이 1천만 이상인 국내채권"
        ),
        "6 screen: 6개월 수익률 50% 이상이고 판매 가능한 국내 ETF, ETN 제외",
        "7 screen: 투자지역이 미국이고 총보수 0.15% 이하인 해외 ETF, ETN 제외",
        "8 screen: 3년 수익률 50% 이상이고 위험등급이 낮은 위험인 공모펀드",
        "9 screen: 3개월 수익률 10% 이상이고 판매 가능한 국내 ETN, ETN 명시",
        (
            "10 rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권 중 "
            "매수가능수량 상위 5개"
        ),
        "11 rank: 국내 ETF 6개월 수익률 상위 5개, ETN 제외",
        "12 rank: 거래통화 USD인 해외 ETN AUM 상위 5개, ETN 명시",
        "13 rank: 공모펀드 3년 수익률 상위 5개",
        "14 compare: 국내채권 KR353601DE34와 KR354301GB84의 매수수익률 비교",
        "15 compare: 국내 ETN KRG520000826와 KRG530001202의 3개월 수익률 비교",
        "16 compare: 공모펀드 KR5174430032와 KR5114450497의 3년 수익률 비교",
        (
            "17 aggregate: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권의 "
            "매수수익률 평균"
        ),
        "18 aggregate: 거래통화 USD인 해외 ETN의 AUM 합계, ETN 명시",
        "19 cross_product: 국내 ETF와 공모펀드의 6개월 수익률 상위 3개를 유형별 분리",
        "20 cross_product: 국내 ETN과 해외 ETN의 AUM 상위 3개를 통화별·유형별 분리",
        (
            "21 clarification: 위험이 낮고 장기 수익률이 좋은 공모펀드 5개 요청. "
            "자연스러운 질문으로만 작성하고 추천·모호성 설명을 쓰지 않으며, "
            "수익률 기간과 복합 우선순위는 질문에서 생략"
        ),
        (
            "22 quality: 매수가능수량이 양수로 기록된 국내채권과 "
            "2026-07-11 기준 만기 경과를 제외한 매수 가능 후보 수를 각각 집계"
        ),
        (
            "23 quality: 해외 ETN 총보수 낮은 5개에서 기록된 0%와 0보다 큰 값을 구분하고, "
            "기록된 0%가 실제 무보수인지 미검증임을 경고"
        ),
        (
            "24 quality: 위험등급별 공모펀드 수를 itm_no 상품번호 기준으로 중복 없이 집계하고 "
            "속성 행 수로 세지 않음을 확인"
        ),
    )
    assert [prompt.index(slot) for slot in batch_003_slots] == sorted(
        prompt.index(slot) for slot in batch_003_slots
    )


def test_batch_002_rejects_v1_screen_question_without_positive_quantity() -> None:
    packet = json.loads(
        (
            Path(__file__).parents[3]
            / "evaluation/review_batches/batch-002-candidates-v1-rejected.json"
        ).read_text(encoding="utf-8")
    )
    content = json.dumps(
        {
            "candidates": [
                {"category": candidate["category"], "question": candidate["question"]}
                for candidate in packet["candidates"]
            ]
        },
        ensure_ascii=False,
    )

    with pytest.raises(ValueError, match="positive buyable quantity"):
        generator._validate_candidates(content, batch_id="002")


def test_batch_002_rejects_clarification_recommendation_or_stated_ambiguity() -> None:
    content = _content_with_question(
        20,
        "수익률이 우수하면서 AUM이 큰 국내 ETF 5개를 추천해주세요. 기간이 명시되지 않았습니다.",
    )

    with pytest.raises(ValueError, match="natural clarification"):
        generator._validate_candidates(content, batch_id="002")


def test_batch_002_rejects_quality_question_without_multiple_rating_policy() -> None:
    content = _content_with_question(
        22,
        "AA- 이상의 신용등급을 가진 국내채권 수를 집계하고 미평가 채권은 제외해주세요.",
    )

    with pytest.raises(ValueError, match="multiple-rating policy"):
        generator._validate_candidates(content, batch_id="002")


@pytest.mark.asyncio
async def test_generation_accepts_one_json_code_fence() -> None:
    packet = await generate_review_packet(
        _Client(f"\n```json\n{_content()}\n```\n"),
        generated_at=datetime(2026, 8, 24, tzinfo=UTC),
    )

    assert len(cast(list[object], packet["candidates"])) == 24


@pytest.mark.asyncio
async def test_generation_accepts_opening_json_fence_without_closing_fence() -> None:
    packet = await generate_review_packet(
        _Client(f"```json\n{_content()}"),
        generated_at=datetime(2026, 8, 24, tzinfo=UTC),
    )

    assert len(cast(list[object], packet["candidates"])) == 24


@pytest.mark.asyncio
async def test_generation_accepts_fenced_json_before_provider_commentary() -> None:
    packet = await generate_review_packet(
        _Client(f"```json\n{_content()}\n``` \n\n각 카테고리별 슬롯 수는 확인했습니다."),
        generated_at=datetime(2026, 8, 24, tzinfo=UTC),
    )

    assert len(cast(list[object], packet["candidates"])) == 24


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
    return (
        *(
            json.dumps(value, ensure_ascii=False)
            for value in (
                wrong_distribution,
                duplicate,
                extra_candidate_field,
                extra_root_field,
                missing_candidate,
                oversized_question,
            )
        ),
        f"설명문\n{_content()}",
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

    async def fake_request(api_key: SecretStr, *, batch_id: str) -> dict[str, object]:
        observed["api_key"] = api_key
        observed["batch_id"] = batch_id
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
    assert observed["batch_id"] == "001"
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


def test_cli_passes_batch_002_to_hcx_and_writes_batch_002_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = asyncio.run(
        generate_review_packet(
            _Client(_batch_002_content()),
            batch_id="002",
            generated_at=datetime(2026, 8, 24, tzinfo=UTC),
        )
    )
    observed: dict[str, object] = {}

    async def fake_request(api_key: SecretStr, *, batch_id: str) -> dict[str, object]:
        observed["api_key"] = api_key
        observed["batch_id"] = batch_id
        return packet

    monkeypatch.setattr(generator, "_request_with_hcx", fake_request)
    output = tmp_path / "review" / "batch-002.json"

    assert (
        generator.main(
            ["--output", str(output), "--batch-id", "002"],
            environ={"FINPROOF_HCX_API_KEY": "not-a-real-key"},
            repository_root=tmp_path,
        )
        == 0
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(observed["api_key"], SecretStr)
    assert observed["batch_id"] == "002"
    assert written["batch_id"] == "002"
    assert written["seed"] == 29
    assert written["prompt_version"] == "canonical-question-candidates-v5"
    assert written["candidates"][0]["candidate_id"] == "CQ-002-LOOKUP-001"
    assert written["candidates"][-1]["candidate_id"] == "CQ-002-QUALITY-003"


def test_cli_passes_batch_003_to_hcx_and_writes_batch_003_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    async def fake_request(api_key: SecretStr, *, batch_id: str) -> dict[str, object]:
        observed["api_key"] = api_key
        observed["batch_id"] = batch_id
        return await generate_review_packet(
            _Client(_content()),
            batch_id=batch_id,
            generated_at=datetime(2026, 8, 25, tzinfo=UTC),
        )

    monkeypatch.setattr(generator, "_request_with_hcx", fake_request)
    output = tmp_path / "review" / "batch-003.json"

    assert (
        generator.main(
            ["--output", str(output), "--batch-id", "003"],
            environ={"FINPROOF_HCX_API_KEY": "not-a-real-key"},
            repository_root=tmp_path,
        )
        == 0
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(observed["api_key"], SecretStr)
    assert observed["batch_id"] == "003"
    assert written["batch_id"] == "003"
    assert written["seed"] == 41
    assert written["prompt_version"] == "canonical-question-candidates-v6"
    assert [candidate["candidate_id"] for candidate in written["candidates"]] == [
        f"CQ-003-{index:03d}" for index in range(1, 25)
    ]
