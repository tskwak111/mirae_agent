# HyperCLOVA X Planner and Evaluation API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a robust HyperCLOVA X planning boundary and expose the verified deterministic engine through the organizer-compatible evaluation API.

**Architecture:** A provider-specific async HTTP client calls CLOVA Studio Chat Completions v3. A structured-output planner is preferred for HCX-007; a strict JSON planner and one bounded repair provide fallback. Every model result enters the same local schema and semantic validator. FastAPI only adapts transport to the HCX-independent core service and returns the exact five-field response.

**Tech Stack:** Python 3.12, httpx, tenacity/bounded custom retry, Pydantic, FastAPI, Uvicorn, structlog, pytest-asyncio, respx, Docker.

## Global Constraints

- Phase 2 gate must pass first.
- HyperCLOVA X is the only generative provider in runtime/evaluation.
- Use CLOVA Studio v3 endpoint `POST /v3/chat-completions/{modelName}` through a direct typed adapter.
- Structured Outputs is enabled only for an account/model that supports it; the seed preference is `HCX-007`.
- Do not combine Structured Outputs with Function Calling or thinking in one request.
- No model output executes before local schema and semantic validation.
- Default answer remains deterministic.
- Evaluation response contains exactly five strings unless an official override is recorded.
- Strict TDD and bounded failure behavior are mandatory.

---

### Task 1: Implement typed CLOVA Studio transport and recorded contract fixtures

**Files:**
- Create: `src/finproof/planner/__init__.py`
- Create: `src/finproof/planner/models.py`
- Create: `src/finproof/planner/hcx_client.py`
- Create: `src/finproof/planner/rate_limits.py`
- Create: `tests/unit/planner/test_hcx_models.py`
- Create: `tests/integration/planner/test_hcx_client.py`
- Create: `tests/fixtures/hcx/structured_success.json`
- Create: `tests/fixtures/hcx/error_429.json`
- Create: `tests/fixtures/hcx/malformed_success.json`
- Modify: `src/finproof/core/settings.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `HcxRequest`, `HcxResponse`, `HcxUsage`, `HcxRateLimitSnapshot`
- Produces: `HcxClient.generate(request: HcxRequest, request_id: str) -> HcxResponse`
- Produces: `HcxClient.close() -> None`
- `HcxClient` posts to `{base_url}/v3/chat-completions/{model_name}` with bearer key and `X-NCP-CLOVASTUDIO-REQUEST-ID`

- [ ] **Step 1: Write failing request serialization tests**

```python
from finproof.planner.models import HcxMessage, HcxRequest


def test_structured_request_uses_v3_camel_case_fields(query_plan_schema) -> None:
    request = HcxRequest.structured(
        model_name="HCX-007",
        messages=(HcxMessage(role="system", content="system"), HcxMessage(role="user", content="question")),
        schema=query_plan_schema,
        max_completion_tokens=1200,
        temperature=0.0,
        seed=17,
    )
    payload = request.to_payload()
    assert payload["responseFormat"] == {"type": "json", "schema": query_plan_schema}
    assert payload["maxCompletionTokens"] == 1200
    assert "tools" not in payload
    assert "thinking" not in payload
```

Add tests that reject a structured request with tools/thinking, multiple system messages, empty API model name, or unbounded token values.

- [ ] **Step 2: Run RED and implement transport models**

```bash
uv run pytest tests/unit/planner/test_hcx_models.py -q
```

Use `extra="forbid"` and immutable transport models. Load the checked-in `schemas/hcx_query_plan.schema.json` exactly for Structured Outputs; do not send the strict canonical schema or dynamically project it at request time. The provider schema uses only the supported subset, while `schemas/query_plan.schema.json` and Pydantic enforce unknown-field, uniqueness, length, and cross-field constraints locally afterward.

- [ ] **Step 3: Write failing HTTP contract tests with `respx`**

```python
@pytest.mark.asyncio
async def test_hcx_client_posts_headers_and_parses_message(hcx_client, respx_mock) -> None:
    route = respx_mock.post("https://example.test/v3/chat-completions/HCX-007").respond(
        200,
        json=json.loads(Path("tests/fixtures/hcx/structured_success.json").read_text()),
        headers={"x-ratelimit-remaining-requests": "59", "x-ratelimit-reset-requests": "23s"},
    )
    response = await hcx_client.generate(valid_request(), request_id="req-1")
    assert route.called
    sent = route.calls[0].request
    assert sent.headers["Authorization"] == "Bearer secret"
    assert sent.headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] == "req-1"
    assert response.message_content.startswith("{")
    assert response.rate_limits.remaining_requests == 59
```

- [ ] **Step 4: Run RED and implement async HTTP client**

```bash
uv run pytest tests/integration/planner/test_hcx_client.py -q
```

Requirements:

- one shared injected `httpx.AsyncClient`
- connect/read/write/pool timeout set explicitly
- response-size cap before JSON parse
- typed handling for HTTP error, API status error, malformed body, and non-success status code
- parse usage and known rate-limit headers without assuming fixed limits
- never log API key or full raw response at INFO
- no automatic retry inside the low-level client

- [ ] **Step 5: Run task checks and commit**

```bash
uv run pytest tests/unit/planner/test_hcx_models.py tests/integration/planner/test_hcx_client.py -q
uv run ruff check src/finproof/planner tests/unit/planner tests/integration/planner
uv run mypy src/finproof/planner tests/unit/planner tests/integration/planner
```

```bash
git add src/finproof/planner src/finproof/core/settings.py tests/unit/planner tests/integration/planner tests/fixtures/hcx docs/implementation/STATUS.md
git commit -m "feat: add typed HyperCLOVA X transport"
```

---

### Task 2: Implement structured/strict JSON planning, bounded repair, and rule fallback

**Files:**
- Create: `src/finproof/planner/prompts.py`
- Create: `src/finproof/planner/provider_schema.py`
- Use: `schemas/hcx_query_plan.schema.json`
- Validate against: `schemas/query_plan.schema.json`
- Create: `src/finproof/planner/structured_planner.py`
- Create: `src/finproof/planner/json_planner.py`
- Create: `src/finproof/planner/rule_fallback.py`
- Create: `src/finproof/planner/service.py`
- Create: `tests/unit/planner/test_provider_schema.py`
- Create: `tests/unit/planner/test_rule_fallback.py`
- Create: `tests/integration/planner/test_planner_service.py`
- Create: `tests/golden/test_seed_plans.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `PlannerProtocol.plan(request: PlanningRequest) -> PlanningResult`
- Produces: `StructuredOutputPlanner`, `StrictJsonPlanner`, `RuleFallbackPlanner`
- Produces: `PlannerService.plan(request: PlanningRequest) -> PlannedQuery`
- `PlannedQuery` includes raw QueryPlan, validated QueryPlan, attempts, latency, fallback path, and safe assumptions

- [ ] **Step 1: Write failing checked-in provider-schema contract tests**

```python
HCX_ALLOWED_SCHEMA_KEYWORDS = {
    "type", "properties", "required", "enum", "format",
    "minimum", "maximum", "minItems", "maxItems", "items", "anyOf",
}


def test_provider_schema_uses_only_supported_subset() -> None:
    schema = build_hcx_query_plan_schema()
    assert schema == json.loads(Path("schemas/hcx_query_plan.schema.json").read_text())
    assert unsupported_schema_keywords(schema, HCX_ALLOWED_SCHEMA_KEYWORDS) == set()
    assert schema["type"] == "object"
    assert set(schema["required"]) == {
        "intent", "product_types", "entities", "as_of_date", "result_grain",
        "filters", "metrics", "sort", "top_k", "top_k_scope",
        "needs_clarification", "clarification_reason",
    }
    assert "product" in schema["properties"]["result_grain"]["enum"]
```

- [ ] **Step 2: Run RED and implement the small HCX schema and versioned prompts**

```bash
uv run pytest tests/unit/planner/test_provider_schema.py -q
```

Load the checked-in provider schema rather than projecting the strict local schema at runtime. Its recursive keyword allowlist is a contract test. Unknown fields, duplicate values, string lengths, cross-field conditions, grain compatibility, and all business semantics remain strict local validation responsibilities.

System prompt rules explicitly state:

- interpret only; never answer the financial question
- use only registered product/field/metric names included in the compact catalog
- current maps to the supplied snapshot context
- ETF excludes ETN
- no SQL, arithmetic, invented identifier, advice, or forecast
- request clarification only under the documented ambiguity policy
- use `result_grain=product` for heterogeneous native grains
- choose `top_k_scope=per_product_type` for explicit “각각 N개”; use `global` only for one compatible rank
- output only the requested JSON

Prompt text receives a version ID and checksum.

- [ ] **Step 3: Write failing planner orchestration tests**

```python
@pytest.mark.asyncio
async def test_valid_structured_output_is_locally_validated_once(planner_service, structured_hcx_success) -> None:
    result = await planner_service.plan(planning_request("미국 ETF 중 총보수 0.2% 이하 5개"))
    assert result.fallback_path == ("structured",)
    assert result.validated_plan.top_k == 5
```

```python
@pytest.mark.asyncio
async def test_malformed_json_gets_one_repair_then_rule_fallback(planner_service, scripted_hcx) -> None:
    scripted_hcx.responses = ["not-json", repaired_but_semantically_invalid_json()]
    result = await planner_service.plan(planning_request("SPY 총보수 알려줘"))
    assert result.attempts.hcx_calls == 2
    assert result.fallback_path == ("structured", "repair", "rule_fallback")
    assert result.validated_plan.intent is Intent.LOOKUP
```

Add tests for timeout, 429 with reset header, unsupported question, ambiguous return period, and no third HCX request.

- [ ] **Step 4: Run RED and implement bounded planner service**

```bash
uv run pytest tests/integration/planner/test_planner_service.py -q
```

Rules:

- preferred planner selected by capability/config
- one initial call
- one repair call only for parse/schema failure when retry budget/time permits
- HTTP 429/timeout follows bounded delay budget; do not multiply retries across layers
- every parsed plan goes through `SemanticValidator`
- rule fallback supports only reviewed patterns: exact lookup, simple top-k, simple numeric filter, and clarification triggers
- fallback never constructs a query from unknown fields

- [ ] **Step 5: Add seed golden-plan tests**

Load every record in `tests/golden/seed_cases.jsonl` that contains an `expected_plan` object and assert the specified canonical intent/product/grain/as-of/top-k-scope/filter/metric/sort semantics. Expected plans are partial semantic expectations, not provider payloads. Normalize safe ordering, not meaning. These `AI-handoff-seed` cases are scaffolding and must be re-reviewed by a human before they count toward the final approved benchmark.

```bash
uv run pytest tests/golden/test_seed_plans.py -q
```

- [ ] **Step 6: Run task quality and commit**

```bash
uv run pytest tests/unit/planner tests/integration/planner tests/golden/test_seed_plans.py -q
uv run ruff check src/finproof/planner tests/unit/planner tests/integration/planner tests/golden
uv run mypy src/finproof/planner tests/unit/planner tests/integration/planner tests/golden
```

```bash
git add src/finproof/planner tests/unit/planner tests/integration/planner tests/golden docs/implementation/STATUS.md
git commit -m "feat: plan financial queries with bounded HCX fallbacks"
```

---

### Task 3: Implement FastAPI app and exact evaluation contract

**Files:**
- Create: `src/finproof/api/__init__.py`
- Create: `src/finproof/api/app.py`
- Create: `src/finproof/api/dependencies.py`
- Create: `src/finproof/api/models.py`
- Create: `src/finproof/api/errors.py`
- Create: `src/finproof/api/routes/__init__.py`
- Create: `src/finproof/api/routes/answer.py`
- Create: `src/finproof/api/routes/health.py`
- Create: `tests/unit/api/test_response_model.py`
- Create: `tests/integration/api/test_answer_endpoint.py`
- Create: `tests/integration/api/test_health_endpoints.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`
- Request: `GET /answer?question_id=<string>&question=<string>`
- Response model: exactly `question_id`, `question`, `retrieved_context`, `think_trace`, `answer`, all strings
- Operations: `/health/live`, `/health/ready`, `/version`

- [ ] **Step 1: Write failing exact response-model tests**

```python
from finproof.api.models import EvaluationResponse


def test_evaluation_response_has_exact_five_string_fields() -> None:
    response = EvaluationResponse(
        question_id="Q1",
        question="질문",
        retrieved_context="{}",
        think_trace="validation=passed",
        answer="답변",
    )
    assert response.model_dump() == {
        "question_id": "Q1",
        "question": "질문",
        "retrieved_context": "{}",
        "think_trace": "validation=passed",
        "answer": "답변",
    }
```

Add rejection tests for extra fields and non-string field values.

- [ ] **Step 2: Run RED and implement strict API models**

```bash
uv run pytest tests/unit/api/test_response_model.py -q
```

- [ ] **Step 3: Write failing endpoint contract tests**

```python
def test_answer_echoes_raw_request_and_returns_exact_schema(test_client, stub_orchestrator) -> None:
    response = test_client.get(
        "/answer",
        params={"question_id": "Q-001", "question": "미국 ETF 총보수 알려줘"},
    )
    assert response.status_code == 200
    assert response.json()["question_id"] == "Q-001"
    assert response.json()["question"] == "미국 ETF 총보수 알려줘"
    assert set(response.json()) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}
```

Add Korean URL encoding, empty/oversized question, missing parameter, finite JSON, and internal exception safe-response tests.

- [ ] **Step 4: Run RED and implement app/dependencies/routes**

```bash
uv run pytest tests/integration/api/test_answer_endpoint.py -q
```

Transport handler creates correlation ID, preserves raw echo, calls one application orchestrator, and maps `AnswerResult` to strings. No business rule appears in the route.

- [ ] **Step 5: Write and implement health/readiness/version tests**

Readiness checks artifact manifest/checksum, read-only DB open, registry validation, and expected version bundle. Liveness only proves process event loop/handler health. `/version` contains no secret and is not constrained to the evaluation five-field schema.

```bash
uv run pytest tests/integration/api/test_health_endpoints.py -q
```

- [ ] **Step 6: Run task checks and commit**

```bash
uv run pytest tests/unit/api tests/integration/api -q
uv run ruff check src/finproof/api tests/unit/api tests/integration/api
uv run mypy src/finproof/api tests/unit/api tests/integration/api
```

```bash
git add src/finproof/api tests/unit/api tests/integration/api docs/implementation/STATUS.md
git commit -m "feat: expose organizer-compatible evaluation API"
```

---

### Task 4: Add bounded orchestration, cache versioning, rate-limit handling, and observability

**Files:**
- Create: `src/finproof/core/logging.py`
- Create: `src/finproof/core/correlation.py`
- Create: `src/finproof/service/orchestrator.py`
- Create: `src/finproof/service/cache.py`
- Create: `src/finproof/service/limits.py`
- Create: `src/finproof/service/verbalizer.py`
- Create: `tests/unit/service/test_cache_key.py`
- Create: `tests/unit/service/test_limits.py`
- Create: `tests/integration/service/test_orchestrator_fallbacks.py`
- Create: `tests/security/test_runtime_provider_policy.py`
- Modify: `src/finproof/api/dependencies.py`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: `EvaluationOrchestrator.answer(request: AnswerRequest) -> AnswerResult`
- Produces: `AnswerCacheKey.from_request(request, versions, normalized_question) -> AnswerCacheKey`
- Produces: `RequestLimiter` for concurrency and deadline budget
- Optional: `VerifiedHcxVerbalizer.verbalize(fact_pack) -> AnswerDraft`; disabled by default

- [ ] **Step 1: Write failing complete cache-key tests**

```python
def test_cache_key_changes_for_every_behavior_version(request, versions) -> None:
    baseline = AnswerCacheKey.from_request(request, "normalized", versions)
    for field in (
        "dataset_version", "metric_registry_version", "state_rule_version",
        "quality_rule_version", "answer_policy_version", "planner_version",
    ):
        changed = versions.model_copy(update={field: increment_version(getattr(versions, field))})
        assert AnswerCacheKey.from_request(request, "normalized", changed) != baseline
```

Also prove `question_id` alone does not affect/define the result cache.

- [ ] **Step 2: Run RED and implement cache key plus bounded in-memory cache interface**

```bash
uv run pytest tests/unit/service/test_cache_key.py -q
```

Cache only verified final results, store version bundle, cap entries/bytes/TTL, and make cache replaceable. Do not cache transient internal-error responses.

- [ ] **Step 3: Write failing deadline/concurrency tests**

```python
@pytest.mark.asyncio
async def test_request_over_deadline_returns_safe_five_field_answer(orchestrator, slow_planner) -> None:
    result = await orchestrator.answer(answer_request(), deadline_seconds=0.01)
    assert result.status == "safe_failure"
    assert "처리" in result.answer
```

Add tests for concurrency semaphore, 429 reset header within budget, retry exceeding budget, and database timeout.

- [ ] **Step 4: Implement one end-to-end deadline budget**

Every stage receives remaining time from one monotonic deadline. Prevent independent retries from exceeding the total. Prefer deterministic/rule fallback over waiting when budget is low.

```bash
uv run pytest tests/unit/service/test_limits.py tests/integration/service/test_orchestrator_fallbacks.py -q
```

- [ ] **Step 5: Add runtime provider compliance test**

```python
def test_runtime_has_no_non_hcx_generative_provider() -> None:
    forbidden = {"openai", "anthropic", "google.generativeai", "groq", "cohere"}
    runtime_files = list(Path("src/finproof").rglob("*.py"))
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in runtime_files)
    assert not forbidden.intersection(imported_top_level_modules(runtime_files))
    assert "api.openai.com" not in text
    assert "api.anthropic.com" not in text
```

Keep the test precise enough not to flag documentation-only words.

- [ ] **Step 6: Implement structured redacted logging and optional verbalizer**

Logs record stage timings, candidate counts, policy IDs, fallback, and errors. Optional verbalizer sees only verified fact pack, cannot change structured claims, and is followed by claim verification; failure falls back to deterministic text.

- [ ] **Step 7: Run task checks and commit**

```bash
uv run pytest tests/unit/service tests/integration/service/test_orchestrator_fallbacks.py tests/security/test_runtime_provider_policy.py -q
uv run ruff check src/finproof/core src/finproof/service tests/unit/service tests/integration/service tests/security
uv run mypy src/finproof/core src/finproof/service tests/unit/service tests/integration/service tests/security
```

```bash
git add src/finproof/core src/finproof/service src/finproof/api/dependencies.py tests docs/implementation/STATUS.md
git commit -m "feat: harden orchestration caching and observability"
```

---

### Task 5: Add Docker, clean startup, and end-to-end API verification

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker-compose.yml`
- Create: `scripts/container-entrypoint.sh`
- Create: `tests/e2e/test_evaluation_api.py`
- Create: `tests/e2e/test_container_smoke.py`
- Create: `docs/API_SPEC.md`
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Container starts `uvicorn finproof.api.app:create_app --factory --host 0.0.0.0 --port 8000`
- Startup verifies frozen artifacts before readiness
- Compose supports local mock HCX only in development profile; evaluation profile uses configured real HCX endpoint

- [ ] **Step 1: Write failing end-to-end API test against an in-process app**

```python
@pytest.mark.asyncio
async def test_full_question_path_returns_verified_contract(e2e_client, recorded_hcx) -> None:
    response = await e2e_client.get(
        "/answer",
        params={"question_id": "E2E-1", "question": "국내 ETF 중 추적오차가 낮은 5개"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}
    assert "공동" in payload["answer"]
    assert "PREF01N001" in payload["retrieved_context"]
```

- [ ] **Step 2: Run RED and wire the real application dependency graph**

```bash
uv run pytest tests/e2e/test_evaluation_api.py -q
```

Use recorded HCX transport and real official artifacts in a marked slow variant; regular CI may use a small deterministic artifact.

- [ ] **Step 3: Write container files**

Use a non-root user, pinned Python 3.12 base image, `uv sync --frozen --no-dev` after `uv.lock` exists, copied source/config/schema, and read-only runtime artifact. Do not bake secrets. Entrypoint verifies manifest then execs Uvicorn.

- [ ] **Step 4: Write and run container smoke test**

`test_container_smoke.py` invokes Docker only when available, builds the image, starts it with a temporary recorded/mock HCX endpoint, waits for readiness, calls `/version` and `/answer`, and always removes the container.

```bash
uv run pytest tests/e2e/test_container_smoke.py -q -m slow
```

- [ ] **Step 5: Document exact API and reproduction**

`docs/API_SPEC.md` contains request query parameters, exact response fields/types, URL-encoding example, safe error behavior, health endpoints, size/time assumptions marked as configurable, and cURL/Python examples. README gives clean clone -> `uv sync` -> build data -> run API -> test.

- [ ] **Step 6: Run Phase 3 gate**

```bash
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
docker build -t finproof:phase3 .
```

Run an external shell call to the started container and validate `schemas/api_response.schema.json`.

- [ ] **Step 7: Update status and commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml scripts tests/e2e docs/API_SPEC.md README.md .github/workflows/ci.yml docs/implementation/STATUS.md
git commit -m "feat: package the FinProof evaluation service"
```
