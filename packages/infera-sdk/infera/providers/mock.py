"""A fake provider for tests and offline development.

No network, no API key, no cost. It returns a canned reply with realistic-looking
token counts, so the whole pipeline can be exercised without a real model.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from ..schemas import Message, Usage
from .base import Provider, ProviderResult, StreamChunk


def _estimate_tokens(text: str) -> int:
    """Rough guess (~4 chars per token). Good enough for a mock."""
    return max(1, len(text) // 4)


class MockProvider(Provider):
    """Echoes the last user message back with fake metadata."""

    name = "mock"

    def __init__(self, *, reply: str | None = None, chunk_delay_s: float = 0.02) -> None:
        self._reply = reply
        self._chunk_delay_s = chunk_delay_s

    def _build_reply(self, messages: list[Message]) -> str:
        if self._reply is not None:
            return self._reply
        last_user = next((m.content for m in reversed(messages) if m.role.value == "user"), "")
        return f"[mock] You said: {last_user}"

    def _usage(self, messages: list[Message], reply: str) -> Usage:
        prompt = sum(_estimate_tokens(m.content) for m in messages)
        completion = _estimate_tokens(reply)
        return Usage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion)

    async def chat(self, messages: list[Message], model: str, **kwargs: Any) -> ProviderResult:
        reply = self._build_reply(messages)
        await asyncio.sleep(self._chunk_delay_s)  # pretend there's some network latency
        return ProviderResult(
            text=reply,
            model=model,
            provider=self.name,
            usage=self._usage(messages, reply),
            cost_usd=0.0,
            raw={"mock": True},
        )

    async def stream(
        self, messages: list[Message], model: str, **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        reply = self._build_reply(messages)
        words = reply.split(" ")
        for i, word in enumerate(words):
            await asyncio.sleep(self._chunk_delay_s)
            yield StreamChunk(delta=word if i == 0 else f" {word}")
        # Real providers send usage on the final chunk; mirror that here.
        yield StreamChunk(delta="", usage=self._usage(messages, reply))
