/**
 * NotFoundPage - 404 error page with branded styling
 */
import { useNavigate } from "react-router-dom";
import { Search, Home, ArrowLeft } from "lucide-react";
import { motion } from "framer-motion";
import { usePageTitle } from "@/hooks/usePageTitle";

export default function NotFoundPage() {
  usePageTitle("Page Not Found");
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex items-center justify-center p-4">
      <motion.div
        className="max-w-md w-full text-center space-y-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {/* 404 with logo */}
        <motion.div
          className="space-y-4"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          {/* Large 404 */}
          <div className="text-9xl font-bold bg-gradient-to-br from-accent via-accent-hover to-accent/80 bg-clip-text text-transparent">
            404
          </div>

          {/* Logo */}
          <div className="flex justify-center">
            <img src="/logo-icon.svg" alt="Nexus" className="h-12 w-12 opacity-80" />
          </div>
        </motion.div>

        {/* Content */}
        <motion.div
          className="space-y-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Page Not Found</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </motion.div>

        {/* Actions */}
        <motion.div
          className="flex flex-col sm:flex-row gap-3 justify-center pt-4"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: 0.3 }}
        >
          <motion.button
            onClick={() => navigate(-1)}
            className="px-6 py-2.5 bg-surface-lighter hover:bg-surface-light border border-border text-gray-200 rounded-lg font-medium transition-colors inline-flex items-center justify-center gap-2"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <ArrowLeft size={16} />
            Go Back
          </motion.button>
          <motion.button
            onClick={() => navigate("/")}
            className="px-6 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors inline-flex items-center justify-center gap-2"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Home size={16} />
            Go Home
          </motion.button>
        </motion.div>

        {/* Decorative search icon */}
        <motion.div
          className="pt-8 flex justify-center opacity-20"
          initial={{ opacity: 0, rotate: -10 }}
          animate={{ opacity: 0.2, rotate: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
        >
          <Search size={64} className="text-accent" strokeWidth={1} />
        </motion.div>
      </motion.div>
    </div>
  );
}
