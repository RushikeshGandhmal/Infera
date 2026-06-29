"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "@/components/Sidebar";
import ModelPicker from "@/components/ModelPicker";
import MessageList from "@/components/MessageList";
import Composer from "@/components/Composer";
import { useChat } from "@/lib/useChat";
import { cancelConversation, listConversations } from "@/lib/api";
import type { ConversationSummary } from "@/lib/types";

export default function Page() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);

  const refreshList = useCallback(async () => {
    try {
      const items = await listConversations();
      setConversations(items);
    } catch {
      // The list is non-critical; a fetch failure shouldn't break the chat.
    } finally {
      setLoadingList(false);
    }
  }, []);

  const {
    conversationId,
    messages,
    isStreaming,
    model,
    setModel,
    send,
    stop,
    loadConversation,
    newConversation,
  } = useChat(refreshList);

  // Load the conversation list once on mount.
  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  // Auto-scroll to the newest message as tokens stream in.
  const bottomRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function onCancelConversation(id: string) {
    await cancelConversation(id);
    await refreshList();
    if (id === conversationId) newConversation();
  }

  // The composer is disabled when the open conversation has been cancelled.
  const activeStatus = conversations.find((c) => c.id === conversationId)?.status;
  const composerDisabled = activeStatus === "cancelled" || activeStatus === "archived";

  return (
    <main className="flex h-screen bg-neutral-950 text-neutral-100">
      <Sidebar
        conversations={conversations}
        activeId={conversationId}
        loading={loadingList}
        onSelect={loadConversation}
        onNew={newConversation}
        onCancel={onCancelConversation}
      />

      <section className="flex h-full flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
          <h1 className="text-sm font-semibold text-neutral-200">Infera Chat</h1>
          <div className="flex items-center gap-3">
            <a
              href="/metrics"
              className="text-xs text-neutral-400 hover:text-neutral-200"
            >
              Metrics
            </a>
            <ModelPicker value={model} onChange={setModel} disabled={isStreaming} />
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl">
            <MessageList messages={messages} />
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="mx-auto w-full max-w-3xl">
          <Composer
            isStreaming={isStreaming}
            disabled={composerDisabled}
            onSend={send}
            onStop={stop}
          />
        </div>
      </section>
    </main>
  );
}
