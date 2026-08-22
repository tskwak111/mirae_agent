FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd --system finproof \
    && useradd --system --gid finproof --home-dir /app finproof \
    && pip install --no-cache-dir uv==0.12.3

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
COPY schemas ./schemas

RUN uv sync --frozen --no-dev \
    && mkdir -p source_material/data

USER finproof

CMD ["uvicorn", "finproof.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
