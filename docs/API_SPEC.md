# FinProof Evaluation API

## Public endpoint

FinProof exposes exactly one public endpoint:

```http
GET /answer?question_id=<id>&question=<URL-encoded question>
```

Both query parameters are required, nonempty strings.

| Parameter | Contract |
|---|---|
| `question_id` | 1–200 characters; echoed exactly after URL decoding |
| `question` | 1–4,000 characters; echoed exactly after URL decoding |

Encode Korean text and reserved characters as URL query data. Do not assemble the query
string by concatenating raw user input.

## Successful response

A successful response has exactly these five fields, and every value is a string:

```json
{
  "question_id": "Q-001",
  "question": "현재 미국 ETF 총보수 알려줘",
  "retrieved_context": "{}",
  "think_trace": "{}",
  "answer": "2026-07-11 제공 스냅샷 기준 ..."
}
```

- `question_id` and `question` exactly echo the validated request values.
- `retrieved_context` is a compact JSON string containing answer evidence.
- `think_trace` is a reproducible execution-trace JSON string, not hidden model
  reasoning.
- `answer` is deterministic Korean output backed by the evidence and claim verifier.

“Current” and an omitted as-of date mean the official `2026-07-11` snapshot. They do
not mean real-time market data.

## Temporary bounds

Q-005 remains open with these fail-closed defaults:

| Boundary | Limit |
|---|---:|
| `question_id` | 200 characters |
| `question` | 4,000 characters |
| `retrieved_context` | 24,000 UTF-8 bytes |
| `think_trace` | 16,000 UTF-8 bytes |
| `answer` | 12,000 characters |
| Canonical successful response | 96,000 UTF-8 bytes |
| End-to-end request deadline | 15 seconds |
| In-flight requests per process | 8 |
| Outer HCX retry | At most 1 within the same deadline |
| HCX response before parsing | 256,000 bytes |

Evidence and claims are never silently truncated to meet these bounds. An unsupported
or overflowing result fails safely.

## Validation and failure behavior

Q-010 remains open. Missing, empty, or oversized query parameters currently receive
the framework-standard, bounded HTTP `422` validation response. That response is not
the five-field success envelope and may contain a bounded `detail` list with validation
type, location, and message fields.

An unexpected internal failure returns HTTP `500` with the same exact five string
fields. The answer is the generic safe message `요청을 처리할 수 없습니다.`;
`retrieved_context` is `{}`; and `think_trace` contains a correlation ID and the
`safe_failure` stage. It does not expose secrets, stack traces, SQL, provider bodies,
questions in logs, or local filesystem paths.

No documentation, OpenAPI, health, readiness, or version route is public in Phase 3.
`/docs`, `/redoc`, `/openapi.json`, `/health`, `/health/live`, `/health/ready`,
`/ready`, `/version`, and `/answer/` return `404`.

## cURL example

```bash
curl --get 'http://127.0.0.1:8000/answer' \
  --data-urlencode 'question_id=Q-001' \
  --data-urlencode 'question=현재 미국 ETF 총보수 알려줘'
```

## Python standard-library example

```python
import json
from urllib.parse import urlencode
from urllib.request import urlopen

params = urlencode(
    {
        "question_id": "Q-001",
        "question": "현재 미국 ETF 총보수 알려줘",
    }
)
with urlopen(f"http://127.0.0.1:8000/answer?{params}", timeout=20) as response:
    payload = json.load(response)

assert set(payload) == {
    "question_id",
    "question",
    "retrieved_context",
    "think_trace",
    "answer",
}
```
