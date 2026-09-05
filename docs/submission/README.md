# Agent.종필 제출 안내

FinProof는 공식 금융상품 데이터에서 검색·비교·계산을 수행하고, 답변의 수치를
원천 근거와 연결하는 질의 시스템입니다. 팀명은 **Agent.종필**, 참가자는 곽태성입니다.

## 제출 자료

| 자료 | 위치 |
|---|---|
| 기술 제안서 | [PDF](FinProof_Technical_Proposal.pdf), [편집 가능한 PPTX](FinProof_Technical_Proposal.pptx) |
| API 주소와 요청·응답 명세 | [API_SCHEMA.md](API_SCHEMA.md) |
| 실행 환경과 재현 명령 | [저장소 README](../../README.md), [Dockerfile](../../Dockerfile) |
| 평가 수치와 해석 범위 | [PROPOSAL_EVIDENCE_INDEX.md](PROPOSAL_EVIDENCE_INDEX.md) |
| 배포 이미지와 검증 기록 | [RELEASE_RECORD.md](RELEASE_RECORD.md) |
| 상품 도메인 정의 | [ontology](../../ontology) |

## 평가 API

`GET https://101-79-30-91.sslip.io/answer`

`question_id`와 `question`을 쿼리 파라미터로 전달합니다. 정상 응답은
`question_id`, `question`, `retrieved_context`, `think_trace`, `answer`의
다섯 문자열 필드입니다. 입력 검증 오류와 지원 불가 응답은 API 명세를 참고해 주세요.

질의 의도 해석과 답변 단계에는 NCP HyperCLOVA X HCX-007을 사용합니다.
검색·순위·계산과 핵심 사실 검증은 코드가 맡습니다. 답변 단계에서 HCX는 검증된
사실 묶음을 받은 뒤 허용된 도입문을 반환하며, 앱은 검증된 본문을 그대로 이어 붙입니다.

## 결과를 읽을 때

검토된 계획을 재생하는 결정론 코어 검증은 144/144건을 통과했습니다.
별도로 봉인한 48건의 평가에서는 정상 응답 25건, 안전 종료 23건을 기록했습니다.
정상 응답 수와 정답 수는 같지 않으며, 상세 집계율은 제안서와 근거 색인에 공개했습니다.

최종 서버 부하는 검토된 네 질의를 가중 반복한 35요청입니다. 실패 0건,
p95 11,007.570ms를 기록했습니다. 반복 안정성 시험은 1,123.638초 동안
80회 관측한 범위이며, 24시간 연속 안정성을 입증한 결과는 아닙니다.

현재 구성종목 기반 검색, 해외 ETF의 1년 수익률, 실시간 값과 수익 전망은 제공하지
않습니다. 공식 데이터의 없는 값을 추정해 채우지 않습니다.

이번 마감 전 개정은 제안서와 안내 문서에만 적용했습니다. 이미 검증한 코드·데이터·
프롬프트·운영 이미지와 `finproof-submission` 태그는 변경하지 않았습니다.
