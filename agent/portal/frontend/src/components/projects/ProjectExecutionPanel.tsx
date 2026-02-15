import { useState, useEffect } from "react";
import { Clock, ExternalLink, Pause, CheckCircle, AlertCircle } from "lucide-react";
import { api } from "@/api/client";

interface ExecutionStatus {
  project_id: string;
  project_status: string;
  current_phase: {
    phase_id: string;
    name: string;
    status: string;
  } | null;
  claude_task_id: string | null;
  claude_task_status: {
    status: string;
    elapsed_seconds: number | null;
  } | null;
  total_tasks: number;
  task_counts: Record<string, number>;
}

interface ProjectExecutionPanelProps {
  projectId: string;
  onExecutionComplete: () => void;
  onPause: () => void;
}

function formatElapsed(seconds: number | null): string {
  if (seconds == null) return "-";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

export default function ProjectExecutionPanel({
  projectId,
  onExecutionComplete,
  onPause,
}: ProjectExecutionPanelProps) {
  const [status, setStatus] = useState<ExecutionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [pausing, setPausing] = useState(false);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await api<ExecutionStatus>(`/api/projects/${projectId}/execution-status`);
        setStatus(data);

        // Check if we should auto-advance
        if (
          data.current_phase &&
          data.claude_task_status?.status === "completed" &&
          data.project_status === "active"
        ) {
          // Current phase completed, check if there are more phases to execute
          const totalTasks = data.total_tasks;
          const doneTasks = data.task_counts.done || 0;
          const doingTasks = data.task_counts.doing || 0;

          if (doneTasks + doingTasks < totalTasks) {
            // More tasks to do, start next phase
            try {
              await api(`/api/projects/${projectId}/execute-phase`, {
                method: "POST",
                body: JSON.stringify({ auto_push: true }),
              });
              // Polling will pick up the new phase
            } catch {
              // Failed to start next phase, just refresh
              onExecutionComplete();
            }
          } else {
            // All tasks complete
            onExecutionComplete();
          }
        }
      } catch {
        // Silent fail
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [projectId, onExecutionComplete]);

  const handlePause = async () => {
    setPausing(true);
    try {
      await api(`/api/projects/${projectId}`, {
        method: "PUT",
        body: JSON.stringify({ status: "paused" }),
      });
      onPause();
    } catch {
      // Error
    } finally {
      setPausing(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-surface-light border border-border rounded-xl p-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          Loading execution status...
        </div>
      </div>
    );
  }

  if (!status || !status.current_phase) {
    return null;
  }

  const currentPhase = status.current_phase;
  const claudeTask = status.claude_task_status;
  const taskCounts = status.task_counts;
  const totalTasks = status.total_tasks;
  const doneTasks = taskCounts.done || 0;
  const doingTasks = taskCounts.doing || 0;
  const failedTasks = taskCounts.failed || 0;

  const overallPct = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

  // Check if all tasks are complete
  if (doneTasks + failedTasks >= totalTasks && claudeTask?.status === "completed") {
    return (
      <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
        <div className="flex items-center gap-2 text-green-400">
          <CheckCircle size={20} />
          <span className="font-medium">All Phases Complete!</span>
        </div>
        <p className="text-sm text-gray-400 mt-2">
          {doneTasks} tasks completed{failedTasks > 0 && `, ${failedTasks} failed`}
        </p>
      </div>
    );
  }

  const isRunning = claudeTask?.status === "running" || claudeTask?.status === "queued";
  const isPaused = status.project_status === "paused";

  return (
    <div className="bg-surface-light border border-border rounded-xl p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRunning && (
            <div className="w-3 h-3 bg-accent rounded-full animate-pulse" />
          )}
          {isPaused && (
            <Pause size={16} className="text-yellow-400" />
          )}
          <h3 className="text-sm font-medium text-white">
            {isPaused ? "Paused — " : "Executing: "}{currentPhase.name}
          </h3>
        </div>
        {status.claude_task_id && (
          <a
            href={`/tasks/${status.claude_task_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
          >
            View Task <ExternalLink size={12} />
          </a>
        )}
      </div>

      {/* Progress */}
      <div>
        <div className="flex justify-between text-sm text-gray-400 mb-2">
          <span>Overall Progress</span>
          <span>{doneTasks}/{totalTasks} tasks ({overallPct}%)</span>
        </div>
        <div className="h-2 bg-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all"
            style={{ width: `${overallPct}%` }}
          />
        </div>
      </div>

      {/* Status details */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
        {claudeTask && (
          <span className="inline-flex items-center gap-1">
            <Clock size={12} />
            {formatElapsed(claudeTask.elapsed_seconds)}
          </span>
        )}
        {doingTasks > 0 && (
          <span className="text-yellow-400">{doingTasks} in progress</span>
        )}
        {failedTasks > 0 && (
          <span className="inline-flex items-center gap-1 text-red-400">
            <AlertCircle size={12} />
            {failedTasks} failed
          </span>
        )}
      </div>

      {/* Actions */}
      {isRunning && !isPaused && (
        <button
          onClick={handlePause}
          disabled={pausing}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow-600/20 text-yellow-400 text-sm font-medium hover:bg-yellow-600/30 transition-colors disabled:opacity-50"
        >
          <Pause size={16} />
          {pausing ? "Pausing..." : "Pause After This Phase"}
        </button>
      )}

      {isPaused && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-3 py-2 text-sm text-yellow-400">
          Execution paused. Use "Resume Implementation" to continue.
        </div>
      )}
    </div>
  );
}
