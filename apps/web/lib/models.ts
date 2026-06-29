// Models offered in the picker. All are reachable through the single
// OpenRouter key, which is what gives us multi-provider support.
export interface ModelOption {
  id: string;
  label: string;
}

export const MODELS: ModelOption[] = [
  { id: "openai/gpt-4o-mini", label: "GPT-4o mini · OpenAI" },
  { id: "anthropic/claude-3.5-sonnet", label: "Claude 3.5 Sonnet · Anthropic" },
  { id: "google/gemini-flash-1.5", label: "Gemini 1.5 Flash · Google" },
  { id: "deepseek/deepseek-chat", label: "DeepSeek Chat · DeepSeek" },
];

export const DEFAULT_MODEL = MODELS[0].id;
