import { NavLink } from "react-router-dom";
import { Home, LayoutDashboard, MessageSquare, Settings, Menu } from "lucide-react";

const BOTTOM_TABS = [
  { to: "/", icon: Home, label: "Home", end: true },
  { to: "/tasks", icon: LayoutDashboard, label: "Tasks" },
  { to: "/chat", icon: MessageSquare, label: "Chat" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

interface BottomNavProps {
  onMenuOpen: () => void;
  activeTaskCount?: number;
  chatUnreadCount?: number;
}

export default function BottomNav({ onMenuOpen, activeTaskCount = 0, chatUnreadCount = 0 }: BottomNavProps) {
  return (
    <nav className="fixed bottom-0 inset-x-0 z-30 md:hidden bg-white dark:bg-surface-light border-t border-light-border dark:border-border flex items-stretch safe-bottom">
      {BOTTOM_TABS.map(({ to, icon: Icon, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-[10px] font-medium relative ${
              isActive ? "text-accent" : "text-gray-500 dark:text-gray-400"
            }`
          }
        >
          <div className="relative">
            <Icon size={20} />
            {label === "Tasks" && activeTaskCount > 0 && (
              <span className="absolute -top-1 -right-1.5 bg-green-500 text-white text-[9px] font-bold rounded-full min-w-[14px] h-3.5 flex items-center justify-center px-0.5">
                {activeTaskCount > 99 ? "99+" : activeTaskCount}
              </span>
            )}
            {label === "Chat" && chatUnreadCount > 0 && (
              <span className="absolute -top-1 -right-1.5 bg-accent text-white text-[9px] font-bold rounded-full min-w-[14px] h-3.5 flex items-center justify-center px-0.5">
                {chatUnreadCount > 99 ? "99+" : chatUnreadCount}
              </span>
            )}
          </div>
          <span>{label}</span>
        </NavLink>
      ))}
      <button
        onClick={onMenuOpen}
        className="flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-[10px] font-medium text-gray-500 dark:text-gray-400"
        aria-label="Open navigation menu"
      >
        <Menu size={20} />
        <span>More</span>
      </button>
    </nav>
  );
}
