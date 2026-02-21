import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { Activity, AlertTriangle } from "lucide-react";
import { api } from "@/api/client";
import { usePageTitle } from "@/hooks/usePageTitle";
import { Skeleton } from "@/components/common/Skeleton";
import type { ModuleHealthMap } from "@/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function StatusPill({ status }: { status: "ok" | "error" | "unknown" }) {
  const styles: Record<string, string> = {
    ok: "bg-green-500/20 text-green-400",
    error: "bg-red-500/20 text-red-400",
    unknown: "bg-gray-500/20 text-gray-400",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${styles[status] ?? styles.unknown}`}>
      {status === "ok" && <span className="w-1.5 h-1.5 rounded-full bg-green-400" />}
      {status === "error" && <span className="w-1.5 h-1.5 rounded-full bg-red-400" />}
      {status === "unknown" && <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />}
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function HealthTableSkeleton() {
  return (
    <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
      <div className="p-4 border-b border-light-border dark:border-border">
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-light-border dark:border-border text-gray-500 text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-2.5 font-medium">Module</th>
              <th className="text-left px-4 py-2.5 font-medium">Status</th>
              <th className="text-right px-4 py-2.5 font-medium">Latency</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-light-border/50 dark:divide-border/50">
            {Array.from({ length: 8 }).map((_, i) => (
              <tr key={i}>
                <td className="px-4 py-3">
                  <Skeleton className="h-3 w-32" />
                </td>
                <td className="px-4 py-3">
                  <Skeleton className="h-5 w-16 rounded-full" />
                </td>
                <td className="px-4 py-3 text-right">
                  <Skeleton className="h-3 w-14 ml-auto" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HealthStatusPage() {
  usePageTitle("Health Status");

  const [data, setData] = useState<ModuleHealthMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const result = await api<ModuleHealthMap>("/api/health");
      setData(result);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch health data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10_000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const entries = data ? Object.entries(data) : [];
  const okCount = entries.filter(([, v]) => v.status === "ok").length;
  const totalCount = entries.length;

  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="p-4 md:p-6 space-y-4 max-w-4xl mx-auto"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity size={22} className="text-accent" />
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
              Health Status
            </h1>
            {lastUpdated && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Last updated: {formatTime(lastUpdated)}
              </p>
            )}
          </div>
        </div>
        {data && (
          <span className="text-sm text-gray-600 dark:text-gray-300 font-medium">
            {okCount} / {totalCount} modules healthy
          </span>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <AlertTriangle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <HealthTableSkeleton />
      ) : (
        <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
          {entries.length === 0 ? (
            <div className="px-4 py-10 text-center text-gray-500 dark:text-gray-400 text-sm">
              No modules configured.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-light-border dark:border-border text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wider">
                    <th className="text-left px-4 py-2.5 font-medium">Module</th>
                    <th className="text-left px-4 py-2.5 font-medium">Status</th>
                    <th className="text-right px-4 py-2.5 font-medium">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-light-border/50 dark:divide-border/50">
                  {entries.map(([name, info]) => (
                    <tr key={name} className="hover:bg-gray-50 dark:hover:bg-surface-lighter transition-colors">
                      <td className="px-4 py-3 font-mono text-sm text-gray-800 dark:text-gray-200">
                        {name}
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={info.status} />
                        {info.error && (
                          <p className="mt-1 text-xs text-red-400 truncate max-w-xs" title={info.error}>
                            {info.error}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400 tabular-nums">
                        {info.latency_ms != null ? `${info.latency_ms} ms` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
