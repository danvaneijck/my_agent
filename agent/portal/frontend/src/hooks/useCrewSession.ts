import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { CrewSessionDetail } from "@/types";

export function useCrewSession(sessionId: string | undefined) {
  const [session, setSession] = useState<CrewSessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSession = useCallback(async () => {
    if (!sessionId) return;
    try {
      const data = await api<CrewSessionDetail>(`/api/crews/${sessionId}`);
      setSession(data || null);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load crew session";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  // Auto-poll while session is running
  useEffect(() => {
    if (!session || !["running", "configuring"].includes(session.status)) return;
    const interval = setInterval(fetchSession, 10000);
    return () => clearInterval(interval);
  }, [session?.status, fetchSession]);

  return { session, loading, error, refetch: fetchSession };
}
