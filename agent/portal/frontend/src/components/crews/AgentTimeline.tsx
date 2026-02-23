import { motion } from "framer-motion";
import type { CrewMember } from "@/types";

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  idle: { color: "text-gray-400", bg: "bg-gray-400/20", label: "Idle" },
  working: { color: "text-blue-400", bg: "bg-blue-500", label: "Working" },
  merging: { color: "text-yellow-400", bg: "bg-yellow-500", label: "Merging" },
  completed: { color: "text-green-400", bg: "bg-green-500", label: "Completed" },
  failed: { color: "text-red-400", bg: "bg-red-500", label: "Failed" },
};

const ROLE_COLORS: Record<string, string> = {
  architect: "bg-purple-500/20 text-purple-400",
  backend: "bg-blue-500/20 text-blue-400",
  frontend: "bg-cyan-500/20 text-cyan-400",
  tester: "bg-orange-500/20 text-orange-400",
  reviewer: "bg-pink-500/20 text-pink-400",
};

interface AgentTimelineProps {
  members: CrewMember[];
  currentWave: number;
  onMemberClick?: (member: CrewMember) => void;
}

export default function AgentTimeline({ members, currentWave, onMemberClick }: AgentTimelineProps) {
  if (members.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
        No agents dispatched yet
      </div>
    );
  }

  // Group members by wave
  const waves = new Map<number, CrewMember[]>();
  for (const m of members) {
    const w = m.wave_number;
    if (!waves.has(w)) waves.set(w, []);
    waves.get(w)!.push(m);
  }
  const sortedWaves = [...waves.entries()].sort(([a], [b]) => a - b);

  return (
    <div className="space-y-4">
      {sortedWaves.map(([waveNum, waveMembers]) => (
        <div key={waveNum}>
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                waveNum === currentWave
                  ? "bg-accent/20 text-accent"
                  : waveNum < currentWave
                    ? "bg-green-500/20 text-green-400"
                    : "bg-gray-200/50 dark:bg-surface-lighter text-gray-500"
              }`}
            >
              Wave {waveNum}
            </span>
          </div>

          <div className="space-y-2">
            {waveMembers.map((member) => {
              const status = STATUS_CONFIG[member.status] || STATUS_CONFIG.idle;
              const roleClass =
                member.role && ROLE_COLORS[member.role]
                  ? ROLE_COLORS[member.role]
                  : "bg-gray-500/20 text-gray-400";

              // Calculate elapsed time for working agents
              let elapsed = "";
              if (member.started_at) {
                const start = new Date(member.started_at).getTime();
                const end = member.completed_at
                  ? new Date(member.completed_at).getTime()
                  : Date.now();
                const secs = Math.floor((end - start) / 1000);
                if (secs >= 3600) {
                  elapsed = `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
                } else if (secs >= 60) {
                  elapsed = `${Math.floor(secs / 60)}m ${secs % 60}s`;
                } else {
                  elapsed = `${secs}s`;
                }
              }

              return (
                <motion.button
                  key={member.id}
                  onClick={() => onMemberClick?.(member)}
                  className="w-full bg-white dark:bg-surface border border-light-border dark:border-border rounded-lg p-3 text-left hover:border-gray-300 dark:hover:border-border-light transition-colors"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  layout
                >
                  <div className="flex items-center gap-3">
                    {/* Status dot */}
                    <div className="relative">
                      <div
                        className={`w-2.5 h-2.5 rounded-full ${status.bg}`}
                      />
                      {member.status === "working" && (
                        <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-blue-500 animate-ping opacity-50" />
                      )}
                    </div>

                    {/* Role badge */}
                    {member.role && (
                      <span className={`text-xs px-2 py-0.5 rounded-full ${roleClass}`}>
                        {member.role}
                      </span>
                    )}

                    {/* Task info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900 dark:text-white truncate">
                        {member.task_title || "Unassigned"}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">
                        {member.branch_name}
                      </p>
                    </div>

                    {/* Time + status */}
                    <div className="text-right shrink-0">
                      <span className={`text-xs font-medium ${status.color}`}>
                        {status.label}
                      </span>
                      {elapsed && (
                        <p className="text-xs text-gray-500 mt-0.5">{elapsed}</p>
                      )}
                    </div>
                  </div>

                  {/* Error message */}
                  {member.error_message && (
                    <p className="text-xs text-red-400 mt-2 line-clamp-2">
                      {member.error_message}
                    </p>
                  )}

                  {/* Progress bar for working agents */}
                  {member.status === "working" && (
                    <div className="mt-2 h-1 bg-gray-200 dark:bg-surface-lighter rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-blue-500 rounded-full"
                        initial={{ width: "0%" }}
                        animate={{ width: "70%" }}
                        transition={{
                          duration: 60,
                          ease: "linear",
                          repeat: Infinity,
                          repeatType: "reverse",
                        }}
                      />
                    </div>
                  )}
                </motion.button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
