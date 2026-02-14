import { Menu, LogOut } from "lucide-react";
import { clearAuth, getUser } from "@/api/client";

interface HeaderProps {
  title: string;
  onMenuToggle: () => void;
}

export default function Header({ title, onMenuToggle }: HeaderProps) {
  const user = getUser();

  return (
    <header className="h-14 border-b border-border bg-surface-light flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="md:hidden p-1.5 rounded hover:bg-surface-lighter text-gray-400"
        >
          <Menu size={20} />
        </button>
        <h1 className="text-base font-semibold text-white">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        {user && (
          <span className="text-sm text-gray-400">{user.username}</span>
        )}
        <button
          onClick={() => {
            clearAuth();
            window.location.reload();
          }}
          className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
          title="Sign out"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
