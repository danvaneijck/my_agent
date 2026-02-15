import { useState } from "react";
import { Wrench, ChevronDown, ChevronRight, CheckCircle2, XCircle } from "lucide-react";
import type { ToolCallsMetadata } from "@/types";

interface ToolCallsDisplayProps {
  metadata: ToolCallsMetadata;
}

export default function ToolCallsDisplay({ metadata }: ToolCallsDisplayProps) {
  const [expanded, setExpanded] = useState(false);

  if (!metadata || metadata.total_count === 0) {
    return null;
  }

  return (
    <div className="mt-3 pt-3 border-t border-border/50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors w-full"
      >
        <Wrench size={14} className="text-accent" />
        <span>
          Used {metadata.total_count} tool{metadata.total_count !== 1 ? "s" : ""}
          {metadata.unique_tools !== metadata.total_count && (
            <span className="text-gray-600"> ({metadata.unique_tools} unique)</span>
          )}
        </span>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>

      {expanded && (
        <div className="mt-2 space-y-1">
          {metadata.tools_sequence.map((tool, idx) => (
            <div
              key={tool.tool_use_id}
              className="flex items-center gap-2 text-xs text-gray-400 pl-6"
            >
              <span className="text-gray-600 font-mono">{idx + 1}.</span>
              <span className="font-mono text-gray-300">{tool.name}</span>
              {tool.success ? (
                <CheckCircle2 size={12} className="text-green-400" />
              ) : (
                <XCircle size={12} className="text-red-400" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
