interface MultiStateProgressBarProps {
  task_counts: {
    todo?: number;
    doing?: number;
    in_review?: number;
    done?: number;
    failed?: number;
  };
  height?: string;
  showLabels?: boolean;
}

interface SegmentConfig {
  key: keyof MultiStateProgressBarProps["task_counts"];
  label: string;
  color: string;
}

const SEGMENTS: SegmentConfig[] = [
  { key: "done", label: "Done", color: "bg-green-500" },
  { key: "in_review", label: "In Review", color: "bg-blue-500" },
  { key: "doing", label: "Doing", color: "bg-yellow-500" },
  { key: "failed", label: "Failed", color: "bg-red-500" },
  { key: "todo", label: "To Do", color: "bg-gray-500" },
];

export default function MultiStateProgressBar({
  task_counts,
  height = "h-1.5",
  showLabels = false,
}: MultiStateProgressBarProps) {
  // Calculate total tasks
  const total = Object.values(task_counts).reduce((sum, count) => sum + (count || 0), 0);

  // If no tasks, show empty state
  if (total === 0) {
    return (
      <div className={`${height} bg-gray-200 dark:bg-surface rounded-full overflow-hidden`}>
        <div className="h-full w-full" />
      </div>
    );
  }

  // Build segments with their percentages
  const segments = SEGMENTS.map((segment) => {
    const count = task_counts[segment.key] || 0;
    const percentage = (count / total) * 100;
    return {
      ...segment,
      count,
      percentage,
    };
  }).filter((s) => s.count > 0);

  return (
    <div className="space-y-1">
      <div className={`${height} bg-gray-200 dark:bg-surface rounded-full overflow-hidden flex`}>
        {segments.map((segment, idx) => (
          <div
            key={segment.key}
            className={`${segment.color} transition-all ${idx === 0 ? "rounded-l-full" : ""} ${idx === segments.length - 1 ? "rounded-r-full" : ""}`}
            style={{ width: `${segment.percentage}%` }}
            title={`${segment.label}: ${segment.count}`}
          />
        ))}
      </div>

      {showLabels && segments.length > 0 && (
        <div className="flex flex-wrap gap-2 text-xs">
          {segments.map((segment) => (
            <div key={segment.key} className="flex items-center gap-1">
              <div className={`w-2 h-2 rounded-sm ${segment.color}`} />
              <span className="text-gray-500 dark:text-gray-400">
                {segment.count} {segment.label.toLowerCase()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
