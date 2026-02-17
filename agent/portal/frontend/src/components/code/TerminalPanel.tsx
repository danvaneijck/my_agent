import { useState, useRef } from "react";
import { X, Minimize2, Maximize2, Terminal as TerminalIcon, Plus, Upload } from "lucide-react";
import TerminalView from "./TerminalView";
import { api } from "@/api/client";

interface TerminalTab {
  id: string;
  sessionId: string;
  label: string;
}

interface TerminalPanelProps {
  taskId: string;
  onClose: () => void;
  initialHeight?: number;
}

const MAX_TERMINALS = 5;

export default function TerminalPanel({
  taskId,
  onClose,
  initialHeight = 400,
}: TerminalPanelProps) {
  const [isMaximized, setIsMaximized] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  // Initialize with one terminal tab
  const [tabs, setTabs] = useState<TerminalTab[]>([
    {
      id: crypto.randomUUID(),
      sessionId: crypto.randomUUID(),
      label: "Terminal 1",
    },
  ]);
  const [activeTabId, setActiveTabId] = useState(tabs[0].id);

  const handleToggleMaximize = () => {
    setIsMaximized(!isMaximized);
  };

  const handleAddTerminal = () => {
    if (tabs.length >= MAX_TERMINALS) {
      return; // Max terminals reached
    }

    const newTab: TerminalTab = {
      id: crypto.randomUUID(),
      sessionId: crypto.randomUUID(),
      label: `Terminal ${tabs.length + 1}`,
    };

    setTabs([...tabs, newTab]);
    setActiveTabId(newTab.id);
  };

  const handleCloseTab = (tabId: string) => {
    if (tabs.length === 1) {
      // If this is the last tab, close the entire terminal panel
      onClose();
      return;
    }

    const newTabs = tabs.filter((t) => t.id !== tabId);
    setTabs(newTabs);

    // If we closed the active tab, switch to the first remaining tab
    if (activeTabId === tabId) {
      setActiveTabId(newTabs[0].id);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      // Upload file to workspace
      const formData = new FormData();
      formData.append("file", file);

      await api(`/api/tasks/${taskId}/workspace/upload`, {
        method: "POST",
        body: formData,
      });

      // Clear the input so the same file can be uploaded again if needed
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      // TODO: Optionally inject an 'ls' command into the terminal to show the uploaded file
      console.log(`File ${file.name} uploaded successfully`);
    } catch (error) {
      console.error("File upload failed:", error);
    } finally {
      setUploading(false);
    }
  };

  const activeTab = tabs.find((t) => t.id === activeTabId);

  return (
    <div
      className={`flex flex-col bg-surface border-t border-border ${
        isMaximized ? "fixed inset-0 z-50" : ""
      }`}
      style={!isMaximized ? { height: `${initialHeight}px` } : undefined}
    >
      {/* Header with tabs */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-light border-b border-border shrink-0">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <TerminalIcon size={14} className="text-accent shrink-0" />

          {/* Terminal tabs */}
          <div className="flex items-center gap-1 flex-1 min-w-0 overflow-x-auto">
            {tabs.map((tab) => (
              <div
                key={tab.id}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors shrink-0 ${
                  activeTabId === tab.id
                    ? "bg-surface text-white"
                    : "text-gray-400 hover:text-white hover:bg-surface/50"
                }`}
              >
                <button
                  onClick={() => setActiveTabId(tab.id)}
                  className="font-medium"
                >
                  {tab.label}
                </button>
                <button
                  onClick={() => handleCloseTab(tab.id)}
                  className="hover:text-red-400 transition-colors"
                  title="Close tab"
                >
                  <X size={12} />
                </button>
              </div>
            ))}

            {/* Add terminal button */}
            {tabs.length < MAX_TERMINALS && (
              <button
                onClick={handleAddTerminal}
                className="p-1 rounded hover:bg-surface text-gray-400 hover:text-white transition-colors shrink-0"
                title={`Add terminal (${tabs.length}/${MAX_TERMINALS})`}
              >
                <Plus size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0 ml-2">
          <button
            onClick={handleUploadClick}
            disabled={uploading}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-white transition-colors disabled:opacity-50"
            title="Upload file to workspace"
          >
            <Upload size={14} className={uploading ? "animate-pulse" : ""} />
          </button>
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

      {/* Terminal content - only render active tab */}
      <div className="flex-1 overflow-hidden">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className={`h-full ${activeTabId === tab.id ? "block" : "hidden"}`}
          >
            <TerminalView
              taskId={taskId}
              sessionId={tab.sessionId}
              onClose={() => handleCloseTab(tab.id)}
            />
          </div>
        ))}
      </div>

      {/* Resize hint (only when not maximized) */}
      {!isMaximized && (
        <div className="h-1 bg-border hover:bg-accent cursor-ns-resize transition-colors" />
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleFileUpload}
        className="hidden"
      />
    </div>
  );
}
