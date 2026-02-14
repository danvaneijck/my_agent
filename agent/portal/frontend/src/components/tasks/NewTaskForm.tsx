import { useState, useEffect } from "react";
import { Play, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import NewTaskModal from "./NewTaskModal";

interface NewTaskFormProps {
  onCreated: () => void;
  defaultRepoUrl?: string;
  defaultBranch?: string;
  defaultPrompt?: string;
  autoOpen?: boolean;
}

interface HealthResponse {
  available: boolean;
  reason?: string;
  error?: string;
}

export default function NewTaskForm({
  onCreated,
  defaultRepoUrl,
  defaultBranch,
  defaultPrompt,
  autoOpen = false,
}: NewTaskFormProps) {
  const [open, setOpen] = useState(autoOpen);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    api<HealthResponse>("/api/tasks/health")
      .then((r) => setHealth(r))
      .catch(() => setHealth({ available: false, reason: "error", error: "Failed to check service status." }));
  }, []);

  if (health && !health.available) {
    const showSettingsLink = health.reason === "no_credentials";
    return (
      <div className="flex items-center gap-2 text-sm text-yellow-400">
        <AlertTriangle size={16} className="shrink-0" />
        <span>
          {health.error || "Claude Code is not available."}{" "}
          {showSettingsLink && (
            <Link to="/settings" className="underline hover:text-yellow-300">
              Configure in Settings
            </Link>
          )}
        </span>
      </div>
    );
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        disabled={health === null}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
      >
        <Play size={16} />
        New Task
      </button>
      <NewTaskModal
        open={open}
        onClose={() => setOpen(false)}
        onCreated={onCreated}
        defaultRepoUrl={defaultRepoUrl}
        defaultBranch={defaultBranch}
        defaultPrompt={defaultPrompt}
      />
    </>
  );
}
