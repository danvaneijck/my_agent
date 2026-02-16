/**
 * Button - Animated button component with micro-interactions
 *
 * Provides consistent hover/tap animations across all buttons
 */

import { motion } from "framer-motion";
import { scaleVariants } from "@/utils/animations";
import type { ReactNode } from "react";

interface ButtonProps {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  className?: string;
  disabled?: boolean;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  type?: "button" | "submit" | "reset";
  form?: string;
  title?: string;
}

const variantStyles = {
  primary: "bg-accent hover:bg-accent-hover text-white",
  secondary: "bg-surface-lighter hover:bg-surface-light border border-border text-gray-200",
  ghost: "bg-transparent hover:bg-surface-lighter text-gray-400 hover:text-gray-200",
  danger: "bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400",
};

const sizeStyles = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

/**
 * Animated button with scale animation on hover/tap
 */
export default function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  disabled = false,
  onClick,
  type = "button",
  form,
  title,
}: ButtonProps) {
  const baseStyles = "rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const combinedClassName = `${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`;

  return (
    <motion.button
      className={combinedClassName}
      initial="rest"
      whileHover={disabled ? undefined : "hover"}
      whileTap={disabled ? undefined : "tap"}
      variants={scaleVariants}
      disabled={disabled}
      onClick={onClick}
      type={type}
      form={form}
      title={title}
    >
      {children}
    </motion.button>
  );
}
