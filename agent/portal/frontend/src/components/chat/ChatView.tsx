import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import { useWebSocket } from "@/hooks/useWebSocket";
import { api } from "@/api/client";
import type { ChatMessage, WsChatMessage } from "@/types";

// Module-level store — survives component remounts during navigation
const pendingConversations = new Set<string>();
export function getPendingConversations(): ReadonlySet<string> {
  return pendingConversations;
}

interface ChatViewProps {
  conversationId: string | null;
  onConversationCreated?: (id: string) => void;
  onWaitingChange?: (conversationId: string, waiting: boolean) => void;
}

export default function ChatView({ conversationId, onConversationCreated, onWaitingChange }: ChatViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [waiting, setWaiting] = useState(false);
  const [activeConversation, setActiveConversation] = useState(conversationId);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const justCreatedRef = useRef<string | null>(null);

  const { lastMessage, send, connected } = useWebSocket("/ws/chat");

  // Load existing messages when conversation changes
  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setWaiting(false);
      return;
    }
    // Skip fetch if we just created this conversation — messages are already in state
    if (justCreatedRef.current === conversationId) {
      justCreatedRef.current = null;
      setActiveConversation(conversationId);
      return;
    }
    setActiveConversation(conversationId);

    // Restore pending state if this conversation was waiting
    if (pendingConversations.has(conversationId)) {
      setWaiting(true);
    }

    api<{ messages: ChatMessage[] }>(
      `/api/chat/conversations/${conversationId}/messages`
    )
      .then((data) => {
        const msgs = data.messages || [];
        setMessages(msgs);
        // If the last message is from assistant, the response arrived while we were away
        if (msgs.length > 0 && msgs[msgs.length - 1].role === "assistant") {
          pendingConversations.delete(conversationId);
          setWaiting(false);
          onWaitingChange?.(conversationId, false);
        }
      })
      .catch(() => {});
  }, [conversationId]);

  // Handle WebSocket responses
  useEffect(() => {
    if (!lastMessage) return;
    const msg = lastMessage as WsChatMessage;

    if (msg.type === "response") {
      setWaiting(false);
      const convId = msg.conversation_id || activeConversation;
      if (convId) {
        pendingConversations.delete(convId);
        onWaitingChange?.(convId, false);
      }
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: msg.content,
        created_at: new Date().toISOString(),
        files: msg.files,
        tool_calls_metadata: msg.tool_calls_metadata,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (!activeConversation && msg.conversation_id) {
        justCreatedRef.current = msg.conversation_id;
        setActiveConversation(msg.conversation_id);
        onConversationCreated?.(msg.conversation_id);
      }
    } else if (msg.type === "error") {
      setWaiting(false);
      const convId = activeConversation;
      if (convId) {
        pendingConversations.delete(convId);
        onWaitingChange?.(convId, false);
      }
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Error: ${msg.message}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  }, [lastMessage]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (content: string) => {
    if (!content) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setWaiting(true);

    // Track pending state so it persists across navigation
    const convId = activeConversation || "__new__";
    pendingConversations.add(convId);
    onWaitingChange?.(convId, true);

    send({
      type: "message",
      content,
      conversation_id: activeConversation,
    });
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-600 mt-12">
            Start a conversation with your agent.
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {waiting && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center shrink-0">
              <div className="w-4 h-4 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
            </div>
            <div className="bg-gray-100 dark:bg-surface-lighter rounded-xl px-4 py-3 text-sm text-gray-500 dark:text-gray-500">
              Thinking...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={waiting || !connected} />

      {/* Connection status */}
      {!connected && (
        <div className="text-center py-1 text-xs text-yellow-500 bg-yellow-500/10">
          Reconnecting...
        </div>
      )}
    </div>
  );
}
