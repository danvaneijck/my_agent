import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Edit3,
  ExternalLink,
  Github,
  GitBranch,
  HelpCircle,
  RefreshCw,
  Shield,
  ShieldOff,
  Trash2,
  X,
  Zap,
} from "lucide-react";

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

interface ClaudeTokenStatus {
  configured: boolean;
  valid?: boolean;
  expires_at?: string | null;
  expires_in_seconds?: number | null;
  needs_refresh?: boolean;
  scopes?: string[];
  subscription_type?: string | null;
  rate_limit_tier?: string | null;
  error?: string;
}

interface GitTokenStatus {
  configured: boolean;
  username?: string | null;
  scopes?: string[];
  expires_at?: string | null;
  expires_in_seconds?: number | null;
  is_expired?: boolean;
  needs_refresh?: boolean;
}

const SETUP_GUIDES: Record<string, SetupGuide> = {
  claude_code: {
    title: "Paste credentials manually (from CLI)",
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
    title: "Alternative: Paste token manually",
    steps: [
      {
        instruction:
          "Option 1: OAuth (Recommended) — Click 'Connect with GitHub' above for seamless authorization with automatic token management.",
      },
      {
        instruction:
          "Option 2: Manual PAT — Create a fine-grained personal access token at GitHub Settings > Developer settings > Personal access tokens. Grant 'repo', 'user:email', and 'workflow' scopes.",
      },
      {
        instruction:
          "SSH Private Key (optional): Only needed for git clone/push over SSH. Paste your private key:",
        code: "cat ~/.ssh/id_ed25519",
      },
    ],
    note: "OAuth tokens are managed automatically. Manual PATs must be regenerated when expired.",
  },
  bitbucket: {
    title: "Bitbucket OAuth Setup",
    steps: [
      {
        instruction:
          "Click 'Connect with Bitbucket' above to authorize via OAuth.",
      },
      {
        instruction:
          "Bitbucket tokens expire every 2 hours but are automatically refreshed in the background.",
      },
    ],
    note: "For Jira and Confluence access, configure Atlassian credentials separately.",
  },
  atlassian: {
    title: "Setting up Atlassian credentials",
    steps: [
      {
        instruction:
          "Instance URL: Your Atlassian instance URL (e.g., https://yourcompany.atlassian.net)",
      },
      {
        instruction:
          "Username: Your Atlassian account email address",
      },
      {
        instruction:
          "API Token: Create an API token at https://id.atlassian.com/manage-profile/security/api-tokens with access to Jira, Confluence, and Bitbucket",
      },
    ],
    note: "These credentials provide access to Jira, Confluence, and Bitbucket repositories. The same API token works across all Atlassian services.",
  },
};

function formatTimeRemaining(seconds: number): string {
  if (seconds <= 0) return "Expired";
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m remaining`;
  return `${mins}m remaining`;
}

// ---------------------------------------------------------------------------
// Claude OAuth sub-component
// ---------------------------------------------------------------------------

function ClaudeOAuthFlow({
  onSuccess,
  onCancel,
}: {
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const [step, setStep] = useState<"idle" | "authorizing" | "exchanging">("idle");
  const [authCode, setAuthCode] = useState("");
  const [error, setError] = useState("");

  const startOAuth = async () => {
    setError("");
    setStep("authorizing");
    try {
      const data = await api<{ authorize_url: string; state: string }>(
        "/api/settings/credentials/claude_code/oauth/start",
        { method: "POST" },
      );
      // Open the Anthropic authorize URL in a new tab
      window.open(data.authorize_url, "_blank", "noopener,noreferrer");
    } catch (err: any) {
      setError(err.message);
      setStep("idle");
    }
  };

  const exchangeCode = async () => {
    const code = authCode.trim();
    if (!code) {
      setError("Please paste the authorization code");
      return;
    }
    setError("");
    setStep("exchanging");
    try {
      await api("/api/settings/credentials/claude_code/oauth/exchange", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      onSuccess();
    } catch (err: any) {
      setError(err.message);
      setStep("authorizing");
    }
  };

  if (step === "idle") {
    return (
      <button
        onClick={startOAuth}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors w-full justify-center"
      >
        <Zap size={16} />
        Connect Claude Account
      </button>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
        <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
          A new tab opened for Anthropic login. After you authorize:
        </p>
        <ol className="text-sm text-gray-600 dark:text-gray-400 space-y-1 ml-4 list-decimal">
          <li>Copy the code shown on the Anthropic page</li>
          <li>Paste it below</li>
        </ol>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">
          Authorization code
        </label>
        <input
          type="text"
          value={authCode}
          onChange={(e) => setAuthCode(e.target.value)}
          placeholder="Paste the code from Anthropic here..."
          className="w-full bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-600 font-mono focus:outline-none focus:border-accent"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter") exchangeCode();
          }}
        />
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex gap-2">
        <button
          onClick={exchangeCode}
          disabled={step === "exchanging"}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          <Check size={14} />
          {step === "exchanging" ? "Connecting..." : "Connect"}
        </button>
        <button
          onClick={onCancel}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm transition-colors"
        >
          <X size={14} />
          Cancel
        </button>
        <button
          onClick={startOAuth}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm transition-colors ml-auto"
          title="Reopen Anthropic login"
        >
          <ExternalLink size={14} />
          Reopen login
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Claude token status sub-component
// ---------------------------------------------------------------------------

function ClaudeTokenStatusBar({
  onRefreshDone,
}: {
  onRefreshDone: () => void;
}) {
  const [status, setStatus] = useState<ClaudeTokenStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api<ClaudeTokenStatus>("/api/settings/credentials/claude_code/status");
      setStatus(data);
    } catch {
      // Silently fail — status is optional enhancement
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshError("");
    try {
      await api("/api/settings/credentials/claude_code/oauth/refresh", {
        method: "POST",
      });
      await fetchStatus();
      onRefreshDone();
    } catch (err: any) {
      setRefreshError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  if (!status || !status.configured) return null;

  const expirySeconds = status.expires_in_seconds ?? 0;
  const isExpired = expirySeconds <= 0;
  const isWarning = !isExpired && (status.needs_refresh ?? false);

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        {/* Token validity */}
        {isExpired ? (
          <span className="text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">
            Token expired
          </span>
        ) : isWarning ? (
          <span className="text-xs text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded-full">
            {formatTimeRemaining(expirySeconds)}
          </span>
        ) : (
          <span className="text-xs text-green-400/70 bg-green-400/5 px-2 py-0.5 rounded-full">
            {formatTimeRemaining(expirySeconds)}
          </span>
        )}

        {/* Subscription type */}
        {status.subscription_type && (
          <span className="text-xs text-gray-500 bg-gray-500/10 px-2 py-0.5 rounded-full">
            {status.subscription_type}
          </span>
        )}

        {/* Refresh button */}
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-50 ml-auto"
          title="Refresh token"
        >
          <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? "Refreshing..." : "Refresh token"}
        </button>
      </div>

      {refreshError && (
        <p className="text-xs text-red-400">{refreshError}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Git OAuth flow (GitHub, Bitbucket)
// ---------------------------------------------------------------------------

function GitOAuthFlow({
  service,
  onSuccess,
  onCancel,
}: {
  service: "github" | "bitbucket";
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const startOAuth = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await api<{ authorize_url: string; state: string }>(
        `/api/settings/credentials/${service}/oauth/start`,
        { method: "POST" },
      );
      // Redirect current window to GitHub/Bitbucket (will redirect back to callback)
      window.location.href = data.authorize_url;
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  const Icon = service === "github" ? Github : GitBranch;
  const label = service === "github" ? "GitHub" : "Bitbucket";

  return (
    <div className="space-y-3">
      <button
        onClick={startOAuth}
        disabled={loading}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors w-full justify-center disabled:opacity-50"
      >
        <Icon size={16} />
        {loading ? `Redirecting to ${label}...` : `Connect with ${label}`}
      </button>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button
        onClick={onCancel}
        className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm transition-colors w-full justify-center"
      >
        <X size={14} />
        Cancel
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Git token status bar
// ---------------------------------------------------------------------------

function GitTokenStatusBar({
  service,
  onRefreshDone,
}: {
  service: "github" | "bitbucket";
  onRefreshDone: () => void;
}) {
  const [status, setStatus] = useState<GitTokenStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api<GitTokenStatus>(
        `/api/settings/credentials/${service}/status`,
      );
      setStatus(data);
    } catch {
      // Silently fail — status is optional enhancement
    }
  }, [service]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshError("");
    try {
      await api(`/api/settings/credentials/${service}/oauth/refresh`, {
        method: "POST",
      });
      await fetchStatus();
      onRefreshDone();
    } catch (err: any) {
      setRefreshError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  if (!status || !status.configured) return null;

  const expirySeconds = status.expires_in_seconds ?? 0;
  const isExpired = status.is_expired ?? false;
  const isWarning = !isExpired && (status.needs_refresh ?? false);
  const hasExpiry = status.expires_at !== null && status.expires_at !== undefined;

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        {/* Username */}
        {status.username && (
          <span className="text-xs text-gray-400">
            @{status.username}
          </span>
        )}

        {/* Token expiry (only for tokens that expire) */}
        {hasExpiry && (
          <>
            {isExpired ? (
              <span className="text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">
                Token expired
              </span>
            ) : isWarning ? (
              <span className="text-xs text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded-full">
                {formatTimeRemaining(expirySeconds)}
              </span>
            ) : expirySeconds > 0 ? (
              <span className="text-xs text-green-400/70 bg-green-400/5 px-2 py-0.5 rounded-full">
                {formatTimeRemaining(expirySeconds)}
              </span>
            ) : null}
          </>
        )}

        {/* Scopes */}
        {status.scopes && status.scopes.length > 0 && (
          <span className="text-xs text-gray-500 bg-gray-500/10 px-2 py-0.5 rounded-full">
            {status.scopes.slice(0, 2).join(", ")}
            {status.scopes.length > 2 && ` +${status.scopes.length - 2}`}
          </span>
        )}

        {/* Refresh button (only for services with refresh tokens) */}
        {(service === "bitbucket" || (service === "github" && hasExpiry)) && (
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors disabled:opacity-50 ml-auto"
            title="Refresh token"
          >
            <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        )}
      </div>

      {refreshError && <p className="text-xs text-red-400">{refreshError}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main CredentialCard
// ---------------------------------------------------------------------------

export default function CredentialCard({ service, onUpdate }: CredentialCardProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [showGuide, setShowGuide] = useState(false);

  const guide = SETUP_GUIDES[service.service];
  const isClaude = service.service === "claude_code";
  const isGitHub = service.service === "github";
  const isBitbucket = service.service === "bitbucket";
  const isGitService = isGitHub || isBitbucket;

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

  const cancelEditing = () => {
    setEditing(false);
    setValues({});
    setError("");
    setShowGuide(false);
  };

  return (
    <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-gray-900 dark:text-white font-medium">{service.label}</h3>
          {service.configured ? (
            <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">
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
              className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors"
              title="Edit"
            >
              <Edit3 size={16} />
            </button>
          )}
          {service.configured && !editing && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors disabled:opacity-50"
              title="Delete"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Configured keys summary + Claude token status */}
      {service.configured && !editing && (
        <>
          <p className="text-xs text-gray-500">
            Keys: {service.configured_keys.join(", ")}
            {service.configured_at && (
              <> &middot; Updated {new Date(service.configured_at).toLocaleDateString()}</>
            )}
          </p>
          {isClaude && <ClaudeTokenStatusBar onRefreshDone={onUpdate} />}
          {isGitHub && <GitTokenStatusBar service="github" onRefreshDone={onUpdate} />}
          {isBitbucket && <GitTokenStatusBar service="bitbucket" onRefreshDone={onUpdate} />}
        </>
      )}

      {/* Edit form */}
      {editing && (
        <div className="space-y-3 mt-3">
          {/* Claude OAuth connect button */}
          {isClaude && (
            <ClaudeOAuthFlow
              onSuccess={() => {
                setEditing(false);
                onUpdate();
              }}
              onCancel={cancelEditing}
            />
          )}

          {/* Git OAuth connect button (GitHub, Bitbucket) */}
          {isGitHub && (
            <GitOAuthFlow
              service="github"
              onSuccess={() => {
                setEditing(false);
                onUpdate();
              }}
              onCancel={cancelEditing}
            />
          )}

          {isBitbucket && (
            <GitOAuthFlow
              service="bitbucket"
              onSuccess={() => {
                setEditing(false);
                onUpdate();
              }}
              onCancel={cancelEditing}
            />
          )}

          {/* Divider between OAuth and manual paste */}
          {(isClaude || isGitHub) && (
            <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-600">
              <div className="flex-1 border-t border-light-border dark:border-border" />
              <span>or paste credentials manually</span>
              <div className="flex-1 border-t border-light-border dark:border-border" />
            </div>
          )}

          {/* Setup guide */}
          {guide && (
            <div className="rounded-lg border border-light-border dark:border-border overflow-hidden">
              <button
                type="button"
                onClick={() => setShowGuide(!showGuide)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
              >
                <HelpCircle size={14} className="shrink-0" />
                <span>{guide.title}</span>
                {showGuide ? (
                  <ChevronDown size={14} className="ml-auto shrink-0" />
                ) : (
                  <ChevronRight size={14} className="ml-auto shrink-0" />
                )}
              </button>
              {showGuide && (
                <div className="px-3 pb-3 space-y-3">
                  <ol className="space-y-2.5">
                    {guide.steps.map((step, i) => (
                      <li key={i} className="flex gap-2.5 text-sm">
                        <span className="text-accent font-medium shrink-0">
                          {i + 1}.
                        </span>
                        <div className="min-w-0">
                          <p className="text-gray-700 dark:text-gray-300">{step.instruction}</p>
                          {step.code && (
                            <pre className="mt-1.5 px-3 py-2 bg-gray-100 dark:bg-surface rounded-md text-xs text-gray-600 dark:text-gray-400 font-mono overflow-x-auto whitespace-pre-wrap break-all">
                              {step.code}
                            </pre>
                          )}
                        </div>
                      </li>
                    ))}
                  </ol>
                  {guide.note && (
                    <p className="text-xs text-gray-500 border-t border-light-border dark:border-border pt-2">
                      {guide.note}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {service.key_definitions.map((keyDef) => (
            <div key={keyDef.key}>
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
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
                  className="w-full bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-600 font-mono focus:outline-none focus:border-accent"
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
                  className="w-full bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:border-accent"
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
              onClick={cancelEditing}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm transition-colors"
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
