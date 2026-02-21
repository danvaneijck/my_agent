import { useState } from "react";
import { api } from "@/api/client";
import { AlertTriangle, Check, Key, X } from "lucide-react";
import ModelSelect from "@/components/common/ModelSelect";
import { DEFAULT_MODEL_PRESETS } from "@/config/modelPresets";

interface LlmSettingsStepProps {
  tokenBudgetMonthly: number | null;
  onNext: () => void;
  onSkip: () => void;
}

export default function LlmSettingsStep({
  tokenBudgetMonthly,
  onNext,
  onSkip,
}: LlmSettingsStepProps) {
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [defaultModel, setDefaultModel] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    const credentials: Record<string, string> = {};
    if (anthropicKey.trim()) credentials["anthropic_api_key"] = anthropicKey.trim();
    if (openaiKey.trim()) credentials["openai_api_key"] = openaiKey.trim();
    if (googleKey.trim()) credentials["google_api_key"] = googleKey.trim();
    if (defaultModel.trim()) credentials["default_model"] = defaultModel.trim();

    if (Object.keys(credentials).length === 0) {
      setSaveError("Enter at least one API key to continue.");
      return;
    }

    setSaving(true);
    setSaveError("");
    try {
      await api("/api/settings/credentials/llm_settings", {
        method: "PUT",
        body: JSON.stringify({ credentials }),
      });
      setSaved(true);
      setAnthropicKey("");
      setOpenaiKey("");
      setGoogleKey("");
      setTimeout(() => onNext(), 700);
    } catch (err: any) {
      setSaveError(err?.message ?? "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  if (saved) {
    return (
      <div className="flex flex-col items-center gap-3 py-8">
        <div className="w-12 h-12 rounded-full bg-green-400/15 flex items-center justify-center">
          <Check size={24} className="text-green-400" />
        </div>
        <p className="text-sm font-medium text-gray-900 dark:text-white">
          API keys saved!
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Explanation */}
      <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
        Add at least one LLM API key. Your keys are Fernet-encrypted before
        storage and never displayed again after saving.
      </p>

      {/* Cap warning */}
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/8 p-3 flex items-start gap-2.5">
        <AlertTriangle size={15} className="text-amber-500 dark:text-amber-400 mt-0.5 shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-400/80 leading-relaxed">
          {tokenBudgetMonthly != null
            ? `Without your own keys you share a monthly budget of ${tokenBudgetMonthly.toLocaleString()} tokens. Usage beyond this budget will be rejected.`
            : "Without your own keys, usage is capped by the shared monthly token budget. Add a key to get unlimited access billed to your provider account."}
        </p>
      </div>

      {/* API key inputs */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Key size={14} className="text-accent shrink-0" />
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            API Keys
          </span>
        </div>

        {[
          { key: "anthropic", label: "Anthropic API Key", placeholder: "sk-ant-api03-…", value: anthropicKey, set: setAnthropicKey },
          { key: "openai", label: "OpenAI API Key", placeholder: "sk-proj-…", value: openaiKey, set: setOpenaiKey },
          { key: "google", label: "Google API Key", placeholder: "AIzaSy…", value: googleKey, set: setGoogleKey },
        ].map(({ key, label, placeholder, value, set }) => (
          <div key={key}>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
              {label} <span className="text-gray-400">(optional — add at least one)</span>
            </label>
            <input
              type="password"
              value={value}
              onChange={(e) => set(e.target.value)}
              placeholder={placeholder}
              className="w-full bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:border-accent"
            />
          </div>
        ))}
      </div>

      {/* Default model */}
      <div>
        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
          Default chat model <span className="text-gray-400">(optional)</span>
        </label>
        <ModelSelect
          presets={DEFAULT_MODEL_PRESETS}
          value={defaultModel}
          onChange={setDefaultModel}
          placeholder="Select a default model…"
        />
        <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
          You can change this and add more model preferences later in Settings → LLM Settings.
        </p>
      </div>

      {saveError && <p className="text-sm text-red-400">{saveError}</p>}

      {/* Actions */}
      <div className="flex flex-col gap-2 pt-1">
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          <Check size={16} />
          {saving ? "Saving…" : "Save API keys"}
        </button>
        <button
          onClick={onSkip}
          className="flex items-center justify-center gap-1.5 text-sm text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors py-1"
        >
          <X size={14} />
          Skip for now
        </button>
      </div>
    </div>
  );
}
