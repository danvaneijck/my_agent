/**
 * modelPresets.ts — Configurable model preset lists for dropdowns.
 *
 * To add or remove model options, edit the arrays below.
 * No component changes are needed.
 */

export interface ModelPreset {
  value: string;
  label: string;
  provider: "anthropic" | "openai" | "google";
  useCase?: string;
}

/** Presets for the default chat model selector. */
export const DEFAULT_MODEL_PRESETS: ModelPreset[] = [
  {
    value: "claude-sonnet-4-20250514",
    label: "Claude Sonnet 4",
    provider: "anthropic",
    useCase: "Best for most tasks",
  },
  {
    value: "claude-opus-4-5-20251101",
    label: "Claude Opus 4.5",
    provider: "anthropic",
    useCase: "Most capable Anthropic model",
  },
  {
    value: "claude-haiku-4-5-20251001",
    label: "Claude Haiku 4.5",
    provider: "anthropic",
    useCase: "Fast and affordable",
  },
  {
    value: "gpt-4o",
    label: "GPT-4o",
    provider: "openai",
    useCase: "OpenAI flagship",
  },
  {
    value: "gpt-4o-mini",
    label: "GPT-4o Mini",
    provider: "openai",
    useCase: "Fast and affordable",
  },
  {
    value: "gemini-2.0-flash",
    label: "Gemini 2.0 Flash",
    provider: "google",
    useCase: "Google fast model",
  },
  {
    value: "gemini-2.5-pro",
    label: "Gemini 2.5 Pro",
    provider: "google",
    useCase: "Google most capable model",
  },
];

/** Presets for the summarisation model selector. */
export const SUMMARIZATION_MODEL_PRESETS: ModelPreset[] = [
  {
    value: "gpt-4o-mini",
    label: "GPT-4o Mini",
    provider: "openai",
    useCase: "Fast, cheap summarisation",
  },
  {
    value: "claude-haiku-4-5-20251001",
    label: "Claude Haiku 4.5",
    provider: "anthropic",
    useCase: "Fast Anthropic model",
  },
  {
    value: "gemini-2.0-flash",
    label: "Gemini 2.0 Flash",
    provider: "google",
    useCase: "Fast Google model",
  },
];

/** Presets for the embedding model selector. */
export const EMBEDDING_MODEL_PRESETS: ModelPreset[] = [
  {
    value: "text-embedding-3-small",
    label: "text-embedding-3-small",
    provider: "openai",
    useCase: "Recommended — 1536 dims",
  },
  {
    value: "text-embedding-3-large",
    label: "text-embedding-3-large",
    provider: "openai",
    useCase: "Higher quality, larger",
  },
  {
    value: "gemini-embedding-001",
    label: "gemini-embedding-001",
    provider: "google",
    useCase: "Google embedding model",
  },
];
