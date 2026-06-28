"""InferaClient — the one object an app uses.

It calls the provider, times the call, builds a log event, and hands it to the
shipper. The chat path stays fast; logging happens in the background.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Optional, Union

from .instrumentation import CallTimer
from .providers.base import Provider
from .redaction import preview
from .schemas import (
    ChatResult,
    InferenceLogEvent,
    InferenceStatus,
    Message,
    Usage,
    new_request_id,
)
from .transport.shipper import LogShipper

# Callers may pass plain dicts or Message objects.
MessageInput = Union[Message, dict[str, Any]]


def _normalize(messages: list[MessageInput]) -> list[Message]:
    return [m if isinstance(m, Message) else Message(**m) for m in messages]


def _last_user_text(messages: list[Message]) -> str:
    return next((m.content for m in reversed(messages) if m.role.value == "user"), "")


class InferaClient:
    def __init__(
        self,
        provider: Provider,
        *,
        ingestion_url: Optional[str] = None,
        redact_previews: bool = False,
        preview_limit: int = 500,
        auto_start: bool = True,
    ) -> None:
        self._provider = provider
        self._redact = redact_previews
        self._preview_limit = preview_limit
        self._shipper = LogShipper(ingestion_url)
        if auto_start:
            self._shipper.start()

    # ----- lifecycle -----
    def start(self) -> None:
        self._shipper.start()

    async def aclose(self) -> None:
        await self._shipper.stop()
        await self._provider.aclose()

    # ----- helpers -----
    def _previews(self, in_text: str, out_text: str) -> tuple[str, str, bool]:
        in_prev, r1 = preview(in_text, limit=self._preview_limit, do_redact=self._redact)
        out_prev, r2 = preview(out_text, limit=self._preview_limit, do_redact=self._redact)
        return in_prev, out_prev, (r1 or r2)

    def _emit(self, event: InferenceLogEvent) -> None:
        self._shipper.ship(event)

    # ----- non-streaming -----
    async def chat(
        self,
        messages: list[MessageInput],
        model: str,
        *,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        msgs = _normalize(messages)
        request_id = new_request_id()
        timer = CallTimer()
        try:
            result = await self._provider.chat(msgs, model, **kwargs)
        except Exception as exc:
            timer.stop()
            self._emit(self._build_event(
                request_id, session_id, conversation_id, self._provider.name, model,
                InferenceStatus.ERROR, timer, Usage(),
                in_text=_last_user_text(msgs), out_text="",
                error=exc, metadata=metadata,
            ))
            raise
        timer.stop()
        in_prev, out_prev, redacted = self._previews(_last_user_text(msgs), result.text)
        self._emit(InferenceLogEvent(
            request_id=request_id,
            session_id=session_id,
            conversation_id=conversation_id,
            provider=result.provider,
            model=result.model,
            status=InferenceStatus.SUCCESS,
            latency_ms=timer.latency_ms,
            ttft_ms=timer.ttft_ms,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            cost_usd=result.cost_usd,
            input_preview=in_prev,
            output_preview=out_prev,
            redacted=redacted,
            metadata=metadata or {},
        ))
        return ChatResult(
            request_id=request_id,
            text=result.text,
            provider=result.provider,
            model=result.model,
            usage=result.usage,
            status=InferenceStatus.SUCCESS,
            latency_ms=timer.latency_ms,
            ttft_ms=timer.ttft_ms,
            cost_usd=result.cost_usd,
            raw=result.raw,
        )

    # ----- streaming -----
    async def stream(
        self,
        messages: list[MessageInput],
        model: str,
        *,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Yield text pieces as they arrive, then ship one log event at the end."""
        msgs = _normalize(messages)
        request_id = new_request_id()
        timer = CallTimer()
        parts: list[str] = []
        usage = Usage()
        status = InferenceStatus.SUCCESS
        error: Optional[Exception] = None
        try:
            async for chunk in self._provider.stream(msgs, model, **kwargs):
                if chunk.delta:
                    timer.mark_first_token()
                    parts.append(chunk.delta)
                    yield chunk.delta
                if chunk.usage:
                    usage = chunk.usage
        except BaseException as exc:  # includes cancellation
            error = exc if isinstance(exc, Exception) else None
            status = (
                InferenceStatus.CANCELLED
                if exc.__class__.__name__ == "CancelledError"
                else InferenceStatus.ERROR
            )
            raise
        finally:
            timer.stop()
            in_prev, out_prev, redacted = self._previews(_last_user_text(msgs), "".join(parts))
            self._emit(self._build_event(
                request_id, session_id, conversation_id, self._provider.name, model,
                status, timer, usage, in_text=None, out_text=None,
                error=error, metadata=metadata,
                input_preview=in_prev, output_preview=out_prev, redacted=redacted,
            ))

    # ----- shared event builder (errors / streaming) -----
    def _build_event(
        self,
        request_id: str,
        session_id: Optional[str],
        conversation_id: Optional[str],
        provider: str,
        model: str,
        status: InferenceStatus,
        timer: CallTimer,
        usage: Usage,
        *,
        in_text: Optional[str],
        out_text: Optional[str],
        error: Optional[Exception],
        metadata: Optional[dict[str, Any]],
        input_preview: Optional[str] = None,
        output_preview: Optional[str] = None,
        redacted: bool = False,
    ) -> InferenceLogEvent:
        if input_preview is None and in_text is not None:
            input_preview, output_preview, redacted = self._previews(in_text, out_text or "")
        return InferenceLogEvent(
            request_id=request_id,
            session_id=session_id,
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            status=status,
            error_type=type(error).__name__ if error else None,
            error_message=str(error) if error else None,
            latency_ms=timer.latency_ms,
            ttft_ms=timer.ttft_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            input_preview=input_preview,
            output_preview=output_preview,
            redacted=redacted,
            metadata=metadata or {},
        )
