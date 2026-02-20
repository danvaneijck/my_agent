import { Link2 } from "lucide-react";

interface ConnectedAccount {
  platform: string;
  username: string | null;
  platform_user_id: string;
}

interface ConnectedAccountsProps {
  accounts: ConnectedAccount[];
}

const PLATFORM_LABELS: Record<string, string> = {
  discord: "Discord",
  google: "Google",
  telegram: "Telegram",
  slack: "Slack",
};

const PLATFORM_COLORS: Record<string, string> = {
  discord: "bg-[#5865F2]/15 text-[#5865F2] border-[#5865F2]/30",
  google: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  telegram: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  slack: "bg-purple-500/15 text-purple-400 border-purple-500/30",
};

export default function ConnectedAccounts({ accounts }: ConnectedAccountsProps) {
  const handleLink = async (provider: string) => {
    try {
      const resp = await fetch(`/api/auth/${provider}/url`);
      if (!resp.ok) throw new Error("Provider not configured");
      const data = await resp.json();
      window.location.href = data.url;
    } catch {
      // provider not available
    }
  };

  // Providers that can be linked
  const linkable = ["discord", "google"];
  const linkedPlatforms = new Set(accounts.map((a) => a.platform));

  return (
    <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Connected Accounts</h2>

      {/* Linked accounts */}
      {accounts.length > 0 ? (
        <div className="space-y-2">
          {accounts.map((account) => (
            <div
              key={`${account.platform}-${account.platform_user_id}`}
              className={`flex items-center justify-between p-3 rounded-lg border ${
                PLATFORM_COLORS[account.platform] || "bg-gray-500/15 text-gray-400 border-gray-500/30"
              }`}
            >
              <div className="flex items-center gap-3">
                <Link2 size={16} />
                <div>
                  <span className="text-sm font-medium">
                    {PLATFORM_LABELS[account.platform] || account.platform}
                  </span>
                  {account.username && (
                    <span className="text-xs opacity-70 ml-2">
                      {account.username}
                    </span>
                  )}
                </div>
              </div>
              <span className="text-xs opacity-60">Linked</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500">No accounts linked yet.</p>
      )}

      {/* Link new providers */}
      {linkable.filter((p) => !linkedPlatforms.has(p)).length > 0 && (
        <div className="pt-2 border-t border-light-border dark:border-border">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Link additional accounts</p>
          <div className="flex gap-2">
            {linkable
              .filter((p) => !linkedPlatforms.has(p))
              .map((provider) => (
                <button
                  key={provider}
                  onClick={() => handleLink(provider)}
                  className="px-4 py-2 rounded-lg bg-gray-100 dark:bg-surface border border-light-border dark:border-border text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:border-accent/50 transition-colors"
                >
                  Link {PLATFORM_LABELS[provider] || provider}
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
