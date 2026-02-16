import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { usePageTitle } from "@/hooks/usePageTitle";
import {
  RefreshCw,
  Clock,
  XCircle,
  ChevronDown,
  ChevronRight,
  Workflow,
  Repeat,
  Bell,
} from "lucide-react";
import { api } from "@/api/client";
import ConfirmDialog from "@/components/common/ConfirmDialog";

interface CheckConfig {
  module?: string;
  tool?: string;
  args?: Record<string, unknown>;
  success_field?: string;
  success_values?: string[];
  [key: string]: unknown;
}

interface ScheduledJob {
  job_id: string;
  job_type: "poll_module" | "delay" | "poll_url";
  status: "active" | "completed" | "failed" | "cancelled";
  on_complete: "notify" | "resume_conversation";
  workflow_id: string | null;
  check_config: CheckConfig;
  attempts: number;
  max_attempts: number;
  interval_seconds: number;
  on_success_message: string;
  created_at: string;
  next_run_at: string | null;
  completed_at: string | null;
}

interface WorkflowGroup {
  workflow_id: string;
  jobs: ScheduledJob[];
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-gray-500/20 text-gray-400",
};

const TYPE_LABELS: Record<string, string> = {
  poll_module: "Module Poll",
  delay: "Delay",
  poll_url: "URL Poll",
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function getCheckLabel(config: CheckConfig): string {
  if (config.module && config.tool) {
    const toolName = config.tool.includes(".")
      ? config.tool.split(".").pop()
      : config.tool;
    return `${config.module}.${toolName}`;
  }
  if (config.url) return String(config.url).slice(0, 40);
  if (config.delay_seconds) return `Wait ${config.delay_seconds}s`;
  return "-";
}

function ProgressBar({
  job,
}: {
  job: ScheduledJob;
}) {
  const pct = Math.min(100, (job.attempts / job.max_attempts) * 100);
  const color =
    job.status === "completed"
      ? "bg-green-500"
      : job.status === "failed"
        ? "bg-red-500"
        : "bg-yellow-500";
  return (
 <div
 className="flex items-center gap-2"
      
      
      
      
>
 <div className="w-16 bg-surface rounded-full h-1.5">
 <div
 className={`h-1.5 rounded-full ${color}`}
 style={{ width: `${pct}%` }}
 />
 </div>
 <span className="text-xs text-gray-400">
 {job.attempts}/{job.max_attempts}
      </span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[status] || STATUS_STYLES.cancelled}`}
    >
      {status === "active" && (
        <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
      )}
      {status}
    </span>
  );
}

function CompletionBadge({ mode }: { mode: string }) {
  if (mode === "resume_conversation") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/15 text-blue-400">
        <Repeat size={10} />
        Chain
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-gray-500/15 text-gray-400">
      <Bell size={10} />
      Notify
    </span>
  );
}

// ---- Job row (used for both standalone and workflow-grouped jobs) ----

function JobRow({
  job,
  onCancel,
  compact,
}: {
  job: ScheduledJob;
  onCancel: (job: ScheduledJob) => void;
  compact?: boolean;
}) {
  return (
    <tr className="hover:bg-surface-lighter/50 transition-colors">
      <td className="px-4 py-3 font-mono text-xs text-gray-400">
        {compact ? "" : job.job_id.slice(0, 8)}
      </td>
      <td className="px-4 py-3 text-gray-300 text-xs">
        <div className="flex items-center gap-2">
          <span>{TYPE_LABELS[job.job_type] || job.job_type}</span>
          <CompletionBadge mode={job.on_complete} />
        </div>
      </td>
      <td className="px-4 py-3 text-xs text-gray-400">
        {getCheckLabel(job.check_config)}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={job.status} />
      </td>
      <td className="px-4 py-3 text-gray-400 text-xs">
        <ProgressBar job={job} />
      </td>
      <td className="px-4 py-3 text-gray-400 text-xs">
        {formatDuration(job.interval_seconds)}
      </td>
      <td className="px-4 py-3 text-gray-400 text-xs">
        {formatDate(job.created_at)}
      </td>
      <td className="px-4 py-3 text-gray-400 text-xs">
        {job.status === "active"
          ? formatDate(job.next_run_at)
          : formatDate(job.completed_at)}
      </td>
      <td className="px-4 py-3 text-right">
        {job.status === "active" && (
          <button
            onClick={() => onCancel(job)}
            className="p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors"
            title="Cancel job"
          >
            <XCircle size={16} />
          </button>
        )}
      </td>
    </tr>
  );
}

// ---- Workflow group ----

function WorkflowGroupView({
  group,
  onCancelJob,
  onCancelWorkflow,
}: {
  group: WorkflowGroup;
  onCancelJob: (job: ScheduledJob) => void;
  onCancelWorkflow: (workflowId: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasActive = group.jobs.some((j) => j.status === "active");
  const allCompleted = group.jobs.every(
    (j) => j.status === "completed" || j.status === "cancelled"
  );
  const hasFailed = group.jobs.some((j) => j.status === "failed");

  const overallStatus = hasFailed
    ? "failed"
    : allCompleted
      ? "completed"
      : hasActive
        ? "active"
        : "cancelled";

  return (
    <>
      <tr
        className="bg-surface-lighter/30 cursor-pointer hover:bg-surface-lighter/60 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-2.5" colSpan={2}>
          <div className="flex items-center gap-2">
            {expanded ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
            <Workflow size={14} className="text-blue-400" />
            <span className="text-xs font-medium text-blue-400">
              Workflow
            </span>
            <span className="font-mono text-xs text-gray-500">
              {group.workflow_id.slice(0, 8)}
            </span>
          </div>
        </td>
        <td className="px-4 py-2.5 text-xs text-gray-400">
          {group.jobs.length} step{group.jobs.length !== 1 ? "s" : ""}
        </td>
        <td className="px-4 py-2.5">
          <StatusBadge status={overallStatus} />
        </td>
        <td className="px-4 py-2.5" colSpan={3}></td>
        <td className="px-4 py-2.5" />
        <td className="px-4 py-2.5 text-right">
          {hasActive && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onCancelWorkflow(group.workflow_id);
              }}
              className="p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors"
              title="Cancel entire workflow"
            >
              <XCircle size={16} />
            </button>
          )}
        </td>
      </tr>
      {expanded &&
        group.jobs.map((job) => (
          <JobRow key={job.job_id} job={job} onCancel={onCancelJob} compact />
        ))}
    </>
  );
}

// ---- Mobile card ----

function JobCard({
  job,
  onCancel,
}: {
  job: ScheduledJob;
  onCancel: (job: ScheduledJob) => void;
}) {
  return (
    <div className="p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-gray-400">
            {job.job_id.slice(0, 8)}
          </span>
          <CompletionBadge mode={job.on_complete} />
        </div>
        <StatusBadge status={job.status} />
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-400">
        <span>{TYPE_LABELS[job.job_type] || job.job_type}</span>
        <span>{getCheckLabel(job.check_config)}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-400">
        <span>
          {job.attempts}/{job.max_attempts} checks
        </span>
        <span>every {formatDuration(job.interval_seconds)}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-surface rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full ${
              job.status === "completed"
                ? "bg-green-500"
                : job.status === "failed"
                  ? "bg-red-500"
                  : "bg-yellow-500"
            }`}
            style={{
              width: `${Math.min(100, (job.attempts / job.max_attempts) * 100)}%`,
            }}
          />
        </div>
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Created {formatDate(job.created_at)}</span>
        {job.status === "active" && (
          <button
            onClick={() => onCancel(job)}
            className="flex items-center gap-1 text-red-400 hover:text-red-300"
          >
            <XCircle size={14} />
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

// ---- Main page ----

type StatusFilter = "all" | "active" | "completed" | "failed" | "cancelled";

export default function SchedulePage() {
  usePageTitle("Scheduled Jobs");
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [cancelTarget, setCancelTarget] = useState<ScheduledJob | null>(null);
  const [cancelWorkflowId, setCancelWorkflowId] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const params = filter !== "all" ? `?status=${filter}` : "";
      const data = await api<{ jobs: ScheduledJob[] }>(
        `/api/schedule${params}`
      );
      setJobs(data.jobs || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    fetchJobs();
  }, [fetchJobs]);

  // Auto-refresh every 15s when there are active jobs
  useEffect(() => {
    const hasActive = jobs.some((j) => j.status === "active");
    if (!hasActive) return;
    const timer = setInterval(fetchJobs, 15000);
    return () => clearInterval(timer);
  }, [jobs, fetchJobs]);

  const handleCancelJob = async () => {
    if (!cancelTarget) return;
    try {
      await api(`/api/schedule/${cancelTarget.job_id}`, { method: "DELETE" });
      fetchJobs();
    } catch {
      // ignore
    }
    setCancelTarget(null);
  };

  const handleCancelWorkflow = async () => {
    if (!cancelWorkflowId) return;
    try {
      await api(`/api/schedule/workflow/${cancelWorkflowId}`, {
        method: "DELETE",
      });
      fetchJobs();
    } catch {
      // ignore
    }
    setCancelWorkflowId(null);
  };

  // Group jobs: workflows together, standalone separate
  const { workflows, standalone } = groupJobs(jobs);

  const activeCount = jobs.filter((j) => j.status === "active").length;

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Clock size={20} className="text-accent" />
            Scheduled Jobs
          </h2>
          <button
            onClick={() => {
              setLoading(true);
              fetchJobs();
            }}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          )}
          {activeCount > 0 && (
            <span className="text-xs text-yellow-400 bg-yellow-500/15 px-2 py-0.5 rounded-full">
              {activeCount} active
            </span>
          )}
        </div>

        {/* Filter */}
        <div className="flex gap-1">
          {(
            ["all", "active", "completed", "failed", "cancelled"] as StatusFilter[]
          ).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === s
                  ? "bg-accent/15 text-accent-hover"
                  : "text-gray-400 hover:text-gray-200 hover:bg-surface-lighter"
              }`}
            >
              {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Job list */}
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
        {loading && jobs.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-12 text-gray-600 text-sm">
            No scheduled jobs found
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-light-border dark:border-border text-gray-500 text-xs uppercase tracking-wider">
                    <th className="text-left px-4 py-3 font-medium">ID</th>
                    <th className="text-left px-4 py-3 font-medium">Type</th>
                    <th className="text-left px-4 py-3 font-medium">Target</th>
                    <th className="text-left px-4 py-3 font-medium">Status</th>
                    <th className="text-left px-4 py-3 font-medium">
                      Progress
                    </th>
                    <th className="text-left px-4 py-3 font-medium">
                      Interval
                    </th>
                    <th className="text-left px-4 py-3 font-medium">
                      Created
                    </th>
                    <th className="text-left px-4 py-3 font-medium">
                      Next / Done
                    </th>
                    <th className="text-right px-4 py-3 font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-light-border dark:divide-border/50">
                  {/* Workflow groups first */}
                  {workflows.map((group) => (
                    <WorkflowGroupView
                      key={group.workflow_id}
                      group={group}
                      onCancelJob={setCancelTarget}
                      onCancelWorkflow={setCancelWorkflowId}
                    />
                  ))}
                  {/* Standalone jobs */}
                  {standalone.map((job) => (
                    <JobRow
                      key={job.job_id}
                      job={job}
                      onCancel={setCancelTarget}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-light-border dark:divide-border/50">
              {/* Workflow groups */}
              {workflows.map((group) => (
                <div key={group.workflow_id}>
                  <div className="px-4 py-2 bg-surface-lighter/30 flex items-center gap-2">
                    <Workflow size={14} className="text-blue-400" />
                    <span className="text-xs font-medium text-blue-400">
                      Workflow
                    </span>
                    <span className="font-mono text-xs text-gray-500">
                      {group.workflow_id.slice(0, 8)}
                    </span>
                    <span className="text-xs text-gray-500">
                      ({group.jobs.length} steps)
                    </span>
                    {group.jobs.some((j) => j.status === "active") && (
                      <button
                        onClick={() =>
                          setCancelWorkflowId(group.workflow_id)
                        }
                        className="ml-auto flex items-center gap-1 text-xs text-red-400"
                      >
                        <XCircle size={12} />
                        Cancel All
                      </button>
                    )}
                  </div>
                  {group.jobs.map((job) => (
                    <JobCard
                      key={job.job_id}
                      job={job}
                      onCancel={setCancelTarget}
                    />
                  ))}
                </div>
              ))}
              {/* Standalone */}
              {standalone.map((job) => (
                <JobCard
                  key={job.job_id}
                  job={job}
                  onCancel={setCancelTarget}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Cancel job dialog */}
      <ConfirmDialog
        open={!!cancelTarget}
        title="Cancel Job"
        message={`Cancel job ${cancelTarget?.job_id.slice(0, 8)}? This cannot be undone.`}
        confirmLabel="Cancel Job"
        onConfirm={handleCancelJob}
        onCancel={() => setCancelTarget(null)}
      />

      {/* Cancel workflow dialog */}
      <ConfirmDialog
        open={!!cancelWorkflowId}
        title="Cancel Workflow"
        message={`Cancel all active jobs in workflow ${cancelWorkflowId?.slice(0, 8)}? This cannot be undone.`}
        confirmLabel="Cancel Workflow"
        onConfirm={handleCancelWorkflow}
        onCancel={() => setCancelWorkflowId(null)}
      />
    </div>
  );
}

// ---- Helpers ----

function groupJobs(jobs: ScheduledJob[]): {
  workflows: WorkflowGroup[];
  standalone: ScheduledJob[];
} {
  const workflowMap = new Map<string, ScheduledJob[]>();
  const standalone: ScheduledJob[] = [];

  for (const job of jobs) {
    if (job.workflow_id) {
      const existing = workflowMap.get(job.workflow_id) || [];
      existing.push(job);
      workflowMap.set(job.workflow_id, existing);
    } else {
      standalone.push(job);
    }
  }

  const workflows: WorkflowGroup[] = [];
  for (const [workflow_id, wfJobs] of workflowMap) {
    // Sort by created_at ascending (step order)
    wfJobs.sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );
    workflows.push({ workflow_id, jobs: wfJobs });
  }

  return { workflows, standalone };
}
