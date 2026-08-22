"""Request-wide deadline and admission behavior."""

import asyncio

import pytest

from finproof.service.limits import RequestLimiter


@pytest.mark.asyncio
async def test_limiter_admits_at_most_its_configured_concurrency() -> None:
    limiter = RequestLimiter(max_in_flight=8, deadline_seconds=1.0)
    entered = 0
    peak = 0
    admitted = asyncio.Event()
    release = asyncio.Event()

    async def request(number: int) -> None:
        nonlocal entered, peak
        async with limiter.acquire(correlation_id=f"corr-{number}"):
            entered += 1
            peak = max(peak, entered)
            if entered == 8:
                admitted.set()
            await release.wait()
            entered -= 1

    tasks = [asyncio.create_task(request(number)) for number in range(16)]
    await admitted.wait()
    assert peak == 8

    release.set()
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_cancelling_admitted_request_releases_its_permit() -> None:
    limiter = RequestLimiter(max_in_flight=1, deadline_seconds=1.0)
    entered = asyncio.Event()

    async def held_request() -> None:
        async with limiter.acquire(correlation_id="corr-held"):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(held_request())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async with limiter.acquire(correlation_id="corr-next") as context:
        assert context.correlation_id == "corr-next"
