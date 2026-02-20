import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { usePageTitle } from "@/hooks/usePageTitle";
import {
  Folder,
  File,
  ArrowLeft,
  ChevronRight,
  RefreshCw,
  Search,
  Code2,
  ExternalLink,
  Copy,
  Check,
  Trash2,
  Terminal,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { api } from "@/api/client";
import StatusBadge from "@/components/common/StatusBadge";
import RepoLabel from "@/components/common/RepoLabel";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import TerminalPanel from "@/components/code/TerminalPanel";
import type { Task, WorkspaceEntry, WorkspaceFileContent } from "@/types";
import { mapTask } from "@/types";

function formatSize(bytes: number | null): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function isPreviewable(path: string): boolean {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  return ["md", "markdown", "html", "htm"].includes(ext);
}

function truncatePrompt(prompt: string, max = 60): string {
  if (prompt.length <= max) return prompt;
  return prompt.slice(0, max) + "...";
}

function CopyableId({ id, truncate = false }: { id: string; truncate?: boolean }) {
  const [copied, setCopied] = useState(false);
  const display = truncate ? id.slice(0, 8) : id;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 font-mono text-gray-600 dark:text-gray-500 hover:text-gray-900 dark:hover:text-gray-300 transition-colors group"
      title={`Copy ${id}`}
    >
      <span>{display}</span>
      {copied ? (
        <Check size={10} className="text-green-400" />
      ) : (
        <Copy size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </button>
  );
}

export default function CodePage() {
  usePageTitle("Code");
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // Workspace browser state
  const [currentPath, setCurrentPath] = useState("");
  const [entries, setEntries] = useState<WorkspaceEntry[]>([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<WorkspaceFileContent | null>(
    null
  );
  const [fileLoading, setFileLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"raw" | "preview">("raw");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Terminal state
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [terminalHeight, setTerminalHeight] = useState(400);

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api<{ tasks: Array<Record<string, unknown>> }>(
        "/api/tasks"
      );
      const mapped = (data.tasks || []).map(mapTask);

      // Group tasks by workspace to show unique workspaces
      // For each workspace, show the most recent task
      const workspaceMap = new Map<string, Task>();

      for (const task of mapped) {
        const workspace = task.workspace;
        if (!workspace) continue;

        const existing = workspaceMap.get(workspace);
        if (!existing || new Date(task.created_at) > new Date(existing.created_at)) {
          workspaceMap.set(workspace, task);
        }
      }

      const uniqueWorkspaces = Array.from(workspaceMap.values()).sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );

      setTasks(uniqueWorkspaces);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Browse workspace when task or path changes
  useEffect(() => {
    if (!selectedTask) return;
    setBrowseLoading(true);
    api<{ entries: WorkspaceEntry[] }>(
      `/api/tasks/${selectedTask.id}/workspace?path=${encodeURIComponent(currentPath)}`
    )
      .then((data) => setEntries(data.entries || []))
      .catch(() => setEntries([]))
      .finally(() => setBrowseLoading(false));
  }, [selectedTask, currentPath]);

  const handleSelectTask = (task: Task) => {
    setSelectedTask(task);
    setCurrentPath("");
    setSelectedFile(null);
    setEntries([]);
    setTerminalOpen(false); // Close terminal when switching workspaces
  };

  const handleDeleteWorkspace = async (taskId: string) => {
    try {
      await api(`/api/tasks/${taskId}/workspace`, { method: "DELETE" });
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
      if (selectedTask?.id === taskId) {
        setSelectedTask(null);
        setEntries([]);
        setSelectedFile(null);
      }
    } catch {
      // ignore
    }
    setDeleteConfirm(null);
  };

  const handleEntryClick = (entry: WorkspaceEntry) => {
    if (!selectedTask) return;
    if (entry.type === "directory") {
      const newPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      setCurrentPath(newPath);
      setSelectedFile(null);
    } else {
      setFileLoading(true);
      const filePath = currentPath
        ? `${currentPath}/${entry.name}`
        : entry.name;
      api<WorkspaceFileContent>(
        `/api/tasks/${selectedTask.id}/workspace/file?path=${encodeURIComponent(filePath)}`
      )
        .then((f) => {
          setSelectedFile(f);
          setViewMode(isPreviewable(filePath) ? "preview" : "raw");
        })
        .catch(() => setSelectedFile(null))
        .finally(() => setFileLoading(false));
    }
  };

  const navigateUp = () => {
    const parts = currentPath.split("/");
    parts.pop();
    setCurrentPath(parts.join("/"));
    setSelectedFile(null);
  };

  const filtered = search
    ? tasks.filter(
        (t) =>
          t.prompt.toLowerCase().includes(search.toLowerCase()) ||
          t.id.toLowerCase().includes(search.toLowerCase()) ||
          (t.repo_url && t.repo_url.toLowerCase().includes(search.toLowerCase()))
      )
    : tasks;

  const breadcrumbs = currentPath ? currentPath.split("/") : [];

  return (
    <motion.div
      className="flex h-full"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {/* Task/workspace list panel */}
      <div className="w-72 shrink-0 border-r border-light-border dark:border-border flex flex-col bg-white dark:bg-surface-light">
        <div className="p-3 space-y-2 shrink-0 border-b border-light-border dark:border-border">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Code2 size={16} className="text-accent" />
              Code Workspaces
            </h2>
            <button
              onClick={() => {
                setLoading(true);
                fetchTasks();
              }}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-400"
              title="Refresh"
            >
              <RefreshCw size={14} />
            </button>
          </div>
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500"
            />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tasks..."
              className="w-full pl-8 pr-3 py-1.5 rounded-md bg-gray-50 dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-xs placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/50"
              aria-label="Search tasks"
            />
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-8 px-4">
              <Code2 size={32} className="mx-auto text-gray-400 dark:text-gray-700 mb-2" />
              <p className="text-gray-600 dark:text-gray-500 text-sm">
                {search ? "No matching workspaces" : "No code workspaces yet"}
              </p>
              <p className="text-gray-500 dark:text-gray-600 text-xs mt-1">
                Run a claude_code task to create a workspace
              </p>
            </div>
          ) : (
            filtered.map((task) => (
              <div
                key={task.id}
                className={`relative group border-b border-light-border dark:border-border/50 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors ${
                  selectedTask?.id === task.id ? "bg-gray-100 dark:bg-surface-lighter" : ""
                }`}
              >
                <button
                  onClick={() => handleSelectTask(task)}
                  className="w-full text-left px-3 py-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs text-gray-900 dark:text-gray-200 leading-tight line-clamp-2">
                      {truncatePrompt(task.prompt, 80)}
                    </span>
                    <StatusBadge status={task.status} />
                  </div>
                <div className="flex flex-wrap items-center gap-1.5 mt-1.5 text-[10px] text-gray-600 dark:text-gray-500">
                  <CopyableId id={task.id} truncate />
                  <span>{timeAgo(task.created_at)}</span>
                </div>
                {task.repo_url && (
                  <div className="mt-1">
                    <RepoLabel repoUrl={task.repo_url} branch={task.branch} />
                  </div>
                )}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteConfirm(task.id);
                  }}
                  className="absolute right-2 top-2 p-1 rounded hover:bg-red-500/20 text-gray-500 dark:text-gray-600 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Delete workspace"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Workspace browser */}
      {selectedTask ? (
        <div className="flex-1 flex flex-col min-w-0">
          {/* Task info bar */}
          <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-surface border-b border-light-border dark:border-border shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xs shrink-0">
                <CopyableId id={selectedTask.id} />
              </span>
              {selectedTask.repo_url && (
                <RepoLabel repoUrl={selectedTask.repo_url} branch={selectedTask.branch} className="shrink-0" />
              )}
              <span className="text-xs text-gray-600 dark:text-gray-300 truncate">
                {selectedTask.prompt}
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setTerminalOpen(!terminalOpen)}
                className={`flex items-center gap-1 text-xs transition-colors ${
                  terminalOpen
                    ? "text-accent-hover"
                    : "text-accent hover:text-accent-hover"
                }`}
                title={terminalOpen ? "Close terminal" : "Open terminal"}
              >
                <Terminal size={12} />
                Terminal
              </button>
              <button
                onClick={() => navigate(`/tasks/${selectedTask.id}`)}
                className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors"
                title="View task details"
              >
                <ExternalLink size={12} />
                Details
              </button>
              <button
                onClick={() => setDeleteConfirm(selectedTask.id)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-400 transition-colors"
                title="Delete workspace"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>

          {/* Breadcrumb navigation */}
          <div className="flex items-center gap-1 px-3 py-2 bg-gray-100 dark:bg-surface border-b border-light-border dark:border-border text-xs text-gray-500 dark:text-gray-400 overflow-x-auto shrink-0">
            <button
              onClick={() => {
                setCurrentPath("");
                setSelectedFile(null);
              }}
              className="hover:text-gray-900 dark:hover:text-white transition-colors"
            >
              root
            </button>
            {breadcrumbs.map((part, i) => (
              <span key={i} className="flex items-center gap-1">
                <ChevronRight size={12} />
                <button
                  onClick={() => {
                    setCurrentPath(breadcrumbs.slice(0, i + 1).join("/"));
                    setSelectedFile(null);
                  }}
                  className="hover:text-gray-900 dark:hover:text-white transition-colors"
                >
                  {part}
                </button>
              </span>
            ))}
          </div>

          <div className={`flex ${terminalOpen ? "flex-col" : "flex-row"} flex-1 min-h-0`}>
            {/* File browser section */}
            <div className={`flex ${terminalOpen ? "flex-row" : "flex-1"} min-h-0 ${terminalOpen ? "flex-1" : ""}`}>
              {/* File listing */}
              <div className="w-64 shrink-0 border-r border-light-border dark:border-border overflow-auto bg-white dark:bg-surface">
              {currentPath && (
                <button
                  onClick={navigateUp}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors"
                >
                  <ArrowLeft size={14} /> ..
                </button>
              )}
              {browseLoading ? (
                <div className="flex justify-center py-4">
                  <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                </div>
              ) : entries.length === 0 ? (
                <div className="text-center py-4 text-gray-500 text-sm">
                  Empty directory
                </div>
              ) : (
                entries.map((entry) => (
                  <button
                    key={entry.name}
                    onClick={() => handleEntryClick(entry)}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors text-left ${
                      selectedFile?.path?.endsWith(entry.name)
                        ? "bg-gray-100 dark:bg-surface-lighter"
                        : ""
                    }`}
                  >
                    {entry.type === "directory" ? (
                      <Folder size={14} className="text-blue-400 shrink-0" />
                    ) : (
                      <File size={14} className="text-gray-500 shrink-0" />
                    )}
                    <span className="text-gray-700 dark:text-gray-200 truncate flex-1">
                      {entry.name}
                    </span>
                    {entry.type === "file" && (
                      <span className="text-gray-500 dark:text-gray-600 text-xs shrink-0">
                        {formatSize(entry.size)}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>

            {/* File content viewer */}
            <div className="flex-1 overflow-auto bg-gray-50 dark:bg-[#0d0e14]">
              {fileLoading ? (
                <div className="flex justify-center py-8">
                  <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                </div>
              ) : selectedFile ? (
                <div className="flex flex-col h-full">
                  <div className="flex items-center justify-between px-4 py-2 bg-gray-200 dark:bg-black/30 border-b border-light-border dark:border-white/10 text-xs text-gray-600 dark:text-gray-400 shrink-0">
                    <span>{selectedFile.path}</span>
                    <div className="flex items-center gap-3">
                      {!selectedFile.binary &&
                        isPreviewable(selectedFile.path) && (
                          <div className="flex rounded-md border border-light-border dark:border-border overflow-hidden">
                            <button
                              onClick={() => setViewMode("raw")}
                              className={`px-2 py-0.5 text-[10px] font-medium transition-colors ${
                                viewMode === "raw"
                                  ? "bg-accent/20 text-accent-hover"
                                  : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                              }`}
                            >
                              Raw
                            </button>
                            <button
                              onClick={() => setViewMode("preview")}
                              className={`px-2 py-0.5 text-[10px] font-medium border-l border-light-border dark:border-border transition-colors ${
                                viewMode === "preview"
                                  ? "bg-accent/20 text-accent-hover"
                                  : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                              }`}
                            >
                              Preview
                            </button>
                          </div>
                        )}
                      <span>
                        {formatSize(selectedFile.size)}
                        {selectedFile.truncated && " (truncated)"}
                      </span>
                    </div>
                  </div>
                  {selectedFile.binary ? (
                    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                      {selectedFile.message || "Binary file"}
                    </div>
                  ) : viewMode === "preview" &&
                    isPreviewable(selectedFile.path) ? (
                    selectedFile.path.match(/\.html?$/i) ? (
                      <iframe
                        srcDoc={selectedFile.content || ""}
                        className="flex-1 w-full bg-white rounded"
                        sandbox="allow-same-origin"
                        title="HTML preview"
                      />
                    ) : (
                      <div className="flex-1 p-6 overflow-auto prose dark:prose-invert prose-sm max-w-none prose-pre:bg-gray-200 dark:prose-pre:bg-[#0d0e14] prose-pre:border prose-pre:border-border prose-code:text-accent dark:prose-code:text-accent-hover bg-white dark:bg-[#0d0e14] text-gray-900 dark:text-gray-100">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypeHighlight]}
                        >
                          {selectedFile.content || ""}
                        </ReactMarkdown>
                      </div>
                    )
                  ) : (
                    <pre className="flex-1 p-4 text-sm text-gray-700 dark:text-gray-300 whitespace-pre overflow-auto font-mono leading-relaxed">
                      {selectedFile.content}
                    </pre>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                  Select a file to view its contents
                </div>
              )}
            </div>
            </div>

            {/* Terminal panel */}
            {terminalOpen && selectedTask && (
              <TerminalPanel
                taskId={selectedTask.id}
                onClose={() => setTerminalOpen(false)}
                initialHeight={terminalHeight}
              />
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-600">
          <div className="text-center space-y-2">
            <Code2 size={40} className="mx-auto text-gray-400 dark:text-gray-700" />
            <p className="text-sm">
              Select a workspace to browse its files
            </p>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete workspace"
        message="This will permanently delete the workspace directory and all associated tasks. This action cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => deleteConfirm && handleDeleteWorkspace(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </motion.div>
  );
}
