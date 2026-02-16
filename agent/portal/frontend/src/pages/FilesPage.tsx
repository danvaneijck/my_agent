import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { RefreshCw, Search } from "lucide-react";
import { api } from "@/api/client";
import { usePageTitle } from "@/hooks/usePageTitle";
import FileList from "@/components/files/FileList";
import FileUpload from "@/components/files/FileUpload";
import FilePreview from "@/components/files/FilePreview";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import type { FileInfo } from "@/types";

export default function FilesPage() {
  usePageTitle("Files");
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<FileInfo | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FileInfo | null>(null);

  const fetchFiles = useCallback(async () => {
    try {
      const data = await api<{ files: FileInfo[] }>("/api/files");
      setFiles(data.files || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api(`/api/files/${deleteTarget.file_id}`, { method: "DELETE" });
      if (selected?.file_id === deleteTarget.file_id) setSelected(null);
      fetchFiles();
    } catch {
      // ignore
    }
    setDeleteTarget(null);
  };

  const filtered = search
    ? files.filter((f) =>
        f.filename.toLowerCase().includes(search.toLowerCase())
      )
    : files;

  return (
    <motion.div
      className="flex flex-col md:flex-row h-full"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {/* File list panel */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-border">
        <div className="p-4 space-y-3 shrink-0">
          {/* Search + refresh */}
          <div className="flex items-center gap-3">
            <div className="flex-1 relative">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search files..."
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
              />
            </div>
            <button
              onClick={fetchFiles}
              className="p-2 rounded-lg hover:bg-surface-lighter text-gray-400"
              title="Refresh"
            >
              <RefreshCw size={16} />
            </button>
          </div>

          {/* Upload */}
          <FileUpload onUploaded={fetchFiles} />
        </div>

        {/* Files */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <FileList
              files={filtered}
              selectedId={selected?.file_id}
              onSelect={setSelected}
              onDelete={setDeleteTarget}
            />
          )}
        </div>
      </div>

      {/* Preview panel (desktop only, or as overlay on mobile) */}
      {selected && (
        <div className="md:w-96 shrink-0 p-4 overflow-auto">
          <FilePreview file={selected} onClose={() => setSelected(null)} />
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete File"
        message={`Delete "${deleteTarget?.filename}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </motion.div>
  );
}
