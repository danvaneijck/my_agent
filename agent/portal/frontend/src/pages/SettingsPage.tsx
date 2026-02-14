import { useState, useEffect, useCallback } from "react";
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

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [profileData, credsData, accountsData] = await Promise.all([
        api<ProfileData>("/api/settings/profile"),
        api<{ services: ServiceCredentialInfo[] }>("/api/settings/credentials"),
        api<{ accounts: ConnectedAccount[] }>("/api/settings/connected-accounts"),
      ]);
      setProfile(profileData);
      setServices(credsData.services || []);
      setAccounts(accountsData.accounts || []);
    } catch {
      // silently fail — individual sections show errors
    } finally {
      setLoading(false);
    }
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
      <h1 className="text-xl font-bold text-white">Settings</h1>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-light rounded-lg p-1 border border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              tab === t.key
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
                  <span className="text-gray-400">Token Budget</span>
                  <p className="text-white mt-1">
                    {profile.token_budget_monthly === null
                      ? "Unlimited"
                      : `${profile.tokens_used_this_month.toLocaleString()} / ${profile.token_budget_monthly.toLocaleString()}`}
                  </p>
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
            </div>
          )}

          {/* Connected Accounts tab */}
          {tab === "accounts" && (
            <ConnectedAccounts accounts={accounts} />
          )}

          {/* Credentials tab */}
          {tab === "credentials" && (
            <div className="space-y-4">
              <p className="text-sm text-gray-400">
                Configure credentials for each service. Values are encrypted at
                rest and never displayed after saving.
              </p>
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
