import { FileText, Image, FileCode, File as FileIcon, Trash2 } from "lucide-react";
import type { FileInfo } from "@/types";

function getFileIcon(mime: string | null) {
  if (!mime) return FileIcon;
  if (mime.startsWith("image/")) return Image;
  if (mime.includes("text") || mime.includes("json") || mime.includes("xml")) return FileText;
  if (mime.includes("javascript") || mime.includes("python") || mime.includes("html")) return FileCode;
  return FileIcon;
}

function formatSize(bytes: number | null): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileListProps {
  files: FileInfo[];
  onSelect: (file: FileInfo) => void;
  onDelete: (file: FileInfo) => void;
  selectedId?: string;
}

export default function FileList({ files, onSelect, onDelete, selectedId }: FileListProps) {
  if (files.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No files yet. Upload one to get started.
      </div>
    );
  }

  return (
    <div className="divide-y divide-border/50">
      {files.map((file) => {
        const Icon = getFileIcon(file.mime_type);
        return (
          <div
            key={file.file_id}
            onClick={() => onSelect(file)}
            className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-lighter ${
              selectedId === file.file_id ? "bg-accent/10" : ""
            }`}
          >
            <Icon size={18} className="text-gray-500 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-200 truncate">{file.filename}</p>
              <p className="text-xs text-gray-500">
                {formatSize(file.size_bytes)} &middot;{" "}
                {new Date(file.created_at).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(file);
              }}
              className="p-1.5 rounded hover:bg-red-600/20 text-gray-500 hover:text-red-400 transition-colors shrink-0"
            >
              <Trash2 size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
