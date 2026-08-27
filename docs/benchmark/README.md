# FinProof benchmark runbook

Phase 4 Task 3 측정은 같은 265개 reviewed canonical case, 공식 artifact,
HyperCLOVA X 모델·설정, prompt/config version, code commit, 실행 환경을 사용한다.
수치 보고서는 실행 결과로만 만들며 수동 보정하지 않는다.

## Ablation

변형은 다음 다섯 개로 고정한다.

1. `A_DIRECT_HCX`: retrieved row를 HCX가 직접 읽는 실험 전용 경로
2. `B_CONSTRAINED_PLAN`: allowlisted QueryPlan
3. `C_DETERMINISTIC_EXECUTOR`: deterministic executor
4. `D_DOMAIN_POLICY`: grain/time/state/metric policy
5. `E_VERIFIED_ANSWER`: evidence/verifier/conditional dual-lens

`A_DIRECT_HCX`는 production/evaluation endpoint에서 호출할 수 없다. 외부 HCX
전송은 이 실험에 대한 명시적 승인을 받은 뒤에만 수행한다. 각 변형의 실제 raw
measurement를 `artifacts/evaluation/ablation_raw/<VARIANT_NAME>.json`에 기록한 뒤
다음 명령으로 동일 case checksum과 환경 identity를 검증하고 묶는다.

```bash
bash scripts/run_ablation.sh
```

## Load

reviewed mix는 lookup, multi-filter rank, cross-product split, quality explanation
네 형태를 4:3:2:1로 사용한다. 질문과 전체 응답은 보고서에 저장하지 않는다.

```bash
bash scripts/run_load.sh --base-url http://127.0.0.1:8000 \
  --duration-seconds 60 --concurrency 8
```

## Soak and readiness

공개 runtime 계약은 `GET /answer` 하나다.
공개 health/readiness/version 경로를 추가하지 않는다. readiness와 restart는 container startup 및 schema-valid
`GET /answer`로 검증하고, version bundle이 같은 deterministic answer hash만 drift로
비교한다.

release 전 최소 24시간, 가능하면 48시간 실행한다. 보고서는 cycle마다 atomic하게
교체되므로 같은 설정과 파일로 재실행하면 이어서 측정한다.

```bash
bash scripts/run_soak.sh --base-url http://127.0.0.1:8000 --hours 24
```

캐시는 frozen decision A-004에 따라 비활성이다. 따라서 캐시 손상 실험은 N/A이며,
그 검사를 위해 캐시를 새로 구현하지 않는다. 보고서에는 secret, API key, 전체 응답,
내부 오류를 넣지 않는다.
