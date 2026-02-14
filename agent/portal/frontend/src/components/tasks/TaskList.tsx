import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, ArrowUp, ArrowDown, ChevronRight, ChevronDown, Layers, Copy, Check } from "lucide-react";
import StatusBadge from "@/components/common/StatusBadge";
import RepoLabel from "@/components/common/RepoLabel";
import type { Task } from "@/types";

function isStale(task: Task): boolean {
  if (task.status !== "running" || !task.heartbeat) return false;
  const heartbeatAge = Date.now() - new Date(task.heartbeat).getTime();
  return heartbeatAge > 90_000;
}

function formatElapsed(seconds: number | null): string {
  if (seconds == null) return "-";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatTime(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type SortKey = "status" | "created_at" | "elapsed_seconds";
type SortDir = "asc" | "desc";

const STATUS_ORDER: Record<string, number> = {
  running: 0,
  queued: 1,
  awaiting_input: 2,
  completed: 3,
  timed_out: 4,
  failed: 5,
  cancelled: 6,
};

interface TaskChain {
  root: Task;
  tasks: Task[]; // all tasks in chain, sorted by created_at
  latest: Task;  // most recent task
}

function buildChains(tasks: Task[]): TaskChain[] {
  const chainMap = new Map<string, Task[]>();

  for (const task of tasks) {
    const chainId = task.parent_task_id || task.id;
    const existing = chainMap.get(chainId);
    if (existing) {
      existing.push(task);
    } else {
      chainMap.set(chainId, [task]);
    }
  }

  const chains: TaskChain[] = [];
  for (const [, chainTasks] of chainMap) {
    const sorted = [...chainTasks].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    const root = sorted[0];
    const latest = sorted[sorted.length - 1];
    chains.push({ root, tasks: sorted, latest });
  }

  return chains;
}

function compareChains(a: TaskChain, b: TaskChain, key: SortKey, dir: SortDir): number {
  let cmp = 0;
  switch (key) {
    case "status":
      cmp = (STATUS_ORDER[a.latest.status] ?? 9) - (STATUS_ORDER[b.latest.status] ?? 9);
      break;
    case "created_at": {
      const ta = a.root.created_at ? new Date(a.root.created_at).getTime() : 0;
      const tb = b.root.created_at ? new Date(b.root.created_at).getTime() : 0;
      cmp = ta - tb;
      break;
    }
    case "elapsed_seconds": {
      const ea = a.tasks.reduce((sum, t) => sum + (t.elapsed_seconds ?? 0), 0);
      const eb = b.tasks.reduce((sum, t) => sum + (t.elapsed_seconds ?? 0), 0);
      cmp = ea - eb;
      break;
    }
  }
  return dir === "desc" ? -cmp : cmp;
}

function totalElapsed(chain: TaskChain): number | null {
  const total = chain.tasks.reduce((sum, t) => sum + (t.elapsed_seconds ?? 0), 0);
  return total > 0 ? total : null;
}

function CopyableId({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 font-mono text-xs text-gray-500 hover:text-gray-300 transition-colors group"
      title={`Copy ${id}`}
    >
      <span className="truncate max-w-[120px]">{id}</span>
      {copied ? (
        <Check size={10} className="shrink-0 text-green-400" />
      ) : (
        <Copy size={10} className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </button>
  );
}

interface TaskListProps {
  tasks: Task[];
}

export default function TaskList({ tasks }: TaskListProps) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const chains = useMemo(() => {
    const c = buildChains(tasks);
    return c.sort((a, b) => compareChains(a, b, sortKey, sortDir));
  }, [tasks, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "created_at" ? "desc" : "asc");
    }
  };

  const toggleExpand = (chainId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(chainId)) next.delete(chainId);
      else next.add(chainId);
      return next;
    });
  };

  if (tasks.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No tasks yet. Create one to get started.
      </div>
    );
  }

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null;
    return sortDir === "desc" ? (
      <ArrowDown size={12} className="inline ml-0.5" />
    ) : (
      <ArrowUp size={12} className="inline ml-0.5" />
    );
  };

  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-gray-500 text-left">
              <th
                className="px-4 py-3 font-medium cursor-pointer select-none hover:text-gray-300"
                onClick={() => toggleSort("status")}
              >
                Status
                <SortIcon col="status" />
              </th>
              <th className="px-4 py-3 font-medium">ID</th>
              <th className="px-4 py-3 font-medium">Repo</th>
              <th className="px-4 py-3 font-medium">Prompt</th>
              <th
                className="px-4 py-3 font-medium cursor-pointer select-none hover:text-gray-300"
                onClick={() => toggleSort("created_at")}
              >
                Created
                <SortIcon col="created_at" />
              </th>
              <th
                className="px-4 py-3 font-medium cursor-pointer select-none hover:text-gray-300"
                onClick={() => toggleSort("elapsed_seconds")}
              >
                Duration
                <SortIcon col="elapsed_seconds" />
              </th>
            </tr>
          </thead>
          <tbody>
            {chains.map((chain) => {
              const isChain = chain.tasks.length > 1;
              const chainId = chain.root.id;
              const isOpen = expanded.has(chainId);

              return (
                <ChainRows
                  key={chainId}
                  chain={chain}
                  isChain={isChain}
                  isOpen={isOpen}
                  onToggle={(e) => toggleExpand(chainId, e)}
                  onNavigate={(id) => navigate(`/tasks/${id}`)}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3 p-4">
        {chains.map((chain) => {
          const isChain = chain.tasks.length > 1;
          const chainId = chain.root.id;
          const isOpen = expanded.has(chainId);

          return (
            <div key={chainId}>
              {/* Chain / standalone card */}
              <div
                onClick={() => navigate(`/tasks/${chain.latest.id}`)}
                className="bg-surface-light border border-border rounded-lg p-4 space-y-2 active:bg-surface-lighter"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {isChain && (
                      <button
                        onClick={(e) => toggleExpand(chainId, e)}
                        className="p-0.5 text-gray-500 hover:text-gray-300"
                      >
                        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>
                    )}
                    <StatusBadge status={chain.latest.status} stale={isStale(chain.latest)} />
                    {isChain && (
                      <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                        <Layers size={10} />
                        {chain.tasks.length}
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-xs text-gray-500">
                    {chain.latest.id.slice(0, 8)}
                  </span>
                </div>
                <p className="text-sm text-gray-200 line-clamp-2">
                  {chain.root.mode === "plan" && (
                    <span className="text-purple-400 text-xs mr-1.5">[plan]</span>
                  )}
                  {chain.root.prompt}
                </p>
                <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                  <span>{formatTime(chain.root.created_at)}</span>
                  <span className="inline-flex items-center gap-1">
                    <Clock size={12} />
                    {formatElapsed(totalElapsed(chain))}
                  </span>
                  {chain.root.repo_url && (
                    <RepoLabel repoUrl={chain.root.repo_url} branch={chain.root.branch} />
                  )}
                </div>
              </div>

              {/* Expanded chain tasks */}
              {isChain && isOpen && (
                <div className="ml-4 mt-1 space-y-1">
                  {chain.tasks.map((task) => (
                    <div
                      key={task.id}
                      onClick={() => navigate(`/tasks/${task.id}`)}
                      className="bg-surface border border-border/50 rounded-lg p-3 space-y-1 active:bg-surface-lighter"
                    >
                      <div className="flex items-center justify-between">
                        <StatusBadge status={task.status} stale={isStale(task)} />
                        <span className="font-mono text-xs text-gray-500">
                          {task.id.slice(0, 8)}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 line-clamp-1">{task.prompt}</p>
                      <div className="flex items-center gap-3 text-xs text-gray-600">
                        <span>{formatTime(task.created_at)}</span>
                        <span>{formatElapsed(task.elapsed_seconds)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

/** Renders the table rows for a single chain (header row + optional expanded children). */
function ChainRows({
  chain,
  isChain,
  isOpen,
  onToggle,
  onNavigate,
}: {
  chain: TaskChain;
  isChain: boolean;
  isOpen: boolean;
  onToggle: (e: React.MouseEvent) => void;
  onNavigate: (id: string) => void;
}) {
  return (
    <>
      {/* Chain header row — clicks navigate to the latest task */}
      <tr
        onClick={() => onNavigate(chain.latest.id)}
        className="border-b border-border/50 hover:bg-surface-lighter cursor-pointer transition-colors"
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {isChain && (
              <button
                onClick={onToggle}
                className="p-0.5 text-gray-500 hover:text-gray-300"
              >
                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            )}
            <StatusBadge status={chain.latest.status} stale={isStale(chain.latest)} />
          </div>
        </td>
        <td className="px-4 py-3 font-mono text-xs text-gray-400">
          <div className="flex items-center gap-1.5">
            {chain.latest.id.slice(0, 8)}
            {isChain && (
              <span className="inline-flex items-center gap-0.5 text-gray-600">
                <Layers size={10} />
                {chain.tasks.length}
              </span>
            )}
          </div>
        </td>
        <td className="px-4 py-3">
          {chain.root.repo_url ? (
            <RepoLabel repoUrl={chain.root.repo_url} branch={chain.root.branch} />
          ) : (
            <CopyableId id={chain.root.workspace} />
          )}
        </td>
        <td className="px-4 py-3 text-gray-200 max-w-md">
          <div className="flex items-center gap-2 min-w-0">
            {chain.root.mode === "plan" && (
              <span className="text-purple-400 text-xs shrink-0">[plan]</span>
            )}
            <span className="truncate">{chain.root.prompt}</span>
          </div>
        </td>
        <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
          {formatTime(chain.root.created_at)}
        </td>
        <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
          <span className="inline-flex items-center gap-1">
            <Clock size={14} />
            {formatElapsed(totalElapsed(chain))}
          </span>
        </td>
      </tr>

      {/* Expanded child rows */}
      {isChain &&
        isOpen &&
        chain.tasks.map((task) => (
          <tr
            key={task.id}
            onClick={() => onNavigate(task.id)}
            className="border-b border-border/30 hover:bg-surface-lighter cursor-pointer transition-colors bg-surface/30"
          >
            <td className="pl-10 pr-4 py-2">
              <StatusBadge status={task.status} stale={isStale(task)} />
            </td>
            <td className="px-4 py-2 font-mono text-xs text-gray-500">
              {task.id.slice(0, 8)}
            </td>
            <td className="px-4 py-2">
              {task.repo_url ? (
                <RepoLabel repoUrl={task.repo_url} branch={task.branch} />
              ) : (
                <CopyableId id={task.workspace} />
              )}
            </td>
            <td className="px-4 py-2 text-gray-400 text-xs max-w-md truncate">
              {task.prompt}
            </td>
            <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
              {formatTime(task.created_at)}
            </td>
            <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
              <span className="inline-flex items-center gap-1">
                <Clock size={12} />
                {formatElapsed(task.elapsed_seconds)}
              </span>
            </td>
          </tr>
        ))}
    </>
  );
}
