"use client";

import type { ConversationSummary } from "@/lib/types";

function statusDot(status: string): string {
  if (status === "active") return "bg-emerald-500";
  if (status === "cancelled") return "bg-red-500";
  return "bg-neutral-500";
}

export default function Sidebar({
  conversations,
  activeId,
  loading,
  onSelect,
  onNew,
  onCancel,
}: {
  conversations: ConversationSummary[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onCancel: (id: string) => void;
}) {
  return (
    <aside className="flex h-full w-72 flex-col border-r border-neutral-800 bg-neutral-900">
      <div className="flex items-center justify-between p-3">
        <span className="text-sm font-semibold tracking-wide text-neutral-300">
          Conversations
        </span>
        <button
          onClick={onNew}
          className="rounded-md bg-neutral-100 px-2.5 py-1 text-xs font-medium text-neutral-900 hover:bg-white"
        >
          + New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {loading && (
          <p className="px-2 py-3 text-xs text-neutral-500">Loading…</p>
        )}
        {!loading && conversations.length === 0 && (
          <p className="px-2 py-3 text-xs text-neutral-500">
            No conversations yet. Start one →
          </p>
        )}
        <ul className="space-y-1">
          {conversations.map((c) => (
            <li key={c.id}>
              <div
                className={`group flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm ${
                  c.id === activeId
                    ? "bg-neutral-800"
                    : "hover:bg-neutral-800/60"
                }`}
                onClick={() => onSelect(c.id)}
              >
                <span
                  className={`h-2 w-2 shrink-0 rounded-full ${statusDot(c.status)}`}
                  title={c.status}
                />
                <span className="flex-1 truncate text-neutral-200">
                  {c.title || "Untitled"}
                </span>
                <span className="text-[10px] text-neutral-500">
                  {c.message_count}
                </span>
                {c.status === "active" && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onCancel(c.id);
                    }}
                    className="hidden text-[10px] text-neutral-400 hover:text-red-400 group-hover:block"
                    title="Cancel conversation"
                  >
                    ✕
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
