"""Generate one HCX-only packet of noncanonical question candidates."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import SecretStr

from finproof.planner.hcx_client import HcxClient, create_hcx_http_client
from finproof.planner.models import HcxMessage, HcxRequest

BATCH_ID = "001"
PROVIDER = "naver-hyperclova-x"
DEFAULT_MODEL = "HCX-007"
SEED = 17
PROMPT_VERSION = "canonical-question-candidates-v4"
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
거래량, 표면금리, 분배금, 레버리지, 가격, 상관계수, 자산배분, 설정일, 상장일은 지원하지 않습니다.
집계는 count 또는 허용 필드의 min/max/avg만 사용하고, sum은 aum과 buyable_quantity에만 사용하십시오.
lookup은 정확한 단일 상품 조회입니다. 공식 데이터에서 검증하지 않은 이름을 만들지 말고
[검증된 상품명 또는 ID] 자리표시자를 사용하십시오.
screen은 조건 필터, rank는 정렬/top-k, compare는 두 상품이나 비교 가능한 집단 비교,
aggregate는 허용 집계, cross_product는 둘 이상의 상품 유형을 분리 실행하는 질문입니다.
clarification은 날짜, 기준값, 우선순위 또는 지표가 실제로 모호한 질문이어야 합니다.
quality는 다음 frozen 사례를 우선 사용하십시오: 국내 추적오차 전부 0 공동순위,
해외 ETF/ETN 1일 수익률 전부 0 공동순위, 해외 총보수 0 미검증 경고,
공모펀드 NULL 위험등급, 채권 미평가/복수 신용등급, 스냅샷 기준일과 상태 제한.
아래 24개 슬롯을 각각 자연스러운 한국어 질문 하나로만 표현하십시오.
슬롯별 의미, 식별자, 필드, 조건, 순서와 category를 바꾸지 마십시오:
1 lookup: 국내채권 KR101501DA16의 매수수익률과 만기일 조회
2 lookup: 국내 ETF KR7305080004의 총보수와 AUM 조회
3 lookup: 해외 ETF EES의 총보수와 거래통화 조회
4 lookup: 공모펀드 KR5114420158의 위험등급과 AUM 조회
5 screen: 총보수 0.2% 이하 해외 ETF만 조회
6 screen: 신용등급 AA- 이상이고 현재 매수 가능한 국내채권 조회
7 screen: 위험등급이 없는 공모펀드 조회
8 screen: 3개월 수익률 5% 이상 국내 ETF 조회
9 screen: 판매 가능한 국내 ETF만 조회하며 ETN 제외
10 rank: 국내 ETF 연초이후 수익률 상위 3개
11 rank: 공모펀드 1년 수익률 상위 5개
12 rank: 국내채권 잔존일수 짧은 순 상위 5개
13 rank: 해외 ETF 총보수 낮은 순 상위 5개
14 compare: 국내 ETF KR7305080004와 KR7371160003의 1년 수익률 비교
15 compare: 해외 ETF EES와 CHGX.O의 총보수 비교
16 compare: 공모펀드 KR5114420158와 KR5138490078의 3개월 수익률 비교
17 aggregate: 국내 ETF 수를 ETN 제외하고 집계
18 aggregate: 공모펀드 1년 수익률 평균 집계
19 cross_product: 국내 ETF와 공모펀드의 1개월 수익률 상위 3개를 유형별로 분리
20 cross_product: 국내 ETF와 해외 ETF의 AUM 상위 3개를 통화별·유형별로 분리
21 clarification: 상품 유형과 수익률 기간이 없는 성과 우수 금융상품 요청
22 quality: 국내 ETF 추적오차 낮은 5개 요청으로 전부 0 공동순위 확인
23 quality: 해외 ETF 1일 수익률 높은 5개 요청으로 전부 0 공동순위 확인
24 quality: 위험등급이 없는 공모펀드 수 집계
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

_PROMPT_002 = """당신은 FinProof 평가 질문 후보 작성자입니다.
생성물은 사람 검토 전의 질문 후보이며 정답 데이터가 아니다. ground truth로 취급하지 마십시오.
공식 2026-07-11 스냅샷의 네 데이터 계열인 국내채권, 국내 ETF/ETN, 해외 ETF/ETN,
공모펀드를 대상으로 자연스러운 한국어 질문을 작성하십시오.
공식 데이터와 FinProof 계약으로 지원 가능한 필드, 상태, 지표, 기간, 통화, 집계만 질문하십시오.
일반적인 ETF 질문은 ETN을 제외합니다. ETN을 명시한 질문만 ETN을 포함합니다.
미래 수익률 예측이나 단정적인 투자 추천을 요구하지 마십시오.
명확화 필요성과 데이터 품질 한계를 의도적으로 시험하는 질문은 해당 범주에 포함할 수 있습니다.
아래 24개 슬롯을 각각 자연스러운 한국어 질문 하나로만 표현하십시오.
슬롯별 의미, 식별자, 지표, 임계값, 상품 유형, 순서와 category를 바꾸지 마십시오:
1 lookup: 국내채권 KR350105G9C6의 신용등급과 매수가능수량 조회
2 lookup: 국내 ETF KR7243880002의 연초이후 수익률과 AUM 조회
3 lookup: 해외 ETF VOO의 AUM과 거래통화 조회
4 lookup: 공모펀드 KR5129470010의 1년 수익률과 위험등급 조회
5 screen: 매수수익률 4% 이상, 만기일이 2026-07-11 이후이고 매수가능수량이 양수인 국내채권
6 screen: AUM 1조원 이상이고 판매 가능한 국내 ETF, ETN 제외
7 screen: 총보수가 0% 초과 0.1% 이하인 해외 ETF
8 screen: 1년 수익률 100% 이상이고 위험등급이 있는 공모펀드
9 screen: 총보수 0.5% 이하이고 판매 가능한 국내 ETN(ETN 명시)
10 rank: 현재 매수 가능한 국내채권 중 매수수익률 높은 5개
11 rank: 국내 ETF AUM 큰 5개, ETN 제외
12 rank: 거래통화 USD인 해외 ETF AUM 큰 5개
13 rank: 거래통화 KRW인 공모펀드 AUM 큰 5개
14 compare: 국내채권 KR350105G9C6와 KR350901G671의 매수가능수량 비교
15 compare: 국내 ETF KR7243880002와 KR7494310006의 연초이후 수익률 비교
16 compare: 공모펀드 KR5129470010와 KR5129470016의 1년 수익률 비교
17 aggregate: 거래통화 USD인 해외 ETF 수 집계, ETN 제외
18 aggregate: 국내 ETF 1년 수익률 평균, ETN 제외
19 cross_product: 국내 ETF와 공모펀드의 3개월 수익률 상위 3개를 유형별 분리
20 cross_product: 국내 ETF와 해외 ETF의 총보수 낮은 3개를 유형별 분리
21 clarification: 국내 ETF 중 수익률이 좋고 AUM이 큰 5개 요청. \
자연스러운 질문으로만 작성하고 추천이나 모호성 설명을 쓰지 마십시오. \
수익률 기간과 복합 우선순위는 질문에서 자연스럽게 생략하십시오.
22 quality: 국내 ETF 총보수 낮은 5개—기록된 0의 미검증 품질 경고 확인
23 quality: AA- 이상 국내채권 수 집계—미평가 채권 제외, 복수 신용등급과 등급 정책 확인
24 quality: 판매 가능한 해외 ETF 5개—검증된 매수 가능 여부 제한 확인
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

_PROMPT_003 = """당신은 FinProof 평가 질문 후보 작성자입니다.
생성물은 사람 검토 전의 질문 후보이며 정답 데이터가 아니다. ground truth로 취급하지 마십시오.
공식 2026-07-11 스냅샷의 네 데이터 계열인 국내채권, 국내 ETF/ETN, 해외 ETF/ETN,
공모펀드를 대상으로 자연스러운 한국어 질문을 작성하십시오.
일반적인 ETF 질문은 ETN을 제외합니다. ETN을 명시한 질문만 ETN을 포함합니다.
미래 수익률 예측이나 단정적인 투자 추천을 요구하지 마십시오.
아래 24개 슬롯을 각각 자연스러운 한국어 질문 하나로만 표현하십시오.
슬롯별 식별자, 필드/지표, 임계값, 날짜, 상품 유형, 순서와 category를 바꾸지 마십시오:
1 lookup: 국내채권 KR353601DE34의 매수수익률과 잔존일수 조회
2 lookup: 국내 ETN KRG520000826의 3개월 수익률과 연초이후 수익률 조회
3 lookup: 해외 ETN NRGD.K의 총보수와 AUM 조회
4 lookup: 공모펀드 KR5174430032의 3년 수익률과 위험등급 조회
5 screen: 매수수익률 3% 이상, 만기일이 2026-07-11 이후이고 \
매수가능수량이 1천만 이상인 국내채권
6 screen: 6개월 수익률 50% 이상이고 판매 가능한 국내 ETF, ETN 제외
7 screen: 투자지역이 미국이고 총보수 0.15% 이하인 해외 ETF, ETN 제외
8 screen: 3년 수익률 50% 이상이고 위험등급이 낮은 위험인 공모펀드
9 screen: 3개월 수익률 10% 이상이고 판매 가능한 국내 ETN, ETN 명시
10 rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권 중 \
매수가능수량 상위 5개
11 rank: 국내 ETF 6개월 수익률 상위 5개, ETN 제외
12 rank: 거래통화 USD인 해외 ETN AUM 상위 5개, ETN 명시
13 rank: 공모펀드 3년 수익률 상위 5개
14 compare: 국내채권 KR353601DE34와 KR354301GB84의 매수수익률 비교
15 compare: 국내 ETN KRG520000826와 KRG530001202의 3개월 수익률 비교
16 compare: 공모펀드 KR5174430032와 KR5114450497의 3년 수익률 비교
17 aggregate: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권의 \
매수수익률 평균
18 aggregate: 거래통화 USD인 해외 ETN의 AUM 합계, ETN 명시
19 cross_product: 국내 ETF와 공모펀드의 6개월 수익률 상위 3개를 유형별 분리
20 cross_product: 국내 ETN과 해외 ETN의 AUM 상위 3개를 통화별·유형별 분리
21 clarification: 위험이 낮고 장기 수익률이 좋은 공모펀드 5개 요청. 자연스러운 질문으로만 작성하고 \
추천·모호성 설명을 쓰지 않으며, 수익률 기간과 복합 우선순위는 질문에서 생략
22 quality: 매수가능수량이 양수로 기록된 국내채권과 2026-07-11 기준 만기 경과를 제외한 \
매수 가능 후보 수를 각각 집계
23 quality: 해외 ETN 총보수 낮은 5개에서 기록된 0%와 0보다 큰 값을 구분하고, \
기록된 0%가 실제 무보수인지 미검증임을 경고
24 quality: 위험등급별 공모펀드 수를 itm_no 상품번호 기준으로 중복 없이 집계하고 \
속성 행 수로 세지 않음을 확인
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

_PROMPT_004 = """당신은 FinProof 평가 질문 후보 작성자입니다.
생성물은 사람 검토 전의 질문 후보이며 정답 데이터가 아니다. ground truth로 취급하지 마십시오.
공식 2026-07-11 스냅샷의 네 데이터 계열인 국내채권, 국내 ETF/ETN, 해외 ETF/ETN,
공모펀드를 대상으로 자연스러운 한국어 질문을 작성하십시오.
일반적인 ETF 질문은 ETN을 제외합니다. ETN을 명시한 질문만 ETN을 포함합니다.
미래 수익률 예측이나 단정적인 투자 추천을 요구하지 마십시오.
아래 24개 슬롯을 각각 자연스러운 한국어 질문 하나로만 표현하십시오.
슬롯별 식별자, 필드/지표, 임계값, 날짜, 상품 유형, 순서와 category를 바꾸지 마십시오:
1 lookup: 국내채권 KR101501DD13의 매수수익률과 만기일 조회
2 lookup: 국내 ETF KR7091160002의 1개월 수익률과 연초이후 수익률 조회
3 lookup: 해외 ETF AAEQ.O의 총보수와 AUM 조회
4 lookup: 공모펀드 KR5010101702의 5년 수익률과 AUM 조회
5 screen: 매수수익률 3.1% 이상, 2026-07-11 기준 만기가 지나지 않고 \
매수가능수량이 양수인 국내채권
6 screen: 투자지역이 국내이고 1개월 수익률 15% 이상이며 판매 가능한 \
국내 ETF, ETN 제외
7 screen: 투자지역이 미국이고 AUM 1억 USD 이상이며 총보수 0.5% 이하인 \
해외 ETF, ETN 제외
8 screen: 5년 수익률 10% 이상이고 위험등급이 매우 낮은 위험인 공모펀드
9 screen: 1년 수익률이 0% 미만이고 판매 가능한 국내 ETN, ETN 명시
10 rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 \
국내채권 중 잔존일수 긴 5개
11 rank: 국내 ETF 1개월 수익률 낮은 5개, ETN 제외
12 rank: 거래통화 USD인 해외 ETF AUM 작은 5개, ETN 제외
13 rank: 공모펀드 5년 수익률 상위 5개
14 compare: 국내채권 KR101501DD13과 KR101501DD47의 잔존일수 비교
15 compare: 해외 ETF AAA와 AAEQ.O의 AUM 비교
16 compare: 공모펀드 KR5010101702와 KR5010101714의 5년 수익률 비교
17 aggregate: 판매 가능한 국내 ETF의 AUM 합계, ETN 제외
18 aggregate: 공모펀드 5년 수익률 최댓값
19 cross_product: 국내 ETF와 공모펀드의 1년 수익률 하위 3개를 유형별 분리
20 cross_product: 국내 ETF와 해외 ETF의 AUM 하위 3개를 통화별·유형별 분리
21 clarification: 안전하고 수익률이 높은 국내채권 5개 요청. 자연스러운 질문으로만 작성하고 \
추천·모호성 설명을 쓰지 않으며, 신용등급 기준과 복합 우선순위는 질문에서 생략
22 quality: 국내 ETF와 해외 ETF의 AUM 상위 5개를 하나의 순위로 합치지 않고 \
통화별로 분리하며 고정 환율 기준이 없음을 경고
23 quality: 판매 가능한 공모펀드 수를 itm_no 상품번호 기준으로 집계하되 \
원천 판매상태와 검증된 매수 가능 상태를 구분
24 quality: KODEX 200처럼 비슷한 이름의 상품 후보를 자동으로 같은 상품에 \
병합하지 않고 정확한 식별자 확인을 요청
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

_PROMPT_005 = """당신은 FinProof 평가 질문 후보 작성자입니다.
생성물은 사람 검토 전의 질문 후보이며 정답 데이터가 아니다. ground truth로 취급하지 마십시오.
공식 2026-07-11 스냅샷의 네 데이터 계열인 국내채권, 국내 ETF/ETN, 해외 ETF/ETN,
공모펀드를 대상으로 자연스러운 한국어 질문을 작성하십시오.
공식 데이터와 FinProof 계약으로 지원 가능한 필드, 상태, 지표, 기간, 통화, 집계만 질문하십시오.
일반적인 ETF 질문은 ETN을 제외합니다. ETN을 명시한 질문만 ETN을 포함합니다.
미래 수익률 예측이나 단정적인 투자 추천을 요구하지 마십시오.
아래 24개 슬롯을 각각 자연스러운 한국어 질문 하나로만 표현하십시오.
슬롯별 식별자, 필드/지표, 임계값, 날짜, 상품 유형, 순서와 category를 바꾸지 마십시오:
1 lookup: 국내채권 KR350901G671의 신용등급과 만기일 조회
2 lookup: 국내 ETF KR7371160003의 총보수와 추적오차 조회
3 lookup: 해외 ETN NRGD.K의 1일 수익률과 거래통화 조회
4 lookup: 공모펀드 KR5138490078의 18개월 수익률과 2년 수익률 조회
5 screen: 신용등급 BBB+ 이상, 매수수익률 3.5% 이상, 2026-07-11 기준 만기가 지나지 않고 \
매수가능수량이 양수인 국내채권
6 screen: 연초이후 수익률이 0% 미만이고 판매 가능한 국내 ETF, ETN 제외
7 screen: 거래통화 USD이고 총보수가 0% 초과인 해외 ETN, ETN 명시
8 screen: 18개월 수익률 10% 이상이고 위험등급이 있는 공모펀드
9 screen: AUM 100억원 이상이고 연초이후 수익률이 0% 초과이며 판매 가능한 국내 ETN, ETN 명시
10 rank: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권 중 \
매수수익률 낮은 5개
11 rank: 국내 ETN 추적오차 높은 5개, ETN 명시
12 rank: 거래통화 USD인 해외 ETN 총보수 높은 5개, ETN 명시
13 rank: 공모펀드 18개월 수익률 상위 5개
14 compare: 국내채권 KR350105G9C6와 KR350901G671의 신용등급 비교
15 compare: 국내 ETF KR7305080004와 KR7371160003의 총보수 비교
16 compare: 공모펀드 KR5114420158과 KR5138490078의 2년 수익률 비교
17 aggregate: 2026-07-11 기준 만기가 지나지 않고 매수가능수량이 양수인 국내채권의 \
매수가능수량 합계
18 aggregate: 공모펀드 18개월 수익률 평균
19 cross_product: 국내 ETF와 공모펀드의 3개월 수익률 하위 3개를 유형별 분리
20 cross_product: 국내 ETN과 해외 ETN의 총보수 낮은 3개를 유형별 분리
21 clarification: 해외 상장 상품 중 하루 수익률이 좋고 총보수가 낮은 5개 요청; \
자연스러운 질문으로만 작성하고 추천·모호성 설명을 쓰지 않으며 \
ETF/ETN 유형과 복합 우선순위는 질문에서 생략
22 quality: 국내 ETN 추적오차 낮은 5개 요청으로 전부 0 공동순위 확인
23 quality: 해외 ETN 1일 수익률 높은 5개 요청으로 전부 0 공동순위 확인
24 quality: 18개월 수익률이 없는 공모펀드 수를 itm_no 상품번호 기준으로 중복 없이 집계하고 \
속성 행 수로 세지 않음을 확인
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


def _batch_contract(batch_id: str) -> tuple[int, str, str, str]:
    if batch_id == "001":
        return SEED, PROMPT_VERSION, _PROMPT, "finproof-canonical-question-candidates-001"
    if batch_id == "002":
        return (
            29,
            "canonical-question-candidates-v5",
            _PROMPT_002,
            ("finproof-canonical-question-candidates-002"),
        )
    if batch_id == "003":
        return (
            41,
            "canonical-question-candidates-v6",
            _PROMPT_003,
            "finproof-canonical-question-candidates-003",
        )
    if batch_id == "004":
        return (
            53,
            "canonical-question-candidates-v7",
            _PROMPT_004,
            "finproof-canonical-question-candidates-004",
        )
    if batch_id == "005":
        return (
            65,
            "canonical-question-candidates-v8",
            _PROMPT_005,
            "finproof-canonical-question-candidates-005",
        )
    raise ValueError("batch_id must be one of: 001, 002, 003, 004, 005")


class _Response(Protocol):
    message_content: str


class _Client(Protocol):
    async def generate(self, request: HcxRequest, request_id: str) -> _Response: ...


class _AuthoringHcxClient(HcxClient):
    _TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0)


async def generate_review_packet(
    client: _Client,
    *,
    model_name: str = DEFAULT_MODEL,
    batch_id: str = BATCH_ID,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Request, validate, and label one pending human-review packet."""
    if model_name != DEFAULT_MODEL:
        raise ValueError(f"model_name must be exactly {DEFAULT_MODEL}")
    seed, prompt_version, prompt, request_id = _batch_contract(batch_id)
    request = HcxRequest.strict_json(
        model_name=model_name,
        messages=(
            HcxMessage(role="system", content=prompt),
            HcxMessage(
                role="user",
                content="지정된 분포대로 한국어 질문 후보 24개를 JSON으로 생성하십시오.",
            ),
        ),
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        temperature=0.0,
        seed=seed,
    )
    response = await client.generate(request, request_id=request_id)
    candidates = _validate_candidates(response.message_content, batch_id=batch_id)
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("generated timestamp must be timezone-aware")
    return {
        "batch_id": batch_id,
        "provider": PROVIDER,
        "model": model_name,
        "seed": seed,
        "prompt_version": prompt_version,
        "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
        "generated_at": timestamp.astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "review_status": "pending_human_review",
        "reviewer": "곽태성",
        "target_distribution": dict(TARGET_DISTRIBUTION),
        "candidates": candidates,
    }


def _validate_candidates(content: str, *, batch_id: str = BATCH_ID) -> list[dict[str, str]]:
    _batch_contract(batch_id)
    if not content or len(content.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("HCX candidate response is empty or oversized")
    content = content.strip()
    if content.startswith("```json\n"):
        content = content[8:]
        if closing_fence := re.search(r"\n```[ \t]*(?:\n|$)", content):
            content = content[: closing_fence.start()]
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
    if batch_id == "002":
        if not any(
            phrase in grouped["screen"][0]
            for phrase in (
                "매수가능수량이 양수",
                "매수가능수량이 0 초과",
                "매수가능수량이 0보다 큰",
            )
        ):
            raise ValueError("batch 002 screen 001 must require positive buyable quantity")
        clarification = grouped["clarification"][0]
        if not all(phrase in clarification for phrase in ("국내 ETF", "수익률", "AUM")) or any(
            phrase in clarification
            for phrase in (
                "추천",
                "기간",
                "우선순위",
                "기준",
                "명시",
                "모호",
                "불명확",
                "1일",
                "1주",
                "1개월",
                "3개월",
                "6개월",
                "1년",
                "2년",
                "3년",
                "5년",
                "연초",
            )
        ):
            raise ValueError("batch 002 clarification must be a natural clarification")
        quality = grouped["quality"][1]
        if "복수" not in quality or "등급 정책" not in quality:
            raise ValueError("batch 002 quality 002 must confirm multiple-rating policy")
    candidates = [
        {
            "candidate_id": f"CQ-{batch_id}-{category.upper()}-{index:03d}",
            "category": category,
            "question": question,
        }
        for category, category_questions in grouped.items()
        for index, question in enumerate(category_questions, 1)
    ]
    if batch_id in {"003", "004", "005"}:
        for index, candidate in enumerate(candidates, 1):
            candidate["candidate_id"] = f"CQ-{batch_id}-{index:03d}"
    return candidates


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
    batch_id = packet["batch_id"]
    if type(batch_id) is not str:
        raise ValueError("review packet batch_id is invalid")
    seed, prompt_version, prompt, _ = _batch_contract(batch_id)
    if (
        packet["provider"] != PROVIDER
        or packet["seed"] != seed
        or packet["prompt_version"] != prompt_version
        or packet["prompt_sha256"] != sha256(prompt.encode("utf-8")).hexdigest()
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
    expected = _validate_candidates(
        json.dumps({"candidates": raw_candidates}, ensure_ascii=False), batch_id=batch_id
    )
    if candidates != expected:
        raise ValueError("review packet candidate IDs or ordering are invalid")


async def _request_with_hcx(
    api_key: SecretStr,
    *,
    batch_id: str = BATCH_ID,
) -> dict[str, object]:
    async with create_hcx_http_client() as http_client:
        client = _AuthoringHcxClient(http_client=http_client, api_key=api_key)
        return await generate_review_packet(client, batch_id=batch_id)


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
    parser.add_argument("--batch-id", default=BATCH_ID, choices=("001", "002", "003", "004", "005"))
    args = parser.parse_args(argv)

    root = repository_root or Path.cwd()
    _validate_output_path(args.output, repository_root=root)
    environment = os.environ if environ is None else environ
    raw_api_key = environment.get("FINPROOF_HCX_API_KEY")
    if raw_api_key is None or not raw_api_key.strip():
        raise SystemExit("FINPROOF_HCX_API_KEY is required")

    packet = asyncio.run(_request_with_hcx(SecretStr(raw_api_key), batch_id=args.batch_id))
    write_review_packet(args.output, packet, repository_root=root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
