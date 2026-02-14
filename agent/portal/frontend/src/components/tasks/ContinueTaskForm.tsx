import { useState } from "react";
import { IterationCw } from "lucide-react";
import { api } from "@/api/client";

interface ContinueTaskFormProps {
  taskId: string;
  onContinued: (newTaskId: string) => void;
  label?: string;
}

export default function ContinueTaskForm({ taskId, onContinued, label = "Continue" }: ContinueTaskFormProps) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError("");

    try {
      const result = await api<{ task_id: string }>(`/api/tasks/${taskId}/continue`, {
        method: "POST",
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      setPrompt("");
      setOpen(false);
      if (result.task_id) onContinued(result.task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to continue task");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-lighter text-gray-300 text-sm hover:bg-border transition-colors"
      >
        <IterationCw size={14} />
        {label}
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 mt-3">
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Follow-up instructions for Claude Code..."
        rows={2}
        autoFocus
        className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
      />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="px-3 py-1.5 text-sm rounded-lg bg-surface-lighter text-gray-300 hover:bg-border transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting || !prompt.trim()}
          className="px-3 py-1.5 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          {submitting ? "Starting..." : `${label} Task`}
        </button>
      </div>
    </form>
  );
}
