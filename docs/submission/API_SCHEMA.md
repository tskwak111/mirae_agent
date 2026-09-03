# Organizer API Schema

## Request

```http
GET /answer?question_id=<id>&question=<URL-encoded Korean question>
```

| Parameter | Required | Bound |
|---|---|---|
| `question_id` | yes | 1–200 characters |
| `question` | yes | 1–4,000 characters |

The end-to-end deadline is 295 seconds. Deterministic work stops with a two-second
serialization reserve. Provider transport calls remain bounded by the same deadline.

## Response

HTTP 200 returns exactly five fields and every value is a string:

```json
{
  "question_id": "Q-001",
  "question": "현재 국내 ETF 총보수 알려줘",
  "retrieved_context": "{}",
  "think_trace": "{}",
  "answer": "2026-08-24 배포본 기준 ..."
}
```

- `question_id` and `question` echo the validated request.
- `retrieved_context` is evidence JSON encoded as a string, at most 24,000 UTF-8 bytes.
- `think_trace` is reproducible execution metadata, not hidden chain-of-thought, at
  most 16,000 UTF-8 bytes.
- `answer` is at most 12,000 characters.
- The canonical response is at most 96,000 UTF-8 bytes.

The authoritative JSON Schema is `schemas/api_response.schema.json`.

## Data and model boundary

“Current” means the official 2026-08-24 distribution: domestic products and public
funds through 2026-08-22, overseas products through Korea-time 2026-08-23. Evaluation
mode requires HCX-007 Structured Outputs for intent analysis and final wording. HCX
never executes SQL or calculations; the local validated plan, deterministic engine,
evidence builder, and claim verifier own those operations.

## Failure behavior

- Invalid or missing query parameters return bounded HTTP 422 validation JSON.
- A failure after safe publication is available returns HTTP 500 with the same five
  strings and a generic Korean failure answer.
- No secret, stack trace, unrestricted SQL, provider body, or local path is exposed.
- Documentation, OpenAPI, health, readiness, version, and slash-redirect routes are
  not public.
