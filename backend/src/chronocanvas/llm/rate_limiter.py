import asyncio
import time


class RateLimiter:
    def __init__(self, max_rpm: int = 60, max_concurrent: int = 5):
        self.max_rpm = max_rpm
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        # Phase 1: claim an RPM slot.
        # The lock is held only for the brief read-modify-write on _timestamps.
        # Sleeping is done *outside* the lock so other coroutines can check
        # concurrently and are not blocked for the full sleep duration.
        while True:
            async with self._lock:
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < 60.0]
                if len(self._timestamps) < self.max_rpm:
                    self._timestamps.append(time.monotonic())
                    break
                sleep_time = 60.0 - (now - self._timestamps[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        # Phase 2: claim a concurrency slot.
        # Acquired *after* the RPM check so the slot is held only while the
        # provider call is actually in flight, not during RPM back-off.
        await self._semaphore.acquire()

    def release(self) -> None:
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()
