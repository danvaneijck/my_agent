import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { GitBranch } from "@/types";

export function useBranches(owner: string, repo: string, enabled: boolean = true) {
  const [branches, setBranches] = useState<GitBranch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBranches = useCallback(async () => {
    if (!owner || !repo || !enabled) {
      setBranches([]);
      return;
    }
    setLoading(true);
    try {
      const result = await api<{ count: number; branches: GitBranch[] }>(
        `/api/repos/${owner}/${repo}/branches?per_page=100`
      );
      setBranches(result.branches || []);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to fetch branches";
      const jsonMatch = msg.match(/\d+:\s*(\{.*\})/);
      if (jsonMatch) {
        try {
          const parsed = JSON.parse(jsonMatch[1]);
          setError(parsed.error || msg);
        } catch {
          setError(msg);
        }
      } else {
        setError(msg);
      }
      setBranches([]);
    } finally {
      setLoading(false);
    }
  }, [owner, repo, enabled]);

  useEffect(() => {
    fetchBranches();
  }, [fetchBranches]);

  return { branches, loading, error, refetch: fetchBranches };
}
