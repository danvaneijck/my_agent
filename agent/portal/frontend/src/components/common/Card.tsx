/**
 * Card - Animated card wrapper component
 *
 * Provides consistent hover lift animation and shadow effects for cards
 */

import { motion } from "framer-motion";
import { cardHoverVariants } from "@/utils/animations";
import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
}

/**
 * Animated card with hover lift effect
 */
export default function Card({ children, className = "", onClick, hoverable = true }: CardProps) {
  const baseStyles = "bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden";
  const clickableStyles = onClick ? "cursor-pointer" : "";
  const combinedClassName = `${baseStyles} ${clickableStyles} ${className}`;

  if (!hoverable && !onClick) {
    // No animations for non-hoverable, non-clickable cards
    return <div className={combinedClassName}>{children}</div>;
  }

  return (
    <motion.div
      className={combinedClassName}
      initial="rest"
      whileHover="hover"
      variants={cardHoverVariants}
      onClick={onClick}
    >
      {children}
    </motion.div>
  );
}
