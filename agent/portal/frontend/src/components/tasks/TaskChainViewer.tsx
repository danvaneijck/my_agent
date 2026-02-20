import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import StatusBadge from "@/components/common/StatusBadge";
import type { Task } from "@/types";
import { mapTask } from "@/types";

interface TaskChainViewerProps {
  taskId: string;
  currentTaskId: string;
}

export default function TaskChainViewer({ taskId, currentTaskId }: TaskChainViewerProps) {
  const [chain, setChain] = useState<Task[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api<{ tasks: Record<string, unknown>[] }>(`/api/tasks/${taskId}/chain`)
      .then((data) => setChain((data.tasks || []).map(mapTask)))
      .catch(() => {});
  }, [taskId]);

  if (chain.length <= 1) return null;

  return (
    <div className="bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg p-3">
      <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
        Task Chain
      </h4>
      <div className="space-y-1">
        {chain.map((t) => (
          <button
            key={t.id}
            onClick={() => navigate(`/tasks/${t.id}`)}
            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-left transition-colors ${
              t.id === currentTaskId
                ? "bg-accent/10 text-accent"
                : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-surface-lighter"
            }`}
          >
            <StatusBadge status={t.status} />
            <span className="font-mono">{t.id.slice(0, 8)}</span>
            <span className="text-gray-500 truncate flex-1">
              {t.mode === "plan" ? "[plan]" : "[exec]"} {(t.prompt || "").slice(0, 60)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
