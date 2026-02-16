/**
 * EnvironmentBadge - Visual indicator for non-production environments
 *
 * Displays a prominent badge in development and staging environments
 * to prevent confusion with production.
 */

import { motion } from "framer-motion";

interface EnvironmentBadgeProps {
  environment?: "development" | "staging" | "production";
}

export default function EnvironmentBadge({ environment }: EnvironmentBadgeProps) {
  // Determine environment from various sources
  // In production builds, MODE is "production", in dev server MODE is "development"
  const env =
    environment ||
    (import.meta.env.MODE === "development"
      ? "development"
      : (import.meta.env.VITE_APP_ENV as string) || "production");

  // Don't show badge in production
  if (env === "production") {
    return null;
  }

  const config = {
    development: {
      label: "DEV",
      bgClass: "bg-blue-500",
      textClass: "text-white",
      borderClass: "border-blue-600",
    },
    staging: {
      label: "STAGING",
      bgClass: "bg-orange-500",
      textClass: "text-white",
      borderClass: "border-orange-600",
    },
  };

  const envConfig = config[env as keyof typeof config];

  if (!envConfig) {
    return null;
  }

  return (
    <motion.div
      className={`fixed top-0 right-0 z-50 ${envConfig.bgClass} ${envConfig.textClass} px-3 py-1 text-xs font-bold uppercase tracking-wider shadow-lg border-b-2 border-l-2 ${envConfig.borderClass} rounded-bl-lg`}
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5, duration: 0.3 }}
    >
      {envConfig.label}
    </motion.div>
  );
}
