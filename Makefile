.PHONY: sync verify audit format lint type test check

sync:
	uv sync --frozen --all-groups

verify:
	uv run python tools/verify_handoff.py

audit:
	uv run python tools/audit_source_data.py --check

format:
	uv run ruff format .

lint:
	uv run ruff check .

type:
	uv run mypy src tests tools

test:
	uv run pytest -q

check: verify audit
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy src tests tools
	uv run pytest -q
