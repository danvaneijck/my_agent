import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { useTasks } from "@/hooks/useTasks";
import TaskList from "@/components/tasks/TaskList";
import NewTaskForm from "@/components/tasks/NewTaskForm";

export default function TasksPage() {
  const { tasks, loading, error, refetch } = useTasks();
  const [searchParams, setSearchParams] = useSearchParams();

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

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Claude Code Tasks</h2>
          <button
            onClick={refetch}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
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
    </div>
  );
}
