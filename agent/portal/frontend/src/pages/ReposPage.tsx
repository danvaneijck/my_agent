import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GitBranch, Search, RefreshCw, Lock, Star } from "lucide-react";
import { useRepos } from "@/hooks/useRepos";
import { ReposGridSkeleton } from "@/components/common/Skeleton";

const LANG_COLORS: Record<string, string> = {
  Python: "bg-blue-500",
  TypeScript: "bg-blue-400",
  JavaScript: "bg-yellow-400",
  Go: "bg-cyan-400",
  Rust: "bg-orange-400",
  Java: "bg-red-400",
  Ruby: "bg-red-500",
  C: "bg-gray-400",
  "C++": "bg-pink-400",
  "C#": "bg-purple-400",
  Shell: "bg-green-400",
  HTML: "bg-orange-500",
  CSS: "bg-purple-500",
  Dockerfile: "bg-blue-300",
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 30) return `${diffDays}d ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}

export default function ReposPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { repos, loading, error, refetch } = useRepos(debouncedSearch);
  const navigate = useNavigate();

  // Simple debounce via timeout
  const handleSearchChange = (value: string) => {
    setSearch(value);
    // Only search via API if input looks intentional (3+ chars or empty)
    if (value.length >= 3 || value.length === 0) {
      setDebouncedSearch(value);
    }
  };

  // Client-side filter for quick filtering while typing
  const filtered = search.length > 0 && search.length < 3
    ? repos.filter(
        (r) =>
          r.full_name.toLowerCase().includes(search.toLowerCase()) ||
          (r.description || "").toLowerCase().includes(search.toLowerCase())
      )
    : repos;

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <GitBranch size={20} className="text-accent" />
            Repositories
          </h2>
          <button
            onClick={refetch}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          )}
        </div>

        {/* Search */}
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search repositories..."
            className="pl-9 pr-3 py-2 w-full sm:w-72 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Repo grid */}
      {loading && repos.length === 0 ? (
        <ReposGridSkeleton />
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-500 text-sm">
          {search ? "No repositories match your search" : "No repositories found"}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {filtered.map((repo) => (
            <button
              key={repo.full_name}
              onClick={() => navigate(`/repos/${repo.owner}/${repo.repo}`)}
              className="bg-surface-light border border-border rounded-xl p-4 text-left hover:border-accent/50 hover:bg-surface-lighter/50 transition-all group"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-accent group-hover:text-accent-hover truncate">
                      {repo.full_name}
                    </span>
                    {repo.private && (
                      <Lock size={12} className="text-gray-500 shrink-0" />
                    )}
                  </div>
                </div>
                {repo.stars > 0 && (
                  <span className="flex items-center gap-1 text-xs text-gray-500 shrink-0">
                    <Star size={12} />
                    {repo.stars}
                  </span>
                )}
              </div>
              {repo.description && (
                <p className="text-xs text-gray-400 mb-3 line-clamp-2">
                  {repo.description}
                </p>
              )}
              <div className="flex items-center gap-3 text-xs text-gray-500">
                {repo.language && (
                  <span className="flex items-center gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        LANG_COLORS[repo.language] || "bg-gray-500"
                      }`}
                    />
                    {repo.language}
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <GitBranch size={12} />
                  {repo.default_branch}
                </span>
                {repo.updated_at && (
                  <span>Updated {formatDate(repo.updated_at)}</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
