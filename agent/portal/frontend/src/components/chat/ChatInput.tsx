import { useState, useRef } from "react";
import { Send, Paperclip, X } from "lucide-react";

interface ChatInputProps {
  onSend: (content: string, files?: File[]) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() && files.length === 0) return;
    onSend(text.trim(), files.length > 0 ? files : undefined);
    setText("");
    setFiles([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-light-border dark:border-border p-3 bg-white dark:bg-surface-light">
      {/* Attached files */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {files.map((file, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-100 dark:bg-surface-lighter text-xs text-gray-700 dark:text-gray-300"
            >
              {file.name}
              <button
                type="button"
                onClick={() => removeFile(i)}
                className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors shrink-0"
          title="Attach file"
        >
          <Paperclip size={18} />
        </button>
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) {
              setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
            }
            e.target.value = "";
          }}
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          rows={1}
          disabled={disabled}
          className="flex-1 px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent resize-none max-h-32 disabled:opacity-50"
          style={{ minHeight: "2.5rem" }}
        />
        <button
          type="submit"
          disabled={disabled || (!text.trim() && files.length === 0)}
          className="p-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 shrink-0"
        >
          <Send size={18} />
        </button>
      </div>
    </form>
  );
}
