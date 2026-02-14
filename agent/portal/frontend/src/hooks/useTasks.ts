import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { Task } from "@/types";
import { mapTask } from "@/types";

export function useTasks(pollInterval = 10000) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api<{ tasks: Record<string, unknown>[] }>("/api/tasks");
      setTasks((data.tasks || []).map(mapTask));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
    const id = setInterval(fetchTasks, pollInterval);
    return () => clearInterval(id);
  }, [fetchTasks, pollInterval]);

  return { tasks, loading, error, refetch: fetchTasks };
}
