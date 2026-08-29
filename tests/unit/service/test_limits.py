"""Request-wide deadline and admission behavior."""

import asyncio

import pytest

from finproof.service.limits import RequestDeadline, RequestLimiter


def test_request_deadline_reserves_exactly_two_seconds_for_publication() -> None:
    now = 41.0
    deadline = RequestDeadline.start(clock=lambda: now)

    assert deadline.started_at == now
    assert deadline.work_cutoff_at == now + 293.0
    assert deadline.outer_at == now + 295.0
    assert deadline.remaining_work_seconds() == 293.0
    assert deadline.remaining_outer_seconds() == 295.0


@pytest.mark.asyncio
async def test_limiter_preserves_ingress_deadline_identity() -> None:
    now = 7.0
    deadline = RequestDeadline.start(clock=lambda: now)
    limiter = RequestLimiter(max_in_flight=1)

    async with limiter.acquire(correlation_id="corr", deadline=deadline) as context:
        assert context.deadline is deadline


@pytest.mark.asyncio
async def test_limiter_admits_at_most_its_configured_concurrency() -> None:
    limiter = RequestLimiter(max_in_flight=8)
    entered = 0
    peak = 0
    admitted = asyncio.Event()
    release = asyncio.Event()

    async def request(number: int) -> None:
        nonlocal entered, peak
        async with limiter.acquire(
            correlation_id=f"corr-{number}", deadline=RequestDeadline.start(clock=lambda: 0.0)
        ):
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
    limiter = RequestLimiter(max_in_flight=1)
    entered = asyncio.Event()

    async def held_request() -> None:
        async with limiter.acquire(
            correlation_id="corr-held", deadline=RequestDeadline.start(clock=lambda: 0.0)
        ):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(held_request())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async with limiter.acquire(
        correlation_id="corr-next", deadline=RequestDeadline.start(clock=lambda: 0.0)
    ) as context:
        assert context.correlation_id == "corr-next"
