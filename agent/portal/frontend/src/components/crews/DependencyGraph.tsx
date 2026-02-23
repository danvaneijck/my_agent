import type { CrewMember } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  idle: "border-gray-400 bg-gray-400/10 text-gray-400",
  working: "border-blue-500 bg-blue-500/10 text-blue-400",
  merging: "border-yellow-500 bg-yellow-500/10 text-yellow-400",
  completed: "border-green-500 bg-green-500/10 text-green-400",
  failed: "border-red-500 bg-red-500/10 text-red-400",
};

interface DependencyGraphProps {
  members: CrewMember[];
  totalWaves: number;
  currentWave: number;
}

export default function DependencyGraph({ members, totalWaves, currentWave }: DependencyGraphProps) {
  if (members.length === 0 && totalWaves === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
        No dependency data available
      </div>
    );
  }

  // Group by wave
  const waves = new Map<number, CrewMember[]>();
  for (const m of members) {
    if (!waves.has(m.wave_number)) waves.set(m.wave_number, []);
    waves.get(m.wave_number)!.push(m);
  }

  const waveNums = Array.from(
    { length: Math.max(totalWaves, waves.size) },
    (_, i) => i,
  );

  return (
    <div className="space-y-4 p-1">
      {waveNums.map((waveNum) => {
        const waveMembers = waves.get(waveNum) || [];
        const isCurrent = waveNum === currentWave;
        const isComplete = waveNum < currentWave;

        return (
          <div key={waveNum}>
            {/* Wave separator with arrow */}
            {waveNum > 0 && (
              <div className="flex justify-center py-1">
                <div className="w-0.5 h-4 bg-gray-300 dark:bg-surface-lighter" />
              </div>
            )}

            <div
              className={`rounded-lg border p-3 ${
                isCurrent
                  ? "border-accent/40 bg-accent/5"
                  : isComplete
                    ? "border-green-500/30 bg-green-500/5"
                    : "border-light-border dark:border-border"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  Wave {waveNum}
                </span>
                {isCurrent && (
                  <span className="text-xs text-accent font-medium">Active</span>
                )}
                {isComplete && (
                  <span className="text-xs text-green-400 font-medium">Done</span>
                )}
              </div>

              {waveMembers.length === 0 ? (
                <p className="text-xs text-gray-500">No tasks assigned</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {waveMembers.map((m) => {
                    const cls = STATUS_COLORS[m.status] || STATUS_COLORS.idle;
                    return (
                      <div
                        key={m.id}
                        className={`border rounded-md px-2.5 py-1.5 text-xs ${cls}`}
                      >
                        <p className="font-medium truncate max-w-[140px]">
                          {m.task_title || "Unassigned"}
                        </p>
                        {m.role && (
                          <p className="opacity-70 capitalize">{m.role}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
