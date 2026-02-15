import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RefreshCw, ChevronRight, FileText, Trash2, Play, Zap } from "lucide-react";
import { useProjectDetail, executePhase, startWorkflow } from "@/hooks/useProjects";
import { api } from "@/api/client";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import PlanningTaskPanel from "@/components/projects/PlanningTaskPanel";
import ProjectExecutionPanel from "@/components/projects/ProjectExecutionPanel";
import type { ProjectPhase } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  planning: "bg-blue-500/20 text-blue-400",
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  archived: "bg-gray-600/20 text-gray-500",
};

const PHASE_STATUS_COLORS: Record<string, string> = {
  planned: "bg-gray-500/20 text-gray-400",
  in_progress: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
};

function PhaseRow({ phase, projectId, onClick }: { phase: ProjectPhase; projectId: string; onClick: () => void }) {
  const counts = phase.task_counts || {};
  const total = Object.values(counts).reduce((a, b) => a + (b || 0), 0);
  const done = counts.done || 0;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <button
      onClick={onClick}
      className="w-full px-4 py-3 hover:bg-surface-lighter/50 transition-colors text-left flex items-center gap-3"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-white">{phase.name}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${PHASE_STATUS_COLORS[phase.status] || PHASE_STATUS_COLORS.planned}`}>
            {phase.status.replace("_", " ")}
          </span>
        </div>
        {phase.description && (
          <p className="text-sm text-gray-400 truncate">{phase.description}</p>
        )}
        {total > 0 && (
          <div className="flex items-center gap-3 mt-1.5">
            <div className="h-1.5 flex-1 max-w-48 bg-surface rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-gray-500">{done}/{total}</span>
            <div className="flex gap-2 text-xs">
              {(counts.doing || 0) > 0 && <span className="text-yellow-400">{counts.doing} doing</span>}
              {(counts.in_review || 0) > 0 && <span className="text-blue-400">{counts.in_review} review</span>}
              {(counts.failed || 0) > 0 && <span className="text-red-400">{counts.failed} failed</span>}
            </div>
          </div>
        )}
      </div>
      <ChevronRight size={16} className="text-gray-500 flex-shrink-0" />
    </button>
  );
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { project, loading, error, refetch } = useProjectDetail(projectId);
  const navigate = useNavigate();
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [starting, setStarting] = useState(false);

  const handleDelete = async () => {
    if (!projectId) return;
    setDeleting(true);
    try {
      await api(`/api/projects/${projectId}`, { method: "DELETE" });
      navigate("/projects");
    } catch {
      setDeleting(false);
      setShowDelete(false);
    }
  };

  const handleStartExecution = async () => {
    if (!projectId) return;
    setStarting(true);
    try {
      await executePhase(projectId, { auto_push: true });
      refetch(); // Refresh to show execution panel
    } catch {
      // Error
    } finally {
      setStarting(false);
    }
  };

  const handleResume = async () => {
    if (!projectId) return;
    setStarting(true);
    try {
      // Update status to active
      await api(`/api/projects/${projectId}`, {
        method: "PUT",
        body: JSON.stringify({ status: "active" }),
      });
      // Start next phase
      await executePhase(projectId, { auto_push: true });
      refetch();
    } catch {
      // Error
    } finally {
      setStarting(false);
    }
  };

  const handleStartWorkflow = async () => {
    if (!projectId) return;
    setStarting(true);
    try {
      await startWorkflow(projectId, { auto_push: true });
      refetch(); // Refresh to show execution panel
    } catch {
      // Error
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-4 animate-pulse">
        <div className="h-6 bg-surface-lighter/60 rounded w-1/3" />
        <div className="h-4 bg-surface-lighter/60 rounded w-2/3" />
        <div className="bg-surface-light border border-border rounded-xl p-4 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-surface-lighter/60 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-4 md:p-6 max-w-5xl mx-auto">
        <button onClick={() => navigate("/projects")} className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 mb-4">
          <ArrowLeft size={16} /> Back to Projects
        </button>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error || "Project not found"}
        </div>
      </div>
    );
  }

  const totalTasks = project.phases.reduce((sum, p) => {
    const counts = p.task_counts || {};
    return sum + Object.values(counts).reduce((a, b) => a + (b || 0), 0);
  }, 0);
  const doneTasks = project.phases.reduce((sum, p) => sum + (p.task_counts?.done || 0), 0);
  const overallPct = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-4">
      {/* Back nav */}
      <button
        onClick={() => navigate("/projects")}
        className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200"
      >
        <ArrowLeft size={16} /> Back to Projects
      </button>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-white">{project.name}</h2>
            <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[project.status] || STATUS_COLORS.planning}`}>
              {project.status}
            </span>
            <button
              onClick={refetch}
              className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
            >
              <RefreshCw size={16} />
            </button>
            <button
              onClick={() => setShowDelete(true)}
              className="p-1.5 rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400"
              title="Delete project"
            >
              <Trash2 size={16} />
            </button>
          </div>
          {project.description && (
            <p className="text-sm text-gray-400 mt-1">{project.description}</p>
          )}
          {project.repo_owner && project.repo_name && (
            <p className="text-xs text-gray-500 mt-1">
              {project.repo_owner}/{project.repo_name} ({project.default_branch})
              {project.auto_merge && <span className="text-yellow-400 ml-2">auto-merge on</span>}
            </p>
          )}
        </div>
      </div>

      {/* Overall progress */}
      {totalTasks > 0 && (
        <div className="bg-surface-light border border-border rounded-xl p-4">
          <div className="flex justify-between text-sm text-gray-400 mb-2">
            <span>Overall Progress</span>
            <span>{doneTasks}/{totalTasks} tasks ({overallPct}%)</span>
          </div>
          <div className="h-2 bg-surface rounded-full overflow-hidden">
            <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${overallPct}%` }} />
          </div>
        </div>
      )}

      {/* Planning Task Panel */}
      {project.planning_task_id && project.phases.length === 0 && (
        <PlanningTaskPanel
          planningTaskId={project.planning_task_id}
          projectId={project.project_id}
          onPlanApplied={refetch}
        />
      )}

      {/* Execution Controls */}
      {project.status === "active" && project.phases.length > 0 && (
        <>
          {/* Check if execution is running */}
          {project.phases.some(p => p.status === "in_progress") ? (
            <ProjectExecutionPanel
              projectId={project.project_id}
              onExecutionComplete={refetch}
              onPause={refetch}
            />
          ) : (
            /* Show Start buttons if there are incomplete phases */
            project.phases.some(p => p.status !== "completed") && (
              <div className="flex gap-3">
                <button
                  onClick={handleStartWorkflow}
                  disabled={starting}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-accent to-purple-500 text-white text-sm font-medium hover:from-accent-hover hover:to-purple-600 transition-colors disabled:opacity-50 shadow-lg shadow-accent/20"
                  title="Automatically execute all phases sequentially with PR creation"
                >
                  <Zap size={16} />
                  {starting ? "Starting..." : "Start Automated Workflow"}
                </button>
                <button
                  onClick={handleStartExecution}
                  disabled={starting}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-lighter border border-border text-gray-300 text-sm font-medium hover:bg-surface hover:text-white transition-colors disabled:opacity-50"
                  title="Manually execute one phase at a time"
                >
                  <Play size={16} />
                  {starting ? "Starting..." : "Start Manual Phase"}
                </button>
              </div>
            )
          )}
        </>
      )}

      {/* Resume button for paused projects */}
      {project.status === "paused" && (
        <button
          onClick={handleResume}
          disabled={starting}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          <Play size={16} />
          {starting ? "Resuming..." : "Resume Implementation"}
        </button>
      )}

      {/* Phases */}
      <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-sm font-medium text-gray-300">
            Phases ({project.phases.length})
          </h3>
        </div>
        {project.phases.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            No phases yet
          </div>
        ) : (
          <div className="divide-y divide-border/50">
            {project.phases.map((phase) => (
              <PhaseRow
                key={phase.phase_id}
                phase={phase}
                projectId={project.project_id}
                onClick={() => navigate(`/projects/${project.project_id}/phases/${phase.phase_id}`)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Design Document */}
      {project.design_document && (
        <details className="bg-surface-light border border-border rounded-xl overflow-hidden">
          <summary className="px-4 py-3 cursor-pointer hover:bg-surface-lighter/50 transition-colors flex items-center gap-2 text-sm font-medium text-gray-300">
            <FileText size={16} />
            Design Document
          </summary>
          <div className="px-4 py-3 border-t border-border">
            <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
              {project.design_document}
            </pre>
          </div>
        </details>
      )}

      <ConfirmDialog
        open={showDelete}
        title="Delete Project"
        message={`Delete "${project.name}" and all its phases and tasks? This cannot be undone.`}
        confirmLabel={deleting ? "Deleting…" : "Delete"}
        onConfirm={handleDelete}
        onCancel={() => setShowDelete(false)}
      />
    </div>
  );
}
