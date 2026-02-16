/**
 * Spinner - Animated loading spinner component
 *
 * Provides smooth rotation animation with framer-motion
 */

import { motion } from "framer-motion";
import { spinnerVariants } from "@/utils/animations";

interface SpinnerProps {
  size?: number;
  className?: string;
  color?: string;
}

/**
 * Animated spinner with smooth rotation
 */
export default function Spinner({ size = 20, className = "", color = "currentColor" }: SpinnerProps) {
  return (
    <motion.div
      className={`inline-block ${className}`}
      animate="animate"
      variants={spinnerVariants}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="40 20"
          opacity="0.4"
        />
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="15 85"
          opacity="1"
        />
      </svg>
    </motion.div>
  );
}
