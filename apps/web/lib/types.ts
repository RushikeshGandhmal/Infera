export type Role = "user" | "assistant" | "system";

// Per-reply stats shown under an assistant bubble once it finishes.
export interface MessageMeta {
  model: string;
  latency_ms: number;
  ttft_ms: number | null;
  total_tokens: number | null;
}

// A message as shown in the chat view. `pending` marks the assistant
// bubble that is currently being streamed into.
export interface ChatMessage {
  id?: string;
  role: Role;
  content: string;
  status?: string;
  pending?: boolean;
  error?: boolean;
  meta?: MessageMeta;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  status: string;
  model: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: string;
  role: Role;
  content: string;
  status: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  request_id: string | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  status: string;
  model: string | null;
  created_at: string;
  updated_at: string;
  messages: MessageOut[];
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

// The final SSE frame emitted when a streamed reply finishes.
export interface DoneMeta {
  conversation_id: string;
  request_id: string;
  provider: string;
  model: string;
  latency_ms: number;
  ttft_ms: number | null;
  usage: Usage;
}
