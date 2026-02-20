import { useState, useEffect } from "react";
import { Download, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { api, apiFetchBlobUrl, apiDownloadFile } from "@/api/client";
import type { FileInfo } from "@/types";

interface FilePreviewProps {
  file: FileInfo;
  onClose: () => void;
}

export default function FilePreview({ file, onClose }: FilePreviewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const isImage = file.mime_type?.startsWith("image/");
  const isMarkdown =
    file.filename.endsWith(".md") || file.mime_type === "text/markdown";
  const isText =
    file.mime_type?.startsWith("text/") ||
    file.mime_type?.includes("json") ||
    file.mime_type?.includes("xml") ||
    file.mime_type?.includes("javascript") ||
    file.mime_type?.includes("python") ||
    file.mime_type?.includes("yaml") ||
    file.mime_type?.includes("toml");

  // Load image as authenticated blob URL
  useEffect(() => {
    if (!isImage) return;
    let revoked = false;
    setLoading(true);
    apiFetchBlobUrl(`/api/files/${file.file_id}/download?inline=1`)
      .then((url) => {
        if (!revoked) setBlobUrl(url);
        else URL.revokeObjectURL(url);
      })
      .catch(() => setBlobUrl(null))
      .finally(() => setLoading(false));
    return () => {
      revoked = true;
      setBlobUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [file.file_id, isImage]);

  // Load text/markdown content
  useEffect(() => {
    if (!isText && !isMarkdown) return;
    setLoading(true);
    api<{ content?: string }>(`/api/files/${file.file_id}`)
      .then((data) => setContent(data.content || null))
      .catch(() => setContent(null))
      .finally(() => setLoading(false));
  }, [file.file_id, isText, isMarkdown]);

  const handleDownload = () => apiDownloadFile(file.file_id, file.filename);

  return (
    <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-light-border dark:border-border">
        <h3 className="text-sm font-medium text-gray-900 dark:text-white truncate">{file.filename}</h3>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleDownload}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            title="Download"
          >
            <Download size={16} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 max-h-[36rem] overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : isImage && blobUrl ? (
          <img
            src={blobUrl}
            alt={file.filename}
            className="max-w-full h-auto rounded"
          />
        ) : isMarkdown && content ? (
          <div className="prose dark:prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {content}
            </ReactMarkdown>
          </div>
        ) : isText && content ? (
          <pre className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono log-viewer">
            {content}
          </pre>
        ) : isImage ? (
          <div className="text-gray-500 text-sm">Unable to load image.</div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <p className="text-sm">Preview not available for this file type.</p>
            <button
              onClick={handleDownload}
              className="inline-flex items-center gap-1.5 mt-3 text-sm text-accent hover:text-accent-hover"
            >
              <Download size={14} />
              Download file
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
