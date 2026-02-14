import { useState } from "react";
import { api } from "@/api/client";
import { Check, ChevronDown, ChevronRight, Edit3, HelpCircle, Trash2, X, Shield, ShieldOff } from "lucide-react";

interface KeyDefinition {
  key: string;
  label: string;
  type: "text" | "password" | "textarea";
}

interface ServiceCredentialInfo {
  service: string;
  label: string;
  keys: string[];
  key_definitions: KeyDefinition[];
  configured: boolean;
  configured_keys: string[];
  configured_at: string | null;
}

interface CredentialCardProps {
  service: ServiceCredentialInfo;
  onUpdate: () => void;
}

interface SetupStep {
  instruction: string;
  code?: string;
}

interface SetupGuide {
  title: string;
  steps: SetupStep[];
  note?: string;
}

const SETUP_GUIDES: Record<string, SetupGuide> = {
  claude_code: {
    title: "Finding your Claude CLI credentials",
    steps: [
      {
        instruction: "Open a terminal and print your credentials file:",
        code: "cat ~/.claude/.credentials.json",
      },
      {
        instruction: "Copy the entire JSON output (it looks like this):",
        code: '{"claudeAiOauth": {"token_type": "Bearer", "access_token": "...", ...}}',
      },
      {
        instruction: "Paste the full JSON into the field below and save.",
      },
    ],
    note: "Your token is encrypted before storage and injected into Claude Code containers at runtime. It is never logged or exposed.",
  },
  github: {
    title: "Setting up GitHub credentials",
    steps: [
      {
        instruction: "GitHub Token (PAT): Create a fine-grained personal access token at GitHub Settings > Developer settings > Personal access tokens. Grant repo access for the repositories you want the agent to work with.",
      },
      {
        instruction: "SSH Private Key (optional): Paste the contents of your private key file. Used for git clone/push over SSH.",
        code: "cat ~/.ssh/id_ed25519",
      },
      {
        instruction: "Git Author Name/Email: Set the identity used for commits made by the agent on your behalf.",
      },
    ],
  },
};

export default function CredentialCard({ service, onUpdate }: CredentialCardProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [showGuide, setShowGuide] = useState(false);

  const guide = SETUP_GUIDES[service.service];

  const handleSave = async () => {
    const nonEmpty = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v.trim())
    );
    if (Object.keys(nonEmpty).length === 0) {
      setError("Enter at least one value");
      return;
    }

    setSaving(true);
    setError("");
    try {
      await api(`/api/settings/credentials/${service.service}`, {
        method: "PUT",
        body: JSON.stringify({ credentials: nonEmpty }),
      });
      setEditing(false);
      setValues({});
      onUpdate();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Remove all ${service.label} credentials?`)) return;

    setDeleting(true);
    setError("");
    try {
      await api(`/api/settings/credentials/${service.service}`, {
        method: "DELETE",
      });
      onUpdate();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="bg-surface-light border border-border rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-white font-medium">{service.label}</h3>
          {service.configured ? (
            <span className="flex items-center gap-1 text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">
              <Shield size={12} />
              Configured
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-gray-500 bg-gray-500/10 px-2 py-0.5 rounded-full">
              <ShieldOff size={12} />
              Not configured
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-surface-lighter transition-colors"
              title="Edit"
            >
              <Edit3 size={16} />
            </button>
          )}
          {service.configured && !editing && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-surface-lighter transition-colors disabled:opacity-50"
              title="Delete"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Configured keys summary */}
      {service.configured && !editing && (
        <p className="text-xs text-gray-500">
          Keys: {service.configured_keys.join(", ")}
          {service.configured_at && (
            <> &middot; Updated {new Date(service.configured_at).toLocaleDateString()}</>
          )}
        </p>
      )}

      {/* Edit form */}
      {editing && (
        <div className="space-y-3 mt-3">
          {/* Setup guide */}
          {guide && (
            <div className="rounded-lg border border-border overflow-hidden">
              <button
                type="button"
                onClick={() => setShowGuide(!showGuide)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                <HelpCircle size={14} className="shrink-0" />
                <span>{guide.title}</span>
                {showGuide
                  ? <ChevronDown size={14} className="ml-auto shrink-0" />
                  : <ChevronRight size={14} className="ml-auto shrink-0" />
                }
              </button>
              {showGuide && (
                <div className="px-3 pb-3 space-y-3">
                  <ol className="space-y-2.5">
                    {guide.steps.map((step, i) => (
                      <li key={i} className="flex gap-2.5 text-sm">
                        <span className="text-accent font-medium shrink-0">{i + 1}.</span>
                        <div className="min-w-0">
                          <p className="text-gray-300">{step.instruction}</p>
                          {step.code && (
                            <pre className="mt-1.5 px-3 py-2 bg-surface rounded-md text-xs text-gray-400 font-mono overflow-x-auto whitespace-pre-wrap break-all">
                              {step.code}
                            </pre>
                          )}
                        </div>
                      </li>
                    ))}
                  </ol>
                  {guide.note && (
                    <p className="text-xs text-gray-500 border-t border-border pt-2">
                      {guide.note}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {service.key_definitions.map((keyDef) => (
            <div key={keyDef.key}>
              <label className="block text-sm text-gray-400 mb-1">
                {keyDef.label}
                {service.configured_keys.includes(keyDef.key) && (
                  <span className="text-green-400/60 ml-1">(saved)</span>
                )}
              </label>
              {keyDef.type === "textarea" ? (
                <textarea
                  value={values[keyDef.key] || ""}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [keyDef.key]: e.target.value }))
                  }
                  placeholder={`Enter ${keyDef.label.toLowerCase()}...`}
                  rows={4}
                  className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 font-mono focus:outline-none focus:border-accent"
                />
              ) : (
                <input
                  type={keyDef.type}
                  value={values[keyDef.key] || ""}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [keyDef.key]: e.target.value }))
                  }
                  placeholder={
                    service.configured_keys.includes(keyDef.key)
                      ? "Leave blank to keep current"
                      : `Enter ${keyDef.label.toLowerCase()}...`
                  }
                  className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent"
                />
              )}
            </div>
          ))}

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              <Check size={14} />
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => {
                setEditing(false);
                setValues({});
                setError("");
                setShowGuide(false);
              }}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-gray-400 hover:text-white text-sm transition-colors"
            >
              <X size={14} />
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
