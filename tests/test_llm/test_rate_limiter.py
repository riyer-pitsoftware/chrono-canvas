import asyncio

import pytest

from historylens.llm.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_acquire_release():
    limiter = RateLimiter(max_rpm=100, max_concurrent=2)
    await limiter.acquire()
    limiter.release()


@pytest.mark.asyncio
async def test_rate_limiter_context_manager():
    limiter = RateLimiter(max_rpm=100, max_concurrent=5)
    async with limiter:
        pass  # Should not raise


@pytest.mark.asyncio
async def test_rate_limiter_concurrency():
    limiter = RateLimiter(max_rpm=100, max_concurrent=2)
    results = []

    async def task(n):
        async with limiter:
            results.append(n)
            await asyncio.sleep(0.01)

    await asyncio.gather(task(1), task(2), task(3))
    assert sorted(results) == [1, 2, 3]
