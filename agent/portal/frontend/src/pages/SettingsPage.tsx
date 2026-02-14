import { useState, useEffect, useCallback } from "react";
import { ShieldOff } from "lucide-react";
import { api } from "@/api/client";
import CredentialCard from "@/components/settings/CredentialCard";
import ConnectedAccounts from "@/components/settings/ConnectedAccounts";

type Tab = "profile" | "accounts" | "credentials";

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
  const [tab, setTab] = useState<Tab>("credentials");
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [services, setServices] = useState<ServiceCredentialInfo[]>([]);
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [credentialsError, setCredentialsError] = useState<string | null>(null);

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

  const tabs: { key: Tab; label: string }[] = [
    { key: "credentials", label: "Credentials" },
    { key: "accounts", label: "Connected Accounts" },
    { key: "profile", label: "Profile" },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6">

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

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {/* Profile tab */}
          {tab === "profile" && profile && (
            <div className="bg-surface-light border border-border rounded-xl p-6 space-y-4">
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
                <div className="pt-4 border-t border-border">
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
    </div>
  );
}
