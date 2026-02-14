import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { GitRepo } from "@/types";

export function useRepos(search: string = "") {
  const [repos, setRepos] = useState<GitRepo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRepos = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ per_page: "100", sort: "updated" });
      if (search.trim()) params.set("search", search.trim());
      const data = await api<{ count: number; repos: GitRepo[] }>(
        `/api/repos?${params}`
      );
      setRepos(data.repos || []);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to fetch repos";
      // Try to extract JSON error body from "STATUS: {json}" format
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
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetchRepos();
  }, [fetchRepos]);

  return { repos, loading, error, refetch: fetchRepos };
}
