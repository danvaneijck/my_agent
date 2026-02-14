import { useState, useEffect, useCallback } from "react";
import {
  RefreshCw,
  Rocket,
  Trash2,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  FileText,
} from "lucide-react";
import { api } from "@/api/client";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import type { Deployment } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  running: "bg-green-500/20 text-green-400",
  building: "bg-yellow-500/20 text-yellow-400",
  failed: "bg-red-500/20 text-red-400",
  stopped: "bg-gray-500/20 text-gray-400",
};

const TYPE_LABELS: Record<string, string> = {
  react: "React",
  nextjs: "Next.js",
  static: "Static",
  node: "Node.js",
  docker: "Docker",
};

type StatusFilter = "all" | "running" | "building" | "failed" | "stopped";

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[status] || STATUS_STYLES.stopped}`}
    >
      {(status === "running" || status === "building") && (
        <span
          className={`w-1.5 h-1.5 rounded-full animate-pulse ${
            status === "running" ? "bg-green-400" : "bg-yellow-400"
          }`}
        />
      )}
      {status}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-medium bg-accent/10 text-accent">
      {TYPE_LABELS[type] || type}
    </span>
  );
}

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

// ---- Log viewer ----

function LogViewer({ deployId }: { deployId: string }) {
  const [logs, setLogs] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<{ logs: string }>(
        `/api/deployments/${deployId}/logs?lines=100`
      );
      setLogs(data.logs || "No logs available");
    } catch {
      setLogs("Failed to fetch logs");
    } finally {
      setLoading(false);
    }
  }, [deployId]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return (
    <div className="bg-surface rounded-lg p-3 mt-2">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400">Container Logs</span>
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="p-1 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
        </button>
      </div>
      <pre className="text-xs text-gray-300 whitespace-pre-wrap max-h-64 overflow-y-auto font-mono">
        {loading && !logs ? "Loading..." : logs}
      </pre>
    </div>
  );
}

// ---- Desktop row ----

function DeploymentRow({
  deployment,
  expanded,
  onToggleLogs,
  onTeardown,
}: {
  deployment: Deployment;
  expanded: boolean;
  onToggleLogs: (id: string) => void;
  onTeardown: (d: Deployment) => void;
}) {
  return (
    <>
      <tr className="hover:bg-surface-lighter/50 transition-colors">
        <td className="px-4 py-3 font-mono text-xs text-gray-400">
          {deployment.deploy_id.slice(0, 8)}
        </td>
        <td className="px-4 py-3 text-sm text-gray-200">
          {deployment.project_name}
        </td>
        <td className="px-4 py-3">
          <TypeBadge type={deployment.project_type} />
        </td>
        <td className="px-4 py-3">
          <StatusBadge status={deployment.status} />
        </td>
        <td className="px-4 py-3 text-xs">
          {deployment.url ? (
            <a
              href={deployment.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-accent hover:text-accent-hover transition-colors"
            >
              :{deployment.port}
              <ExternalLink size={12} />
            </a>
          ) : (
            <span className="text-gray-500">-</span>
          )}
        </td>
        <td className="px-4 py-3 text-gray-400 text-xs">
          {formatDate(deployment.created_at)}
        </td>
        <td className="px-4 py-3 text-right">
          <div className="flex items-center justify-end gap-1">
            <button
              onClick={() => onToggleLogs(deployment.deploy_id)}
              className="p-1 rounded hover:bg-surface-lighter text-gray-500 hover:text-gray-300 transition-colors"
              title="View logs"
            >
              {expanded ? (
                <ChevronDown size={16} />
              ) : (
                <FileText size={16} />
              )}
            </button>
            <button
              onClick={() => onTeardown(deployment)}
              className="p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors"
              title="Teardown"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="px-4 pb-3">
            <LogViewer deployId={deployment.deploy_id} />
          </td>
        </tr>
      )}
    </>
  );
}

// ---- Mobile card ----

function DeploymentCard({
  deployment,
  expanded,
  onToggleLogs,
  onTeardown,
}: {
  deployment: Deployment;
  expanded: boolean;
  onToggleLogs: (id: string) => void;
  onTeardown: (d: Deployment) => void;
}) {
  return (
    <div className="p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">
            {deployment.project_name}
          </span>
          <TypeBadge type={deployment.project_type} />
        </div>
        <StatusBadge status={deployment.status} />
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-400">
        <span className="font-mono">{deployment.deploy_id.slice(0, 8)}</span>
        {deployment.url && (
          <a
            href={deployment.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-accent hover:text-accent-hover"
          >
            :{deployment.port}
            <ExternalLink size={12} />
          </a>
        )}
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Created {formatDate(deployment.created_at)}</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggleLogs(deployment.deploy_id)}
            className="flex items-center gap-1 text-gray-400 hover:text-gray-200"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Logs
          </button>
          <button
            onClick={() => onTeardown(deployment)}
            className="flex items-center gap-1 text-red-400 hover:text-red-300"
          >
            <Trash2 size={14} />
            Teardown
          </button>
        </div>
      </div>
      {expanded && <LogViewer deployId={deployment.deploy_id} />}
    </div>
  );
}

// ---- Main page ----

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [teardownTarget, setTeardownTarget] = useState<Deployment | null>(null);
  const [teardownAllOpen, setTeardownAllOpen] = useState(false);
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set());

  const fetchDeployments = useCallback(async () => {
    try {
      const data = await api<{ deployments: Deployment[]; total: number }>(
        "/api/deployments"
      );
      setDeployments(data.deployments || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchDeployments();
  }, [fetchDeployments]);

  // Auto-refresh every 10s
  useEffect(() => {
    const timer = setInterval(fetchDeployments, 10000);
    return () => clearInterval(timer);
  }, [fetchDeployments]);

  const filtered =
    filter === "all"
      ? deployments
      : deployments.filter((d) => d.status === filter);

  const handleTeardown = async () => {
    if (!teardownTarget) return;
    try {
      await api(`/api/deployments/${teardownTarget.deploy_id}`, {
        method: "DELETE",
      });
      fetchDeployments();
    } catch {
      // ignore
    }
    setTeardownTarget(null);
  };

  const handleTeardownAll = async () => {
    try {
      await api("/api/deployments", { method: "DELETE" });
      fetchDeployments();
    } catch {
      // ignore
    }
    setTeardownAllOpen(false);
  };

  const toggleLogs = (deployId: string) => {
    setExpandedLogs((prev) => {
      const next = new Set(prev);
      if (next.has(deployId)) next.delete(deployId);
      else next.add(deployId);
      return next;
    });
  };

  const runningCount = deployments.filter((d) => d.status === "running").length;

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Rocket size={20} className="text-accent" />
            Deployments
          </h2>
          <button
            onClick={() => {
              setLoading(true);
              fetchDeployments();
            }}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          )}
          {runningCount > 0 && (
            <span className="text-xs text-green-400 bg-green-500/15 px-2 py-0.5 rounded-full">
              {runningCount} running
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Filter */}
          <div className="flex gap-1">
            {(
              ["all", "running", "building", "failed", "stopped"] as StatusFilter[]
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
          {/* Teardown All */}
          {deployments.length > 0 && (
            <button
              onClick={() => setTeardownAllOpen(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:bg-red-500/15 transition-colors"
            >
              Teardown All
            </button>
          )}
        </div>
      </div>

      {/* Deployment list */}
      <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
        {loading && deployments.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-gray-600 text-sm">
            {deployments.length === 0
              ? "No deployments found"
              : "No deployments match the selected filter"}
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-gray-500 text-xs uppercase tracking-wider">
                    <th className="text-left px-4 py-3 font-medium">ID</th>
                    <th className="text-left px-4 py-3 font-medium">Name</th>
                    <th className="text-left px-4 py-3 font-medium">Type</th>
                    <th className="text-left px-4 py-3 font-medium">Status</th>
                    <th className="text-left px-4 py-3 font-medium">URL</th>
                    <th className="text-left px-4 py-3 font-medium">Created</th>
                    <th className="text-right px-4 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {filtered.map((d) => (
                    <DeploymentRow
                      key={d.deploy_id}
                      deployment={d}
                      expanded={expandedLogs.has(d.deploy_id)}
                      onToggleLogs={toggleLogs}
                      onTeardown={setTeardownTarget}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-border/50">
              {filtered.map((d) => (
                <DeploymentCard
                  key={d.deploy_id}
                  deployment={d}
                  expanded={expandedLogs.has(d.deploy_id)}
                  onToggleLogs={toggleLogs}
                  onTeardown={setTeardownTarget}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Teardown single dialog */}
      <ConfirmDialog
        open={!!teardownTarget}
        title="Teardown Deployment"
        message={`Tear down "${teardownTarget?.project_name}" (${teardownTarget?.deploy_id?.slice(0, 8)})? This will stop and remove the container.`}
        confirmLabel="Teardown"
        onConfirm={handleTeardown}
        onCancel={() => setTeardownTarget(null)}
      />

      {/* Teardown all dialog */}
      <ConfirmDialog
        open={teardownAllOpen}
        title="Teardown All Deployments"
        message={`Remove all ${deployments.length} deployment(s)? This cannot be undone.`}
        confirmLabel="Teardown All"
        onConfirm={handleTeardownAll}
        onCancel={() => setTeardownAllOpen(false)}
      />
    </div>
  );
}
