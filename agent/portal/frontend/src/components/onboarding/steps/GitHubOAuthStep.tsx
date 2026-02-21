import { useState } from "react";
import { api } from "@/api/client";
import { Github, X } from "lucide-react";

interface GitHubOAuthStepProps {
  onNext: () => void;
  onSkip: () => void;
}

export default function GitHubOAuthStep({ onNext: _onNext, onSkip }: GitHubOAuthStepProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const startOAuth = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await api<{ authorize_url: string; state: string }>(
        "/api/settings/credentials/github/oauth/start",
        { method: "POST" }
      );
      // Redirect current window — GitHub sends back to /settings?oauth=github&status=success
      window.location.href = data.authorize_url;
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Explanation */}
      <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
        Connect GitHub to enable code tasks, pull request management, and
        repository browsing. The agent will use your account when pushing
        branches or opening PRs on your behalf.
      </p>

      <button
        onClick={startOAuth}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
      >
        <Github size={16} />
        {loading ? "Redirecting to GitHub…" : "Connect with GitHub"}
      </button>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <p className="text-xs text-gray-500 dark:text-gray-400">
        You will be redirected to GitHub to authorise Nexus. After authorising,
        you will return here automatically.
      </p>

      {/* Skip */}
      <button
        onClick={onSkip}
        className="flex items-center gap-1.5 text-sm text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
      >
        <X size={14} />
        Skip this step
      </button>
    </div>
  );
}
