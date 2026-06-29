"""Builds the one InferaClient the gateway uses to call the LLM.

If an OpenRouter key is configured we use the real provider; otherwise we fall
back to the mock provider so the gateway still runs end-to-end with no key and
no cost. The client is a process-wide singleton; its background log shipper is
started/stopped by the app lifespan (see main.py).
"""

from __future__ import annotations

from functools import lru_cache

from infera import InferaClient
from infera.providers import MockProvider, OpenRouterProvider

from .config import get_settings


@lru_cache
def get_client() -> InferaClient:
    s = get_settings()
    if s.openrouter_api_key:
        provider = OpenRouterProvider(
            api_key=s.openrouter_api_key,
            base_url=s.openrouter_base_url,
            app_title=s.openrouter_app_title,
            app_url=s.openrouter_app_url,
        )
    else:
        provider = MockProvider()

    # auto_start=False: the shipper's background task is started in the app
    # lifespan, once an event loop is running.
    return InferaClient(
        provider=provider,
        ingestion_url=s.ingestion_url,
        redact_previews=s.redact_previews,
        auto_start=False,
    )
