/**
 * Animation Configuration Utilities
 *
 * Centralized animation variants and utilities for Framer Motion.
 * Respects user's prefers-reduced-motion setting.
 */

import { Variants, Transition } from 'framer-motion';

/**
 * Check if user prefers reduced motion
 */
export const prefersReducedMotion = (): boolean => {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

/**
 * Get transition with reduced motion support
 */
export const getTransition = (transition: Transition): Transition => {
  if (prefersReducedMotion()) {
    return { duration: 0 };
  }
  return transition;
};

/**
 * Standard easing curves
 */
export const easings = {
  easeOut: [0.0, 0.0, 0.2, 1],
  easeIn: [0.4, 0.0, 1, 1],
  easeInOut: [0.4, 0.0, 0.2, 1],
  sharp: [0.4, 0.0, 0.6, 1],
} as const;

/**
 * Page transition variants
 * Fade in with subtle slide up effect
 */
export const pageVariants: Variants = {
  initial: {
    opacity: 0,
    y: 20,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: getTransition({
      duration: 0.2,
      ease: easings.easeOut,
    }),
  },
  exit: {
    opacity: 0,
    y: -10,
    transition: getTransition({
      duration: 0.15,
      ease: easings.easeIn,
    }),
  },
};

/**
 * Card stagger container variants
 */
export const staggerContainerVariants: Variants = {
  initial: {},
  animate: {
    transition: getTransition({
      staggerChildren: 0.05,
      delayChildren: 0.1,
    }),
  },
};

/**
 * Card stagger item variants
 */
export const staggerItemVariants: Variants = {
  initial: {
    opacity: 0,
    y: 20,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: getTransition({
      duration: 0.3,
      ease: easings.easeOut,
    }),
  },
};

/**
 * List stagger container variants
 */
export const listContainerVariants: Variants = {
  initial: {},
  animate: {
    transition: getTransition({
      staggerChildren: 0.03,
    }),
  },
  exit: {
    transition: getTransition({
      staggerChildren: 0.02,
      staggerDirection: -1,
    }),
  },
};

/**
 * List item variants
 */
export const listItemVariants: Variants = {
  initial: {
    opacity: 0,
    x: -10,
  },
  animate: {
    opacity: 1,
    x: 0,
    transition: getTransition({
      duration: 0.2,
      ease: easings.easeOut,
    }),
  },
  exit: {
    opacity: 0,
    x: 10,
    transition: getTransition({
      duration: 0.15,
      ease: easings.easeIn,
    }),
  },
};

/**
 * Modal/Dialog variants
 */
export const modalVariants: Variants = {
  initial: {
    opacity: 0,
    scale: 0.95,
  },
  animate: {
    opacity: 1,
    scale: 1,
    transition: getTransition({
      duration: 0.2,
      ease: easings.easeOut,
    }),
  },
  exit: {
    opacity: 0,
    scale: 0.95,
    transition: getTransition({
      duration: 0.15,
      ease: easings.easeIn,
    }),
  },
};

/**
 * Toast notification variants
 */
export const toastVariants: Variants = {
  initial: {
    opacity: 0,
    y: -50,
    x: 50,
  },
  animate: {
    opacity: 1,
    y: 0,
    x: 0,
    transition: getTransition({
      duration: 0.3,
      ease: easings.easeOut,
    }),
  },
  exit: {
    opacity: 0,
    x: 100,
    transition: getTransition({
      duration: 0.2,
      ease: easings.easeIn,
    }),
  },
};

/**
 * Fade in variants (simple)
 */
export const fadeInVariants: Variants = {
  initial: {
    opacity: 0,
  },
  animate: {
    opacity: 1,
    transition: getTransition({
      duration: 0.2,
    }),
  },
  exit: {
    opacity: 0,
    transition: getTransition({
      duration: 0.15,
    }),
  },
};

/**
 * Scale variants for buttons and interactive elements
 */
export const scaleVariants = {
  rest: { scale: 1 },
  hover: {
    scale: 1.02,
    transition: getTransition({
      duration: 0.15,
      ease: easings.easeOut,
    }),
  },
  tap: {
    scale: 0.98,
    transition: getTransition({
      duration: 0.1,
    }),
  },
};

/**
 * Card hover variants
 */
export const cardHoverVariants = {
  rest: {
    y: 0,
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  hover: {
    y: -2,
    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    transition: getTransition({
      duration: 0.2,
      ease: easings.easeOut,
    }),
  },
};

/**
 * Shimmer effect for skeleton loaders
 */
export const shimmerVariants: Variants = {
  initial: {
    backgroundPosition: '-200% 0',
  },
  animate: {
    backgroundPosition: '200% 0',
    transition: {
      repeat: Infinity,
      duration: prefersReducedMotion() ? 0 : 1.5,
      ease: 'linear',
    },
  },
};

/**
 * Spinner rotation variants
 */
export const spinnerVariants: Variants = {
  animate: {
    rotate: 360,
    transition: {
      repeat: Infinity,
      duration: prefersReducedMotion() ? 0 : 1,
      ease: 'linear',
    },
  },
};

/**
 * Stream entry variants — used for new log/event entries fading in during task streaming
 */
export const streamEntryVariants: Variants = {
  initial: {
    opacity: 0,
    y: 8,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: getTransition({
      duration: 0.25,
      ease: easings.easeOut,
    }),
  },
};

/**
 * Progress bar variants
 */
export const progressVariants = {
  initial: { width: '0%' },
  animate: (progress: number) => ({
    width: `${progress}%`,
    transition: getTransition({
      type: 'spring',
      stiffness: 100,
      damping: 20,
    }),
  }),
};
