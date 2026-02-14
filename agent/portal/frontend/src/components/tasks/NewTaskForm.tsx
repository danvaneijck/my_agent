import { useState } from "react";
import { Play } from "lucide-react";
import { api } from "@/api/client";

interface NewTaskFormProps {
  onCreated: () => void;
}

export default function NewTaskForm({ onCreated }: NewTaskFormProps) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [mode, setMode] = useState<"execute" | "plan">("execute");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError("");

    try {
      const body: Record<string, string> = { prompt: prompt.trim(), mode };
      if (repoUrl.trim()) body.repo_url = repoUrl.trim();
      if (branch.trim()) body.branch = branch.trim();

      await api("/api/tasks", {
        method: "POST",
        body: JSON.stringify(body),
      });

      setPrompt("");
      setRepoUrl("");
      setBranch("");
      setMode("execute");
      setOpen(false);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create task");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
      >
        <Play size={16} />
        New Task
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-surface-light border border-border rounded-xl p-4 space-y-3"
    >
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe the task for Claude Code..."
        rows={3}
        autoFocus
        className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
      />
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="Repository URL (optional)"
          className="flex-1 px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
        />
        <input
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          placeholder="Branch (optional)"
          className="sm:w-40 px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
        />
      </div>
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
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="px-4 py-2 text-sm rounded-lg bg-surface-lighter text-gray-300 hover:bg-border transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting || !prompt.trim()}
          className="px-4 py-2 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          {submitting ? "Starting..." : mode === "plan" ? "Start Planning" : "Start Task"}
        </button>
      </div>
    </form>
  );
}
