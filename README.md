# FinProof

FinProof is an evidence-first financial-product analysis agent for the 2026 Mirae
Asset Securities AI Festival.

> HyperCLOVA X plans. Deterministic code executes. Evidence proves. Verification blocks unsupported claims.

## Prerequisites

- Python 3.12
- `uv` 0.12.3 or compatible
- Docker for the container checks and deployment
- The official files under `source_material/`

## Clean setup and verified artifacts

```bash
git clone <repository-url> finproof
cd finproof
uv sync --frozen --all-groups
uv run python tools/verify_handoff.py
uv run python tools/audit_source_data.py --check
uv run finproof build-data --clean
```

The build creates the expected-verified runtime tree under `artifacts/`. Official
source files are read-only inputs and are never copied into the container image.

## Run the evaluation API

The safe default disables live HCX and uses the validated deterministic rule fallback:

```bash
FINPROOF_HCX_ENABLED=false uv run uvicorn finproof.api.app:create_app \
  --factory --host 127.0.0.1 --port 8000
```

To enable the strict-JSON HCX planner, operators supply `FINPROOF_HCX_ENABLED`,
`FINPROOF_HCX_API_KEY`, and optionally `FINPROOF_HCX_MODEL_NAME` through the runtime
environment. Do not commit their values. Structured Outputs is not active in the Phase
3 runtime.

The sole public route is documented in [docs/API_SPEC.md](docs/API_SPEC.md). Current
implementation and release status is in
[docs/implementation/STATUS.md](docs/implementation/STATUS.md).

## Run with Docker

```bash
docker build -t finproof:phase3 .
docker run --rm --publish 127.0.0.1:8000:8000 \
  -e FINPROOF_HCX_ENABLED=false \
  --mount "type=bind,src=$(pwd)/artifacts,dst=/app/artifacts,readonly" \
  finproof:phase3
```

For HCX-enabled operation, pass the same HCX environment-variable names to
`docker run` without embedding secret values in the image or command history.

## Checks

Use focused tests while changing one behavior, for example:

```bash
uv run pytest tests/unit/planner/test_rule_fallback.py -q
uv run pytest tests/integration/api/test_answer_endpoint.py -q
```

The mandatory full repository gate is:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

## Core constraints

- HyperCLOVA X is the only generative model allowed in evaluation/runtime code.
- Official data and the `2026-07-11` snapshot are the source of truth.
- Retrieval, filtering, ranking, calculations, evidence, and claim verification are
  deterministic.
- Plain ETF excludes ETN; public-fund default grain is `itm_no`.
- No free-form Text-to-SQL, fuzzy automatic merge, or unsupported investment forecast.
- The evaluation API returns exactly five string fields unless an official override is
  recorded.
