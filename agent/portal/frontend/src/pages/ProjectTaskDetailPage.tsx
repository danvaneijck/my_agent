import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, GitBranch, GitPullRequest, ExternalLink, Clock, AlertCircle } from "lucide-react";
import { api } from "@/api/client";
import type { ProjectTask } from "@/types";

const STATUS_BADGE: Record<string, string> = {
  todo: "bg-gray-500/20 text-gray-400",
  doing: "bg-yellow-500/20 text-yellow-400",
  in_review: "bg-blue-500/20 text-blue-400",
  done: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
};

function formatDate(iso: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleString();
}

export default function ProjectTaskDetailPage() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<ProjectTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTask = useCallback(async () => {
    if (!projectId || !taskId) return;
    try {
      const data = await api<ProjectTask>(`/api/projects/${projectId}/tasks/${taskId}`);
      setTask(data);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load task");
    } finally {
      setLoading(false);
    }
  }, [projectId, taskId]);

  useEffect(() => {
    fetchTask();
  }, [fetchTask]);

  if (loading) {
    return (
      <motion.div
      className="p-4 md:p-6 max-w-3xl mx-auto space-y-4 animate-pulse"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
        <div className="h-5 bg-surface-lighter/60 rounded w-1/4" />
        <div className="h-6 bg-surface-lighter/60 rounded w-1/2" />
        <div className="h-32 bg-surface-lighter/60 rounded" />
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="p-4 md:p-6 max-w-3xl mx-auto">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 mb-4">
          <ArrowLeft size={16} /> Back
        </button>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error || "Task not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-4">
      {/* Back nav */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200"
      >
        <ArrowLeft size={16} /> Back
      </button>

      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <h2 className="text-lg font-semibold text-white">{task.title}</h2>
          <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[task.status]}`}>
            {task.status.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* Description */}
      {task.description && (
        <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Description</h3>
          <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans">{task.description}</pre>
        </div>
      )}

      {/* Acceptance Criteria */}
      {task.acceptance_criteria && (
        <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Acceptance Criteria</h3>
          <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans">{task.acceptance_criteria}</pre>
        </div>
      )}

      {/* Git & Integration Info */}
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 space-y-3">
        <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider">Integration</h3>

        {task.branch_name && (
          <div className="flex items-center gap-2 text-sm">
            <GitBranch size={14} className="text-gray-500" />
            <span className="text-gray-300 font-mono text-xs">{task.branch_name}</span>
          </div>
        )}

        {task.pr_number && (
          <div className="flex items-center gap-2 text-sm">
            <GitPullRequest size={14} className="text-blue-400" />
            <span className="text-gray-300">PR #{task.pr_number}</span>
          </div>
        )}

        {task.issue_number && (
          <div className="flex items-center gap-2 text-sm">
            <ExternalLink size={14} className="text-gray-500" />
            <span className="text-gray-300">Issue #{task.issue_number}</span>
          </div>
        )}

        {task.claude_task_id && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-500 text-xs">Claude Code:</span>
            <a href={`/tasks/${task.claude_task_id}`} className="text-accent hover:underline text-xs">
              {task.claude_task_id}
            </a>
          </div>
        )}

        {!task.branch_name && !task.pr_number && !task.issue_number && !task.claude_task_id && (
          <p className="text-xs text-gray-500">No integration data yet</p>
        )}
      </div>

      {/* Error */}
      {task.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle size={14} className="text-red-400" />
            <h3 className="text-xs font-medium text-red-400 uppercase tracking-wider">Error</h3>
          </div>
          <pre className="text-sm text-red-300 whitespace-pre-wrap font-mono">{task.error_message}</pre>
        </div>
      )}

      {/* Timestamps */}
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 space-y-2">
        <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Timeline</h3>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Clock size={12} />
          Created: {formatDate(task.created_at)}
        </div>
        {task.started_at && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Clock size={12} />
            Started: {formatDate(task.started_at)}
          </div>
        )}
        {task.completed_at && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Clock size={12} />
            Completed: {formatDate(task.completed_at)}
          </div>
        )}
      </div>
    </motion.div>
  );
}
