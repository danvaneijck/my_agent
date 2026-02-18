import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";

export interface Skill {
  skill_id: string;
  name: string;
  description?: string;
  category?: string;
  content: string;
  language?: string;
  tags: string[];
  is_template: boolean;
  created_at: string;
  updated_at: string;
}

export interface SkillSummary {
  skill_id: string;
  name: string;
  description?: string;
  category?: string;
  language?: string;
  tags: string[];
  is_template: boolean;
  created_at: string;
  updated_at: string;
}

export interface SkillsListResponse {
  skills: SkillSummary[];
  count: number;
}

export interface CreateSkillPayload {
  name: string;
  content: string;
  description?: string;
  category?: string;
  language?: string;
  tags?: string[];
  is_template?: boolean;
}

export interface UpdateSkillPayload {
  name?: string;
  content?: string;
  description?: string;
  category?: string;
  language?: string;
  tags?: string[];
  is_template?: boolean;
}

export function useSkills(
  categoryFilter?: string,
  tagFilter?: string,
  searchQuery?: string
) {
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (categoryFilter) params.append("category_filter", categoryFilter);
      if (tagFilter) params.append("tag_filter", tagFilter);
      if (searchQuery) params.append("search_query", searchQuery);

      const queryString = params.toString();
      const url = `/api/skills${queryString ? `?${queryString}` : ""}`;

      const data = await api<SkillsListResponse>(url);
      setSkills(data?.skills || []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load skills";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, tagFilter, searchQuery]);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  return { skills, loading, error, refetch: fetchSkills };
}

export async function createSkill(payload: CreateSkillPayload): Promise<Skill> {
  return api<Skill>("/api/skills", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateSkill(
  skillId: string,
  payload: UpdateSkillPayload
): Promise<Skill> {
  return api<Skill>(`/api/skills/${skillId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteSkill(skillId: string): Promise<{ success: boolean; message: string }> {
  return api(`/api/skills/${skillId}`, {
    method: "DELETE",
  });
}

export async function renderSkill(
  skillId: string,
  variables?: Record<string, unknown>
): Promise<{ rendered: string }> {
  return api(`/api/skills/${skillId}/render`, {
    method: "POST",
    body: JSON.stringify({ variables: variables || {} }),
  });
}
