import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { RefreshCw, Trash2 } from "lucide-react";
import { useTasks } from "@/hooks/useTasks";
import { usePageTitle } from "@/hooks/usePageTitle";
import TaskList from "@/components/tasks/TaskList";
import NewTaskForm from "@/components/tasks/NewTaskForm";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import { api } from "@/api/client";
import { pageVariants } from "@/utils/animations";

export default function TasksPage() {
  usePageTitle("Claude Code Tasks");
  const { tasks, loading, error, refetch } = useTasks();
  const [searchParams, setSearchParams] = useSearchParams();
  const [showDeleteAllConfirm, setShowDeleteAllConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Read URL params for pre-filling the new task modal
  const urlDefaults = useMemo(() => {
    const repoUrl = searchParams.get("repo_url") || undefined;
    const branch = searchParams.get("branch") || undefined;
    const prompt = searchParams.get("prompt") || undefined;
    const autoOpen = !!(repoUrl || prompt);
    return { repoUrl, branch, prompt, autoOpen };
  }, [searchParams]);

  const handleCreated = () => {
    // Clear URL params after task created
    if (searchParams.toString()) {
      setSearchParams({});
    }
    refetch();
  };

  const handleDeleteAll = async () => {
    setIsDeleting(true);
    try {
      await api("/api/tasks", { method: "DELETE" });
      await refetch();
      setShowDeleteAllConfirm(false);
    } catch (err) {
      console.error("Failed to delete all tasks:", err);
      alert(err instanceof Error ? err.message : "Failed to delete all tasks");
    } finally {
      setIsDeleting(false);
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Claude Code Tasks</h2>
          <button
            onClick={refetch}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          )}
          {tasks.length > 0 && (
            <button
              onClick={() => setShowDeleteAllConfirm(true)}
              disabled={isDeleting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-red-600/10 text-red-400 hover:bg-red-600/20 border border-red-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Delete all tasks and workspaces"
            >
              <Trash2 size={14} />
              <span className="hidden sm:inline">Delete All</span>
            </button>
          )}
        </div>
        <NewTaskForm
          onCreated={handleCreated}
          defaultRepoUrl={urlDefaults.repoUrl}
          defaultBranch={urlDefaults.branch}
          defaultPrompt={urlDefaults.prompt}
          autoOpen={urlDefaults.autoOpen}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Task list */}
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
        <TaskList tasks={tasks} />
      </div>

      {/* Delete All Confirmation Dialog */}
      <ConfirmDialog
        open={showDeleteAllConfirm}
        title="Delete All Tasks?"
        message={`This will permanently delete all ${tasks.length} task${tasks.length !== 1 ? 's' : ''} and their workspaces. This action cannot be undone.`}
        confirmLabel={isDeleting ? "Deleting..." : "Delete All"}
        onConfirm={handleDeleteAll}
        onCancel={() => setShowDeleteAllConfirm(false)}
      />
    </motion.div>
  );
}
