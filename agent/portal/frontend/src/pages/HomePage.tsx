import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Home,
  RefreshCw,
  FolderKanban,
  ListChecks,
  GitPullRequest,
  Rocket,
  BarChart3,
  Gauge,
  ExternalLink,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";
import type { AnthropicUsageData } from "@/hooks/useDashboard";
import type {
  ProjectSummary,
  Task,
  GitPullRequest as PRType,
  Deployment,
} from "@/types";
import { Skeleton } from "@/components/common/Skeleton";
import { pageVariants, staggerContainerVariants, staggerItemVariants } from "@/utils/animations";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelative(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatCost(n: number): string {
  return `$${n.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Status badge styles
// ---------------------------------------------------------------------------

const PROJECT_STATUS_COLORS: Record<string, string> = {
  planning: "bg-blue-500/20 text-blue-400",
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  archived: "bg-gray-600/20 text-gray-500",
};

const TASK_STATUS_COLORS: Record<string, string> = {
  queued: "bg-blue-500/20 text-blue-400",
  running: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-gray-500/20 text-gray-400",
  awaiting_input: "bg-purple-500/20 text-purple-400",
  timed_out: "bg-orange-500/20 text-orange-400",
};

const PR_STATE_COLORS: Record<string, string> = {
  open: "bg-green-500/20 text-green-400",
  closed: "bg-red-500/20 text-red-400",
  merged: "bg-purple-500/20 text-purple-400",
};

const DEPLOY_STATUS_COLORS: Record<string, string> = {
  running: "bg-green-500/20 text-green-400",
  building: "bg-yellow-500/20 text-yellow-400",
  failed: "bg-red-500/20 text-red-400",
  stopped: "bg-gray-500/20 text-gray-400",
};

const PROJECT_TASK_STATUS_COLORS: Record<string, string> = {
  todo: "bg-gray-500/20 text-gray-400",
  doing: "bg-yellow-500/20 text-yellow-400",
  in_review: "bg-blue-500/20 text-blue-400",
  done: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
};

function Badge({ status, colorMap }: { status: string; colorMap: Record<string, string> }) {
  const style = colorMap[status] || "bg-gray-500/20 text-gray-400";
  const label = status.replace(/_/g, " ");
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${style}`}
    >
      {(status === "running" || status === "building" || status === "awaiting_input") && (
        <span
          className={`w-1.5 h-1.5 rounded-full animate-pulse ${
            status === "running" ? "bg-yellow-400" :
            status === "building" ? "bg-yellow-400" :
            "bg-purple-400"
          }`}
        />
      )}
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Card wrapper
// ---------------------------------------------------------------------------

function DashboardCard({
  title,
  icon: Icon,
  error,
  loading,
  children,
  headerAction,
}: {
  title: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  error?: string;
  loading?: boolean;
  children: React.ReactNode;
  headerAction?: React.ReactNode;
}) {
  return (
    <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-light-border dark:border-border">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Icon size={16} className="text-accent" />
          {title}
        </h3>
        {headerAction}
      </div>
      {error ? (
        <div className="p-4">
          <div className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle size={14} />
            {error}
          </div>
        </div>
      ) : loading ? (
        <div className="p-4 space-y-3">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ) : (
        children
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat counter row
// ---------------------------------------------------------------------------

function StatRow({ items }: { items: { label: string; value: number; color?: string }[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4">
      {items.map((item) => (
        <div key={item.label} className="text-center">
          <p className={`text-xl font-bold ${item.color || "text-white"}`}>
            {item.value}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">{item.label}</p>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Projects Overview Card
// ---------------------------------------------------------------------------

type ProjectStatusFilter = "" | "active" | "planning" | "paused" | "completed";

function ProjectsCard({
  projects,
  loading,
  error,
}: {
  projects: ProjectSummary[];
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<ProjectStatusFilter>("");

  const stats = useMemo(() => {
    const active = projects.filter((p) => p.status === "active").length;
    const planning = projects.filter((p) => p.status === "planning").length;
    const paused = projects.filter((p) => p.status === "paused").length;
    const completed = projects.filter((p) => p.status === "completed").length;
    return { total: projects.length, active, planning, paused, completed };
  }, [projects]);

  const filtered = useMemo(() => {
    const list = statusFilter
      ? projects.filter((p) => p.status === statusFilter)
      : projects;
    return list.slice(0, 5);
  }, [projects, statusFilter]);

  return (
    <DashboardCard
      title="Projects"
      icon={FolderKanban}
      loading={loading && projects.length === 0}
      error={error}
      headerAction={
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ProjectStatusFilter)}
            className="bg-white dark:bg-surface border border-light-border dark:border-border rounded-lg px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:border-accent"
            aria-label="Filter projects by status"
          >
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="planning">Planning</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
          </select>
          <button
            onClick={() => navigate("/projects")}
            className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
            aria-label="View all projects"
          >
            View all <ArrowRight size={12} />
          </button>
        </div>
      }
    >
      <StatRow
        items={[
          { label: "Total", value: stats.total },
          { label: "Active", value: stats.active, color: "text-green-400" },
          { label: "Planning", value: stats.planning, color: "text-blue-400" },
          { label: "Paused", value: stats.paused, color: "text-yellow-400" },
        ]}
      />
      {filtered.length === 0 ? (
        <div className="px-4 pb-4 text-sm text-gray-500 text-center">
          No projects{statusFilter ? ` with status "${statusFilter}"` : ""}
        </div>
      ) : (
        <div className="divide-y divide-light-border dark:divide-border/50">
          {filtered.map((project) => {
            const pct =
              project.total_tasks > 0
                ? Math.round(
                    (project.done_tasks / project.total_tasks) * 100
                  )
                : 0;
            return (
              <button
                key={project.project_id}
                onClick={() => navigate(`/projects/${project.project_id}`)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-surface-lighter/50 transition-colors text-left"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-800 dark:text-gray-200 truncate">
                      {project.name}
                    </span>
                    <Badge
                      status={project.status}
                      colorMap={PROJECT_STATUS_COLORS}
                    />
                  </div>
                  {project.total_tasks > 0 && (
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 h-1 bg-surface rounded-full overflow-hidden max-w-[120px]">
                        <div
                          className="h-full bg-accent rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">
                        {project.done_tasks}/{project.total_tasks}
                      </span>
                    </div>
                  )}
                </div>
                <ArrowRight size={14} className="text-gray-600 shrink-0" />
              </button>
            );
          })}
        </div>
      )}
    </DashboardCard>
  );
}

// ---------------------------------------------------------------------------
// Tasks Summary Card
// ---------------------------------------------------------------------------

type TaskSortOption = "recent" | "status";

function TasksCard({
  tasks,
  loading,
  error,
}: {
  tasks: Task[];
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();
  const [sortBy, setSortBy] = useState<TaskSortOption>("recent");

  const stats = useMemo(() => {
    const running = tasks.filter((t) => t.status === "running").length;
    const queued = tasks.filter((t) => t.status === "queued").length;
    const completed = tasks.filter((t) => t.status === "completed").length;
    const failed = tasks.filter((t) => t.status === "failed").length;
    return { total: tasks.length, running, queued, completed, failed };
  }, [tasks]);

  const sorted = useMemo(() => {
    const list = [...tasks];
    if (sortBy === "status") {
      const order: Record<string, number> = {
        running: 0,
        awaiting_input: 1,
        queued: 2,
        failed: 3,
        completed: 4,
        cancelled: 5,
        timed_out: 6,
      };
      list.sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));
    } else {
      list.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    }
    return list.slice(0, 5);
  }, [tasks, sortBy]);

  const nextTask = useMemo(() => {
    return tasks.find(
      (t) => t.status === "running" || t.status === "awaiting_input"
    );
  }, [tasks]);

  return (
    <DashboardCard
      title="Tasks"
      icon={ListChecks}
      loading={loading && tasks.length === 0}
      error={error}
      headerAction={
        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as TaskSortOption)}
            className="bg-white dark:bg-surface border border-light-border dark:border-border rounded-lg px-2 py-1 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:border-accent"
            aria-label="Sort tasks"
          >
            <option value="recent">Recent</option>
            <option value="status">By Status</option>
          </select>
          <button
            onClick={() => navigate("/")}
            className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
            aria-label="View all tasks"
          >
            View all <ArrowRight size={12} />
          </button>
        </div>
      }
    >
      <StatRow
        items={[
          { label: "Running", value: stats.running, color: "text-yellow-400" },
          { label: "Queued", value: stats.queued, color: "text-blue-400" },
          { label: "Completed", value: stats.completed, color: "text-green-400" },
          { label: "Failed", value: stats.failed, color: "text-red-400" },
        ]}
      />
      {nextTask && (
        <div className="mx-4 mb-3 p-3 bg-accent/5 border border-accent/20 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-accent font-medium">Active Task</span>
            <Badge status={nextTask.status} colorMap={TASK_STATUS_COLORS} />
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-1">{nextTask.prompt}</p>
          <button
            onClick={() => navigate(`/tasks/${nextTask.id}`)}
            className="text-xs text-accent hover:text-accent-hover mt-1 flex items-center gap-1"
          >
            View details <ArrowRight size={10} />
          </button>
        </div>
      )}
      {sorted.length === 0 ? (
        <div className="px-4 pb-4 text-sm text-gray-500 text-center">
          No tasks yet
        </div>
      ) : (
        <div className="divide-y divide-light-border dark:divide-border/50">
          {sorted.map((task) => (
            <button
              key={task.id}
              onClick={() => navigate(`/tasks/${task.id}`)}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-surface-lighter/50 transition-colors text-left"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-800 dark:text-gray-200 truncate">
                    {task.prompt.length > 60
                      ? task.prompt.slice(0, 60) + "..."
                      : task.prompt}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <Badge status={task.status} colorMap={TASK_STATUS_COLORS} />
                  <span className="text-xs text-gray-500">
                    {formatRelative(task.created_at)}
                  </span>
                </div>
              </div>
              <ArrowRight size={14} className="text-gray-600 shrink-0" />
            </button>
          ))}
        </div>
      )}
    </DashboardCard>
  );
}

// ---------------------------------------------------------------------------
// Pull Requests Card
// ---------------------------------------------------------------------------

function PullRequestsCard({
  pullRequests,
  count,
  loading,
  error,
}: {
  pullRequests: PRType[];
  count: number;
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();

  const stats = useMemo(() => {
    const open = pullRequests.filter((pr) => pr.state === "open").length;
    const merged = pullRequests.filter(
      (pr) => pr.state === "closed" && pr.merged_at
    ).length;
    const closed = pullRequests.filter(
      (pr) => pr.state === "closed" && !pr.merged_at
    ).length;
    const draft = pullRequests.filter((pr) => pr.draft).length;
    return { total: count, open, merged, closed, draft };
  }, [pullRequests, count]);

  const recent = useMemo(() => {
    return [...pullRequests]
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )
      .slice(0, 5);
  }, [pullRequests]);

  return (
    <DashboardCard
      title="Pull Requests"
      icon={GitPullRequest}
      loading={loading && pullRequests.length === 0}
      error={error}
      headerAction={
        <button
          onClick={() => navigate("/pulls")}
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
          aria-label="View all pull requests"
        >
          View all <ArrowRight size={12} />
        </button>
      }
    >
      <StatRow
        items={[
          { label: "Open", value: stats.open, color: "text-green-400" },
          { label: "Merged", value: stats.merged, color: "text-purple-400" },
          { label: "Closed", value: stats.closed, color: "text-red-400" },
          { label: "Draft", value: stats.draft, color: "text-gray-400" },
        ]}
      />
      {recent.length === 0 ? (
        <div className="px-4 pb-4 text-sm text-gray-500 text-center">
          No pull requests
        </div>
      ) : (
        <div className="divide-y divide-light-border dark:divide-border/50">
          {recent.map((pr) => {
            const state =
              pr.state === "closed" && pr.merged_at ? "merged" : pr.state;
            return (
              <button
                key={`${pr.owner}-${pr.repo}-${pr.number}`}
                onClick={() =>
                  navigate(`/pulls/${pr.owner}/${pr.repo}/${pr.number}`)
                }
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-surface-lighter/50 transition-colors text-left"
              >
                <GitPullRequest
                  size={16}
                  className={
                    state === "open"
                      ? "text-green-400"
                      : state === "merged"
                      ? "text-purple-400"
                      : "text-red-400"
                  }
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-800 dark:text-gray-200 truncate">
                      {pr.title}
                    </span>
                    {pr.draft && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400">
                        draft
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500">
                    <span>
                      {pr.owner}/{pr.repo}#{pr.number}
                    </span>
                    <span>{formatRelative(pr.created_at)}</span>
                    {pr.author && <span>by {pr.author}</span>}
                  </div>
                </div>
                <Badge status={state} colorMap={PR_STATE_COLORS} />
              </button>
            );
          })}
        </div>
      )}
    </DashboardCard>
  );
}

// ---------------------------------------------------------------------------
// Deployments Card
// ---------------------------------------------------------------------------

function DeploymentsCard({
  deployments,
  loading,
  error,
}: {
  deployments: Deployment[];
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();

  const stats = useMemo(() => {
    const running = deployments.filter((d) => d.status === "running").length;
    const building = deployments.filter((d) => d.status === "building").length;
    const failed = deployments.filter((d) => d.status === "failed").length;
    const stopped = deployments.filter((d) => d.status === "stopped").length;
    return { total: deployments.length, running, building, failed, stopped };
  }, [deployments]);

  return (
    <DashboardCard
      title="Deployments"
      icon={Rocket}
      loading={loading && deployments.length === 0}
      error={error}
      headerAction={
        <button
          onClick={() => navigate("/deployments")}
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
          aria-label="View all deployments"
        >
          View all <ArrowRight size={12} />
        </button>
      }
    >
      <StatRow
        items={[
          { label: "Running", value: stats.running, color: "text-green-400" },
          {
            label: "Building",
            value: stats.building,
            color: "text-yellow-400",
          },
          { label: "Failed", value: stats.failed, color: "text-red-400" },
          { label: "Stopped", value: stats.stopped, color: "text-gray-400" },
        ]}
      />
      {deployments.length === 0 ? (
        <div className="px-4 pb-4 text-sm text-gray-500 text-center">
          No deployments
        </div>
      ) : (
        <div className="divide-y divide-light-border dark:divide-border/50">
          {deployments.slice(0, 5).map((d) => (
            <div
              key={d.deploy_id}
              className="flex items-center gap-3 px-4 py-3"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-800 dark:text-gray-200 truncate">
                    {d.project_name}
                  </span>
                  <Badge
                    status={d.status}
                    colorMap={DEPLOY_STATUS_COLORS}
                  />
                </div>
                <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500">
                  <span className="font-mono">
                    {d.deploy_id.slice(0, 8)}
                  </span>
                  <span>{formatDate(d.created_at)}</span>
                </div>
              </div>
              {d.url && d.status === "running" && (
                <a
                  href={d.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:text-accent-hover p-1"
                  title="Open deployment"
                  aria-label={`Open deployment ${d.project_name}`}
                >
                  <ExternalLink size={14} />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </DashboardCard>
  );
}

// ---------------------------------------------------------------------------
// Usage Metrics Card
// ---------------------------------------------------------------------------

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

function UsageCard({
  usage,
  loading,
  error,
}: {
  usage: UsageSummary | null;
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();

  if (!usage && !loading && !error) return null;

  const hasBudget = usage?.token_budget_monthly != null;
  const usagePct =
    hasBudget && usage
      ? Math.min(
          100,
          (usage.tokens_used_this_month / usage.token_budget_monthly!) * 100
        )
      : 0;

  function budgetColor(pct: number): string {
    if (pct > 90) return "bg-red-500";
    if (pct > 70) return "bg-yellow-500";
    return "bg-green-500";
  }

  return (
    <DashboardCard
      title="Usage"
      icon={BarChart3}
      loading={loading && !usage}
      error={error}
      headerAction={
        <button
          onClick={() => navigate("/usage")}
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
          aria-label="View full usage details"
        >
          Details <ArrowRight size={12} />
        </button>
      }
    >
      {usage && (
        <div className="p-4 space-y-4">
          {/* Budget bar */}
          <div>
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="text-lg font-bold text-white">
                {formatNumber(usage.tokens_used_this_month)}
              </span>
              <span className="text-xs text-gray-400">
                {hasBudget
                  ? `/ ${formatNumber(usage.token_budget_monthly!)} tokens`
                  : "Unlimited"}
              </span>
            </div>
            {hasBudget && (
              <div className="w-full bg-surface rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${budgetColor(usagePct)}`}
                  style={{ width: `${usagePct}%` }}
                />
              </div>
            )}
          </div>

          {/* Monthly stats */}
          <div className="grid grid-cols-2 gap-3 pt-3 border-t border-light-border dark:border-border">
            <div>
              <p className="text-xs text-gray-400">Monthly Cost</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white mt-0.5">
                {formatCost(usage.this_month.cost)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Requests</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white mt-0.5">
                {usage.this_month.requests.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Input Tokens</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white mt-0.5">
                {formatNumber(usage.this_month.input_tokens)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Output Tokens</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white mt-0.5">
                {formatNumber(usage.this_month.output_tokens)}
              </p>
            </div>
          </div>
        </div>
      )}
    </DashboardCard>
  );
}

// ---------------------------------------------------------------------------
// Claude Code Usage Card
// ---------------------------------------------------------------------------

function utilizationColor(pct: number): string {
  if (pct > 90) return "bg-red-500";
  if (pct > 70) return "bg-yellow-500";
  return "bg-green-500";
}

function utilizationTextColor(pct: number): string {
  if (pct > 90) return "text-red-400";
  if (pct > 70) return "text-yellow-400";
  return "text-green-400";
}

function formatResetTime(resetTimestamp: number): string {
  const now = Date.now();
  const diffMs = resetTimestamp - now;
  if (diffMs <= 0) return "Reset time passed";
  const diffMins = Math.round(diffMs / 60_000);
  const hours = Math.floor(diffMins / 60);
  const mins = diffMins % 60;
  if (hours > 0) return `Resets in ${hours}h ${mins}m`;
  return `Resets in ${mins}m`;
}

function ClaudeCodeUsageCard({
  data,
  loading,
  error,
}: {
  data: AnthropicUsageData | null;
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();

  if (!data && !loading && !error) return null;

  return (
    <DashboardCard
      title="Claude Code Usage"
      icon={Gauge}
      loading={loading && !data}
      error={error}
      headerAction={
        <button
          onClick={() => navigate("/usage")}
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
          aria-label="View full usage details"
        >
          Details <ArrowRight size={12} />
        </button>
      }
    >
      {data && !data.available && (
        <div className="p-4 text-sm text-gray-500">
          Configure Claude Code credentials in{" "}
          <a href="/settings" className="text-accent hover:underline">
            Settings
          </a>{" "}
          to view usage limits.
        </div>
      )}
      {data && data.available && (
        <div className="p-4 space-y-4">
          {data.five_hour && (
            <div>
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="text-sm text-gray-700 dark:text-gray-300">5 Hour</span>
                <span className={`text-lg font-bold ${utilizationTextColor(data.five_hour.utilization_percent)}`}>
                  {Math.round(data.five_hour.utilization_percent)}%
                </span>
              </div>
              <div className="w-full bg-surface rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full transition-all ${utilizationColor(data.five_hour.utilization_percent)}`}
                  style={{ width: `${Math.min(100, data.five_hour.utilization_percent)}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {formatResetTime(data.five_hour.reset_timestamp)}
              </p>
            </div>
          )}
          {data.seven_day && (
            <div>
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="text-sm text-gray-700 dark:text-gray-300">7 Day</span>
                <span className={`text-lg font-bold ${utilizationTextColor(data.seven_day.utilization_percent)}`}>
                  {Math.round(data.seven_day.utilization_percent)}%
                </span>
              </div>
              <div className="w-full bg-surface rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full transition-all ${utilizationColor(data.seven_day.utilization_percent)}`}
                  style={{ width: `${Math.min(100, data.seven_day.utilization_percent)}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {formatResetTime(data.seven_day.reset_timestamp)}
              </p>
            </div>
          )}
          {!data.five_hour && !data.seven_day && (
            <p className="text-sm text-gray-500">
              No usage data available. The token may need the{" "}
              <code className="text-gray-400">user:profile</code> scope.
            </p>
          )}
        </div>
      )}
    </DashboardCard>
  );
}

// ---------------------------------------------------------------------------
// Project Tasks Summary Card (aggregated across all projects)
// ---------------------------------------------------------------------------

function ProjectTasksCard({
  projects,
  loading,
  error,
}: {
  projects: ProjectSummary[];
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();

  const stats = useMemo(() => {
    let todo = 0,
      doing = 0,
      inReview = 0,
      done = 0,
      failed = 0;
    for (const p of projects) {
      todo += p.task_counts?.todo || 0;
      doing += p.task_counts?.doing || 0;
      inReview += p.task_counts?.in_review || 0;
      done += p.task_counts?.done || 0;
      failed += p.task_counts?.failed || 0;
    }
    return { todo, doing, inReview, done, failed, total: todo + doing + inReview + done + failed };
  }, [projects]);

  const activeProjects = useMemo(() => {
    return projects
      .filter(
        (p) =>
          (p.task_counts?.doing || 0) > 0 ||
          (p.task_counts?.in_review || 0) > 0
      )
      .slice(0, 3);
  }, [projects]);

  return (
    <DashboardCard
      title="Project Tasks"
      icon={ListChecks}
      loading={loading && projects.length === 0}
      error={error}
      headerAction={
        <button
          onClick={() => navigate("/projects")}
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
          aria-label="View all project tasks"
        >
          View all <ArrowRight size={12} />
        </button>
      }
    >
      <StatRow
        items={[
          { label: "To Do", value: stats.todo, color: "text-gray-400" },
          { label: "In Progress", value: stats.doing, color: "text-yellow-400" },
          { label: "In Review", value: stats.inReview, color: "text-blue-400" },
          { label: "Done", value: stats.done, color: "text-green-400" },
        ]}
      />
      {stats.total > 0 && (
        <div className="px-4 pb-3">
          <div className="flex h-2 rounded-full overflow-hidden bg-surface">
            {stats.done > 0 && (
              <div
                className="bg-green-500"
                style={{ width: `${(stats.done / stats.total) * 100}%` }}
              />
            )}
            {stats.inReview > 0 && (
              <div
                className="bg-blue-500"
                style={{ width: `${(stats.inReview / stats.total) * 100}%` }}
              />
            )}
            {stats.doing > 0 && (
              <div
                className="bg-yellow-500"
                style={{ width: `${(stats.doing / stats.total) * 100}%` }}
              />
            )}
            {stats.failed > 0 && (
              <div
                className="bg-red-500"
                style={{ width: `${(stats.failed / stats.total) * 100}%` }}
              />
            )}
          </div>
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500" /> Done
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500" /> Review
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-yellow-500" /> Doing
            </span>
            {stats.failed > 0 && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500" /> Failed
              </span>
            )}
          </div>
        </div>
      )}
      {activeProjects.length > 0 && (
        <>
          <div className="px-4 py-2 border-t border-light-border dark:border-border">
            <p className="text-xs text-gray-400 font-medium">
              Projects with active tasks
            </p>
          </div>
          <div className="divide-y divide-light-border dark:divide-border/50">
            {activeProjects.map((p) => (
              <button
                key={p.project_id}
                onClick={() => navigate(`/projects/${p.project_id}`)}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 dark:hover:bg-surface-lighter/50 transition-colors text-left"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-gray-800 dark:text-gray-200 truncate block">
                    {p.name}
                  </span>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500">
                    {(p.task_counts?.doing || 0) > 0 && (
                      <span className="text-yellow-400">
                        {p.task_counts.doing} in progress
                      </span>
                    )}
                    {(p.task_counts?.in_review || 0) > 0 && (
                      <span className="text-blue-400">
                        {p.task_counts.in_review} in review
                      </span>
                    )}
                  </div>
                </div>
                <ArrowRight size={14} className="text-gray-600 shrink-0" />
              </button>
            ))}
          </div>
        </>
      )}
    </DashboardCard>
  );
}

// ---------------------------------------------------------------------------
// Dashboard Skeleton
// ---------------------------------------------------------------------------

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {Array.from({ length: 7 }).map((_, i) => (
        <div
          key={i}
          className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden"
        >
          <div className="flex items-center gap-2 px-4 py-3 border-b border-light-border dark:border-border">
            <Skeleton className="h-4 w-4" />
            <Skeleton className="h-4 w-24" />
          </div>
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-4 gap-3">
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} className="text-center space-y-1">
                  <Skeleton className="h-6 w-8 mx-auto" />
                  <Skeleton className="h-3 w-12 mx-auto" />
                </div>
              ))}
            </div>
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Home Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const dashboard = useDashboard();
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Auto-refresh every 30s when enabled
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => dashboard.refetch(), 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, dashboard.refetch]);

  return (
    <motion.div
      className="p-4 md:p-6 space-y-4 max-w-7xl mx-auto"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Home size={20} className="text-accent" />
          Dashboard
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh((prev) => !prev)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              autoRefresh
                ? "bg-accent/15 text-accent-hover"
                : "text-gray-400 hover:text-gray-800 dark:text-gray-200 hover:bg-surface-lighter"
            }`}
            title={autoRefresh ? "Disable auto-refresh" : "Enable auto-refresh (30s)"}
            aria-label="Toggle auto-refresh"
          >
            Auto-refresh {autoRefresh ? "on" : "off"}
          </button>
          <button
            onClick={dashboard.refetch}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-800 dark:text-gray-200 transition-colors"
            title="Refresh dashboard"
            aria-label="Refresh dashboard"
          >
            <RefreshCw
              size={16}
              className={dashboard.loading ? "animate-spin" : ""}
            />
          </button>
          {dashboard.loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          )}
        </div>
      </div>

      {/* Dashboard grid */}
      {dashboard.loading &&
      dashboard.projects.length === 0 &&
      dashboard.tasks.length === 0 ? (
        <DashboardSkeleton />
      ) : (
        <motion.div
          className="grid grid-cols-1 lg:grid-cols-2 gap-4"
          initial="initial"
          animate="animate"
          variants={staggerContainerVariants}
        >
          <motion.div variants={staggerItemVariants}>
            <ProjectsCard
              projects={dashboard.projects}
              loading={dashboard.loading}
              error={dashboard.errors.projects}
            />
          </motion.div>
          <motion.div variants={staggerItemVariants}>
            <TasksCard
              tasks={dashboard.tasks}
              loading={dashboard.loading}
              error={dashboard.errors.tasks}
            />
          </motion.div>
          <motion.div variants={staggerItemVariants}>
            <ProjectTasksCard
              projects={dashboard.projects}
              loading={dashboard.loading}
              error={dashboard.errors.projects}
            />
          </motion.div>
          <motion.div variants={staggerItemVariants}>
            <PullRequestsCard
              pullRequests={dashboard.pullRequests}
              count={dashboard.prCount}
              loading={dashboard.loading}
              error={dashboard.errors.pullRequests}
            />
          </motion.div>
          <motion.div variants={staggerItemVariants}>
            <DeploymentsCard
              deployments={dashboard.deployments}
              loading={dashboard.loading}
              error={dashboard.errors.deployments}
            />
          </motion.div>
          <motion.div variants={staggerItemVariants}>
            <UsageCard
              usage={dashboard.usage}
              loading={dashboard.loading}
              error={dashboard.errors.usage}
            />
          </motion.div>
          <motion.div variants={staggerItemVariants}>
            <ClaudeCodeUsageCard
              data={dashboard.anthropicUsage}
              loading={dashboard.loading}
              error={dashboard.errors.anthropicUsage}
            />
          </motion.div>
        </motion.div>
      )}
    </motion.div>
  );
}
