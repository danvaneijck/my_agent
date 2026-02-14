import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { GitPullRequest } from "@/types";

export function usePullRequests() {
  const [pullRequests, setPullRequests] = useState<GitPullRequest[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<{ count: number; pull_requests: GitPullRequest[] }>(
        "/api/repos/pulls/all"
      );
      setPullRequests(data.pull_requests || []);
      setCount(data.count || 0);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to fetch pull requests";
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
  }, []);

  useEffect(() => {
    fetch_();
  }, [fetch_]);

  return { pullRequests, count, loading, error, refetch: fetch_ };
}
