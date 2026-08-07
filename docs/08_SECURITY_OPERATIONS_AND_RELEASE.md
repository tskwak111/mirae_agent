# Security, Operations, and Release Freeze

## 1. Threat model

Untrusted inputs include:

- user question and identifiers
- product names, descriptions, and strategy text
- all official workbook cells, including schema/sample cells, labels, descriptions, and embedded
  strings, for instruction interpretation
- model output
- external demo data
- query parameters and headers

Potential failures include prompt injection through data, SQL injection, policy bypass, secret leakage, denial of service, cache poisoning, unsupported provider use, stale artifact serving, and post-freeze drift.

## 2. Controls

### Model boundary

- system and schema instructions are fixed/versioned
- Official workbook cells retain declared fact and source-lineage authority but are untrusted for
  instructions. Schema/sample cells, labels, descriptions, product text, and embedded strings are
  labeled data and never executable instructions.
- model output must parse and pass semantic validation
- at most one bounded repair attempt
- planner cannot choose SQL, registry versions, execution mode, or source priority

### Query boundary

- field/operator/product/grain allowlists
- parameterized values
- capped filters, top-k, rows, answer bytes, and execution time
- read-only runtime database user/connection
- no arbitrary filesystem/network tool exposed to the model

### API boundary

- maximum question length
- request timeout and concurrency semaphore
- stable safe errors
- no internal stack trace/SQL/path in output
- exact schema and JSON-safe finite values
- question and logs redacted according to configured policy

### Secrets

- environment variables only
- no key in repository, image history, tests, fixtures, or logs
- separate development/evaluation keys where available
- rotate any accidentally exposed key immediately

## 3. Observability

Structured event fields:

```text
correlation_id
question_id_hash
request_started_at
dataset/artifact/policy/planner versions
intent/product/grain
planner attempts and latency
candidate counts by stage
DB/evidence/render latency
fallback path
answer status
error category
```

Do not log raw hidden reasoning. Store full raw question only when explicitly enabled and justified.

Metrics:

- request rate, success, fallback, clarification, unsupported, and error counts
- latency histograms by stage
- HCX status/rate-limit/retry
- cache hit by version bundle
- evidence-verification failure
- readiness and artifact checksum state

## 4. Deployment

Evaluation runtime:

- immutable container image
- official data artifact baked or mounted read-only
- read-only DuckDB connection
- health/live, health/ready, and version endpoints
- restart policy and startup self-check
- no live external data dependency
- public HTTPS endpoint

Readiness requires:

- manifest/checksum verification
- database opens read-only
- all registry schemas validate
- expected version bundle is loaded
- HCX configuration is syntactically present, while transient HCX availability does not make liveness fail

## 5. Release process

1. complete all phase gates
2. run clean-room build from a fresh clone
3. run full tests, source audit, load, and soak
4. create release candidate tag
5. produce artifact manifest with file/image/config/prompt checksums
6. verify endpoint against API schema from an external network
7. apply the internal repository freeze policy to code, source artifacts, prompts, policies,
   environment image, and documentation
8. submit repository commit, image/artifact identity, endpoint, and API spec
9. monitor without behavior-changing deployment

## 6. Post-freeze policy

Official attribution from p.7: submit through the organizer-provided GitHub Organization Private
Repository by `2026-09-06`; code/results may not change after that deadline. The designated
API-active window is `2026-09-07` through `2026-09-20`, subject to organizer change.

The broader freeze on data, prompts, policies, images, documentation, deployment artifacts, and
new builds is an internal repository freeze policy, not verbatim organizer language. Before
freeze, ask the organizer whether these are allowed without disqualification:

- automatic process restart with identical image
- infrastructure failover to identical image/config/artifact
- secret rotation without code change
- certificate renewal

These restart, failover, secret-rotation, and certificate questions remain `OPEN_OFFICIAL`. Until
clarified, prepare failover before freeze and record exact hashes. Never silently deploy a new
build.

## 7. Incident runbook

For an outage:

1. preserve logs and timestamps
2. verify DNS/TLS/process/readiness/artifact checksum
3. restart only the identical approved image if allowed
4. do not hotfix behavior after freeze
5. record action and evidence
6. notify organizer when required

For wrong-answer detection before freeze:

1. add a failing regression test
2. reproduce root cause
3. fix the smallest policy/code boundary
4. rerun golden/differential suite
5. record decision and benchmark delta
