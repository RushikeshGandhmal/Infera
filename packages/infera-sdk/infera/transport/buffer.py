"""A fixed-size, non-blocking buffer for outgoing log events.

This is the safety valve that keeps logging from ever slowing the chat path.
Producers call `offer()`, which never waits. If the buffer is full (ingestion is
slow or down), the event is dropped and a counter ticks up — we'd rather lose a
log line than make the user wait.
"""

from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class BoundedBuffer(Generic[T]):
    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self._dropped = 0

    @property
    def dropped(self) -> int:
        """How many events were dropped because the buffer was full."""
        return self._dropped

    @property
    def size(self) -> int:
        return self._queue.qsize()

    def offer(self, item: T) -> bool:
        """Add without blocking. Returns False if dropped (buffer full)."""
        try:
            self._queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            self._dropped += 1
            return False

    async def drain_batch(self, max_items: int, timeout_s: float) -> list[T]:
        """Wait for the first item (up to timeout_s), then grab whatever else is queued.

        This turns a trickle of events into efficient batches, and idles cheaply
        when there's no traffic.
        """
        items: list[T] = []
        try:
            items.append(await asyncio.wait_for(self._queue.get(), timeout=timeout_s))
        except asyncio.TimeoutError:
            return items

        while len(items) < max_items and not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items
