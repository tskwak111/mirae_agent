"""Request correlation shared across transport, orchestration, and logging."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

_CORRELATION_ID: ContextVar[str | None] = ContextVar("finproof_correlation_id", default=None)


def current_correlation_id() -> str:
    """Return the request correlation ID, creating one for direct service calls."""
    return _CORRELATION_ID.get() or uuid4().hex


@contextmanager
def bind_correlation_id(correlation_id: str | None = None) -> Iterator[str]:
    """Bind exactly one safe correlation identifier for a request lifetime."""
    value = correlation_id or uuid4().hex
    token = _CORRELATION_ID.set(value)
    try:
        yield value
    finally:
        _CORRELATION_ID.reset(token)
