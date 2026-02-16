import { NavLink } from "react-router-dom";
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
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-56
          bg-white dark:bg-surface-light
          border-r border-light-border dark:border-border
          transform transition-transform duration-200 ease-in-out
          md:translate-x-0 md:static md:z-auto
          ${open ? "translate-x-0" : "-translate-x-full"}
        `}
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
            className="md:hidden p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="p-3 space-y-1">
          {NAV_ITEMS.map(({ to, icon: Icon, label, badgeKey, end }) => (
            <NavLink
              key={to}
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
          ))}
        </nav>
      </aside>
    </>
  );
}
