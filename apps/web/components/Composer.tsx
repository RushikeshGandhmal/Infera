"use client";

import { useState } from "react";

export default function Composer({
  isStreaming,
  disabled,
  onSend,
  onStop,
}: {
  isStreaming: boolean;
  disabled?: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const [text, setText] = useState("");

  function submit() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  }

  // Enter sends, Shift+Enter inserts a newline.
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="bg-gradient-to-t from-neutral-900 via-neutral-900 to-transparent px-4 pb-4 pt-2">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-neutral-700 bg-neutral-800 p-2 shadow-lg focus-within:border-neutral-500">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={disabled}
            rows={1}
            placeholder={disabled ? "This conversation is closed" : "Message Infera…"}
            className="max-h-40 flex-1 resize-none bg-transparent px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-500 disabled:opacity-50"
          />
          {isStreaming ? (
            <button
              onClick={onStop}
              aria-label="Stop generating"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-500/90 text-white transition hover:bg-red-500"
            >
              <span className="block h-3 w-3 rounded-[2px] bg-white" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={disabled || !text.trim()}
              aria-label="Send message"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-neutral-100 text-neutral-900 transition hover:bg-white disabled:opacity-40"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[11px] text-neutral-600">
          Infera can make mistakes. Responses are logged for observability.
        </p>
      </div>
    </div>
  );
}
