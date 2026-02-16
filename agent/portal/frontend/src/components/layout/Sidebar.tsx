import { NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect } from "react";
import {
  Home,
  LayoutDashboard,
  MessageSquare,
  FolderOpen,
  FolderKanban,
  Code2,
  GitBranch,
  GitPullRequest,
  Clock,
  Rocket,
  BarChart3,
  Settings,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", icon: Home, label: "Home", end: true },
  { to: "/chat", icon: MessageSquare, label: "Chat", badgeKey: "chat" },
  { to: "/tasks", icon: LayoutDashboard, label: "Tasks", badgeKey: "tasks" },
  { to: "/projects", icon: FolderKanban, label: "Projects" },
  { to: "/repos", icon: GitBranch, label: "Repos" },
  { to: "/pulls", icon: GitPullRequest, label: "Pull Requests", badgeKey: "pulls" },
  { to: "/code", icon: Code2, label: "Code" },
  { to: "/deployments", icon: Rocket, label: "Deployments" },
  { to: "/files", icon: FolderOpen, label: "Files" },
  { to: "/schedule", icon: Clock, label: "Schedule" },
  { to: "/usage", icon: BarChart3, label: "Usage" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  chatUnreadCount?: number;
  openPrCount?: number;
  activeTaskCount?: number;
}

export default function Sidebar({ open, onClose, chatUnreadCount = 0, openPrCount = 0, activeTaskCount = 0 }: SidebarProps) {
  // Check if we're on desktop (md breakpoint and above)
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const checkDesktop = () => {
      setIsDesktop(window.innerWidth >= 768); // md breakpoint
    };

    checkDesktop();
    window.addEventListener("resize", checkDesktop);
    return () => window.removeEventListener("resize", checkDesktop);
  }, []);

  return (
    <>
      {/* Mobile overlay with backdrop blur */}
      <AnimatePresence>
        {open && !isDesktop && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
            onClick={onClose}
            aria-label="Close menu"
          />
        )}
      </AnimatePresence>

      {/* Sidebar with slide animation on mobile, static on desktop */}
      <motion.aside
        initial={false}
        animate={{
          x: isDesktop ? 0 : (open ? 0 : "-100%"),
        }}
        transition={{
          type: "spring",
          damping: 30,
          stiffness: 300,
        }}
        className="fixed inset-y-0 left-0 z-40 w-56 bg-white dark:bg-surface-light border-r border-light-border dark:border-border md:static"
      >
        <div className="flex items-center justify-between h-14 px-4 border-b border-light-border dark:border-border">
          <NavLink
            to="/"
            className="flex items-center gap-2.5 hover:opacity-80 transition-opacity"
            onClick={onClose}
          >
            <img
              src="/logo-icon.svg"
              alt="Nexus"
              className="h-7 w-7"
            />
            <span className="text-lg font-semibold text-gray-900 dark:text-white">
              Nexus
            </span>
          </NavLink>
          <button
            onClick={onClose}
            className="md:hidden p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400 focus:outline-none focus:ring-2 focus:ring-accent"
            aria-label="Close navigation menu"
          >
            <X size={18} />
          </button>
        </div>

        <motion.nav
          className="p-3 space-y-1"
          initial={false}
          animate={open ? "open" : "closed"}
          variants={{
            open: {
              transition: { staggerChildren: 0.05, delayChildren: 0.1 },
            },
            closed: {
              transition: { staggerChildren: 0.03, staggerDirection: -1 },
            },
          }}
        >
          {NAV_ITEMS.map(({ to, icon: Icon, label, badgeKey, end }, index) => (
            <motion.div
              key={to}
              variants={{
                open: { opacity: 1, x: 0 },
                closed: { opacity: 0, x: -20 },
              }}
              transition={{ duration: 0.2 }}
            >
              <NavLink
                to={to}
                end={end}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive
                    ? "bg-accent/15 text-accent dark:text-accent-hover"
                    : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-surface-lighter"
                  }`
                }
              >
                <Icon size={18} />
                <span className="flex-1">{label}</span>
                {badgeKey === "tasks" && activeTaskCount > 0 && (
                  <span className="bg-green-500 text-white text-xs font-bold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
                    {activeTaskCount > 99 ? "99+" : activeTaskCount}
                  </span>
                )}
                {badgeKey === "chat" && chatUnreadCount > 0 && (
                  <span className="bg-accent text-white text-xs font-bold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
                    {chatUnreadCount > 99 ? "99+" : chatUnreadCount}
                  </span>
                )}
                {badgeKey === "pulls" && openPrCount > 0 && (
                  <span className="bg-accent text-white text-xs font-bold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
                    {openPrCount > 99 ? "99+" : openPrCount}
                  </span>
                )}
              </NavLink>
            </motion.div>
          ))}
        </motion.nav>
      </motion.aside>
    </>
  );
}
