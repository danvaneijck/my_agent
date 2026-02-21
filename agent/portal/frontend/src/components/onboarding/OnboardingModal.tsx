/**
 * OnboardingModal — Multi-step wizard shown to users on fresh sign-in when
 * they haven't yet configured Claude OAuth, GitHub OAuth, or LLM API keys.
 *
 * Steps that are already configured are skipped automatically. The modal
 * stays open until the user reaches the final "Complete" step or explicitly
 * skips/dismisses it.
 */

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

import WelcomeStep from "@/components/onboarding/steps/WelcomeStep";
import ClaudeOAuthStep from "@/components/onboarding/steps/ClaudeOAuthStep";
import GitHubOAuthStep from "@/components/onboarding/steps/GitHubOAuthStep";
import LlmSettingsStep from "@/components/onboarding/steps/LlmSettingsStep";
import CompleteStep from "@/components/onboarding/steps/CompleteStep";

export interface OnboardingStatus {
  has_claude_oauth: boolean;
  has_github_oauth: boolean;
  has_llm_key: boolean;
  needs_onboarding: boolean;
  token_budget_monthly: number | null;
  tokens_used_this_month: number;
}

interface OnboardingModalProps {
  status: OnboardingStatus;
  onClose: () => void;
}

interface StepDef {
  id: string;
  title: string;
}

export default function OnboardingModal({ status, onClose }: OnboardingModalProps) {
  // Build the list of steps to show, skipping already-configured ones
  const steps: StepDef[] = [
    { id: "welcome", title: "Welcome to Nexus" },
    ...(!status.has_claude_oauth ? [{ id: "claude", title: "Connect Claude" }] : []),
    ...(!status.has_github_oauth ? [{ id: "github", title: "Connect GitHub" }] : []),
    ...(!status.has_llm_key ? [{ id: "llm", title: "LLM API Keys" }] : []),
    { id: "complete", title: "All done" },
  ];

  const [currentIndex, setCurrentIndex] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());

  const currentStep = steps[currentIndex];
  const isLast = currentIndex === steps.length - 1;
  const isFirst = currentIndex === 0;

  // Count optional steps (everything except welcome + complete)
  const optionalStepIds = steps
    .map((s) => s.id)
    .filter((id) => id !== "welcome" && id !== "complete");

  const markCompleted = (id: string) => {
    setCompletedSteps((prev) => new Set([...prev, id]));
  };

  const goNext = (stepId?: string) => {
    if (stepId) markCompleted(stepId);
    if (isLast) {
      onClose();
    } else {
      setCurrentIndex((i) => i + 1);
    }
  };

  const goSkip = () => {
    if (isLast) {
      onClose();
    } else {
      setCurrentIndex((i) => i + 1);
    }
  };

  // Progress fraction (excluding welcome and complete from count)
  const progressSteps = steps.filter(
    (s) => s.id !== "welcome" && s.id !== "complete"
  );
  const progressCurrent = progressSteps.findIndex(
    (s) => s.id === currentStep.id
  );
  const showProgress = progressCurrent >= 0;

  return (
    // Overlay — fixed over everything, not dismissable by clicking backdrop
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <motion.div
        className="absolute inset-0 bg-black/60"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      />

      {/* Modal panel */}
      <motion.div
        className="relative bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.25, ease: [0.0, 0.0, 0.2, 1] }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-light-border dark:border-border">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">
              {currentStep.title}
            </h2>
            {showProgress && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                {progressCurrent + 1} / {progressSteps.length}
              </span>
            )}
          </div>

          {/* Dismiss button */}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors"
            aria-label="Close onboarding"
          >
            <X size={18} />
          </button>
        </div>

        {/* Progress bar (shown for non-welcome/complete steps) */}
        {progressSteps.length > 0 && (
          <div className="h-0.5 bg-gray-100 dark:bg-surface">
            <motion.div
              className="h-full bg-accent"
              initial={false}
              animate={{
                width: showProgress
                  ? `${((progressCurrent + 1) / progressSteps.length) * 100}%`
                  : isLast
                  ? "100%"
                  : "0%",
              }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
            />
          </div>
        )}

        {/* Step content */}
        <div className="px-6 py-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep.id}
              initial={{ opacity: 0, x: isFirst ? 0 : 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.18 }}
            >
              {currentStep.id === "welcome" && (
                <WelcomeStep
                  tokenBudgetMonthly={status.token_budget_monthly}
                  onNext={() => goNext()}
                  onSkip={onClose}
                />
              )}

              {currentStep.id === "claude" && (
                <ClaudeOAuthStep
                  onNext={() => goNext("claude")}
                  onSkip={goSkip}
                />
              )}

              {currentStep.id === "github" && (
                <GitHubOAuthStep
                  onNext={() => goNext("github")}
                  onSkip={goSkip}
                />
              )}

              {currentStep.id === "llm" && (
                <LlmSettingsStep
                  tokenBudgetMonthly={status.token_budget_monthly}
                  onNext={() => goNext("llm")}
                  onSkip={goSkip}
                />
              )}

              {currentStep.id === "complete" && (
                <CompleteStep
                  completedSteps={completedSteps}
                  totalOptionalSteps={optionalStepIds.length}
                  onClose={onClose}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}
