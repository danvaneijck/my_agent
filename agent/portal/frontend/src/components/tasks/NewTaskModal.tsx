import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { X, GitBranch } from "lucide-react";
import { api } from "@/api/client";

interface NewTaskModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  defaultRepoUrl?: string;
  defaultBranch?: string;
  defaultPrompt?: string;
}

export default function NewTaskModal({
  open,
  onClose,
  onCreated,
  defaultRepoUrl = "",
  defaultBranch = "",
  defaultPrompt = "",
}: NewTaskModalProps) {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [repoUrl, setRepoUrl] = useState(defaultRepoUrl);
  const [branch, setBranch] = useState(defaultBranch);
  const [newBranch, setNewBranch] = useState("");
  const [mode, setMode] = useState<"execute" | "plan">("execute");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const promptRef = useRef<HTMLTextAreaElement>(null);

  // The branch actually sent to the API: new branch overrides source branch
  const effectiveBranch = newBranch.trim() || branch.trim();

  // Sync defaults when props change (e.g. opened from different repo/branch)
  useEffect(() => {
    if (open) {
      setRepoUrl(defaultRepoUrl);
      setBranch(defaultBranch);
      setNewBranch("");
      setPrompt(defaultPrompt);
      setMode("execute");
      setError("");
      setTimeout(() => promptRef.current?.focus(), 50);
    }
  }, [open, defaultRepoUrl, defaultBranch, defaultPrompt]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError("");

    try {
      const body: Record<string, string> = { prompt: prompt.trim(), mode };
      if (repoUrl.trim()) body.repo_url = repoUrl.trim();
      if (effectiveBranch) body.branch = effectiveBranch;
      // When creating a new branch from a specific source, tell the backend
      // to checkout the source first before creating the new branch
      if (newBranch.trim() && branch.trim()) {
        body.source_branch = branch.trim();
      }

      const result = await api<{ task_id: string }>("/api/tasks", {
        method: "POST",
        body: JSON.stringify(body),
      });

      onClose();
      onCreated?.();

      if (result.task_id) {
        navigate(`/tasks/${result.task_id}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create task");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-surface-light border border-border rounded-xl w-full max-w-lg shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="text-base font-semibold text-white">New Task</h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Repository info (if pre-filled) */}
          {defaultRepoUrl && (
            <div className="space-y-3">
              <div className="bg-surface/50 border border-border rounded-lg px-3 py-2">
                <span className="text-xs text-gray-500 block mb-0.5">Repository</span>
                <span className="text-sm text-gray-300 font-mono">{repoUrl}</span>
                {branch && (
                  <>
                    <span className="text-xs text-gray-500 mx-2">/</span>
                    <span className="text-sm text-accent font-mono">{branch}</span>
                  </>
                )}
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  <GitBranch size={14} className="inline mr-1 -mt-0.5" />
                  New branch name
                  <span className="text-gray-600 ml-1">(optional)</span>
                </label>
                <input
                  value={newBranch}
                  onChange={(e) => setNewBranch(e.target.value)}
                  placeholder={`Leave empty to work on ${branch || "default branch"}`}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent font-mono"
                />
                {newBranch.trim() && (
                  <p className="text-xs text-gray-500 mt-1">
                    Will create <span className="text-accent font-mono">{newBranch.trim()}</span> from{" "}
                    <span className="font-mono">{branch || "default branch"}</span>
                  </p>
                )}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Task description</label>
            <textarea
              ref={promptRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe what you want Claude Code to do..."
              rows={4}
              className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
            />
          </div>

          {/* Repo URL / Branch (collapsible if not pre-filled) */}
          {!defaultRepoUrl && (
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1">
                <label className="block text-sm text-gray-400 mb-1.5">Repository URL</label>
                <input
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo.git"
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
                />
              </div>
              <div className="sm:w-40">
                <label className="block text-sm text-gray-400 mb-1.5">Branch</label>
                <input
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  placeholder="main"
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
                />
              </div>
            </div>
          )}

          {/* Mode */}
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-400">Mode:</label>
            <button
              type="button"
              onClick={() => setMode(mode === "execute" ? "plan" : "execute")}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                mode === "plan"
                  ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                  : "bg-surface-lighter text-gray-300 border border-border"
              }`}
            >
              {mode === "plan" ? "Plan First" : "Execute Directly"}
            </button>
            {mode === "plan" && (
              <span className="text-xs text-gray-500">
                Claude will create a plan for your review before implementing
              </span>
            )}
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-lg bg-surface-lighter text-gray-300 hover:bg-border transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !prompt.trim()}
              className="px-4 py-2 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {submitting
                ? "Starting..."
                : mode === "plan"
                ? "Start Planning"
                : "Start Task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
