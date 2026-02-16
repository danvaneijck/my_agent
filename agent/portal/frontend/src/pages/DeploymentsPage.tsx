import { useState, useEffect, useCallback } from "react";
import {
  RefreshCw,
  Rocket,
  Trash2,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  FileText,
  Settings,
  RotateCcw,
  X,
  Plus,
  Save,
  Minus,
} from "lucide-react";
import { api } from "@/api/client";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import type { Deployment, DeploymentService, ServicePort } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  running: "bg-green-500/20 text-green-400",
  building: "bg-yellow-500/20 text-yellow-400",
  failed: "bg-red-500/20 text-red-400",
  stopped: "bg-gray-500/20 text-gray-400",
  exited: "bg-gray-500/20 text-gray-400",
  pending: "bg-blue-500/20 text-blue-400",
};

const TYPE_LABELS: Record<string, string> = {
  react: "React",
  nextjs: "Next.js",
  static: "Static",
  node: "Node.js",
  docker: "Docker",
  compose: "Compose",
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

// ---- Ports display ----

function PortsList({ deployment }: { deployment: Deployment }) {
  const ports =
    deployment.all_ports && deployment.all_ports.length > 0
      ? deployment.all_ports
      : deployment.port
        ? [{ host: deployment.port, container: 0, protocol: "tcp" } as ServicePort]
        : [];

  if (ports.length === 0) {
    return <span className="text-gray-500">-</span>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {ports.map((p, i) => (
        <a
          key={i}
          href={`http://localhost:${p.host}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-0.5 text-accent hover:text-accent-hover transition-colors"
          title={
            p.service
              ? `${p.service}: host ${p.host} → container ${p.container}`
              : `host ${p.host} → container ${p.container}`
          }
        >
          {p.service && (
            <span className="text-gray-500 text-[10px]">{p.service}</span>
          )}
          :{p.host}
          <ExternalLink size={10} />
        </a>
      ))}
    </div>
  );
}

// ---- Log viewer ----

function LogViewer({ deployId, serviceName }: { deployId: string; serviceName?: string }) {
  const [logs, setLogs] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const url = serviceName
        ? `/api/deployments/${deployId}/services/${serviceName}/logs?lines=100`
        : `/api/deployments/${deployId}/logs?lines=100`;
      const data = await api<{ logs: string }>(url);
      setLogs(data.logs || "No logs available");
    } catch {
      setLogs("Failed to fetch logs");
    } finally {
      setLoading(false);
    }
  }, [deployId, serviceName]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return (
    <div className="bg-gray-100 dark:bg-surface rounded-lg p-3 mt-2">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400">
          {serviceName ? `${serviceName} logs` : "Container Logs"}
        </span>
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

// ---- Service list (for compose) ----

function ServiceList({ deployId, services }: { deployId: string; services: DeploymentService[] }) {
  const [selectedService, setSelectedService] = useState<string | null>(null);

  if (services.length === 0) {
    return <div className="text-xs text-gray-500 py-2">No services found</div>;
  }

  return (
    <div className="mt-2 space-y-2">
      <div className="text-xs text-gray-400 font-medium">
        Services ({services.length})
      </div>
      <div className="bg-gray-100 dark:bg-surface rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-light-border dark:border-border text-gray-500">
              <th className="text-left px-3 py-2 font-medium">Service</th>
              <th className="text-left px-3 py-2 font-medium">Status</th>
              <th className="text-left px-3 py-2 font-medium">Ports</th>
              <th className="text-left px-3 py-2 font-medium">Image</th>
              <th className="text-right px-3 py-2 font-medium">Logs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-light-border dark:divide-border/50">
            {services.map((svc) => (
              <tr key={svc.name} className="hover:bg-surface-lighter/50">
                <td className="px-3 py-2 font-mono text-gray-200">{svc.name}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={svc.status} />
                </td>
                <td className="px-3 py-2">
                  {svc.ports.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {svc.ports.map((p, i) => (
                        <a
                          key={i}
                          href={`http://localhost:${p.host}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-accent hover:text-accent-hover"
                        >
                          :{p.host}
                        </a>
                      ))}
                    </div>
                  ) : (
                    <span className="text-gray-600">-</span>
                  )}
                </td>
                <td className="px-3 py-2 text-gray-400 truncate max-w-[200px]">
                  {svc.image || "-"}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() =>
                      setSelectedService(
                        selectedService === svc.name ? null : svc.name
                      )
                    }
                    className="p-1 rounded hover:bg-surface-lighter text-gray-500 hover:text-gray-300"
                  >
                    <FileText size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedService && (
        <LogViewer deployId={deployId} serviceName={selectedService} />
      )}
    </div>
  );
}

// ---- Env var editor modal ----

function EnvVarEditor({
  deployId,
  onClose,
}: {
  deployId: string;
  onClose: () => void;
}) {
  const [envVars, setEnvVars] = useState<[string, string][]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await api<{ env_vars: Record<string, string> }>(
          `/api/deployments/${deployId}/env`
        );
        const entries = Object.entries(data.env_vars || {});
        setEnvVars(entries.length > 0 ? entries : [["", ""]]);
      } catch {
        setEnvVars([["", ""]]);
      } finally {
        setLoading(false);
      }
    })();
  }, [deployId]);

  const handleSave = async (restart: boolean) => {
    setSaving(true);
    try {
      const vars: Record<string, string> = {};
      for (const [key, value] of envVars) {
        if (key.trim()) vars[key.trim()] = value;
      }
      await api(`/api/deployments/${deployId}/env`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ env_vars: vars, restart }),
      });
      onClose();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  const updateEntry = (index: number, field: 0 | 1, value: string) => {
    setEnvVars((prev) => {
      const next = [...prev];
      next[index] = [...next[index]] as [string, string];
      next[index][field] = value;
      return next;
    });
  };

  const addEntry = () => setEnvVars((prev) => [...prev, ["", ""]]);

  const removeEntry = (index: number) => {
    setEnvVars((prev) => {
      if (prev.length <= 1) return [["", ""]];
      return prev.filter((_, i) => i !== index);
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-light-border dark:border-border">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Settings size={16} className="text-accent" />
            Environment Variables
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {envVars.map(([key, value], i) => (
                <div key={i} className="flex gap-2 items-center">
                  <input
                    type="text"
                    value={key}
                    onChange={(e) => updateEntry(i, 0, e.target.value)}
                    placeholder="KEY"
                    className="flex-[2] bg-surface border border-border rounded px-2 py-1.5 text-xs text-gray-200 font-mono placeholder-gray-600 focus:outline-none focus:border-accent"
                  />
                  <span className="text-gray-600">=</span>
                  <input
                    type="text"
                    value={value}
                    onChange={(e) => updateEntry(i, 1, e.target.value)}
                    placeholder="value"
                    className="flex-[3] bg-surface border border-border rounded px-2 py-1.5 text-xs text-gray-200 font-mono placeholder-gray-600 focus:outline-none focus:border-accent"
                  />
                  <button
                    onClick={() => removeEntry(i)}
                    className="p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400"
                  >
                    <Minus size={14} />
                  </button>
                </div>
              ))}
              <button
                onClick={addEntry}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200 mt-1"
              >
                <Plus size={12} />
                Add variable
              </button>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-light-border dark:border-border">
          <button
            onClick={() => handleSave(false)}
            disabled={saving}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-gray-300 hover:bg-surface-lighter transition-colors"
          >
            <span className="flex items-center gap-1">
              <Save size={12} />
              Save Only
            </span>
          </button>
          <button
            onClick={() => handleSave(true)}
            disabled={saving}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/15 text-accent-hover hover:bg-accent/25 transition-colors"
          >
            {saving ? (
              <div className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="flex items-center gap-1">
                <Save size={12} />
                Save & Restart
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Desktop row ----

function DeploymentRow({
  deployment,
  expanded,
  onToggleExpand,
  onTeardown,
  onRestart,
  onEditEnv,
}: {
  deployment: Deployment;
  expanded: boolean;
  onToggleExpand: (id: string) => void;
  onTeardown: (d: Deployment) => void;
  onRestart: (id: string) => void;
  onEditEnv: (id: string) => void;
}) {
  const isCompose = deployment.project_type === "compose";

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
          <PortsList deployment={deployment} />
        </td>
        <td className="px-4 py-3 text-gray-400 text-xs">
          {formatDate(deployment.created_at)}
        </td>
        <td className="px-4 py-3 text-right">
          <div className="flex items-center justify-end gap-1">
            {isCompose && (
              <button
                onClick={() => onEditEnv(deployment.deploy_id)}
                className="p-1 rounded hover:bg-surface-lighter text-gray-500 hover:text-gray-300 transition-colors"
                title="Environment variables"
              >
                <Settings size={16} />
              </button>
            )}
            <button
              onClick={() => onRestart(deployment.deploy_id)}
              className="p-1 rounded hover:bg-surface-lighter text-gray-500 hover:text-gray-300 transition-colors"
              title="Restart"
            >
              <RotateCcw size={16} />
            </button>
            <button
              onClick={() => onToggleExpand(deployment.deploy_id)}
              className="p-1 rounded hover:bg-surface-lighter text-gray-500 hover:text-gray-300 transition-colors"
              title={isCompose ? "Services & Logs" : "View logs"}
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
            {isCompose ? (
              <ServiceList
                deployId={deployment.deploy_id}
                services={deployment.services || []}
              />
            ) : (
              <LogViewer deployId={deployment.deploy_id} />
            )}
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
  onToggleExpand,
  onTeardown,
  onRestart,
  onEditEnv,
}: {
  deployment: Deployment;
  expanded: boolean;
  onToggleExpand: (id: string) => void;
  onTeardown: (d: Deployment) => void;
  onRestart: (id: string) => void;
  onEditEnv: (id: string) => void;
}) {
  const isCompose = deployment.project_type === "compose";

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
        <PortsList deployment={deployment} />
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Created {formatDate(deployment.created_at)}</span>
        <div className="flex items-center gap-2">
          {isCompose && (
            <button
              onClick={() => onEditEnv(deployment.deploy_id)}
              className="flex items-center gap-1 text-gray-400 hover:text-gray-200"
            >
              <Settings size={14} />
              Env
            </button>
          )}
          <button
            onClick={() => onRestart(deployment.deploy_id)}
            className="flex items-center gap-1 text-gray-400 hover:text-gray-200"
          >
            <RotateCcw size={14} />
          </button>
          <button
            onClick={() => onToggleExpand(deployment.deploy_id)}
            className="flex items-center gap-1 text-gray-400 hover:text-gray-200"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {isCompose ? "Services" : "Logs"}
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
      {expanded &&
        (isCompose ? (
          <ServiceList
            deployId={deployment.deploy_id}
            services={deployment.services || []}
          />
        ) : (
          <LogViewer deployId={deployment.deploy_id} />
        ))}
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
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [envEditorId, setEnvEditorId] = useState<string | null>(null);

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

  const handleRestart = async (deployId: string) => {
    try {
      await api(`/api/deployments/${deployId}/restart`, { method: "POST" });
      fetchDeployments();
    } catch {
      // ignore
    }
  };

  const toggleExpand = (deployId: string) => {
    setExpandedIds((prev) => {
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
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
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
                  <tr className="border-b border-light-border dark:border-border text-gray-500 text-xs uppercase tracking-wider">
                    <th className="text-left px-4 py-3 font-medium">ID</th>
                    <th className="text-left px-4 py-3 font-medium">Name</th>
                    <th className="text-left px-4 py-3 font-medium">Type</th>
                    <th className="text-left px-4 py-3 font-medium">Status</th>
                    <th className="text-left px-4 py-3 font-medium">Ports</th>
                    <th className="text-left px-4 py-3 font-medium">Created</th>
                    <th className="text-right px-4 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-light-border dark:divide-border/50">
                  {filtered.map((d) => (
                    <DeploymentRow
                      key={d.deploy_id}
                      deployment={d}
                      expanded={expandedIds.has(d.deploy_id)}
                      onToggleExpand={toggleExpand}
                      onTeardown={setTeardownTarget}
                      onRestart={handleRestart}
                      onEditEnv={setEnvEditorId}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-light-border dark:divide-border/50">
              {filtered.map((d) => (
                <DeploymentCard
                  key={d.deploy_id}
                  deployment={d}
                  expanded={expandedIds.has(d.deploy_id)}
                  onToggleExpand={toggleExpand}
                  onTeardown={setTeardownTarget}
                  onRestart={handleRestart}
                  onEditEnv={setEnvEditorId}
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
        message={`Tear down "${teardownTarget?.project_name}" (${teardownTarget?.deploy_id?.slice(0, 8)})? This will stop and remove ${teardownTarget?.project_type === "compose" ? "all services" : "the container"}.`}
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

      {/* Env var editor modal */}
      {envEditorId && (
        <EnvVarEditor
          deployId={envEditorId}
          onClose={() => setEnvEditorId(null)}
        />
      )}
    </div>
  );
}
