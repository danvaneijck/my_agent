import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { User, Bot, Download, ChevronDown, ChevronRight, Workflow } from "lucide-react";
import type { ChatMessage } from "@/types";
import ToolCallsDisplay from "./ToolCallsDisplay";

interface MessageBubbleProps {
  message: ChatMessage;
}

const WORKFLOW_PREFIX = "[Automated workflow continuation";

function parseWorkflowMessage(content: string) {
  const lines = content.split("\n");
  // Extract job ID from first line: [Automated workflow continuation — job <uuid>]
  const headerMatch = lines[0]?.match(/job\s+([a-f0-9-]+)/i);
  const jobId = headerMatch?.[1] || null;

  // Find the actual context message (between header and result data / instruction)
  let contextMsg = "";
  let resultData = "";
  let inResult = false;

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("Task result data:") || line.startsWith("Task result summary:")) {
      inResult = true;
      resultData = line.replace(/^Task result (?:data|summary):/, "").trim();
      continue;
    }
    if (line.startsWith("Continue with the next steps")) {
      break;
    }
    if (inResult) {
      resultData += "\n" + line;
    } else {
      contextMsg += (contextMsg ? "\n" : "") + line;
    }
  }

  // Strip large inline dict/JSON blobs from contextMsg (legacy messages may
  // have the full result_data embedded via {result} interpolation).
  // Detect patterns like: "Build status: {'task_id': ...}" and move them to resultData.
  const cleaned = contextMsg.trim();
  const inlineBlobMatch = cleaned.match(/^(.*?)(\{[\s\S]{200,})$/s);
  if (inlineBlobMatch) {
    contextMsg = inlineBlobMatch[1].trim();
    if (!resultData) {
      resultData = inlineBlobMatch[2].trim();
    }
  }

  return { jobId, contextMsg: contextMsg.trim(), resultData: resultData.trim() };
}

function WorkflowBubble({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(false);
  const { jobId, contextMsg, resultData } = parseWorkflowMessage(message.content);

  return (
    <div className="flex gap-3">
      <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-yellow-500/20 text-yellow-400">
        <Workflow size={16} />
      </div>
      <div className="max-w-[80%] rounded-xl px-4 py-3 text-sm bg-yellow-500/5 border border-yellow-500/20 text-gray-700 dark:text-gray-300">
        <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 text-xs font-medium mb-1">
          <span>Workflow continuation</span>
          {jobId && (
            <span className="text-gray-500 dark:text-gray-600 font-mono">
              {jobId.slice(0, 8)}
            </span>
          )}
        </div>
        {contextMsg && (
          <p className="text-gray-700 dark:text-gray-300 text-sm whitespace-pre-wrap">{contextMsg}</p>
        )}
        {resultData && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            Result data
          </button>
        )}
        {expanded && resultData && (
          <pre className="mt-1 text-xs text-gray-600 dark:text-gray-500 bg-gray-100 dark:bg-surface rounded p-2 overflow-auto max-h-40 border border-light-border dark:border-border">
            {(() => {
              try {
                return JSON.stringify(JSON.parse(resultData), null, 2);
              } catch {
                return resultData;
              }
            })()}
          </pre>
        )}
        {message.created_at && (
          <div className="mt-1 text-xs text-gray-500 dark:text-gray-600">
            {new Date(message.created_at).toLocaleTimeString(undefined, {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isWorkflow = isUser && message.content.startsWith(WORKFLOW_PREFIX);

  if (isWorkflow) {
    return <WorkflowBubble message={message} />;
  }

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? "bg-accent/20 text-accent" : "bg-green-500/20 text-green-400"
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Content */}
      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
          isUser
            ? "bg-accent/15 text-gray-800 dark:text-gray-200"
            : "bg-gray-100 dark:bg-surface-lighter text-gray-800 dark:text-gray-200"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose dark:prose-invert prose-sm max-w-none prose-pre:bg-gray-200 dark:prose-pre:bg-[#0d0e14] prose-pre:border prose-pre:border-light-border dark:prose-pre:border-border prose-code:text-accent dark:prose-code:text-accent-hover">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Tool calls metadata */}
        {!isUser && message.tool_calls_metadata && (
          <ToolCallsDisplay metadata={message.tool_calls_metadata} />
        )}

        {/* File attachments */}
        {message.files && message.files.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.files.map((file, i) => (
              <a
                key={i}
                href={file.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover"
              >
                <Download size={12} />
                {file.filename}
              </a>
            ))}
          </div>
        )}

        {/* Timestamp */}
        {message.created_at && (
          <div className="mt-1 text-xs text-gray-500 dark:text-gray-600">
            {new Date(message.created_at).toLocaleTimeString(undefined, {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
        )}
      </div>
    </div>
  );
}
