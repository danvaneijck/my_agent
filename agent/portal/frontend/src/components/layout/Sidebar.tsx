import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquare,
  FolderOpen,
  Code2,
  Clock,
  Rocket,
  Settings,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/chat", icon: MessageSquare, label: "Chat", badgeKey: "chat" },
  { to: "/", icon: LayoutDashboard, label: "Tasks" },
  { to: "/code", icon: Code2, label: "Code" },
  { to: "/deployments", icon: Rocket, label: "Deployments" },
  { to: "/files", icon: FolderOpen, label: "Files" },
  { to: "/schedule", icon: Clock, label: "Schedule" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  chatUnreadCount?: number;
}

export default function Sidebar({ open, onClose, chatUnreadCount = 0 }: SidebarProps) {
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
          fixed inset-y-0 left-0 z-40 w-56 bg-surface-light border-r border-border
          transform transition-transform duration-200 ease-in-out
          md:translate-x-0 md:static md:z-auto
          ${open ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        <div className="flex items-center justify-between h-14 px-4 border-b border-border">
          <span className="text-lg font-semibold text-white">Agent Portal</span>
          <button
            onClick={onClose}
            className="md:hidden p-1 rounded hover:bg-surface-lighter text-gray-400"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="p-3 space-y-1">
          {NAV_ITEMS.map(({ to, icon: Icon, label, badgeKey }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive
                  ? "bg-accent/15 text-accent-hover"
                  : "text-gray-400 hover:text-gray-200 hover:bg-surface-lighter"
                }`
              }
            >
              <Icon size={18} />
              <span className="flex-1">{label}</span>
              {badgeKey === "chat" && chatUnreadCount > 0 && (
                <span className="bg-accent text-white text-xs font-bold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
                  {chatUnreadCount > 99 ? "99+" : chatUnreadCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
