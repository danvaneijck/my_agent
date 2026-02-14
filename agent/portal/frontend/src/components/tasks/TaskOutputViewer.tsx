import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Bot,
  Wrench,
  Terminal,
  CheckCircle2,
  XCircle,
  Pause,
  Play,
  Loader2,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getToken } from "@/api/client";
import type { WsTaskMessage } from "@/types";

interface Props {
  taskId: string;
  initialStatus: string;
}

interface StreamEvent {
  id: number;
  timestamp: string;
  type: string;
  data: Record<string, unknown>;
}

const LOG_LINE_RE = /^\[(\d{2}:\d{2}:\d{2})\]\s+\[stdout\]\s+(.+)$/;

function parseLogLines(lines: string[]): StreamEvent[] {
  const events: StreamEvent[] = [];
  let id = 0;
  for (const line of lines) {
    const m = line.match(LOG_LINE_RE);
    if (!m) continue;
    try {
      const data = JSON.parse(m[2]);
      if (data.type) {
        events.push({ id: id++, timestamp: m[1], type: data.type, data });
      }
    } catch {
      /* skip non-JSON */
    }
  }
  return events;
}

function toolSummary(name: string, input: Record<string, unknown>): string {
  if (!input) return "";
  switch (name) {
    case "Read":
      return (input.file_path as string) || "";
    case "Write":
      return (input.file_path as string) || "";
    case "Edit":
      return (input.file_path as string) || "";
    case "Bash":
      return (input.command as string) || "";
    case "Glob":
      return (input.pattern as string) || "";
    case "Grep":
      return `${input.pattern || ""}${input.path ? ` in ${input.path}` : ""}`;
    case "WebFetch":
      return (input.url as string) || "";
    case "WebSearch":
      return (input.query as string) || "";
    case "Task":
      return (
        (input.description as string) ||
        (input.prompt as string)?.slice(0, 80) ||
        ""
      );
    default:
      return "";
  }
}

function Collapsible({
  label,
  children,
  defaultOpen = false,
}: {
  label: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {label}
      </button>
      {open && <div className="mt-1">{children}</div>}
    </div>
  );
}

function CodeBlock({
  content,
  maxLines = 20,
}: {
  content: string;
  maxLines?: number;
}) {
  const lines = content.split("\n");
  const truncated = lines.length > maxLines;
  const [expanded, setExpanded] = useState(false);
  const display = expanded ? content : lines.slice(0, maxLines).join("\n");

  return (
    <div>
      <pre className="text-xs text-gray-400 bg-black/30 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all max-h-96 overflow-y-auto">
        {display}
      </pre>
      {truncated && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="text-xs text-accent hover:underline mt-1"
        >
          Show all {lines.length} lines
        </button>
      )}
    </div>
  );
}

// --- Event renderers ---

function SystemCard({ event }: { event: StreamEvent }) {
  const tools = event.data.tools as string[] | undefined;
  return (
    <div className="flex items-center gap-2 text-xs text-gray-600 py-1">
      <Terminal size={12} />
      <span>Session started</span>
      {typeof event.data.session_id === "string" && (
        <span className="font-mono">
          {event.data.session_id.slice(0, 8)}
        </span>
      )}
      {tools && <span>&middot; {tools.length} tools</span>}
    </div>
  );
}

function formatToolResult(resultEvent: StreamEvent): string {
  let content = resultEvent.data.content;
  if (Array.isArray(content)) {
    content = (content as Record<string, unknown>[])
      .map((c) =>
        typeof c === "string"
          ? c
          : (c.text as string) ||
            (c.content as string) ||
            JSON.stringify(c),
      )
      .join("\n");
  }
  if (typeof content !== "string") {
    content = JSON.stringify(content, null, 2);
  }
  return content as string;
}

function AssistantCard({
  event,
  toolResults,
  taskRunning,
}: {
  event: StreamEvent;
  toolResults: Map<string, StreamEvent>;
  taskRunning: boolean;
}) {
  const message = event.data.message as Record<string, unknown> | undefined;
  if (!message?.content) return null;

  const contentBlocks = Array.isArray(message.content) ? message.content : [];

  return (
    <>
      {contentBlocks.map((block: Record<string, unknown>, i: number) => {
        if (block.type === "text" && block.text) {
          return (
            <div key={i} className="flex gap-2 py-1">
              <Bot size={14} className="text-accent mt-0.5 shrink-0" />
              <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-[#0d0e14] prose-pre:border prose-pre:border-border prose-code:text-accent-hover">
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                  {block.text as string}
                </ReactMarkdown>
              </div>
            </div>
          );
        }
        if (block.type === "tool_use") {
          const toolUseId = block.id as string;
          const resultEvent = toolUseId
            ? toolResults.get(toolUseId)
            : undefined;
          const isRunning = !resultEvent && taskRunning;
          const isError = resultEvent?.data.is_error === true;
          const hasResult = !!resultEvent;

          const summary = toolSummary(
            block.name as string,
            block.input as Record<string, unknown>,
          );

          let borderClass = "border-border";
          let bgClass = "bg-surface/50";
          let iconColor = "text-blue-400";

          if (isRunning) {
            borderClass = "border-yellow-500/40";
            bgClass = "bg-yellow-500/5";
            iconColor = "text-yellow-400";
          } else if (isError) {
            borderClass = "border-red-500/40";
            bgClass = "bg-red-500/5";
            iconColor = "text-red-400";
          } else if (hasResult) {
            borderClass = "border-green-500/40";
            bgClass = "bg-green-500/5";
            iconColor = "text-green-400";
          }

          const resultContent = resultEvent
            ? formatToolResult(resultEvent)
            : undefined;
          const resultLines = resultContent?.split("\n") || [];
          const isLongResult = resultLines.length > 3;

          return (
            <div
              key={i}
              className={`border rounded-lg p-2 ${borderClass} ${bgClass}`}
            >
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <Loader2
                    size={12}
                    className="text-yellow-400 animate-spin"
                  />
                ) : isError ? (
                  <XCircle size={12} className={iconColor} />
                ) : hasResult ? (
                  <CheckCircle2 size={12} className={iconColor} />
                ) : (
                  <Wrench size={12} className={iconColor} />
                )}
                <span className={`text-xs font-medium ${iconColor}`}>
                  {block.name as string}
                </span>
                {summary && (
                  <span className="text-xs text-gray-500 truncate flex-1 font-mono">
                    {summary}
                  </span>
                )}
                {isRunning && (
                  <span className="text-xs text-yellow-400/70 animate-pulse">
                    running
                  </span>
                )}
              </div>
              {typeof block.input === "object" &&
              block.input !== null &&
              Object.keys(block.input as Record<string, unknown>).length > 0 ? (
                <Collapsible label="Input">
                  <CodeBlock
                    content={JSON.stringify(block.input, null, 2)}
                    maxLines={10}
                  />
                </Collapsible>
              ) : null}
              {resultContent && (
                <Collapsible
                  label={`Output (${resultLines.length} lines)`}
                  defaultOpen={!isLongResult}
                >
                  <CodeBlock content={resultContent} />
                </Collapsible>
              )}
            </div>
          );
        }
        return null;
      })}
    </>
  );
}

function ResultCard({ event }: { event: StreamEvent }) {
  const {
    subtype,
    result,
    is_error,
    duration_ms,
    num_turns,
    total_cost_usd,
  } = event.data;
  const success = subtype === "success" && !is_error;

  return (
    <div
      className={`border rounded-lg p-3 ${
        success
          ? "border-green-500/30 bg-green-500/5"
          : "border-red-500/30 bg-red-500/5"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        {success ? (
          <CheckCircle2 size={14} className="text-green-400" />
        ) : (
          <XCircle size={14} className="text-red-400" />
        )}
        <span
          className={`text-sm font-medium ${success ? "text-green-400" : "text-red-400"}`}
        >
          {success ? "Completed" : "Failed"}
        </span>
        <div className="flex-1" />
        <div className="flex items-center gap-3 text-xs text-gray-500">
          {duration_ms != null && (
            <span>{((duration_ms as number) / 1000).toFixed(1)}s</span>
          )}
          {num_turns != null && <span>{num_turns as number} turns</span>}
          {total_cost_usd != null && (
            <span>${(total_cost_usd as number).toFixed(4)}</span>
          )}
        </div>
      </div>
      {result ? (
        <Collapsible label="Result" defaultOpen>
          <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-[#0d0e14] prose-pre:border prose-pre:border-border prose-code:text-accent-hover mt-1">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {String(result)}
            </ReactMarkdown>
          </div>
        </Collapsible>
      ) : null}
    </div>
  );
}

function EventCard({
  event,
  toolResults,
  taskRunning,
}: {
  event: StreamEvent;
  toolResults: Map<string, StreamEvent>;
  taskRunning: boolean;
}) {
  switch (event.type) {
    case "system":
      return <SystemCard event={event} />;
    case "assistant":
      return (
        <AssistantCard
          event={event}
          toolResults={toolResults}
          taskRunning={taskRunning}
        />
      );
    case "tool_result":
      return null;
    case "result":
      return <ResultCard event={event} />;
    default:
      return null;
  }
}

export default function TaskOutputViewer({ taskId, initialStatus }: Props) {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState(initialStatus);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const wsPath =
    status === "running" || status === "queued"
      ? `/api/tasks/${taskId}/logs/ws`
      : null;

  const { lastMessage, connected } = useWebSocket(wsPath);

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

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  const events = useMemo(() => parseLogLines(lines), [lines]);

  const toolResults = useMemo(() => {
    const map = new Map<string, StreamEvent>();
    const pendingIds: string[] = [];

    // Helper: mark all pending tool calls as completed (inferred from
    // a subsequent assistant or result event — Claude can only respond
    // after all tool results have been processed).
    const flushPending = (ts: string) => {
      for (const id of pendingIds) {
        if (!map.has(id)) {
          map.set(id, {
            id: -1,
            timestamp: ts,
            type: "tool_result",
            data: { content: "", _inferred: true },
          });
        }
      }
      pendingIds.length = 0;
    };

    for (const event of events) {
      if (event.type === "assistant") {
        // A new assistant turn means all previous tool calls completed
        flushPending(event.timestamp);

        const message = event.data.message as Record<string, unknown>;
        const blocks = Array.isArray(message?.content)
          ? (message.content as Record<string, unknown>[])
          : [];
        for (const block of blocks) {
          if (block.type === "tool_use" && block.id) {
            pendingIds.push(block.id as string);
          }
        }
      } else if (event.type === "tool_result") {
        // Explicit tool_result events (if the CLI emits them)
        const toolUseId = event.data.tool_use_id as string;
        if (toolUseId) {
          map.set(toolUseId, event);
        } else if (pendingIds.length > 0) {
          map.set(pendingIds.shift()!, event);
        }
      } else if (event.type === "result") {
        // Task finished — all remaining pending tool calls completed
        flushPending(event.timestamp);
      }
    }

    return map;
  }, [events]);

  const taskRunning = status === "running" || status === "queued";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-surface border-b border-border text-xs">
        <div className="flex items-center gap-3 text-gray-500">
          <span>{events.length} events</span>
          {wsPath && (
            <span className={connected ? "text-green-500" : "text-red-400"}>
              {connected ? "live" : "disconnected"}
            </span>
          )}
        </div>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`p-1.5 rounded hover:bg-surface-lighter ${
            autoScroll ? "text-accent" : "text-gray-500"
          }`}
          title={autoScroll ? "Pause auto-scroll" : "Resume auto-scroll"}
        >
          {autoScroll ? <Pause size={14} /> : <Play size={14} />}
        </button>
      </div>

      <div ref={containerRef} className="flex-1 overflow-auto p-4 space-y-2">
        {events.length === 0 ? (
          <div className="text-gray-600 italic">
            {status === "queued"
              ? "Waiting for task to start..."
              : "No output yet..."}
          </div>
        ) : (
          events.map((event) => (
            <EventCard
              key={event.id}
              event={event}
              toolResults={toolResults}
              taskRunning={taskRunning}
            />
          ))
        )}
      </div>
    </div>
  );
}
