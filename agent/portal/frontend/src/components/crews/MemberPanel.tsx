import { X, ExternalLink } from "lucide-react";
import type { CrewMember } from "@/types";

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  idle: { color: "text-gray-400", bg: "bg-gray-400/20", label: "Idle" },
  working: { color: "text-blue-400", bg: "bg-blue-500/20", label: "Working" },
  merging: { color: "text-yellow-400", bg: "bg-yellow-500/20", label: "Merging" },
  completed: { color: "text-green-400", bg: "bg-green-500/20", label: "Completed" },
  failed: { color: "text-red-400", bg: "bg-red-500/20", label: "Failed" },
};

interface MemberPanelProps {
  member: CrewMember;
  onClose: () => void;
}

export default function MemberPanel({ member, onClose }: MemberPanelProps) {
  const status = STATUS_CONFIG[member.status] || STATUS_CONFIG.idle;

  const formatDate = (d: string | null) => {
    if (!d) return "-";
    return new Date(d).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-medium text-gray-900 dark:text-white">
            {member.task_title || "Unassigned Agent"}
          </h3>
          {member.role && (
            <span className="text-xs text-gray-500 dark:text-gray-400 capitalize">
              {member.role}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500"
        >
          <X size={16} />
        </button>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span className={`text-xs px-2 py-0.5 rounded-full ${status.bg} ${status.color}`}>
          {status.label}
        </span>
        <span className="text-xs text-gray-500">Wave {member.wave_number}</span>
      </div>

      {/* Details */}
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Branch</span>
          <span className="text-gray-900 dark:text-white font-mono text-xs">
            {member.branch_name}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Started</span>
          <span className="text-gray-900 dark:text-white text-xs">
            {formatDate(member.started_at)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Completed</span>
          <span className="text-gray-900 dark:text-white text-xs">
            {formatDate(member.completed_at)}
          </span>
        </div>
      </div>

      {/* Task link */}
      {member.claude_task_id && (
        <a
          href={`/tasks/${member.claude_task_id}`}
          className="flex items-center gap-1.5 text-xs text-accent hover:underline"
        >
          <ExternalLink size={12} />
          View Claude task
        </a>
      )}

      {/* Error */}
      {member.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          <p className="text-xs text-red-400">{member.error_message}</p>
        </div>
      )}
    </div>
  );
}
