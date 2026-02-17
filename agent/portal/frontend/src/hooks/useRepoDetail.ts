import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { GitBranch, GitIssue, GitPullRequest } from "@/types";

interface RepoDetailData {
  branches: GitBranch[];
  issues: GitIssue[];
  pullRequests: GitPullRequest[];
}

export function useRepoDetail(owner: string, repo: string, provider: string = "github") {
  const [data, setData] = useState<RepoDetailData>({
    branches: [],
    issues: [],
    pullRequests: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    if (!owner || !repo) return;
    setLoading(true);
    try {
      const [branchRes, issueRes, prRes] = await Promise.all([
        api<{ count: number; branches: GitBranch[] }>(
          `/api/repos/${owner}/${repo}/branches?per_page=100&provider=${provider}`
        ),
        api<{ count: number; issues: GitIssue[] }>(
          `/api/repos/${owner}/${repo}/issues?state=open&per_page=50&provider=${provider}`
        ).catch(() => ({ count: 0, issues: [] })),
        api<{ count: number; pull_requests: GitPullRequest[] }>(
          `/api/repos/${owner}/${repo}/pulls?state=open&per_page=50&provider=${provider}`
        ),
      ]);
      setData({
        branches: branchRes.branches || [],
        issues: issueRes.issues || [],
        pullRequests: prRes.pull_requests || [],
      });
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to fetch repo details";
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
  }, [owner, repo, provider]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { ...data, loading, error, refetch: fetchAll };
}
