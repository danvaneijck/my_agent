import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { usePageTitle } from "@/hooks/usePageTitle";
import {
  Plus,
  MessageSquare,
  MoreVertical,
  Pencil,
  Trash2,
  Check,
  X,
} from "lucide-react";
import { api } from "@/api/client";
import ChatView, { getPendingConversations } from "@/components/chat/ChatView";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import type { Conversation } from "@/types";

export default function ChatPage() {
  usePageTitle("Chat");
  const { conversationId } = useParams<{ conversationId: string }>();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set(getPendingConversations()));
  const menuRef = useRef<HTMLDivElement>(null);

  const fetchConversations = useCallback(() => {
    api<{ conversations: Conversation[] }>("/api/chat/conversations")
      .then((data) => setConversations(data.conversations || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Mark conversation as read when opened
  useEffect(() => {
    if (conversationId) {
      api(`/api/chat/conversations/${conversationId}/read`, {
        method: "POST",
      }).catch(() => {});
      // Update local state immediately
      setConversations((prev) =>
        prev.map((c) =>
          c.id === conversationId ? { ...c, unread_count: 0 } : c
        )
      );
    }
  }, [conversationId]);

  // Listen for notification events to refresh conversations
  useEffect(() => {
    const handler = async (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.conversation_id && detail.conversation_id === conversationId) {
        // User is viewing this conversation — mark as read before refreshing
        // so the refreshed list won't briefly show an unread badge
        await api(`/api/chat/conversations/${conversationId}/read`, {
          method: "POST",
        }).catch(() => {});
      }
      fetchConversations();
    };
    window.addEventListener("chat-notification", handler);
    return () => window.removeEventListener("chat-notification", handler);
  }, [conversationId, fetchConversations]);

  // Close menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    };
    if (menuOpenId) {
      document.addEventListener("mousedown", handler);
      return () => document.removeEventListener("mousedown", handler);
    }
  }, [menuOpenId]);

  const startNew = () => {
    navigate("/chat");
  };

  const handleRename = async (convId: string) => {
    if (!renameValue.trim()) return;
    await api(`/api/chat/conversations/${convId}`, {
      method: "PATCH",
      body: JSON.stringify({ title: renameValue.trim() }),
    }).catch(() => {});
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId ? { ...c, title: renameValue.trim() } : c
      )
    );
    setRenamingId(null);
  };

  const handleDelete = async (convId: string) => {
    await api(`/api/chat/conversations/${convId}`, {
      method: "DELETE",
    }).catch(() => {});
    setConversations((prev) => prev.filter((c) => c.id !== convId));
    setDeleteConfirm(null);
    if (conversationId === convId) {
      navigate("/chat");
    }
  };

  const handleConversationCreated = (id: string) => {
    // Move pending from __new__ to the real conversation ID
    setPendingIds((prev) => {
      const next = new Set(prev);
      next.delete("__new__");
      next.add(id);
      return next;
    });
    navigate(`/chat/${id}`, { replace: true });
    // Refresh conversations list after a short delay to pick up the new conversation + auto-generated title
    setTimeout(fetchConversations, 2000);
  };

  const handleWaitingChange = useCallback((convId: string, waiting: boolean) => {
    setPendingIds((prev) => {
      const next = new Set(prev);
      if (waiting) {
        next.add(convId);
      } else {
        next.delete(convId);
      }
      return next;
    });
  }, []);

  const totalUnread = conversations.reduce((sum, c) => sum + (c.unread_count || 0), 0);

  // Expose total unread for Layout to pick up
  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent("chat-unread-update", { detail: { count: totalUnread } })
    );
  }, [totalUnread]);

  return (
    <div className="flex h-full">
      {/* Conversation sidebar */}
      <div
        className={`
          ${showHistory ? "block" : "hidden"} md:block
          w-full md:w-64 border-r border-light-border dark:border-border bg-light-surface-secondary dark:bg-surface-light shrink-0
          absolute md:static inset-0 z-20 md:z-auto
        `}
      >
        <div className="p-3 border-b border-light-border dark:border-border flex items-center justify-between">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Conversations</span>
          <button
            onClick={startNew}
            className="p-1.5 rounded hover:bg-light-surface-tertiary dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
            title="New conversation"
          >
            <Plus size={16} />
          </button>
        </div>
        <div className="overflow-auto max-h-[calc(100%-3.5rem)]">
          {/* New chat option */}
          <button
            onClick={() => {
              navigate("/chat");
              setShowHistory(false);
            }}
            className={`w-full text-left px-3 py-3 text-sm border-b border-light-border dark:border-border/50 hover:bg-light-surface-tertiary dark:hover:bg-surface-lighter transition-colors ${
              !conversationId ? "bg-accent/10 text-accent dark:text-accent-hover" : "text-gray-700 dark:text-gray-400"
            }`}
          >
            New Chat
          </button>

          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`relative group border-b border-light-border dark:border-border/50 ${
                conversationId === conv.id
                  ? "bg-accent/10"
                  : "hover:bg-light-surface-tertiary dark:hover:bg-surface-lighter"
              }`}
            >
              {renamingId === conv.id ? (
                /* Inline rename */
                <div className="px-3 py-2 flex items-center gap-1">
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleRename(conv.id);
                      if (e.key === "Escape") setRenamingId(null);
                    }}
                    autoFocus
                    className="flex-1 bg-white dark:bg-surface text-sm text-gray-900 dark:text-gray-200 px-2 py-1 rounded border border-light-border dark:border-border focus:border-accent focus:ring-2 focus:ring-accent/50 outline-none min-w-0"
                    aria-label="Rename conversation"
                  />
                  <button
                    onClick={() => handleRename(conv.id)}
                    className="p-1.5 rounded hover:bg-light-surface-tertiary dark:hover:bg-surface-lighter text-green-600 dark:text-green-400 focus:outline-none focus:ring-2 focus:ring-accent"
                    aria-label="Confirm rename"
                  >
                    <Check size={16} />
                  </button>
                  <button
                    onClick={() => setRenamingId(null)}
                    className="p-1.5 rounded hover:bg-light-surface-tertiary dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400 focus:outline-none focus:ring-2 focus:ring-accent"
                    aria-label="Cancel rename"
                  >
                    <X size={16} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    navigate(`/chat/${conv.id}`);
                    setShowHistory(false);
                  }}
                  className="w-full text-left px-3 py-3 text-sm transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`truncate flex-1 ${
                        conversationId === conv.id
                          ? "text-accent dark:text-accent-hover"
                          : "text-gray-700 dark:text-gray-300"
                      }`}
                    >
                      {conv.title || "Untitled conversation"}
                    </span>
                    {pendingIds.has(conv.id) ? (
                      <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin shrink-0" />
                    ) : conv.unread_count > 0 ? (
                      <span className="bg-accent text-white text-xs font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 shrink-0">
                        {conv.unread_count}
                      </span>
                    ) : null}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-600 mt-0.5">
                    {conv.last_active_at
                      ? new Date(conv.last_active_at).toLocaleDateString()
                      : ""}
                  </div>
                </button>
              )}

              {/* Context menu trigger */}
              {renamingId !== conv.id && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpenId(menuOpenId === conv.id ? null : conv.id);
                  }}
                  className="absolute right-2 top-2 p-1 rounded hover:bg-light-surface-tertiary dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-500 hover:text-gray-900 dark:hover:text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <MoreVertical size={14} />
                </button>
              )}

              {/* Context menu dropdown */}
              {menuOpenId === conv.id && (
                <div
                  ref={menuRef}
                  className="absolute right-2 top-8 z-30 bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-lg shadow-xl py-1 min-w-[120px]"
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setRenameValue(conv.title || "");
                      setRenamingId(conv.id);
                      setMenuOpenId(null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-surface-lighter flex items-center gap-2"
                  >
                    <Pencil size={13} />
                    Rename
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirm(conv.id);
                      setMenuOpenId(null);
                    }}
                    className="w-full text-left px-3 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-surface-lighter flex items-center gap-2"
                  >
                    <Trash2 size={13} />
                    Delete
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile toggle */}
        <div className="md:hidden flex items-center gap-2 px-3 py-2 border-b border-light-border dark:border-border">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400"
          >
            <MessageSquare size={16} />
          </button>
          <span className="text-xs text-gray-600 dark:text-gray-500 truncate">
            {conversationId
              ? conversations.find((c) => c.id === conversationId)?.title ||
                "Conversation"
              : "New Chat"}
          </span>
        </div>

        <div className="flex-1 min-h-0">
          <ChatView
            conversationId={conversationId || null}
            onConversationCreated={handleConversationCreated}
            onWaitingChange={handleWaitingChange}
          />
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete conversation"
        message="This will permanently delete this conversation and all its messages. This action cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => deleteConfirm && handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </div>
  );
}
