import { useState, useRef } from "react";
import { Upload, X } from "lucide-react";
import { api } from "@/api/client";

interface FileUploadProps {
  onUploaded: () => void;
}

export default function FileUpload({ onUploaded }: FileUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const uploadFiles = async (fileList: FileList) => {
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(fileList)) {
        const form = new FormData();
        form.append("file", file);
        await api("/api/files", { method: "POST", body: form });
      }
      onUploaded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length > 0) {
          uploadFiles(e.dataTransfer.files);
        }
      }}
      className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
        dragging
          ? "border-accent bg-accent/10"
          : "border-border hover:border-border-light"
      }`}
    >
      <Upload size={24} className="mx-auto mb-2 text-gray-500" />
      <p className="text-sm text-gray-400">
        {uploading ? "Uploading..." : "Drag & drop files here or"}
      </p>
      {!uploading && (
        <button
          onClick={() => fileRef.current?.click()}
          className="mt-2 px-4 py-1.5 rounded-lg bg-surface-lighter text-sm text-gray-300 hover:bg-border transition-colors"
        >
          Browse Files
        </button>
      )}
      <input
        ref={fileRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            uploadFiles(e.target.files);
          }
          e.target.value = "";
        }}
      />
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
    </div>
  );
}
