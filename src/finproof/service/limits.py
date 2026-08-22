"""One end-to-end request deadline and bounded admission."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass(slots=True)
class RequestContext:
    """The one absolute monotonic deadline carried through a request."""

    correlation_id: str
    deadline_at: float
    _clock: Callable[[], float] = monotonic
    _retained: bool = False

    def retain_permit_until_done(self, worker: asyncio.Future[Any]) -> None:
        """Keep the acquired permit until detached synchronous work has actually ended."""
        if self._retained:
            return
        self._retained = True

        def release(completed: asyncio.Future[Any]) -> None:
            if not completed.cancelled():
                completed.exception()
            self._release()

        worker.add_done_callback(release)

    _release: Callable[[], None] = lambda: None

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
            _release=self._semaphore.release,
        )
        remaining = context.remaining_seconds()
        if remaining <= 0:
            raise TimeoutError
        await asyncio.wait_for(self._semaphore.acquire(), timeout=remaining)
        try:
            yield context
        finally:
            if not context._retained:
                self._semaphore.release()
