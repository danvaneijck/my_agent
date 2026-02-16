import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, RefreshCw, GitBranch, GitPullRequest, ExternalLink, AlertCircle, RotateCcw } from "lucide-react";
import { useProjectDetail, usePhaseTasks, retryPhase } from "@/hooks/useProjects";
import { usePageTitle } from "@/hooks/usePageTitle";
import { api } from "@/api/client";
import type { ProjectTask } from "@/types";
import { pageVariants } from "@/utils/animations";

const COLUMNS = [
  { key: "todo", label: "To Do", color: "border-gray-500" },
  { key: "doing", label: "In Progress", color: "border-yellow-500" },
  { key: "in_review", label: "In Review", color: "border-blue-500" },
  { key: "done", label: "Done", color: "border-green-500" },
] as const;

type ColumnKey = (typeof COLUMNS)[number]["key"];

function TaskCard({
  task,
  projectId,
  repoOwner,
  repoName,
}: {
  task: ProjectTask;
  projectId: string;
  repoOwner: string | null;
  repoName: string | null;
}) {
  const navigate = useNavigate();

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", task.task_id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onClick={() => navigate(`/projects/${projectId}/tasks/${task.task_id}`)}
      className="bg-gray-100 dark:bg-surface border border-border rounded-lg p-3 cursor-grab active:cursor-grabbing hover:border-border-light transition-colors"
    >
      <p className="text-sm font-medium text-white mb-1">{task.title}</p>

      {task.description && (
        <p className="text-xs text-gray-400 line-clamp-2 mb-2">{task.description}</p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {task.branch_name && (
          <span className="inline-flex items-center gap-1 text-xs text-gray-500 bg-surface-lighter rounded px-1.5 py-0.5">
            <GitBranch size={10} />
            <span className="truncate max-w-[120px]">{task.branch_name.split("/").pop()}</span>
          </span>
        )}
        {task.pr_number && repoOwner && repoName && (
          <a
            href={`https://github.com/${repoOwner}/${repoName}/pull/${task.pr_number}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-xs text-blue-400 bg-blue-500/10 rounded px-1.5 py-0.5 hover:bg-blue-500/20"
          >
            <GitPullRequest size={10} />
            #{task.pr_number}
          </a>
        )}
        {task.issue_number && repoOwner && repoName && (
          <a
            href={`https://github.com/${repoOwner}/${repoName}/issues/${task.issue_number}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-xs text-gray-400 bg-surface-lighter rounded px-1.5 py-0.5 hover:bg-border"
          >
            <ExternalLink size={10} />
            #{task.issue_number}
          </a>
        )}
        {task.claude_task_id && (
          <a
            href={`/tasks/${task.claude_task_id}`}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-xs text-accent bg-accent/10 rounded px-1.5 py-0.5 hover:bg-accent/20"
          >
            task
          </a>
        )}
        {task.status === "failed" && task.error_message && (
          <span className="inline-flex items-center gap-1 text-xs text-red-400" title={task.error_message}>
            <AlertCircle size={10} />
            failed
          </span>
        )}
      </div>
    </div>
  );
}

export default function PhaseDetailPage() {
  const { projectId, phaseId } = useParams<{ projectId: string; phaseId: string }>();
  const { project } = useProjectDetail(projectId);
  const { tasks, loading, error, refetch } = usePhaseTasks(projectId, phaseId);
  const navigate = useNavigate();
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    if (!projectId || !phaseId) return;
    setRetrying(true);
    try {
      await retryPhase(projectId, phaseId);
      navigate(`/projects/${projectId}`);
    } catch {
      setRetrying(false);
    }
  };

  const phase = project?.phases.find((p) => p.phase_id === phaseId);
  usePageTitle(phase ? `${phase.name} - ${project?.name}` : "Phase");

  const columns = COLUMNS.map((col) => ({
    ...col,
    tasks: tasks.filter((t) => t.status === col.key),
  }));

  // Also collect failed tasks to show separately
  const failedTasks = tasks.filter((t) => t.status === "failed");

  const handleDrop = async (e: React.DragEvent, targetStatus: ColumnKey) => {
    e.preventDefault();
    setDragOver(null);
    const taskId = e.dataTransfer.getData("text/plain");
    if (!taskId || !projectId) return;

    const task = tasks.find((t) => t.task_id === taskId);
    if (!task || task.status === targetStatus) return;

    try {
      await api(`/api/projects/${projectId}/tasks/${taskId}`, {
        method: "PUT",
        body: JSON.stringify({ status: targetStatus }),
      });
      refetch();
    } catch (err) {
      console.error("Failed to update task status:", err);
    }
  };

  return (
    <motion.div
      className="p-4 md:p-6 space-y-4"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {/* Back nav */}
      <button
        onClick={() => navigate(`/projects/${projectId}`)}
        className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200"
      >
        <ArrowLeft size={16} /> Back to Project
      </button>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-white">
              {phase?.name || "Phase"}
            </h2>
            {phase?.pr_number && project?.repo_owner && project?.repo_name && (
              <a
                href={`https://github.com/${project.repo_owner}/${project.repo_name}/pull/${phase.pr_number}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-400 bg-blue-500/10 rounded px-2 py-1 hover:bg-blue-500/20"
              >
                <GitPullRequest size={12} />
                PR #{phase.pr_number}
              </a>
            )}
            <button
              onClick={refetch}
              className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
          {phase?.description && (
            <p className="text-sm text-gray-400 mt-1">{phase.description}</p>
          )}
          <p className="text-xs text-gray-500 mt-1">
            {tasks.length} tasks total — drag cards between columns to update status
          </p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Kanban Board */}
      {loading && tasks.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-3 animate-pulse">
              <div className="h-4 bg-surface-lighter/60 rounded w-1/2 mb-3" />
              <div className="space-y-2">
                <div className="h-20 bg-surface-lighter/60 rounded" />
                <div className="h-20 bg-surface-lighter/60 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {columns.map((col) => (
            <div
              key={col.key}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                setDragOver(col.key);
              }}
              onDragLeave={() => setDragOver(null)}
              onDrop={(e) => handleDrop(e, col.key)}
              className={`bg-surface-light border-t-2 ${col.color} border border-border rounded-xl overflow-hidden transition-colors ${
                dragOver === col.key ? "ring-2 ring-accent/50 bg-accent/5" : ""
              }`}
            >
              <div className="px-3 py-2 border-b border-light-border dark:border-border flex items-center justify-between">
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                  {col.label}
                </h3>
                <span className="text-xs text-gray-500">{col.tasks.length}</span>
              </div>
              <div className="p-2 space-y-2 min-h-[100px]">
                {col.tasks.map((task) => (
                  <TaskCard
                    key={task.task_id}
                    task={task}
                    projectId={projectId!}
                    repoOwner={project?.repo_owner || null}
                    repoName={project?.repo_name || null}
                  />
                ))}
                {col.tasks.length === 0 && (
                  <div className="text-center py-4 text-xs text-gray-600">
                    No tasks
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Failed tasks */}
      {failedTasks.length > 0 && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-xl overflow-hidden">
          <div className="px-4 py-2 border-b border-red-500/20 flex items-center justify-between">
            <h3 className="text-xs font-medium text-red-400 uppercase tracking-wider">
              Failed ({failedTasks.length})
            </h3>
            <button
              onClick={handleRetry}
              disabled={retrying}
              className="inline-flex items-center gap-1.5 text-xs text-red-400 hover:text-white px-2.5 py-1 rounded-lg bg-red-500/10 hover:bg-red-500/30 transition-colors disabled:opacity-50"
            >
              <RotateCcw size={12} className={retrying ? "animate-spin" : ""} />
              {retrying ? "Retrying..." : "Retry Failed Tasks"}
            </button>
          </div>
          <div className="p-2 space-y-2">
            {failedTasks.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                projectId={projectId!}
                repoOwner={project?.repo_owner || null}
                repoName={project?.repo_name || null}
              />
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
