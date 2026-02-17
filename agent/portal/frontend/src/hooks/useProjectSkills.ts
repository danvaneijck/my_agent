import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";

export interface ProjectSkill {
  project_id: string;
  skill_id: string;
  skill_name: string;
  skill_description?: string;
  skill_category?: string;
  skill_language?: string;
  attached_at: string;
}

export interface ProjectSkillsResponse {
  project_id: string;
  skills: ProjectSkill[];
  count: number;
}

export function useProjectSkills(projectId: string | undefined) {
  const [skills, setSkills] = useState<ProjectSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    if (!projectId) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const data = await api<ProjectSkillsResponse>(
        `/api/skills/projects/${projectId}`
      );
      setSkills(data?.skills || []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load project skills";
      setError(msg);
      setSkills([]);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  return { skills, loading, error, refetch: fetchSkills };
}

export async function attachSkillToProject(
  projectId: string,
  skillId: string
): Promise<{ project_id: string; skill_id: string; attached_at: string }> {
  return api(`/api/skills/projects/${projectId}/skills/${skillId}`, {
    method: "POST",
  });
}

export async function detachSkillFromProject(
  projectId: string,
  skillId: string
): Promise<{ success: boolean; message: string }> {
  return api(`/api/skills/projects/${projectId}/skills/${skillId}`, {
    method: "DELETE",
  });
}
