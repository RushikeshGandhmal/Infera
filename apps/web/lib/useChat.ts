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

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      // Optimistically show the user message plus an empty assistant bubble
      // that tokens will stream into.
      setMessages((prev) => [
        ...prev,
        { role: "user", content: trimmed },
        { role: "assistant", content: "", pending: true },
      ]);
      setIsStreaming(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        await streamChat(
          { message: trimmed, conversation_id: conversationId, model },
          {
            signal: ctrl.signal,
            onStart: (cid) => setConversationId(cid),
            onToken: (t) =>
              setMessages((prev) =>
                patchLastAssistant(prev, (m) => ({
                  ...m,
                  content: m.content + t,
                })),
              ),
            onDone: (meta) => {
              setLastMeta(meta);
              setMessages((prev) =>
                patchLastAssistant(prev, (m) => ({
                  ...m,
                  pending: false,
                  meta: {
                    model: meta.model,
                    latency_ms: meta.latency_ms,
                    ttft_ms: meta.ttft_ms,
                    total_tokens: meta.usage?.total_tokens ?? null,
                  },
                })),
              );
              onAfterTurn?.(meta.conversation_id);
            },
            onError: (detail) =>
              setMessages((prev) =>
                patchLastAssistant(prev, (m) => ({
                  ...m,
                  content: m.content || `⚠️ ${detail}`,
                  pending: false,
                  error: true,
                })),
              ),
          },
        );
      } catch (err) {
        const aborted = (err as Error).name === "AbortError";
        setMessages((prev) =>
          patchLastAssistant(prev, (m) => ({
            ...m,
            content: aborted ? m.content + "\n\n_(stopped)_" : `⚠️ ${(err as Error).message}`,
            pending: false,
            error: !aborted,
          })),
        );
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [conversationId, model, isStreaming, onAfterTurn],
  );

  // Stop the in-flight streamed reply (the "cancel a streaming response" UX).
  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    const detail = await getConversation(id);
    setConversationId(detail.id);
    if (detail.model) setModel(detail.model);
    setMessages(
      detail.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        status: m.status,
      })),
    );
    setLastMeta(null);
  }, []);

  const newConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setLastMeta(null);
  }, []);

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
