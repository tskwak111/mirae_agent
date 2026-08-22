# HyperCLOVA X Planner and Evaluation API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a robust HyperCLOVA X planning boundary and expose the verified deterministic engine through the organizer-compatible evaluation API.

**Architecture:** A provider-specific async HTTP client calls CLOVA Studio Chat Completions v3. Phase 3 implements and fixture-tests the HCX-007 Structured Outputs adapter but keeps it outside runtime composition while Q-006 is open; runtime uses strict JSON, one bounded repair, and then the rule fallback. Every model result enters the same local schema and semantic validator. FastAPI only adapts transport to the HCX-independent core service and returns the exact five-field response.

**Tech Stack:** Python 3.12, httpx, Pydantic, FastAPI, Uvicorn, structlog, pytest-asyncio, respx, Docker.

**Spec:** `docs/02_FINAL_FROZEN_DESIGN.md` and `docs/superpowers/specs/2026-08-07-finproof-design.md`

## Global Constraints

- Phase 2 gate must pass first.
- HyperCLOVA X is the only generative provider in runtime/evaluation.
- Use CLOVA Studio v3 endpoint `POST /v3/chat-completions/{modelName}` through a direct typed adapter.
- Evaluation traffic uses only the fixed official origin `https://clovastudio.stream.ntruss.com`; tests inject `httpx` transports and never configure another provider URL.
- Structured Outputs is valid only for `HCX-007` and is hard-disabled in Phase 3 runtime composition. Recorded fixtures and an optional credentialed smoke may verify capability, but activation requires a later explicit frozen decision; strict JSON and the local rule parser are the Phase 3 runtime paths.
- Do not combine Structured Outputs with Function Calling or thinking in one request.
- No model output executes before local schema and semantic validation.
- Default answer remains deterministic.
- Evaluation response contains exactly five strings unless an official override is recorded.
- Apply Q-005's exact temporary bounds. Preserve the existing 24,000-byte retrieved-context contract by compacting repeated provenance; never truncate evidence or claims.
- A-004: do not implement result caching in Phase 3.
- A-007: expose only the official `GET /answer`; public health/readiness/version endpoints remain deferred.
- A-012: prove the positive HCX-only network boundary in Task 1, not with an inevitably incomplete provider blacklist.
- Deterministic rendering remains the only Phase 3 answer path; defer the optional HCX verbalizer.
- Strict TDD and bounded failure behavior are mandatory.
- For every behavior: write one focused test, observe the expected RED, implement the minimum behavior, observe focused GREEN. Run a task aggregate only after its behavior bundle closes and the full repository gate only for the final candidate.
- Do not update `docs/implementation/STATUS.md` during Tasks 1-5. After the implementation commit and independent 0 Critical / 0 Important review, update closure documentation once.

---

### Task 1: Implement typed CLOVA Studio transport and recorded contract fixtures

**Files:**
- Create: `src/finproof/planner/__init__.py`
- Create: `src/finproof/planner/models.py`
- Create: `src/finproof/planner/hcx_client.py`
- Create: `src/finproof/planner/rate_limits.py`
- Create: `tests/unit/planner/test_hcx_models.py`
- Create: `tests/unit/core/test_hcx_settings.py`
- Create: `tests/integration/planner/test_hcx_client.py`
- Create: `tests/integration/planner/test_live_hcx.py`
- Create: `tests/security/test_runtime_provider_policy.py`
- Create: `tests/fixtures/hcx/structured_success.json`
- Create: `tests/fixtures/hcx/error_429.json`
- Create: `tests/fixtures/hcx/no_content_20400.json`
- Create: `tests/fixtures/hcx/malformed_success.json`
- Modify: `src/finproof/core/settings.py`

**Interfaces:**
- Produces: `HcxRequest`, `HcxResponse`, `HcxUsage`, `HcxRateLimitSnapshot`
- Produces: `async HcxClient.generate(request: HcxRequest, request_id: str) -> HcxResponse`
- Consumes one owner-managed shared `httpx.AsyncClient`; the composition root, not `HcxClient`, closes it.
- `HcxClient` posts only to `https://clovastudio.stream.ntruss.com/v3/chat-completions/{model_name}` with bearer key, JSON content type, and `X-NCP-CLOVASTUDIO-REQUEST-ID`.
- Settings add `hcx_enabled: bool = False`, `hcx_api_key: SecretStr | None = None`, and `hcx_model_name: str = "HCX-007"`; enabled HCX requires a key and model names require the `HCX-` prefix. There is deliberately no Structured Outputs enable flag in Phase 3.

- [ ] **Step 1: Write focused HCX Settings tests**

```python
def test_hcx_settings_fail_closed_and_have_no_structured_toggle(settings_values) -> None:
    disabled = Settings(**settings_values, hcx_enabled=False)
    assert disabled.hcx_api_key is None
    assert "hcx_structured_enabled" not in Settings.model_fields

    with pytest.raises(ValueError, match="API key"):
        Settings(**settings_values, hcx_enabled=True)

    enabled = Settings(
        **settings_values,
        hcx_enabled=True,
        hcx_api_key="secret",
        hcx_model_name="HCX-007",
    )
    assert "secret" not in repr(enabled)
```

The same file rejects non-`HCX-` model names and proves that no environment variable can configure a provider origin.

- [ ] **Step 2: Run the HCX Settings RED**

```bash
uv run pytest tests/unit/core/test_hcx_settings.py -q
```

Expected: selectors fail because the HCX settings fields do not exist.

- [ ] **Step 3: Implement the minimum HCX Settings fields**

Use `SecretStr` for the optional key, require it only when HCX is enabled, validate the model prefix, and expose no base-URL or Structured Outputs toggle.

- [ ] **Step 4: Run focused HCX Settings GREEN**

```bash
uv run pytest tests/unit/core/test_hcx_settings.py -q
```

- [ ] **Step 5: Write focused request-model tests**

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


def test_structured_request_rejects_every_model_except_hcx_007(query_plan_schema) -> None:
    with pytest.raises(ValueError, match="HCX-007"):
        HcxRequest.structured(
            model_name="HCX-DASH-002",
            messages=valid_messages(),
            schema=query_plan_schema,
            max_completion_tokens=1200,
            temperature=0.0,
            seed=17,
        )
```

The same file contains named selectors that reject tools/thinking, multiple system messages, empty model names, `maxCompletionTokens` outside `1..32768`, a canonical request whose UTF-8 byte length plus requested completion tokens exceeds the HCX-007 128,000-token context ceiling, and non-HCX model names for strict JSON requests. UTF-8 input bytes are used only as a conservative upper bound on input tokens; do not invent an unofficial tokenizer.

- [ ] **Step 6: Run the request-model RED**

```bash
uv run pytest tests/unit/planner/test_hcx_models.py -q
```

Expected: collection fails because `finproof.planner.models` is absent.

- [ ] **Step 7: Implement the minimum immutable transport models**

Use `extra="forbid"` and immutable transport models. `HcxRequest.structured()` rejects any model except exact `HCX-007`; the strict JSON constructor accepts only a non-empty `HCX-` model name. Enforce `1 <= maxCompletionTokens <= 32768` and the conservative `canonical_request_utf8_bytes + maxCompletionTokens <= 128000` context budget before transport. Load `schemas/hcx_query_plan.schema.json` exactly; local canonical validation remains mandatory afterward.

- [ ] **Step 8: Run focused request-model GREEN**

```bash
uv run pytest tests/unit/planner/test_hcx_models.py -q
```

- [ ] **Step 9: Write focused HTTP response, failure, and provider-boundary tests**

```python
@pytest.mark.asyncio
async def test_hcx_client_posts_headers_and_parses_message(hcx_client, respx_mock) -> None:
    route = respx_mock.post(
        "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-007"
    ).respond(
        200,
        json=json.loads(Path("tests/fixtures/hcx/structured_success.json").read_text()),
        headers={
            "x-ratelimit-limit-requests": "60",
            "x-ratelimit-remaining-requests": "59",
            "x-ratelimit-reset-requests": "23s",
            "x-ratelimit-limit-tokens": "60000",
            "x-ratelimit-remaining-tokens": "58700",
            "x-ratelimit-reset-tokens": "41s",
        },
    )
    response = await hcx_client.generate(valid_request(), request_id="req-1")
    assert route.called
    sent = route.calls[0].request
    assert sent.headers["Authorization"] == "Bearer secret"
    assert sent.headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] == "req-1"
    assert sent.headers["Content-Type"] == "application/json"
    assert response.status_code == "20000"
    assert response.message_content.startswith("{")
    assert response.rate_limits.remaining_requests == 59
```

`test_hcx_client.py` defines `test_non_20000_api_status_is_typed_error`, `test_20400_without_message_is_no_content_error`, `test_malformed_body_is_typed_error`, `test_oversized_stream_stops_before_json_parse`, parametrized `test_429_api_status_is_rate_limit_error` for `42900`/`42901`/`42902`, parametrized timeout mapping for connect/read/write/pool, and `test_error_log_redacts_key_and_raw_body`. `20400` is never a successful `HcxResponse`.

`tests/security/test_runtime_provider_policy.py` begins with this positive-boundary selector and also asserts that `httpx` is imported only by `src/finproof/planner/hcx_client.py` in production code. The existing production dependency inventory may be a legitimate first-GREEN acceptance; do not manufacture a RED for unchanged behavior.

```python
from finproof.core.settings import Settings
from finproof.planner.hcx_client import HcxClient


def test_runtime_network_boundary_is_fixed_to_hcx() -> None:
    assert HcxClient.API_ORIGIN == "https://clovastudio.stream.ntruss.com"
    assert "hcx_base_url" not in Settings.model_fields
    assert "hcx_structured_enabled" not in Settings.model_fields
```

- [ ] **Step 10: Run the HTTP/client-boundary RED**

```bash
uv run pytest tests/integration/planner/test_hcx_client.py tests/security/test_runtime_provider_policy.py -q
```

Expected: failures because `HcxClient` and its typed transport errors are absent.

- [ ] **Step 11: Implement the minimum async HCX client**

Requirements:

- one shared injected `httpx.AsyncClient`
- connect/read/write/pool timeout set explicitly
- response-size cap before JSON parse
- stream response chunks and abort as soon as the cap is exceeded rather than buffering an unbounded body
- typed handling for HTTP error, API status error, malformed body, and non-success status code
- require native `status.code == "20000"` plus `result.message.content`
- parse usage and all six documented request/token limit, remaining, and reset headers without assuming fixed limits
- never log API key or full raw response at INFO
- no automatic retry inside the low-level client

- [ ] **Step 12: Run focused HTTP GREEN and the HCX-only guard**

```bash
uv run pytest tests/integration/planner/test_hcx_client.py tests/security/test_runtime_provider_policy.py -q
```

`tests/integration/planner/test_live_hcx.py` is marked `slow` and skipped unless `FINPROOF_RUN_LIVE_HCX=1` plus a real key are present. It sends one minimal HCX-007 structured request, requires native status `20000`, parses the returned JSON, and emits no prompt/body/key. It is an external capability check, not part of ordinary CI.

- [ ] **Step 13: Run the Task 1 aggregate and commit**

```bash
uv run pytest tests/unit/core/test_hcx_settings.py tests/unit/planner/test_hcx_models.py tests/integration/planner/test_hcx_client.py tests/security/test_runtime_provider_policy.py -q
uv run ruff check src/finproof/core/settings.py src/finproof/planner tests/unit/core/test_hcx_settings.py tests/unit/planner tests/integration/planner tests/security/test_runtime_provider_policy.py
uv run mypy src/finproof/core/settings.py src/finproof/planner tests/unit/core/test_hcx_settings.py tests/unit/planner tests/integration/planner tests/security/test_runtime_provider_policy.py
```

```bash
git add src/finproof/planner src/finproof/core/settings.py tests/unit/core/test_hcx_settings.py tests/unit/planner tests/integration/planner tests/security/test_runtime_provider_policy.py tests/fixtures/hcx
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
- Create: `tests/unit/planner/test_prompts.py`
- Create: `tests/unit/planner/test_rule_fallback.py`
- Create: `tests/integration/planner/test_planner_service.py`
- Create: `tests/golden/test_seed_plans.py`
- Modify: `schemas/hcx_query_plan.schema.json`

**Interfaces:**
- Produces: `PlanningRequest`, `PlannerAttemptSummary`, and `PlannedQuery`
- Produces: `PlannerProtocol.plan(request: PlanningRequest) -> Awaitable[PlannedQuery]`
- Produces: `StructuredOutputPlanner`, `StrictJsonPlanner`, `RuleFallbackPlanner`
- Produces: `PlannerService.plan(request: PlanningRequest) -> Awaitable[PlannedQuery]`
- `PlannedQuery` includes the canonical `QueryPlan`, `ValidatedQueryPlan`, attempt summary, latency, fallback path, and safe assumptions.

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
        "filters", "metrics", "sort", "aggregation", "top_k", "top_k_scope",
        "needs_clarification", "clarification_reason",
    }
    aggregation = schema["properties"]["aggregation"]
    assert aggregation["type"] == "object"
    assert set(aggregation["required"]) == {"function", "field", "group_by"}
    assert "none" in aggregation["properties"]["function"]["enum"]
    assert "product" in schema["properties"]["result_grain"]["enum"]
```

`test_prompts.py` imports the versioned system prompt and asserts its checksum, compact registry catalog, snapshot assumption, ETF/ETN split, D-027 aggregation rule, heterogeneous grain, top-k-scope rule, and prohibitions on answering, SQL, advice, forecasts, arithmetic, and invented identifiers. It also proves that full source rows, secrets, and local paths never enter a prompt.

- [ ] **Step 2: Run the provider-schema RED**

```bash
uv run pytest tests/unit/planner/test_provider_schema.py tests/unit/planner/test_prompts.py -q
```

Expected: the provider-schema assertion fails because `aggregation` is absent and prompt collection fails because the prompt module is absent.

- [ ] **Step 3: Add `aggregation` to the checked-in HCX schema and version the prompts**

Because the documented HCX subset does not include JSON Schema `null`, represent provider aggregation as one required object with `function`, `field`, and bounded `group_by`. Provider `function="none"` plus `field=""` maps locally to canonical `aggregation=None`; `count` also requires an empty provider field and maps it to canonical `field=None`; `min`/`max`/`sum`/`avg` require a non-empty canonical field. Reject every other shape before `QueryPlan` construction. Do not encode unsupported conditional keywords; `QueryPlan` and `SemanticValidator` enforce the final intent/function/field relationship locally. Load the checked-in provider schema rather than projecting the strict schema at runtime.

System prompt rules explicitly state:

- interpret only; never answer the financial question
- use only registered product/field/metric names included in the compact catalog
- current maps to the supplied snapshot context
- ETF excludes ETN
- no SQL, arithmetic, invented identifier, advice, or forecast
- request clarification only under the documented ambiguity policy
- use `result_grain=product` for heterogeneous native grains
- choose `top_k_scope=per_product_type` for explicit “각각 N개”; use `global` only for one compatible rank
- emit `aggregation={"function":"none","field":"","group_by":[]}` unless `intent=aggregate`; aggregate requests emit exactly one D-027 aggregation object
- output only the requested JSON

Prompt text receives a version ID and checksum.

- [ ] **Step 4: Run focused provider-schema GREEN**

```bash
uv run pytest tests/unit/planner/test_provider_schema.py tests/unit/planner/test_prompts.py -q
```

- [ ] **Step 5: Write focused planner-orchestration tests**

```python
@pytest.mark.asyncio
async def test_valid_structured_output_is_locally_validated_once(
    structured_planner, structured_hcx_success
) -> None:
    result = await structured_planner.plan(
        planning_request("미국 ETF 중 총보수 0.2% 이하 5개")
    )
    assert result.fallback_path == ("structured",)
    assert result.validated_plan.top_k == 5
```

```python
@pytest.mark.asyncio
async def test_malformed_json_gets_one_repair_then_rule_fallback(planner_service, scripted_hcx) -> None:
    scripted_hcx.responses = ["not-json", repaired_but_semantically_invalid_json()]
    result = await planner_service.plan(planning_request("SPY 총보수 알려줘"))
    assert result.attempts.hcx_calls == 2
    assert result.fallback_path == ("strict_json", "repair", "rule_fallback")
    assert result.validated_plan.intent is Intent.LOOKUP
```

The same test file contains exact selectors proving: the provider `none` sentinel becomes canonical `aggregation=None`; an aggregate structured adapter response reaches canonical `QueryPlan` with its `AggregationSpec`; invalid sentinel/count/value-aggregation shapes fail before execution; Phase 3 `PlannerService` never selects or accepts an injected `StructuredOutputPlanner`; `20400`, timeout, malformed response, and 429 reset durations stay within the one shared deadline; parse/schema failure permits at most one repair; semantic failure never executes; unsupported questions and ambiguous return periods fail closed; and no path makes a third HCX request.

`test_rule_fallback.py` contains exact supported lookup, numeric-filter, simple-top-k, ETF-excludes-ETN, current-snapshot, ambiguity, unknown-field, advice, and forecast selectors. Unsupported syntax returns clarification/unsupported and never a guessed executable plan.

- [ ] **Step 6: Run the planner-service RED**

```bash
uv run pytest tests/unit/planner/test_rule_fallback.py tests/integration/planner/test_planner_service.py -q
```

Expected: collection or selectors fail because the planners and service are absent.

- [ ] **Step 7: Implement the minimum bounded planner service**

Rules:

- Phase 3 runtime composition selects `StrictJsonPlanner` when HCX is enabled and never selects `StructuredOutputPlanner`
- `StructuredOutputPlanner` remains directly fixture-testable as a dormant provider adapter but has no production composition path or enable setting
- one initial call
- one repair call only for parse/schema failure when retry budget/time permits
- HTTP 429/timeout follows bounded delay budget; do not multiply retries across layers
- every parsed plan goes through `SemanticValidator`
- rule fallback supports only reviewed patterns: exact lookup, simple top-k, simple numeric filter, and clarification triggers
- fallback never constructs a query from unknown fields

- [ ] **Step 8: Run focused planner-service GREEN**

```bash
uv run pytest tests/unit/planner/test_rule_fallback.py tests/integration/planner/test_planner_service.py -q
```

- [ ] **Step 9: Write seed semantic acceptance tests**

Load every record in `tests/golden/seed_cases.jsonl` that contains an `expected_plan` object and assert the specified canonical intent/product/grain/as-of/top-k-scope/filter/metric/sort semantics. Expected plans are partial semantic expectations, not provider payloads. Normalize safe ordering, not meaning. These `AI-handoff-seed` cases are scaffolding and must be re-reviewed by a human before they count toward the final approved benchmark.

- [ ] **Step 10: Run the seed semantic acceptance checks**

```bash
uv run pytest tests/golden/test_seed_plans.py -q
```

These are acceptance checks over pre-existing seed data and may be first-GREEN; do not alter seeds to manufacture a RED.

- [ ] **Step 11: Run the Task 2 aggregate and commit**

```bash
uv run pytest tests/unit/planner tests/integration/planner tests/golden/test_seed_plans.py -q
uv run ruff check src/finproof/planner tests/unit/planner tests/integration/planner tests/golden
uv run mypy src/finproof/planner tests/unit/planner tests/integration/planner tests/golden
```

```bash
git add src/finproof/planner schemas/hcx_query_plan.schema.json tests/unit/planner tests/integration/planner tests/golden
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
- Create: `tests/unit/api/test_response_model.py`
- Create: `tests/unit/api/test_response_limits.py`
- Create: `tests/integration/api/test_answer_endpoint.py`
- Modify: `src/finproof/evidence/serializer.py`
- Modify: `tests/unit/evidence/test_builder.py`

**Interfaces:**
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`
- Request: `GET /answer?question_id=<string>&question=<string>`
- Response model: exactly `question_id`, `question`, `retrieved_context`, `think_trace`, `answer`, all strings
- No other public route is created while A-007 remains open.

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

`test_response_model.py` also contains named selectors rejecting extra fields, non-string values, `question_id` over 200 characters, questions over 4,000 characters, retrieved context over 24,000 UTF-8 bytes, trace over 16,000 UTF-8 bytes, answers over 12,000 characters, and a complete successful JSON response over 96,000 UTF-8 bytes.

- [ ] **Step 2: Run the response-model RED**

```bash
uv run pytest tests/unit/api/test_response_model.py -q
```

Expected: collection fails because `finproof.api.models` is absent.

- [ ] **Step 3: Implement the strict API model**

Use strict frozen Pydantic fields and `extra="forbid"`. Apply byte limits to UTF-8 encoded strings and check the final canonical JSON bytes; do not rely on character count where Q-005 specifies bytes.

- [ ] **Step 4: Run focused response-model GREEN**

```bash
uv run pytest tests/unit/api/test_response_model.py -q
```

- [ ] **Step 5: Write the retrieved-context compaction RED**

Replace the existing top-k-50 assertion in `tests/unit/evidence/test_builder.py` with a contract that the deterministic JSON remains at most the registry's 24,000-byte limit while every material evidence ID and every Source Fidelity field remains recoverable. `test_response_limits.py` additionally asserts that the serializer reads the checked-in answer-policy limit rather than owning a divergent numeric constant.

```bash
uv run pytest tests/unit/evidence/test_builder.py::test_valid_top_k_50_evidence_and_claim_boundary_serializes tests/unit/api/test_response_limits.py -q
```

Expected: RED because the current serializer permits and the existing fixture produces more than 24,000 bytes.

- [ ] **Step 6: Implement compact lossless evidence serialization**

Deduplicate repeated source table/file/sheet/checksum/snapshot metadata into a stable `sources` array and reference it by integer from direct and derived evidence entries. Preserve evidence ID, field, row, column name/number/letter, raw and normalized values, quality state, transformation rule, applicable date, formula inputs, summaries, limitations, policy IDs, version bundle, and artifact logical hash. Use canonical JSON and reject overflow; never truncate a record, claim, warning, or locator.

- [ ] **Step 7: Run focused retrieved-context GREEN**

```bash
uv run pytest tests/unit/evidence/test_builder.py::test_valid_top_k_50_evidence_and_claim_boundary_serializes tests/unit/api/test_response_limits.py -q
```

- [ ] **Step 8: Write focused endpoint contract tests**

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

The same file contains named selectors for Korean URL encoding, empty/oversized question, missing parameters, bounded JSON strings, framework-standard bounded 422 validation under Q-010, internal-exception redaction, a canonical `think_trace` containing only reproducible execution-stage summaries (never prompts or model reasoning), and a deterministic safe five-field response carrying a correlation ID but no stack trace or local path. It asserts that `/health`, `/health/live`, `/health/ready`, `/ready`, `/version`, `/docs`, `/redoc`, and `/openapi.json` all return 404.

- [ ] **Step 9: Run the endpoint RED**

```bash
uv run pytest tests/integration/api/test_answer_endpoint.py -q
```

Expected: collection or requests fail because the app and route are absent.

- [ ] **Step 10: Implement the app and sole `/answer` route**

Create FastAPI with documentation/schema routes disabled. The transport handler creates a correlation ID, preserves the validated raw echo, calls one injected application orchestrator, serializes the bounded deterministic trace, and maps `AnswerResult` to five strings. FastAPI lifespan opens the expected-verified artifact/session before accepting traffic and closes owned resources on shutdown; startup fails closed for missing or tampered artifacts. No business rule appears in the route.

- [ ] **Step 11: Run focused endpoint GREEN**

```bash
uv run pytest tests/integration/api/test_answer_endpoint.py -q
```

- [ ] **Step 12: Run the Task 3 aggregate and commit**

```bash
uv run pytest tests/unit/api tests/integration/api tests/unit/evidence/test_builder.py -q
uv run ruff check src/finproof/api src/finproof/evidence/serializer.py tests/unit/api tests/integration/api tests/unit/evidence/test_builder.py
uv run mypy src/finproof/api src/finproof/evidence/serializer.py tests/unit/api tests/integration/api tests/unit/evidence/test_builder.py
```

```bash
git add src/finproof/api src/finproof/evidence/serializer.py tests/unit/api tests/integration/api tests/unit/evidence/test_builder.py
git commit -m "feat: expose organizer-compatible evaluation API"
```

---

### Task 4: Add bounded orchestration, rate-limit handling, and observability

**Files:**
- Create: `src/finproof/core/logging.py`
- Create: `src/finproof/core/correlation.py`
- Create: `src/finproof/service/orchestrator.py`
- Create: `src/finproof/service/limits.py`
- Create: `tests/unit/service/test_limits.py`
- Create: `tests/unit/core/test_logging.py`
- Create: `tests/integration/service/test_orchestrator_fallbacks.py`
- Modify: `src/finproof/api/dependencies.py`

**Interfaces:**
- Produces: `async EvaluationOrchestrator.answer(request: AnswerRequest) -> AnswerResult`
- Produces: `RequestLimiter(max_in_flight: int = 8, deadline_seconds: float = 15.0)`
- Reuses: Phase 2 `AnswerService` for deterministic rendering and claim verification.
- Explicitly does not produce a result cache or HCX verbalizer.

- [ ] **Step 1: Write focused deadline and concurrency tests**

```python
@pytest.mark.asyncio
async def test_request_over_deadline_returns_verified_safe_failure(
    orchestrator_factory, slow_planner
) -> None:
    orchestrator = orchestrator_factory(
        planner=slow_planner,
        limiter=RequestLimiter(max_in_flight=8, deadline_seconds=0.01),
    )
    result = await orchestrator.answer(answer_request())
    assert result.trace.validation is TraceValidation.SAFE_FAILURE
    assert "처리" in result.answer.text
```

The same bundle contains selectors for an eight-request semaphore, cancellation-safe permit release, 429 reset delay that fits the remaining budget, retry refusal when it does not fit, database timeout, malformed HCX output, DNS failure, and deterministic fallback without a third provider call.

- [ ] **Step 2: Run the orchestration-limit RED**

```bash
uv run pytest tests/unit/service/test_limits.py tests/integration/service/test_orchestrator_fallbacks.py -q
```

Expected: collection or selectors fail because `RequestLimiter` and `EvaluationOrchestrator` are absent.

- [ ] **Step 3: Implement one monotonic deadline and the minimum orchestrator**

Every stage receives remaining time from one monotonic deadline. One semaphore admission covers the request, cancellation releases it, and retries never create a new budget. Prefer the validated rule fallback over waiting when the remaining budget cannot cover one provider attempt. Compose the planner with the existing deterministic query/evidence/answer services; do not duplicate their policy logic.

- [ ] **Step 4: Run focused orchestration GREEN**

```bash
uv run pytest tests/unit/service/test_limits.py tests/integration/service/test_orchestrator_fallbacks.py -q
```

- [ ] **Step 5: Write the redacted-logging RED**

```python
def test_request_log_is_structured_and_redacted(captured_events) -> None:
    event = captured_events.single("request_complete")
    assert event["correlation_id"] == "corr-1"
    assert set(event["stage_latency_ms"]) == {"planner", "database", "evidence", "render"}
    serialized = json.dumps(event, ensure_ascii=False)
    assert "미국 ETF 총보수 알려줘" not in serialized
    assert "secret" not in serialized
    assert "/Users/" not in serialized
```

- [ ] **Step 6: Run the logging RED**

```bash
uv run pytest tests/unit/core/test_logging.py -q
```

Expected: collection fails because the logging configuration is absent.

- [ ] **Step 7: Implement structured redacted logging**

Logs record correlation ID, stage timings, candidate counts, policy IDs, fallback, and typed error category. They omit API keys, raw HCX bodies, full questions, local paths, and stack traces at INFO.

- [ ] **Step 8: Run focused logging GREEN**

```bash
uv run pytest tests/unit/core/test_logging.py -q
```

- [ ] **Step 9: Run the Task 4 aggregate and commit**

```bash
uv run pytest tests/unit/core/test_logging.py tests/unit/service tests/integration/service/test_orchestrator_fallbacks.py -q
uv run ruff check src/finproof/core src/finproof/service tests/unit/core/test_logging.py tests/unit/service tests/integration/service
uv run mypy src/finproof/core src/finproof/service tests/unit/core/test_logging.py tests/unit/service tests/integration/service
```

```bash
git add src/finproof/core src/finproof/service src/finproof/api/dependencies.py tests/unit/core/test_logging.py tests/unit/service tests/integration/service
git commit -m "feat: bound and observe evaluation orchestration"
```

---

### Task 5: Add Docker, clean startup, and end-to-end API verification

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `tests/contract/test_container_contract.py`
- Create: `tests/e2e/test_evaluation_api.py`
- Create: `tests/e2e/test_container_smoke.py`
- Create: `tests/performance/test_api_load.py`
- Create: `tests/resilience/test_api_soak.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Container starts `uvicorn finproof.api.app:create_app --factory --host 0.0.0.0 --port 8000`
- Startup verifies frozen artifacts before binding the service port.
- Runtime artifacts are mounted read-only; the image contains no raw source data or secrets.
- Container smoke uses disabled-HCX deterministic fallback, not an alternate provider URL or a public health/version route.

- [ ] **Step 1: Write the in-process end-to-end RED**

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

- [ ] **Step 2: Run the end-to-end RED**

```bash
uv run pytest tests/e2e/test_evaluation_api.py -q
```

Expected: the request fails because the real Phase 3 dependency graph is not wired.

- [ ] **Step 3: Wire the minimum application graph**

Use recorded HCX transport and the expected-verified official artifacts for the marked slow variant; regular CI uses a small deterministic artifact issued through the same runtime-session boundary.

- [ ] **Step 4: Run focused end-to-end GREEN**

```bash
uv run pytest tests/e2e/test_evaluation_api.py -q
```

- [ ] **Step 5: Write the container-file RED before creating production files**

```python
def test_container_contract_is_non_root_frozen_and_has_no_secret_or_artifact_copy() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.12.13-slim-bookworm")
    assert "uv==0.12.3" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    assert "USER finproof" in dockerfile
    assert "COPY artifacts" not in dockerfile
    assert "COPY source_material" not in dockerfile
    assert "CLOVA" not in dockerfile
    assert "--factory" in dockerfile
```

The same contract test checks a bounded `.dockerignore`, no shell-form `CMD`, no compose/mock-provider/entrypoint files, and CI jobs for the container, API-load, and short-soak checks. At this step also write `test_container_smoke.py`: its success selector mounts an expected-verified artifact read-only, disables HCX, waits for the port, calls `/answer`, and asserts `/version` is 404; its failure selector mounts a missing/tampered artifact and proves the process exits before opening the port. The dynamic selectors skip unless `FINPROOF_RUN_DOCKER_SMOKE=1` and Docker is available, so ordinary full pytest does not build containers implicitly.

- [ ] **Step 6: Run the container-file RED**

```bash
FINPROOF_RUN_DOCKER_SMOKE=1 uv run pytest tests/contract/test_container_contract.py tests/e2e/test_container_smoke.py -q
```

Expected: `FileNotFoundError` because `Dockerfile` and `.dockerignore` do not exist.

- [ ] **Step 7: Write the minimum container files**

Use `python:3.12.13-slim-bookworm`, install `uv==0.12.3`, perform frozen production-only sync, copy only package/config/schema metadata plus the build-required `README.md`, create a non-root `finproof` user, set `.venv/bin` on `PATH`, and use exec-form `CMD`. Update CI with the contract, container, load, and short-soak jobs proved by Step 5's tests. Do not add Compose or an entrypoint wrapper; FastAPI lifespan already owns startup verification and resource shutdown.

- [ ] **Step 8: Run focused container-file GREEN**

```bash
uv run pytest tests/contract/test_container_contract.py -q
```

- [ ] **Step 9: Run the Docker smoke and fail-closed startup tests**

Build `finproof:phase3` once for this focused GREEN, then run the smoke against that image. The host-side test validates the `/answer` payload against `schemas/api_response.schema.json`, and always removes its container. Docker availability is mandatory at the final candidate gate.

```bash
docker build -t finproof:phase3 .
FINPROOF_RUN_DOCKER_SMOKE=1 FINPROOF_IMAGE=finproof:phase3 uv run pytest tests/e2e/test_container_smoke.py -q -m slow
```

- [ ] **Step 10: Write bounded load and short-soak acceptance checks**

`test_api_load.py` drives eight concurrent recorded-planner requests and asserts bounded admission, exact schemas, zero unsupported claims, and per-stage latency recording; it skips unless `FINPROOF_RUN_API_LOAD=1`. `test_api_soak.py` repeats representative lookup, ranking, cross-product, timeout, 429, malformed-output, and fallback traffic for the duration supplied by `FINPROOF_SOAK_SECONDS` and skips when the variable is absent; it asserts no permit leak, unbounded memory growth, or response-contract drift. These are acceptance tests over completed behavior and may be first-GREEN; do not weaken assertions to create a synthetic RED.

- [ ] **Step 11: Run load and short-soak acceptance checks**

```bash
FINPROOF_RUN_API_LOAD=1 uv run pytest tests/performance/test_api_load.py -q -m performance
FINPROOF_SOAK_SECONDS=30 uv run pytest tests/resilience/test_api_soak.py -q -m slow
```

- [ ] **Step 12: Run the Task 5 aggregate**

```bash
uv run pytest tests/contract/test_container_contract.py tests/e2e/test_evaluation_api.py tests/e2e/test_container_smoke.py -q
uv run ruff check tests/contract/test_container_contract.py tests/e2e tests/performance/test_api_load.py tests/resilience/test_api_soak.py
uv run mypy tests/contract/test_container_contract.py tests/e2e tests/performance/test_api_load.py tests/resilience/test_api_soak.py
```

Do not commit Task 5 yet; Task 6 first verifies the exact implementation candidate.

---

### Task 6: Run the single final gate, bounded review, and closure

**Files:**
- Create after 0C/0I: `docs/API_SPEC.md`
- Modify after 0C/0I: `README.md`
- Modify after 0C/0I: `docs/implementation/STATUS.md`

**Interfaces:**
- Candidate review scope is the Phase 3 diff against the Phase 2 closure commit.
- Only Critical and Important findings block closure.
- A 24-hour soak remains a Phase 4 release prerequisite; the Phase 3 short soak does not claim release readiness.

- [ ] **Step 1: Run the final implementation-candidate gate once**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run pytest tests/integration/api tests/e2e/test_evaluation_api.py -q
FINPROOF_RUN_API_LOAD=1 uv run pytest tests/performance/test_api_load.py -q -m performance
FINPROOF_SOAK_SECONDS=300 uv run pytest tests/resilience/test_api_soak.py -q -m slow
docker build -t finproof:phase3 .
FINPROOF_RUN_DOCKER_SMOKE=1 FINPROOF_IMAGE=finproof:phase3 uv run pytest tests/e2e/test_container_smoke.py -q -m slow
```

The explicit container-smoke command above performs the outside-container `/answer` call and validates `schemas/api_response.schema.json`. When credentials are available, run `FINPROOF_RUN_LIVE_HCX=1 uv run pytest tests/integration/planner/test_live_hcx.py -q -m slow` and record its result as Phase 4 activation evidence; Phase 3 runtime remains hard-disabled for Structured Outputs even when the smoke succeeds.

- [ ] **Step 2: Commit the verified implementation candidate**

```bash
git add src/finproof/planner src/finproof/api src/finproof/core src/finproof/service src/finproof/evidence/serializer.py schemas/hcx_query_plan.schema.json tests Dockerfile .dockerignore .github/workflows/ci.yml
git commit -m "feat: expose verified FinProof evaluation service"
```

- [ ] **Step 3: Run one independent code review**

The reviewer checks only the approved Phase 3 contract and candidate diff. Record Critical, Important, and backlog findings separately. If the result is 0 Critical / 0 Important, stop the review immediately and proceed to closure.

- [ ] **Step 4: Apply at most one focused correction wave when blocked**

For each real Critical/Important finding, write and observe a focused RED, make the minimum correction, run focused GREEN, and run the affected task aggregate. Then rerun the complete Step 1 gate exactly once, commit the correction, and request one scoped re-review. After that re-review, any new finding is classified by the root agent as: direct frozen-contract violation to fix now; regression risk outside approved scope to backlog; or unsupported/over-defensive to reject. Do not create an unbounded review loop.

- [ ] **Step 5: Update closure documentation once after 0C/0I**

`docs/API_SPEC.md` records only `GET /answer`, exact query parameters and five string fields, URL encoding, Q-005 bounds, Q-010 validation behavior, deterministic safe failures, and cURL/Python examples. README records clean clone, frozen sync, artifact build, API run, container run, and focused/full checks. STATUS records exact RED/GREEN selectors, final gate outputs, candidate/review commits, backlog, unresolved official questions, and the exact Phase 4 next task.

```bash
uv run python tools/verify_handoff.py
git diff --check
git add docs/API_SPEC.md README.md docs/implementation/STATUS.md
git commit -m "docs: close Phase 3 implementation"
```
