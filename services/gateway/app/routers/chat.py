"""Chat endpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from infera import ChatResult, InferaClient
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


def _sse(data: dict) -> bytes:
    """Format one Server-Sent Event frame."""
    return f"data: {json.dumps(data)}\n\n".encode()


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    client: InferaClient = Depends(get_client),
) -> StreamingResponse:
    """Stream the reply token-by-token over SSE.

    We resolve the conversation and save the user message up front so proper
    HTTP errors (404/409) can be returned before the stream starts. The assistant
    reply is persisted once the stream finishes.
    """
    try:
        prep = await chat_service.prepare_turn(
            session,
            message=payload.message,
            conversation_id=payload.conversation_id,
            model=payload.model,
        )
        await session.commit()
    except chat_service.ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except chat_service.ConversationClosed:
        raise HTTPException(status_code=409, detail="Conversation is not active")

    async def event_stream() -> AsyncIterator[bytes]:
        holder: dict[str, ChatResult] = {}

        def _capture(result: ChatResult) -> None:
            holder["result"] = result

        # Send the conversation id first so the UI can update immediately
        # (important when a new conversation was just created).
        yield _sse({"type": "start", "conversation_id": prep.conversation_id})

        try:
            async for piece in client.stream(
                prep.sdk_messages,
                model=prep.model,
                session_id=prep.conversation_id,
                conversation_id=prep.conversation_id,
                on_complete=_capture,
            ):
                yield _sse({"type": "token", "content": piece})
        except Exception as exc:  # provider/network error mid-stream
            yield _sse({"type": "error", "detail": str(exc)})

        result = holder.get("result")
        if result is not None:
            await chat_service.persist_stream_result(prep.conversation_id, result)
            yield _sse(
                {
                    "type": "done",
                    "conversation_id": prep.conversation_id,
                    "request_id": result.request_id,
                    "provider": result.provider,
                    "model": result.model,
                    "latency_ms": result.latency_ms,
                    "ttft_ms": result.ttft_ms,
                    "usage": {
                        "prompt_tokens": result.usage.prompt_tokens,
                        "completion_tokens": result.usage.completion_tokens,
                        "total_tokens": result.usage.total_tokens,
                    },
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
