import { useState } from "react";
import { X, Minimize2, Maximize2, Terminal as TerminalIcon } from "lucide-react";
import TerminalView from "./TerminalView";

interface TerminalPanelProps {
  taskId: string;
  onClose: () => void;
  initialHeight?: number;
}

export default function TerminalPanel({
  taskId,
  onClose,
  initialHeight = 400,
}: TerminalPanelProps) {
  const [isMaximized, setIsMaximized] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "connected" | "disconnected"
  >("connecting");

  const handleToggleMaximize = () => {
    setIsMaximized(!isMaximized);
  };

  return (
    <div
      className={`flex flex-col bg-surface border-t border-border ${
        isMaximized ? "fixed inset-0 z-50" : ""
      }`}
      style={!isMaximized ? { height: `${initialHeight}px` } : undefined}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-light border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <TerminalIcon size={14} className="text-accent" />
          <span className="text-xs font-medium text-white">Terminal</span>
          <span className="text-xs text-gray-500">•</span>
          <span className="text-xs text-gray-500 font-mono">{taskId.slice(0, 8)}</span>
          <div className="flex items-center gap-1.5 ml-2">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                connectionStatus === "connected"
                  ? "bg-green-500"
                  : connectionStatus === "connecting"
                  ? "bg-yellow-500 animate-pulse"
                  : "bg-red-500"
              }`}
            />
            <span className="text-[10px] text-gray-500 capitalize">
              {connectionStatus}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={handleToggleMaximize}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-white transition-colors"
            title={isMaximized ? "Restore" : "Maximize"}
          >
            {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-white transition-colors"
            title="Close terminal"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Terminal content */}
      <div className="flex-1 overflow-hidden">
        <TerminalView taskId={taskId} onClose={onClose} />
      </div>

      {/* Resize hint (only when not maximized) */}
      {!isMaximized && (
        <div className="h-1 bg-border hover:bg-accent cursor-ns-resize transition-colors" />
      )}
    </div>
  );
}
