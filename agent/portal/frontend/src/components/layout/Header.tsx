import { Menu, LogOut } from "lucide-react";
import { clearAuth, getUser } from "@/api/client";
import ThemeToggle from "@/components/common/ThemeToggle";

interface HeaderProps {
  title: string;
  onMenuToggle: () => void;
}

export default function Header({ title, onMenuToggle }: HeaderProps) {
  const user = getUser();

  return (
    <header className="h-14 border-b border-light-border dark:border-border bg-white dark:bg-surface-light flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="md:hidden p-2.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400 focus:outline-none focus:ring-2 focus:ring-accent"
          aria-label="Open navigation menu"
        >
          <Menu size={20} />
        </button>
        <h1 className="text-base font-semibold text-gray-900 dark:text-white">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        {user && (
          <span className="text-sm text-gray-600 dark:text-gray-400 hidden sm:block">{user.username}</span>
        )}
        <ThemeToggle />
        <button
          onClick={() => {
            clearAuth();
            window.location.reload();
          }}
          className="p-2.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-accent"
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
