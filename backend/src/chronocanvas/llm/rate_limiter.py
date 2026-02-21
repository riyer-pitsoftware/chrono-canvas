import asyncio
import time


class RateLimiter:
    def __init__(self, max_rpm: int = 60, max_concurrent: int = 5):
        self.max_rpm = max_rpm
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        now = time.monotonic()
        self._timestamps = [t for t in self._timestamps if now - t < 60.0]
        if len(self._timestamps) >= self.max_rpm:
            sleep_time = 60.0 - (now - self._timestamps[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        self._timestamps.append(time.monotonic())

    def release(self) -> None:
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()
