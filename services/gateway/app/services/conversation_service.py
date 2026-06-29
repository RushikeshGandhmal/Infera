"""Conversation management: list, open/resume, and cancel.

These are read/update operations on the transactional chat data in Postgres.
They power the conversation list, resuming an existing chat, and cancelling one.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Conversation, ConversationStatus, Message


class ConversationNotFound(Exception):
    """Raised when a client references a conversation id that doesn't exist."""


@dataclass
class ConversationListItem:
    """A conversation plus its message count, for list/cancel responses."""

    conversation: Conversation
    message_count: int


async def list_conversations(
    session: AsyncSession,
    *,
    status: ConversationStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ConversationListItem]:
    """Most recently active conversations first, optionally filtered by status."""
    # Count messages per conversation in the same query via a correlated subquery,
    # so listing N conversations stays a single round-trip (no N+1 queries).
    message_count = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .scalar_subquery()
    )

    stmt = select(Conversation, message_count.label("message_count"))
    if status is not None:
        stmt = stmt.where(Conversation.status == status)
    stmt = stmt.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)

    rows = await session.execute(stmt)
    return [ConversationListItem(conversation=c, message_count=n) for c, n in rows.all()]


async def get_conversation(session: AsyncSession, conversation_id: str) -> Conversation:
    """Load a conversation with all its messages (for resuming a chat)."""
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))  # eager-load to avoid async lazy IO
    )
    convo = (await session.execute(stmt)).scalar_one_or_none()
    if convo is None:
        raise ConversationNotFound(conversation_id)
    return convo


async def cancel_conversation(session: AsyncSession, conversation_id: str) -> ConversationListItem:
    """Mark a conversation cancelled. Idempotent: cancelling twice is a no-op."""
    convo = await session.get(Conversation, conversation_id)
    if convo is None:
        raise ConversationNotFound(conversation_id)

    if convo.status is ConversationStatus.ACTIVE:
        convo.status = ConversationStatus.CANCELLED
        await session.commit()
        # `updated_at` is server-computed (onupdate=now()); refresh it inside the
        # async context so serializing the response doesn't trigger lazy IO.
        await session.refresh(convo)

    count = await session.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == convo.id)
    )
    return ConversationListItem(conversation=convo, message_count=count or 0)
