import { useState, useEffect } from "react";
import { Folder, File, ArrowLeft, ChevronRight, Terminal } from "lucide-react";
import { api } from "@/api/client";
import type { WorkspaceEntry, WorkspaceFileContent } from "@/types";
import TerminalPanel from "@/components/code/TerminalPanel";

interface WorkspaceBrowserProps {
  taskId: string;
}

function formatSize(bytes: number | null): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function WorkspaceBrowser({ taskId }: WorkspaceBrowserProps) {
  const [currentPath, setCurrentPath] = useState("");
  const [entries, setEntries] = useState<WorkspaceEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<WorkspaceFileContent | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);

  useEffect(() => {
    setLoading(true);
    api<{ entries: WorkspaceEntry[] }>(
      `/api/tasks/${taskId}/workspace?path=${encodeURIComponent(currentPath)}`
    )
      .then((data) => setEntries(data.entries || []))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [taskId, currentPath]);

  const handleEntryClick = (entry: WorkspaceEntry) => {
    if (entry.type === "directory") {
      const newPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      setCurrentPath(newPath);
      setSelectedFile(null);
    } else {
      setFileLoading(true);
      const filePath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      api<WorkspaceFileContent>(
        `/api/tasks/${taskId}/workspace/file?path=${encodeURIComponent(filePath)}`
      )
        .then(setSelectedFile)
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

  const breadcrumbs = currentPath ? currentPath.split("/") : [];

  return (
    <div className="flex flex-col h-full">
      {/* Breadcrumb navigation with terminal toggle */}
      <div className="flex items-center gap-1 px-3 py-2 bg-gray-100 dark:bg-surface border-b border-light-border dark:border-border text-xs text-gray-500 dark:text-gray-400 overflow-x-auto shrink-0">
        <button
          onClick={() => { setCurrentPath(""); setSelectedFile(null); }}
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

        <div className="flex-1" />

        {/* Terminal toggle button */}
        <button
          onClick={() => setShowTerminal(!showTerminal)}
          className={`inline-flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
            showTerminal
              ? "bg-accent text-white"
              : "bg-gray-200 dark:bg-surface-lighter text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          }`}
          title={showTerminal ? "Close terminal" : "Open terminal"}
        >
          <Terminal size={14} />
          Terminal
        </button>
      </div>

      <div className={`flex flex-1 min-h-0 ${showTerminal ? "flex-col" : ""}`}>
        <div className={`flex ${showTerminal ? "flex-1" : "flex-1"} min-h-0`}>
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
          {loading ? (
            <div className="flex justify-center py-4">
              <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-4 text-gray-500 text-sm">Empty directory</div>
          ) : (
            entries.map((entry) => (
              <button
                key={entry.name}
                onClick={() => handleEntryClick(entry)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors text-left ${
                  selectedFile?.path?.endsWith(entry.name) ? "bg-gray-100 dark:bg-surface-lighter" : ""
                }`}
              >
                {entry.type === "directory" ? (
                  <Folder size={14} className="text-blue-400 shrink-0" />
                ) : (
                  <File size={14} className="text-gray-500 shrink-0" />
                )}
                <span className="text-gray-700 dark:text-gray-200 truncate flex-1">{entry.name}</span>
                {entry.type === "file" && (
                  <span className="text-gray-500 dark:text-gray-600 text-xs shrink-0">{formatSize(entry.size)}</span>
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
                <span>
                  {formatSize(selectedFile.size)}
                  {selectedFile.truncated && " (truncated)"}
                </span>
              </div>
              {selectedFile.binary ? (
                <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                  {selectedFile.message || "Binary file"}
                </div>
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
        {showTerminal && (
          <TerminalPanel
            taskId={taskId}
            onClose={() => setShowTerminal(false)}
            initialHeight={400}
          />
        )}
      </div>
    </div>
  );
}
