/**
 * Modal - Animated modal/dialog component
 *
 * Provides fade + scale animation for modal enter/exit
 */

import { motion, AnimatePresence } from "framer-motion";
import { modalVariants, fadeInVariants } from "@/utils/animations";
import type { ReactNode } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
}

const sizeStyles = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-4xl",
  xl: "max-w-6xl",
};

/**
 * Animated modal with backdrop
 */
export default function Modal({ open, onClose, title, children, className = "", size = "md" }: ModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/50 z-40"
            initial="initial"
            animate="animate"
            exit="exit"
            variants={fadeInVariants}
            onClick={onClose}
          />

          {/* Modal */}
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              className={`bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl shadow-xl w-full ${sizeStyles[size]} ${className}`}
              initial="initial"
              animate="animate"
              exit="exit"
              variants={modalVariants}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              {title && (
                <div className="flex items-center justify-between px-6 py-4 border-b border-light-border dark:border-border">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
                  <button
                    onClick={onClose}
                    className="p-1 rounded hover:bg-surface-lighter transition-colors text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                  >
                    <X size={20} />
                  </button>
                </div>
              )}

              {/* Content */}
              <div className="p-6">{children}</div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
