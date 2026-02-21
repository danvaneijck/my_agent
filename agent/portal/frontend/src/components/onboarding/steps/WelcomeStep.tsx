import { AlertTriangle, Key, Github, Zap, ChevronRight } from "lucide-react";

interface WelcomeStepProps {
  tokenBudgetMonthly: number | null;
  onNext: () => void;
  onSkip: () => void;
}

export default function WelcomeStep({
  tokenBudgetMonthly,
  onNext,
  onSkip,
}: WelcomeStepProps) {
  return (
    <div className="space-y-6">
      {/* Intro */}
      <div className="text-center space-y-2">
        <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed">
          To get the most out of Nexus, connect your own accounts and API keys.
          This takes about 2 minutes and unlocks unrestricted usage.
        </p>
      </div>

      {/* Token cap warning */}
      <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-4 flex items-start gap-3">
        <AlertTriangle
          size={18}
          className="text-amber-500 dark:text-amber-400 mt-0.5 shrink-0"
        />
        <div>
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
            Token usage is heavily capped without your own credentials
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400/80 mt-1 leading-relaxed">
            {tokenBudgetMonthly != null
              ? `Shared accounts have a monthly budget of ${tokenBudgetMonthly.toLocaleString()} tokens. Add your own API keys to get unlimited usage billed directly to your provider account.`
              : "Shared accounts have a strict monthly token budget. Add your own API keys to get unlimited usage billed directly to your provider account."}
          </p>
        </div>
      </div>

      {/* What we'll set up */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          What we'll set up
        </p>
        <div className="space-y-2">
          {[
            {
              icon: Zap,
              title: "Claude OAuth",
              desc: "Run Claude Code tasks with your own Claude subscription",
            },
            {
              icon: Github,
              title: "GitHub",
              desc: "Enable code tasks, pull requests, and repo management",
            },
            {
              icon: Key,
              title: "LLM API Keys",
              desc: "Use Anthropic, OpenAI, or Google with your own keys",
            },
          ].map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-surface border border-light-border dark:border-border"
            >
              <div className="p-1.5 rounded-md bg-accent/10 text-accent shrink-0">
                <Icon size={15} />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  {title}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2 pt-2">
        <button
          onClick={onNext}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
        >
          Get started
          <ChevronRight size={16} />
        </button>
        <button
          onClick={onSkip}
          className="w-full text-center text-sm text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors py-1"
        >
          Skip for now
        </button>
      </div>
    </div>
  );
}
