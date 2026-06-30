"""Ollama provider using its OpenAI-compatible API."""

from __future__ import annotations

from typing import Optional

from .openrouter import OpenRouterProvider


class OllamaProvider(OpenRouterProvider):
    """Local model provider backed by Ollama.

    Ollama exposes an OpenAI-compatible `/v1/chat/completions` endpoint. The API
    key is ignored by Ollama, but an Authorization header keeps the request shape
    compatible with OpenAI-style clients.
    """

    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        app_title: Optional[str] = None,
        app_url: Optional[str] = None,
        timeout_s: float = 120.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            app_title=app_title,
            app_url=app_url,
            timeout_s=timeout_s,
        )

    def provider_for(self, model: str) -> str:
        return self.name
