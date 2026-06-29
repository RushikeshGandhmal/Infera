"""Chat endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from infera import InferaClient
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import ChatRequest, ChatResponse, Usage
from ..sdk_client import get_client
from ..services import chat_service

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    client: InferaClient = Depends(get_client),
) -> ChatResponse:
    try:
        outcome = await chat_service.handle_chat(
            session,
            client,
            message=payload.message,
            conversation_id=payload.conversation_id,
            model=payload.model,
        )
    except chat_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except chat_service.ConversationClosed:
        raise HTTPException(status_code=409, detail="Conversation is not active")

    return ChatResponse(
        conversation_id=outcome.conversation_id,
        request_id=outcome.request_id,
        reply=outcome.reply,
        provider=outcome.provider,
        model=outcome.model,
        latency_ms=outcome.latency_ms,
        usage=Usage(
            prompt_tokens=outcome.prompt_tokens,
            completion_tokens=outcome.completion_tokens,
            total_tokens=outcome.total_tokens,
        ),
    )
