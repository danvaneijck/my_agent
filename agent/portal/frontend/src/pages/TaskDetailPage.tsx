import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, XCircle, Clock, FolderOpen, Trash2, Brain } from "lucide-react";
import { api } from "@/api/client";
import { usePageTitle } from "@/hooks/usePageTitle";
import StatusBadge from "@/components/common/StatusBadge";
import RepoLabel from "@/components/common/RepoLabel";
import TaskLogViewer from "@/components/tasks/TaskLogViewer";
import TaskOutputViewer from "@/components/tasks/TaskOutputViewer";
import ContinueTaskForm from "@/components/tasks/ContinueTaskForm";
import PlanReviewPanel from "@/components/tasks/PlanReviewPanel";
import TaskChainViewer from "@/components/tasks/TaskChainViewer";
import WorkspaceBrowser from "@/components/tasks/WorkspaceBrowser";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import type { Task, ContextTracking } from "@/types";
import { mapTask } from "@/types";

function formatElapsed(seconds: number | null): string {
  if (seconds == null) return "-";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

interface TokenSummary {
  latest_context_tokens: number;
  peak_context_tokens?: number;
  total_output_tokens: number;
  num_turns: number;
  num_compactions?: number;
  num_continuations?: number;
  model?: string;
}

function ContextUsageBadge({ summary, tracking }: { summary?: TokenSummary; tracking?: ContextTracking }) {
  // Prefer live context_tracking data (available during execution), fall back to token_summary
  const peak = tracking?.peak_context_tokens ?? summary?.peak_context_tokens ?? summary?.latest_context_tokens ?? 0;
  const model = tracking?.context_model ?? summary?.model;
  const maxCtx = model?.includes("gemini") ? 1000000 : 200000;
  const pct = Math.round((peak / maxCtx) * 100);
  const color = pct > 80 ? "text-red-400" : pct > 50 ? "text-yellow-400" : "text-green-400";
  const fmt = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}K` : `${n}`);
  const turns = tracking?.num_turns ?? summary?.num_turns ?? 0;
  const compactions = tracking?.num_compactions ?? summary?.num_compactions ?? 0;
  const continuations = tracking?.num_continuations ?? summary?.num_continuations ?? 0;

  const titleParts = [
    `Peak: ${peak.toLocaleString()} / ${maxCtx.toLocaleString()} context tokens`,
    `${(summary?.total_output_tokens ?? 0).toLocaleString()} output`,
    `${turns} turns`,
  ];
  if (compactions > 0) titleParts.push(`${compactions} compaction(s)`);
  if (continuations > 0) titleParts.push(`${continuations} auto-continuation(s)`);

  return (
    <span
      className={`inline-flex items-center gap-1 ${color}`}
      title={titleParts.join(" | ")}
    >
      <Brain size={12} />
      {fmt(peak)} / {fmt(maxCtx)} ({pct}%)
      {compactions > 0 && (
        <span className="text-xs text-yellow-500" title={`${compactions} compaction(s) detected`}>
          C{compactions}
        </span>
      )}
      {continuations > 0 && (
        <span className="text-xs text-blue-400" title={`${continuations} auto-continuation(s)`}>
          R{continuations}
        </span>
      )}
    </span>
  );
}

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  usePageTitle(task ? `Task ${task.prompt.slice(0, 30)}...` : "Task");
  const [loading, setLoading] = useState(true);
  const [showCancel, setShowCancel] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [viewMode, setViewMode] = useState<"output" | "logs" | "files">("output");

  useEffect(() => {
    if (!taskId) return;
    setLoading(true);
    api<Record<string, unknown>>(`/api/tasks/${taskId}`)
      .then((data) => setTask(mapTask(data)))
      .catch(() => {})
      .finally(() => setLoading(false));

    // Poll for status updates
    const id = setInterval(() => {
      api<Record<string, unknown>>(`/api/tasks/${taskId}`).then((data) => setTask(mapTask(data))).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [taskId]);

  const handleCancel = async () => {
    setShowCancel(false);
    if (!taskId) return;
    try {
      await api(`/api/tasks/${taskId}`, { method: "DELETE" });
      // Refresh task
      const updated = await api<Record<string, unknown>>(`/api/tasks/${taskId}`);
      setTask(mapTask(updated));
    } catch {
      // ignore
    }
  };

  const handleDelete = async () => {
    setShowDelete(false);
    if (!taskId) return;
    try {
      await api(`/api/tasks/${taskId}/workspace`, { method: "DELETE" });
      navigate("/");
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="p-6 text-center text-gray-500">
        Task not found.
        <button onClick={() => navigate("/")} className="ml-2 text-accent hover:underline">
          Back to tasks
        </button>
      </div>
    );
  }

  const isStale =
    task.status === "running" &&
    task.heartbeat &&
    Date.now() - new Date(task.heartbeat).getTime() > 90_000;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 md:px-6 border-b border-light-border dark:border-border space-y-3 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/")}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400"
          >
            <ArrowLeft size={18} />
          </button>
          <StatusBadge status={task.status} stale={!!isStale} />
          <span className="font-mono text-sm text-gray-400">{task.id}</span>
          {task.mode === "plan" && (
            <span className="px-2 py-0.5 rounded text-xs bg-purple-500/20 text-purple-400">
              plan mode
            </span>
          )}
          {task.auto_push && (
            <span className={`px-2 py-0.5 rounded text-xs ${
              task.result?.auto_push
                ? (task.result.auto_push as Record<string, unknown>).success
                  ? "bg-green-500/20 text-green-400"
                  : "bg-red-500/20 text-red-400"
                : "bg-blue-500/20 text-blue-400"
            }`}>
              {task.result?.auto_push
                ? (task.result.auto_push as Record<string, unknown>).success
                  ? "pushed"
                  : "push failed"
                : "auto-push"}
            </span>
          )}

          <div className="flex-1" />

          {(task.status === "running" || task.status === "queued") && (
            <button
              onClick={() => setShowCancel(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600/20 text-red-400 text-sm hover:bg-red-600/30 transition-colors"
            >
              <XCircle size={14} />
              Cancel
            </button>
          )}
          {task.status !== "running" && task.status !== "queued" && (
            <button
              onClick={() => setShowDelete(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-lighter text-gray-400 text-sm hover:text-red-400 hover:bg-red-600/20 transition-colors"
              title="Delete workspace"
            >
              <Trash2 size={14} />
              Delete
            </button>
          )}
        </div>

        <p className="text-sm text-gray-200 line-clamp-3">{task.prompt}</p>

        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
          <span className="inline-flex items-center gap-1">
            <Clock size={12} />
            {formatElapsed(task.elapsed_seconds)}
          </span>
          {task.repo_url && (
            <RepoLabel repoUrl={task.repo_url} branch={task.branch} size="md" />
          )}
          <span className="inline-flex items-center gap-1">
            <FolderOpen size={12} />
            {task.workspace}
          </span>
          {(task.context_tracking && task.context_tracking.num_turns > 0) || task.result?.token_summary != null ? (
            <ContextUsageBadge
              tracking={task.context_tracking?.num_turns ? task.context_tracking : undefined}
              summary={task.result?.token_summary as TokenSummary | undefined}
            />
          ) : null}
        </div>

        {task.error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-sm text-red-400">
            {task.error}
          </div>
        )}

        {/* Plan Review Panel — shown when awaiting user input */}
        {task.status === "awaiting_input" && (
          <PlanReviewPanel
            task={task}
            onContinued={(newId) => navigate(`/tasks/${newId}`)}
          />
        )}

        {/* Resume form — shown for timed out tasks */}
        {task.status === "timed_out" && (
          <ContinueTaskForm
            taskId={task.id}
            onContinued={(newId) => navigate(`/tasks/${newId}`)}
            label="Resume"
          />
        )}

        {/* Continue form — shown for completed non-plan tasks */}
        {task.status === "completed" && (
          <ContinueTaskForm
            taskId={task.id}
            onContinued={(newId) => navigate(`/tasks/${newId}`)}
          />
        )}

        {/* Task chain timeline */}
        {(task.parent_task_id || task.mode === "plan") && (
          <TaskChainViewer taskId={task.id} currentTaskId={task.id} />
        )}
      </div>

      {/* View mode tabs */}
      <div className="flex border-b border-light-border dark:border-border shrink-0">
        {(["output", "logs", "files"] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`px-4 py-2 text-sm font-medium transition-colors capitalize ${
              viewMode === mode
                ? "text-accent border-b-2 border-accent"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {mode}
          </button>
        ))}
      </div>

      {/* Content area — fills remaining space */}
      <div className="flex-1 min-h-0">
        {viewMode === "output" && (
          <TaskOutputViewer taskId={task.id} initialStatus={task.status} />
        )}
        {viewMode === "logs" && (
          <TaskLogViewer taskId={task.id} initialStatus={task.status} />
        )}
        {viewMode === "files" && <WorkspaceBrowser taskId={task.id} />}
      </div>

      <ConfirmDialog
        open={showCancel}
        title="Cancel Task"
        message="This will kill the running container. Are you sure?"
        confirmLabel="Cancel Task"
        onConfirm={handleCancel}
        onCancel={() => setShowCancel(false)}
      />
      <ConfirmDialog
        open={showDelete}
        title="Delete Workspace"
        message="This will permanently delete the workspace directory and all associated tasks. This action cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setShowDelete(false)}
      />
    </div>
  );
}
