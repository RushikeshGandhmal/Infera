"""Builds the one InferaClient the gateway uses to call the LLM.

In auto mode, a configured OpenRouter key is used as the primary provider.
Without a key, the gateway uses local Ollama. Mock is kept as an explicit
offline/test provider.
"""

from __future__ import annotations

from functools import lru_cache

from infera import InferaClient
from infera.providers import FallbackProvider, MockProvider, OllamaProvider, OpenRouterProvider

from .config import get_settings


def _openrouter_provider() -> OpenRouterProvider:
    s = get_settings()
    return OpenRouterProvider(
        api_key=s.openrouter_api_key or "",
        base_url=s.openrouter_base_url,
        app_title=s.openrouter_app_title,
        app_url=s.openrouter_app_url,
    )


def _ollama_provider() -> OllamaProvider:
    s = get_settings()
    return OllamaProvider(
        base_url=s.ollama_base_url,
        app_title=s.openrouter_app_title,
        app_url=s.openrouter_app_url,
    )


@lru_cache
def get_client() -> InferaClient:
    s = get_settings()
    selected = s.llm_provider.lower()

    if selected == "mock":
        provider = MockProvider()
    elif selected == "ollama":
        provider = _ollama_provider()
    elif selected == "openrouter":
        provider = _openrouter_provider()
        if s.openrouter_fallback_to_ollama:
            provider = FallbackProvider(
                provider,
                _ollama_provider(),
                fallback_model=s.ollama_model,
            )
    elif s.openrouter_api_key:
        provider = _openrouter_provider()
        if s.openrouter_fallback_to_ollama:
            provider = FallbackProvider(
                provider,
                _ollama_provider(),
                fallback_model=s.ollama_model,
            )
    else:
        provider = _ollama_provider()

    # auto_start=False: the shipper's background task is started in the app
    # lifespan, once an event loop is running.
    return InferaClient(
        provider=provider,
        ingestion_url=s.ingestion_url,
        redact_previews=s.redact_previews,
        auto_start=False,
    )
