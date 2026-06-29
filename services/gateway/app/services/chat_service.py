"""Chat orchestration: the gateway's core behaviour for one user turn.

Steps for every message:
  1. find or create the conversation
  2. save the user message
  3. build context (recent messages) to send to the model
  4. call the LLM through the SDK
  5. save the assistant reply (with tokens + request_id linking to the log)

The SDK call is the only slow part; the inference log it produces is shipped in
the background and never blocks this request.
"""

from __future__ import annotations

from dataclasses import dataclass

from infera import InferaClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    MessageStatus,
)


class ConversationNotFound(Exception):
    """Raised when a client references a conversation id that doesn't exist."""


class ConversationClosed(Exception):
    """Raised when posting to a cancelled/archived conversation."""


@dataclass
class ChatOutcome:
    conversation_id: str
    request_id: str
    reply: str
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _title_from(text: str, limit: int = 60) -> str:
    text = text.strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


async def _get_or_create_conversation(
    session: AsyncSession, conversation_id: str | None, model: str, first_message: str
) -> Conversation:
    if conversation_id is not None:
        convo = await session.get(Conversation, conversation_id)
        if convo is None:
            raise ConversationNotFound(conversation_id)
        if convo.status is not ConversationStatus.ACTIVE:
            raise ConversationClosed(conversation_id)
        return convo

    convo = Conversation(model=model, title=_title_from(first_message))
    session.add(convo)
    await session.flush()  # assigns convo.id
    return convo


async def _load_context(session: AsyncSession, conversation_id: str, limit: int) -> list[Message]:
    """Most recent `limit` messages, returned oldest-first for the model."""
    rows = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(rows.scalars().all()))


async def handle_chat(
    session: AsyncSession,
    client: InferaClient,
    *,
    message: str,
    conversation_id: str | None = None,
    model: str | None = None,
) -> ChatOutcome:
    settings = get_settings()
    model = model or settings.default_model

    convo = await _get_or_create_conversation(session, conversation_id, model, message)

    # 2. persist the user's message before calling the model.
    session.add(Message(conversation_id=convo.id, role=MessageRole.USER, content=message))
    await session.flush()

    # 3. context = recent history (now includes the message we just saved).
    history = await _load_context(session, convo.id, settings.max_context_messages)
    sdk_messages = [{"role": m.role.value, "content": m.content} for m in history]

    # 4. call the LLM through the SDK.
    result = await client.chat(
        sdk_messages,
        model=model,
        session_id=convo.id,
        conversation_id=convo.id,
    )

    # 5. persist the assistant reply, linked to its inference log by request_id.
    session.add(
        Message(
            conversation_id=convo.id,
            role=MessageRole.ASSISTANT,
            content=result.text,
            status=MessageStatus.COMPLETE,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            request_id=result.request_id,
        )
    )
    convo.model = result.model  # remember the model that actually answered
    await session.commit()

    return ChatOutcome(
        conversation_id=convo.id,
        request_id=result.request_id,
        reply=result.text,
        provider=result.provider,
        model=result.model,
        latency_ms=result.latency_ms,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
    )
