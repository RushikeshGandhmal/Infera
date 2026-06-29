"""The provider interface — what every LLM adapter must implement.

The client only talks to this interface, so it doesn't care which model it's
calling. Adding a new provider means writing one class here; nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

from ..schemas import Message, Usage


@dataclass
class StreamChunk:
    """One piece of a streamed reply. The last chunk usually carries the token usage."""

    delta: str = ""
    usage: Optional[Usage] = None
    model: Optional[str] = None  # actual model that answered, when the provider reports it
    raw: Optional[dict[str, Any]] = None


@dataclass
class ProviderResult:
    """The result of a non-streaming call, in the same shape for every provider."""

    text: str
    model: str
    provider: str
    usage: Usage = field(default_factory=Usage)
    cost_usd: Optional[float] = None
    raw: Optional[dict[str, Any]] = None


class Provider(ABC):
    """Base class for all adapters."""

    name: str = "base"

    @abstractmethod
    async def chat(self, messages: list[Message], model: str, **kwargs: Any) -> ProviderResult:
        """Return a complete reply in one shot."""

    @abstractmethod
    def stream(
        self, messages: list[Message], model: str, **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Yield reply chunks as they arrive (implemented as an async generator)."""

    def provider_for(self, model: str) -> str:
        """Upstream provider name for a model. Override when one adapter proxies many."""
        return self.name

    async def aclose(self) -> None:  # noqa: B027 - optional override
        """Release resources like HTTP connections. Optional."""
        return None
