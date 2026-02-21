import { X, ExternalLink } from "lucide-react";
import { motion } from "framer-motion";

export interface DeployRun {
  id: number;
  name: string;
  status: "queued" | "in_progress";
  url: string;
  created_at: string;
  updated_at: string;
}

interface DeploymentBannerProps {
  run: DeployRun;
  onDismiss: () => void;
}

export default function DeploymentBanner({ run, onDismiss }: DeploymentBannerProps) {
  return (
    <motion.div
      className="fixed top-0 inset-x-0 z-40 bg-amber-500 dark:bg-amber-600 text-white text-sm shadow-md"
      initial={{ y: -48, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: -48, opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div className="flex items-center gap-3 px-4 py-2 max-w-screen-xl mx-auto">
        {/* Pulsing status dot */}
        <span className="shrink-0 w-2 h-2 rounded-full bg-white animate-pulse" aria-hidden="true" />

        {/* Message */}
        <p className="flex-1 min-w-0 truncate font-medium">
          Deployment in progress &mdash; <span className="font-normal opacity-90">{run.name}</span> is{" "}
          {run.status === "queued" ? "queued" : "running"}. The app may restart and briefly become unavailable.
        </p>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <a
            href={run.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-white/20 hover:bg-white/30 transition-colors focus:outline-none focus:ring-2 focus:ring-white"
          >
            View run
            <ExternalLink size={11} />
          </a>
          <button
            onClick={onDismiss}
            className="p-1.5 rounded hover:bg-white/20 transition-colors focus:outline-none focus:ring-2 focus:ring-white"
            aria-label="Dismiss deployment banner"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </motion.div>
  );
}
