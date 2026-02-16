/**
 * AnimatedList - Reusable list animation component
 *
 * Provides staggered fade-in animations for list items with layout animations
 * for filter/sort changes and exit animations when items are removed.
 */

import { motion, AnimatePresence } from "framer-motion";
import { listContainerVariants, listItemVariants } from "@/utils/animations";
import type { ReactNode } from "react";

interface AnimatedListProps {
  children: ReactNode;
  className?: string;
}

/**
 * Animated container for lists
 * Wraps children with stagger animation
 */
export function AnimatedListContainer({ children, className = "" }: AnimatedListProps) {
  return (
    <motion.div
      className={className}
      initial="initial"
      animate="animate"
      exit="exit"
      variants={listContainerVariants}
    >
      {children}
    </motion.div>
  );
}

interface AnimatedListItemProps {
  children: ReactNode;
  itemKey: string | number;
  className?: string;
}

/**
 * Animated list item
 * Provides fade-in with slide animation and layout animation
 */
export function AnimatedListItem({ children, itemKey, className = "" }: AnimatedListItemProps) {
  return (
    <motion.div
      key={itemKey}
      className={className}
      variants={listItemVariants}
      layout
      layoutId={String(itemKey)}
    >
      {children}
    </motion.div>
  );
}

/**
 * Animated list with AnimatePresence
 * Use this when you need exit animations (e.g., when items can be removed)
 */
interface AnimatedListWithPresenceProps {
  children: ReactNode;
  className?: string;
}

export function AnimatedListWithPresence({ children, className = "" }: AnimatedListWithPresenceProps) {
  return (
    <AnimatePresence mode="popLayout">
      <AnimatedListContainer className={className}>
        {children}
      </AnimatedListContainer>
    </AnimatePresence>
  );
}

/**
 * Default export combines container and item for convenience
 */
const AnimatedList = {
  Container: AnimatedListContainer,
  Item: AnimatedListItem,
  WithPresence: AnimatedListWithPresence,
};

export default AnimatedList;
