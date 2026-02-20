import { useEffect, useRef, useState } from "react";
import { Pause, Play, Copy, Check } from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getToken } from "@/api/client";
import type { WsTaskMessage } from "@/types";

interface TaskLogViewerProps {
  taskId: string;
  initialStatus: string;
}

export default function TaskLogViewer({ taskId, initialStatus }: TaskLogViewerProps) {
  const [lines, setLines] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const [status, setStatus] = useState(initialStatus);
  const containerRef = useRef<HTMLDivElement>(null);

  // Only connect WebSocket if task might produce more logs
  const wsPath =
    status === "running" || status === "queued"
      ? `/api/tasks/${taskId}/logs/ws`
      : null;

  const { lastMessage, connected } = useWebSocket(wsPath);

  // Load initial logs for completed/failed tasks
  useEffect(() => {
    if (status !== "running" && status !== "queued") {
      fetch(`/api/tasks/${taskId}/logs?tail=5000`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.lines) setLines(data.lines);
        })
        .catch(() => {});
    }
  }, [taskId, status]);

  // Process WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;
    const msg = lastMessage as WsTaskMessage;

    if (msg.type === "log_lines") {
      setLines((prev) => [...prev, ...msg.lines]);
      setStatus(msg.status);
    } else if (msg.type === "status_change") {
      setStatus(msg.status);
    }
  }, [lastMessage]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-100 dark:bg-surface border-b border-light-border dark:border-border text-xs">
        <div className="flex items-center gap-3 text-gray-500">
          <span>{lines.length} lines</span>
          {wsPath && (
            <span className={connected ? "text-green-500" : "text-red-400"}>
              {connected ? "live" : "disconnected"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded hover:bg-gray-200 dark:hover:bg-surface-lighter ${
              autoScroll ? "text-accent" : "text-gray-500"
            }`}
            title={autoScroll ? "Pause auto-scroll" : "Resume auto-scroll"}
          >
            {autoScroll ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            onClick={handleCopy}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-surface-lighter text-gray-500"
            title="Copy all logs"
          >
            {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          </button>
        </div>
      </div>

      {/* Log content */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-gray-50 dark:bg-[#0d0e14] p-3 log-viewer"
      >
        {lines.length === 0 ? (
          <div className="text-gray-500 italic">
            {status === "queued" ? "Waiting for task to start..." : "No log output yet..."}
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-all hover:bg-black/5 dark:hover:bg-white/5">
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
