"""Ships log events to the ingestion endpoint in the background.

A background task pulls events from the buffer in batches and POSTs them, with
retries and exponential backoff. The chat path only ever calls `ship()`, which
hands the event to the buffer and returns immediately.

If no ingestion_url is set, the shipper is a no-op (handy for tests).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from ..schemas import InferenceLogEvent
from .buffer import BoundedBuffer

logger = logging.getLogger("infera.shipper")


class LogShipper:
    def __init__(
        self,
        ingestion_url: Optional[str],
        *,
        buffer_maxsize: int = 10_000,
        batch_size: int = 50,
        flush_interval_s: float = 1.0,
        max_retries: int = 3,
        timeout_s: float = 5.0,
    ) -> None:
        self._url = ingestion_url
        self._buffer: BoundedBuffer[InferenceLogEvent] = BoundedBuffer(buffer_maxsize)
        self._batch_size = batch_size
        self._flush_interval_s = flush_interval_s
        self._max_retries = max_retries
        self._timeout_s = timeout_s
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._running = False

    @property
    def dropped(self) -> int:
        return self._buffer.dropped

    def ship(self, event: InferenceLogEvent) -> None:
        """Queue an event for delivery. Never blocks; safe to call from the chat path."""
        if self._url:
            self._buffer.offer(event)

    def start(self) -> None:
        """Start the background delivery loop."""
        if self._running or not self._url:
            return
        self._running = True
        self._client = httpx.AsyncClient(timeout=self._timeout_s)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the loop and try to flush whatever is left."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._flush_remaining()
        if self._client:
            await self._client.aclose()

    async def _run(self) -> None:
        while self._running:
            try:
                batch = await self._buffer.drain_batch(self._batch_size, self._flush_interval_s)
                if batch:
                    await self._send_with_retry(batch)
            except asyncio.CancelledError:
                break
            except Exception:  # never let the loop die on a single failure
                logger.exception("shipper loop error")

    async def _flush_remaining(self) -> None:
        batch = await self._buffer.drain_batch(self._batch_size, timeout_s=0.0)
        if batch:
            await self._send_with_retry(batch)

    async def _send_with_retry(self, batch: list[InferenceLogEvent]) -> None:
        assert self._client is not None
        payload = [e.model_dump(mode="json") for e in batch]
        delay = 0.5
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._client.post(self._url, json={"events": payload})
                resp.raise_for_status()
                return
            except Exception:
                if attempt == self._max_retries:
                    logger.warning("dropping %d events after %d attempts", len(batch), attempt)
                    return
                await asyncio.sleep(delay)
                delay *= 2  # exponential backoff
