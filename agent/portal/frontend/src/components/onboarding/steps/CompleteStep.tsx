import { Check, Minus, Settings } from "lucide-react";

interface CompleteStepProps {
  completedSteps: Set<string>;
  totalOptionalSteps: number;
  onClose: () => void;
}

const STEP_LABELS: Record<string, { label: string; desc: string }> = {
  claude: {
    label: "Claude OAuth",
    desc: "Claude Code tasks use your subscription",
  },
  github: {
    label: "GitHub",
    desc: "Repo management and PRs enabled",
  },
  llm: {
    label: "LLM API Keys",
    desc: "Unlimited usage billed to your provider",
  },
};

export default function CompleteStep({
  completedSteps,
  totalOptionalSteps,
  onClose,
}: CompleteStepProps) {
  const allDone = completedSteps.size === totalOptionalSteps;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <div className="flex justify-center mb-3">
          <div
            className={`w-14 h-14 rounded-full flex items-center justify-center ${
              allDone
                ? "bg-green-400/15"
                : "bg-accent/10"
            }`}
          >
            <Check
              size={28}
              className={allDone ? "text-green-400" : "text-accent"}
            />
          </div>
        </div>
        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
          {allDone ? "You're all set!" : "Setup complete"}
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {allDone
            ? "All credentials are configured. Enjoy unrestricted access."
            : "You can configure remaining credentials anytime in Settings."}
        </p>
      </div>

      {/* Summary */}
      <div className="space-y-2">
        {Object.entries(STEP_LABELS).map(([id, { label, desc }]) => {
          const done = completedSteps.has(id);
          return (
            <div
              key={id}
              className={`flex items-center gap-3 p-3 rounded-lg border ${
                done
                  ? "border-green-400/30 bg-green-400/5"
                  : "border-light-border dark:border-border bg-gray-50 dark:bg-surface"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                  done
                    ? "bg-green-400/20 text-green-400"
                    : "bg-gray-200 dark:bg-surface-lighter text-gray-400 dark:text-gray-500"
                }`}
              >
                {done ? <Check size={13} /> : <Minus size={13} />}
              </div>
              <div>
                <p
                  className={`text-sm font-medium ${
                    done
                      ? "text-gray-900 dark:text-white"
                      : "text-gray-500 dark:text-gray-400"
                  }`}
                >
                  {label}
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {done ? desc : "Not configured — set up in Settings"}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2">
        <button
          onClick={onClose}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
        >
          Go to dashboard
        </button>
        {!allDone && (
          <a
            href="/settings?tab=credentials"
            className="w-full flex items-center justify-center gap-1.5 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            <Settings size={14} />
            Open Settings
          </a>
        )}
      </div>
    </div>
  );
}
