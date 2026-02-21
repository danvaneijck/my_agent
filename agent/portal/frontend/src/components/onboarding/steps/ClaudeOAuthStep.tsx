import { useState } from "react";
import { api } from "@/api/client";
import { AlertTriangle, Check, ExternalLink, X, Zap } from "lucide-react";

interface ClaudeOAuthStepProps {
  onNext: () => void;
  onSkip: () => void;
}

type FlowStep = "idle" | "authorizing" | "exchanging" | "done";

export default function ClaudeOAuthStep({ onNext, onSkip }: ClaudeOAuthStepProps) {
  const [flowStep, setFlowStep] = useState<FlowStep>("idle");
  const [authCode, setAuthCode] = useState("");
  const [error, setError] = useState("");

  const startOAuth = async () => {
    setError("");
    setFlowStep("authorizing");
    try {
      const data = await api<{ authorize_url: string; state: string }>(
        "/api/settings/credentials/claude_code/oauth/start",
        { method: "POST" }
      );
      window.open(data.authorize_url, "_blank", "noopener,noreferrer");
    } catch (err: any) {
      setError(err.message);
      setFlowStep("idle");
    }
  };

  const exchangeCode = async () => {
    const code = authCode.trim();
    if (!code) {
      setError("Please paste the authorization code from the Anthropic page");
      return;
    }
    setError("");
    setFlowStep("exchanging");
    try {
      await api("/api/settings/credentials/claude_code/oauth/exchange", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setFlowStep("done");
      setTimeout(() => onNext(), 800);
    } catch (err: any) {
      setError(err.message);
      setFlowStep("authorizing");
    }
  };

  if (flowStep === "done") {
    return (
      <div className="flex flex-col items-center gap-3 py-8">
        <div className="w-12 h-12 rounded-full bg-green-400/15 flex items-center justify-center">
          <Check size={24} className="text-green-400" />
        </div>
        <p className="text-sm font-medium text-gray-900 dark:text-white">
          Claude account connected!
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Explanation */}
      <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
        Connecting your Claude account lets the agent run Claude Code tasks using
        your own Claude subscription — no shared quota, no throttling.
      </p>

      {/* Cap warning */}
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/8 p-3 flex items-start gap-2.5">
        <AlertTriangle size={15} className="text-amber-500 dark:text-amber-400 mt-0.5 shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-400/80 leading-relaxed">
          Without Claude OAuth, code tasks run on shared quota and may be
          paused or rejected when the budget is exhausted.
        </p>
      </div>

      {flowStep === "idle" && (
        <button
          onClick={startOAuth}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
        >
          <Zap size={16} />
          Connect Claude Account
        </button>
      )}

      {(flowStep === "authorizing" || flowStep === "exchanging") && (
        <div className="space-y-4">
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
            <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
              A new tab opened for Anthropic login. After you authorize:
            </p>
            <ol className="text-sm text-gray-600 dark:text-gray-400 space-y-1 ml-4 list-decimal">
              <li>Copy the code shown on the Anthropic page</li>
              <li>Paste it below and click Connect</li>
            </ol>
          </div>

          <div>
            <label className="block text-sm text-gray-500 dark:text-gray-400 mb-1">
              Authorization code
            </label>
            <input
              type="text"
              value={authCode}
              onChange={(e) => setAuthCode(e.target.value)}
              placeholder="Paste the code from Anthropic here…"
              className="w-full bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-600 font-mono focus:outline-none focus:border-accent"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") exchangeCode();
              }}
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex gap-2 flex-wrap">
            <button
              onClick={exchangeCode}
              disabled={flowStep === "exchanging"}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              <Check size={14} />
              {flowStep === "exchanging" ? "Connecting…" : "Connect"}
            </button>
            <button
              onClick={startOAuth}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm transition-colors"
              title="Reopen Anthropic login"
            >
              <ExternalLink size={14} />
              Reopen login
            </button>
          </div>
        </div>
      )}

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
