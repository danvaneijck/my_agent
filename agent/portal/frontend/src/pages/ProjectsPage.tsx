import { useState } from "react";
import { motion } from "framer-motion";
import { pageVariants, listContainerVariants, listItemVariants } from "@/utils/animations";
import { useNavigate } from "react-router-dom";
import { FolderKanban, RefreshCw, Plus } from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import NewProjectModal from "@/components/projects/NewProjectModal";
import type { ProjectSummary } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  planning: "bg-blue-500/20 text-blue-400",
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  archived: "bg-gray-600/20 text-gray-500",
};

function ProjectCard({ project, onClick }: { project: ProjectSummary; onClick: () => void }) {
  const total = project.total_tasks;
  const done = project.done_tasks;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <button
      onClick={onClick}
      className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 text-left hover:border-border-light transition-colors w-full"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-medium text-white truncate">{project.name}</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[project.status] || STATUS_COLORS.planning}`}>
          {project.status}
        </span>
      </div>

      {project.description && (
        <p className="text-sm text-gray-400 line-clamp-2 mb-3">{project.description}</p>
      )}

      {project.repo_owner && project.repo_name && (
        <p className="text-xs text-gray-500 mb-3">
          {project.repo_owner}/{project.repo_name}
        </p>
      )}

      {total > 0 && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-gray-400">
            <span>{done}/{total} tasks done</span>
            <span>{pct}%</span>
          </div>
          <div className="h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex gap-3 text-xs text-gray-500">
            {(project.task_counts.doing || 0) > 0 && (
              <span className="text-yellow-400">{project.task_counts.doing} in progress</span>
            )}
            {(project.task_counts.in_review || 0) > 0 && (
              <span className="text-blue-400">{project.task_counts.in_review} in review</span>
            )}
            {(project.task_counts.failed || 0) > 0 && (
              <span className="text-red-400">{project.task_counts.failed} failed</span>
            )}
          </div>
        </div>
      )}

      {total === 0 && (
        <p className="text-xs text-gray-500">No tasks yet</p>
      )}
    </button>
  );
}

export default function ProjectsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showNewProject, setShowNewProject] = useState(false);
  const { projects, loading, error, refetch } = useProjects(statusFilter || undefined);
  const navigate = useNavigate();

  return (
    <motion.div
      className="p-4 md:p-6 space-y-4"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <FolderKanban size={20} className="text-accent" />
            Projects
          </h2>
          <button
            onClick={refetch}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-lg px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-accent"
          >
            <option value="">All statuses</option>
            <option value="planning">Planning</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </select>
          <button
            onClick={() => setShowNewProject(true)}
            className="bg-accent hover:bg-accent-hover text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
          >
            <Plus size={16} />
            New Project
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Content */}
      {loading && projects.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 animate-pulse">
              <div className="h-5 bg-surface-lighter/60 rounded w-2/3 mb-3" />
              <div className="h-4 bg-surface-lighter/60 rounded w-full mb-2" />
              <div className="h-4 bg-surface-lighter/60 rounded w-1/2 mb-3" />
              <div className="h-1.5 bg-surface-lighter/60 rounded-full" />
            </div>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <FolderKanban size={40} className="mx-auto mb-3 opacity-50" />
          <p>No projects yet</p>
          <p className="text-sm mt-1 mb-4">Create your first project to get started</p>
          <button
            onClick={() => setShowNewProject(true)}
            className="bg-accent hover:bg-accent-hover text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors inline-flex items-center gap-1.5"
          >
            <Plus size={16} />
            New Project
          </button>
        </div>
      ) : (
        <motion.div
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3"
          initial="initial"
          animate="animate"
          variants={listContainerVariants}
        >
          {projects.map((project) => (
            <motion.div key={project.project_id} variants={listItemVariants} layout>
              <ProjectCard
                project={project}
                onClick={() => navigate(`/projects/${project.project_id}`)}
              />
            </motion.div>
          ))}
        </motion.div>
      )}

      <NewProjectModal
        open={showNewProject}
        onClose={() => setShowNewProject(false)}
        onCreated={(projectId) => {
          setShowNewProject(false);
          refetch();
          navigate(`/projects/${projectId}`);
        }}
      />
    </motion.div>
  );
}
