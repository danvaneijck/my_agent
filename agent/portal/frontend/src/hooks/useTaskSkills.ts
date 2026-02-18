import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";

export interface TaskSkill {
  task_id: string;
  skill_id: string;
  skill_name: string;
  skill_description?: string;
  skill_category?: string;
  skill_language?: string;
  attached_at: string;
}

export interface TaskSkillsResponse {
  task_id: string;
  skills: TaskSkill[];
  count: number;
}

export function useTaskSkills(taskId: string | undefined) {
  const [skills, setSkills] = useState<TaskSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    if (!taskId) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const data = await api<TaskSkillsResponse>(
        `/api/skills/tasks/${taskId}`
      );
      setSkills(data?.skills || []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load task skills";
      setError(msg);
      setSkills([]);
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  return { skills, loading, error, refetch: fetchSkills };
}

export async function attachSkillToTask(
  taskId: string,
  skillId: string
): Promise<{ task_id: string; skill_id: string; attached_at: string }> {
  return api(`/api/skills/tasks/${taskId}/skills/${skillId}`, {
    method: "POST",
  });
}

export async function detachSkillFromTask(
  taskId: string,
  skillId: string
): Promise<{ success: boolean; message: string }> {
  return api(`/api/skills/tasks/${taskId}/skills/${skillId}`, {
    method: "DELETE",
  });
}
