/**
 * ShowcasePage - Component showcase for design system
 *
 * Demonstrates all design system components with interactive examples.
 * Accessible via /showcase route for developers and designers.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { usePageTitle } from "@/hooks/usePageTitle";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import StatusBadge from "@/components/common/StatusBadge";
import { Skeleton } from "@/components/common/Skeleton";
import Spinner from "@/components/common/Spinner";
import ProgressBar from "@/components/common/ProgressBar";
import EmptyState from "@/components/common/EmptyState";
import Modal from "@/components/common/Modal";
import {
  Palette,
  Type,
  Square,
  Zap,
  Inbox,
  CheckCircle,
  AlertCircle,
  XCircle,
  Clock,
} from "lucide-react";

export default function ShowcasePage() {
  usePageTitle("Component Showcase");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [progress, setProgress] = useState(65);

  // Brand color mapping for showcase
  const brandColors: Record<number, string> = {
    50: "#eef2ff",
    100: "#e0e7ff",
    200: "#c7d2fe",
    300: "#a5b4fc",
    400: "#818cf8",
    500: "#6366f1",
    600: "#4f46e5",
    700: "#4338ca",
    800: "#3730a3",
    900: "#312e81",
    950: "#1e1b4b",
  };

  return (
    <motion.div
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto"
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Component Showcase
        </h1>
        <p className="text-base text-gray-600 dark:text-gray-400">
          Interactive examples of all design system components
        </p>
      </div>

      {/* Color System */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <Palette className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Color System
          </h2>
        </div>

        <div className="space-y-6">
          {/* Brand Colors */}
          <div>
            <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-3">
              Brand Colors
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {Object.entries(brandColors).map(([shade, color]) => (
                <div key={shade} className="space-y-2">
                  <div
                    className="h-16 rounded-lg border border-light-border dark:border-border"
                    style={{
                      backgroundColor: color,
                    }}
                  />
                  <div className="text-xs text-gray-600 dark:text-gray-400 font-mono">
                    brand-{shade}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Semantic Colors */}
          <div>
            <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-3">
              Semantic Colors
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="space-y-2">
                <div className="h-16 rounded-lg bg-success" />
                <div className="text-xs text-gray-600 dark:text-gray-400 font-mono">success</div>
              </div>
              <div className="space-y-2">
                <div className="h-16 rounded-lg bg-warning" />
                <div className="text-xs text-gray-600 dark:text-gray-400 font-mono">warning</div>
              </div>
              <div className="space-y-2">
                <div className="h-16 rounded-lg bg-error" />
                <div className="text-xs text-gray-600 dark:text-gray-400 font-mono">error</div>
              </div>
              <div className="space-y-2">
                <div className="h-16 rounded-lg bg-info" />
                <div className="text-xs text-gray-600 dark:text-gray-400 font-mono">info</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Typography */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <Type className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Typography
          </h2>
        </div>

        <Card>
          <div className="p-6 space-y-4">
            <div>
              <div className="text-7xl font-bold text-gray-900 dark:text-white mb-1">
                Aa
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Inter · Sans-serif · Variable font
              </p>
            </div>

            <div className="space-y-3 pt-4 border-t border-light-border dark:border-border">
              <p className="text-4xl font-bold text-gray-900 dark:text-white">
                Hero Display (4xl)
              </p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                Page Heading (3xl)
              </p>
              <p className="text-2xl font-semibold text-gray-800 dark:text-gray-200">
                Section Heading (2xl)
              </p>
              <p className="text-xl font-semibold text-gray-800 dark:text-gray-200">
                Subsection (xl)
              </p>
              <p className="text-base text-gray-700 dark:text-gray-300">
                Body text (base) - The quick brown fox jumps over the lazy dog
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Small text (sm) - Secondary information and labels
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-500">
                Caption (xs) - Metadata and timestamps
              </p>
              <code className="font-mono text-sm bg-gray-100 dark:bg-surface-lighter px-2 py-1 rounded text-gray-800 dark:text-gray-200">
                Code (mono) - JetBrains Mono
              </code>
            </div>
          </div>
        </Card>
      </section>

      {/* Buttons */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <Square className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Buttons
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Variants */}
          <Card>
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">
                Variants
              </h3>
              <div className="space-y-3">
                <Button variant="primary" className="w-full">
                  Primary Button
                </Button>
                <Button variant="secondary" className="w-full">
                  Secondary Button
                </Button>
                <Button variant="ghost" className="w-full">
                  Ghost Button
                </Button>
                <Button variant="danger" className="w-full">
                  Danger Button
                </Button>
              </div>
            </div>
          </Card>

          {/* Sizes */}
          <Card>
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">
                Sizes
              </h3>
              <div className="space-y-3">
                <Button size="lg" className="w-full">
                  Large Button
                </Button>
                <Button size="md" className="w-full">
                  Medium Button (Default)
                </Button>
                <Button size="sm" className="w-full">
                  Small Button
                </Button>
              </div>
            </div>
          </Card>

          {/* States */}
          <Card>
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">
                States
              </h3>
              <div className="space-y-3">
                <Button className="w-full">Normal State</Button>
                <Button disabled className="w-full">
                  Disabled State
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Status Badges */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <CheckCircle className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Status Badges
          </h2>
        </div>

        <Card>
          <div className="p-6">
            <div className="flex flex-wrap gap-3">
              <StatusBadge status="queued" />
              <StatusBadge status="running" />
              <StatusBadge status="running" stale />
              <StatusBadge status="completed" />
              <StatusBadge status="failed" />
              <StatusBadge status="cancelled" />
              <StatusBadge status="awaiting_input" />
              <StatusBadge status="timed_out" />
            </div>
          </div>
        </Card>
      </section>

      {/* Loading States */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <Zap className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Loading States
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Spinners */}
          <Card>
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">
                Spinners
              </h3>
              <div className="flex items-center gap-6">
                <div className="text-center">
                  <Spinner size={16} className="text-accent" />
                  <p className="text-xs text-gray-500 mt-2">Small (16px)</p>
                </div>
                <div className="text-center">
                  <Spinner size={24} className="text-accent" />
                  <p className="text-xs text-gray-500 mt-2">Medium (24px)</p>
                </div>
                <div className="text-center">
                  <Spinner size={32} className="text-accent" />
                  <p className="text-xs text-gray-500 mt-2">Large (32px)</p>
                </div>
              </div>
            </div>
          </Card>

          {/* Skeletons */}
          <Card>
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">
                Skeleton Loaders
              </h3>
              <div className="space-y-3">
                <Skeleton className="h-8 w-3/4" />
                <Skeleton className="h-6 w-full" />
                <Skeleton className="h-6 w-5/6" />
                <div className="flex gap-3">
                  <Skeleton className="h-12 w-12 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-2/3" />
                    <Skeleton className="h-4 w-1/2" />
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Progress Bar */}
          <Card>
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">
                Progress Bar
              </h3>
              <div className="space-y-4">
                <ProgressBar progress={progress} />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => setProgress(Math.max(0, progress - 10))}
                    disabled={progress === 0}
                  >
                    -10%
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => setProgress(Math.min(100, progress + 10))}
                    disabled={progress === 100}
                  >
                    +10%
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setProgress(0)}>
                    Reset
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Cards */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <Square className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Cards
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card hoverable>
            <div className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                Hoverable Card
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Hover to see lift animation
              </p>
            </div>
          </Card>

          <Card onClick={() => setIsModalOpen(true)} hoverable>
            <div className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                Clickable Card
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Click to open modal
              </p>
            </div>
          </Card>

          <Card hoverable={false}>
            <div className="p-6">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                Static Card
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                No hover effect
              </p>
            </div>
          </Card>
        </div>
      </section>

      {/* Empty States */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <Inbox className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Empty States
          </h2>
        </div>

        <Card>
          <div className="p-12">
            <EmptyState
              icon={Inbox}
              title="No items found"
              description="There are no items to display. Try creating a new one to get started."
              action={{
                label: "Create Item",
                onClick: () => {},
              }}
            />
          </div>
        </Card>
      </section>

      {/* Modals */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <Square className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Modals
          </h2>
        </div>

        <Card>
          <div className="p-6">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Click the button below or the "Clickable Card" above to see a modal
            </p>
            <Button onClick={() => setIsModalOpen(true)}>
              Open Modal
            </Button>
          </div>
        </Card>
      </section>

      {/* Icons */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <CheckCircle className="text-accent" size={24} />
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Icons (Lucide)
          </h2>
        </div>

        <Card>
          <div className="p-6">
            <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-6">
              <div className="flex flex-col items-center gap-2">
                <CheckCircle size={24} className="text-success" />
                <span className="text-xs text-gray-500">Check</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <XCircle size={24} className="text-error" />
                <span className="text-xs text-gray-500">Error</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <AlertCircle size={24} className="text-warning" />
                <span className="text-xs text-gray-500">Alert</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <Clock size={24} className="text-info" />
                <span className="text-xs text-gray-500">Time</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <Inbox size={24} className="text-gray-400" />
                <span className="text-xs text-gray-500">Inbox</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <Palette size={24} className="text-accent" />
                <span className="text-xs text-gray-500">Palette</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <Type size={24} className="text-accent" />
                <span className="text-xs text-gray-500">Type</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <Zap size={24} className="text-accent" />
                <span className="text-xs text-gray-500">Zap</span>
              </div>
            </div>
          </div>
        </Card>
      </section>

      {/* Modal Demo */}
      <Modal
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Example Modal"
        size="md"
      >
        <div className="space-y-4">
          <p className="text-gray-700 dark:text-gray-300">
            This is an example modal dialog with scale animation and backdrop blur.
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            It supports keyboard navigation (Escape to close) and includes a focus trap
            for accessibility.
          </p>
          <div className="flex justify-end gap-2 pt-4 border-t border-light-border dark:border-border">
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setIsModalOpen(false)}>
              Confirm
            </Button>
          </div>
        </div>
      </Modal>
    </motion.div>
  );
}
