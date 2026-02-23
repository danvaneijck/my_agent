import type { CrewSessionSummary } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  configuring: "bg-blue-500/20 text-blue-400",
  running: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  failed: "bg-red-500/20 text-red-400",
};

interface CrewCardProps {
  crew: CrewSessionSummary;
  onClick: () => void;
}

export default function CrewCard({ crew, onClick }: CrewCardProps) {
  const wavePct =
    crew.total_waves > 0
      ? Math.round((crew.current_wave / crew.total_waves) * 100)
      : 0;

  return (
    <button
      onClick={onClick}
      className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 text-left hover:border-gray-300 dark:hover:border-border-light transition-colors w-full"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-medium text-gray-900 dark:text-white truncate">
          {crew.name}
        </h3>
        <span
          className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[crew.status] || STATUS_COLORS.configuring}`}
        >
          {crew.status}
        </span>
      </div>

      <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mb-3">
        <span>{crew.member_count} agent{crew.member_count !== 1 ? "s" : ""}</span>
        <span>Max {crew.max_agents}</span>
      </div>

      {crew.total_waves > 0 && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>
              Wave {crew.current_wave}/{crew.total_waves}
            </span>
            <span>{wavePct}%</span>
          </div>
          <div className="h-1.5 bg-gray-200 dark:bg-surface-lighter rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-500"
              style={{ width: `${wavePct}%` }}
            />
          </div>
        </div>
      )}

      {crew.total_waves === 0 && (
        <p className="text-xs text-gray-500">No waves computed yet</p>
      )}
    </button>
  );
}
