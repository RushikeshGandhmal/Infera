"""Data shapes used across the SDK.

The key type is `InferenceLogEvent`: the record we ship for every LLM call.
The ingestion API, the database table, and the dashboards all follow this shape,
so it's the single source of truth for "what we log".
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def new_request_id() -> str:
    """A unique id for one LLM call (used for tracing and de-duplication)."""
    return f"req_{uuid.uuid4().hex}"


def utcnow() -> datetime:
    """Current time in UTC. We never store naive timestamps in a log pipeline."""
    return datetime.now(timezone.utc)


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class InferenceStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class Message(BaseModel):
    """One turn in a conversation."""

    role: Role
    content: str


class Usage(BaseModel):
    """Token counts reported by the provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResult(BaseModel):
    """What the app gets back from a non-streaming `chat()` call."""

    request_id: str
    text: str
    provider: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    status: InferenceStatus = InferenceStatus.SUCCESS
    latency_ms: float = 0.0
    ttft_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    raw: Optional[dict[str, Any]] = None


class InferenceLogEvent(BaseModel):
    """The record shipped to the ingestion endpoint for one LLM call."""

    # who / which request
    request_id: str = Field(default_factory=new_request_id)
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None

    # which model answered
    provider: str
    model: str

    # how it went
    status: InferenceStatus
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # how fast
    latency_ms: float = 0.0
    ttft_ms: Optional[float] = None  # time-to-first-token, streaming only

    # how much
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Optional[float] = None

    # short, optionally-redacted snippets for debugging
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    redacted: bool = False

    # when (client time; the server adds its own ingest time)
    created_at: datetime = Field(default_factory=utcnow)

    # any extra context (app version, flags, etc.)
    metadata: dict[str, Any] = Field(default_factory=dict)
