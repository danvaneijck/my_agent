import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { ShieldOff, Sun, Moon, Monitor, CheckCircle, XCircle } from "lucide-react";
import { api } from "@/api/client";
import { useTheme } from "@/contexts/ThemeContext";
import { usePageTitle } from "@/hooks/usePageTitle";
import CredentialCard from "@/components/settings/CredentialCard";
import ConnectedAccounts from "@/components/settings/ConnectedAccounts";

type Tab = "appearance" | "profile" | "accounts" | "credentials";

interface ProfileData {
  user_id: string;
  username: string;
  permission_level: string;
  token_budget_monthly: number | null;
  tokens_used_this_month: number;
  created_at: string | null;
}

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

interface ConnectedAccount {
  platform: string;
  username: string | null;
  platform_user_id: string;
}

export default function SettingsPage() {
  usePageTitle("Settings");
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>("appearance");
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [services, setServices] = useState<ServiceCredentialInfo[]>([]);
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [credentialsError, setCredentialsError] = useState<string | null>(null);
  const [oauthMessage, setOauthMessage] = useState<{ type: "success" | "error"; provider: string; message: string } | null>(null);
  const { theme, setTheme, resolvedTheme } = useTheme();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setCredentialsError(null);

    const [profileResult, credsResult, accountsResult] = await Promise.allSettled([
      api<ProfileData>("/api/settings/profile"),
      api<{ services: ServiceCredentialInfo[] }>("/api/settings/credentials"),
      api<{ accounts: ConnectedAccount[] }>("/api/settings/connected-accounts"),
    ]);

    if (profileResult.status === "fulfilled") {
      setProfile(profileResult.value);
    }

    if (credsResult.status === "fulfilled") {
      setServices(credsResult.value.services || []);
    } else {
      setServices([]);
      const errMsg = (credsResult.reason as Error)?.message || "";
      setCredentialsError(
        errMsg.includes("503")
          ? "Credential storage not configured. Set CREDENTIAL_ENCRYPTION_KEY in your .env file."
          : "Failed to load credentials."
      );
    }

    if (accountsResult.status === "fulfilled") {
      setAccounts(accountsResult.value.accounts || []);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Check for OAuth callback status in URL query params
  useEffect(() => {
    const oauth = searchParams.get("oauth");
    const status = searchParams.get("status");
    const message = searchParams.get("message");

    if (oauth && status) {
      if (status === "success") {
        setOauthMessage({
          type: "success",
          provider: oauth,
          message: `Successfully connected ${oauth.charAt(0).toUpperCase() + oauth.slice(1)} account`,
        });
        setTab("credentials"); // Switch to credentials tab
      } else if (status === "error") {
        setOauthMessage({
          type: "error",
          provider: oauth,
          message: message || `Failed to connect ${oauth.charAt(0).toUpperCase() + oauth.slice(1)} account`,
        });
        setTab("credentials"); // Switch to credentials tab
      }
      // Clear OAuth params from URL
      setSearchParams({});

      // Auto-dismiss success messages after 5 seconds
      if (status === "success") {
        setTimeout(() => setOauthMessage(null), 5000);
      }
    }
  }, [searchParams, setSearchParams]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "appearance", label: "Appearance" },
    { key: "credentials", label: "Credentials" },
    { key: "accounts", label: "Connected Accounts" },
    { key: "profile", label: "Profile" },
  ];

  const themeOptions = [
    {
      value: "light" as const,
      label: "Light",
      description: "Light mode for daytime use",
      icon: Sun,
    },
    {
      value: "dark" as const,
      label: "Dark",
      description: "Dark mode for reduced eye strain",
      icon: Moon,
    },
    {
      value: "system" as const,
      label: "System",
      description: "Follow your system preference",
      icon: Monitor,
    },
  ];

  return (
    <motion.div
      className="max-w-3xl mx-auto space-y-6"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >

      {/* Tabs */}
      <div className="mt-4 flex gap-1 bg-surface-light rounded-lg p-1 border border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${tab === t.key
              ? "bg-accent/15 text-accent-hover"
              : "text-gray-400 hover:text-gray-200"
              }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* OAuth callback message */}
      {oauthMessage && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className={`rounded-xl border p-4 flex items-start gap-3 ${
            oauthMessage.type === "success"
              ? "bg-green-500/10 border-green-500/30"
              : "bg-red-500/10 border-red-500/30"
          }`}
        >
          {oauthMessage.type === "success" ? (
            <CheckCircle size={20} className="text-green-400 mt-0.5 shrink-0" />
          ) : (
            <XCircle size={20} className="text-red-400 mt-0.5 shrink-0" />
          )}
          <div className="flex-1">
            <p className={`text-sm font-medium ${
              oauthMessage.type === "success" ? "text-green-300" : "text-red-300"
            }`}>
              {oauthMessage.message}
            </p>
          </div>
          <button
            onClick={() => setOauthMessage(null)}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <XCircle size={16} />
          </button>
        </motion.div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {/* Appearance tab */}
          {tab === "appearance" && (
            <div className="space-y-6">
              <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-6">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                  Theme
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                  Choose how Nexus looks to you. Select a single theme, or sync
                  with your system and automatically switch between day and night
                  themes.
                </p>

                <div className="space-y-3">
                  {themeOptions.map((option) => {
                    const Icon = option.icon;
                    const isSelected = theme === option.value;

                    return (
                      <button
                        key={option.value}
                        onClick={() => setTheme(option.value)}
                        className={`w-full flex items-start gap-4 p-4 rounded-lg border-2 transition-all ${
                          isSelected
                            ? "border-accent bg-accent/5"
                            : "border-light-border dark:border-border hover:border-accent/50 hover:bg-gray-50 dark:hover:bg-surface-lighter/50"
                        }`}
                      >
                        <div
                          className={`p-2 rounded-lg ${
                            isSelected
                              ? "bg-accent/15 text-accent"
                              : "bg-gray-100 dark:bg-surface-lighter text-gray-600 dark:text-gray-400"
                          }`}
                        >
                          <Icon size={20} />
                        </div>
                        <div className="flex-1 text-left">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900 dark:text-white">
                              {option.label}
                            </span>
                            {isSelected && (
                              <svg
                                className="w-4 h-4 text-accent"
                                fill="currentColor"
                                viewBox="0 0 20 20"
                              >
                                <path
                                  fillRule="evenodd"
                                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                  clipRule="evenodd"
                                />
                              </svg>
                            )}
                          </div>
                          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                            {option.description}
                          </p>
                          {isSelected && theme === "system" && (
                            <p className="text-xs text-accent mt-2">
                              Currently: {resolvedTheme === "dark" ? "Dark" : "Light"}
                            </p>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Profile tab */}
          {tab === "profile" && profile && (
            <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-6 space-y-4">
              <h2 className="text-lg font-semibold text-white">Profile</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Username</span>
                  <p className="text-white mt-1">{profile.username}</p>
                </div>
                <div>
                  <span className="text-gray-400">Permission Level</span>
                  <p className="text-white mt-1 capitalize">
                    {profile.permission_level}
                  </p>
                </div>
                <div>
                  <span className="text-gray-400">Token Usage</span>
                  {profile.token_budget_monthly === null ? (
                    <p className="text-white mt-1">Unlimited</p>
                  ) : (
                    <div className="mt-1">
                      <p className="text-white">
                        {profile.tokens_used_this_month.toLocaleString()} / {profile.token_budget_monthly.toLocaleString()}
                      </p>
                      <div className="w-full bg-surface rounded-full h-1.5 mt-1.5">
                        <div
                          className={`h-1.5 rounded-full transition-all ${profile.tokens_used_this_month / profile.token_budget_monthly > 0.9
                            ? "bg-red-500"
                            : profile.tokens_used_this_month / profile.token_budget_monthly > 0.7
                              ? "bg-yellow-500"
                              : "bg-green-500"
                            }`}
                          style={{
                            width: `${Math.min(100, (profile.tokens_used_this_month / profile.token_budget_monthly) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                <div>
                  <span className="text-gray-400">Member Since</span>
                  <p className="text-white mt-1">
                    {profile.created_at
                      ? new Date(profile.created_at).toLocaleDateString()
                      : "N/A"}
                  </p>
                </div>
              </div>

              {/* Connected platforms summary */}
              {accounts.length > 0 && (
                <div className="pt-4 border-t border-light-border dark:border-border">
                  <span className="text-sm text-gray-400">Connected Platforms</span>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {accounts.map((account) => (
                      <span
                        key={`${account.platform}-${account.platform_user_id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-accent/10 text-accent-hover border border-accent/20"
                      >
                        {account.platform.charAt(0).toUpperCase() + account.platform.slice(1)}
                        {account.username && (
                          <span className="text-gray-400">({account.username})</span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Connected Accounts tab */}
          {tab === "accounts" && (
            <ConnectedAccounts accounts={accounts} />
          )}

          {/* Credentials tab */}
          {tab === "credentials" && (
            <div className="space-y-4">
              {credentialsError ? (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-start gap-3">
                  <ShieldOff size={18} className="text-yellow-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm text-yellow-300 font-medium">
                      Credential storage unavailable
                    </p>
                    <p className="text-sm text-yellow-400/70 mt-1">
                      {credentialsError}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-400">
                  Configure credentials for each service. Values are encrypted at
                  rest and never displayed after saving.
                </p>
              )}
              {services.map((svc) => (
                <CredentialCard
                  key={svc.service}
                  service={svc}
                  onUpdate={fetchData}
                />
              ))}
            </div>
          )}
        </>
      )}
    </motion.div>
  );
}
