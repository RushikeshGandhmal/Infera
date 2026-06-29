"""Request/response shapes for the gateway's HTTP API.

These are the contract the web app talks to. They're intentionally separate from
the database models (which are an internal detail) and from the SDK schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """A user turn. Omit conversation_id to start a new conversation."""

    message: str = Field(min_length=1)
    conversation_id: str | None = None
    model: str | None = None  # falls back to the server default


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """The assistant's reply plus the metadata the UI may want to show."""

    conversation_id: str
    request_id: str
    reply: str
    provider: str
    model: str
    latency_ms: float
    usage: Usage
