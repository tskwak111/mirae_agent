"""One end-to-end request deadline and bounded admission."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True, slots=True)
class RequestContext:
    """The one absolute monotonic deadline carried through a request."""

    correlation_id: str
    deadline_at: float
    _clock: Callable[[], float] = monotonic

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_at - self._clock())


class RequestLimiter:
    """Bound end-to-end request work, including queue admission."""

    def __init__(
        self,
        max_in_flight: int = 8,
        deadline_seconds: float = 15.0,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be positive")
        if deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")
        self._semaphore = asyncio.Semaphore(max_in_flight)
        self._deadline_seconds = deadline_seconds
        self._clock = clock

    @asynccontextmanager
    async def acquire(self, *, correlation_id: str) -> AsyncIterator[RequestContext]:
        """Admit one request and release its sole permit even if it is cancelled."""
        context = RequestContext(
            correlation_id=correlation_id,
            deadline_at=self._clock() + self._deadline_seconds,
            _clock=self._clock,
        )
        remaining = context.remaining_seconds()
        if remaining <= 0:
            raise TimeoutError
        await asyncio.wait_for(self._semaphore.acquire(), timeout=remaining)
        try:
            yield context
        finally:
            self._semaphore.release()
