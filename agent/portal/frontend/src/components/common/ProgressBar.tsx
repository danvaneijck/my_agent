/**
 * ProgressBar - Animated progress bar component
 *
 * Provides spring physics animation for smooth progress updates
 */

import { motion } from "framer-motion";
import { progressVariants } from "@/utils/animations";

interface ProgressBarProps {
  progress: number; // 0-100
  className?: string;
  color?: string;
  height?: number;
  showLabel?: boolean;
}

/**
 * Animated progress bar with spring physics
 */
export default function ProgressBar({
  progress,
  className = "",
  color = "bg-accent",
  height = 8,
  showLabel = false,
}: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div className={className}>
      {showLabel && (
        <div className="flex items-center justify-between mb-2 text-sm text-gray-600 dark:text-gray-400">
          <span>Progress</span>
          <span className="font-medium">{Math.round(clampedProgress)}%</span>
        </div>
      )}
      <div
        className="bg-gray-200 dark:bg-surface-lighter rounded-full overflow-hidden"
        style={{ height }}
      >
        <motion.div
          className={`h-full ${color} rounded-full`}
          initial="initial"
          animate="animate"
          custom={clampedProgress}
          variants={progressVariants}
        />
      </div>
    </div>
  );
}
