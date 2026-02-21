import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { X, MessageSquare } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Sidebar from "./Sidebar";
import Header from "./Header";
import BottomNav from "./BottomNav";
import SkipToContent from "@/components/common/SkipToContent";
import EnvironmentBadge from "@/components/common/EnvironmentBadge";
import DeploymentBanner from "@/components/common/DeploymentBanner";
import type { DeployRun } from "@/components/common/DeploymentBanner";
import { connectWs } from "@/api/websocket";
import { api } from "@/api/client";
import type { Conversation, WsNotification } from "@/types";

const PAGE_TITLES: Record<string, string> = {
  "/": "Home",
  "/tasks": "Tasks",
  "/chat": "Chat",
  "/files": "Files",
};

interface Toast {
  id: number;
  content: string;
  conversationId?: string | null;
}

let toastId = 0;

export default function Layout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [chatUnreadCount, setChatUnreadCount] = useState(0);
  const [openPrCount, setOpenPrCount] = useState(0);
  const [activeTaskCount, setActiveTaskCount] = useState(0);
  const [deployRun, setDeployRun] = useState<DeployRun | null>(null);
  const [dismissedRunId, setDismissedRunId] = useState<number | null>(null);
  const [openErrorCount, setOpenErrorCount] = useState(0);
  const location = useLocation();
  const navigate = useNavigate();

  const addToast = useCallback(
    (content: string, conversationId?: string | null) => {
      const id = ++toastId;
      setToasts((prev) => [...prev, { id, content, conversationId }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 15000);
    },
    []
  );

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Fetch initial unread count
  const fetchUnreadCount = useCallback(() => {
    api<{ conversations: Conversation[] }>("/api/chat/conversations")
      .then((data) => {
        const total = (data.conversations || []).reduce(
          (sum, c) => sum + (c.unread_count || 0),
          0
        );
        setChatUnreadCount(total);
      })
      .catch(() => { });
  }, []);

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Fetch open PR count
  const fetchPrCount = useCallback(() => {
    api<{ count: number }>("/api/repos/pulls/all")
      .then((data) => setOpenPrCount(data.count || 0))
      .catch(() => { });
  }, []);

  useEffect(() => {
    fetchPrCount();
    const interval = setInterval(fetchPrCount, 60000);
    return () => clearInterval(interval);
  }, [fetchPrCount]);

  // Fetch active task count (running + queued)
  const fetchActiveTaskCount = useCallback(() => {
    api<{ tasks: { status: string }[] }>("/api/tasks")
      .then((data) => {
        const count = (data.tasks || []).filter(
          (t) => t.status === "running" || t.status === "queued"
        ).length;
        setActiveTaskCount(count);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchActiveTaskCount();
    const interval = setInterval(fetchActiveTaskCount, 10000);
    return () => clearInterval(interval);
  }, [fetchActiveTaskCount]);

  // Poll deployment workflow status — shared server-side check, works for all users
  const fetchDeployStatus = useCallback(() => {
    api<{ active: boolean; run: DeployRun | null; configured: boolean }>(
      "/api/system/deploy-status"
    )
      .then((data) => setDeployRun(data.active ? data.run : null))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchDeployStatus();
    const interval = setInterval(fetchDeployStatus, 60_000);
    return () => clearInterval(interval);
  }, [fetchDeployStatus]);

  // Fetch open error count (admin-only; silently skips for non-admins)
  const fetchErrorCount = useCallback(() => {
    api<{ open: number }>("/api/errors/summary")
      .then((data) => setOpenErrorCount(data.open || 0))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchErrorCount();
    const interval = setInterval(fetchErrorCount, 60000);
    return () => clearInterval(interval);
  }, [fetchErrorCount]);

  // Re-fetch PR count when a PR is merged
  useEffect(() => {
    const handler = () => fetchPrCount();
    window.addEventListener("pr-count-update", handler);
    return () => window.removeEventListener("pr-count-update", handler);
  }, [fetchPrCount]);

  // Listen for unread count updates from ChatPage
  useEffect(() => {
    const handler = (e: Event) => {
      const count = (e as CustomEvent).detail?.count ?? 0;
      setChatUnreadCount(count);
    };
    window.addEventListener("chat-unread-update", handler);
    return () => window.removeEventListener("chat-unread-update", handler);
  }, []);

  // Connect to notification WebSocket
  useEffect(() => {
    const cleanup = connectWs("/ws/notifications", {
      onMessage: (data: unknown) => {
        const msg = data as WsNotification;
        if (msg.type === "notification" && msg.content) {
          addToast(msg.content, msg.conversation_id);

          // Dispatch event for ChatPage to handle
          window.dispatchEvent(
            new CustomEvent("chat-notification", {
              detail: {
                conversation_id: msg.conversation_id,
                content: msg.content,
              },
            })
          );

          // Refresh unread count
          fetchUnreadCount();
        }
      },
      reconnect: true,
    });
    return cleanup;
  }, [addToast, fetchUnreadCount]);

  const title =
    PAGE_TITLES[location.pathname] ||
    (location.pathname.startsWith("/tasks/") ? "Task Detail" : "Agent Portal");

  const showDeployBanner = deployRun !== null && deployRun.id !== dismissedRunId;

  return (
    <div className={`h-full flex${showDeployBanner ? " pt-9" : ""}`}>
      {showDeployBanner && (
        <DeploymentBanner
          run={deployRun!}
          onDismiss={() => setDismissedRunId(deployRun!.id)}
        />
      )}
      <SkipToContent />
      <EnvironmentBadge />
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        chatUnreadCount={chatUnreadCount}
        openPrCount={openPrCount}
        activeTaskCount={activeTaskCount}
        openErrorCount={openErrorCount}
        bannerVisible={showDeployBanner}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          title={title}
          onMenuToggle={() => setSidebarOpen(!sidebarOpen)}
        />
        <main id="main-content" className="flex-1 overflow-auto pb-16 md:pb-0" tabIndex={-1}>
          {children}
        </main>
      </div>
      <BottomNav
        onMenuOpen={() => setSidebarOpen(true)}
        activeTaskCount={activeTaskCount}
        chatUnreadCount={chatUnreadCount}
      />

      {/* Notification toasts */}
      {toasts.length > 0 && (
        <div className="fixed inset-x-0 top-16 z-50 flex flex-col items-center gap-2 pointer-events-none">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className="pointer-events-auto bg-white dark:bg-surface-light border border-accent/30 rounded-lg p-4 shadow-xl animate-in fade-in slide-in-from-top-2 max-w-lg w-full mx-4"
            >
              <div className="flex items-start gap-3">
                <div className="flex-1 text-sm text-gray-700 dark:text-gray-200 break-words max-h-60 overflow-y-auto prose dark:prose-invert prose-sm prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-1 prose-pre:my-1 prose-pre:bg-gray-100 dark:prose-pre:bg-black/30 prose-code:text-accent dark:prose-code:text-accent-hover max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {toast.content}
                  </ReactMarkdown>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {toast.conversationId && (
                    <button
                      onClick={() => {
                        navigate(`/chat/${toast.conversationId}`);
                        dismissToast(toast.id);
                      }}
                      className="p-2 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-accent hover:text-accent-hover focus:outline-none focus:ring-2 focus:ring-accent"
                      title="View in chat"
                      aria-label="View in chat"
                    >
                      <MessageSquare size={16} />
                    </button>
                  )}
                  <button
                    onClick={() => dismissToast(toast.id)}
                    className="p-2 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-accent"
                    aria-label="Dismiss notification"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
