"""Request/response shapes for the gateway's HTTP API.

These are the contract the web app talks to. They're intentionally separate from
the database models (which are an internal detail) and from the SDK schemas.
"""

from __future__ import annotations

from datetime import datetime

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


class ConversationSummary(BaseModel):
    """One row in the conversation list (no message bodies)."""

    id: str
    title: str | None
    status: str
    model: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    """A single message when a conversation is opened/resumed."""

    id: str
    role: str
    content: str
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    request_id: str | None
    created_at: datetime


class ConversationDetail(BaseModel):
    """A full conversation with its messages, used to resume a chat."""

    id: str
    title: str | None
    status: str
    model: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]
