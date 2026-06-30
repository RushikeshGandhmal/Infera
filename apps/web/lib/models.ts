// Models offered in the picker. The local model works through Ollama; the
// hosted models work through OpenRouter when an active key is configured.
export interface ModelOption {
  id: string;
  label: string;
}

export const MODELS: ModelOption[] = [
  { id: "qwen3:14b", label: "Qwen3 14B · Local" },
  { id: "qwen3:8b", label: "Qwen3 8B · Local" },
  { id: "openai/gpt-4o-mini", label: "GPT-4o mini · OpenAI" },
  { id: "anthropic/claude-3.5-sonnet", label: "Claude 3.5 Sonnet · Anthropic" },
  { id: "google/gemini-flash-1.5", label: "Gemini 1.5 Flash · Google" },
  { id: "deepseek/deepseek-chat", label: "DeepSeek Chat · DeepSeek" },
];

export const DEFAULT_MODEL = MODELS[0].id;
