"""The real provider: OpenRouter.

OpenRouter offers an OpenAI-style /chat/completions endpoint that reaches many
upstream models (OpenAI, Anthropic, Google, etc.) with one API key. The model
string carries the provider, e.g. "anthropic/claude-3.5-sonnet", and the response
tells us the model that actually answered.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..schemas import Message, Usage
from .base import Provider, ProviderResult, StreamChunk

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _provider_from_model(model: str) -> str:
    """'anthropic/claude-3.5-sonnet' -> 'anthropic'."""
    if model and "/" in model:
        return model.split("/", 1)[0]
    return "openrouter"


def _usage_from_payload(payload: dict[str, Any]) -> Usage:
    u = payload.get("usage") or {}
    return Usage(
        prompt_tokens=u.get("prompt_tokens", 0) or 0,
        completion_tokens=u.get("completion_tokens", 0) or 0,
        total_tokens=u.get("total_tokens", 0) or 0,
    )


class OpenRouterProvider(Provider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        app_title: Optional[str] = None,
        app_url: Optional[str] = None,
        timeout_s: float = 60.0,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # Optional attribution shown on the OpenRouter dashboard.
        if app_url:
            headers["HTTP-Referer"] = app_url
        if app_title:
            headers["X-Title"] = app_title
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_s)

    def _body(self, messages: list[Message], model: str, stream: bool, **kwargs: Any) -> dict:
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "stream": stream,
        }
        if stream:
            # Ask OpenRouter to send a final chunk with token usage (off by default).
            body["stream_options"] = {"include_usage": True}
        body.update({k: v for k, v in kwargs.items() if v is not None})  # temperature, max_tokens, ...
        return body

    async def chat(self, messages: list[Message], model: str, **kwargs: Any) -> ProviderResult:
        resp = await self._client.post("/chat/completions", json=self._body(messages, model, False, **kwargs))
        resp.raise_for_status()
        data = resp.json()
        actual_model = data.get("model", model)
        return ProviderResult(
            text=data["choices"][0]["message"]["content"],
            model=actual_model,
            provider=_provider_from_model(actual_model),
            usage=_usage_from_payload(data),
            cost_usd=None,  # exact cost is looked up separately; left optional here
            raw=data,
        )

    async def stream(
        self, messages: list[Message], model: str, **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        body = self._body(messages, model, True, **kwargs)
        async with self._client.stream("POST", "/chat/completions", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                # Server-Sent Events: each useful line looks like "data: {...}".
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                delta = (choices[0].get("delta") or {}).get("content") or "" if choices else ""
                usage = _usage_from_payload(chunk) if chunk.get("usage") else None
                if delta or usage:
                    yield StreamChunk(delta=delta, usage=usage, model=chunk.get("model"), raw=chunk)

    def provider_for(self, model: str) -> str:
        return _provider_from_model(model)

    async def aclose(self) -> None:
        await self._client.aclose()
