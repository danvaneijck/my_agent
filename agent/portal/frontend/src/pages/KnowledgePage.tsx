import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, Plus, Search, Trash2, X, Sparkles, MessageSquare } from "lucide-react";
import {
  useKnowledge,
  rememberFact,
  recallMemories,
  forgetMemory,
} from "@/hooks/useKnowledge";
import EmptyState from "@/components/common/EmptyState";
import {
  pageVariants,
  staggerContainerVariants,
  staggerItemVariants,
  listItemVariants,
} from "@/utils/animations";
import type { Memory } from "@/types";

// ── Helpers ────────────────────────────────────────────────────────

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHrs = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHrs / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHrs < 24) return `${diffHrs}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// ── Add Memory Modal ───────────────────────────────────────────────

interface AddMemoryModalProps {
  onClose: () => void;
  onSave: (content: string) => Promise<void>;
}

function AddMemoryModal({ onClose, onSave }: AddMemoryModalProps) {
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const trimmed = content.trim();
    if (!trimmed) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(trimmed);
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save memory");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div
        className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl shadow-2xl w-full max-w-lg"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.2 }}
      >
        <div className="flex items-center justify-between p-5 border-b border-light-border dark:border-border">
          <div className="flex items-center gap-2">
            <Brain size={18} className="text-accent" />
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">
              Add Memory
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              What should I remember?
            </label>
            <textarea
              className="w-full h-32 px-3 py-2 text-sm bg-gray-50 dark:bg-surface-lighter border border-light-border dark:border-border rounded-lg text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent resize-none"
              placeholder="e.g. My preferred coding language is TypeScript. My timezone is UTC+10."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              autoFocus
            />
            <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
              Facts stored here are used by the AI when answering your questions.
            </p>
          </div>

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </div>

        <div className="flex justify-end gap-2 px-5 pb-5">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!content.trim() || saving}
            className="px-4 py-2 text-sm font-medium bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Save Memory"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Confirm Delete Dialog ──────────────────────────────────────────

interface ConfirmDeleteProps {
  memory: Memory;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}

function ConfirmDeleteDialog({ memory, onCancel, onConfirm }: ConfirmDeleteProps) {
  const [deleting, setDeleting] = useState(false);

  const handleConfirm = async () => {
    setDeleting(true);
    try {
      await onConfirm();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div
        className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl shadow-2xl w-full max-w-sm"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.2 }}
      >
        <div className="p-5 space-y-3">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">
            Delete memory?
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3">
            "{memory.content}"
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500">
            This action cannot be undone.
          </p>
        </div>
        <div className="flex justify-end gap-2 px-5 pb-5">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={deleting}
            className="px-4 py-2 text-sm font-medium bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Memory Card ────────────────────────────────────────────────────

interface MemoryCardProps {
  memory: Memory;
  onDelete: (memory: Memory) => void;
}

function MemoryCard({ memory, onDelete }: MemoryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isLong = memory.content.length > 200;

  return (
    <motion.div
      variants={listItemVariants}
      className="group bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 hover:border-accent/30 dark:hover:border-accent/30 transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          <div className="w-8 h-8 rounded-lg bg-accent/10 dark:bg-accent/20 flex items-center justify-center">
            <Brain size={14} className="text-accent" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <p className={`text-sm text-gray-800 dark:text-gray-200 leading-relaxed ${!expanded && isLong ? "line-clamp-3" : ""}`}>
            {memory.content}
          </p>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-xs text-accent hover:text-accent-hover transition-colors"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}

          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {formatRelativeTime(memory.created_at)}
            </span>
            {memory.conversation_id && (
              <span className="inline-flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
                <MessageSquare size={10} />
                from conversation
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => onDelete(memory)}
          className="flex-shrink-0 p-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
          aria-label="Delete memory"
          title="Delete memory"
        >
          <Trash2 size={15} />
        </button>
      </div>
    </motion.div>
  );
}

// ── Recall Panel ───────────────────────────────────────────────────

function RecallPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleRecall = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const data = await recallMemories(trimmed, 8);
      setResults(data.memories || []);
      setHasSearched(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Recall failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gradient-to-br from-accent/5 to-transparent dark:from-accent/10 dark:to-transparent border border-accent/20 dark:border-accent/30 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles size={15} className="text-accent" />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Semantic Recall
        </span>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          — find memories by meaning, not just keywords
        </span>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          className="flex-1 px-3 py-2 text-sm bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-lg text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
          placeholder="What do you want to recall? e.g. my programming preferences"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleRecall()}
        />
        <button
          onClick={handleRecall}
          disabled={!query.trim() || loading}
          className="px-4 py-2 text-sm font-medium bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
          ) : (
            <Sparkles size={14} />
          )}
          Recall
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {hasSearched && (
        <div className="space-y-2 pt-1">
          {results.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 py-2">
              No relevant memories found for that query.
            </p>
          ) : (
            <>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {results.length} relevant {results.length === 1 ? "memory" : "memories"} found
              </p>
              <div className="space-y-2">
                {results.map((m) => (
                  <div
                    key={m.memory_id}
                    className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-lg p-3"
                  >
                    <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                      {m.content}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {formatRelativeTime(m.created_at)}
                    </p>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────

export default function KnowledgePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [deletingMemory, setDeletingMemory] = useState<Memory | null>(null);
  const [showRecall, setShowRecall] = useState(false);

  const { memories, total, loading, error, refetch } = useKnowledge(searchQuery);

  const handleSaveMemory = async (content: string) => {
    await rememberFact(content);
    await refetch();
  };

  const handleDeleteMemory = async () => {
    if (!deletingMemory) return;
    await forgetMemory(deletingMemory.memory_id);
    setDeletingMemory(null);
    await refetch();
  };

  return (
    <motion.div
      className="p-4 md:p-6 max-w-4xl mx-auto space-y-6"
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <Brain size={22} className="text-accent" />
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">
              Knowledge Base
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {loading
              ? "Loading memories..."
              : `${total} ${total === 1 ? "memory" : "memories"} stored`}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => setShowRecall(!showRecall)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border transition-colors ${
              showRecall
                ? "bg-accent/10 border-accent/30 text-accent dark:text-accent-hover"
                : "border-light-border dark:border-border text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-surface-lighter"
            }`}
          >
            <Sparkles size={15} />
            Recall
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors"
          >
            <Plus size={15} />
            Add Memory
          </button>
        </div>
      </div>

      {/* Recall panel */}
      <AnimatePresence>
        {showRecall && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            <RecallPanel />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search bar */}
      <div className="relative">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"
        />
        <input
          type="text"
          className="w-full pl-9 pr-4 py-2.5 text-sm bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
          placeholder="Filter memories..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
            aria-label="Clear search"
          >
            <X size={15} />
          </button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 animate-pulse"
            >
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-lg bg-gray-200 dark:bg-surface-lighter flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 dark:bg-surface-lighter rounded w-3/4" />
                  <div className="h-4 bg-gray-200 dark:bg-surface-lighter rounded w-1/2" />
                  <div className="h-3 bg-gray-200 dark:bg-surface-lighter rounded w-1/4 mt-2" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-xl p-4">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          <button
            onClick={refetch}
            className="mt-2 text-sm text-red-600 dark:text-red-400 underline hover:no-underline"
          >
            Try again
          </button>
        </div>
      ) : memories.length === 0 ? (
        searchQuery ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <Search size={32} className="text-gray-300 dark:text-gray-600" />
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              No memories match "{searchQuery}"
            </p>
            <button
              onClick={() => setSearchQuery("")}
              className="text-sm text-accent hover:text-accent-hover transition-colors"
            >
              Clear filter
            </button>
          </div>
        ) : (
          <EmptyState
            icon={Brain}
            title="No memories yet"
            description="Store facts, preferences, and context that the AI should remember across conversations."
            action={{ label: "Add your first memory", onClick: () => setShowAddModal(true) }}
          />
        )
      ) : (
        <>
          {searchQuery && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Showing {memories.length} of {total} {total === 1 ? "memory" : "memories"}
            </p>
          )}
          <motion.div
            className="space-y-3"
            variants={staggerContainerVariants}
            initial="initial"
            animate="animate"
          >
            <AnimatePresence mode="popLayout">
              {memories.map((memory) => (
                <motion.div
                  key={memory.memory_id}
                  variants={staggerItemVariants}
                  layout
                  exit={{ opacity: 0, x: -20, transition: { duration: 0.2 } }}
                >
                  <MemoryCard
                    memory={memory}
                    onDelete={setDeletingMemory}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        </>
      )}

      {/* Modals */}
      <AnimatePresence>
        {showAddModal && (
          <AddMemoryModal
            onClose={() => setShowAddModal(false)}
            onSave={handleSaveMemory}
          />
        )}
        {deletingMemory && (
          <ConfirmDeleteDialog
            memory={deletingMemory}
            onCancel={() => setDeletingMemory(null)}
            onConfirm={handleDeleteMemory}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
