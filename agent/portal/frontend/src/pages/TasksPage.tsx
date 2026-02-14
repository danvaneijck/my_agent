import { RefreshCw } from "lucide-react";
import { useTasks } from "@/hooks/useTasks";
import TaskList from "@/components/tasks/TaskList";
import NewTaskForm from "@/components/tasks/NewTaskForm";

export default function TasksPage() {
  const { tasks, loading, error, refetch } = useTasks();

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
        <NewTaskForm onCreated={refetch} />
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Task list */}
      <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
        <TaskList tasks={tasks} />
      </div>
    </div>
  );
}
