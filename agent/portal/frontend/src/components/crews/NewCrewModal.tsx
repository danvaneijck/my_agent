import { useState, useEffect, useRef } from "react";
import { X, Users } from "lucide-react";
import { api } from "@/api/client";
import { createCrewSession } from "@/hooks/useCrews";
import type { ProjectSummary } from "@/types";

interface NewCrewModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (sessionId: string) => void;
  initialProjectId?: string;
}

export default function NewCrewModal({ open, onClose, onCreated, initialProjectId }: NewCrewModalProps) {
  const [name, setName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [maxAgents, setMaxAgents] = useState(4);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);

  // Load projects for picker
  useEffect(() => {
    if (open) {
      api<ProjectSummary[]>("/api/projects")
        .then((data) => {
          setProjects(data || []);
          // Auto-fill name from pre-selected project
          if (initialProjectId) {
            const match = (data || []).find((p) => p.project_id === initialProjectId);
            if (match && !name) {
              setName(`Crew: ${match.name}`);
            }
          }
        })
        .catch(() => {});
    }
  }, [open, initialProjectId]);

  // Reset on open
  useEffect(() => {
    if (open) {
      setName("");
      setProjectId(initialProjectId || "");
      setMaxAgents(4);
      setError("");
      setSubmitting(false);
      setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open, initialProjectId]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose, submitting]);

  if (!open) return null;

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const result = await createCrewSession({
        name: name.trim(),
        project_id: projectId || undefined,
        max_agents: maxAgents,
      });
      onCreated?.(result.session_id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to create crew";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl w-full max-w-md shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-light-border dark:border-border">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Users size={18} className="text-accent" />
            New Crew Session
          </h3>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 transition-colors disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
              Crew name <span className="text-red-400">*</span>
            </label>
            <input
              ref={nameRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Backend + Frontend Sprint"
              className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
              onKeyDown={(e) => {
                if (e.key === "Enter" && name.trim()) handleSubmit();
              }}
            />
          </div>

          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
              Link to project
            </label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm focus:outline-none focus:border-accent"
            >
              <option value="">No project (standalone)</option>
              {projects.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
              Max parallel agents
            </label>
            <div className="flex items-center gap-3">
              {[2, 3, 4, 5, 6].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setMaxAgents(n)}
                  className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
                    maxAgents === n
                      ? "bg-accent text-white"
                      : "bg-gray-100 dark:bg-surface-lighter text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-light-border dark:border-border">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm rounded-lg bg-gray-100 dark:bg-surface-lighter text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-border transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !name.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {submitting ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating...
              </>
            ) : (
              "Create Crew"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
