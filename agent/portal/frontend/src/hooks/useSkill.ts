import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { Skill } from "./useSkills";

export function useSkill(skillId: string | undefined) {
  const [skill, setSkill] = useState<Skill | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSkill = useCallback(async () => {
    if (!skillId) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const data = await api<Skill>(`/api/skills/${skillId}`);
      setSkill(data || null);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load skill";
      setError(msg);
      setSkill(null);
    } finally {
      setLoading(false);
    }
  }, [skillId]);

  useEffect(() => {
    fetchSkill();
  }, [fetchSkill]);

  return { skill, loading, error, refetch: fetchSkill };
}
