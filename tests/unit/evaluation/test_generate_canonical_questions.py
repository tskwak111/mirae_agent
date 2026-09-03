# ruff: noqa: E501 - prompt slot literals mirror the independently reviewed contract.

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
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
from finproof.service.limits import RequestDeadline

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

_NEW_BATCH_CASES = (
    (
        "006",
        77,
        "canonical-question-candidates-v9",
        "finproof-canonical-question-candidates-006",
        (
            "lookup: 국내채권 KR101501DB72의 신용등급과 매수수익률 조회",
            "lookup: 국내 ETF KR70000D0009의 3개월 수익률과 판매상태 조회",
            "lookup: 해외 ETF AAAA.K의 1일 수익률과 투자지역 조회",
            "lookup: 공모펀드 KR5010101401의 1주 수익률과 미래에셋 판매상태 조회",
            "screen: 2026-07-11 이후부터 2027-07-11까지 만기이고 매수가능수량이 양수인 국내채권",
            "screen: 3개월 수익률이 0% 미만이고 판매 가능한 국내 ETF, ETN 제외",
            "screen: AUM이 5천만 USD 이상이고 총보수가 0.25% 이하인 해외 ETF, ETN 제외",
            "screen: 1주 수익률이 1% 이상이고 거래통화가 KRW인 공모펀드",
            "screen: 6개월 수익률이 0% 초과이고 판매 가능한 국내 ETN, ETN 명시",
            "rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권 중 만기일이 빠른 5개",
            "rank: 국내 ETF 3개월 수익률 높은 5개, ETN 제외",
            "rank: 해외 ETF 1일 수익률 낮은 5개, ETN 제외",
            "rank: 공모펀드 1주 수익률 높은 5개",
            "compare: 국내채권 KR101501DA16과 KR350105G9C6의 만기일 비교",
            "compare: 국내 ETF KR7243880002와 KR7494310006의 3개월 수익률 비교",
            "compare: 공모펀드 KR5129470010과 KR5129470016의 3개월 수익률 비교",
            "aggregate: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권의 매수수익률 최솟값",
            "aggregate: 공모펀드 1주 수익률 최댓값",
            "cross_product: 국내 ETF와 공모펀드의 1개월 수익률 하위 4개를 유형별 분리",
            "cross_product: 국내 ETF와 해외 ETF의 총보수 높은 4개를 유형별 분리",
            "clarification: 수익률이 안정적이고 규모가 큰 ETF 5개 요청에서 국내·해외 구분, 수익률 기간과 복합 우선순위 생략",
            "quality: 매수가능수량이 양수로 기록된 국내채권의 원천 수량 합계와 2026-07-11 기준 만기 검증 후 수량 합계를 구분",
            "quality: 해외 ETF 1일 수익률 낮은 5개의 기록된 0 공동순위와 동률 정책 확인",
            "quality: 1주 수익률이 없는 공모펀드 수를 itm_no 상품번호 기준으로 중복 없이 집계",
        ),
    ),
    (
        "007",
        89,
        "canonical-question-candidates-v10",
        "finproof-canonical-question-candidates-007",
        (
            "lookup: 국내채권 KR101501DD88의 만기일과 매수가능수량 조회",
            "lookup: 국내 ETN KRG500000614의 총보수와 1년 수익률 조회",
            "lookup: 해외 ETN AIQD.K의 AUM과 1일 수익률 조회",
            "lookup: 공모펀드 KR5010101402의 6개월 수익률과 위험등급 조회",
            "screen: 신용등급 A+ 이상이고 잔존일수가 365일 이하이며 매수가능수량이 양수인 국내채권",
            "screen: 1년 수익률이 10% 이상이고 판매 가능한 국내 ETF, ETN 제외",
            "screen: 거래통화가 USD이고 총보수가 0.3% 이하인 해외 ETN, ETN 명시",
            "screen: 6개월 수익률이 0% 미만이고 위험등급이 있는 공모펀드",
            "screen: 추적오차가 0%이고 판매 가능한 국내 ETN, ETN 명시",
            "rank: 2026-07-11 기준 매수 가능한 국내채권 중 신용등급 높은 5개",
            "rank: 국내 ETF 1년 수익률 낮은 5개, ETN 제외",
            "rank: 해외 ETN AUM 작은 5개, ETN 명시",
            "rank: 공모펀드 6개월 수익률 높은 5개",
            "compare: 국내채권 KR353601DE34와 KR354301GB84의 매수가능수량 비교",
            "compare: 해외 ETF VOO와 EES의 AUM 비교",
            "compare: 공모펀드 KR5174430032와 KR5114450497의 5년 수익률 비교",
            "aggregate: 국내 ETF 총보수 최솟값, ETN 제외",
            "aggregate: 공모펀드 6개월 수익률 평균",
            "cross_product: 판매 가능한 국내 ETF와 공모펀드의 1년 수익률 상위 4개를 유형별 분리",
            "cross_product: 국내 ETF와 해외 ETF의 AUM 평균을 통화별·유형별 분리",
            "clarification: 성과가 좋고 총보수가 낮은 해외 ETF 5개 요청에서 수익률 기간과 복합 우선순위 생략",
            "quality: 해외 ETF 총보수 낮은 5개에서 기록된 0%와 양수 값을 분리하고 0% 미검증 경고",
            "quality: 공모펀드의 원천 판매상태와 미래에셋 판매상태를 itm_no 기준으로 표시하고 검증된 매수 가능 상태로 해석하지 않음",
            "quality: 판매상태가 누락된 해외 ETN 수를 원천 기록 기준으로 집계하고 검증된 매수 가능 여부의 부재를 경고",
        ),
    ),
    (
        "008",
        101,
        "canonical-question-candidates-v11",
        "finproof-canonical-question-candidates-008",
        (
            "lookup: 국내채권 KR101501DDA1의 잔존일수와 거래통화 조회",
            "lookup: 국내 ETF KR70000H0005의 6개월 수익률과 총보수 조회",
            "lookup: 해외 ETF AAAC.K의 원천 판매상태와 거래통화 조회",
            "lookup: 공모펀드 KR5010101404의 2년 수익률과 3년 수익률 조회",
            "screen: 매수수익률이 3% 이하이고 2026-07-11 기준 만기가 지나지 않았으며 매수가능수량이 양수인 국내채권",
            "screen: 추적오차가 0% 초과인 국내 ETF, ETN 제외",
            "screen: 1일 수익률이 0%이고 총보수가 0% 초과인 해외 ETF, ETN 제외",
            "screen: 2년 수익률이 20% 이상이고 미래에셋 판매 가능한 공모펀드",
            "screen: 1년 수익률이 0% 미만인 국내 ETN, ETN 명시",
            "rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권 중 매수가능수량 작은 5개",
            "rank: 국내 ETF 총보수 높은 5개, ETN 제외",
            "rank: 해외 ETF 1일 수익률 높은 7개, ETN 제외",
            "rank: 공모펀드 2년 수익률 낮은 5개",
            "compare: 국내채권 KR101501DD13과 KR101501DD47의 매수수익률 비교",
            "compare: 국내 ETN KRG520000826와 KRG530001202의 연초이후 수익률 비교",
            "compare: 공모펀드 KR5010101702와 KR5010101714의 3년 수익률 비교",
            "aggregate: 거래통화가 USD인 해외 ETF의 AUM 최댓값, ETN 제외",
            "aggregate: 공모펀드 2년 수익률 최솟값",
            "cross_product: 국내 ETF와 공모펀드의 6개월 수익률 하위 4개를 유형별 분리",
            "cross_product: 국내 ETN과 해외 ETN의 AUM 하위 4개를 통화별·유형별 분리",
            "clarification: 만기가 짧고 매수수익률이 높은 국내채권 5개 요청에서 복합 우선순위 생략",
            "quality: 국내 ETF 추적오차 높은 5개가 기록된 0%로 공동순위인지 확인하고 동률 정책 표시",
            "quality: 2년 수익률이 없는 공모펀드 수를 fund_item grain의 itm_no 기준으로 집계",
            "quality: 판매 가능한 해외 ETF 요청에서 원천 판매상태만 표시하고 검증된 매수 가능 여부는 지원하지 않음을 경고",
        ),
    ),
    (
        "009",
        113,
        "canonical-question-candidates-v12",
        "finproof-canonical-question-candidates-009",
        (
            "lookup: 국내채권 KR101501DE61의 상품명과 신용등급 조회",
            "lookup: 국내 ETN KRG500000630의 3개월 수익률과 추적오차 조회",
            "lookup: 해외 ETN AIQU.K의 총보수와 원천 판매상태 조회",
            "lookup: 공모펀드 KR5010101405의 3개월 수익률과 5년 수익률 조회",
            "screen: 신용등급 AAA이고 잔존일수가 180일 이하이며 매수가능수량이 양수인 국내채권",
            "screen: 3개월 수익률이 -5% 이하이고 판매 가능한 국내 ETF, ETN 제외",
            "screen: 투자지역이 미국이고 1일 수익률이 0% 이하인 해외 ETF, ETN 제외",
            "screen: 3개월 수익률이 3% 이상이고 미래에셋 판매 가능한 공모펀드",
            "screen: AUM이 50억원 이하이고 판매 가능한 국내 ETN, ETN 명시",
            "rank: 신용등급 AAA이고 2026-07-11 기준 매수 가능한 국내채권 중 만기일이 늦은 7개",
            "rank: 국내 ETF 1개월 수익률 높은 7개, ETN 제외",
            "rank: 해외 ETN 총보수 낮은 7개, ETN 명시",
            "rank: 공모펀드 5년 수익률 낮은 5개",
            "compare: 국내채권 KR350105G9C6와 KR350901G671의 만기일 비교",
            "compare: 해외 ETN NRGD.K와 AIQD.K의 총보수 비교",
            "compare: 공모펀드 KR5114420158과 KR5138490078의 1년 수익률 비교",
            "aggregate: 국내 ETF AUM 평균, ETN 제외",
            "aggregate: 2026-07-11 기준 매수 가능한 국내채권의 매수가능수량 최댓값",
            "cross_product: 판매 가능한 국내 ETF와 미래에셋 판매 가능한 공모펀드의 3개월 수익률 상위 4개를 유형별 분리",
            "cross_product: 국내채권은 매수수익률 상위 4개, 국내 ETF는 연초이후 수익률 상위 4개로 유형별 분리",
            "clarification: 신용등급이 높고 만기가 적당한 국내채권 요청에서 만기 범위와 복합 우선순위 생략",
            "quality: 복수 신용등급 국내채권을 높은 등급 순으로 볼 때 미평가 제외와 등급 정책 표시",
            "quality: 총보수가 없는 국내 ETF를 순위에서 제외하면서 누락값 수와 제외 정책 표시",
            "quality: 공모펀드의 원천 판매상태와 미래에셋 판매상태가 다른 itm_no 수를 표시하고 검증된 상태로 추론하지 않음",
        ),
    ),
    (
        "010",
        125,
        "canonical-question-candidates-v13",
        "finproof-canonical-question-candidates-010",
        (
            "lookup: 국내채권 KR101501DE79의 만기일과 매수수익률 조회",
            "lookup: 국내 ETF KR70000J0003의 연초이후 수익률과 추적오차 조회",
            "lookup: 해외 ETF AAAD.K의 AUM과 총보수 조회",
            "lookup: 공모펀드 KR5010101501의 18개월 수익률과 5년 수익률 조회",
            "screen: 매수수익률이 4% 이상이고 잔존일수가 730일 이상이며 매수가능수량이 양수인 국내채권",
            "screen: 6개월 수익률이 0% 이하이고 판매 가능한 국내 ETF, ETN 제외",
            "screen: AUM이 1억 USD 이상인 해외 ETN, ETN 명시",
            "screen: 18개월 수익률이 0% 미만이고 위험등급이 있는 공모펀드",
            "screen: 총보수가 0% 초과이고 연초이후 수익률이 0% 초과인 국내 ETN, ETN 명시",
            "rank: 잔존일수가 730일 이상이고 2026-07-11 기준 매수 가능한 국내채권 중 매수수익률 높은 7개",
            "rank: 국내 ETF 연초이후 수익률 낮은 7개, ETN 제외",
            "rank: 해외 ETF 총보수 높은 7개, ETN 제외",
            "rank: 공모펀드 18개월 수익률 낮은 7개",
            "compare: 국내채권 KR101501DA16과 KR101501DD13의 신용등급 비교",
            "compare: 국내 ETF KR7305080004와 KR7371160003의 추적오차 비교",
            "compare: 공모펀드 KR5129470010과 KR5129470016의 2년 수익률 비교",
            "aggregate: 거래통화가 USD인 해외 ETN의 AUM 평균, ETN 명시",
            "aggregate: 공모펀드 18개월 수익률 최댓값",
            "cross_product: 국내 ETF와 공모펀드의 1개월 수익률 평균을 유형별 분리",
            "cross_product: 국내 ETF와 해외 ETF의 AUM 합계를 통화별·유형별 분리",
            "clarification: 단기와 장기 수익률이 모두 좋은 공모펀드 요청에서 두 기간과 복합 우선순위 생략",
            "quality: 5년 수익률이 없는 공모펀드 수를 itm_no 상품번호 기준으로 집계하고 속성 행 수 제외",
            "quality: 해외 ETF AUM 평균 집계에서 기록된 0과 누락값을 분리하고 집계 정책 표시",
            "quality: 국내 ETF의 원천 판매상태와 2026-07-11 기준 검증된 판매 가능 상태의 차이 표시",
        ),
    ),
    (
        "011",
        137,
        "canonical-question-candidates-v14",
        "finproof-canonical-question-candidates-011",
        (
            "lookup: 국내채권 KR101501DE95의 매수가능수량과 신용등급 조회",
            "lookup: 국내 ETN KRG500000671의 6개월 수익률과 AUM 조회",
            "lookup: 해외 ETN AMJB.K의 1일 수익률과 총보수 조회",
            "lookup: 공모펀드 KR5010101802의 1개월 수익률과 1년 수익률 조회",
            "screen: 신용등급 AA+ 이상이고 잔존일수가 180일 이상이며 매수가능수량이 양수인 국내채권",
            "screen: AUM이 1천억원 미만이고 판매 가능한 국내 ETF, ETN 제외",
            "screen: 총보수가 1% 이상인 해외 ETF, ETN 제외",
            "screen: 거래통화가 USD이고 1년 수익률이 0% 이상 10% 이하인 공모펀드",
            "screen: 3개월 수익률이 0% 미만이고 총보수가 0% 초과인 국내 ETN, ETN 명시",
            "rank: 신용등급 AA+ 이상이고 2026-07-11 기준 매수 가능한 국내채권 중 매수수익률 높은 7개",
            "rank: 국내 ETN AUM 큰 7개, ETN 명시",
            "rank: 거래통화가 USD인 해외 ETF AUM 작은 7개, ETN 제외",
            "rank: 공모펀드 1개월 수익률 낮은 7개",
            "compare: 국내채권 KR353601DE34와 KR354301GB84의 잔존일수 비교",
            "compare: 해외 ETF AAA와 AAEQ.O의 총보수 비교",
            "compare: 공모펀드 KR5174430032와 KR5114450497의 1개월 수익률 비교",
            "aggregate: 판매 가능한 국내 ETN 수 집계, ETN 명시",
            "aggregate: 거래통화가 KRW인 공모펀드의 AUM 합계",
            "cross_product: 국내채권은 매수가능수량 상위 4개, 공모펀드는 AUM 상위 4개로 유형별 분리",
            "cross_product: 국내 ETN과 해외 ETN의 총보수 높은 4개를 유형별 분리",
            "clarification: 현재 살 수 있고 수익률이 좋은 ETF 요청에서 국내·해외, 수익률 기간과 우선순위 생략",
            "quality: 매수가능수량이 0으로 기록된 국내채권을 표시하되 매수 가능 필터와 순위에서는 제외하고 경고",
            "quality: 해외 ETF AUM 낮은 순위에서 기록된 0과 누락값 및 동률을 분리",
            "quality: 원천 판매상태가 누락된 공모펀드 수를 itm_no 기준으로 집계하고 검증된 매수 가능 상태를 추론하지 않음",
        ),
    ),
)


def _expected_new_prompt(slots: tuple[str, ...]) -> str:
    numbered_slots = "\n".join(f"{index} {slot}" for index, slot in enumerate(slots, start=1))
    return f"""당신은 FinProof 평가 질문 후보 작성자입니다.
생성물은 사람 검토 전의 질문 후보이며 정답 데이터가 아니다. ground truth로 취급하지 마십시오.
공식 2026-07-11 스냅샷의 국내채권, 국내 ETF/ETN, 해외 ETF/ETN, 공모펀드만 대상으로
자연스러운 한국어 질문을 작성하십시오. 공식 데이터와 FinProof 계약으로 지원 가능한
필드, 상태, 지표, 기간, 통화, 집계만 질문하십시오.
일반적인 ETF 질문은 ETN을 제외합니다. ETN을 명시한 질문만 ETN을 포함합니다.
미래 수익률 예측, 단정적인 투자 추천, 실시간 값, 가족형 펀드 추론을 요구하지 마십시오.
허용 필드는 아래 목록으로 닫혀 있습니다:
- domestic_bond: product_name, product_id, currency, buyable_quantity, maturity_date,
  remaining_days_at_as_of, credit_rating, buy_yield
- domestic_etf/domestic_etn: product_name, product_id, asset_type, region, currency,
  total_fee, aum, tracking_error, return_1m, return_3m, return_6m, return_1y,
  return_ytd, saleable
- overseas_etf/overseas_etn: product_name, product_id, asset_type, region, currency,
  total_fee, aum, return_1d, saleable
- public_fund: product_name, product_id, region, currency, aum, return_1w, return_1m,
  return_3m, return_6m, return_18m, return_1y, return_2y, return_3y, return_5y,
  risk_grade, saleable, mirae_saleable
집계는 count 또는 허용 필드의 min/max/avg만 사용하고, sum은 aum과 buyable_quantity에만 사용하십시오.
공모펀드 검색·비교·순위·집계는 itm_no의 fund_item grain을 사용하고 속성 행을 상품으로 세지 마십시오.
검증된 매수 가능 상태는 국내채권과 국내 ETF/ETN에만 적용하며 해외 상품과 공모펀드의
원천 판매상태를 검증된 상태로 바꾸지 마십시오. 통화가 다른 AUM은 고정 환율 없이 통합 순위를 만들지 마십시오.
아래 24개 슬롯을 각각 자연스러운 한국어 질문 하나로만 표현하십시오.
슬롯별 식별자, 필드/지표, 임계값, 날짜, 상품 유형, 집계, 순서와 category를 바꾸지 마십시오:
{numbered_slots}
슬롯에 명시된 식별자와 질문 조건 수치 외에는 expected plan, expected answer/result,
상품 ID, 값, 결과 개수 또는 정답을 사실로 출력하지 마십시오.
응답은 JSON 객체 하나만 반환하고 다른 텍스트나 마크다운을 포함하지 마십시오.
루트 키는 candidates 하나뿐이며 각 항목의 키는 category와 question 두 개뿐입니다.
정확히 24개를 만들고 범주별 개수는 다음과 같습니다:
lookup 4, screen 5, rank 4, compare 3, aggregate 2, cross_product 2,
clarification 1, quality 3.
배열 슬롯은 1~4 lookup, 5~9 screen, 10~13 rank, 14~16 compare,
17~18 aggregate, 19~20 cross_product, 21 clarification, 22~24 quality 순서로 고정하십시오.
출력 전 candidates 배열 길이가 24이고 각 슬롯의 category가 위 구간과 일치하는지 확인하십시오.
"""


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
        self.deadlines: list[RequestDeadline] = []

    async def generate(
        self, request: HcxRequest, request_id: str, *, deadline: RequestDeadline
    ) -> _Response:
        self.requests.append((request, request_id))
        self.deadlines.append(deadline)
        return _Response(self._content)


def test_authoring_timeout_extends_only_the_read_window() -> None:
    assert HcxClient._TIMEOUT.read == 15.0
    assert generator._AuthoringHcxClient._TIMEOUT.read == 60.0
    assert generator._AuthoringHcxClient._TIMEOUT.connect == 5.0
    assert generator._AuthoringHcxClient._TIMEOUT.write == 5.0
    assert generator._AuthoringHcxClient._TIMEOUT.pool == 5.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("batch_id", "seed", "prompt_version", "request_id", "slots"),
    _NEW_BATCH_CASES,
)
async def test_batches_006_011_emit_exact_pending_review_contracts(
    batch_id: str,
    seed: int,
    prompt_version: str,
    request_id: str,
    slots: tuple[str, ...],
) -> None:
    client = _Client(_content())
    expected_prompt = _expected_new_prompt(slots)

    packet = await generate_review_packet(
        client,
        batch_id=batch_id,
        generated_at=datetime(2026, 8, 26, 12, 30, tzinfo=UTC),
    )

    assert packet["batch_id"] == batch_id
    assert packet["provider"] == "naver-hyperclova-x"
    assert packet["model"] == "HCX-007"
    assert packet["seed"] == seed
    assert packet["prompt_version"] == prompt_version
    assert packet["prompt_sha256"] == sha256(expected_prompt.encode("utf-8")).hexdigest()
    assert packet["review_status"] == "pending_human_review"
    assert packet["reviewer"] == "곽태성"
    candidates = cast(list[dict[str, str]], packet["candidates"])
    assert [candidate["candidate_id"] for candidate in candidates] == [
        f"CQ-{batch_id}-{index:03d}" for index in range(1, 25)
    ]
    request, observed_request_id = client.requests[0]
    assert observed_request_id == request_id
    assert type(client.deadlines[0]) is RequestDeadline
    assert request.seed == seed
    assert request.temperature == 0.0
    assert request.messages[0].content == expected_prompt


@pytest.mark.parametrize("batch_id", [case[0] for case in _NEW_BATCH_CASES])
def test_batches_006_011_cli_writes_selected_packet(
    batch_id: str,
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
            generated_at=datetime(2026, 8, 26, tzinfo=UTC),
        )

    monkeypatch.setattr(generator, "_request_with_hcx", fake_request)
    output = tmp_path / "review" / f"batch-{batch_id}.json"

    assert (
        generator.main(
            ["--output", str(output), "--batch-id", batch_id],
            environ={"FINPROOF_HCX_API_KEY": "not-a-real-key"},
            repository_root=tmp_path,
        )
        == 0
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(observed["api_key"], SecretStr)
    assert observed["batch_id"] == batch_id
    assert written["batch_id"] == batch_id
    assert [candidate["candidate_id"] for candidate in written["candidates"]] == [
        f"CQ-{batch_id}-{index:03d}" for index in range(1, 25)
    ]


@pytest.mark.parametrize("batch_id", [case[0] for case in _NEW_BATCH_CASES])
def test_batches_006_011_reject_misordered_raw_categories(batch_id: str) -> None:
    content = json.loads(_content())
    candidates = content["candidates"]
    candidates[0]["category"], candidates[4]["category"] = (
        candidates[4]["category"],
        candidates[0]["category"],
    )

    with pytest.raises(ValueError, match="candidate order"):
        generator._validate_candidates(json.dumps(content, ensure_ascii=False), batch_id=batch_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("batch_id", "seed", "prompt_version", "request_id", "first_id", "last_id", "prompt_hash"),
    [
        (
            "001",
            17,
            "canonical-question-candidates-v4",
            "finproof-canonical-question-candidates-001",
            "CQ-001-LOOKUP-001",
            "CQ-001-QUALITY-003",
            "658fd6e181b66ad1e10f96e0e788a56e879ab0c4d7c666bd33580a7ab31ed8ca",
        ),
        (
            "002",
            29,
            "canonical-question-candidates-v5",
            "finproof-canonical-question-candidates-002",
            "CQ-002-LOOKUP-001",
            "CQ-002-QUALITY-003",
            "81a872569d8c7dd0fe7cb652890ba1d292b443c407c9a42f58a40ef20e90a8f8",
        ),
        (
            "003",
            41,
            "canonical-question-candidates-v6",
            "finproof-canonical-question-candidates-003",
            "CQ-003-001",
            "CQ-003-024",
            "edfbcd76c90eee8e02f9af21033b959149fdfd7c2ed1c73add6f433f32406f71",
        ),
        (
            "004",
            53,
            "canonical-question-candidates-v7",
            "finproof-canonical-question-candidates-004",
            "CQ-004-001",
            "CQ-004-024",
            "88900b53f9f338ccc34dbc028e12e95d288751e14184f021b5ff918baf4c142e",
        ),
        (
            "005",
            65,
            "canonical-question-candidates-v8",
            "finproof-canonical-question-candidates-005",
            "CQ-005-001",
            "CQ-005-024",
            "1551205333c322a3813cbdc40a25d0c4f2558a189d0e2fc285007d15654bc6a9",
        ),
    ],
)
async def test_legacy_batches_retain_metadata_ids_and_prompt_hashes(
    batch_id: str,
    seed: int,
    prompt_version: str,
    request_id: str,
    first_id: str,
    last_id: str,
    prompt_hash: str,
) -> None:
    content = _batch_002_content() if batch_id == "002" else _content()
    client = _Client(content)

    packet = await generate_review_packet(
        client,
        batch_id=batch_id,
        generated_at=datetime(2026, 8, 26, tzinfo=UTC),
    )

    assert packet["seed"] == seed
    assert packet["prompt_version"] == prompt_version
    assert packet["prompt_sha256"] == prompt_hash
    candidates = cast(list[dict[str, str]], packet["candidates"])
    assert candidates[0]["candidate_id"] == first_id
    assert candidates[-1]["candidate_id"] == last_id
    assert client.requests[0][1] == request_id


def test_unknown_batch_still_fails_closed() -> None:
    with pytest.raises(ValueError, match="batch_id"):
        generator._batch_contract("999")


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
    assert request.to_payload()["thinking"] == {"effort": "none"}
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


@pytest.mark.asyncio
async def test_hcx_generation_supports_the_frozen_batch_004_contract() -> None:
    client = _Client(_content())

    packet = await generate_review_packet(
        client,
        batch_id="004",
        generated_at=datetime(2026, 8, 25, 12, 30, tzinfo=UTC),
    )

    assert packet["batch_id"] == "004"
    assert packet["model"] == "HCX-007"
    assert packet["seed"] == 53
    assert packet["prompt_version"] == "canonical-question-candidates-v7"
    assert packet["review_status"] == "pending_human_review"
    assert packet["reviewer"] == "곽태성"
    candidates = cast(list[dict[str, str]], packet["candidates"])
    assert [candidate["candidate_id"] for candidate in candidates] == [
        f"CQ-004-{index:03d}" for index in range(1, 25)
    ]
    request, request_id = client.requests[0]
    assert request_id == "finproof-canonical-question-candidates-004"
    assert request.model_name == "HCX-007"
    assert request.seed == 53
    prompt = request.messages[0].content
    batch_004_slots = (
        "1 lookup: 국내채권 KR101501DD13의 매수수익률과 만기일 조회",
        "2 lookup: 국내 ETF KR7091160002의 1개월 수익률과 연초이후 수익률 조회",
        "3 lookup: 해외 ETF AAEQ.O의 총보수와 AUM 조회",
        "4 lookup: 공모펀드 KR5010101702의 5년 수익률과 AUM 조회",
        (
            "5 screen: 매수수익률 3.1% 이상, 2026-07-11 기준 만기가 지나지 않고 "
            "매수가능수량이 양수인 국내채권"
        ),
        ("6 screen: 투자지역이 국내이고 1개월 수익률 15% 이상이며 판매 가능한 국내 ETF, ETN 제외"),
        (
            "7 screen: 투자지역이 미국이고 AUM 1억 USD 이상이며 총보수 0.5% 이하인 "
            "해외 ETF, ETN 제외"
        ),
        ("8 screen: 5년 수익률 10% 이상이고 위험등급이 매우 낮은 위험인 공모펀드"),
        "9 screen: 1년 수익률이 0% 미만이고 판매 가능한 국내 ETN, ETN 명시",
        (
            "10 rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 "
            "국내채권 중 잔존일수 긴 5개"
        ),
        "11 rank: 국내 ETF 1개월 수익률 낮은 5개, ETN 제외",
        "12 rank: 거래통화 USD인 해외 ETF AUM 작은 5개, ETN 제외",
        "13 rank: 공모펀드 5년 수익률 상위 5개",
        "14 compare: 국내채권 KR101501DD13과 KR101501DD47의 잔존일수 비교",
        "15 compare: 해외 ETF AAA와 AAEQ.O의 AUM 비교",
        "16 compare: 공모펀드 KR5010101702와 KR5010101714의 5년 수익률 비교",
        "17 aggregate: 판매 가능한 국내 ETF의 AUM 합계, ETN 제외",
        "18 aggregate: 공모펀드 5년 수익률 최댓값",
        ("19 cross_product: 국내 ETF와 공모펀드의 1년 수익률 하위 3개를 유형별 분리"),
        ("20 cross_product: 국내 ETF와 해외 ETF의 AUM 하위 3개를 통화별·유형별 분리"),
        (
            "21 clarification: 안전하고 수익률이 높은 국내채권 5개 요청. 자연스러운 "
            "질문으로만 작성하고 추천·모호성 설명을 쓰지 않으며, 신용등급 기준과 "
            "복합 우선순위는 질문에서 생략"
        ),
        (
            "22 quality: 국내 ETF와 해외 ETF의 AUM 상위 5개를 하나의 순위로 합치지 않고 "
            "통화별로 분리하며 고정 환율 기준이 없음을 경고"
        ),
        (
            "23 quality: 판매 가능한 공모펀드 수를 itm_no 상품번호 기준으로 집계하되 "
            "원천 판매상태와 검증된 매수 가능 상태를 구분"
        ),
        (
            "24 quality: KODEX 200처럼 비슷한 이름의 상품 후보를 자동으로 같은 상품에 "
            "병합하지 않고 정확한 식별자 확인을 요청"
        ),
    )
    assert [prompt.index(slot) for slot in batch_004_slots] == sorted(
        prompt.index(slot) for slot in batch_004_slots
    )


@pytest.mark.asyncio
async def test_hcx_generation_supports_the_frozen_batch_005_contract() -> None:
    client = _Client(_content())

    packet = await generate_review_packet(
        client,
        batch_id="005",
        generated_at=datetime(2026, 8, 25, 12, 30, tzinfo=UTC),
    )

    assert packet["batch_id"] == "005"
    assert packet["model"] == "HCX-007"
    assert packet["seed"] == 65
    assert packet["prompt_version"] == "canonical-question-candidates-v8"
    assert packet["review_status"] == "pending_human_review"
    assert packet["reviewer"] == "곽태성"
    candidates = cast(list[dict[str, str]], packet["candidates"])
    assert [candidate["candidate_id"] for candidate in candidates] == [
        f"CQ-005-{index:03d}" for index in range(1, 25)
    ]
    request, request_id = client.requests[0]
    assert request_id == "finproof-canonical-question-candidates-005"
    assert request.model_name == "HCX-007"
    assert request.seed == 65
    prompt = request.messages[0].content
    assert all(
        phrase in prompt
        for phrase in (
            "일반적인 ETF 질문은 ETN을 제외합니다. ETN을 명시한 질문만 ETN을 포함합니다.",
            "미래 수익률 예측이나 단정적인 투자 추천을 요구하지 마십시오.",
            "응답은 JSON 객체 하나만 반환하고 다른 텍스트나 마크다운을 포함하지 마십시오.",
            "루트 키는 candidates 하나뿐이며 각 항목의 키는 category와 question 두 개뿐입니다.",
            "1~4 lookup",
            "22~24 quality",
        )
    )
    batch_005_slots = (
        "1 lookup: 국내채권 KR350901G671의 신용등급과 만기일 조회",
        "2 lookup: 국내 ETF KR7371160003의 총보수와 추적오차 조회",
        "3 lookup: 해외 ETN NRGD.K의 1일 수익률과 거래통화 조회",
        "4 lookup: 공모펀드 KR5138490078의 18개월 수익률과 2년 수익률 조회",
        (
            "5 screen: 신용등급 BBB+ 이상, 매수수익률 3.5% 이상, 2026-07-11 기준 "
            "만기가 지나지 않고 매수가능수량이 양수인 국내채권"
        ),
        "6 screen: 연초이후 수익률이 0% 미만이고 판매 가능한 국내 ETF, ETN 제외",
        "7 screen: 거래통화 USD이고 총보수가 0% 초과인 해외 ETN, ETN 명시",
        "8 screen: 18개월 수익률 10% 이상이고 위험등급이 있는 공모펀드",
        (
            "9 screen: AUM 100억원 이상이고 연초이후 수익률이 0% 초과이며 "
            "판매 가능한 국내 ETN, ETN 명시"
        ),
        (
            "10 rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 "
            "국내채권 중 매수수익률 낮은 5개"
        ),
        "11 rank: 국내 ETN 추적오차 높은 5개, ETN 명시",
        "12 rank: 거래통화 USD인 해외 ETN 총보수 높은 5개, ETN 명시",
        "13 rank: 공모펀드 18개월 수익률 상위 5개",
        "14 compare: 국내채권 KR350105G9C6와 KR350901G671의 신용등급 비교",
        "15 compare: 국내 ETF KR7305080004와 KR7371160003의 총보수 비교",
        "16 compare: 공모펀드 KR5114420158과 KR5138490078의 2년 수익률 비교",
        (
            "17 aggregate: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 "
            "국내채권의 매수가능수량 합계"
        ),
        "18 aggregate: 공모펀드 18개월 수익률 평균",
        "19 cross_product: 국내 ETF와 공모펀드의 3개월 수익률 하위 3개를 유형별 분리",
        "20 cross_product: 국내 ETN과 해외 ETN의 총보수 낮은 3개를 유형별 분리",
        (
            "21 clarification: 해외 상장 상품 중 하루 수익률이 좋고 총보수가 낮은 5개 요청; "
            "자연스러운 질문으로만 작성하고 추천·모호성 설명을 쓰지 않으며 ETF/ETN 유형과 "
            "복합 우선순위는 질문에서 생략"
        ),
        "22 quality: 국내 ETN 추적오차 낮은 5개 요청으로 전부 0 공동순위 확인",
        "23 quality: 해외 ETN 1일 수익률 높은 5개 요청으로 전부 0 공동순위 확인",
        (
            "24 quality: 18개월 수익률이 없는 공모펀드 수를 itm_no 상품번호 기준으로 "
            "중복 없이 집계하고 속성 행 수로 세지 않음을 확인"
        ),
    )
    assert [prompt.index(slot) for slot in batch_005_slots] == sorted(
        prompt.index(slot) for slot in batch_005_slots
    )


def test_batch_005_rejects_misordered_raw_candidate_categories() -> None:
    content = json.loads(_content())
    candidates = content["candidates"]
    candidates[0]["category"], candidates[4]["category"] = (
        candidates[4]["category"],
        candidates[0]["category"],
    )

    with pytest.raises(ValueError, match="batch 005 candidate order"):
        generator._validate_candidates(json.dumps(content, ensure_ascii=False), batch_id="005")


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


def test_cli_passes_batch_004_to_hcx_and_writes_batch_004_packet(
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
    output = tmp_path / "review" / "batch-004.json"

    assert (
        generator.main(
            ["--output", str(output), "--batch-id", "004"],
            environ={"FINPROOF_HCX_API_KEY": "not-a-real-key"},
            repository_root=tmp_path,
        )
        == 0
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(observed["api_key"], SecretStr)
    assert observed["batch_id"] == "004"
    assert written["batch_id"] == "004"
    assert written["seed"] == 53
    assert written["prompt_version"] == "canonical-question-candidates-v7"
    assert [candidate["candidate_id"] for candidate in written["candidates"]] == [
        f"CQ-004-{index:03d}" for index in range(1, 25)
    ]


def test_cli_passes_batch_005_to_hcx_and_writes_batch_005_packet(
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
    output = tmp_path / "review" / "batch-005.json"

    assert (
        generator.main(
            ["--output", str(output), "--batch-id", "005"],
            environ={"FINPROOF_HCX_API_KEY": "not-a-real-key"},
            repository_root=tmp_path,
        )
        == 0
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(observed["api_key"], SecretStr)
    assert observed["batch_id"] == "005"
    assert written["batch_id"] == "005"
    assert written["seed"] == 65
    assert written["prompt_version"] == "canonical-question-candidates-v8"
    assert [candidate["candidate_id"] for candidate in written["candidates"]] == [
        f"CQ-005-{index:03d}" for index in range(1, 25)
    ]
