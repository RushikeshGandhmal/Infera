"use client";

import type { ChatMessage } from "@/lib/types";

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-neutral-100 text-neutral-900"
            : "bg-neutral-800 text-neutral-100"
        }`}
      >
        {message.content || (
          <span className="inline-flex gap-1">
            <span className="h-2 w-2 animate-pulse rounded-full bg-neutral-500" />
            <span className="h-2 w-2 animate-pulse rounded-full bg-neutral-500 [animation-delay:150ms]" />
            <span className="h-2 w-2 animate-pulse rounded-full bg-neutral-500 [animation-delay:300ms]" />
          </span>
        )}
        {message.meta && (
          <div className="mt-1.5 text-[10px] text-neutral-400">
            {message.meta.model} · {Math.round(message.meta.latency_ms)}ms
            {message.meta.ttft_ms != null &&
              ` · ttft ${Math.round(message.meta.ttft_ms)}ms`}
            {message.meta.total_tokens != null &&
              ` · ${message.meta.total_tokens} tok`}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MessageList({
  messages,
}: {
  messages: ChatMessage[];
}) {
  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-neutral-500">
          Ask anything to start the conversation.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {messages.map((m, i) => (
        <Bubble key={m.id ?? i} message={m} />
      ))}
    </div>
  );
}
