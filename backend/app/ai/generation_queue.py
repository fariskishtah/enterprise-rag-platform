"""Process-level generation concurrency limiter.

On an 8 GB Apple Silicon Mac, running multiple heavy model generation
tasks concurrently causes memory thrashing and potential OOM.  This
module provides an ``asyncio.Semaphore``-backed queue that serialises
generation work and provides introspectable state.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GenerationQueueStats:
    queued: int = 0
    active: int = 0
    completed: int = 0
    timed_out: int = 0
    last_generation_finished: float | None = None


class GenerationQueue:
    """Async semaphore that limits concurrent generation tasks.

    Usage::

        async with generation_queue.acquire(timeout=45):
            result = await asyncio.to_thread(model.generate, prompt)
    """

    def __init__(self, max_concurrent: int = 1, queue_timeout: float = 120.0) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._queue_timeout = queue_timeout
        self._active = 0
        self._queued = 0
        self._completed = 0
        self._timed_out = 0
        self._last_finished: float | None = None

    @property
    def stats(self) -> GenerationQueueStats:
        return GenerationQueueStats(
            queued=self._queued,
            active=self._active,
            completed=self._completed,
            timed_out=self._timed_out,
            last_generation_finished=self._last_finished,
        )

    class _Slot:
        """Context manager returned by :meth:`acquire`."""

        def __init__(self, queue: GenerationQueue) -> None:
            self._queue = queue

        async def __aenter__(self) -> GenerationQueue._Slot:
            self._queue._active += 1
            self._queue._queued = max(0, self._queue._queued - 1)
            return self

        async def __aexit__(self, *exc_info: object) -> None:
            self._queue._active = max(0, self._queue._active - 1)
            self._queue._completed += 1
            self._queue._last_finished = time.time()
            self._queue._semaphore.release()

    async def acquire(self, timeout: float | None = None) -> _Slot:
        """Wait for a generation slot.

        Raises ``asyncio.TimeoutError`` if *timeout* (or the default
        queue timeout) elapses before a slot becomes available.
        """
        effective_timeout = timeout if timeout is not None else self._queue_timeout
        self._queued += 1
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=effective_timeout)
        except TimeoutError:
            self._queued = max(0, self._queued - 1)
            self._timed_out += 1
            logger.warning("Generation queue wait timed out after %.1fs", effective_timeout)
            raise
        return self._Slot(self)
