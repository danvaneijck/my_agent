import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { CrewSessionSummary } from "@/types";

export function useCrews(statusFilter?: string) {
  const [crews, setCrews] = useState<CrewSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCrews = useCallback(async () => {
    try {
      const params = statusFilter ? `?status=${statusFilter}` : "";
      const data = await api<CrewSessionSummary[]>(`/api/crews${params}`);
      setCrews(data || []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load crews";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchCrews();
  }, [fetchCrews]);

  return { crews, loading, error, refetch: fetchCrews };
}

export async function createCrewSession(payload: {
  name: string;
  project_id?: string;
  max_agents?: number;
  repo_url?: string;
  source_branch?: string;
}): Promise<{ session_id: string }> {
  return api<{ session_id: string }>("/api/crews", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function startCrewSession(sessionId: string): Promise<void> {
  await api(`/api/crews/${sessionId}/start`, { method: "POST" });
}

export async function pauseCrewSession(sessionId: string): Promise<void> {
  await api(`/api/crews/${sessionId}/pause`, { method: "POST" });
}

export async function resumeCrewSession(sessionId: string): Promise<void> {
  await api(`/api/crews/${sessionId}/resume`, { method: "POST" });
}

export async function cancelCrewSession(sessionId: string): Promise<void> {
  await api(`/api/crews/${sessionId}/cancel`, { method: "POST" });
}

export async function postCrewContext(
  sessionId: string,
  payload: { entry_type: string; title: string; content: string },
): Promise<void> {
  await api(`/api/crews/${sessionId}/context`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
