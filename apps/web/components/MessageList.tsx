"use client";

import { Streamdown } from "streamdown";
import type { ChatMessage } from "@/lib/types";

function Avatar({ role }: { role: string }) {
  const isUser = role === "user";
  return (
    <div
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
        isUser
          ? "bg-neutral-700 text-neutral-200"
          : "bg-emerald-600 text-white"
      }`}
    >
      {isUser ? "You" : "AI"}
    </div>
  );
}

function MetaLine({ message }: { message: ChatMessage }) {
  if (!message.meta) return null;
  const { model, latency_ms, ttft_ms, total_tokens } = message.meta;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-neutral-500">
      <span className="rounded bg-neutral-800 px-1.5 py-0.5 font-medium text-neutral-400">
        {model}
      </span>
      <span>{Math.round(latency_ms)}ms</span>
      {ttft_ms != null && <span>· ttft {Math.round(ttft_ms)}ms</span>}
      {total_tokens != null && <span>· {total_tokens} tok</span>}
    </div>
  );
}

function Row({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const thinking = !isUser && message.pending && !message.content;

  return (
    <div className="group w-full animate-msg-in px-4 py-5 md:px-6">
      <div className="mx-auto flex max-w-3xl gap-4">
        <Avatar role={message.role} />
        <div className="min-w-0 flex-1">
          <div className="mb-1 text-xs font-semibold text-neutral-400">
            {isUser ? "You" : "Assistant"}
          </div>

          {thinking ? (
            <div className="flex items-center gap-1 py-1.5">
              <span className="h-2 w-2 animate-bounce rounded-full bg-neutral-500" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-neutral-500 [animation-delay:150ms]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-neutral-500 [animation-delay:300ms]" />
            </div>
          ) : isUser ? (
            <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-neutral-100">
              {message.content}
            </div>
          ) : (
            <div
              className={`text-[15px] leading-relaxed ${
                message.error ? "text-red-300" : "text-neutral-100"
              }`}
            >
              <Streamdown className="space-y-3">{message.content}</Streamdown>
            </div>
          )}

          <MetaLine message={message} />
        </div>
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
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-600 text-lg font-bold text-white">
          I
        </div>
        <h2 className="text-lg font-semibold text-neutral-200">
          How can I help you today?
        </h2>
        <p className="mt-1 text-sm text-neutral-500">
          Ask anything — responses stream in real time.
        </p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-neutral-800/60">
      {messages.map((m, i) => (
        <Row key={m.id ?? i} message={m} />
      ))}
    </div>
  );
}
