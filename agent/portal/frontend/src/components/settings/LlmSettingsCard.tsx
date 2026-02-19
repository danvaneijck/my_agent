import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Key,
  Save,
  Trash2,
  Unlock,
  Lock,
} from "lucide-react";

interface LlmStatus {
  configured_keys: string[];
  has_anthropic: boolean;
  has_openai: boolean;
  has_google: boolean;
  has_any_key: boolean;
  default_model: string | null;
  summarization_model: string | null;
  embedding_model: string | null;
}

interface LlmSettingsCardProps {
  onUpdate: () => void;
}

const PROVIDER_HINTS: Record<string, string> = {
  anthropic_api_key: "e.g. sk-ant-api03-...",
  openai_api_key: "e.g. sk-proj-...",
  google_api_key: "e.g. AIzaSy...",
};

const MODEL_HINTS: Record<string, string> = {
  default_model:
    "e.g. claude-sonnet-4-20250514 · gpt-4o · gemini-2.0-flash",
  summarization_model: "e.g. gpt-4o-mini · claude-haiku-4-5-20251001",
  embedding_model: "e.g. text-embedding-3-small · gemini-embedding-001",
};

export default function LlmSettingsCard({ onUpdate }: LlmSettingsCardProps) {
  const [status, setStatus] = useState<LlmStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state — kept separate so we never pre-fill secret values
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [defaultModel, setDefaultModel] = useState("");
  const [summarizationModel, setSummarizationModel] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [showKeys, setShowKeys] = useState(false);
  const [showModels, setShowModels] = useState(false);

  const [deleting, setDeleting] = useState(false);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api<LlmStatus>("/api/settings/llm-settings/status");
      setStatus(data);
      // Pre-fill model fields from stored preferences (these are not secrets)
      setDefaultModel(data.default_model ?? "");
      setSummarizationModel(data.summarization_model ?? "");
      setEmbeddingModel(data.embedding_model ?? "");
    } catch (err: any) {
      const msg: string = err?.message ?? "";
      if (msg.includes("503")) {
        setError(
          "Credential storage not configured. Set CREDENTIAL_ENCRYPTION_KEY in your .env file."
        );
      } else {
        setError("Failed to load LLM settings.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleSave = async () => {
    const credentials: Record<string, string> = {};

    if (anthropicKey.trim()) credentials["anthropic_api_key"] = anthropicKey.trim();
    if (openaiKey.trim()) credentials["openai_api_key"] = openaiKey.trim();
    if (googleKey.trim()) credentials["google_api_key"] = googleKey.trim();
    if (defaultModel.trim()) credentials["default_model"] = defaultModel.trim();
    if (summarizationModel.trim()) credentials["summarization_model"] = summarizationModel.trim();
    if (embeddingModel.trim()) credentials["embedding_model"] = embeddingModel.trim();

    if (Object.keys(credentials).length === 0) {
      setSaveError("Enter at least one value to save.");
      return;
    }

    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);

    try {
      await api("/api/settings/credentials/llm_settings", {
        method: "PUT",
        body: JSON.stringify({ credentials }),
      });
      // Clear secret fields after save — they should not persist in state
      setAnthropicKey("");
      setOpenaiKey("");
      setGoogleKey("");
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      await fetchStatus();
      onUpdate();
    } catch (err: any) {
      setSaveError(err?.message ?? "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (
      !confirm(
        "Remove all personal LLM API keys and model preferences? You will fall back to shared system keys and budget limits will apply."
      )
    )
      return;

    setDeleting(true);
    try {
      await api("/api/settings/credentials/llm_settings", { method: "DELETE" });
      setAnthropicKey("");
      setOpenaiKey("");
      setGoogleKey("");
      setDefaultModel("");
      setSummarizationModel("");
      setEmbeddingModel("");
      await fetchStatus();
      onUpdate();
    } catch (err: any) {
      setSaveError(err?.message ?? "Delete failed.");
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
        <p className="text-sm text-yellow-300">{error}</p>
      </div>
    );
  }

  const hasAnyKey = status?.has_any_key ?? false;

  return (
    <div className="space-y-4">
      {/* Status banner */}
      <div
        className={`rounded-xl border p-4 flex items-start gap-3 ${
          hasAnyKey
            ? "bg-green-500/10 border-green-500/30"
            : "bg-yellow-500/10 border-yellow-500/30"
        }`}
      >
        {hasAnyKey ? (
          <Unlock size={18} className="text-green-400 mt-0.5 shrink-0" />
        ) : (
          <Lock size={18} className="text-yellow-400 mt-0.5 shrink-0" />
        )}
        <div>
          <p
            className={`text-sm font-medium ${
              hasAnyKey ? "text-green-300" : "text-yellow-300"
            }`}
          >
            {hasAnyKey
              ? "Using your own API keys — token budget not enforced"
              : "Using shared system keys — budget limits apply"}
          </p>
          <p
            className={`text-xs mt-1 ${
              hasAnyKey ? "text-green-400/70" : "text-yellow-400/70"
            }`}
          >
            {hasAnyKey
              ? `Providers configured: ${[
                  status?.has_anthropic && "Anthropic",
                  status?.has_openai && "OpenAI",
                  status?.has_google && "Google",
                ]
                  .filter(Boolean)
                  .join(", ")}. Your usage still counts toward analytics.`
              : "Add your own API keys below to get unlimited usage. Your keys are encrypted at rest."}
          </p>
        </div>
        {hasAnyKey && (
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="ml-auto p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-surface-lighter transition-colors disabled:opacity-50 shrink-0"
            title="Remove all personal LLM settings"
          >
            <Trash2 size={15} />
          </button>
        )}
      </div>

      {/* API Keys section */}
      <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowKeys((v) => !v)}
          className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-surface-lighter/40 transition-colors"
        >
          <Key size={16} className="text-accent shrink-0" />
          <span className="text-white font-medium flex-1">API Keys</span>
          <div className="flex items-center gap-2">
            {status?.has_anthropic && (
              <span className="text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">
                Anthropic
              </span>
            )}
            {status?.has_openai && (
              <span className="text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">
                OpenAI
              </span>
            )}
            {status?.has_google && (
              <span className="text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">
                Google
              </span>
            )}
          </div>
          {showKeys ? (
            <ChevronDown size={16} className="text-gray-400 shrink-0" />
          ) : (
            <ChevronRight size={16} className="text-gray-400 shrink-0" />
          )}
        </button>

        {showKeys && (
          <div className="px-5 pb-5 space-y-4 border-t border-border">
            <p className="text-xs text-gray-500 pt-4">
              Enter keys for the providers you want to use. Leave blank to keep
              existing values. Keys are Fernet-encrypted before storage and
              never displayed.
            </p>

            {[
              {
                key: "anthropic_api_key",
                label: "Anthropic API Key",
                value: anthropicKey,
                set: setAnthropicKey,
                configured: status?.has_anthropic,
              },
              {
                key: "openai_api_key",
                label: "OpenAI API Key",
                value: openaiKey,
                set: setOpenaiKey,
                configured: status?.has_openai,
              },
              {
                key: "google_api_key",
                label: "Google API Key",
                value: googleKey,
                set: setGoogleKey,
                configured: status?.has_google,
              },
            ].map(({ key, label, value, set, configured }) => (
              <div key={key}>
                <label className="block text-sm text-gray-400 mb-1">
                  {label}
                  {configured && (
                    <span className="text-green-400/60 ml-1">(configured)</span>
                  )}
                </label>
                <input
                  type="password"
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  placeholder={
                    configured
                      ? "Leave blank to keep current"
                      : PROVIDER_HINTS[key] ?? `Enter ${label.toLowerCase()}...`
                  }
                  className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Model preferences section */}
      <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowModels((v) => !v)}
          className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-surface-lighter/40 transition-colors"
        >
          <span className="text-accent text-base leading-none shrink-0">⚙</span>
          <span className="text-white font-medium flex-1">Model Preferences</span>
          {(status?.default_model ||
            status?.summarization_model ||
            status?.embedding_model) && (
            <span className="text-xs text-gray-400">
              {[
                status?.default_model,
                status?.summarization_model,
                status?.embedding_model,
              ]
                .filter(Boolean)
                .length}{" "}
              set
            </span>
          )}
          {showModels ? (
            <ChevronDown size={16} className="text-gray-400 shrink-0" />
          ) : (
            <ChevronRight size={16} className="text-gray-400 shrink-0" />
          )}
        </button>

        {showModels && (
          <div className="px-5 pb-5 space-y-4 border-t border-border">
            <p className="text-xs text-gray-500 pt-4">
              Override the default models used for your conversations. Requires a
              matching API key to be configured above. Leave blank to use system
              defaults.
            </p>

            {[
              {
                key: "default_model",
                label: "Default Chat Model",
                value: defaultModel,
                set: setDefaultModel,
              },
              {
                key: "summarization_model",
                label: "Summarisation Model",
                value: summarizationModel,
                set: setSummarizationModel,
              },
              {
                key: "embedding_model",
                label: "Embedding Model",
                value: embeddingModel,
                set: setEmbeddingModel,
              },
            ].map(({ key, label, value, set }) => (
              <div key={key}>
                <label className="block text-sm text-gray-400 mb-1">
                  {label}
                </label>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  placeholder={MODEL_HINTS[key] ?? `Enter model name...`}
                  className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Save button + feedback */}
      {saveError && (
        <p className="text-sm text-red-400">{saveError}</p>
      )}
      {saveSuccess && (
        <div className="flex items-center gap-2 text-sm text-green-400">
          <Check size={14} />
          Saved successfully
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
      >
        <Save size={14} />
        {saving ? "Saving..." : "Save LLM Settings"}
      </button>
    </div>
  );
}
