"""Provider wrapper that falls back before a response has started."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..schemas import Message
from .base import Provider, ProviderResult, StreamChunk


class FallbackProvider(Provider):
    """Try a primary provider, then a fallback provider if the call fails.

    Streaming fallback only happens if the primary provider fails before yielding
    any text. Once tokens have been sent to the user, switching providers would
    produce a mixed answer, so the original error is allowed to surface.
    """

    name = "fallback"

    def __init__(
        self,
        primary: Provider,
        fallback: Provider,
        *,
        fallback_model: str | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._fallback_model = fallback_model
        self.name = f"{primary.name}_with_{fallback.name}_fallback"

    async def chat(self, messages: list[Message], model: str, **kwargs: Any) -> ProviderResult:
        try:
            return await self._primary.chat(messages, model, **kwargs)
        except Exception:
            return await self._fallback.chat(messages, self._fallback_model or model, **kwargs)

    async def stream(
        self, messages: list[Message], model: str, **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        yielded = False
        try:
            async for chunk in self._primary.stream(messages, model, **kwargs):
                if chunk.delta:
                    yielded = True
                yield chunk
        except Exception:
            if yielded:
                raise
            async for chunk in self._fallback.stream(
                messages, self._fallback_model or model, **kwargs
            ):
                if chunk.model is None:
                    chunk.model = self._fallback_model or model
                yield chunk

    def provider_for(self, model: str) -> str:
        if self._fallback_model and model == self._fallback_model:
            return self._fallback.provider_for(model)
        return self._primary.provider_for(model)

    async def aclose(self) -> None:
        await self._primary.aclose()
        await self._fallback.aclose()
