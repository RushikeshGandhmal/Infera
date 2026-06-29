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
    <div className="flex items-end gap-2 border-t border-neutral-800 bg-neutral-900 p-3">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        rows={1}
        placeholder={disabled ? "This conversation is closed" : "Message…"}
        className="max-h-40 flex-1 resize-none rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-2.5 text-sm text-neutral-100 outline-none placeholder:text-neutral-500 focus:border-neutral-500 disabled:opacity-50"
      />
      {isStreaming ? (
        <button
          onClick={onStop}
          className="rounded-lg bg-red-500/90 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-500"
        >
          Stop
        </button>
      ) : (
        <button
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="rounded-lg bg-neutral-100 px-4 py-2.5 text-sm font-medium text-neutral-900 hover:bg-white disabled:opacity-40"
        >
          Send
        </button>
      )}
    </div>
  );
}
