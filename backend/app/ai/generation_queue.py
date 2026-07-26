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
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

logger = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")


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
        self._draining_tasks: set[asyncio.Task[None]] = set()

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

    async def execute(
        self,
        slot: _Slot,
        operation: Callable[[], ResultT],
        *,
        timeout: float,
    ) -> ResultT:
        """Run blocking model work without releasing its slot before it truly exits.

        ``asyncio.to_thread`` cannot cancel an already-running worker thread. On an HTTP
        timeout or client cancellation, keep the semaphore occupied in the background so a
        second heavyweight request cannot overlap the still-draining model call.
        """

        await slot.__aenter__()
        task = asyncio.create_task(asyncio.to_thread(operation))
        try:
            result = await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except BaseException:
            if task.done():
                await slot.__aexit__(None, None, None)
            else:
                self._timed_out += 1
                release_task = asyncio.create_task(self._release_when_done(slot, task))
                self._draining_tasks.add(release_task)
                release_task.add_done_callback(self._draining_tasks.discard)
            raise
        await slot.__aexit__(None, None, None)
        return result

    async def _release_when_done(
        self,
        slot: _Slot,
        task: asyncio.Task[ResultT],
    ) -> None:
        try:
            await task
        except BaseException:
            logger.info("A timed-out generation task finished with an error.")
        finally:
            await slot.__aexit__(None, None, None)
