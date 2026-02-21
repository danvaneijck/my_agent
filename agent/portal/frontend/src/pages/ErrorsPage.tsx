import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { usePageTitle } from "@/hooks/usePageTitle";
import {
  AlertTriangle,
  RefreshCw,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  RotateCcw,
} from "lucide-react";
import { api } from "@/api/client";

interface ErrorEntry {
  id: string;
  service: string;
  error_type: string;
  tool_name: string | null;
  tool_arguments: Record<string, unknown> | null;
  error_message: string;
  stack_trace: string | null;
  user_id: string | null;
  conversation_id: string | null;
  status: "open" | "dismissed" | "resolved";
  created_at: string;
  resolved_at: string | null;
}

interface ErrorsResponse {
  errors: ErrorEntry[];
  total: number;
  open_count: number;
}

interface SummaryResponse {
  open: number;
  dismissed: number;
  resolved: number;
  by_service_and_type: { service: string; error_type: string; count: number }[];
}

const STATUS_STYLES: Record<string, string> = {
  open: "bg-red-500/15 text-red-400",
  dismissed: "bg-gray-500/15 text-gray-400",
  resolved: "bg-green-500/15 text-green-400",
};

const ERROR_TYPE_LABELS: Record<string, string> = {
  tool_execution: "Tool Error",
  agent_loop: "Agent Error",
  module_startup: "Startup Error",
  invalid_tool: "Invalid Tool",
  llm_call: "LLM Error",
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function buildClaudePrompt(err: ErrorEntry): string {
  const lines: string[] = [
    "Fix this error in the AI agent system:",
    "",
    `Service: ${err.service}`,
    `Error type: ${err.error_type}`,
  ];
  if (err.tool_name) lines.push(`Tool: ${err.tool_name}`);
  lines.push(`Error: ${err.error_message}`);
  if (err.tool_arguments && Object.keys(err.tool_arguments).length > 0) {
    lines.push(`Arguments: ${JSON.stringify(err.tool_arguments, null, 2)}`);
  }
  if (err.stack_trace) {
    lines.push("", "Stack trace:", err.stack_trace);
  }
  lines.push("", `Timestamp: ${err.created_at}`);
  lines.push("", "Please diagnose and fix the root cause.");
  return lines.join("\n");
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[status] || STATUS_STYLES.open}`}
    >
      {status === "open" && (
        <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
      )}
      {status}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <button
      onClick={handleCopy}
      title="Copy prompt for Claude"
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-accent/15 text-accent hover:bg-accent/25 transition-colors"
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      {copied ? "Copied!" : "Copy for Claude"}
    </button>
  );
}

function ErrorCard({
  err,
  onAction,
}: {
  err: ErrorEntry;
  onAction: (id: string, action: "dismiss" | "resolve" | "reopen") => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-light-border dark:border-border rounded-xl overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-start gap-3 p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-surface-lighter/40 transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="mt-0.5 flex-shrink-0 text-gray-400">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <StatusBadge status={err.status} />
            <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-surface text-gray-600 dark:text-gray-400 font-medium">
              {err.service}
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-surface text-gray-600 dark:text-gray-400">
              {ERROR_TYPE_LABELS[err.error_type] || err.error_type}
            </span>
            {err.tool_name && (
              <span className="text-xs font-mono text-gray-500 dark:text-gray-400">
                {err.tool_name}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-800 dark:text-gray-200 truncate">
            {err.error_message}
          </p>
          <p className="text-xs text-gray-400 mt-1">{formatDate(err.created_at)}</p>
        </div>

        {/* Action buttons — stop propagation so clicking them doesn't expand */}
        <div
          className="flex items-center gap-2 flex-shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          <CopyButton text={buildClaudePrompt(err)} />
          {err.status === "open" && (
            <>
              <button
                onClick={() => onAction(err.id, "dismiss")}
                className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                title="Dismiss"
              >
                <XCircle size={16} />
              </button>
              <button
                onClick={() => onAction(err.id, "resolve")}
                className="p-1.5 rounded-lg hover:bg-green-500/15 text-gray-400 hover:text-green-400 transition-colors"
                title="Mark resolved"
              >
                <CheckCircle size={16} />
              </button>
            </>
          )}
          {(err.status === "dismissed" || err.status === "resolved") && (
            <button
              onClick={() => onAction(err.id, "reopen")}
              className="p-1.5 rounded-lg hover:bg-yellow-500/15 text-gray-400 hover:text-yellow-400 transition-colors"
              title="Reopen"
            >
              <RotateCcw size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3 border-t border-light-border dark:border-border">
              {err.tool_arguments && Object.keys(err.tool_arguments).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1 mt-3">
                    Arguments
                  </p>
                  <pre className="text-xs font-mono bg-gray-50 dark:bg-surface p-3 rounded-lg overflow-x-auto text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-all">
                    {JSON.stringify(err.tool_arguments, null, 2)}
                  </pre>
                </div>
              )}

              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1 mt-3">
                  Error Message
                </p>
                <pre className="text-xs font-mono bg-red-50 dark:bg-red-500/10 p-3 rounded-lg overflow-x-auto text-red-700 dark:text-red-300 whitespace-pre-wrap break-all">
                  {err.error_message}
                </pre>
              </div>

              {err.stack_trace && (
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                    Stack Trace
                  </p>
                  <pre className="text-xs font-mono bg-gray-50 dark:bg-surface p-3 rounded-lg overflow-x-auto text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                    {err.stack_trace}
                  </pre>
                </div>
              )}

              {(err.user_id || err.conversation_id) && (
                <div className="flex flex-wrap gap-4 text-xs text-gray-400">
                  {err.user_id && (
                    <span>
                      <span className="text-gray-500">User:</span>{" "}
                      <span className="font-mono">{err.user_id}</span>
                    </span>
                  )}
                  {err.conversation_id && (
                    <span>
                      <span className="text-gray-500">Conversation:</span>{" "}
                      <span className="font-mono">{err.conversation_id}</span>
                    </span>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

type StatusFilter = "all" | "open" | "dismissed" | "resolved";

export default function ErrorsPage() {
  usePageTitle("Error Logs");
  const [errors, setErrors] = useState<ErrorEntry[]>([]);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("open");

  const fetchData = useCallback(async () => {
    try {
      const [errData, sumData] = await Promise.all([
        api<ErrorsResponse>(
          `/api/errors${filter !== "all" ? `?status=${filter}` : ""}?limit=100`
        ),
        api<SummaryResponse>("/api/errors/summary"),
      ]);
      setErrors(errData.errors || []);
      setSummary(sumData);
    } catch {
      // ignore — user may not have admin permission
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [fetchData]);

  const handleAction = async (
    id: string,
    action: "dismiss" | "resolve" | "reopen"
  ) => {
    try {
      await api(`/api/errors/${id}/${action}`, { method: "POST" });
      fetchData();
    } catch {
      // ignore
    }
  };

  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="p-4 md:p-6 space-y-4"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <AlertTriangle size={20} className="text-red-400" />
            Error Logs
          </h2>
          <button
            onClick={() => {
              setLoading(true);
              fetchData();
            }}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          )}
        </div>

        {/* Status filter */}
        <div className="flex gap-1">
          {(["open", "all", "dismissed", "resolved"] as StatusFilter[]).map(
            (s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  filter === s
                    ? "bg-accent/15 text-accent-hover"
                    : "text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-surface-lighter"
                }`}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
                {s === "open" && summary && summary.open > 0 && (
                  <span className="ml-1.5 bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5">
                    {summary.open}
                  </span>
                )}
              </button>
            )
          )}
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-red-400">{summary.open}</p>
            <p className="text-xs text-gray-500 mt-1">Open</p>
          </div>
          <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-gray-400">{summary.dismissed}</p>
            <p className="text-xs text-gray-500 mt-1">Dismissed</p>
          </div>
          <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-green-400">{summary.resolved}</p>
            <p className="text-xs text-gray-500 mt-1">Resolved</p>
          </div>
        </div>
      )}

      {/* Top errors by service */}
      {summary && summary.by_service_and_type.length > 0 && (
        <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
            Open Errors by Service
          </p>
          <div className="flex flex-wrap gap-2">
            {summary.by_service_and_type.slice(0, 10).map((g) => (
              <span
                key={`${g.service}-${g.error_type}`}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-red-500/10 text-red-400"
              >
                <span className="font-medium">{g.service}</span>
                <span className="text-red-500/60">·</span>
                <span>{ERROR_TYPE_LABELS[g.error_type] || g.error_type}</span>
                <span className="font-bold ml-0.5">{g.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Error list */}
      <div className="space-y-2">
        {loading && errors.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : errors.length === 0 ? (
          <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-12 text-center">
            <CheckCircle size={32} className="mx-auto text-green-400 mb-3" />
            <p className="text-gray-600 dark:text-gray-400 text-sm">
              {filter === "open"
                ? "No open errors — everything looks healthy!"
                : `No ${filter} errors found.`}
            </p>
          </div>
        ) : (
          errors.map((err) => (
            <ErrorCard key={err.id} err={err} onAction={handleAction} />
          ))
        )}
      </div>
    </motion.div>
  );
}
