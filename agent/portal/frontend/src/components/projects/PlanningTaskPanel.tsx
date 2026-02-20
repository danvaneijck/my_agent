import { useState, useEffect } from "react";
import { Clock, CheckCircle, MessageSquare, ExternalLink, AlertCircle, RefreshCw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { api } from "@/api/client";
import { mapTask } from "@/types";
import type { Task } from "@/types";

interface PlanningTaskPanelProps {
  planningTaskId: string;
  projectId: string;
  onPlanApplied: () => void;
}

function formatElapsed(seconds: number | null): string {
  if (seconds == null) return "-";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

export default function PlanningTaskPanel({
  planningTaskId,
  projectId,
  onPlanApplied,
}: PlanningTaskPanelProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [feedbackMode, setFeedbackMode] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchTask = async () => {
      try {
        const data = await api<Record<string, unknown>>(`/api/tasks/${planningTaskId}`);
        setTask(mapTask(data));
      } catch {
        // Silent fail on poll
      } finally {
        setLoading(false);
      }
    };

    fetchTask();
    const interval = setInterval(fetchTask, 5000);
    return () => clearInterval(interval);
  }, [planningTaskId]);

  const handleApply = async () => {
    setSubmitting(true);
    setError("");
    try {
      await api(`/api/projects/${projectId}/apply-plan`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      onPlanApplied();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to apply plan");
    } finally {
      setSubmitting(false);
    }
  };

  const handleFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedback.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await api<{ task_id: string }>(`/api/tasks/${planningTaskId}/continue`, {
        method: "POST",
        body: JSON.stringify({
          prompt: feedback.trim(),
          mode: "plan",
        }),
      });
      setFeedback("");
      setFeedbackMode(false);
      // Polling will pick up the new task automatically
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send feedback");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = async () => {
    // Retry planning by kicking off a new task
    setSubmitting(true);
    setError("");
    try {
      await api(`/api/projects/${projectId}/kickoff`, {
        method: "POST",
        body: JSON.stringify({ mode: "plan", auto_push: true }),
      });
      onPlanApplied(); // Refresh the project page
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to retry planning");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4">
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          Loading planning task...
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-400">
        Planning task not found.
      </div>
    );
  }

  const planContent =
    (task.result as Record<string, unknown>)?.plan_content as string ||
    (task.result as Record<string, unknown>)?.raw_text as string ||
    "";

  // Running or queued
  if (task.status === "running" || task.status === "queued") {
    return (
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
              {task.status === "queued" ? "Planning task queued..." : "Claude is creating your project plan..."}
            </span>
          </div>
          <a
            href={`/tasks/${planningTaskId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            View Full Task <ExternalLink size={12} />
          </a>
        </div>
        {task.prompt && (
          <p className="text-sm text-gray-400 line-clamp-2">{task.prompt}</p>
        )}
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="inline-flex items-center gap-1">
            <Clock size={12} />
            {formatElapsed(task.elapsed_seconds)}
          </span>
        </div>
      </div>
    );
  }

  // Awaiting input (plan ready for review)
  if (task.status === "awaiting_input") {
    return (
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
            <CheckCircle size={16} className="text-green-400" />
            Plan Ready for Review
          </h3>
          <a
            href={`/tasks/${planningTaskId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            View Full Task <ExternalLink size={12} />
          </a>
        </div>

        {planContent && (
          <div className="bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg p-4 prose dark:prose-invert prose-sm max-w-none max-h-96 overflow-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {planContent}
            </ReactMarkdown>
          </div>
        )}

        {!planContent && (
          <div className="bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg p-4 text-sm text-gray-500 dark:text-gray-400">
            Plan completed — check the task logs for details.
          </div>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}

        {!feedbackMode ? (
          <div className="flex gap-2">
            <button
              onClick={handleApply}
              disabled={submitting}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600/20 text-green-400 text-sm font-medium hover:bg-green-600/30 transition-colors disabled:opacity-50"
            >
              <CheckCircle size={16} />
              {submitting ? "Applying Plan..." : "Apply Plan"}
            </button>
            <button
              onClick={() => setFeedbackMode(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 dark:bg-surface-lighter text-gray-700 dark:text-gray-300 text-sm hover:bg-gray-200 dark:hover:bg-border transition-colors"
            >
              <MessageSquare size={16} />
              Give Feedback
            </button>
          </div>
        ) : (
          <form onSubmit={handleFeedback} className="space-y-3">
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Describe what changes you'd like to the plan..."
              rows={3}
              autoFocus
              className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setFeedbackMode(false)}
                className="px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-surface-lighter text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-border transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !feedback.trim()}
                className="px-3 py-1.5 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
              >
                {submitting ? "Sending..." : "Send Feedback"}
              </button>
            </div>
          </form>
        )}
      </div>
    );
  }

  // Completed (plan mode finished with output)
  if (task.status === "completed") {
    return (
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white flex items-center gap-2">
            <CheckCircle size={16} className="text-green-400" />
            Planning Complete
          </h3>
          <a
            href={`/tasks/${planningTaskId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            View Full Task <ExternalLink size={12} />
          </a>
        </div>

        {planContent && (
          <div className="bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg p-4 prose dark:prose-invert prose-sm max-w-none max-h-96 overflow-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {planContent}
            </ReactMarkdown>
          </div>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          onClick={handleApply}
          disabled={submitting}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600/20 text-green-400 text-sm font-medium hover:bg-green-600/30 transition-colors disabled:opacity-50"
        >
          <CheckCircle size={16} />
          {submitting ? "Applying Plan..." : "Apply Plan"}
        </button>
      </div>
    );
  }

  // Failed, cancelled, or timed out
  if (task.status === "failed" || task.status === "cancelled" || task.status === "timed_out") {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-red-400 flex items-center gap-2">
            <AlertCircle size={16} />
            Planning {task.status === "timed_out" ? "Timed Out" : "Failed"}
          </h3>
          <a
            href={`/tasks/${planningTaskId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            View Full Task <ExternalLink size={12} />
          </a>
        </div>

        {task.error && (
          <p className="text-sm text-red-400">{task.error}</p>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          onClick={handleRetry}
          disabled={submitting}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/20 text-accent text-sm font-medium hover:bg-accent/30 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} />
          {submitting ? "Retrying..." : "Retry Planning"}
        </button>
      </div>
    );
  }

  return null;
}
