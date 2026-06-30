"use client";

import { useCallback, useRef, useState } from "react";
import { getConversation, streamChat } from "./api";
import { DEFAULT_MODEL } from "./models";
import type { ChatMessage, DoneMeta } from "./types";

// Replace the last assistant message immutably. Used heavily while tokens
// stream in, so it must return a new array each time for React to re-render.
function patchLastAssistant(
  messages: ChatMessage[],
  patch: (m: ChatMessage) => ChatMessage,
): ChatMessage[] {
  const next = [...messages];
  for (let i = next.length - 1; i >= 0; i--) {
    if (next[i].role === "assistant") {
      next[i] = patch(next[i]);
      break;
    }
  }
  return next;
}

export function useChat(onAfterTurn?: (conversationId: string) => void) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [model, setModel] = useState<string>(DEFAULT_MODEL);
  const [lastMeta, setLastMeta] = useState<DoneMeta | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const conversationIdRef = useRef<string | null>(null);
  const selectionVersionRef = useRef(0);
  const loadSeqRef = useRef(0);
  const streamSeqRef = useRef(0);
  const activeStreamRef = useRef<{
    id: number;
    conversationId: string | null;
    selectionVersion: number;
    messages: ChatMessage[];
  } | null>(null);

  const showConversation = useCallback((id: string | null) => {
    conversationIdRef.current = id;
    selectionVersionRef.current += 1;
    setConversationId(id);
  }, []);

  const streamIsVisible = useCallback(
    (stream: { conversationId: string | null; selectionVersion: number }) =>
      stream.conversationId === conversationIdRef.current &&
      (stream.conversationId !== null ||
        stream.selectionVersion === selectionVersionRef.current),
    [],
  );

  const patchActiveStream = useCallback(
    (
      streamId: number,
      patch: (m: ChatMessage) => ChatMessage,
    ) => {
      const stream = activeStreamRef.current;
      if (!stream || stream.id !== streamId) return;

      stream.messages = patchLastAssistant(stream.messages, patch);
      if (streamIsVisible(stream)) {
        setMessages(stream.messages);
      }
    },
    [streamIsVisible],
  );

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const streamId = streamSeqRef.current + 1;
      streamSeqRef.current = streamId;
      const startConversationId = conversationIdRef.current;
      const startSelectionVersion = selectionVersionRef.current;
      const optimisticMessages = [
        ...messages,
        { role: "user" as const, content: trimmed },
        { role: "assistant" as const, content: "", pending: true },
      ];

      // Optimistically show the user message plus an empty assistant bubble
      // that tokens will stream into.
      activeStreamRef.current = {
        id: streamId,
        conversationId: startConversationId,
        selectionVersion: startSelectionVersion,
        messages: optimisticMessages,
      };
      setMessages(optimisticMessages);
      setIsStreaming(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        await streamChat(
          { message: trimmed, conversation_id: startConversationId, model },
          {
            signal: ctrl.signal,
            onStart: (cid) => {
              const stream = activeStreamRef.current;
              if (!stream || stream.id !== streamId) return;

              stream.conversationId = cid;

              // For a new conversation, the server assigns the real id after
              // the stream opens. Only move the visible selection if the user
              // has not navigated away while the request was starting.
              if (
                conversationIdRef.current === startConversationId &&
                selectionVersionRef.current === startSelectionVersion
              ) {
                conversationIdRef.current = cid;
                setConversationId(cid);
              }
            },
            onToken: (t) =>
              patchActiveStream(streamId, (m) => ({
                ...m,
                content: m.content + t,
              })),
            onDone: (meta) => {
              if (conversationIdRef.current === meta.conversation_id) {
                setLastMeta(meta);
              }
              patchActiveStream(streamId, (m) => ({
                ...m,
                pending: false,
                meta: {
                  model: meta.model,
                  latency_ms: meta.latency_ms,
                  ttft_ms: meta.ttft_ms,
                  total_tokens: meta.usage?.total_tokens ?? null,
                },
              }));
              onAfterTurn?.(meta.conversation_id);
            },
            onError: (detail) =>
              patchActiveStream(streamId, (m) => ({
                ...m,
                content: m.content || `⚠️ ${detail}`,
                pending: false,
                error: true,
              })),
          },
        );
      } catch (err) {
        const aborted = (err as Error).name === "AbortError";
        patchActiveStream(streamId, (m) => ({
          ...m,
          content: aborted
            ? m.content + "\n\n_(stopped)_"
            : `⚠️ ${(err as Error).message}`,
          pending: false,
          error: !aborted,
        }));
      } finally {
        if (activeStreamRef.current?.id === streamId) {
          activeStreamRef.current = null;
          setIsStreaming(false);
          abortRef.current = null;
        }
      }
    },
    [
      isStreaming,
      messages,
      model,
      onAfterTurn,
      patchActiveStream,
    ],
  );

  // Stop the in-flight streamed reply (the "cancel a streaming response" UX).
  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    const seq = loadSeqRef.current + 1;
    loadSeqRef.current = seq;
    const detail = await getConversation(id);
    if (seq !== loadSeqRef.current) return;

    showConversation(detail.id);
    if (detail.model) setModel(detail.model);
    const stream = activeStreamRef.current;
    if (stream?.conversationId === detail.id) {
      setMessages(stream.messages);
    } else {
      setMessages(
        detail.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          status: m.status,
        })),
      );
    }
    setLastMeta(null);
  }, [showConversation]);

  const newConversation = useCallback(() => {
    loadSeqRef.current += 1;
    showConversation(null);
    setMessages([]);
    setLastMeta(null);
  }, [showConversation]);

  return {
    conversationId,
    messages,
    isStreaming,
    model,
    setModel,
    lastMeta,
    send,
    stop,
    loadConversation,
    newConversation,
  };
}
