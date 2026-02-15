import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { ProjectSummary, ProjectDetail, ProjectTask, CreateProjectPayload, KickoffResult } from "@/types";

export function useProjects(statusFilter?: string) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      const params = statusFilter ? `?status=${statusFilter}` : "";
      const data = await api<ProjectSummary[]>(`/api/projects${params}`);
      setProjects(data || []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load projects";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return { projects, loading, error, refetch: fetchProjects };
}

export function useProjectDetail(projectId: string | undefined) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProject = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await api<ProjectDetail>(`/api/projects/${projectId}`);
      setProject(data || null);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load project";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProject();
  }, [fetchProject]);

  return { project, loading, error, refetch: fetchProject };
}

export function usePhaseTasks(projectId: string | undefined, phaseId: string | undefined) {
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    if (!projectId || !phaseId) return;
    try {
      const data = await api<ProjectTask[]>(
        `/api/projects/${projectId}/phases/${phaseId}/tasks`
      );
      setTasks(data || []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load tasks";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [projectId, phaseId]);

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 15000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  return { tasks, loading, error, refetch: fetchTasks };
}

export async function createProject(payload: CreateProjectPayload): Promise<{ project_id: string }> {
  return api<{ project_id: string }>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function kickoffProject(
  projectId: string,
  options: { mode: string; auto_push: boolean; description?: string },
): Promise<KickoffResult> {
  return api<KickoffResult>(`/api/projects/${projectId}/kickoff`, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export async function executePhase(
  projectId: string,
  options?: { phase_id?: string; auto_push?: boolean; timeout?: number },
): Promise<{ phase_id: string; claude_task_id: string; task_count: number }> {
  return api(`/api/projects/${projectId}/execute-phase`, {
    method: "POST",
    body: JSON.stringify(options || {}),
  });
}
