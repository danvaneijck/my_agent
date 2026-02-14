const STATUS_STYLES: Record<string, string> = {
  queued: "bg-blue-500/20 text-blue-400",
  running: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-gray-500/20 text-gray-400",
  awaiting_input: "bg-purple-500/20 text-purple-400",
  timed_out: "bg-orange-500/20 text-orange-400",
};

const STATUS_LABELS: Record<string, string> = {
  awaiting_input: "awaiting review",
  timed_out: "timed out",
};

interface StatusBadgeProps {
  status: string;
  stale?: boolean;
}

export default function StatusBadge({ status, stale }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.cancelled;
  const label = STATUS_LABELS[status] || status;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${style}`}>
      {(status === "running" || status === "awaiting_input") && (
        <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${
          status === "awaiting_input" ? "bg-purple-400" :
          stale ? "bg-orange-400" : "bg-yellow-400"
        }`} />
      )}
      {label}
      {stale && <span className="text-orange-400 ml-0.5">(stale)</span>}
    </span>
  );
}
