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

from infera import ChatResult, InferaClient, InferenceStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import SessionLocal
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


@dataclass
class PreparedTurn:
    conversation_id: str
    model: str
    sdk_messages: list[dict[str, str]]


async def prepare_turn(
    session: AsyncSession,
    *,
    message: str,
    conversation_id: str | None,
    model: str | None,
) -> PreparedTurn:
    """Resolve the conversation, save the user message, and build the context.

    Shared by the streaming and non-streaming paths. Flushes but does not
    commit, so the caller owns the transaction boundary.
    """
    settings = get_settings()
    model = model or settings.default_model
    convo = await _get_or_create_conversation(session, conversation_id, model, message)
    session.add(Message(conversation_id=convo.id, role=MessageRole.USER, content=message))
    await session.flush()
    history = await _load_context(session, convo.id, settings.max_context_messages)
    sdk_messages = [{"role": m.role.value, "content": m.content} for m in history]
    return PreparedTurn(conversation_id=convo.id, model=model, sdk_messages=sdk_messages)


_STATUS_MAP = {
    InferenceStatus.SUCCESS: MessageStatus.COMPLETE,
    InferenceStatus.ERROR: MessageStatus.ERROR,
    InferenceStatus.CANCELLED: MessageStatus.CANCELLED,
}


async def persist_stream_result(conversation_id: str, result: ChatResult) -> None:
    """Save the assistant reply after a streamed turn ends, using its own session.

    The streaming HTTP response holds no DB session open for the whole stream, so
    we open a short-lived one here once we have the final text and metadata.
    """
    async with SessionLocal() as session:
        convo = await session.get(Conversation, conversation_id)
        if convo is None:
            return
        session.add(
            Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=result.text,
                status=_STATUS_MAP.get(result.status, MessageStatus.COMPLETE),
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                request_id=result.request_id,
            )
        )
        convo.model = result.model
        await session.commit()


async def handle_chat(
    session: AsyncSession,
    client: InferaClient,
    *,
    message: str,
    conversation_id: str | None = None,
    model: str | None = None,
) -> ChatOutcome:
    prep = await prepare_turn(
        session, message=message, conversation_id=conversation_id, model=model
    )

    # call the LLM through the SDK.
    result = await client.chat(
        prep.sdk_messages,
        model=prep.model,
        session_id=prep.conversation_id,
        conversation_id=prep.conversation_id,
    )

    # persist the assistant reply, linked to its inference log by request_id.
    convo = await session.get(Conversation, prep.conversation_id)
    session.add(
        Message(
            conversation_id=prep.conversation_id,
            role=MessageRole.ASSISTANT,
            content=result.text,
            status=MessageStatus.COMPLETE,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            request_id=result.request_id,
        )
    )
    if convo is not None:
        convo.model = result.model  # remember the model that actually answered
    await session.commit()

    return ChatOutcome(
        conversation_id=prep.conversation_id,
        request_id=result.request_id,
        reply=result.text,
        provider=result.provider,
        model=result.model,
        latency_ms=result.latency_ms,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
    )
