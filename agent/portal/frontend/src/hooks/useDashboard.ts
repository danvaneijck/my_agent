import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type {
  ProjectSummary,
  Task,
  GitPullRequest,
  Deployment,
  GitWorkflowRun,
} from "@/types";
import { mapTask } from "@/types";

interface UsageSummary {
  token_budget_monthly: number | null;
  tokens_used_this_month: number;
  budget_reset_at: string | null;
  this_month: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost: number;
    requests: number;
  };
}

export interface AnthropicUsageWindow {
  utilization_percent: number;
  reset_timestamp: number;
}

export interface AnthropicUsageData {
  available: boolean;
  five_hour: AnthropicUsageWindow | null;
  seven_day: AnthropicUsageWindow | null;
}

export interface DashboardData {
  projects: ProjectSummary[];
  tasks: Task[];
  pullRequests: GitPullRequest[];
  prCount: number;
  deployments: Deployment[];
  usage: UsageSummary | null;
  anthropicUsage: AnthropicUsageData | null;
  workflowRuns: GitWorkflowRun[];
}

export interface DashboardState extends DashboardData {
  loading: boolean;
  errors: Record<string, string>;
  refetch: () => void;
  refetchSection: (section: keyof DashboardData) => void;
}

export function useDashboard(): DashboardState {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [pullRequests, setPullRequests] = useState<GitPullRequest[]>([]);
  const [prCount, setPrCount] = useState(0);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [anthropicUsage, setAnthropicUsage] = useState<AnthropicUsageData | null>(null);
  const [workflowRuns, setWorkflowRuns] = useState<GitWorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const fetchProjects = useCallback(async () => {
    try {
      const data = await api<ProjectSummary[]>("/api/projects");
      setProjects(data || []);
      setErrors((prev) => {
        const next = { ...prev };
        delete next.projects;
        return next;
      });
    } catch (e) {
      setErrors((prev) => ({
        ...prev,
        projects: e instanceof Error ? e.message : "Failed to load projects",
      }));
    }
  }, []);

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api<{ tasks: Record<string, unknown>[] }>("/api/tasks");
      setTasks((data.tasks || []).map(mapTask));
      setErrors((prev) => {
        const next = { ...prev };
        delete next.tasks;
        return next;
      });
    } catch (e) {
      setErrors((prev) => ({
        ...prev,
        tasks: e instanceof Error ? e.message : "Failed to load tasks",
      }));
    }
  }, []);

  const fetchPullRequests = useCallback(async () => {
    try {
      const data = await api<{
        count: number;
        pull_requests: GitPullRequest[];
      }>("/api/repos/pulls/all");
      setPullRequests(data.pull_requests || []);
      setPrCount(data.count || 0);
      setErrors((prev) => {
        const next = { ...prev };
        delete next.pullRequests;
        return next;
      });
    } catch (e) {
      setErrors((prev) => ({
        ...prev,
        pullRequests:
          e instanceof Error ? e.message : "Failed to load pull requests",
      }));
    }
  }, []);

  const fetchDeployments = useCallback(async () => {
    try {
      const data = await api<{ deployments: Deployment[]; total: number }>(
        "/api/deployments"
      );
      setDeployments(data.deployments || []);
      setErrors((prev) => {
        const next = { ...prev };
        delete next.deployments;
        return next;
      });
    } catch (e) {
      setErrors((prev) => ({
        ...prev,
        deployments:
          e instanceof Error ? e.message : "Failed to load deployments",
      }));
    }
  }, []);

  const fetchUsage = useCallback(async () => {
    try {
      const data = await api<UsageSummary>("/api/usage/summary");
      setUsage(data);
      setErrors((prev) => {
        const next = { ...prev };
        delete next.usage;
        return next;
      });
    } catch (e) {
      setErrors((prev) => ({
        ...prev,
        usage: e instanceof Error ? e.message : "Failed to load usage",
      }));
    }
  }, []);

  const fetchAnthropicUsage = useCallback(async () => {
    try {
      const data = await api<AnthropicUsageData>("/api/usage/anthropic");
      setAnthropicUsage(data);
      setErrors((prev) => {
        const next = { ...prev };
        delete next.anthropicUsage;
        return next;
      });
    } catch (e) {
      setErrors((prev) => ({
        ...prev,
        anthropicUsage:
          e instanceof Error ? e.message : "Failed to load Claude Code usage",
      }));
    }
  }, []);

  const fetchWorkflowRuns = useCallback(async () => {
    try {
      const data = await api<{ total_count: number; workflow_runs: GitWorkflowRun[] }>(
        "/api/repos/actions/running"
      );
      setWorkflowRuns(data.workflow_runs || []);
      setErrors((prev) => {
        const next = { ...prev };
        delete next.workflowRuns;
        return next;
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load workflow runs";
      // Silently ignore "not configured" errors — card hides itself in that case
      if (/not configured|no provider configured|no github/i.test(msg)) {
        setWorkflowRuns([]);
        return;
      }
      setErrors((prev) => ({
        ...prev,
        workflowRuns: msg,
      }));
    }
  }, []);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    await Promise.allSettled([
      fetchProjects(),
      fetchTasks(),
      fetchPullRequests(),
      fetchDeployments(),
      fetchUsage(),
      fetchAnthropicUsage(),
      fetchWorkflowRuns(),
    ]);
    setLoading(false);
  }, [fetchProjects, fetchTasks, fetchPullRequests, fetchDeployments, fetchUsage, fetchAnthropicUsage, fetchWorkflowRuns]);

  const refetchSection = useCallback(
    (section: keyof DashboardData) => {
      const map: Record<keyof DashboardData, () => Promise<void>> = {
        projects: fetchProjects,
        tasks: fetchTasks,
        pullRequests: fetchPullRequests,
        prCount: fetchPullRequests,
        deployments: fetchDeployments,
        usage: fetchUsage,
        anthropicUsage: fetchAnthropicUsage,
        workflowRuns: fetchWorkflowRuns,
      };
      map[section]?.();
    },
    [fetchProjects, fetchTasks, fetchPullRequests, fetchDeployments, fetchUsage, fetchAnthropicUsage, fetchWorkflowRuns]
  );

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return {
    projects,
    tasks,
    pullRequests,
    prCount,
    deployments,
    usage,
    anthropicUsage,
    workflowRuns,
    loading,
    errors,
    refetch: fetchAll,
    refetchSection,
  };
}
