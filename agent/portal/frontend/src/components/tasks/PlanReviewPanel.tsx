import { useState } from "react";
import { CheckCircle, MessageSquare } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { api } from "@/api/client";
import type { Task } from "@/types";

interface PlanReviewPanelProps {
  task: Task;
  onContinued: (newTaskId: string) => void;
}

export default function PlanReviewPanel({ task, onContinued }: PlanReviewPanelProps) {
  const [feedbackMode, setFeedbackMode] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const planContent =
    (task.result as Record<string, unknown>)?.plan_content as string ||
    (task.result as Record<string, unknown>)?.raw_text as string ||
    "";

  const handleApprove = async () => {
    setSubmitting(true);
    setError("");
    try {
      const result = await api<{ task_id: string }>(`/api/tasks/${task.id}/continue`, {
        method: "POST",
        body: JSON.stringify({
          prompt: "The plan has been approved. Please proceed with the full implementation.",
          mode: "execute",
        }),
      });
      if (result.task_id) onContinued(result.task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to approve plan");
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
      const result = await api<{ task_id: string }>(`/api/tasks/${task.id}/continue`, {
        method: "POST",
        body: JSON.stringify({
          prompt: feedback.trim(),
          mode: "plan",
        }),
      });
      if (result.task_id) onContinued(result.task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send feedback");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      {planContent && (
        <div className="bg-surface border border-border rounded-lg p-4 prose prose-invert prose-sm max-w-none max-h-96 overflow-auto">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {planContent}
          </ReactMarkdown>
        </div>
      )}

      {!planContent && (
        <div className="bg-surface border border-border rounded-lg p-4 text-sm text-gray-400">
          Plan completed — check the logs or workspace files for details.
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      {!feedbackMode ? (
        <div className="flex gap-2">
          <button
            onClick={handleApprove}
            disabled={submitting}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600/20 text-green-400 text-sm font-medium hover:bg-green-600/30 transition-colors disabled:opacity-50"
          >
            <CheckCircle size={16} />
            {submitting ? "Approving..." : "Approve & Implement"}
          </button>
          <button
            onClick={() => setFeedbackMode(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-lighter text-gray-300 text-sm hover:bg-border transition-colors"
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
            className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setFeedbackMode(false)}
              className="px-3 py-1.5 text-sm rounded-lg bg-surface-lighter text-gray-300 hover:bg-border transition-colors"
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
