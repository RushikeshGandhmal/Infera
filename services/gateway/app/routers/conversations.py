"""Conversation endpoints: list, resume, and cancel."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import ConversationStatus
from ..schemas import ConversationDetail, ConversationSummary, MessageOut
from ..services import conversation_service
from ..services.conversation_service import ConversationListItem

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_summary(item: ConversationListItem) -> ConversationSummary:
    c = item.conversation
    return ConversationSummary(
        id=c.id,
        title=c.title,
        status=c.status.value,
        model=c.model,
        message_count=item.message_count,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    status: ConversationStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationSummary]:
    items = await conversation_service.list_conversations(
        session, status=status, limit=limit, offset=offset
    )
    return [_to_summary(i) for i in items]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    try:
        convo = await conversation_service.get_conversation(session, conversation_id)
    except conversation_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetail(
        id=convo.id,
        title=convo.title,
        status=convo.status.value,
        model=convo.model,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role.value,
                content=m.content,
                status=m.status.value,
                prompt_tokens=m.prompt_tokens,
                completion_tokens=m.completion_tokens,
                request_id=m.request_id,
                created_at=m.created_at,
            )
            for m in convo.messages
        ],
    )


@router.post("/{conversation_id}/cancel", response_model=ConversationSummary)
async def cancel_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> ConversationSummary:
    try:
        item = await conversation_service.cancel_conversation(session, conversation_id)
    except conversation_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _to_summary(item)
