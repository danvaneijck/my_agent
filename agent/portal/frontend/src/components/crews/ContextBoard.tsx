import { useState } from "react";
import { Send } from "lucide-react";
import { motion } from "framer-motion";
import { streamEntryVariants } from "@/utils/animations";
import type { CrewContextEntry } from "@/types";

const TYPE_COLORS: Record<string, string> = {
  decision: "bg-purple-500/20 text-purple-400",
  api_contract: "bg-blue-500/20 text-blue-400",
  interface: "bg-cyan-500/20 text-cyan-400",
  note: "bg-gray-500/20 text-gray-400",
  blocker: "bg-red-500/20 text-red-400",
  merge_result: "bg-green-500/20 text-green-400",
};

interface ContextBoardProps {
  entries: CrewContextEntry[];
  onPost?: (entry: { entry_type: string; title: string; content: string }) => Promise<void>;
  readOnly?: boolean;
}

export default function ContextBoard({ entries, onPost, readOnly }: ContextBoardProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [entryType, setEntryType] = useState("note");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim() || !onPost) return;
    setSubmitting(true);
    try {
      await onPost({ entry_type: entryType, title: title.trim(), content: content.trim() });
      setTitle("");
      setContent("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Entries feed */}
      <div className="flex-1 overflow-y-auto space-y-3 p-1">
        {entries.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
            No context entries yet
          </div>
        ) : (
          entries.map((entry) => {
            const typeClass = TYPE_COLORS[entry.entry_type] || TYPE_COLORS.note;
            const time = new Date(entry.created_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            });

            return (
              <motion.div
                key={entry.id}
                variants={streamEntryVariants}
                initial="initial"
                animate="animate"
                className="bg-white dark:bg-surface border border-light-border dark:border-border rounded-lg p-3"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${typeClass}`}>
                    {entry.entry_type.replace("_", " ")}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">{time}</span>
                </div>
                <p className="text-sm font-medium text-gray-900 dark:text-white mb-1">
                  {entry.title}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                  {entry.content}
                </p>
              </motion.div>
            );
          })
        )}
      </div>

      {/* Post form */}
      {!readOnly && onPost && (
        <div className="border-t border-light-border dark:border-border pt-3 mt-3 space-y-2">
          <div className="flex gap-2">
            <select
              value={entryType}
              onChange={(e) => setEntryType(e.target.value)}
              className="bg-white dark:bg-surface border border-light-border dark:border-border rounded-lg px-2 py-1.5 text-xs text-gray-700 dark:text-gray-300 focus:outline-none focus:border-accent"
            >
              <option value="note">Note</option>
              <option value="decision">Decision</option>
              <option value="api_contract">API Contract</option>
              <option value="interface">Interface</option>
              <option value="blocker">Blocker</option>
            </select>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title"
              className="flex-1 px-2 py-1.5 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
            />
          </div>
          <div className="flex gap-2">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Context content..."
              rows={2}
              className="flex-1 px-2 py-1.5 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
            />
            <button
              onClick={handleSubmit}
              disabled={submitting || !title.trim() || !content.trim()}
              className="self-end p-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
