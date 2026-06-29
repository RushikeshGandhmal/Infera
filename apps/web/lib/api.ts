import type {
  ConversationDetail,
  ConversationSummary,
  DoneMeta,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function listConversations(
  status?: string,
): Promise<ConversationSummary[]> {
  const url = new URL(`${API}/conversations`);
  if (status) url.searchParams.set("status", status);
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to list conversations (${res.status})`);
  return res.json();
}

export async function getConversation(
  id: string,
): Promise<ConversationDetail> {
  const res = await fetch(`${API}/conversations/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load conversation (${res.status})`);
  return res.json();
}

export async function cancelConversation(
  id: string,
): Promise<ConversationSummary> {
  const res = await fetch(`${API}/conversations/${id}/cancel`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to cancel conversation (${res.status})`);
  return res.json();
}

export interface StreamHandlers {
  signal?: AbortSignal;
  onStart?: (conversationId: string) => void;
  onToken?: (text: string) => void;
  onDone?: (meta: DoneMeta) => void;
  onError?: (detail: string) => void;
}

export interface StreamPayload {
  message: string;
  conversation_id?: string | null;
  model?: string | null;
}

// Calls POST /chat/stream and parses the Server-Sent Events frames as they
// arrive. EventSource only supports GET, so we read the response body stream
// manually and split on the SSE frame delimiter.
export async function streamChat(
  payload: StreamPayload,
  handlers: StreamHandlers,
): Promise<void> {
  const res = await fetch(`${API}/chat/stream`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  // Validation errors (404/409/422) are returned before the stream opens.
  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep the status-code message */
    }
    handlers.onError?.(detail);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const json = line.slice(5).trim();
      if (!json) continue;

      const ev = JSON.parse(json);
      switch (ev.type) {
        case "start":
          handlers.onStart?.(ev.conversation_id);
          break;
        case "token":
          handlers.onToken?.(ev.content);
          break;
        case "done":
          handlers.onDone?.(ev as DoneMeta);
          break;
        case "error":
          handlers.onError?.(ev.detail);
          break;
      }
    }
  }
}
