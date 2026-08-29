"""One end-to-end request deadline and bounded admission."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Any

REQUEST_DEADLINE_SECONDS = 295.0
SERIALIZATION_RESERVE_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class RequestDeadline:
    """One ingress-issued absolute deadline shared by every request stage."""

    started_at: float
    work_cutoff_at: float
    outer_at: float
    _clock: Callable[[], float]

    @classmethod
    def start(cls, *, clock: Callable[[], float] = monotonic) -> "RequestDeadline":
        started_at = clock()
        return cls(
            started_at=started_at,
            work_cutoff_at=started_at + REQUEST_DEADLINE_SECONDS - SERIALIZATION_RESERVE_SECONDS,
            outer_at=started_at + REQUEST_DEADLINE_SECONDS,
            _clock=clock,
        )

    def remaining_work_seconds(self) -> float:
        return max(0.0, self.work_cutoff_at - self._clock())

    def remaining_outer_seconds(self) -> float:
        return max(0.0, self.outer_at - self._clock())


@dataclass(slots=True)
class RequestContext:
    """The one absolute monotonic deadline carried through a request."""

    correlation_id: str
    deadline: RequestDeadline
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

    def remaining_work_seconds(self) -> float:
        return self.deadline.remaining_work_seconds()


class RequestLimiter:
    """Bound end-to-end request work, including queue admission."""

    def __init__(
        self,
        max_in_flight: int = 8,
    ) -> None:
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be positive")
        self._semaphore = asyncio.Semaphore(max_in_flight)

    @asynccontextmanager
    async def acquire(
        self, *, correlation_id: str, deadline: RequestDeadline
    ) -> AsyncIterator[RequestContext]:
        """Admit one request and release its sole permit even if it is cancelled."""
        context = RequestContext(
            correlation_id=correlation_id,
            deadline=deadline,
            _release=self._semaphore.release,
        )
        remaining = context.remaining_work_seconds()
        if remaining <= 0:
            raise TimeoutError
        await asyncio.wait_for(self._semaphore.acquire(), timeout=remaining)
        try:
            yield context
        finally:
            if not context._retained:
                self._semaphore.release()
