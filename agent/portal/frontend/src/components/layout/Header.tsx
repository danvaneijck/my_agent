import { Menu, LogOut } from "lucide-react";
import { clearAuth, getUser } from "@/api/client";

interface HeaderProps {
  title: string;
  onMenuToggle: () => void;
}

export default function Header({ title, onMenuToggle }: HeaderProps) {
  const user = getUser();

  return (
    <header className="h-14 border-b border-border bg-gradient-to-r from-surface-light via-surface-light to-surface-lighter flex items-center justify-between px-4 shrink-0 shadow-sm">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="md:hidden p-2 rounded-lg hover:bg-surface-lighter/80 text-gray-400 hover:text-gray-200 transition-colors"
          aria-label="Toggle menu"
        >
          <Menu size={20} />
        </button>
        <h1 className="text-base font-bold text-white tracking-tight">{title}</h1>
      </div>
      <div className="flex items-center gap-4">
        {user && (
          <div className="flex flex-col items-end">
            <span className="text-sm font-medium text-gray-300">{user.username}</span>
            <span className="text-xs text-gray-500 capitalize">{user.permission_level}</span>
          </div>
        )}
        <button
          onClick={() => {
            clearAuth();
            window.location.reload();
          }}
          className="p-2 rounded-lg bg-surface-lighter/50 hover:bg-red-500/10 text-gray-400 hover:text-red-400 transition-all duration-200 border border-transparent hover:border-red-500/30"
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
