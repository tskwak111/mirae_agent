# FinProof macOS 이관 및 전수 감사 보고서

**감사일:** 2026-08-13

**대상:** Windows 작업 폴더를 압축해 Apple Silicon MacBook으로 이관한 저장소 전체

**감사 범위:** 초기 95개 파일과 25개 디렉터리, 이후 생성한 macOS 부트스트랩 파일 및 Git 기준선

**제품 구현 상태:** handoff scaffold만 존재하며 Phase 1 제품 구현은 시작되지 않음

## 1. 요약 결론

- 공식 입력 9개(PDF 1개, XLSX 8개)는 저장소의 SHA-256 manifest와 일치한다.
- 공식 데이터 감사는 총 145,393행, 기준일 `2026-07-11`로 동결 기준과 일치한다.
- 네 개 schema workbook에서 추출한 catalog는 총 207개 열로 원본과 일치한다.
- 공식 PDF 8쪽은 전부 렌더링했으며 누락, 깨진 글자, 잘림, 암호화, 폼, JavaScript가 없다.
- XLSX 8개는 ZIP/XML 구조, CRC, 시트, 행/열, 헤더, 관계 파일이 정상이다. 수식, 매크로, 외부 연결, 임베딩, 암호화는 없다.
- 실제 production package는 `src/finproof/__init__.py`와 `py.typed`뿐이다. 데이터 파이프라인, 질의 엔진, 증거/검증, HCX, FastAPI는 아직 없다.
- Mac에는 Apple Silicon 네이티브 Python 3.12.13과 uv를 설치했고, `.python-version`, `.venv`, `uv.lock`을 생성했다.
- Git이 없던 폴더에 `main` 저장소를 만들고 초기 handoff 기준선 commit을 생성했다.
- 압축 이관 찌꺼기 15개(`.DS_Store` 4개, CPython 3.14 `.pyc` 11개)와 빈 pytest 임시 디렉터리를 제거했다. `.pyc` 일부에 포함됐던 Windows 사용자 절대경로도 함께 제거됐다.
- 초기 품질 실행에서 pytest/원본 감사/스키마 검사는 성공했지만 Ruff와 mypy는 handoff 시점의 미검증 부채를 검출했다. 별도 품질 commit에서 수정했고 잠금 환경으로 재검증했다.
- 현재 Mac은 Phase 1 Task 1을 시작할 수 있는 workstation 상태다. FinProof 제품 자체나 CI/container가 준비됐다는 뜻은 아니다.

이 검사는 현재 폴더 내부의 일관성을 증명한다. manifest가 공식 기관의 전자서명으로 서명된 것은 아니고 원래 organizer 저장소 이력도 없으므로, 외부 원본에 대한 독립적 진위 증명까지 의미하지는 않는다. 최초 Git commit은 cleanup과 bootstrap 이후에 만들어졌으므로, Git만으로 cleanup 전 전달물의 chain of custody를 재구성할 수도 없다.

## 2. 프로젝트가 무엇인가

FinProof는 2026 미래에셋증권 AI Festival용 금융상품 분석 agent다. 한국어 질문을 다음 네 공식 master에 대해 처리한다.

| 데이터 | 테이블 | 원본 행 | 기본 grain |
|---|---|---:|---|
| 국내채권 | `PRBD01N001` | 42,394 | `instrument` |
| 국내 ETF/ETN | `PREF01N001` | 1,734 | `listed_product` |
| 해외 ETF/ETN | `PREF02N001` | 5,646 | `listed_product` |
| 공모펀드 속성행 | `PRFD01N001` | 95,619 | 기본 결과는 `fund_item` |

핵심 구조는 다음과 같다.

```text
한국어 질문
  -> HyperCLOVA X의 제한된 QueryPlan
  -> strict schema/semantic validation
  -> 상품별 native ExecutionSegment
  -> allowlist AST와 parameterized SQL
  -> DuckDB에서 결정론적 실행
  -> 상태/품질/비교가능성 정책
  -> source-cell evidence
  -> 결정론적 한국어 답변
  -> claim verifier
  -> GET /answer의 정확한 5개 문자열 필드
```

LLM은 SQL을 만들거나 금융 수치를 계산하거나 정책을 선택할 수 없다. 실행·필터·정렬·집계·계산·증거 생성은 코드가 담당한다. evaluation/runtime 경로의 유일한 생성형 모델은 HyperCLOVA X다.

## 3. 모든 파일 확인 범위

감사 과정에서 cleanup 전에 직접 관찰한 초기 폴더의 95개 파일과 25개 디렉터리를 다음처럼 분류했다. 별도의 pre-clean inventory 파일이나 pre-bootstrap Git parent는 없으므로 이 초기 개수는 감사 관찰 기록이며, Git으로 독립 재현 가능한 기준선은 post-cleanup root commit부터다.

- 의미 있는 원본/프로젝트 파일 80개
  - 최상위 계약·안내·prompt·빌드 파일
  - `docs/`의 설계, 계약, 위험, phase plan, 상태 파일 전체
  - `prompts/` 전체
  - `config/` YAML 8개
  - `schemas/` JSON Schema 8개
  - `src/`, `tests/`, `tools/`의 모든 source/fixture 파일
  - `source_material/`의 README, manifest, schema catalog, PDF, XLSX 8개
- 생성 찌꺼기 15개
  - `.DS_Store` 4개
  - CPython 3.14 `.pyc` 11개

텍스트 파일은 UTF-8/LF 여부와 내용의 끝까지 읽었다. 문서 감사 대상 35개만 해도 5,371줄/227,444 bytes이며, JSON 11개와 JSONL 13줄은 모두 parse했다. JSON Schema 8개는 Draft 2020-12 meta-schema 검사에 성공했다. YAML 8개는 부트스트랩 후 PyYAML로 versioned mapping임을 확인했다. 바이너리는 내용을 텍스트로 오인하지 않고 PDF renderer, XLSX ZIP/XML/relationship 검사, workbook reader로 구조와 표시 내용을 확인했다.

bundled spreadsheet reader로 7개 workbook을 직접 import/inspect했다. 약 400만 cell인 공모펀드 data workbook은 해당 범용 reader의 메모리 한계를 넘어 OOM이 발생했으나, 프로젝트의 streaming reader와 독립 ZIP CRC/XML/header/row-cell 검사는 전체 파일을 끝까지 성공했다. 이는 파일 손상이 아니라 범용 도구의 materialization 한계이며, 위 행 수와 무결성 결론은 streaming 결과에 근거한다.

파일명은 대소문자/Unicode 정규화 충돌, Windows 예약명, 위험한 ZIP 경로, symlink/hardlink가 없다. 텍스트에는 CRLF, BOM, 누락된 마지막 newline이 없다. 현재 Mac 볼륨은 case-insensitive이므로 향후 Linux CI에서 case-sensitive 검사를 유지해야 한다.

전달 당시 일반 파일은 `0666`, 디렉터리는 `0777`로 과도하게 열려 있었다. 현재 `.git`/`.venv`를 제외한 프로젝트 파일·디렉터리는 일반적인 `0644`/`0755`, 공식 입력 tree는 `0444`/`0555`로 정규화했으며 world-writable 항목이 0개임을 확인했다. 전달 파일의 `com.apple.quarantine`과 `com.apple.provenance` extended attribute는 내용 검증을 방해하지 않고 출처 흔적으로도 쓸 수 있어 보존했다.

## 4. 공식 입력 무결성

| 입력 | 크기 | 구조 | SHA-256 |
|---|---:|---:|---|
| 과제 PDF | 924,413 B | 8쪽 | `3717441e091958b7214db710e0e4b9b8ae15ac6c205cad6e51721214798eb3de` |
| 국내채권 data | 6,836,772 B | 42,394 × 40 | `728f44a567a986d21cf843d711c6c4dfa1a24d05b39c7da0541b981b57ecccf8` |
| 국내채권 schema | 18,021 B | 40 columns | `f0647ce274f94e0474960b98832b98d87838d812b4772f15bdeda2dceff3676b` |
| 국내 ETF/ETN data | 706,081 B | 1,734 × 73 | `0f5706d45f93284bcaac2fa8eaed04db920a7043abaa859e455f06e246d54723` |
| 국내 ETF/ETN schema | 18,970 B | 73 columns | `17ae6befa4f0f5b60481882ff24de1f7729386cef9d9b56f32187e41f1cb00e6` |
| 해외 ETF/ETN data | 2,114,967 B | 5,646 × 49 | `3cec19043f742771e0016d56fe806f19ad78f4295d1ae59192740a78feb2253b` |
| 해외 ETF/ETN schema | 40,216 B | 49 columns | `c6a022dd8a349363c405e7bf47b44f8cc099a92bfafb276b985a5c89d1881162` |
| 공모펀드 data | 30,709,892 B | 95,619 × 45 | `140d1ef0cec918d0b3f7c52c107cb123395594eb089b0cd70bb305709b0f44eb` |
| 공모펀드 schema | 15,596 B | 45 columns | `eedb7e517312234b2825a6752adb2b5f11053f0f4fb93b70e83e87b56ee134e9` |

알려진 이상치는 파일 손상이 아니라 설계가 처리해야 할 공식 데이터 품질 사례다.

- 공모펀드 Excel 84,563행에 malformed item ID 1개
- 양수 buyable quantity가 있으나 snapshot 전에 만기된 채권 71개
- 해외 ETF fee 0, 국내 tracking error 0, 해외 1일 수익률 0 등 suspicious/constant zero
- 공모펀드 `NULL` 문자열 risk와 통화 혼합

## 5. 현재 실제 구현 상태

`docs/implementation/STATUS.md`의 기록과 실제 파일이 일치한다. 제품 구현은 시작되지 않았다.

현재 가능한 것은 handoff 단계 도구뿐이다.

- XLSX ZIP/XML streaming reader
- 공식 입력 manifest 생성/검증
- 네 데이터셋의 동결 audit 재현
- schema workbook catalog 추출
- handoff 파일/schema/seed의 제한된 계약 검사
- handoff 및 bootstrap 계약 pytest 8개

현재 불가능한 것은 다음과 같다.

- `finproof` CLI entry point: `pyproject.toml`에는 선언됐지만 `finproof.cli.main`이 없음
- typed settings/version/error contract
- source lineage ingestion과 normalization/quarantine
- Parquet/DuckDB artifact build
- entity resolution, QueryPlan validator, SQL compiler/executor
- metric/state/comparability policy 실행
- evidence/claim verification/answer renderer
- HyperCLOVA X planner
- FastAPI `/answer`
- Docker, golden benchmark, load/resilience/soak, release manifest

## 6. 남은 phase

### Phase 1 — 데이터 기반

1. settings, version bundle, errors, CLI, CI bootstrap
2. source manifest model과 exact Excel lineage streaming
3. 국내채권/국내 ETF·ETN normalization
4. 해외 ETF·ETN/공모펀드 normalization 및 quarantine
5. 재현 가능한 Parquet/DuckDB와 exact link 47개
6. Phase 1 gate

### Phase 2 — 결정론적 질의·증거 엔진

1. domain contract와 registry loader
2. exact/alias/fuzzy-candidate entity resolution
3. semantic validation, native segment, allowlist SQL
4. executor와 pure-Python differential reference
5. state/zero/tie/currency/period comparability
6. evidence, fail-closed verifier, Korean renderer, service
7. Phase 2 gate

### Phase 3 — HCX와 평가 API

1. CLOVA Studio transport/fixture
2. structured JSON, strict JSON, one repair, rule fallback
3. exact five-string `/answer`와 health/readiness/version
4. timeout/retry/concurrency/cache/logging
5. Docker와 end-to-end test
6. Phase 3 gate

### Phase 4 — 평가·배포·freeze

1. 사람 검수 golden 250~300개
2. paraphrase/metamorphic/differential/adversarial suite
3. ablation, latency/load/resilience, 24~48시간 soak
4. competition compliance와 독립 review
5. clean-room reproduction, release manifest/tag/freeze
6. Phase 4 gate

## 7. 발견한 설계/계약 충돌과 해소 시점

아래 항목은 `docs/10_DECISION_LOG.md`의 A-001~A-014에도 등록했다. 제품 의미는 이번 이관 작업에서 임의로 결정하지 않았다. Phase 1 Task 1은 바로 시작할 수 있고, 각 open 항목은 표의 최초 영향 task 전에만 반드시 해소하면 된다.

| ID | 발견 사항 | 최초 영향 task | 상태 |
|---|---|---|---|
| A-001 | `aggregate` intent에 typed aggregation/grouping/output contract가 없음 | Phase 2 Task 1/3 | open |
| A-002 | SourceRow/evidence locator가 checksum/snapshot/applicable date를 모두 표현하지 않음 | Phase 1 Task 2 | open |
| A-003 | 해외 listed/public-fund eligibility 규칙 미완결 | Phase 2 Task 5 | open |
| A-004 | cache key의 field와 호출 순서가 문서/test 사이에서 불일치 | Phase 3 Task 4 | open |
| A-005 | final commit보다 먼저 release manifest를 만드는 순환·staleness 문제 | Phase 4 Task 5 | open |
| A-006 | product top-k와 currency/policy partition의 적용 순서 미정 | Phase 2 Task 3/5 | open |
| A-007 | health endpoint 이름이 문서별로 다름 | Phase 3 Task 3 | open |
| A-008 | 원본 manifest가 실제로 없는 CI/pre-commit/env template을 포함한다고 주장 | Phase 1 Task 1 | 이관 문구 수정; 파일 생성은 Task 1 |
| A-009 | seed 13개의 `expected_plan`이 canonical 필수 field 누락 | Phase 4 Task 1 또는 재사용 전 | open |
| A-010 | `return_1d`, `risk_grade`와 7개 metric이 field registry로 도달 불가 | Phase 2 Task 1 | open |
| A-011 | golden/evidence/quality schema와 metric registry가 frozen 필드를 모두 강제하지 않음 | Phase 1 Task 2/4, Phase 2 Task 1/6 | open |
| A-012 | provider-compliance 계획이 전체 non-HCX ban보다 좁음 | Phase 3 Task 1 | open |
| A-013 | hidden-answer matching/request-validation 질문이 decision log에 없었음 | organizer 답변 | Q-009/Q-010으로 등록 |
| A-014 | 일부 Phase 3/4 계획이 test-first 순서가 아님 | 각 해당 Phase 3/4 task | open |

## 8. organizer에 확인할 기존 질문

- hidden evaluation의 공모펀드 기본 grain
- suspicious zero의 literal/ranking 처리 기대
- 채권 “매수 가능”의 정확한 의미
- `think_trace`의 정확한 내용/길이
- API timeout/concurrency/retry/size 제한
- 사용 가능한 HyperCLOVA X model/feature
- JSON을 문자열로 직렬화한 context/trace 허용 여부
- freeze 후 동일 image restart/failover 허용 여부

## 9. Mac 환경 변경

설치/생성한 항목:

- Homebrew `uv 0.12.3` arm64
- Homebrew `python@3.12 3.12.13` arm64
- `.python-version` = `3.12`
- `.venv` = Python 3.12.13
- resolver가 생성한 `uv.lock`
- `.gitignore`
- Git `main` 저장소와 초기 기준선 commit
- `source_material/` local mode를 read-only로 변경
- 일반 project 파일/디렉터리를 `0644`/`0755`로 정규화하고 world-writable 항목을 제거

`chmod`의 read-only bit는 Git clone에서 보존되지 않는다. 장기적으로는 checksum gate, write-open 금지, container/CI read-only mount가 필요하다.

현재 Docker는 없다. Phase 1에는 필요하지 않으며 Phase 3 container gate 전에 Apple Silicon Docker Desktop을 설치하면 된다.

Codex sandbox에서는 기본 `~/.cache/uv` 쓰기가 막힐 수 있어 다음처럼 실행했다.

```bash
uv --cache-dir /private/tmp/finproof-uv-cache run <command>
```

일반 Terminal에서는 보통 `uv run <command>`면 충분하다.

## 10. 검증 기록

초기 RED/기준선:

- `python3 tools/verify_handoff.py` — 성공, 단 PyYAML 부재로 fallback 검사
- `python3 tools/audit_source_data.py --check` — 성공, 145,393행
- `uv run pytest -q` — 성공, 7 tests
- `uv run python tools/extract_schema_catalog.py --check` — 성공, 207 columns
- `uv run ruff format --check .` — 실패, 6 files
- `uv run ruff check .` — 실패, 41 findings
- `uv run mypy src tests tools` — 실패, 14 findings

이 Ruff/mypy finding은 transferred baseline을 dependency가 갖춰진 Mac 환경에서 처음 검사했을 때 존재했다. 원래 handoff 보고서도 두 도구를 실행하지 못했다고 기록하지만, 그 사실만으로 각 finding의 인과를 더 강하게 단정하지는 않는다.

품질 수정 후 결과:

- `uv run ruff format --check .` — 성공, 10 files already formatted
- `uv run ruff check .` — 성공, all checks passed
- `uv run mypy src tests tools` — 성공, 10 source files에서 issue 0개
- `uv run pytest -q` — 성공, 7 tests
- `uv run python tools/audit_source_data.py --check` — 성공, 145,393행
- `uv run python tools/verify_handoff.py` — 성공, 61 required files/9 official inputs/41,384,928 bytes, PyYAML parser 활성
- `uv run python tools/extract_schema_catalog.py --check` — 성공, 207 columns

최종 bootstrap 안내 회귀 test의 TDD 기록:

- RED 1: 새 계약 test가 `Makefile`에 `uv sync --frozen --all-groups`가 없어 예상대로 실패
- RED 2: command-order assertion이 pre-install source 검사보다 sync를 먼저 안내하던 manifest에서 예상대로 실패
- GREEN: `Makefile`, `START_HERE.md`, handoff manifest를 잠금 설치와 pre-install 검사 순서로 고친 뒤 focused test 성공

전수 검사 방법과 관찰 증거:

- `git ls-files`와 보고서 부록을 exact path로 대조 — 현재 의미 있는 파일 인벤토리 누락 0개
- `unzip -t`/ZIP CRC 및 XML/relationship parser — XLSX 8개 모두 archive/part 오류 0개
- project streaming reader — 8개 workbook의 header, row/cell structure, audit 값을 끝까지 확인
- bundled spreadsheet reader — 7개 workbook import/inspect 성공; 대형 공모펀드 workbook OOM은 위 streaming 검사로 대체
- `pdfinfo`와 `pdftoppm` — PDF 8쪽, encryption/form/JavaScript 없음; 8개 page render를 전부 육안 확인
- path/encoding/mode/xattr 검사 — collision/symlink/CRLF/BOM 없음, 권한 정규화 후 world-writable 0개

독립 review 반영 후 최종 current-tree 검사:

- `uv sync --frozen --all-groups` — 성공, 67 packages 확인
- `uv run ruff format --check .` — 성공, 10 files already formatted
- `uv run ruff check .` — 성공
- `uv run mypy src tests tools` — 성공, 10 source files에서 issue 0개
- `uv run pytest -q` — 성공, 8 tests
- source audit — 성공, 145,393행/`2026-07-11`
- handoff verify — 성공, 61 required files/9 official inputs/41,384,928 bytes
- schema catalog — 성공, 207 columns
- permission gate와 `git diff --check` — 성공

이 최종 감사 기록 전에 생성된 intermediate commit:

- `68bdd2e1686737eee652c91e8d3751a92e3555a8` — 검증된 handoff와 macOS bootstrap 기준선
- `97a79c3483086e0e25c073e1537181a4d8ea6f6d` — 기존 handoff tool의 Ruff/mypy 부채 정리

## 11. 정확한 다음 작업

제품 코드의 다음 작업은 여전히 **Phase 1, Task 1**이며 현재 workstation에서 바로 시작할 수 있다.

1. Task 1 계획의 file list에 CI workflow, `.env.example`, `.pre-commit-config.yaml`을 명시한다.
2. settings/version/error/CLI와 위 환경 파일을 strict red-green-refactor TDD로 구현한다.
3. 7절의 open 항목은 `docs/10_DECISION_LOG.md`에 지정한 각 최초 영향 task 전에 해소한다. 현재 Task 1을 선행 차단하지 않는다.

## 부록 A. 파일별 전수 확인 인벤토리

아래는 이관 원본의 의미 있는 파일 80개와 이번 macOS bootstrap에서 추가한 파일을 하나씩 확인한 기록이다. `.venv`, test가 다시 만든 ignored cache, `.git` 내부 객체는 이관 원본이나 제품 source가 아니므로 목록에서 제외했다.

### 최상위와 빌드 환경

| 파일 | 역할과 확인 결과 |
|---|---|
| `.gitignore` | macOS/Python/test/editor/secret/generated artifact를 제외하는 이관 후 규칙. |
| `.python-version` | 로컬 Python baseline을 `3.12`로 고정. |
| `AGENTS.md` | 저장소 전체에 적용되는 FinProof 구현 계약과 작업 순서. |
| `CODEX_MASTER_PROMPT.md` | 전체 구현을 처음부터 실행할 때의 master prompt. |
| `CODEX_RESUME_PROMPT.md` | 중단 지점에서 `STATUS.md` 기준으로 재개하는 prompt. |
| `CODEX_REVIEW_PROMPT.md` | 독립 검토와 stop-condition 확인용 prompt. |
| `HANDOFF_PACKAGE_MANIFEST.md` | handoff 구성 설명. 원본의 잘못된 template 포함 주장을 현재/pending 상태로 수정. |
| `Makefile` | sync, lint, type, test, audit 등 개발 명령 wrapper. |
| `README.md` | FinProof의 목적, 원칙, 저장소 지도. |
| `START_HERE.md` | 첫 세션이 읽고 실행해야 할 순서와 현재 handoff 상태. |
| `pyproject.toml` | Python 범위, runtime/dev dependency, Ruff/mypy/pytest, 미구현 CLI entry point. |
| `uv.lock` | 2026-08-13 Mac에서 실제 resolver로 생성한 전체 dependency lock. |

### `config/`

| 파일 | 역할과 확인 결과 |
|---|---|
| `config/answer_policy.yaml` | 결정론적 답변, 근거, 한계 및 warning 정책 seed. |
| `config/datasets.yaml` | 네 데이터셋의 파일/table/snapshot/grain 메타데이터. |
| `config/field_registry.yaml` | 공개 field와 원본 column mapping. 일부 seed/metric 도달성 공백 발견. |
| `config/metric_registry.yaml` | 25개 metric의 단위·기간·정렬 등 seed. frozen prose가 요구하는 일부 세부 필드 없음. |
| `config/planner_catalog.yaml` | HCX planner에 노출할 intent/product/operator vocabulary. |
| `config/quality_rules.yaml` | malformed ID, zero, stale/maturity 등 품질 rule seed. |
| `config/rating_scale.yaml` | 신용등급 정규화와 비교 순서 seed. |
| `config/state_rules.yaml` | 거래/판매/만기 등 상태 판정 seed. 일부 상품 규칙 미완결. |

### 핵심 문서 `docs/`

| 파일 | 역할과 확인 결과 |
|---|---|
| `docs/00_PROJECT_CHARTER.md` | 목표, 성공 기준, 비범위. |
| `docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md` | 공식 요구사항을 설계/test/release 증거에 연결. 미추적 질문 일부 발견. |
| `docs/02_FINAL_FROZEN_DESIGN.md` | 최상위 frozen architecture와 invariant. |
| `docs/03_DATA_AUDIT_BASELINE.md` | 145,393행 및 알려진 데이터 이상치 기준선. |
| `docs/04_DATA_AND_DOMAIN_CONTRACTS.md` | grain, lineage, state, time, metric domain contract. |
| `docs/05_QUERYPLAN_AND_API_CONTRACT.md` | QueryPlan, execution bundle, 정확한 `/answer` response contract. aggregate 구조 공백 발견. |
| `docs/06_METRIC_REGISTRY_POLICY.md` | metric별 단위/zero/tie/aggregation/comparability 요구. |
| `docs/07_TESTING_AND_EVALUATION.md` | 필수 test layer, golden, load/soak gate. |
| `docs/08_SECURITY_OPERATIONS_AND_RELEASE.md` | 위협 모델, 운영 endpoint, release/freeze. manifest 순환 문제 발견. |
| `docs/09_RISK_REGISTER.md` | 품질·모델·운영·일정 위험과 완화책. |
| `docs/10_DECISION_LOG.md` | frozen 결정과 미결 official question. 누락된 미결 사항 발견. |
| `docs/11_DEFINITION_OF_DONE.md` | phase 및 submission 완료 조건. |
| `docs/12_CODE_REVIEW_CHECKLIST.md` | 독립 review 시 확인할 correctness/security/evidence 항목. |
| `docs/13_HANDOFF_VALIDATION_REPORT.md` | 2026-08-07 package 검사 기록과 당시 환경 제약. |

### 진행 상태, 사양, 실행 계획

| 파일 | 역할과 확인 결과 |
|---|---|
| `docs/implementation/PHASE_GATES.md` | 네 phase의 진입/종료 gate. 모두 미통과. |
| `docs/implementation/STATUS.md` | 21개 task/4개 phase gate와 정확한 다음 작업. 이번 감사 기록 추가. |
| `docs/implementation/2026-08-13_MACOS_HANDOFF_AUDIT.md` | 이 문서. 이관, 전수 감사, 환경, 위험, 다음 작업의 단일 보고서. |
| `docs/superpowers/specs/2026-08-07-finproof-design.md` | 구현 가능한 상세 frozen spec. |
| `docs/superpowers/plans/2026-08-07-00-roadmap.md` | Phase 1~4 전체 순서와 checkpoint. |
| `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md` | Phase 1의 strict TDD 계획. 현재 Task 1이 다음 작업. |
| `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md` | Phase 2 질의/정책/증거 엔진 계획. |
| `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md` | Phase 3 HCX/API/운영 계획. endpoint/cache 불일치 발견. |
| `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md` | Phase 4 평가/release 계획. 일부 TDD·manifest 순서 문제 발견. |
| `docs/superpowers/plans/2026-08-13-macos-handoff-and-bootstrap.md` | 이번 Mac 이관 작업의 실행 기록과 경계. |

### 단계별 Codex prompt `prompts/`

| 파일 | 역할과 확인 결과 |
|---|---|
| `prompts/00_INITIAL_KICKOFF.md` | 최초 bootstrap 지시. |
| `prompts/01_DATA_FOUNDATION.md` | Phase 1 실행 지시. |
| `prompts/02_QUERY_ENGINE.md` | Phase 2 실행 지시. |
| `prompts/03_HCX_AND_API.md` | Phase 3 실행 지시. health endpoint 명칭이 normative 문서와 다름. |
| `prompts/04_EVALUATION_AND_RELEASE.md` | Phase 4 평가·freeze 지시. |
| `prompts/99_CODE_REVIEW.md` | phase별 독립 review 지시. |

### 기계 검증 계약 `schemas/`

| 파일 | 역할과 확인 결과 |
|---|---|
| `schemas/api_response.schema.json` | 다섯 문자열 응답을 강제. |
| `schemas/artifact_manifest.schema.json` | build artifact와 source checksum manifest shape. |
| `schemas/evidence_record.schema.json` | claim evidence shape. 일부 source/as-of checksum 필수성 부족. |
| `schemas/execution_trace.schema.json` | 재현 가능한 `think_trace` 구조. |
| `schemas/golden_case.schema.json` | golden case envelope. expected plan/result/answer 내부 제약 부족. |
| `schemas/hcx_query_plan.schema.json` | HCX의 외부 plan output shape. |
| `schemas/quality_issue.schema.json` | quarantine/quality issue shape. raw payload/hash/first detected 공백. |
| `schemas/query_plan.schema.json` | canonical validated QueryPlan. aggregate field 부재 및 seed 불일치. |

### 공식 입력 `source_material/`

| 파일 | 역할과 확인 결과 |
|---|---|
| `source_material/README.md` | ASCII alias와 공식 파일 취급/불변성 설명. |
| `source_material/input_manifest.json` | PDF/XLSX 9개의 size/SHA-256 기준. 모두 일치. |
| `source_material/schema_catalog.json` | schema workbook 207개 열의 정규화 catalog. 재추출 일치. |
| `source_material/competition_task_financial_product_agent.pdf` | 공식 8쪽 과제 문서. 전 페이지 render/structure 검사 정상. |
| `source_material/data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx` | 국내채권 42,394행/40열. CRC·header·내용 구조 정상. |
| `source_material/data/PRBD01N001_schema.xlsx` | 국내채권 40열 schema와 코드값. catalog 일치. |
| `source_material/data/PREF01N001_domestic_etf_20260711_datarows.xlsx` | 국내 ETF/ETN 1,734행/73열. CRC·header·내용 구조 정상. |
| `source_material/data/PREF01N001_schema.xlsx` | 국내 ETF/ETN 73열 schema와 코드값. catalog 일치. |
| `source_material/data/PREF02N001_overseas_etf_20260711_datarows.xlsx` | 해외 ETF/ETN 5,646행/49열. CRC·header·내용 구조 정상. |
| `source_material/data/PREF02N001_schema.xlsx` | 해외 ETF/ETN 49열 schema와 코드값. catalog 일치. |
| `source_material/data/PRFD01N001_public_funds_20260711_datarows.xlsx` | 공모펀드 95,619행/45열. streaming CRC/XML/header 검사 정상. |
| `source_material/data/PRFD01N001_schema.xlsx` | 공모펀드 45열 schema와 코드값. catalog 일치. |

### Python package, test, fixture, 도구

| 파일 | 역할과 확인 결과 |
|---|---|
| `src/finproof/__init__.py` | `__version__ = "0.0.0"`만 있는 package placeholder. |
| `src/finproof/py.typed` | typed package marker. |
| `tests/__init__.py` | test package marker. |
| `tests/contract/__init__.py` | handoff contract test package marker. |
| `tests/contract/test_handoff_package.py` | manifest/audit/schema/schema-seed/bootstrap 안내 contract 8개. 현재 모두 성공. |
| `tests/contracts/README.md` | future recorded contracts의 위치/규칙. |
| `tests/contracts/expected_source_audit.json` | 145,393행과 데이터 이상치의 frozen expected value. |
| `tests/golden/README.md` | seed와 향후 human-reviewed golden set의 구분. |
| `tests/golden/seed_cases.jsonl` | AI 작성 seed 13개. parse되지만 canonical expected plan과 불일치. |
| `tools/__init__.py` | tool module package marker. |
| `tools/xlsx_stream.py` | 공식 XLSX를 materialize하지 않고 읽는 shared XML streaming primitive. |
| `tools/create_input_manifest.py` | 공식 입력 size/SHA manifest 생성기. |
| `tools/audit_source_data.py` | 네 workbook의 행/이상치 audit와 frozen baseline 비교기. |
| `tools/extract_schema_catalog.py` | 네 schema workbook에서 207열 catalog 추출/비교. |
| `tools/verify_handoff.py` | required file, manifest, JSON/YAML/schema/seed의 handoff gate. |
